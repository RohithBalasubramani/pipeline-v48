"""Power Quality summary — Transformer strategy.

Left column of the Power Quality page (4 cards on a single live WebSocket):

  1. Critical Diagnosis      Status + Compliance + Trend + Severity tiles
  2. Current Harmonic Stress Dominant order + THD snapshot + H5/H7 tiles
  3. Source & Mitigation     Action badge + 2x2 tiles (source / filter /
                             cap bank / next priority)
  4. (page-level)            Voltage Quality footer (flicker, crest factor)

Path A wiring: text labels for Severity, Active Issue, Likely Source,
Filter State, Cap Bank, Next Priority, Nonlinear Signature, Action Badge,
and the Secondary Dominant Harmonic are all derived on-the-fly in
`compute_status(row)` via the shared `_pq_labels` module. No new schema
columns; FE reads them from `frame.status.<key>`.
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_flicker_pst, label_crest_factor, label_thd_movement, label_ieee519,
)
from .._pq_labels import derive_all


class TransformerPowerQualitySummary(BaseLiveStrategy):
    columns = [
        # ── Compliance + trend (Card 1: Critical Diagnosis) ────────────
        'thd_compliance_ieee519',          # 'Pass' / 'Fail'
        'thd_compliance_v_avg',            # avg V-THD %
        'thd_compliance_i_avg',            # avg I-THD %
        'thd_movement_pct_per_h',          # rising/falling %/h
        'pq_constraint',                   # 'Voltage' / 'Current' / 'Both'
        'sustained_thd_breach_active',     # bool
        'sustained_thd_breach_started_at', # timestamp

        # ── Per-phase THD (drives the Current Harmonic Stress card) ────
        'thd_voltage_r_pct', 'thd_voltage_y_pct', 'thd_voltage_b_pct',
        'thd_current_r_pct', 'thd_current_y_pct', 'thd_current_b_pct',

        # ── Individual harmonic orders (H5/H7 tile + secondary derive) ─
        'harmonic_3rd_pct', 'harmonic_5th_pct', 'harmonic_7th_pct',
        'harmonic_11th_pct', 'harmonic_13th_pct',
        'dominant_harmonic_order',

        # ── Inputs the label derivers need ─────────────────────────────
        'voltage_unbalance_pct',           # → severity / issue type
        'current_unbalance_pct',
        'power_factor_total',              # → PF Drop / action / cap bank
        'kpi_displacement_pf',             # → pf_displacement_gap
        'kpi_true_pf',
        'k_factor',                        # → likely-source heuristic
        'sag_events_24h', 'swell_events_24h',  # → issue type / count

        # ── Voltage Quality card (flicker + crest) ─────────────────────
        'flicker_pst', 'flicker_plt',
        'crest_factor_voltage', 'crest_factor_current',
    ]
    status_rules = {
        # Per-column threshold rules (simple lookups)
        'flicker_pst':            label_flicker_pst,
        'crest_factor_voltage':   label_crest_factor,
        'crest_factor_current':   label_crest_factor,
        'thd_movement_pct_per_h': label_thd_movement,
        'thd_compliance_ieee519': label_ieee519,
    }

    def compute_status(self, row):
        out = super().compute_status(row)
        # Composite labels — pure functions of cols above
        for k, v in derive_all(row, prefer_stored=False).items():
            out[k] = v
        # Pass-through: pq_constraint is itself a label
        if row.get('pq_constraint'):
            out.setdefault('pq_constraint', str(row['pq_constraint']))
        return out
