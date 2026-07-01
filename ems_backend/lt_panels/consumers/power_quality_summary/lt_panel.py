"""Power Quality summary — LT panel strategy.

Same Path A pattern as the Transformer PQ strategy: raw inputs streamed as
columns; composite labels (severity, issue type, likely source, filter
state, capacitor bank, next priority, nonlinear signature, action badge,
secondary dominant harmonic) derived in `compute_status(row)` via the
shared `_pq_labels` module. FE reads them from `frame.status.<key>`.

This includes the Solar Incomer flavour of LT — solar-specific status
labels live on the Overview strategy, not here.
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_flicker_pst, label_crest_factor, label_thd_movement, label_ieee519,
)
from .._pq_labels import derive_all


class LtPanelPowerQualitySummary(BaseLiveStrategy):
    columns = [
        # ── Compliance + trend (Card 1: Critical Diagnosis) ────────────
        'thd_compliance_ieee519',
        'thd_compliance_v_avg',
        'thd_compliance_i_avg',
        'thd_movement_pct_per_h',
        'pq_constraint',
        'sustained_thd_breach_active',
        'sustained_thd_breach_started_at',

        # ── Per-phase THD ──────────────────────────────────────────────
        'thd_voltage_r_pct', 'thd_voltage_y_pct', 'thd_voltage_b_pct',
        'thd_current_r_pct', 'thd_current_y_pct', 'thd_current_b_pct',

        # ── Individual harmonic orders (H5/H7 tile + secondary derive) ─
        'harmonic_3rd_pct', 'harmonic_5th_pct', 'harmonic_7th_pct',
        'harmonic_11th_pct', 'harmonic_13th_pct',
        'dominant_harmonic_order',

        # ── Inputs the label derivers need ─────────────────────────────
        'voltage_unbalance_pct',
        'current_unbalance_pct',
        'power_factor_total',
        'kpi_displacement_pf',
        'kpi_true_pf',
        'k_factor',
        'sag_events_24h', 'swell_events_24h',

        # ── Voltage Quality card (flicker + crest) ─────────────────────
        'flicker_pst', 'flicker_plt',
        'crest_factor_voltage', 'crest_factor_current',
    ]
    status_rules = {
        'flicker_pst':            label_flicker_pst,
        'crest_factor_voltage':   label_crest_factor,
        'crest_factor_current':   label_crest_factor,
        'thd_movement_pct_per_h': label_thd_movement,
        'thd_compliance_ieee519': label_ieee519,
    }

    def compute_status(self, row):
        out = super().compute_status(row)
        for k, v in derive_all(row, prefer_stored=False).items():
            out[k] = v
        if row.get('pq_constraint'):
            out.setdefault('pq_constraint', str(row['pq_constraint']))
        return out
