"""Voltage & Current — UPS strategy.

Targets the UPS Voltage & Current tab (URL:
  /equipment/pcc-panels/<pcc>/ups/ups-<n>  → Voltage & Current)

Live cards served by this WebSocket (column-row, 1-Hz delta queue):

  Voltage Live Health   Actual V · Nominal · Deviation% · Unbalance% · Max gap V
                        · Rate Change V/min · R/Y/B values + per-phase %

  Current Live Health   Unbalance% · Max gap A · Neutral/phase% ·
                        R/Y/B/N values + per-phase %

  Voltage History header tiles
                        Max Deviation today · Worst Spread V + pair + at-time ·
                        Primary Event today · Sag/Swell event counters
                        (the chart trace itself comes from VoltageHistoryDispatcher)

  Current History header tiles
                        Peak Current today · Avg Current today ·
                        Max Unbalance today · Neutral Peak today
                        (the chart trace itself comes from CurrentHistoryDispatcher)
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_voltage_deviation, label_voltage_unbalance,
    label_current_unbalance, label_neutral_ratio,
)


class UpsVoltageCurrent(BaseLiveStrategy):
    columns = [
        # ── Voltage Live Health ──────────────────────────────────────────
        'voltage_r_n', 'voltage_y_n', 'voltage_b_n',
        'voltage_avg', 'voltage_max', 'voltage_min',
        'voltage_r_deviation_pct',
        'voltage_y_deviation_pct',
        'voltage_b_deviation_pct',
        'kpi_voltage_deviation_pct',
        'voltage_unbalance_pct',
        # Voltage phase-pair spreads — newly added
        'voltage_max_spread_v',
        'voltage_spread_ry_v',
        'voltage_spread_yb_v',
        'voltage_spread_br_v',
        # Voltage rate of change (UPS_OVERVIEW_EXTRAS)
        'voltage_rate_change_v_per_min',

        # ── Current Live Health ──────────────────────────────────────────
        'current_r', 'current_y', 'current_b', 'current_neutral',
        'current_avg', 'current_max', 'current_min',
        'current_r_deviation_pct',
        'current_y_deviation_pct',
        'current_b_deviation_pct',
        'current_unbalance_pct',
        'current_max_spread', 'current_spread_br',
        'current_spread_ry', 'current_spread_by',
        'kpi_neutral_to_phase_ratio_pct',
        # 60-s rolling rate-of-change for current — siblings to voltage_rate_change above
        'current_rate_change_a_per_min',

        # ── Voltage History header tiles (point-in-time aggregates) ──────
        'max_voltage_deviation_today_pct',
        'max_voltage_deviation_at_time',
        'worst_spread_today_v',
        'worst_spread_today_pair',          # NEW — "R-Y" / "Y-B" / "B-R"
        'primary_voltage_event_today',      # NEW — "Motor start sag" / etc.
        'sag_events_24h', 'swell_events_24h',

        # ── Current History header tiles ────────────────────────────────
        'peak_current_today_a', 'avg_current_today_a',
        'max_current_unbalance_today_pct', 'max_unbalance_at_time',
        'neutral_peak_today_a', 'neutral_peak_events_today',
    ]
    status_rules = {
        'voltage_r_deviation_pct':        label_voltage_deviation,
        'voltage_y_deviation_pct':        label_voltage_deviation,
        'voltage_b_deviation_pct':        label_voltage_deviation,
        'kpi_voltage_deviation_pct':      label_voltage_deviation,
        'voltage_unbalance_pct':          label_voltage_unbalance,
        'current_r_deviation_pct':        label_voltage_deviation,
        'current_y_deviation_pct':        label_voltage_deviation,
        'current_b_deviation_pct':        label_voltage_deviation,
        'current_unbalance_pct':          label_current_unbalance,
        'kpi_neutral_to_phase_ratio_pct': label_neutral_ratio,
    }
