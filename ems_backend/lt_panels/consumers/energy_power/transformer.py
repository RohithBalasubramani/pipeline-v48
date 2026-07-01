"""Energy & Power — Transformer strategy.

Live cards on the page (single WebSocket carries both):
  1. Today's Energy:     Active / Reactive kWh, SEC, subsidy bar
                         (range filter: Today / This Week / This Month)
  2. Input vs Output:    HV input kW, LV output kW, efficiency, loss kW
                         + derived Loss/Expected-Loss kWh + delta %

Derived values (`efficiency_pct`, `hv_lv_delta_pct`,
`active_energy_loss_today_kwh`, `expected_energy_loss_today_kwh`,
`loss_pct_of_input`) are computed in `compute_status()` via the shared
`_ep_metrics` module — same Path A pattern used for PQ labels.

The two chart cards on the page (Power Energy Analysis bars, Load
Anomalies) are date-bucketed and use the sibling `demand-profile/` and
`load-anomalies/` history WSes — not this stream.
"""
from .._base import BaseLiveStrategy
from .._common import label_capacity_pct, label_loss_pct
from .._ep_metrics import derive_all_ep

# Transformer rated efficiency assumption — drives `expected_energy_loss_today_kwh`.
# Distribution transformer at rated load typically 98-99% efficient.
TRANSFORMER_RATED_EFFICIENCY_PCT = 98.5


class TransformerEnergyPower(BaseLiveStrategy):
    columns = [
        # ── Today's Energy card ────────────────────────────────────────
        # Range-switchable energy totals (FE picks today / week / month)
        'active_energy_today_kwh',
        'active_energy_this_week_kwh',
        'active_energy_this_month_kwh',
        'reactive_energy_today_kvarh',
        'reactive_energy_this_week_kvarh',
        'reactive_energy_this_month_kvarh',
        'apparent_energy_today_kvah',
        'apparent_energy_this_week_kvah',
        'apparent_energy_this_month_kvah',
        # KPIs
        'specific_energy_consumption',
        'kpi_kw_load_pct_of_rated',
        'cumulative_vs_budget_kwh',

        # ── Power profile (live legend values) ─────────────────────────
        'active_power_total_kw',
        'reactive_power_total_kvar',
        'apparent_power_total_kva',
        'projected_eod_kwh',
        'budget_delta_kwh',

        # ── Input vs Output Energy card ────────────────────────────────
        'hv_input_kw',
        'lv_output_kw',
        'active_power_loss_kw',
        'active_power_loss_pct',

        # ── Load anomalies header KPIs ─────────────────────────────────
        'kpi_load_factor',
        'peak_demand_today_kw', 'peak_demand_at_time',

        # ── Trend status text columns ──────────────────────────────────
        'sec_trend_status',
        'load_factor_trend_status',
        'peak_demand_trend_status',
        'power_trend_status',
    ]
    status_rules = {
        'active_power_loss_pct':       label_loss_pct,
        'kpi_kw_load_pct_of_rated':    label_capacity_pct,
        # Pass-through trend statuses
        'specific_energy_consumption': 'sec_trend_status',
        'kpi_load_factor':             'load_factor_trend_status',
        'peak_demand_today_kw':        'peak_demand_trend_status',
        'active_power_total_kw':       'power_trend_status',
    }

    def compute_status(self, row):
        out = super().compute_status(row)
        for k, v in derive_all_ep(row, rated_efficiency_pct=TRANSFORMER_RATED_EFFICIENCY_PCT).items():
            out[k] = v
        return out
