"""pq_severity_label — composite severity from IEEE 519 + trend + breach."""
from __future__ import annotations

from .helpers import _max_thd_i, _max_thd_v
from .thresholds import I_THD_LIMIT_PCT, THD_RISING_RATE_PCT_H, V_THD_LIMIT_PCT


# ── 1. pq_severity_label ────────────────────────────────────────────────
def derive_severity(row):
    """Composite severity from IEEE 519 + trend + sustained breach.

    Critical: compliance fails OR any THD already above limit
    Watch:    distortion is climbing fast OR a sustained breach is active
    Normal:   else
    """
    compliance = row.get('thd_compliance_ieee519')
    movement   = row.get('thd_movement_pct_per_h')
    sustained  = row.get('sustained_thd_breach_active')
    v_thd_max  = _max_thd_v(row)
    i_thd_max  = _max_thd_i(row)

    if compliance == 'Fail':
        return 'Critical'
    if v_thd_max is not None and v_thd_max > V_THD_LIMIT_PCT:
        return 'Critical'
    if i_thd_max is not None and i_thd_max > I_THD_LIMIT_PCT:
        return 'Critical'
    if sustained:
        return 'Watch'
    if movement is not None and movement > THD_RISING_RATE_PCT_H:
        return 'Watch'
    return 'Normal'
