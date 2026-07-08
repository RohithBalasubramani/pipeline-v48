"""layer1b/resolve/asset_resolve.py — PURE-AI asset resolution: confident pin / ambiguous candidates / empty / pinned.
The AI resolves by NAME, never by registry id: the lt_mfm id is off-by-one from the unit number in the name
('Transformer 6' = id 7), so a model that emits an id reliably mis-pins to an adjacent sibling (and crosses class,
e.g. DG-08 -> RTCC Panel). We hide the id column from the model and map its VERBATIM name back to the registry row
deterministically (exact, then space/punctuation/case-insensitive), so the readable name is authoritative and the id
is looked up, never guessed. [spec section 2 L1b, #14; batch root-cause: asset_name_mismatch (11/66)]

HARDENING (silent-empty family): an implied-asset prompt can no longer dead-end in how='empty' —
  · an LLM transport failure ({} from fail-open call_qwen) is retried ONCE (guardrail/retry_one) and, if still dead,
    surfaces the browse picker via empty_fallback (class-narrowed when a prior exists) + llm_failed telemetry;
  · `confident` DEFAULTS FALSE when the key is absent (a half-parsed emission is not a confident nothing);
  · paraphrased/typo'd names recover as AMBIGUOUS candidates via guardrail/spelling_recovery (never a confident pin);
  · every outcome carries class_prior + class_mismatch telemetry (guardrail/same_family_gate — telemetry, NOT a gate).
"""
import os
import re

from llm.client import call_qwen
from layer1b.resolve.asset_candidates import asset_candidates, as_asset
from layer1b.resolve.no_data_gate import no_data_outcome
from layer1b.resolve.pinned_skip import pinned_skip
from layer1b.resolve.class_from_subject import class_from_subject, candidates_of_class
from layer1b.resolve.confident_pin import confident_pin
from layer1b.resolve.ambiguous_candidates import ambiguous_candidates
from layer1b.resolve.member_scope import member_scope
from layer1b.resolve.empty_fallback import empty_fallback
from layer1b.resolve.answer_schema import asset_answer_schema
from layer1b.guardrail.retry_one import retry_once
from layer1b.guardrail.spelling_recovery import fuzzy_rows
from layer1b.guardrail.same_family_gate import class_mismatch

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_prompt(name):
    with open(os.path.join(_HERE, "prompts", name)) as f:
        return f.read()


def _norm(s):
    """space/punctuation/case-insensitive match key: 'PCC Panel 2 A' == 'pcc panel 2a' == 'PCC-Panel-2A'."""
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _is_ghost(row):
    """A candidate that can NEVER render — a `_sch`/dead disambiguation stub (table_exists flag, index 9, is False;
    fail-open to renderable when the column is absent). Such a row is never a confident pin; the caller falls through to
    the model's candidate list / no-data handling. [P03]"""
    return len(row) > 9 and not row[9]


def _pcc_alias_index():
    """{normalized_alias: canonical_panel_name} from cmd_catalog.pcc_panel_alias (the CMD_V2 PCC panel naming brought
    into our DB — PCC-1A/1B/2A…/Panel-N → PCC-Panel-N). {} on the equipment.alias knob being off or any outage — a
    dictionary of facts, not a heuristic; the canonical name stays the return contract. [#3]"""
    try:
        from config.app_config import cfg
        if str(cfg("equipment.alias.enabled", "on")).strip().lower() in ("off", "", "0", "false", "no", "none"):
            return {}
        from data.db_client import q
        return {_norm(a): pn for a, pn in q("cmd_catalog", "SELECT alias, panel_name FROM pcc_panel_alias")
                if a and pn}
    except Exception:
        return {}


def resolve_asset(prompt, asset_id_override=None):
    cands = asset_candidates()
    by_id = {str(c[0]): c for c in cands}

    # PIPELINE_ASSET_ID round-trip: the user already picked -> skip resolution (delegated to pinned_skip: honors the
    # exact pin, no de-dup, but still runs the no_data gate so an empty pick surfaces NO-DATA not a blank card). [#14]
    pinned = pinned_skip(asset_id_override, by_id)
    if pinned is not None:
        # the pinned path returns BEFORE _finish, so stamp the PANEL READING DIRECTION here too — the ORIGINAL prompt
        # ('incomer PCC-1A') still drives member_scope on the picker-repick, so a picked panel honors incomer vs
        # outgoing instead of silently defaulting to outgoing. [panel_overview — pinned-path parity]
        _pa = pinned.get("asset")
        if isinstance(_pa, dict):
            _pa["member_scope"] = member_scope(prompt)
        return pinned

    # CLASS PRIOR: infer the equipment class from the prompt subject/metric and narrow the listing shown to the AI, so
    # a bare/implied class with no unit number is resolved within the right class instead of across all 310 rows. The
    # prior only NARROWS (fail-open to the full list; None on multi-class ambiguity) — see class_from_subject. [RN-06]
    prior = class_from_subject(prompt)
    listed = candidates_of_class(cands, prior)

    # NAME -> registry row (deterministic). by_norm carries ALL rows for a normalized key, so a name that collides
    # across rows surfaces as ambiguous rather than an arbitrary pick. Resolution maps against the FULL registry (not
    # just the class-narrowed listing) so a verbatim name the AI copies always maps back even if the prior mis-narrowed.
    # by_alias [stream C]: the equipment-registry HUMAN aliases (row idx 10) resolve too — canonical wins first, a
    # UNIQUE normalized alias resolves last, an alias collision NEVER pins (falls to the ambiguous path).
    by_name = {c[1]: c for c in cands}
    by_norm, by_alias = {}, {}
    for c in cands:
        by_norm.setdefault(_norm(c[1]), []).append(c)
        if len(c) > 10 and c[10]:
            by_alias.setdefault(_norm(c[10]), []).append(c)
    # PCC PANEL alias index [#3, cmd_catalog.pcc_panel_alias]: EVERY CMD_V2 panel alias (PCC-1A/1B/2A/…/Panel-1) →
    # its canonical PCC-Panel-N row, so a prompt spelling any of them resolves the panel even when the AI echoes the
    # alias rather than the canonical name. Fail-open ({} on outage/knob-off) — the equipment.alias knob gates it.
    for _al, _pn in _pcc_alias_index().items():
        _row = by_name.get(_pn)
        if _row is not None:
            by_alias.setdefault(_al, []).append(_row)

    def resolve_name(name):
        if name in by_name:                                            # exact verbatim copy
            return by_name[name]
        rows = by_norm.get(_norm(name))                                # space/punct/case-insensitive canonical
        if rows:
            return rows[0] if len(rows) == 1 else None                 # unique-or-None (collisions -> ambiguous)
        arows = by_alias.get(_norm(name))                              # equipment/PCC alias (hint) [stream C, #3]
        if not arows:
            return None
        ids = {r[0] for r in arows}                                    # dedup by registry id: the SAME row reached via
        return arows[0] if len(ids) == 1 else None                    # two alias sources (display aka + pcc index) is
        #                                                               NOT a collision; only DISTINCT rows are ambiguous

    def _class_rows():
        """The prior-class listing, data-bearing first (dead-meter-honest picker default)."""
        return [c for c in listed if c[6]] or listed

    def _finish(outcome):
        """Attach the resolution telemetry every outcome carries (surfaced by run/harness stage + the FE picker)."""
        outcome["class_prior"] = prior
        outcome["llm_failed"] = llm_failed
        outcome["class_mismatch"] = class_mismatch(prior, outcome.get("asset"), outcome.get("candidates"))
        # PANEL READING DIRECTION [panel_overview]: stamp the prompt's incomer-vs-outgoing choice on the resolved asset
        # so the Layer-2 PANEL MEMBERS facts + the panel-aggregate fill read ONE decision. Default 'outgoing' (the fed
        # feeders/bays) — the single-asset render is byte-identical (the flag is consulted only for has_feeders panels).
        asset = outcome.get("asset")
        if isinstance(asset, dict):
            asset["member_scope"] = member_scope(prompt)
        return outcome

    # listing has NO id column: the model must reason over name/class/load_group only, never registry ids. The
    # NO-DATA flag marks empty/never-wired meters: the model should PREFER data-bearing assets and only resolve to a
    # NO-DATA one when the prompt explicitly names it (we then return the no_data outcome).
    listing = "\n".join(
        f"{c[1]}\t{c[5]}\t{c[4]}\t{'NO-DATA' if not c[6] else ''}\t{c[10] if len(c) > 10 else ''}" for c in listed
    )
    # the LIVE class vocabulary is injected verbatim so the prompt's class rule can never drift from the registry
    classes_present = ", ".join(sorted({c[5] for c in cands if c[5]}))
    system = _load_prompt("asset_system.md")
    user = (f"CANDIDATES (name<TAB>class<TAB>load_group<TAB>flag<TAB>aka):\n{listing}\n\n"
            f"CLASSES PRESENT IN THE REGISTRY: {classes_present}\n"
            f"PROMPT: {prompt!r}\nJSON:")
    # stage='asset_resolve' names this call site in llm/obs failure telemetry (before: outage entries bucketed
    # stage='-') AND keys the per-stage timeout INSIDE the client from the SAME app_config row this line used to read
    # locally (llm.timeout.asset_resolve; base llm.timeout fallback) — one config path, no duplicate cfg lookup.
    # [AI_QUALITY_BACKLOG item 15]
    # json_schema [item 17, DEFAULT OFF]: asset_answer_schema() reads the flag row llm.guided_json.asset_resolve —
    # 'off'/absent → None → the request is byte-identical to before; 'on' → vLLM guided decoding pins the reply to
    # {"names":[...],"confident":bool,"candidates":[...]} so an unparseable emission is impossible.
    res, llm_failed = retry_once(lambda: call_qwen(system, user, stage="asset_resolve",
                                                   json_schema=asset_answer_schema()))

    if llm_failed:
        # the model was NEVER HEARD (transport/parse failure twice) — honest degrade to the browse picker (class-
        # narrowed when a class was implied), never a silent how='empty' with no candidates. [hardening]
        return _finish(empty_fallback(prompt, rows=(_class_rows() if prior else None)))

    confident = bool(res.get("confident", False))                     # absent key ≠ confident (was fail-open True)
    names = [n for n in (res.get("names") or []) if n]
    cand_names = [n for n in (res.get("candidates") or []) if n]
    picks = [r for r in (resolve_name(n) for n in names) if r]
    cand_rows = [r for r in (resolve_name(n) for n in cand_names) if r]

    # AI-FIRST RESOLUTION [deterministic name-collision override REMOVED 2026-07-09]: the lexical token-match gate that
    # used to pre-empt the model — forcing a deterministic homonym picker AHEAD of the AI — is deleted. It OVERRODE
    # CORRECT AI ANSWERS: 'PCC-1A' collides lexically with the four PCC-01 transformer meters, yet the model resolves it
    # to PCC-Panel-1 CONFIDENTLY (empirically verified) — the gate threw that away and showed 4 wrong transformers. The
    # MODEL now OWNS the end-user outcome: a confident pin stands; genuine ambiguity surfaces the MODEL'S OWN candidate
    # list (the ambiguous branch below). Homonym recall/precision is an AI-GROUNDING concern (candidate context + the
    # asset_system.md confident-vs-ambiguous contract), never a lexical override. colliding_rows/uniquely_named are no
    # longer consulted here. [AI-first: no deterministic list to the end user]
    if confident and picks and not _is_ghost(picks[0]):             # the model confidently pinned a RENDERABLE asset...
        asset = confident_pin(picks[0], cands)
        # ...has data? render. else NO-DATA (carrying onward-pick alternatives so the picker is never a dead end).
        return _finish(no_data_outcome(asset, cands) or {"asset": asset, "how": "AI", "candidates": []})
    # a confident pin on a GHOST (table_exists=False, `_sch`/dead stub) can never render → NOT a pin; falls through to
    # the model's candidate list / no-data handling below (honest, no deterministic re-point). [P03]

    unresolved = [n for n in names + cand_names if resolve_name(n) is None]
    if not picks and not cand_rows and unresolved:
        # the model NAMED something but paraphrased/typo'd it — fuzzy-recover as AMBIGUOUS candidates (never a pin)
        fuzzy = fuzzy_rows(unresolved, cands)
        if fuzzy:
            return _finish(ambiguous_candidates(fuzzy, cands))

    if confident and not picks and not cand_rows:
        if prior or unresolved:
            # an asset WAS implied (class prior / unresolvable names) — 'empty' would be a dead end; open the picker
            return _finish(empty_fallback(prompt, rows=(_class_rows() if prior else None)))
        return _finish({"asset": None, "how": "empty", "candidates": []})    # genuine pure-metric prompt, no asset

    crows = cand_rows or picks
    if not crows:
        crows = _class_rows() if prior else ([c for c in cands if c[6]] or cands)   # surface DATA-bearing meters
    # ambiguous_candidates de-dups by registry id and leads with data-bearing rows so the picker never leads with dead
    # meters. (No twin de-dup: each registry row is its own device — device_mappings prove no true twins. [F5, RN-06])
    return _finish(ambiguous_candidates(crows, cands))
