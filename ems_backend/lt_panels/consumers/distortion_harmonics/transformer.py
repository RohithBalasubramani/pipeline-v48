"""Distortion & Harmonics — Transformer strategy.

Right column of the Power Quality page (2 chart cards on a single live WS):

  1. Distortion & Harmonic Profile
       Toggles: V/I THD | H5/H7  + badge "Current limit breach"
       Lines:   V-THD R/Y/B, I-THD R/Y/B, H5, H7
       Refs:    V limit 5%, I limit 8%, H5 watch, H7 watch
       KPIs:    Avg V-THD, Avg I-THD, H5 order, H7 order

  2. Phase & Load Quality Impact
       Toggles: PF | Phase Angle | K Stress  + badge "Harmonic heating watch"
       Lines:   Power Factor, True PF, Displacement PF, Phase Angle, K-Factor stress
       Refs:    PF target 0.95, Lag watch 20°, K watch
       KPIs:    Power Factor, True PF, Phase Angle, K-Factor

Column-tolerant fetch silently pads None for unconfirmed names below.
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_pf, label_v_thd, label_i_thd, label_k_factor, label_phase_angle,
)


class TransformerDistortionHarmonics(BaseLiveStrategy):
    columns = [
        # ── Card 1: Distortion & Harmonic Profile ──────────────────────
        # V-THD per phase (+ I-THD per phase) — chart line series
        'thd_voltage_r_pct', 'thd_voltage_y_pct', 'thd_voltage_b_pct',
        'thd_current_r_pct', 'thd_current_y_pct', 'thd_current_b_pct',
        # Avg KPIs on the right-side strip
        'thd_compliance_v_avg',           # "Avg V-THD: 4.2 %"
        'thd_compliance_i_avg',           # "Avg I-THD: 13.2 %"
        # Individual harmonic orders for the H5/H7 toggle + KPIs
        'harmonic_3rd_pct',
        'harmonic_5th_pct',               # "H5 order: 9.0 %"
        'harmonic_7th_pct',               # "H7 order: 5.6 %"
        'harmonic_11th_pct',
        'harmonic_13th_pct',
        # Reference / threshold lines on the chart
        'pq_v_thd_limit_pct',             # TODO — "V limit 5 %"
        'pq_i_thd_limit_pct',             # TODO — "I limit 8 %"
        'pq_h5_watch_pct',                # TODO — "H5 watch"
        'pq_h7_watch_pct',                # TODO — "H7 watch"
        'pq_current_limit_breach',        # TODO — drives "Current limit breach" badge

        # ── Card 2: Phase & Load Quality Impact ────────────────────────
        # PF lines + KPIs
        'power_factor_total',             # "Power Factor: 0.935"
        'kpi_true_pf',                    # "True PF: 0.885"
        'kpi_displacement_pf',            # chart line, no KPI tile
        # Phase angle line + KPI
        'phase_angle_deg',                # "Phase Angle: 16.4 deg"
        # K-Factor stress line + KPI
        'k_factor',                       # "K-Factor: 11.9"
        # Loss / heating context
        'harmonic_loss_factor_fhl',
        # Reference / threshold lines on the chart
        'pq_pf_target',                   # TODO — "PF target 0.95"
        'pq_phase_angle_lag_watch_deg',   # TODO — "Lag watch 20°"
        'pq_k_factor_watch',              # TODO — "K watch"
        'pq_harmonic_heating_watch',      # TODO — drives "Harmonic heating watch" badge
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
