"""UPS — Output Load & Capacity tab (widget envelope).

Same shape as Source & Transfer:
  capacity_index    (live)     headroom + limiting factor + kVA/kW/current scores
  kw_score          (live)     PF-rated target / measured kW / free kW / PF penalty
  activity_30d      (bucketed) 30-day daily load % (AVG)
  score_envelope_24h(windowed) 24h min/max/avg of the headroom score
  composite_timeline(bucketed) range×sampling: output kVA + headroom % + operating mode
"""
from .._widgets_base import (
    BaseWidgetStrategy, _BaseWidgetDispatcher, StaticKpi, WindowedKpi, BucketedSeries,
)
from .._timefilters import build_bucket_edges


class UpsOutputCapacity(BaseWidgetStrategy):
    CONFIG_TABLE = 'ups_config'

    widgets = [
        StaticKpi('capacity_index', columns=[
            'ups_capacity_headroom_score', 'ups_capacity_limiting_factor',
            'ups_capacity_kva_score', 'ups_capacity_kw_score', 'ups_capacity_current_score',
        ]),
        StaticKpi('kw_score', columns=[
            'ups_kw_capacity_target_kw', 'active_power_total_kw',
            'ups_kw_headroom_kw', 'power_factor_total',
        ]),
        BucketedSeries('activity_30d', default_range='last-30-days', default_sampling='daily',
                       ranges=['last-30-days']),
        WindowedKpi('score_envelope_24h', ranges=['24h'], default_range='24h'),
        BucketedSeries('composite_timeline', default_range='today', default_sampling='hourly'),
    ]

    async def render_static(self, d):
        cfg = await d.config_row(self.CONFIG_TABLE) or {}
        return {
            'rated_kva': cfg.get('rated_kva') or cfg.get('kva_rating'),
            'overload_pct': 125, 'watch_pct': 50, 'headroom_floor_pct': 30,
        }

    async def render_windowed(self, d, widget, range_token):
        stats = await d.window_stats('ups_capacity_headroom_score', 'last-24h') or {}
        return {
            'range': '24h',
            'min': round(stats['min'], 1) if 'min' in stats else None,
            'max': round(stats['max'], 1) if 'max' in stats else None,
            'avg': round(stats['avg'], 1) if 'avg' in stats else None,
        }

    async def render_bucketed(self, d, widget, range_token, sampling, custom_start=None, custom_end=None):
        edges = build_bucket_edges(range_token, sampling, custom_start, custom_end)

        if widget.name == 'activity_30d':
            rows = await d.bucketed(['ups_kva_used_pct'], range_token, sampling, custom_start, custom_end)
            by = {r['bucket']: r for r in rows}
            series, vals = [], []
            for s, _e, lbl in edges:
                v = by.get(s, {}).get('ups_kva_used_pct_avg')
                series.append({'label': lbl, 'load_pct': v})
                if v is not None:
                    vals.append(v)
            return {'range': range_token, 'sampling': sampling, 'series': series, 'now': {
                'peak_pct': round(max(vals), 1) if vals else None,
                'avg_pct': round(sum(vals) / len(vals), 1) if vals else None,
            }}

        # composite_timeline
        rows = await d.bucketed(['apparent_power_total_kva', 'ups_capacity_headroom_score'],
                                range_token, sampling, custom_start, custom_end)
        by = {r['bucket']: r for r in rows}
        modes = await d.bucket_last('ups_operating_mode', range_token, sampling, custom_start, custom_end)
        series = [{
            'label': lbl,
            'output_kva': by.get(s, {}).get('apparent_power_total_kva_avg'),
            'headroom_pct': by.get(s, {}).get('ups_capacity_headroom_score_avg'),
            'mode': modes.get(s),
        } for s, _e, lbl in edges]
        now = await d.latest(['apparent_power_total_kva', 'ups_capacity_headroom_score',
                              'ups_kva_free_kva', 'ups_operating_mode']) or {}
        return {'range': range_token, 'sampling': sampling, 'series': series, 'now': {
            'output_kva': now.get('apparent_power_total_kva'),
            'headroom_pct': now.get('ups_capacity_headroom_score'),
            'kva_free': now.get('ups_kva_free_kva'),
            'mode': now.get('ups_operating_mode'),
        }}


class UpsOutputCapacityDispatcher(_BaseWidgetDispatcher):
    PAGE_CODE  = 'ups-output-capacity'
    ASSET_TYPE = 'ups'
    STRATEGY   = UpsOutputCapacity
