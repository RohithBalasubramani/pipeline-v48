"""layer1b/resolve/asset_resolve.py — PURE-AI asset resolution: confident pin / ambiguous candidates / empty / pinned.
The AI resolves by NAME, never by registry id: the lt_mfm id is off-by-one from the unit number in the name
('Transformer 6' = id 7), so a model that emits an id reliably mis-pins to an adjacent sibling (and crosses class,
e.g. DG-08 -> RTCC Panel). We hide the id column from the model and map its VERBATIM name back to the registry row
deterministically (exact, then space/punctuation/case-insensitive), so the readable name is authoritative and the id
is looked up, never guessed. [spec section 2 L1b, #14; batch root-cause: asset_name_mismatch (11/66)]

HARDENING (silent-empty family): an implied-asset prompt can no longer dead-end in how='empty' —
  · a TRANSIENT LLM transport failure is retried once (llm/transient_retry — deterministic timeouts fail fast) and, if still dead,
    surfaces the browse picker via empty_fallback (class-narrowed when a prior exists) + llm_failed telemetry;
  · `confident` DEFAULTS FALSE when the key is absent (a half-parsed emission is not a confident nothing);
  · paraphrased/typo'd names recover as AMBIGUOUS candidates via guardrail/spelling_recovery (never a confident pin);
  · every outcome carries class_prior + class_mismatch telemetry (guardrail/same_family_gate — telemetry, NOT a gate).
"""
import os
from llm.prompt_load import load as _prompt_load
import re

from llm.client import call_qwen
from layer1b.resolve.asset_candidates import asset_candidates
from layer1b.resolve.no_data_gate import no_data_outcome
from layer1b.resolve.pinned_skip import pinned_skip
from layer1b.resolve.class_from_subject import class_from_subject, candidates_of_class
from layer1b.resolve.confident_pin import confident_pin
from layer1b.resolve.ambiguous_candidates import ambiguous_candidates
from layer1b.resolve.empty_fallback import empty_fallback
from layer1b.resolve.answer_schema import asset_answer_schema
from llm.transient_retry import retry_transient_result
from layer1b.guardrail.spelling_recovery import fuzzy_rows
from layer1b.guardrail.same_family_gate import class_mismatch

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_prompt(name):
    return _prompt_load(_HERE, name)   # the ONE loader (llm/prompt_load, D8); errors="replace" house default


from layer1b.normalize import norm as _norm  # the ONE asset-name match key (D9)


def _is_ghost(row):
    """A candidate that can NEVER render — a `_sch`/dead disambiguation stub (table_exists flag, index 9, is False;
    fail-open to renderable when the column is absent). Such a row is never a confident pin; the caller falls through to
    the model's candidate list / no-data handling. [P03]"""
    return len(row) > 9 and not row[9]


def _full_listing_on():
    """resolver.full_listing [T0-7]: show the model the FULL registry instead of the class-prior-narrowed subset.
    Never raises; absent row / DB outage → off (byte-identical legacy narrowing)."""
    try:
        from config.app_config import flag_on
        return flag_on("resolver.full_listing")
    except Exception:
        return False


def _section_ai_on():
    """resolver.section_ai [T0-9]: the model emits `section` ('A'/'B'/'both'/'none') and panel_sections validates it
    against pcc_panel_alias facts (fixing the elided 'compare pcc 1a and 1b' the substring detector misses). Never
    raises; off → byte-identical (schema + prompt clause + parse all collapse; the substring detector stays)."""
    try:
        from config.app_config import flag_on
        return flag_on("resolver.section_ai")
    except Exception:
        return False


def _member_direction_ai_on():
    """resolver.member_direction_ai [T1-10]: the model emits `member_direction` (incomer/outgoing) in its existing
    call; enum-clamped + validated against the keyword scan fallback. Never raises; off → byte-identical."""
    try:
        from config.app_config import flag_on
        return flag_on("resolver.member_direction_ai")
    except Exception:
        return False


_SECTION_NORMALIZE = {"a": "A", "b": "B", "both": "both", "none": "none"}


# BUS-SECTION facts + the ONE stamping site moved to layer1b/resolve/panel_sections.py [T0-8, atomic-structure].
# Byte-compat re-exports: _alias_rescue + external readers keep their names; the STAMPING now goes through
# panel_sections.stamp_section_facts (the pinned path and _finish used to duplicate it inline).
from layer1b.resolve.panel_sections import (  # noqa: E402,F401
    pcc_section_index as _pcc_section_index, panel_section, compare_sections, stamp_section_facts)


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


def resolve_asset(prompt, asset_id_override=None, cands=None):
    # `cands` [compare-share fix]: the natural-compare per-name resolver fans 3-5 CONCURRENT resolve_asset calls; each
    # re-running asset_candidates() fired 3-5 simultaneous ~250-table has_data probes over the flaky :5433 tunnel —
    # slow, contending, and outage-raising (two probes flapped -> two sub-resolves errored -> the compare silently
    # bailed to single). The caller that already HOLDS the candidate list passes it; default None keeps every other
    # call site byte-identical.
    cands = cands if cands is not None else asset_candidates()
    by_id = {str(c[0]): c for c in cands}

    # PIPELINE_ASSET_ID round-trip: the user already picked -> skip resolution (delegated to pinned_skip: honors the
    # exact pin, no de-dup, but still runs the no_data gate so an empty pick surfaces NO-DATA not a blank card). [#14]
    pinned = pinned_skip(asset_id_override, by_id)
    if pinned is not None:
        # the pinned path returns BEFORE _finish, so stamp the PANEL READING DIRECTION here too — the ORIGINAL prompt
        # ('incomer PCC-1A') still drives member_scope on the picker-repick, so a picked panel honors incomer vs
        # outgoing instead of silently defaulting to outgoing. [panel_overview — pinned-path parity]
        stamp_section_facts(pinned.get("asset"), prompt)    # AI-free pinned path: detector-only stamps [sections]
        return pinned

    # CLASS PRIOR: infer the equipment class from the prompt subject/metric and narrow the listing shown to the AI, so
    # a bare/implied class with no unit number is resolved within the right class instead of across all 310 rows. The
    # prior only NARROWS (fail-open to the full list; None on multi-class ambiguity) — see class_from_subject. [RN-06]
    # FULL LISTING [T0-7, flag resolver.full_listing — AI-first]: the keyword prior can MIS-narrow ('temperature in
    # the transformer room' hides non-Transformer rows the model would pick correctly from the full list). Flag on →
    # the model sees EVERY candidate; the prior is KEPT for class_mismatch telemetry + the class-narrowed
    # empty-fallback picker (_class_rows iterates _narrowed, never the widened listing). Flag off → byte-identical.
    prior = class_from_subject(prompt)
    _narrowed = candidates_of_class(cands, prior)
    listed = cands if _full_listing_on() else _narrowed

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
        """The prior-class listing, data-bearing first (dead-meter-honest picker default). Reads _narrowed, NOT
        `listed` — under resolver.full_listing the empty-fallback picker must stay class-narrowed [T0-7]."""
        return [c for c in _narrowed if c[6]] or _narrowed

    def _alias_rescue(outcome):
        """★ ALIAS-DICTIONARY RESCUE [sections]: the model returned AMBIGUOUS between PCC panels, but every sectioned
        panel alias the prompt spells maps to ONE canonical panel row (cmd_catalog.pcc_panel_alias — dictionary FACTS,
        not a lexical heuristic): 'pcc 1a and pcc 1b' IS PCC-Panel-1, its two bus sections. A dictionary-clear mention
        is not genuine ambiguity — the model was observed flip-flopping this exact prompt (pin one run, Panel-1-vs-
        Panel-2 picker the next). POST-AI only: a confident pin is NEVER overridden (the deleted pre-AI collision gate
        stays deleted); the rescue fires only on an all-panel ambiguous outcome, and fail-opens to the model's own
        candidate list."""
        try:
            if outcome.get("asset") is not None or outcome.get("how") != "ambiguous":
                return outcome
            cands_out = outcome.get("candidates") or []
            if not cands_out or any(str(c.get("class") or "").strip().lower() != "panel" for c in cands_out):
                return outcome
            p = _norm(prompt)
            hit = {pn for al, (pn, _sec) in _pcc_section_index().items() if al in p}
            if len(hit) != 1:
                return outcome
            row = by_name.get(next(iter(hit)))
            if row is None or _is_ghost(row):
                return outcome
            asset = confident_pin(row, cands)
            return no_data_outcome(asset, cands) or {"asset": asset, "how": "alias-dictionary", "candidates": []}
        except Exception:
            return outcome

    def _finish(outcome):
        """Attach the resolution telemetry every outcome carries (surfaced by run/harness stage + the FE picker)."""
        outcome = _alias_rescue(outcome)
        outcome["class_prior"] = prior
        outcome["llm_failed"] = llm_failed
        outcome["class_mismatch"] = class_mismatch(prior, outcome.get("asset"), outcome.get("candidates"))
        # PANEL READING DIRECTION + BUS-SECTION facts [panel_overview/sections]: ONE stamping site
        # (panel_sections.stamp_section_facts) — member_scope + section + compare_sections; the pinned path calls the
        # same helper (parity by construction). `_ai_section`/`_ai_member_direction` (closure vars set after the
        # resolve call; None when the flag is off / llm_failed / pinned) are VALIDATED inside the helper.
        stamp_section_facts(outcome.get("asset"), prompt, ai_section=_ai_section,
                            ai_member_direction=_ai_member_direction)
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
    if _section_ai_on():                                  # T0-9: teach the optional `section` key (flag off → byte-identical)
        system = system + "\n" + _load_prompt("asset_section_clause.md")
    if _member_direction_ai_on():                         # T1-10: teach the optional `member_direction` key
        system = system + "\n" + _load_prompt("asset_member_direction.md")
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
    # transient-only retry [no-retry rule]: a deterministic timeout/truncation fails FAST (retrying doubles the
    # hang); a transport blip is re-sent once. llm_failed = the model was NEVER HEARD (marker survived every attempt).
    # DECISION INSPECTOR: the class-narrowed registry listing IS the option set shown to the model — declared per
    # attempt (call_qwen clears the context when it returns) so the llm event's `decision` carries it. The id column
    # stays hidden from the candidates view too, matching the resolve-by-NAME contract.
    from obs import llm_tap

    def _call():
        llm_tap.set_decision(kind="selection", candidate_kind="asset",
                             candidates=[{"name": c[1], "class": c[5], "load_group": c[4], "has_data": bool(c[6]),
                                          "aka": (c[10] if len(c) > 10 and c[10] else None)} for c in listed],
                             class_prior=prior)
        return call_qwen(system, user, stage="asset_resolve",
                         json_schema=asset_answer_schema(), on_error="marker")

    res, llm_failed = retry_transient_result(_call)
    # T0-9/T1-10: the model's optional bus-section + reading-side emissions (None unless the flag + a clean answer).
    # Normalized to the panel_sections vocabulary; validated against the alias facts / clamped to the enum inside
    # stamp_section_facts (called by _finish). Closure vars — set here (after the resolve call), read there.
    _ai_section = None
    _ai_member_direction = None
    if not llm_failed and _section_ai_on():
        _ai_section = _SECTION_NORMALIZE.get(str((res or {}).get("section") or "").strip().lower())
    if not llm_failed and _member_direction_ai_on():
        _v = str((res or {}).get("member_direction") or "").strip().lower()
        _ai_member_direction = _v if _v in ("incomer", "outgoing") else None

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
    # ★ AI COMPARE SET [AI-first compare — the lexical detector is DELETED]: the model confidently named 2+ DISTINCT
    # renderable assets, so IT decided this is a compare. The answer schema always returned `names` as a LIST; the old
    # deterministic `named_full_rows` substring detector (which missed elided lists like 'pcc 1 and 2' — the "2" never
    # sat next to "pcc") is gone. Surface every distinct pick as `compare_ids` so the host short-circuits to the author-
    # once-per-class multi assembler. `asset`=picks[0] stays the primary pin, so a single-asset consumer of the outcome
    # (or a host that ignores compare_ids) is byte-identical and still renders ONE real panel — never a crash.
    if confident:
        _distinct, _seen = [], set()
        for p in picks:
            if not _is_ghost(p) and p[0] not in _seen:
                _seen.add(p[0]); _distinct.append(p)
        # PRIMARY PIN MUST BE DATA-BEARING [no_data-gate parity — property P1]: how='AI' promises a renderable,
        # data-bearing asset to every single-asset consumer of the outcome. A dark comparand stays IN compare_ids
        # (its lane honest-blanks per-leaf in the multi assembler), but it can never be the primary; all-dark →
        # fall through to the single-pick path below, whose no_data_outcome handles it honestly.
        _primary = next((p for p in _distinct if p[6]), None)
        if len(_distinct) >= 2 and _primary is not None:
            return _finish({"asset": confident_pin(_primary, cands), "how": "AI", "candidates": [],
                            "compare_ids": [p[0] for p in _distinct]})

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
