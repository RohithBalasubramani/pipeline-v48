"""Power Quality summary — UPS strategy.

Drives the left column of the UPS Power Quality tab:

  Critical Diagnosis card  Issue type · Description · Compliance · Trend ·
                           Severity · Active Issue count
  Current Harmonic Stress  Dominant orders · THD V/I snapshot ·
                           H5/H7 · Nonlinear Signature
  Source & mitigation      Likely Source · Filter State · Capacitor Bank ·
                           Next Priority

Chart traces (Distortion & Harmonic Profile, Load Impact & Transformer Stress)
are served by `PowerQualityHistoryDispatcher` — separate WS.
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_flicker_pst, label_crest_factor, label_thd_movement, label_ieee519,
    label_pq_severity, label_pq_filter_state, label_pq_capacitor_bank,
    label_pq_active_issues,
)


class UpsPowerQualitySummary(BaseLiveStrategy):
    columns = [
        # ── Critical Diagnosis card ──────────────────────────────────────
        'pq_critical_issue_type',        # bold title ("Voltage Imbalance" / "Harmonic Distortion" / ...)
        'pq_severity_label',             # "Normal" / "Watch" / "Critical"
        'pq_active_issue_count',         # right-side badge
        'thd_compliance_ieee519',        # Compliance: "IEEE 519 Pass"
        'thd_compliance_v_avg',
        'thd_compliance_i_avg',
        'thd_movement_pct_per_h',        # Trend: "+3.6%/h Distortion Rate"
        'pq_constraint',                 # legacy constraint label (Voltage/Current/Both)

        # ── Current Harmonic Stress card ────────────────────────────────
        'dominant_harmonic_order',
        'pq_dominant_harmonic_secondary',
        'thd_voltage_r_pct', 'thd_voltage_y_pct', 'thd_voltage_b_pct',
        'thd_current_r_pct', 'thd_current_y_pct', 'thd_current_b_pct',
        'harmonic_3rd_pct', 'harmonic_5th_pct', 'harmonic_7th_pct',
        'harmonic_11th_pct', 'harmonic_13th_pct',
        'pq_nonlinear_signature_label',  # "Both within limit" / etc.

        # ── Power-quality exposure (24h windows) ────────────────────────
        'ups_thd_v_exposure_pct',
        'ups_thd_i_exposure_pct',

        # ── Other PQ scalars used by the card legends ───────────────────
        'flicker_pst', 'flicker_plt',
        'crest_factor_voltage', 'crest_factor_current',
        'sustained_thd_breach_active', 'sustained_thd_breach_started_at',

        # ── Inputs used by _pq_labels derivers (PF gap + likely source) ─
        'kpi_displacement_pf', 'kpi_true_pf', 'pf_displacement_gap',
        'k_factor',
        'voltage_unbalance_pct', 'current_unbalance_pct',
        'power_factor_total',
        'sag_events_24h', 'swell_events_24h',

        # ── Source & mitigation card ────────────────────────────────────
        'pq_likely_source_label',        # "Mixed nonlinear load" / "VFD" / ...
        'pq_filter_state',               # Filter State: Normal
        'pq_capacitor_bank_state',       # Capacitor Bank: Watch
        'pq_next_priority_label',        # "Improve PF margin"
    ]
    status_rules = {
        'pq_severity_label':       label_pq_severity,
        'pq_active_issue_count':   label_pq_active_issues,
        'thd_compliance_ieee519':  label_ieee519,
        'thd_movement_pct_per_h':  label_thd_movement,
        'flicker_pst':             label_flicker_pst,
        'crest_factor_voltage':    label_crest_factor,
        'crest_factor_current':    label_crest_factor,
        'pq_filter_state':         label_pq_filter_state,
        'pq_capacitor_bank_state': label_pq_capacitor_bank,
    }

    def compute_status(self, row):
        out = super().compute_status(row)
        # Path A: always derive labels in the WS layer so the casing /
        # vocabulary matches what Transformer and LT panels ship ("Watch"
        # not "watch", "APF active" not "normal"). The simulator's stored
        # `pq_*_label` columns are still in the row for any consumer that
        # wants them raw — we just don't surface them via `status`.
        from .._pq_labels import derive_all
        for k, v in derive_all(row, prefer_stored=False).items():
            out[k] = v
        # pq_constraint is itself a label
        if row.get('pq_constraint'):
            out.setdefault('pq_constraint', str(row['pq_constraint']))
        return out
