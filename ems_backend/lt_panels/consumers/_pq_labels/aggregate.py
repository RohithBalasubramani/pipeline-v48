"""Convenience bundle — the registry of all derivers + the one-shot
`derive_all` entry point used by the PQ-summary strategies.
"""
from __future__ import annotations

from .harmonics import derive_dominant_harmonic_secondary, derive_pf_displacement_gap
from .issues import derive_active_issue_count, derive_critical_issue_type
from .mitigation import (
    derive_action_badge,
    derive_capacitor_bank_state,
    derive_filter_state,
    derive_nonlinear_signature,
)
from .severity import derive_severity
from .source import derive_likely_source, derive_next_priority


# ── Convenience: bundle all derivations into one call ──────────────────
ALL_DERIVERS = {
    'pq_severity_label':              derive_severity,
    'pq_critical_issue_type':         derive_critical_issue_type,
    'pq_active_issue_count':          derive_active_issue_count,
    'pq_likely_source_label':         derive_likely_source,
    'pq_next_priority_label':         derive_next_priority,
    'pq_nonlinear_signature_label':   derive_nonlinear_signature,
    'pq_action_badge':                derive_action_badge,
    'pq_filter_state':                derive_filter_state,
    'pq_capacitor_bank_state':        derive_capacitor_bank_state,
    'pq_dominant_harmonic_secondary': derive_dominant_harmonic_secondary,
    'pf_displacement_gap':            derive_pf_displacement_gap,
}


def derive_all(row, *, prefer_stored=True):
    """Compute all PQ labels. If `prefer_stored=True` and the column is
    already present in `row` (e.g. UPS stores them in panel_readings),
    pass-through that value instead of recomputing. Otherwise always
    recompute from raw inputs.
    """
    out = {}
    for key, fn in ALL_DERIVERS.items():
        if prefer_stored and row.get(key) is not None:
            out[key] = row[key]
        else:
            v = fn(row)
            if v is not None:
                out[key] = v
    return out
