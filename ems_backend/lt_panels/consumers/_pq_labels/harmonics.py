"""Harmonic-order + PF-gap arithmetic derivers."""
from __future__ import annotations


# ── 10. pq_dominant_harmonic_secondary ─────────────────────────────────
def derive_dominant_harmonic_secondary(row):
    """The 2nd-largest harmonic order after dominant_harmonic_order.

    Sorts harmonic_*_pct values desc, returns the order number of the 2nd.
    """
    candidates = [
        (3,  row.get('harmonic_3rd_pct')),
        (5,  row.get('harmonic_5th_pct')),
        (7,  row.get('harmonic_7th_pct')),
        (11, row.get('harmonic_11th_pct')),
        (13, row.get('harmonic_13th_pct')),
    ]
    candidates = [(n, v) for n, v in candidates if v is not None]
    if len(candidates) < 2:
        return None
    candidates.sort(key=lambda t: t[1], reverse=True)
    return candidates[1][0]   # second-largest


# ── 11. pf_displacement_gap — pure arithmetic ─────────────────────────
def derive_pf_displacement_gap(row):
    """kpi_displacement_pf − kpi_true_pf — quantifies harmonic-induced PF loss."""
    dpf = row.get('kpi_displacement_pf')
    tpf = row.get('kpi_true_pf')
    if dpf is None or tpf is None:
        return None
    return round(dpf - tpf, 4)
