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
from layer1b.resolve.name_collision import is_collision, colliding_rows, uniquely_named
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


def resolve_asset(prompt, asset_id_override=None):
    cands = asset_candidates()
    by_id = {str(c[0]): c for c in cands}

    # PIPELINE_ASSET_ID round-trip: the user already picked -> skip resolution (delegated to pinned_skip: honors the
    # exact pin, no de-dup, but still runs the no_data gate so an empty pick surfaces NO-DATA not a blank card). [#14]
    pinned = pinned_skip(asset_id_override, by_id)
    if pinned is not None:
        return pinned

    # CLASS PRIOR: infer the equipment class from the prompt subject/metric and narrow the listing shown to the AI, so
    # a bare/implied class with no unit number is resolved within the right class instead of across all 310 rows. The
    # prior only NARROWS (fail-open to the full list; None on multi-class ambiguity) — see class_from_subject. [RN-06]
    prior = class_from_subject(prompt)
    listed = candidates_of_class(cands, prior)

    # NAME -> registry row (deterministic). by_norm carries ALL rows for a normalized key, so a name that collides
    # across rows surfaces as ambiguous rather than an arbitrary pick. Resolution maps against the FULL registry (not
    # just the class-narrowed listing) so a verbatim name the AI copies always maps back even if the prior mis-narrowed.
    by_name = {c[1]: c for c in cands}
    by_norm = {}
    for c in cands:
        by_norm.setdefault(_norm(c[1]), []).append(c)

    def resolve_name(name):
        if name in by_name:                                            # exact verbatim copy
            return by_name[name]
        rows = by_norm.get(_norm(name))                                # space/punct/case-insensitive
        return rows[0] if rows and len(rows) == 1 else None            # unique-or-None (collisions -> ambiguous)

    def _class_rows():
        """The prior-class listing, data-bearing first (dead-meter-honest picker default)."""
        return [c for c in listed if c[6]] or listed

    def _finish(outcome):
        """Attach the resolution telemetry every outcome carries (surfaced by run/harness stage + the FE picker)."""
        outcome["class_prior"] = prior
        outcome["llm_failed"] = llm_failed
        outcome["class_mismatch"] = class_mismatch(prior, outcome.get("asset"), outcome.get("candidates"))
        return outcome

    # listing has NO id column: the model must reason over name/class/load_group only, never registry ids. The
    # NO-DATA flag marks empty/never-wired meters: the model should PREFER data-bearing assets and only resolve to a
    # NO-DATA one when the prompt explicitly names it (we then return the no_data outcome).
    listing = "\n".join(
        f"{c[1]}\t{c[5]}\t{c[4]}\t{'NO-DATA' if not c[6] else ''}" for c in listed
    )
    # the LIVE class vocabulary is injected verbatim so the prompt's class rule can never drift from the registry
    classes_present = ", ".join(sorted({c[5] for c in cands if c[5]}))
    system = _load_prompt("asset_system.md")
    user = (f"CANDIDATES (name<TAB>class<TAB>load_group<TAB>flag):\n{listing}\n\n"
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

    # NAME-COLLISION GATE [F5/F6] — deterministic on the PROMPT, ahead of every AI-driven branch. When the prompt's
    # asset token (class+unit) maps to >1 distinct RENDERABLE registry row (DG-3 legacy meter vs DG-03 [Jackson]; the
    # three real UPS-04s across GIC nodes; the five UPS-01s), the user's intent is genuinely ambiguous:
    #   · a confident single pin would be a fabrication of certainty (F5 — the AI picked the Jackson genset / a Laminator
    #     feeder for a legacy meter / a real UPS);
    #   · the AI's own ambiguous candidate list has BROKEN RECALL (F6 — it dropped the correctly-named GIC-01-N3-UPS-01
    #     and leaked a UPS-07). The colliding set is computed registry-wide from the token, so the right-named asset is
    #     ALWAYS present and wrong-unit rows never leak, regardless of what the AI emitted. Ghost rows are already
    #     excluded by colliding_rows, which also drops the P03 `_sch` ghost.
    crows_tok = colliding_rows(prompt, cands)
    if len(crows_tok) > 1:
        named = uniquely_named(prompt, crows_tok)                    # the prompt spelled ONE colliding row out in full?
        if named is not None:
            # the user typed the whole discriminating name ('GIC-01-N3-UPS-01') — deterministic pin, no picker. Skip the
            # collision gate AND the AI's (possibly wrong) pick; the full name is authoritative.
            asset = confident_pin(named, cands)
            return _finish(no_data_outcome(asset, cands) or {"asset": asset, "how": "AI", "candidates": []})
        return _finish(ambiguous_candidates(crows_tok, cands))       # genuine homonym → picker (F5/F6)

    if confident and picks:                                          # asked asset resolved (non-colliding token)...
        # GHOST-PIN GUARD [P03]: the AI may confidently name a `_sch`/dead disambiguation ghost (table_exists=False —
        # physically no neuract table, e.g. a lone Transformer with only a ghost row). A ghost can never render, so it is
        # NEVER a confident pin: re-point to renderable same-token rows if any exist (picker), else fall to no_data.
        if len(picks[0]) > 9 and not picks[0][9]:
            renderable = colliding_rows(prompt, cands)
            if renderable:
                return _finish(ambiguous_candidates(renderable, cands))
        asset = confident_pin(picks[0], cands)
        # ...has data? render. else NO-DATA (carrying onward-pick alternatives so the picker is never a dead end).
        return _finish(no_data_outcome(asset, cands) or {"asset": asset, "how": "AI", "candidates": []})

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
