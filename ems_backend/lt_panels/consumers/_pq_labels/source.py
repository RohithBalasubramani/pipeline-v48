"""Load-source classification + its follow-on recommendation.

`pq_likely_source_label` names the offending load type; `pq_next_priority_label`
turns the current critical issue into the recommended next action.
"""
from __future__ import annotations

from .helpers import _ord
from .issues import derive_critical_issue_type
from .thresholds import V_UNBALANCE_WARN_PCT


# ── 4. pq_likely_source_label ──────────────────────────────────────────
def derive_likely_source(row):
    """Heuristic classification of the load type causing distortion.

    Reads dominant harmonic order(s) + K-factor + unbalance to pick
    a short signature label that drives the "Likely Source" tile.
    """
    dom  = row.get('dominant_harmonic_order')
    sec  = row.get('pq_dominant_harmonic_secondary')
    kf   = row.get('k_factor') or 0
    unb  = row.get('voltage_unbalance_pct') or 0
    pf   = row.get('power_factor_total') or 1.0

    # 6-pulse rectifier signature
    if dom in (5, 7) or sec in (5, 7):
        if kf > 4:
            return 'VFD / 6-pulse rectifier'
        return 'Non-linear rectifier load'

    # 12-pulse rectifier
    if dom in (11, 13) or sec in (11, 13):
        if pf < 0.9:
            return '12-pulse rectifier'
        return 'High-order harmonic load'

    # Single-phase / triplen dominance
    if dom == 3 or sec == 3:
        if unb > V_UNBALANCE_WARN_PCT:
            return 'Single-phase non-linear load'
        return 'Triplen-harmonic load'

    # Mixed signature
    if dom is not None and kf > 2:
        return 'Mixed nonlinear load'

    return 'Linear / balanced load'


# ── 5. pq_next_priority_label ───────────────────────────────────────────
def derive_next_priority(row):
    """Recommendation derived from the active critical issue."""
    issue = derive_critical_issue_type(row)
    if issue == 'Voltage Imbalance':
        return 'Balance phase loads'
    if issue == 'Harmonic Distortion':
        dom = row.get('dominant_harmonic_order')
        if dom:
            label = _ord(dom)
            return f'Add {label} harmonic filter'
        return 'Add harmonic filter'
    if issue == 'PF Drop':
        return 'Improve PF margin'
    if issue == 'Sag/Swell Events':
        return 'Tighten upstream regulation'
    return 'Monitor'
