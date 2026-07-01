"""UPS — Battery & Autonomy tab (widget envelope).

Widgets:
  battery_anatomy   (live)     SOC · DC bus V/A + electrical status · temperature
  autonomy_readiness(live)     autonomy envelope/index · limited-by · runtime · headroom · transfer
  battery_history   (bucketed) range×sampling: limiting/SOC/DC-bus/thermal scores + peak temp
  autonomy_history  (bucketed) range×sampling: autonomy index/runtime score/load pressure/min runtime
"""
from .._widgets_base import (
    BaseWidgetStrategy, _BaseWidgetDispatcher, StaticKpi, BucketedSeries,
)
from .._timefilters import build_bucket_edges


_BAT_SCORE_COLS = [
    'ups_battery_limiting_score', 'ups_battery_soc_score',
    'ups_battery_dc_bus_quality_score', 'ups_battery_thermal_score',
    'ups_battery_peak_temp_c',
]
_AUT_COLS = [
    'ups_autonomy_index', 'ups_runtime_score', 'ups_min_runtime_min',
    'ups_load_headroom_pct', 'ups_kva_used_pct',
]


class UpsBatteryAutonomy(BaseWidgetStrategy):
    widgets = [
        StaticKpi('battery_anatomy', columns=[
            'ups_battery_soc_pct', 'ups_battery_dc_bus_voltage_v', 'ups_battery_dc_current_a',
            'ups_battery_electrical_status', 'ups_battery_temperature_c', 'ups_battery_peak_temp_c',
        ]),
        StaticKpi('autonomy_readiness', columns=[
            'ups_autonomy_index', 'ups_autonomy_limited_by', 'ups_autonomy_min',
            'ups_runtime_target_min', 'ups_load_headroom_pct', 'ups_inverter_status',
            'ups_operating_mode',
        ]),
        BucketedSeries('battery_history', default_range='today', default_sampling='hourly'),
        BucketedSeries('autonomy_history', default_range='today', default_sampling='hourly'),
    ]

    async def render_bucketed(self, d, widget, range_token, sampling, custom_start=None, custom_end=None):
        edges = build_bucket_edges(range_token, sampling, custom_start, custom_end)

        if widget.name == 'battery_history':
            rows = await d.bucketed(_BAT_SCORE_COLS, range_token, sampling, custom_start, custom_end)
            by = {r['bucket']: r for r in rows}
            series = [{
                'label': lbl,
                'limiting': by.get(s, {}).get('ups_battery_limiting_score_avg'),
                'soc':      by.get(s, {}).get('ups_battery_soc_score_avg'),
                'dc_bus':   by.get(s, {}).get('ups_battery_dc_bus_quality_score_avg'),
                'thermal':  by.get(s, {}).get('ups_battery_thermal_score_avg'),
                'peak_temp': by.get(s, {}).get('ups_battery_peak_temp_c_max'),
            } for s, _e, lbl in edges]
            now = await d.latest([*_BAT_SCORE_COLS, 'ups_battery_charge_state']) or {}
            return {'range': range_token, 'sampling': sampling, 'series': series, 'now': {
                'limiting': now.get('ups_battery_limiting_score'),
                'soc': now.get('ups_battery_soc_score'),
                'dc_bus': now.get('ups_battery_dc_bus_quality_score'),
                'thermal': now.get('ups_battery_thermal_score'),
                'mode_state': now.get('ups_battery_charge_state'),
                'peak_temp': now.get('ups_battery_peak_temp_c'),
            }}

        # autonomy_history
        rows = await d.bucketed(_AUT_COLS, range_token, sampling, custom_start, custom_end)
        by = {r['bucket']: r for r in rows}
        series = [{
            'label': lbl,
            'autonomy_index': by.get(s, {}).get('ups_autonomy_index_avg'),
            'runtime_score':  by.get(s, {}).get('ups_runtime_score_avg'),
            'load_pressure':  by.get(s, {}).get('ups_kva_used_pct_avg'),
            'min_runtime':    by.get(s, {}).get('ups_min_runtime_min_min'),
        } for s, _e, lbl in edges]
        now = await d.latest([*_AUT_COLS, 'ups_autonomy_min', 'ups_inverter_status']) or {}
        return {'range': range_token, 'sampling': sampling, 'series': series, 'now': {
            'autonomy_index': now.get('ups_autonomy_index'),
            'runtime_score': now.get('ups_runtime_score'),
            'runtime_now': now.get('ups_autonomy_min'),
            'load_headroom': now.get('ups_load_headroom_pct'),
            'load_pressure': now.get('ups_kva_used_pct'),
            'transfer_state': now.get('ups_inverter_status'),
            'min_runtime': now.get('ups_min_runtime_min'),
        }}


class UpsBatteryAutonomyDispatcher(_BaseWidgetDispatcher):
    PAGE_CODE  = 'ups-battery-autonomy'
    ASSET_TYPE = 'ups'
    STRATEGY   = UpsBatteryAutonomy
