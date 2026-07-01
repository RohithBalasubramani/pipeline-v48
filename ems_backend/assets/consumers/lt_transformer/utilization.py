"""LT Transformer — Utilization tab.

Widget-envelope page. Simpler than Thermal & Life — no range×sampling dropdown:
  config       (static)  rated kVA + load threshold lines (70/85/100 %)
  kpi_cards    (live)     TUF lifetime · live load · peak today · efficiency
  load_history (windowed) fixed last-24h hourly load % (avg + peak)
"""
from .._widgets_base import (
    BaseWidgetStrategy, _BaseWidgetDispatcher, StaticKpi, WindowedKpi,
)
from ...services import LOCAL_TZ


class LtTransformerUtilization(BaseWidgetStrategy):
    CONFIG_TABLE = 'transformer_config'

    widgets = [
        StaticKpi('kpi_cards', columns=[
            'tuf_lifetime_pct', 'max_demand_lifetime_kva',
            'kva_utilization_pct', 'demand_present_kva',
            'peak_load_pct_today', 'peak_load_pct_today_at_time', 'demand_max_kva',
            'efficiency_pct', 'lv_output_kw', 'hv_input_kw', 'kpi_kw_load_pct_of_rated',
        ]),
        WindowedKpi('load_history', ranges=['24h'], default_range='24h'),
    ]

    async def render_static(self, d):
        cfg = await d.config_row(self.CONFIG_TABLE) or {}
        return {
            'rated_kva': cfg.get('rated_kva'),
            'load_watch_pct': 70, 'load_warning_pct': 85, 'nameplate_pct': 100,
        }

    async def render_windowed(self, d, widget, range_token):
        # Fixed trailing-24h hourly load %, against the kVA plate.
        rows = await d.bucketed(['kva_utilization_pct'], 'last-24h', 'hour')
        series, vals, peak = [], [], None
        for r in rows:
            avg = r.get('kva_utilization_pct_avg')
            mx = r.get('kva_utilization_pct_max')
            bucket = r.get('bucket')
            label = bucket.astimezone(LOCAL_TZ).strftime('%H:%M') if bucket else ''
            series.append({'label': label, 'load_pct': avg, 'peak_pct': mx})
            if avg is not None:
                vals.append(avg)
            if mx is not None:
                peak = mx if peak is None else max(peak, mx)
        return {
            'range': '24h',
            'series': series,
            'peak_pct': round(peak, 1) if peak is not None else None,
            'avg_pct': round(sum(vals) / len(vals), 1) if vals else None,
        }


class LtTransformerUtilizationDispatcher(_BaseWidgetDispatcher):
    PAGE_CODE  = 'lt-transformer-utilization'
    ASSET_TYPE = 'lt_transformer'
    STRATEGY   = LtTransformerUtilization
