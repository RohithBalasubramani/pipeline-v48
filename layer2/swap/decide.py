"""layer2/swap/decide.py — the deterministic swap gate (ported from v47 layer2_swap.run). KEEP unless EVERY rule holds.
Resolves swap_decision.origin (kept|swapped|must_swap). [spec §2 L2, contract 5 swap_decision]

RENDERABILITY ENFORCER (user rule 1): after the normal AI/gate resolution, if the CURRENT card CANNOT render REAL DATA
it is FORCE-swapped to a render_real pool candidate — deterministically, overriding whatever the AI wanted. Two triggers:
(a) the STATIC card_feasibility.verdict IN drop/no_data (this KIND of card never renders); (b) the AI's own per-asset
verdict answerability='none' (`answerability` kwarg) — a catalog-renderable card WHOLLY unfillable for THIS asset (every
leaf honest-blanks: Fuel Tank on a fuel-less DG). No unclaimed candidate → honest KEEP. [gate_force_renderable, #1]"""
from layer2.swap import vocab as _swapvocab   # the ONE swap vocab home [typing F5]
from layer2.swap import (gate_confidence, gate_vague_reject, gate_criterion_story, gate_pool_valid,
                         gate_no_dup, combo_cascade, gate_force_renderable)


def gate(decision, *, pool_ids, template_card_ids, already_chosen, page_card_ids, current_card_id,
         current_verdict=None, pool=None, answerability=None, story=None):
    """Return the resolved swap_decision (action/origin/swap_to_id). Default KEEP; honor SWAP only if all gates pass.

    When `current_verdict` marks the current card UNRENDERABLE (config.feasibility.UNRENDERABLE_VERDICTS), the
    RENDERABILITY ENFORCER overrides the result: force-swap to the closest candidate in `pool` (already filtered to
    render_real + recoverable-default + registered renderer by candidates.py) that is NOT in `already_chosen`,
    or KEEP+flag if none. `pool` = the slot's swap_candidates (list of {card_id,title,...}); `pool_ids` = their ids."""
    d = dict(decision or {})
    # T1-12: capture the AI's OWN swap target BEFORE the gates normalize it away — a DATALESS force-swap may honor this
    # nomination (gate_force_renderable, DB knob swap.dataless_nomination, default off) even when the gate chain reset it.
    _ai_nom = (decision or {}).get("swap_to_id")
    if d.get("action") != _swapvocab.SWAP:
        d.update(action="keep", origin="kept", swap_to_id=None, swap_to_title=None)
    else:
        passes = (gate_confidence.ok(d)
                  and gate_vague_reject.ok(d)
                  # T1-11 CRITERION<->STORY gate (default off) — AFTER the cheap vague backstop: reject a criterion that
                  # names no word of THIS card's story angle. It is the ONLY gate that leaves a corrective re-emit reason.
                  and gate_criterion_story.ok(d, story)
                  and gate_pool_valid.ok(d, pool_ids)
                  # gate_no_dup already folds template_card_ids into `forbidden`, so the sacred-template guard is here
                  # too (the old separate gate_template_dedup was subsumed and removed, 2026-07-12).
                  and gate_no_dup.ok(d, template_card_ids, already_chosen, page_card_ids)
                  and combo_cascade.ok(d, pool_ids))
        if passes:
            d.update(action="swap", origin="swapped")
        else:
            d.update(action="keep", origin="kept", swap_to_id=None, swap_to_title=None)
            # ONLY the criterion<->story gate leaves a corrective reason, and only when IT is the reason (the cheap
            # gates before it passed) — every other gate stays a silent safe-KEEP. build.py re-emits once on it. [T1-11]
            if (gate_confidence.ok(d) and gate_vague_reject.ok(d)
                    and not gate_criterion_story.ok(d, story)):
                d["gate_reject"] = gate_criterion_story.reject_reason(d, story)
    # RENDERABILITY ENFORCER — runs last, overrides the above only when the current card CANNOT render. [user rule 1]
    # already_chosen is threaded so a forced swap never lands on a target another slot already claimed. [META-04]
    d, forced_kept = gate_force_renderable.enforce(d, verdict=current_verdict, pool=pool,
                                                   already_chosen=already_chosen, answerability=answerability,
                                                   ai_nomination=_ai_nom)
    return d
