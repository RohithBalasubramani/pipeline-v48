"""Source & mitigation state labels — compliance signature, action badge,
APF filter state, capacitor-bank state.
"""
from __future__ import annotations

from .helpers import _avg_thd_i, _avg_thd_v, _max_thd_i
from .thresholds import I_THD_LIMIT_PCT, PF_TARGET, V_THD_LIMIT_PCT


# ── 6. pq_nonlinear_signature_label ────────────────────────────────────
def derive_nonlinear_signature(row):
    """V/I THD compliance composite label."""
    v_avg = row.get('thd_compliance_v_avg') or _avg_thd_v(row)
    i_avg = row.get('thd_compliance_i_avg') or _avg_thd_i(row)
    v_over = v_avg is not None and v_avg > V_THD_LIMIT_PCT
    i_over = i_avg is not None and i_avg > I_THD_LIMIT_PCT
    if v_over and i_over:
        return 'Both exceeded'
    if v_over:
        return 'Voltage exceeded'
    if i_over:
        return 'Current exceeded'
    return 'Both within limit'


# ── 7. pq_action_badge — drives the FE's APFC Tune / PF Watch / Stable ─
def derive_action_badge(row):
    """Top-line action call for the Source & mitigation card."""
    i_max = _max_thd_i(row) or 0
    pf = row.get('power_factor_total') or 1.0
    if i_max > I_THD_LIMIT_PCT:
        return 'APFC Tune'
    if pf < PF_TARGET:
        return 'PF Watch'
    return 'Stable'


# ── 8. pq_filter_state — APF on/off + saturation hint ──────────────────
def derive_filter_state(row):
    """Heuristic until real filter hardware telemetry is wired."""
    i_max = _max_thd_i(row) or 0
    if i_max > I_THD_LIMIT_PCT * 1.5:   # 12% — heavy distortion
        return 'Saturated'
    if i_max > I_THD_LIMIT_PCT:
        return 'APF active'
    return 'Normal'


# ── 9. pq_capacitor_bank_state ─────────────────────────────────────────
def derive_capacitor_bank_state(row):
    pf = row.get('power_factor_total')
    if pf is None:
        return None
    if pf < 0.85:
        return 'Overcurrent'
    if pf < PF_TARGET:
        return 'Watch'
    return 'Normal'
