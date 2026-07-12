"""tools/payload_diff/align.py — pair the cards of two executions. Identity = extract.card_key (asset-tag + 1a card_id),
which survives same-prompt re-runs, code/config changes, and multi-asset compares. Keys present in only one execution
are 'added'/'removed' — the honest answer for a different-prompt diff too (a shared catalog card on both pages still
pairs; the rest genuinely differ)."""


def align(view_a, view_b):
    """Two {key: ...} card views → (paired_keys, only_a, only_b), page order preserved (A's order, then B's extras)."""
    paired = [k for k in view_a if k in view_b]
    only_a = [k for k in view_a if k not in view_b]
    only_b = [k for k in view_b if k not in view_a]
    return paired, only_a, only_b
