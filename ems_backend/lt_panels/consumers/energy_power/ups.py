"""Energy & Power — UPS strategy.

Targets the UPS Energy & Power tab (URL:
  /equipment/pcc-panels/<pcc>/ups/ups-<n>  → Energy & Power)

Live tiles served by this WebSocket:

  Today's Energy card        Active / Reactive / Apparent kWh (today),
                              + windowed variants (this_week, this_month)
                              + subsidy progress is computed on the client
                              from the active-energy column and ups_config

  Power Energy Analysis      Rated kW / Contracted kW are config (REST),
                              the hourly bar chart + Hourly Average line are
                              served by the EnergyPowerHistoryDispatcher
                              (separate WS), NOT this one.

  Input vs Output Energy     hv_input_kw · lv_output_kw · loss kW · loss % ·
                              efficiency derived in the WS

  Load Anomalies KPIs        Max %, Surge/Dip event counts, Load Factor — all
                              served by EnergyPowerHistoryDispatcher (windowed)
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_power_rate, label_loss_pct, label_capacity_pct, label_ups_loading,
)
from .._ep_metrics import derive_all_ep

# UPS rated efficiency assumption — drives `expected_energy_loss_today_kwh`.
# Modern double-conversion UPS typically rated 96-97% AC efficiency.
UPS_RATED_EFFICIENCY_PCT = 96.5


class UpsEnergyPower(BaseLiveStrategy):
    columns = [
        # ── Today's Energy card ──────────────────────────────────────────
        'active_energy_today_kwh',
        'reactive_energy_today_kvarh',
        'apparent_energy_today_kvah',
        'cumulative_vs_budget_kwh',
        'specific_energy_consumption',

        # Week / Month variants (for the range dropdown)
        'active_energy_this_week_kwh',
        'reactive_energy_this_week_kvarh',
        'apparent_energy_this_week_kvah',
        'active_energy_this_month_kwh',
        'reactive_energy_this_month_kvarh',
        'apparent_energy_this_month_kvah',

        # ── Power Energy Analysis card (live legend values) ──────────────
        'active_power_total_kw',
        'reactive_power_total_kvar',
        'apparent_power_total_kva',
        'projected_eod_kwh',
        'budget_delta_kwh',

        # ── Input vs Output Energy card ──────────────────────────────────
        'hv_input_kw',
        'lv_output_kw',
        'active_power_loss_kw',
        'active_power_loss_pct',

        # ── Load Anomalies header KPIs (point-in-time) ───────────────────
        'kpi_kw_load_pct_of_rated',          # Present 70%
        'kpi_load_factor',                   # Load Factor (live ratio)
        'peak_demand_today_kw', 'peak_demand_at_time',
        'peak_load_pct_today', 'peak_load_pct_today_at_time',
        'peak_load_pct_this_week', 'peak_load_pct_this_week_at_time',
        'peak_load_pct_this_month', 'peak_load_pct_this_month_at_time',

        # ── Trend / rate-of-change ───────────────────────────────────────
        'power_rate_kw_per_h',
        'rate_of_change_power_kw_per_min',
        'reactive_power_trend',

        # ── Trend status text columns (already-computed labels in DB) ────
        'sec_trend_status',
        'load_factor_trend_status',
        'peak_demand_trend_status',
        'power_trend_status',
    ]
    status_rules = {
        # Pass-through (sibling column carries the label)
        'specific_energy_consumption': 'sec_trend_status',
        'kpi_load_factor':             'load_factor_trend_status',
        'peak_demand_today_kw':        'peak_demand_trend_status',
        'active_power_total_kw':       'power_trend_status',
        # Threshold-based
        'power_rate_kw_per_h':         label_power_rate,
        'active_power_loss_pct':       label_loss_pct,
        'kpi_kw_load_pct_of_rated':    label_ups_loading,
    }

    def compute_status(self, row):
        out = super().compute_status(row)
        # Derived Input-vs-Output values the FE expects in its inputOutput
        # widget (`efficiency_pct`, `hv_lv_delta_pct`,
        # `active_energy_loss_today_kwh`, `expected_energy_loss_today_kwh`,
        # `loss_pct_of_input`). Without these the FE binds the wrong cols
        # to its Loss/Expected-Loss tiles (the screenshot bug).
        for k, v in derive_all_ep(row, rated_efficiency_pct=UPS_RATED_EFFICIENCY_PCT).items():
            out[k] = v
        return out
