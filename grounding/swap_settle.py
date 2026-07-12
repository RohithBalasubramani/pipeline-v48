"""grounding/swap_settle.py — the deterministic swap SETTLE post-pass that runs AFTER the parallel Layer-2 emits.
ZERO AI.

SETTLE — the production runner runs each card's swap emit CONCURRENTLY with an EMPTY `already_chosen` [META-04], so
two slots can independently swap to the SAME off-page target (duplicate card), or a slot can swap to a target another
slot already claimed. This pass replays the swaps DETERMINISTICALLY in a stable order, threading an accumulating
`already_chosen` set: the FIRST (highest-confidence, then lowest card_id) claim wins each target; every later
colliding swap is REVERTED to KEEP (its own byte-identical default still renders).

The POOL FILTER policy (a swap target must be a REGISTERED renderer id [FR-5] AND have a RECOVERABLE default — never
an ungated example payload [META-05]) is enforced on the LIVE path by layer2/swap/candidates.pool, which reads
is_registered() below + grounding.default_assemble.has_default. (The uncalled swappable_pool re-implementation that
lived here was deleted 2026-07-12 — audit layer2-grounding OBS-5 — so the two copies can't drift.)

Every policy (the registered-renderer id set) is an EDITABLE ROW read via config accessors — no hardcoded id list.
Covers: META-04, META-05, FR-5.
"""
from __future__ import annotations

from config import quality_policy as qp
from config import reason_templates as rt


# ── registered-renderer id set (editable policy) [FR-5] ───────────────────────────────────────────
# The set of card_ids that have a front-end renderer (FILL ∪ COMPONENTS ∪ COMPOSE in host/web/src/cmd). A swap target
# outside this set has no renderer → a permanent 'not wired' blank. Kept as a comma-separated editable policy row
# (quality_policy 'registered_card_ids') so it follows the front-end registry without a code edit.
def registered_card_ids():
    raw = qp.txt("registered_card_ids", "")
    out = set()
    for tok in (raw or "").split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.add(int(tok))
    return out


def is_registered(card_id):
    reg = registered_card_ids()
    # empty policy → fail-open (don't block swaps if the registry policy row is unset), so the pipeline never dead-locks
    # on a missing config; the has-default gate still applies.
    return (not reg) or (int(card_id) in reg)


# ── settle collisions [META-04] ─────────────────────────────────────────────────────────────────
def _confidence(decision):
    try:
        return float(decision.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _revert(output, reason_cause, **kw):
    """Deterministically revert a slot's swap to KEEP (its own byte-identical default renders). Records the machine
    reason on the output so the settle is auditable. Mutates + returns the output."""
    sw = dict(output.get("swap_decision") or {})
    sw.update(action="keep", origin="kept", swap_to_id=None, swap_to_title=None,
              settled_revert=True, settle_reason=rt.reason(reason_cause, **kw))
    output["swap_decision"] = sw
    return output


def settle(outputs, *, page_card_ids=None, template_card_ids=None):
    """Deterministic swap-collision settle over the parallel Layer-2 outputs.

    `outputs`          — {card_id: Layer2CardOutput}; each output carries swap_decision {action, origin, swap_to_id,
                         confidence, ...}. Mutated in place (and returned).
    `page_card_ids`    — card_ids already on the page (a swap toward one is a dup).
    `template_card_ids`— card_ids in 1a's template (likewise forbidden).

    Rule: process the slots in a STABLE order (highest swap confidence first, then lowest card_id) and thread an
    accumulating `already_chosen` (page + template + every prior winning render id). The first claim on a target wins;
    any later swap to an already-chosen id, or a swap onto a page/template id, is REVERTED to KEEP. A kept card renders
    its own default, so both slots still render distinct + correct.

    Returns {settled: outputs, already_chosen: set, reverts: [{card_id, target, reason}], swaps: [{card_id, target}]}.
    """
    already = set(int(x) for x in (page_card_ids or [])) | set(int(x) for x in (template_card_ids or []))
    reverts, swaps = [], []

    # order the SWAP slots deterministically: high confidence first, then low card_id (stable, no AI, no randomness).
    def _key(item):
        cid, o = item
        sw = o.get("swap_decision") or {}
        swapping = sw.get("action") == "swap" and sw.get("swap_to_id") is not None
        return (0 if swapping else 1, -_confidence(sw), int(cid))

    for cid, o in sorted(outputs.items(), key=_key):
        sw = o.get("swap_decision") or {}
        if sw.get("action") != "swap" or sw.get("swap_to_id") is None:
            # a KEEP slot renders its own card_id — reserve it so a later swap can't collide onto it.
            already.add(int(cid))
            continue
        tgt = int(sw["swap_to_id"])
        if tgt in already:
            # collision: this target is already claimed (by the page, template, or a higher-priority slot) → revert.
            _revert(o, "swap_dup", target=tgt)
            reverts.append({"card_id": int(cid), "target": tgt,
                            "reason": (o["swap_decision"].get("settle_reason"))})
            already.add(int(cid))                     # the reverted slot now renders its OWN id → reserve it
        else:
            already.add(tgt)                          # this slot wins the target
            swaps.append({"card_id": int(cid), "target": tgt})

    return {"settled": outputs, "already_chosen": already, "reverts": reverts, "swaps": swaps}
