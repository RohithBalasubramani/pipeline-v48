"""LT Transformer — Loss Analysis tab (widget envelope).

Widgets:
  loss_inspector  (windowed) pick one hour of TODAY ("00:00"…"23:00") → that
                             hour's loss composition (totals + drivers list).
  loss_timeline   (bucketed) range×sampling stacked-loss + efficiency/load lines.
  performance_map (windowed) operating point + last-24h hourly scatter
                             (load × actual/expected loss) + component stack.
  config          (static)   best/watch/critical zones (chart bands).
"""
from datetime import datetime

from .._widgets_base import (
    BaseWidgetStrategy, _BaseWidgetDispatcher, WindowedKpi, BucketedSeries,
)
from .._timefilters import build_bucket_edges
from ...services import LOCAL_TZ


def _r(v, ndigits=2):
    return round(v, ndigits) if v is not None else None


_INSPECTOR_SAMPLING = {
    'today':         'hourly',   # 3 h buckets, 00:00 … 21:00
    'yesterday':     'hourly',
    'last-7-days':   'daily',    # D-6 … Today
    'last-30-days':  'daily',
    'this-month':    'daily',
    'last-month':    'daily',
    'last-90-days':  'weekly',   # ~13 weekly buckets
    'last-365-days': 'weekly',
    'custom-range':  'daily',    # overridden by duration heuristic below
}


def _sampling_for_custom(start_iso: str, end_iso: str) -> str:
    """Custom-range duration → sensible sampling."""
    from datetime import datetime
    try:
        s = datetime.fromisoformat((start_iso or '').replace('Z', '+00:00'))
        e = datetime.fromisoformat((end_iso or '').replace('Z', '+00:00'))
    except Exception:
        return 'daily'
    days = max((e - s).total_seconds() / 86400.0, 0)
    if days <= 2:   return 'hourly'
    if days <= 45:  return 'daily'
    return 'weekly'


class LtTransformerLossAnalysis(BaseWidgetStrategy):
    widgets = [
        # Two filters: date `range` + `bucket` label. The bucket dropdown
        # adapts per range (hourly slots for today/yesterday, days for 7D/30D,
        # weeks for 3M/1Y). `available_buckets` is returned with each render.
        WindowedKpi('loss_inspector',
                    ranges=['today', 'yesterday', 'last-7-days', 'last-30-days',
                            'this-month', 'last-month', 'last-90-days',
                            'last-365-days', 'custom-range'],
                    default_range='today'),
        BucketedSeries('loss_timeline', default_range='today', default_sampling='hourly'),
        WindowedKpi('performance_map', ranges=['last-24h'], default_range='last-24h'),
    ]

    async def render_static(self, d):
        return {
            'best_zone':     {'load_min': 55, 'load_max': 75, 'label': 'highest efficiency band'},
            'watch_zone':    {'load_min': 75, 'load_max': 90, 'label': 'copper loss rises faster'},
            'critical_zone': {'load_above': 90, 'efficiency_below_pct': 98.4},
        }

    async def render_windowed(self, d, widget, range_token):
        if widget.name == 'loss_inspector':
            return await self._render_inspector(d, range_token)
        if widget.name == 'performance_map':
            return await self._render_performance_map(d)
        return {}

    async def _render_inspector(self, d, date_token):
        """Two filters: date_token (today/yesterday/7D/30D/3M/1Y/custom-range)
        + bucket label read from the dispatcher's per-widget state. Sampling
        adapts per range — hourly for single days, daily for week/month ranges,
        weekly for multi-month ranges. `available_buckets` ships with the
        block so the frontend dropdown knows what's selectable."""
        bucket_label = (d._buckets.get('loss_inspector') or '').strip()
        custom = d._windowed_custom.get('loss_inspector', {}) or {}
        cs, ce = custom.get('start'), custom.get('end')
        if date_token == 'custom-range':
            sampling = _sampling_for_custom(cs, ce)
        else:
            sampling = _INSPECTOR_SAMPLING.get(date_token, 'daily')
        edges = build_bucket_edges(date_token, sampling, cs, ce)

        # Resolve the picked edge.
        picked = None
        if bucket_label:
            for s, e, lbl in edges:
                if lbl == bucket_label:
                    picked = (s, e, lbl)
                    break
        if picked is None:
            now_local = datetime.now(LOCAL_TZ)
            candidates = [(s, e, lbl) for s, e, lbl in edges if s.astimezone(LOCAL_TZ) <= now_local]
            picked = candidates[-1] if candidates else (edges[-1] if edges else None)
        if picked is None:
            return {'range': date_token, 'sampling': sampling, 'bucket': bucket_label,
                    'has_data': False, 'available_buckets': []}
        s_, _e, picked_label = picked

        rows = await d.bucketed(
            ['copper_loss_kw', 'iron_loss_kw', 'stray_loss_kw', 'cooling_aux_loss_kw',
             'total_loss_with_aux_kw', 'efficiency_pct', 'kpi_kw_load_pct_of_rated',
             'k_factor', 'voltage_regulation_pct', 'remaining_useful_life_years'],
            date_token, sampling, cs, ce,
        )
        row = next((r for r in rows if r['bucket'] == s_), {}) or {}
        cu    = row.get('copper_loss_kw_avg')
        core  = row.get('iron_loss_kw_avg')
        stray = row.get('stray_loss_kw_avg')
        aux   = row.get('cooling_aux_loss_kw_avg')
        total = row.get('total_loss_with_aux_kw_avg')
        load  = row.get('kpi_kw_load_pct_of_rated_avg')
        kf    = row.get('k_factor_avg')
        reg   = row.get('voltage_regulation_pct_avg')

        def pct(v):
            return round((v / total) * 100, 0) if (v is not None and total) else None

        return {
            'range': date_token,
            'sampling': sampling,
            'bucket': picked_label,
            'available_buckets': [lbl for _s, _e, lbl in edges],
            'has_data': total is not None,
            'totals': {
                'total': _r(total), 'copper': _r(cu), 'core': _r(core),
                'stray': _r(stray), 'aux': _r(aux),
                'efficiency_pct': _r(row.get('efficiency_pct_avg'), 3),
            },
            'focus': {
                'load_pct': _r(load, 1),
                'k_factor': _r(kf, 2),
                'rul_years': _r(row.get('remaining_useful_life_years_avg'), 1),
            },
            'drivers': [
                {'name': 'Winding I2R',    'kw': _r(cu),    'pct': pct(cu),
                 'badge': f'{load:.1f}% load' if load is not None else None},
                {'name': 'Core / no-load', 'kw': _r(core),  'pct': pct(core),
                 'badge': f'{reg:.2f}% reg' if reg is not None else None},
                {'name': 'Harmonic stray', 'kw': _r(stray), 'pct': pct(stray),
                 'badge': f'K {kf:.2f}' if kf is not None else None},
                {'name': 'Cooling aux',    'kw': _r(aux),   'pct': pct(aux), 'badge': 'base draw'},
            ],
        }

    async def _render_performance_map(self, d):
        rows = await d.bucketed(
            ['kpi_kw_load_pct_of_rated', 'total_loss_with_aux_kw',
             'expected_loss_kw', 'efficiency_pct'],
            'last-24h', 'hour',
        )
        points = [{
            'load_pct':       r.get('kpi_kw_load_pct_of_rated_avg'),
            'actual_kw':      r.get('total_loss_with_aux_kw_avg'),
            'expected_kw':    r.get('expected_loss_kw_avg'),
            'efficiency_pct': r.get('efficiency_pct_avg'),
        } for r in rows]
        op = await d.latest([
            'kpi_kw_load_pct_of_rated', 'total_loss_with_aux_kw',
            'hv_input_kw', 'lv_output_kw', 'active_power_loss_pct',
            'loss_vs_expected_curve_kw', 'copper_loss_kw', 'iron_loss_kw',
            'stray_loss_kw', 'cooling_aux_loss_kw',
        ]) or {}
        return {
            'range': 'last-24h',
            'points': points,
            'operating_point': {
                'load_pct':        op.get('kpi_kw_load_pct_of_rated'),
                'loss_kw':         op.get('total_loss_with_aux_kw'),
                'input_kw':        op.get('hv_input_kw'),
                'output_kw':       op.get('lv_output_kw'),
                'loss_pct':        op.get('active_power_loss_pct'),
                'delta_vs_curve':  op.get('loss_vs_expected_curve_kw'),
                'components': {
                    'cu':   op.get('copper_loss_kw'),
                    'core': op.get('iron_loss_kw'),
                    'harm': op.get('stray_loss_kw'),
                    'aux':  op.get('cooling_aux_loss_kw'),
                },
            },
        }

    async def render_bucketed(self, d, widget, range_token, sampling, custom_start=None, custom_end=None):
        # loss_timeline only
        cols = ['copper_loss_kw', 'iron_loss_kw', 'stray_loss_kw', 'cooling_aux_loss_kw',
                'total_loss_with_aux_kw', 'efficiency_pct', 'kpi_kw_load_pct_of_rated']
        rows = await d.bucketed(cols, range_token, sampling, custom_start, custom_end)
        by = {r['bucket']: r for r in rows}
        edges = build_bucket_edges(range_token, sampling, custom_start, custom_end)
        series = [{
            'label':      lbl,
            'copper':     by.get(s, {}).get('copper_loss_kw_avg'),
            'core':       by.get(s, {}).get('iron_loss_kw_avg'),
            'stray':      by.get(s, {}).get('stray_loss_kw_avg'),
            'aux':        by.get(s, {}).get('cooling_aux_loss_kw_avg'),
            'total':      by.get(s, {}).get('total_loss_with_aux_kw_avg'),
            'efficiency': by.get(s, {}).get('efficiency_pct_avg'),
            'load':       by.get(s, {}).get('kpi_kw_load_pct_of_rated_avg'),
        } for s, _e, lbl in edges]
        now = await d.latest(cols) or {}
        return {'range': range_token, 'sampling': sampling, 'series': series, 'now': {
            'total':      now.get('total_loss_with_aux_kw'),
            'copper':     now.get('copper_loss_kw'),
            'core':       now.get('iron_loss_kw'),
            'stray':      now.get('stray_loss_kw'),
            'aux':        now.get('cooling_aux_loss_kw'),
            'efficiency': now.get('efficiency_pct'),
            'load':       now.get('kpi_kw_load_pct_of_rated'),
        }}


class LtTransformerLossAnalysisDispatcher(_BaseWidgetDispatcher):
    PAGE_CODE  = 'lt-transformer-loss'
    ASSET_TYPE = 'lt_transformer'
    STRATEGY   = LtTransformerLossAnalysis
