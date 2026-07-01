"""Base classes for widget-envelope pages (Overview + the deep transformer tabs).

These pages don't stream a flat (column, value) row — each card is its own
block, and widgets have independent cadences and **independent filters** (same
vocabulary, used per-widget):

  LiveGauge / LiveSpark / LiveBars / StaticKpi  — rebuilt every tick from the
                                                  latest row.
  WindowedKpi    — window-filtered (today / week / month). Re-rendered on a
                   slow poll and on a `{"widget","range"}` command. The block
                   shape is whatever the strategy returns (a KPI dict, or a
                   per-time-of-day heatmap, …).
  BucketedSeries — range × sampling history (the days/shifts/hours vocab from
                   `_timefilters`). Re-rendered on a `{"widget","range",
                   "sampling"[,"start","end"]}` command and a slow poll.

A dispatcher binds to ONE strategy. Single-type pages set `STRATEGY` (+ an
optional `ASSET_TYPE` guard); the shared Overview sets `STRATEGIES` keyed by
asset category.
"""

import asyncio
import json
from dataclasses import dataclass, field

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from ..models import Asset
from ..services import (
    fetch_live, fetch_period_delta, fetch_config_row, fetch_bucketed,
    fetch_tod_peaks, fetch_window_stats, fetch_bucket_last, resolve_range,
)
from ._dispatch import lookup_strategy, resolve_category
from ._timefilters import (
    canonical_range, canonical_sampling, validate_range_sampling, SAMPLING_BY_RANGE,
)
from ._serializer import fallback as _fallback


# ─────────────────────────────────────────────────────────────────────────────
# Widget shape primitives
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _WidgetBase:
    name: str
    columns: list[str] = field(default_factory=list)


@dataclass
class LiveGauge(_WidgetBase):
    status: callable = None
    status_column: str = None


@dataclass
class LiveSpark(_WidgetBase):
    status: callable = None
    status_column: str = None


@dataclass
class LiveBars(_WidgetBase):
    status: callable = None
    status_column: str = None


@dataclass
class StaticKpi(_WidgetBase):
    status: callable = None
    status_column: str = None


@dataclass
class WindowedKpi(_WidgetBase):
    """Window-filtered widget. Strategy owns the render via `render_windowed`."""
    ranges: list[str] = field(default_factory=lambda: ['today', 'week', 'month'])
    default_range: str = 'today'
    refresh_seconds: float = 30.0


@dataclass
class BucketedSeries(_WidgetBase):
    """range × sampling history series. Strategy owns the render via
    `render_bucketed`; allowed combos come from `_timefilters`. `ranges` is the
    UI range list (the descriptor also ships the allowed sampling per range)."""
    default_range: str = 'today'
    default_sampling: str = 'hourly'
    ranges: list[str] = field(default_factory=lambda: ['today', 'last-7-days', 'last-30-days'])
    refresh_seconds: float = 30.0


_LIVE_KINDS = (LiveGauge, LiveSpark, LiveBars, StaticKpi)


# ─────────────────────────────────────────────────────────────────────────────
# Strategy
# ─────────────────────────────────────────────────────────────────────────────

class BaseWidgetStrategy:
    """Declares `widgets = [...]` in render order. Override `render_windowed`
    for WindowedKpi widgets and `render_bucketed` for BucketedSeries widgets."""

    widgets: list = []
    interval_seconds: float = 1.0

    def __init__(self, asset, query_string: bytes = b''):
        self.asset = asset
        self._query_string = query_string

    def is_configured(self) -> bool:
        return bool(self.widgets)

    # ── live (per-tick) ────────────────────────────────────────────────────

    def live_columns(self) -> list[str]:
        cols: list[str] = []
        for w in self.widgets:
            if isinstance(w, _LIVE_KINDS):
                for c in w.columns:
                    if c not in cols:
                        cols.append(c)
        return cols

    def render_widgets(self, row: dict) -> dict:
        out = {}
        for w in self.widgets:
            if not isinstance(w, _LIVE_KINDS):
                continue
            block = {c: row.get(c) for c in w.columns}
            if w.status is not None:
                drive_col = w.status_column or (w.columns[0] if w.columns else None)
                drive_val = row.get(drive_col) if drive_col else None
                label = w.status(drive_val) if drive_val is not None else None
                if label:
                    block['status'] = label
            out[w.name] = block
        return out

    # ── filtered widgets ────────────────────────────────────────────────────

    def windowed_widgets(self) -> list[WindowedKpi]:
        return [w for w in self.widgets if isinstance(w, WindowedKpi)]

    def bucketed_widgets(self) -> list[BucketedSeries]:
        return [w for w in self.widgets if isinstance(w, BucketedSeries)]

    async def render_windowed(self, dispatcher, widget: 'WindowedKpi', range_token: str) -> dict:
        raise NotImplementedError

    async def render_bucketed(self, dispatcher, widget: 'BucketedSeries',
                              range_token: str, sampling: str,
                              custom_start: str = None, custom_end: str = None) -> dict:
        raise NotImplementedError

    async def render_static(self, dispatcher) -> dict | None:
        """Optional one-time static block (nameplate / thresholds — denominators
        and chart reference lines). Included in the snapshot under
        widgets['config']; NOT re-sent on ticks. Default: none."""
        return None

    # ── layout catalogue (sent in snapshot) ────────────────────────────────

    def widget_descriptors(self) -> list[dict]:
        out = []
        for w in self.widgets:
            entry = {'name': w.name, 'kind': type(w).__name__}
            cols = getattr(w, 'columns', None)
            if cols:
                entry['columns'] = list(cols)
            if isinstance(w, WindowedKpi):
                entry['ranges'] = list(w.ranges)
                entry['default_range'] = w.default_range
            if isinstance(w, BucketedSeries):
                entry['default_range'] = w.default_range
                entry['default_sampling'] = w.default_sampling
                entry['ranges'] = list(w.ranges)
                entry['sampling_by_range'] = {
                    r: list(SAMPLING_BY_RANGE.get(r, ())) for r in w.ranges
                }
            out.append(entry)
        return out


class StubWidgetStrategy(BaseWidgetStrategy):
    """Marker for strategies not yet specified — dispatcher sends 'pending'."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class _BaseWidgetDispatcher(AsyncWebsocketConsumer):
    """Widget-envelope dispatcher. Set STRATEGY (single-type, + optional
    ASSET_TYPE guard) or STRATEGIES (per-category map, e.g. shared Overview)."""

    PAGE_CODE: str = ''
    STRATEGY: type | None = None
    STRATEGIES: dict[str, type] = {}
    ASSET_TYPE: str | None = None

    _MAX_CONSECUTIVE_ERRORS: int = 10

    async def connect(self):
        self.asset_pk = self.scope['url_route']['kwargs']['asset_id']
        try:
            self.asset = await self._get_asset(self.asset_pk)
        except Asset.DoesNotExist:
            await self.accept()
            await self._send_error(f'Asset {self.asset_pk} not found')
            await self.close(code=4404)
            return
        if not self.asset.asset_id:
            await self.accept()
            await self._send_error('Asset has no asset_id configured')
            await self.close(code=4400)
            return

        if self.STRATEGY is not None:
            type_code = resolve_category(self.asset)
            if self.ASSET_TYPE and self.ASSET_TYPE not in (type_code, self.asset.asset_type.code):
                await self.accept()
                await self._send_error(
                    f"Page '{self.PAGE_CODE}' is for '{self.ASSET_TYPE}' assets, not '{type_code}'")
                await self.close(code=4404)
                return
            StrategyCls = self.STRATEGY
        else:
            StrategyCls, type_code = lookup_strategy(self.STRATEGIES, self.asset)
            if StrategyCls is None:
                await self.accept()
                await self._send_error(
                    f"Page '{self.PAGE_CODE}' not configured for category '{type_code}'")
                await self.close(code=4404)
                return

        self.strategy = StrategyCls(self.asset, self.scope.get('query_string', b''))
        self.interval_seconds = self.strategy.interval_seconds
        self.last_ts = None
        self.running = True
        # Per-widget filter state (independent per widget).
        self._ranges = {w.name: w.default_range for w in self.strategy.windowed_widgets()}
        # Optional per-WindowedKpi bucket pick (e.g. Loss Inspector's hour).
        # Strategies that care read `dispatcher._buckets[widget.name]`; others
        # ignore it. Empty string → strategy default (latest available).
        self._buckets = {w.name: '' for w in self.strategy.windowed_widgets()}
        # Optional per-WindowedKpi custom-range start/end (used when the
        # widget's selected range is 'custom-range').
        self._windowed_custom = {w.name: {'start': None, 'end': None}
                                 for w in self.strategy.windowed_widgets()}
        self._series = {w.name: {'range': w.default_range, 'sampling': w.default_sampling,
                                 'start': None, 'end': None}
                        for w in self.strategy.bucketed_widgets()}
        await self.accept()

        if not self.strategy.is_configured():
            await self._send_json(self._envelope('snapshot', type_code, widgets={}, layout=[],
                                                 extra={'pending': True,
                                                        'note': f"'{self.PAGE_CODE}' not configured for '{type_code}'"}))
            return

        try:
            row = await self._fetch_live()
            widgets = self.strategy.render_widgets(row or {})
            for w in self.strategy.windowed_widgets():
                widgets[w.name] = await self.strategy.render_windowed(self, w, self._ranges[w.name])
            for w in self.strategy.bucketed_widgets():
                f = self._series[w.name]
                widgets[w.name] = await self.strategy.render_bucketed(
                    self, w, f['range'], f['sampling'], f['start'], f['end'])
            static = await self.strategy.render_static(self)
            if static is not None:
                widgets['config'] = static
            layout = self.strategy.widget_descriptors()
            ts = row.get('ts') if row else None
            if row:
                self.last_ts = row.get('ts')
        except Exception as exc:
            await self._send_error(str(exc))
            await self.close(code=4500)
            return

        await self._send_json(self._envelope('snapshot', type_code, widgets=widgets,
                                             layout=layout, extra={'ts': ts}))

        self._tick_task = asyncio.create_task(self._tick_loop())
        if self.strategy.windowed_widgets() or self.strategy.bucketed_widgets():
            self._slow_task = asyncio.create_task(self._slow_loop())

    async def disconnect(self, code):
        self.running = False
        for attr in ('_tick_task', '_slow_task'):
            task = getattr(self, attr, None)
            if task:
                task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        """Per-widget filter commands:
          WindowedKpi:    {"widget","range"}
          BucketedSeries: {"widget","range","sampling"[,"start","end"]}
        """
        if not text_data:
            return
        try:
            cmd = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON command')
            return
        if not isinstance(cmd, dict):
            await self._send_error('Command must be a JSON object')
            return
        widget_name = cmd.get('widget')

        win = next((w for w in self.strategy.windowed_widgets() if w.name == widget_name), None)
        if win is not None:
            await self._cmd_windowed(win, cmd)
            return
        ser = next((w for w in self.strategy.bucketed_widgets() if w.name == widget_name), None)
        if ser is not None:
            await self._cmd_bucketed(ser, cmd)
            return
        await self._send_json({'type': 'ack', 'note': 'Unsupported command',
                               'received_keys': list(cmd.keys())[:10]})

    async def _cmd_windowed(self, widget, cmd):
        new_range = cmd.get('range')
        new_bucket = cmd.get('bucket')
        new_start = cmd.get('start')
        new_end = cmd.get('end')
        if all(v is None for v in (new_range, new_bucket, new_start, new_end)):
            await self._send_error(f"'{widget.name}' needs at least one of: range, bucket, start, end")
            return
        if new_range is not None:
            if new_range not in widget.ranges:
                await self._send_error(f"Range '{new_range}' not allowed for '{widget.name}' "
                                       f"(allowed: {widget.ranges})")
                return
            self._ranges[widget.name] = new_range
        if new_bucket is not None:
            self._buckets[widget.name] = new_bucket
        if new_start is not None or new_end is not None:
            cur = self._windowed_custom[widget.name]
            if new_start is not None: cur['start'] = new_start
            if new_end   is not None: cur['end']   = new_end
        try:
            block = await self.strategy.render_windowed(self, widget, self._ranges[widget.name])
        except Exception as exc:
            await self._send_error(str(exc))
            return
        await self._send_json({'type': 'widget_update', 'widgets': {widget.name: block}})

    async def _cmd_bucketed(self, widget, cmd):
        rng = canonical_range(cmd.get('range') or widget.default_range)
        samp = canonical_sampling(cmd.get('sampling') or widget.default_sampling)
        start, end = cmd.get('start'), cmd.get('end')
        if rng is None or samp is None:
            await self._send_error(f"Bad range/sampling for '{widget.name}'")
            return
        err = validate_range_sampling(rng, samp)
        if err:
            await self._send_error(err)
            return
        if rng == 'custom-range' and not (start and end):
            await self._send_error("custom-range needs 'start' and 'end'")
            return
        self._series[widget.name] = {'range': rng, 'sampling': samp, 'start': start, 'end': end}
        try:
            block = await self.strategy.render_bucketed(self, widget, rng, samp, start, end)
        except Exception as exc:
            await self._send_error(str(exc))
            return
        await self._send_json({'type': 'widget_update', 'widgets': {widget.name: block}})

    async def _tick_loop(self):
        consec = 0
        while self.running:
            try:
                row = await self._fetch_live()
                if row and row.get('ts') != self.last_ts:
                    self.last_ts = row.get('ts')
                    await self._send_json({'type': 'tick', 'ts': row.get('ts'),
                                           'widgets': self.strategy.render_widgets(row)})
                consec = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consec += 1
                await self._send_error(str(exc))
                if consec >= self._MAX_CONSECUTIVE_ERRORS:
                    await self.close(code=4500)
                    return
            await asyncio.sleep(self.interval_seconds)

    async def _slow_loop(self):
        windowed = self.strategy.windowed_widgets()
        bucketed = self.strategy.bucketed_widgets()
        refresh = min([w.refresh_seconds for w in (windowed + bucketed)] or [30.0])
        while self.running:
            await asyncio.sleep(refresh)
            try:
                blocks = {}
                for w in windowed:
                    blocks[w.name] = await self.strategy.render_windowed(self, w, self._ranges[w.name])
                for w in bucketed:
                    f = self._series[w.name]
                    blocks[w.name] = await self.strategy.render_bucketed(
                        self, w, f['range'], f['sampling'], f['start'], f['end'])
                if blocks:
                    await self._send_json({'type': 'widget_update', 'widgets': blocks})
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._send_error(str(exc))

    # ── async DB helpers used by strategy renders ───────────────────────────

    @database_sync_to_async
    def _get_asset(self, asset_pk):
        return Asset.objects.select_related('asset_type').get(id=asset_pk)

    @database_sync_to_async
    def _fetch_live(self):
        return fetch_live(self.asset.db_link, self.asset.table_name, self.asset.asset_id,
                          columns=self.strategy.live_columns())

    @database_sync_to_async
    def latest(self, columns):
        return fetch_live(self.asset.db_link, self.asset.table_name, self.asset.asset_id,
                          columns=columns)

    @database_sync_to_async
    def period_delta(self, column, start, end):
        return fetch_period_delta(self.asset.db_link, self.asset.table_name,
                                  self.asset.asset_id, column, start, end)

    @database_sync_to_async
    def config_row(self, table):
        return fetch_config_row(self.asset.db_link, table, self.asset.asset_id)

    @database_sync_to_async
    def bucketed(self, columns, range_token, sampling, custom_start=None,
                 custom_end=None, extra_aggregates=None):
        start, end = (resolve_range(None, custom_start, custom_end)
                      if range_token == 'custom-range' else resolve_range(range_token))
        return fetch_bucketed(self.asset.db_link, self.asset.table_name, self.asset.asset_id,
                              columns, start, end, sampling, extra_aggregates)

    @database_sync_to_async
    def tod_peaks(self, columns, range_token, custom_start=None, custom_end=None):
        start, end = (resolve_range(None, custom_start, custom_end)
                      if range_token == 'custom-range' else resolve_range(range_token))
        return fetch_tod_peaks(self.asset.db_link, self.asset.table_name, self.asset.asset_id,
                               columns, start, end)

    @database_sync_to_async
    def window_stats(self, column, range_token, custom_start=None, custom_end=None):
        start, end = (resolve_range(None, custom_start, custom_end)
                      if range_token == 'custom-range' else resolve_range(range_token))
        return fetch_window_stats(self.asset.db_link, self.asset.table_name,
                                  self.asset.asset_id, column, start, end)

    @database_sync_to_async
    def bucket_last(self, column, range_token, sampling, custom_start=None, custom_end=None):
        start, end = (resolve_range(None, custom_start, custom_end)
                      if range_token == 'custom-range' else resolve_range(range_token))
        return fetch_bucket_last(self.asset.db_link, self.asset.table_name,
                                 self.asset.asset_id, column, start, end, sampling)

    # ── send helpers ────────────────────────────────────────────────────────

    def _envelope(self, frame_type, type_code, widgets, layout, extra=None):
        env = {
            'type': frame_type,
            'asset_id': self.asset.id, 'asset_name': self.asset.name,
            'asset_key': self.asset.asset_id, 'asset_type': type_code,
            'page': self.PAGE_CODE, 'layout': layout, 'widgets': widgets,
        }
        if extra:
            env.update(extra)
        return env

    async def _send_json(self, payload):
        await self.send(text_data=json.dumps(payload, default=_fallback))

    async def _send_error(self, message):
        await self._send_json({'type': 'error', 'message': message})
