"""Shared Power Quality label derivers (Path A — compute on-the-fly in WS layer).

Used by `TransformerPowerQualitySummary`, `LtPanelPowerQualitySummary`,
and `UpsPowerQualitySummary` strategies' `compute_status(row)` methods to
produce canonical text labels for the PQ tab — instead of FE deriving them
with duplicated if/else rules per page.

Each derive_* function:
  - takes a single live row dict (column → value)
  - returns a short text label (string) or None when the inputs are absent
  - is pure (no DB I/O, no state) — safe to call per-tick

Rules mirror the threshold logic the UPS simulator uses for its stored
columns (pq_severity_label, pq_critical_issue_type, ...) so the labels
are consistent across types.

Thresholds (constants below) are chosen to match the seeded `*_config`
table defaults (v_thd_limit_pct = 5, i_thd_limit_pct = 8, pf_target = 0.95).

This package was atomised from a single `_pq_labels.py` module into
one single-purpose file per concern. The barrel below preserves the
original public surface so `from .._pq_labels import derive_all`
(and any other name) keeps working unchanged.
"""
from __future__ import annotations

from .aggregate import ALL_DERIVERS, derive_all
from .harmonics import (
    derive_dominant_harmonic_secondary,
    derive_pf_displacement_gap,
)
from .issues import (
    derive_active_issue_count,
    derive_critical_issue_type,
)
from .mitigation import (
    derive_action_badge,
    derive_capacitor_bank_state,
    derive_filter_state,
    derive_nonlinear_signature,
)
from .severity import derive_severity
from .source import derive_likely_source, derive_next_priority
from .thresholds import (
    I_THD_LIMIT_PCT,
    ORDINAL,
    PF_TARGET,
    SAG_SWELL_EVENT_HOT,
    THD_RISING_RATE_PCT_H,
    V_THD_LIMIT_PCT,
    V_UNBALANCE_WARN_PCT,
)

__all__ = [
    # thresholds / constants
    'V_THD_LIMIT_PCT',
    'I_THD_LIMIT_PCT',
    'PF_TARGET',
    'V_UNBALANCE_WARN_PCT',
    'THD_RISING_RATE_PCT_H',
    'SAG_SWELL_EVENT_HOT',
    'ORDINAL',
    # derivers
    'derive_severity',
    'derive_critical_issue_type',
    'derive_active_issue_count',
    'derive_likely_source',
    'derive_next_priority',
    'derive_nonlinear_signature',
    'derive_action_badge',
    'derive_filter_state',
    'derive_capacitor_bank_state',
    'derive_dominant_harmonic_secondary',
    'derive_pf_displacement_gap',
    # bundle
    'ALL_DERIVERS',
    'derive_all',
]
