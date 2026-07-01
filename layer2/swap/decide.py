"""layer2/swap/decide.py — the deterministic swap gate (ported from v47 layer2_swap.run). KEEP unless EVERY rule holds.
Resolves swap_decision.origin (kept|swapped|must_swap). [spec §2 L2, contract 5 swap_decision]"""
from layer2.swap import (gate_confidence, gate_vague_reject, gate_pool_valid,
                         gate_no_dup, gate_template_dedup, combo_cascade)


def gate(decision, *, pool_ids, template_card_ids, already_chosen, page_card_ids, current_card_id):
    """Return the resolved swap_decision (action/origin/swap_to_id). Default KEEP; honor SWAP only if all gates pass."""
    d = dict(decision or {})
    if d.get("action") != "swap":
        d.update(action="keep", origin="kept", swap_to_id=None, swap_to_title=None)
        return d
    passes = (gate_confidence.ok(d)
              and gate_vague_reject.ok(d)
              and gate_pool_valid.ok(d, pool_ids)
              and gate_no_dup.ok(d, template_card_ids, already_chosen, page_card_ids)
              and gate_template_dedup.ok(d, template_card_ids)
              and combo_cascade.ok(d, pool_ids))
    if passes:
        d.update(action="swap", origin="swapped")
    else:
        d.update(action="keep", origin="kept", swap_to_id=None, swap_to_title=None)
    return d
