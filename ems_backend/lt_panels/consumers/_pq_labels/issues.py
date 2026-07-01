"""Active-issue chain — the single source of truth for the triggered
issue families, plus the two derivers built on top of it
(`pq_critical_issue_type`, `pq_active_issue_count`).
"""
from __future__ import annotations

from .helpers import _max_thd_i, _max_thd_v
from .thresholds import (
    I_THD_LIMIT_PCT,
    PF_TARGET,
    SAG_SWELL_EVENT_HOT,
    V_THD_LIMIT_PCT,
    V_UNBALANCE_WARN_PCT,
)


# ── 2. pq_critical_issue_type ───────────────────────────────────────────
def _active_issues(row):
    """Return the ordered list of triggered (issue_key, issue_label) tuples
    for this row. Single source of truth for the priority chain used by
    `derive_critical_issue_type` (first match) and
    `derive_active_issue_count` (len).

    Adding a new check here automatically flows through to both derivers.
    Ordering matters: the first entry is what "Critical Issue" displays.
    Note `sustained_breach` historically counted toward the active-issue
    count but NOT the critical-issue label — preserve that by keeping it
    last; `derive_critical_issue_type` falls back to 'Normal' before
    matching it.
    """
    out = []
    if (row.get('voltage_unbalance_pct') or 0) > V_UNBALANCE_WARN_PCT:
        out.append(('voltage_imbalance', 'Voltage Imbalance'))
    v_max = _max_thd_v(row) or 0
    i_max = _max_thd_i(row) or 0
    if v_max > V_THD_LIMIT_PCT or i_max > I_THD_LIMIT_PCT:
        out.append(('harmonic_distortion', 'Harmonic Distortion'))
    pf = row.get('power_factor_total')
    if pf is not None and pf < PF_TARGET:
        out.append(('pf_drop', 'PF Drop'))
    sag = row.get('sag_events_24h') or 0
    swl = row.get('swell_events_24h') or 0
    if sag + swl > SAG_SWELL_EVENT_HOT:
        out.append(('sag_swell_events', 'Sag/Swell Events'))
    if row.get('sustained_thd_breach_active'):
        out.append(('sustained_breach', 'Sustained THD Breach'))
    return out


def derive_critical_issue_type(row):
    """Priority chain — first match wins. Drives the Active Issue title.

    Note: `sustained_breach` is excluded from the critical-issue label
    (historic behaviour) — it only counts toward `derive_active_issue_count`.
    """
    for key, label in _active_issues(row):
        if key == 'sustained_breach':
            continue
        return label
    return 'Normal'


# ── 3. pq_active_issue_count ───────────────────────────────────────────
def derive_active_issue_count(row):
    """Count of distinct issue families currently triggered."""
    return len(_active_issues(row))
