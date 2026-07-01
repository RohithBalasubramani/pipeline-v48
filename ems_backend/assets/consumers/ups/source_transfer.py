"""UPS — Source & Transfer tab (widget envelope).

Widgets:
  transfer_index    (live)     composite + readiness + limiting + input/bypass/sync permissive scores
  sync_score        (live)     measured bypass Hz + sync deviation (target/penalty from config)
  activity_30d      (bucketed) 30-day daily transfer-event histogram (Δ of the lifetime counter)
  score_envelope_24h(windowed) 24h min/max/avg of the composite score
  composite_timeline(bucketed) range×sampling multi-series (Input/Bypass V, Input I, Bypass Hz,
                               Readiness, Transfer events) + per-bucket operating mode + now legend
"""
from .._widgets_base import (
    BaseWidgetStrategy, _BaseWidgetDispatcher, StaticKpi, WindowedKpi, BucketedSeries,
)
from .._timefilters import build_bucket_edges


_TRANSFERS_DELTA = 'MAX("ups_transfers_lifetime") - MIN("ups_transfers_lifetime")'
_TIMELINE_COLS = [
    'ups_input_voltage_v', 'ups_bypass_voltage_v', 'ups_input_current_a',
    'ups_bypass_frequency_hz', 'ups_transfer_composite_score',
]


class UpsSourceTransfer(BaseWidgetStrategy):
    CONFIG_TABLE = 'ups_config'

    widgets = [
        StaticKpi('transfer_index', columns=[
            'ups_transfer_composite_score', 'ups_transfer_readiness_status',
            'ups_transfer_limiting_permissive', 'ups_input_permissive_score',
            'ups_bypass_permissive_score', 'ups_sync_permissive_score',
        ]),
        StaticKpi('sync_score', columns=[
            'ups_bypass_frequency_hz', 'ups_sync_deviation_hz',
        ]),
        BucketedSeries('activity_30d', default_range='last-30-days', default_sampling='daily',
                       ranges=['last-30-days']),
        WindowedKpi('score_envelope_24h', ranges=['24h'], default_range='24h'),
        BucketedSeries('composite_timeline', default_range='today', default_sampling='hourly'),
    ]

    async def render_static(self, d):
        return {
            'sync_target_hz': 50.0,
            'sync_penalty_per_hz': -1200,
            'readiness_ready': 70,
            'input_v_low': 390,
        }

    async def render_windowed(self, d, widget, range_token):
        # score_envelope_24h — 24h min/max/avg of the composite score.
        stats = await d.window_stats('ups_transfer_composite_score', 'last-24h') or {}
        return {
            'range': '24h',
            'min': round(stats['min'], 1) if 'min' in stats else None,
            'max': round(stats['max'], 1) if 'max' in stats else None,
            'avg': round(stats['avg'], 1) if 'avg' in stats else None,
        }

    async def render_bucketed(self, d, widget, range_token, sampling, custom_start=None, custom_end=None):
        edges = build_bucket_edges(range_token, sampling, custom_start, custom_end)

        if widget.name == 'activity_30d':
            rows = await d.bucketed([], range_token, sampling, custom_start, custom_end,
                                    extra_aggregates={'transfers': _TRANSFERS_DELTA})
            by = {r['bucket']: r for r in rows}
            series = [{'label': lbl, 'transfers': int(by.get(s, {}).get('transfers') or 0)}
                      for s, _e, lbl in edges]
            now = await d.latest(['ups_transfers_lifetime', 'ups_transfers_30d',
                                  'ups_days_since_last_transfer', 'ups_last_transfer_type']) or {}
            return {'range': range_token, 'sampling': sampling, 'series': series, 'now': {
                'lifetime': now.get('ups_transfers_lifetime'),
                'last_30d': now.get('ups_transfers_30d'),
                'days_since_last': now.get('ups_days_since_last_transfer'),
                'last_type': now.get('ups_last_transfer_type'),
            }}

        # composite_timeline — multi-series + per-bucket mode
        rows = await d.bucketed(_TIMELINE_COLS, range_token, sampling, custom_start, custom_end,
                                extra_aggregates={'transfer_events': _TRANSFERS_DELTA})
        by = {r['bucket']: r for r in rows}
        modes = await d.bucket_last('ups_operating_mode', range_token, sampling, custom_start, custom_end)
        series = [{
            'label': lbl,
            'input_v':  by.get(s, {}).get('ups_input_voltage_v_avg'),
            'bypass_v': by.get(s, {}).get('ups_bypass_voltage_v_avg'),
            'input_i':  by.get(s, {}).get('ups_input_current_a_avg'),
            'bypass_hz': by.get(s, {}).get('ups_bypass_frequency_hz_avg'),
            'readiness': by.get(s, {}).get('ups_transfer_composite_score_avg'),
            'transfer_events': int(by.get(s, {}).get('transfer_events') or 0),
            'mode': modes.get(s),
        } for s, _e, lbl in edges]
        now = await d.latest([*_TIMELINE_COLS, 'ups_operating_mode']) or {}
        return {'range': range_token, 'sampling': sampling, 'series': series, 'now': {
            'input_v': now.get('ups_input_voltage_v'),
            'bypass_v': now.get('ups_bypass_voltage_v'),
            'input_i': now.get('ups_input_current_a'),
            'bypass_hz': now.get('ups_bypass_frequency_hz'),
            'readiness': now.get('ups_transfer_composite_score'),
            'mode': now.get('ups_operating_mode'),
        }}


class UpsSourceTransferDispatcher(_BaseWidgetDispatcher):
    PAGE_CODE  = 'ups-source-transfer'
    ASSET_TYPE = 'ups'
    STRATEGY   = UpsSourceTransfer
