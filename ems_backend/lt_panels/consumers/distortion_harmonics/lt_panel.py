"""Distortion & Harmonics — LT panel (PCC) strategy.

Ported from legacy DistortionHarmonicsConsumer.
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_pf, label_v_thd, label_i_thd, label_k_factor, label_phase_angle,
)


class LtPanelDistortionHarmonics(BaseLiveStrategy):
    columns = [
        # Distortion & Harmonic Profile
        'thd_voltage_r_pct', 'thd_voltage_y_pct', 'thd_voltage_b_pct',
        'thd_current_r_pct', 'thd_current_y_pct', 'thd_current_b_pct',
        'harmonic_3rd_pct', 'harmonic_5th_pct', 'harmonic_7th_pct',
        'harmonic_11th_pct', 'harmonic_13th_pct',
        'thd_compliance_v_avg', 'thd_compliance_i_avg',
        # Phase & Load Quality Impact
        'power_factor_total', 'kpi_true_pf', 'kpi_displacement_pf',
        'phase_angle_deg', 'k_factor',
        'harmonic_loss_factor_fhl',
    ]
    status_rules = {
        'power_factor_total':   label_pf,
        'kpi_true_pf':          label_pf,
        'kpi_displacement_pf':  label_pf,
        'thd_compliance_v_avg': label_v_thd,
        'thd_compliance_i_avg': label_i_thd,
        'k_factor':             label_k_factor,
        'phase_angle_deg':      label_phase_angle,
    }
