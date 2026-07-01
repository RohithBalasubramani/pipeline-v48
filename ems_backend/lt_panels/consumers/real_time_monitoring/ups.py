"""Real Time Monitoring — UPS strategy.

Targets the UPS Real-Time Monitoring tab (URL:
  /equipment/pcc-panels/<pcc>/ups/ups-<n>  → Real Time Monitoring)

Three live cards on the page (one WebSocket carries all three):

  1. Power & Energy:    Active/Reactive Power · Active/Reactive Energy ·
                        Projected · Apparent · dKW/dt · kVAR Trend
  2. Voltage Monitor:   B/R/Y phase voltages (LV-side — 415 V) + Avg/Max/Min
  3. Current Monitor:   B/R/Y phase currents + Neutral + Avg/Max/Min

Chart threshold reference lines (Max-420V / Min-400V / Max-120A / Min-100A)
live on the per-UPS `ups_config` row, not the live stream. The frontend
should fetch them once via REST and overlay on the live chart.

Note: UPS-01 is on the 415 V LT side; the frontend's "HV B-Phase" labels
are a known bug — these are LV (L-N) phase voltages.
"""
from .._base import BaseLiveStrategy


class UpsRealTimeMonitoring(BaseLiveStrategy):
    columns = [
        # ── Power & Energy card ────────────────────────────────────────
        'active_power_total_kw',            # Active Power 344.2 kW
        'reactive_power_total_kvar',        # Reactive Power 101.5 kVAR
        'apparent_power_total_kva',         # Apparent 358.8 kVA
        'active_energy_today_kwh',          # Active Energy 2185 kWh
        'reactive_energy_today_kvarh',      # Reactive Energy 4594 kVARh
        'projected_power_kw',               # Projected 327 kW
        'rate_of_change_power_kw_per_min',  # dKW/dt 213.5/min
        'reactive_power_trend',             # kVAR Trend (Falling/Rising/Steady)

        # ── Voltage Monitor card (LV side — labelled "HV" in legacy UI) ─
        'voltage_r_n', 'voltage_y_n', 'voltage_b_n',
        'voltage_avg', 'voltage_max', 'voltage_min',

        # ── Current Monitor card ──────────────────────────────────────
        'current_r', 'current_y', 'current_b', 'current_neutral',
        'current_avg', 'current_max', 'current_min',
    ]
    # No status labels on the legacy RTM consumer — keep parity.
    status_rules = {}
