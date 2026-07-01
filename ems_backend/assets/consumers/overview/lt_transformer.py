"""Overview — LT Transformer (widget-envelope).

Maps the real mfm_tf_* columns onto the Overview page widgets (headline KPI
tiles, Power Factor, Voltage Deviation, Grid Frequency, Phase Balance,
Harmonics, Energy Consumption with a today/week/month filter, kW Load) plus
a templated AI-summary narrative.

Static nameplate (rated kW, subsidy budget) comes from `transformer_config`,
not the timeseries.
"""
from .._widgets_base import (
    BaseWidgetStrategy, StaticKpi, LiveGauge, LiveSpark, LiveBars, WindowedKpi,
)
from ...services import resolve_range


# ── status callables ───────────────────────────────────────────────────────

def _pf_status(v):
    try: v = float(v)
    except (TypeError, ValueError): return ''
    return 'Good' if v >= 0.95 else 'Fair' if v >= 0.85 else 'Poor'


def _voltage_status(v):
    try: v = abs(float(v))
    except (TypeError, ValueError): return ''
    return 'Normal' if v <= 3 else 'Elevated' if v <= 5 else 'Critical'


def _freq_status(v):
    try: d = abs(float(v) - 50)
    except (TypeError, ValueError): return ''
    return 'Stable' if d <= 0.05 else 'Fair' if d <= 0.1 else 'Unstable'


def _balance_status(v):
    try: v = float(v)
    except (TypeError, ValueError): return ''
    return 'Balanced' if v <= 5 else 'Watch' if v <= 10 else 'Unbalanced'


# range token → period column suffix used by transformer_config + readings
_REACTIVE_COL = {
    'today': 'reactive_energy_today_kvarh',
    'week':  'reactive_energy_this_week_kvarh',
    'month': 'reactive_energy_this_month_kvarh',
}
_SUBSIDY_CFG = {
    'today': 'subsidy_today_kwh',
    'week':  'subsidy_this_week_kwh',
    'month': 'subsidy_this_month_kwh',
}


class LtTransformerOverview(BaseWidgetStrategy):
    CONFIG_TABLE = 'transformer_config'

    widgets = [
        StaticKpi('headline_kpis', columns=[
            'kpi_kw_load_pct_of_rated', 'winding_hotspot_temperature_c',
            'efficiency_pct', 'remaining_useful_life_years',
        ]),
        LiveGauge('power_factor', columns=[
            'power_factor_total', 'kpi_displacement_pf', 'kpi_true_pf',
            'harmonic_gap', 'last_pf_drop_at', 'last_pf_drop_cause',
        ], status=_pf_status, status_column='power_factor_total'),
        # voltage_ll_avg (L-L, matches the design's "Actual Voltage") is not
        # populated in the current sim — voltage_avg (L-N) is, so send both.
        LiveGauge('voltage_deviation', columns=[
            'kpi_voltage_deviation_pct', 'voltage_ll_avg', 'voltage_avg',
        ], status=_voltage_status, status_column='kpi_voltage_deviation_pct'),
        LiveSpark('grid_frequency', columns=[
            'frequency_hz', 'frequency_deviation_hz',
            'worst_frequency_today_hz', 'worst_frequency_today_at_time',
        ], status=_freq_status, status_column='frequency_hz'),
        LiveBars('phase_balance', columns=[
            'current_unbalance_pct', 'current_r', 'current_y', 'current_b',
            'current_neutral', 'current_avg',
        ], status=_balance_status, status_column='current_unbalance_pct'),
        LiveGauge('harmonics', columns=[
            'k_factor', 'harmonic_loss_factor_fhl', 'thd_compliance_ieee519',
            'thd_compliance_v_avg', 'thd_compliance_i_avg',
        ]),
        StaticKpi('kw_load', columns=[
            'kpi_kw_load_pct_of_rated', 'active_power_total_kw',
            'peak_load_pct_today', 'peak_load_pct_today_at_time',
            'kpi_demand_headroom_kva', 'kpi_demand_headroom_pct', 'kpi_load_factor',
        ]),
        WindowedKpi('energy_consumption', ranges=['today', 'week', 'month'], default_range='today'),
    ]

    async def render_windowed(self, d, widget, range_token):
        start, end = resolve_range(range_token)
        active_kwh = await d.period_delta('active_energy_import_kwh', start, end)
        live = await d.latest([
            *_REACTIVE_COL.values(),
            'tod_rate_inr_per_kwh', 'tod_period', 'cumulative_vs_budget_kwh',
        ]) or {}
        cfg = await d.config_row(self.CONFIG_TABLE) or {}

        reactive = live.get(_REACTIVE_COL[range_token])
        tod_rate = live.get('tod_rate_inr_per_kwh')
        # Derived cost = period kWh × current ToD rate. (The sim's
        # energy_cost_per_day column is a lifetime cumulative, not a daily
        # figure, so we don't use it here.)
        energy_cost = (round(active_kwh * float(tod_rate), 2)
                       if active_kwh is not None and tod_rate is not None else None)

        return {
            'range': range_token,
            'active_kwh': active_kwh,
            'reactive_kvarh': reactive,
            'subsidy_target_kwh': cfg.get(_SUBSIDY_CFG[range_token]),
            'energy_cost': energy_cost,
            'tod_rate_inr_per_kwh': tod_rate,
            'tod_period': live.get('tod_period'),
            'budget_kwh': live.get('cumulative_vs_budget_kwh'),
        }
