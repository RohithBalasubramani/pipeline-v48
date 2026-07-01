"""Voltage & Current — Transformer strategy.

Two live cards on the page (single WebSocket carries both):
  1. Voltage Live Health: Actual voltage + nominal + deviation %, gauge,
                          per-phase R/Y/B with deviation %, unbalance %,
                          max gap (between two phases), rate of change V/min,
                          overall status badge (Normal/Watch/Critical).
  2. Current Live Health: Unbalance %, max gap (between two phases),
                          neutral/phase ratio %, per-phase R/Y/B/N with
                          deviation %, overall status badge.

The two history cards on the page (Voltage History + Current History with
Today/Week/Month filters) are served by `voltage-history/` and
`current-history/` history WSes. Static thresholds (Max V / Min V chart
reference lines, Nominal V tile) come from `/api/mfm/{id}/config/`.
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_voltage_deviation, label_voltage_unbalance,
    label_current_unbalance, label_neutral_ratio,
)


class TransformerVoltageCurrent(BaseLiveStrategy):
    columns = [
        # ── Voltage Live Health card ───────────────────────────────────
        # Header readout: actual avg / nominal (from /config/) / deviation %
        'voltage_avg',                          # "Actual voltage"
        'kpi_voltage_deviation_pct',            # "Deviation %"
        # Per-phase L-N bars + per-phase deviation %
        'voltage_r_n',
        'voltage_y_n',
        'voltage_b_n',
        'voltage_r_deviation_pct',
        'voltage_y_deviation_pct',
        'voltage_b_deviation_pct',
        # KPI strip on the card
        'voltage_unbalance_pct',                # "Unbalance %"
        'voltage_max_spread_v',                 # "Max gap N V"
        'voltage_spread_ry_v',                  # individual pair gaps,
        'voltage_spread_yb_v',                  # for FE to derive pair label
        'voltage_spread_br_v',
        'rate_of_change_voltage_v_per_min',     # "Rate Change V/min"

        # ── Current Live Health card ───────────────────────────────────
        # KPI strip
        'current_unbalance_pct',                # "Unbalance %"
        'current_max_spread',                   # "Max gap N A"
        'current_spread_ry',                    # individual pair gaps,
        'current_spread_yb',                    # for FE to derive pair label
        'current_spread_br',
        'kpi_neutral_to_phase_ratio_pct',       # "Neutral/phase %"
        # Per-phase + neutral bars + per-phase deviation %
        'current_r',
        'current_y',
        'current_b',
        'current_neutral',
        'current_r_deviation_pct',
        'current_y_deviation_pct',
        'current_b_deviation_pct',

        # 60-s rolling rate-of-change (detail V&C rate-of-change card)
        'voltage_rate_change_v_per_min',
        'current_rate_change_a_per_min',

        # Today's event counters (referenced from Voltage History card too)
        'sag_events_24h',
        'swell_events_24h',
    ]
    status_rules = {
        # Voltage card status badges
        'voltage_r_deviation_pct':        label_voltage_deviation,
        'voltage_y_deviation_pct':        label_voltage_deviation,
        'voltage_b_deviation_pct':        label_voltage_deviation,
        'kpi_voltage_deviation_pct':      label_voltage_deviation,
        'voltage_unbalance_pct':          label_voltage_unbalance,
        # Current card status badges
        'current_r_deviation_pct':        label_voltage_deviation,
        'current_y_deviation_pct':        label_voltage_deviation,
        'current_b_deviation_pct':        label_voltage_deviation,
        'current_unbalance_pct':          label_current_unbalance,
        'kpi_neutral_to_phase_ratio_pct': label_neutral_ratio,
    }
