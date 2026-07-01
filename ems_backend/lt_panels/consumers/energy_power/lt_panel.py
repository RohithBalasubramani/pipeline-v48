"""Energy & Power — LT panel (PCC) strategy.

Ported from legacy EnergyPowerConsumer.
"""
from .._base import BaseLiveStrategy
from .._common import label_power_rate, label_loss_pct, label_capacity_pct
from .._ep_metrics import derive_all_ep

# LT panel rated efficiency assumption (distribution-side; typically 99%+).
LT_RATED_EFFICIENCY_PCT = 99.0


class LtPanelEnergyPower(BaseLiveStrategy):
    columns = [
        # Today's energy + week/month variants for range filter
        'active_energy_today_kwh', 'reactive_energy_today_kvarh', 'apparent_energy_today_kvah',
        'active_energy_this_week_kwh', 'reactive_energy_this_week_kvarh', 'apparent_energy_this_week_kvah',
        'active_energy_this_month_kwh', 'reactive_energy_this_month_kvarh', 'apparent_energy_this_month_kvah',
        'cumulative_vs_budget_kwh', 'kpi_kw_load_pct_of_rated',
        # Input vs Output
        'hv_input_kw', 'lv_output_kw', 'active_power_loss_kw', 'active_power_loss_pct',
        'loss_energy_today_kwh',
        # Power profile
        'active_power_total_kw', 'reactive_power_total_kvar', 'apparent_power_total_kva',
        # KPIs
        'specific_energy_consumption', 'kpi_load_factor',
        'peak_demand_today_kw', 'peak_demand_at_time',
        'power_rate_kw_per_h',
        # Trend status text columns (already-computed labels in DB)
        'sec_trend_status', 'load_factor_trend_status',
        'peak_demand_trend_status', 'power_trend_status',
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
        'kpi_kw_load_pct_of_rated':    label_capacity_pct,
    }

    def compute_status(self, row):
        out = super().compute_status(row)
        for k, v in derive_all_ep(row, rated_efficiency_pct=LT_RATED_EFFICIENCY_PCT).items():
            out[k] = v
        return out
