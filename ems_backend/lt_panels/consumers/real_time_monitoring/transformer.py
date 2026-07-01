"""Real Time Monitoring — Transformer strategy.

Three live cards on the page (single WebSocket carries all three):
  1. Power & Energy:  Active/Reactive Power & Energy, Projected, Apparent,
                      dKW/dt, Frequency
  2. Voltage Monitor: R/Y/B L-N phases + Avg/Max/Min
  3. Current Monitor: R/Y/B phases + Neutral + Avg/Max/Min

Column names match the simulator's actual schema (COMMON_COLUMNS) —
frontend's dataSourceRegistry expects the unprefixed names.
"""
from .._base import BaseLiveStrategy


class TransformerRealTimeMonitoring(BaseLiveStrategy):
    columns = [
        # ── Power & Energy card ────────────────────────────────────────
        'active_power_total_kw',           # Active Power (kW)
        'reactive_power_total_kvar',       # Reactive Power (kVAR)
        'apparent_power_total_kva',        # Apparent (kVA)
        'active_energy_import_kwh',        # Active Energy (kWh)
        'reactive_energy_import_kvarh',    # Reactive Energy (kVARh)
        'projected_power_kw',              # Projected (kW) — 15-min linear
        'rate_of_change_power_kw_per_min', # dKW/dt
        'frequency_hz',                    # Grid frequency

        # ── Voltage Monitor card (L-N phase voltages) ──────────────────
        'voltage_r_n',
        'voltage_y_n',
        'voltage_b_n',
        'voltage_avg',
        'voltage_max',
        'voltage_min',

        # ── Current Monitor card ──────────────────────────────────────
        'current_r',
        'current_y',
        'current_b',
        'current_neutral',
        'current_avg',
        'current_max',
        'current_min',
    ]
    # No status labels on the legacy RTM consumer; keep parity until spec'd.
    status_rules = {}
