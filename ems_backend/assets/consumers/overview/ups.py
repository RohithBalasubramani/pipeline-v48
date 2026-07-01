"""Overview — UPS (widget-envelope).

Maps the real mfm_ups_* columns onto the UPS Overview page: headline tiles,
Input vs Output Voltage, Output Load, Output Frequency, Output Phase Balance,
the 5 status chips, Energy & Autonomy, and Output Power Quality. All widgets
are live (one fetch per tick); rated kVA / nominal voltage come from
`ups_config`. The AI-summary line is a frontend concern.
"""
from .._widgets_base import (
    BaseWidgetStrategy, StaticKpi, LiveGauge, LiveSpark, LiveBars,
)


class UpsOverview(BaseWidgetStrategy):
    CONFIG_TABLE = 'ups_config'

    widgets = [
        StaticKpi('headline_kpis', columns=[
            'ups_kva_used_pct',          # Loading %
            'ups_battery_reserve_pct',   # Battery reserve
            'ups_autonomy_min',          # Autonomy (runtime remaining)
            'current_unbalance_pct',     # Output current imbalance
        ]),
        LiveGauge('input_output_voltage', columns=[
            'ups_input_voltage_v', 'voltage_avg',
            'ups_input_voltage_deviation_pct', 'ups_output_input_voltage_delta_pct',
            'ups_voltage_regulation_pct',
        ]),
        StaticKpi('output_load', columns=[
            'apparent_power_total_kva', 'active_power_total_kw',
            'ups_kva_used_pct', 'ups_kva_free_kva',
        ]),
        LiveSpark('output_frequency', columns=[
            'frequency_hz', 'frequency_deviation_hz',
            'ups_bypass_frequency_hz', 'ups_sync_window_state',
        ]),
        LiveBars('phase_balance', columns=[
            'ups_output_phase_balance_pct', 'current_unbalance_pct',
            'current_r', 'current_y', 'current_b', 'current_neutral', 'current_avg',
        ]),
        StaticKpi('status_chips', columns=[
            'ups_communication_status', 'ups_operating_mode', 'ups_inverter_status',
            'ups_battery_charge_state', 'ups_bypass_sync_state',
            'alerts_critical_count', 'alerts_total_count',
        ]),
        StaticKpi('energy_autonomy', columns=[
            'ups_autonomy_min', 'ups_battery_soc_pct', 'ups_battery_charge_state',
            'ups_battery_dc_bus_voltage_v', 'ups_battery_dc_current_a',
            'ups_battery_temperature_c', 'ups_kva_used_pct',
        ]),
        LiveGauge('power_quality', columns=[
            'thd_compliance_v_avg', 'thd_compliance_i_avg',
            'ups_thd_v_exposure_pct', 'ups_thd_i_exposure_pct',
            'power_factor_total', 'ups_sync_window_state', 'ups_bypass_frequency_hz',
        ]),
    ]

    async def render_static(self, d):
        cfg = await d.config_row(self.CONFIG_TABLE) or {}
        return {
            'rated_kva': cfg.get('rated_kva') or cfg.get('kva_rating'),
            'nominal_voltage_v': cfg.get('nominal_voltage_v'),
            'contract_limit_kva': cfg.get('contract_limit_kva'),
        }
