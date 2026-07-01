"""Distortion & Harmonics — UPS strategy.

Drives the right-side chart legends on the UPS Power Quality tab:

  Distortion & Harmonic Profile chart   V-THD · I-THD · H5/H7 per phase
                                        + Average Voltage legend tile

  Load Impact & Transformer Stress      PF Health · PF Angle · K-Stress
                                        + Power Factor · True PF ·
                                        PF Gap (Displacement) · PF Target

Live legend values stream here; the chart traces themselves come from
PowerQualityHistoryDispatcher (separate WS).
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_pf, label_v_thd, label_i_thd, label_k_factor, label_phase_angle,
    label_pf_displacement_gap,
)


class UpsDistortionHarmonics(BaseLiveStrategy):
    columns = [
        # ── Distortion & Harmonic Profile chart legend ───────────────────
        'thd_voltage_r_pct', 'thd_voltage_y_pct', 'thd_voltage_b_pct',
        'thd_current_r_pct', 'thd_current_y_pct', 'thd_current_b_pct',
        'harmonic_3rd_pct', 'harmonic_5th_pct', 'harmonic_7th_pct',
        'harmonic_11th_pct', 'harmonic_13th_pct',
        'thd_compliance_v_avg', 'thd_compliance_i_avg',
        'voltage_avg',                         # "Average Voltage 415V" tile
        'dominant_harmonic_order',
        'pq_dominant_harmonic_secondary',

        # ── Load Impact & Transformer Stress chart legend ────────────────
        'power_factor_total',
        'kpi_true_pf',
        'kpi_displacement_pf',
        'pf_displacement_gap',                 # NEW — kpi_displacement_pf − kpi_true_pf
        'pf_gap_vs_full_load',
        'phase_angle_deg',
        'k_factor',
        'harmonic_loss_factor_fhl',
        'harmonic_gap',
        'last_pf_drop_at',

        # ── Negative sequence (extra rotation drill-in) ──────────────────
        'negative_sequence_voltage_pct', 'negative_sequence_current_pct',
        'true_rms_voltage', 'fundamental_rms_voltage',
    ]
    status_rules = {
        'power_factor_total':    label_pf,
        'kpi_true_pf':           label_pf,
        'kpi_displacement_pf':   label_pf,
        'thd_compliance_v_avg':  label_v_thd,
        'thd_compliance_i_avg':  label_i_thd,
        'k_factor':              label_k_factor,
        'phase_angle_deg':       label_phase_angle,
        'pf_displacement_gap':   label_pf_displacement_gap,
    }
