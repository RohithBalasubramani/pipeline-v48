"""LT Transformer — Thermal & Life tab.

Widget-envelope page (single asset type). Widgets:
  config         (static)  nameplate denominators + chart reference lines
  kpi_cards      (live)     thermal stress / loss / load / efficiency / life / derating
  thermal_monitor(live)     winding / oil / hotspot / ambient temps + status + today peak
  thermal_series (bucketed) range×sampling history: hotspot, oil, load, efficiency
  peak_heatmap   (windowed) today/week/month per-3h-slot MAX of the 4 temps
"""
from .._widgets_base import (
    BaseWidgetStrategy, _BaseWidgetDispatcher, StaticKpi, LiveBars,
    BucketedSeries, WindowedKpi,
)
from .._timefilters import build_bucket_edges


_HEATMAP_COLS = [
    'winding_temperature_c', 'top_oil_temperature_c',
    'winding_hotspot_temperature_c', 'ambient_temperature_c',
]
_TOD_SLOTS = ['00-03', '03-06', '06-09', '09-12', '12-15', '15-18', '18-21', '21-24']


class LtTransformerThermal(BaseWidgetStrategy):
    CONFIG_TABLE = 'transformer_config'

    widgets = [
        StaticKpi('kpi_cards', columns=[
            'thermal_stress_pct', 'total_loss_with_aux_kw', 'kpi_kw_load_pct_of_rated',
            'efficiency_pct', 'remaining_useful_life_years', 'insulation_life_consumed_pct',
            'faa_acceleration_factor', 'derated_capacity_kva', 'derating_headroom_kva',
        ]),
        LiveBars('thermal_monitor', columns=[
            'winding_temperature_c', 'top_oil_temperature_c',
            'winding_hotspot_temperature_c', 'ambient_temperature_c',
            'winding_thermal_status', 'oil_thermal_status',
            'hotspot_thermal_status', 'ambient_thermal_status',
            'peak_hotspot_today_c', 'peak_hotspot_at_time',
        ]),
        BucketedSeries('thermal_series',
                       columns=['winding_hotspot_temperature_c', 'top_oil_temperature_c',
                                'kpi_kw_load_pct_of_rated', 'efficiency_pct'],
                       default_range='last-7-days', default_sampling='daily'),
        WindowedKpi('peak_heatmap', ranges=['today', 'week', 'month'], default_range='today'),
    ]

    async def render_static(self, d):
        cfg = await d.config_row(self.CONFIG_TABLE) or {}
        return {
            'rated_kva': cfg.get('rated_kva'),
            'design_life_years': cfg.get('design_life_years'),
            'rated_efficiency_pct': cfg.get('rated_efficiency_pct'),
            'hotspot_warning_temp_c': cfg.get('hotspot_warning_temp_c'),
            'hotspot_critical_temp_c': cfg.get('hotspot_critical_temp_c'),
            'oil_high_temp_c': cfg.get('oil_high_temp_c'),
            'winding_high_temp_c': cfg.get('winding_high_temp_c'),
            'ambient_high_temp_c': cfg.get('ambient_high_temp_c'),
        }

    async def render_bucketed(self, d, widget, range_token, sampling,
                              custom_start=None, custom_end=None):
        rows = await d.bucketed(widget.columns, range_token, sampling, custom_start, custom_end)
        by_bucket = {r['bucket']: r for r in rows}
        edges = build_bucket_edges(range_token, sampling, custom_start, custom_end)
        series = []
        for start, _end, label in edges:
            r = by_bucket.get(start, {})
            series.append({
                'label': label,
                'hotspot': r.get('winding_hotspot_temperature_c_max'),
                'oil': r.get('top_oil_temperature_c_max'),
                'load': r.get('kpi_kw_load_pct_of_rated_avg'),
                'efficiency': r.get('efficiency_pct_avg'),
            })
        return {'range': range_token, 'sampling': sampling, 'series': series}

    async def render_windowed(self, d, widget, range_token):
        peaks = await d.tod_peaks(_HEATMAP_COLS, range_token)  # {slot: {col: max}}

        def row(col):
            return [(peaks.get(i) or {}).get(col) for i in range(len(_TOD_SLOTS))]

        return {
            'range': range_token,
            'slots': _TOD_SLOTS,
            'rows': {
                'winding_hv': row('winding_temperature_c'),
                'oil_top':    row('top_oil_temperature_c'),
                'hot_spot':   row('winding_hotspot_temperature_c'),
                'ambient':    row('ambient_temperature_c'),
            },
        }


class LtTransformerThermalDispatcher(_BaseWidgetDispatcher):
    PAGE_CODE  = 'lt-transformer-thermal'
    ASSET_TYPE = 'lt_transformer'
    STRATEGY   = LtTransformerThermal
