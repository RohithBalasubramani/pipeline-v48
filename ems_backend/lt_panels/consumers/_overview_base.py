"""Base classes for the widget-shaped Overview page.

Overview pages don't stream a flat (column, value) row. They stream a per-widget
envelope: each widget on the page is its own block in the payload, and different
widgets have different cadences (live tick vs windowed aggregate vs event lookup
vs slow-refresh narrative).

Widget shape primitives:
  LiveGauge / LiveSpark / LiveBars  — recompute on every tick from latest row
  StaticKpi                          — same row source, but cadence may be slower
  WindowedKpi                        — accepts a range filter (today/week/month);
                                       re-fetched on range change + slow poll
  Narrative                          — slow-refresh text block (e.g. AI summary)

A type's overview strategy declares `widgets = [...]` in declaration order.
The dispatcher fetches the latest row once per tick, hands it to every "live"
widget, and runs the slow-refresh widgets on their own cadences.

NOTE: this is the SKELETON. The dispatcher's slow-cadence + range-filter loops
are stubbed for now (only live-tick widgets work end-to-end). Filling in the
slow loop comes when we wire the first WindowedKpi in production.
"""

import asyncio
import json
from dataclasses import dataclass, field
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from ..models import MFM
from ..services import fetch_live, DATA_HAS_PANEL_ID
from ._dispatch import lookup_strategy
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
    """Single gauge widget. Updated on every tick from latest row."""
    status: callable = None        # callable(value) -> label string
    status_column: str = None      # which column drives the status label
    last_event_query: str = None   # optional: pulls a "last X event" lookup (TODO)


@dataclass
class LiveSpark(_WidgetBase):
    """Sparkline widget. Updated on every tick; clients may keep their own history."""
    status: callable = None
    status_column: str = None


@dataclass
class LiveBars(_WidgetBase):
    """Bar-chart widget (e.g. R/Y/B/N phases). Updated every tick."""
    status: callable = None
    status_column: str = None


@dataclass
class StaticKpi(_WidgetBase):
    """Slow-changing KPI card. Same source as live widgets but the dispatcher
    may throttle these to a slower cadence in future."""
    status: callable = None
    status_column: str = None


@dataclass
class WindowedKpi(_WidgetBase):
    """Range-filtered KPI (e.g. Energy Consumption: today/this_week/this_month).

    Re-fetched on range change (client sends {"widget": name, "range": "..."})
    and on a slow poll cadence. NOT recomputed on the live tick.
    """
    ranges: list[str] = field(default_factory=lambda: ['today', 'this_week', 'this_month'])
    default_range: str = 'today'
    refresh_seconds: float = 30.0


@dataclass
class Narrative:
    """Slow-refresh text block (e.g. AI summary). Has its own cadence."""
    name: str
    refresh_seconds: float = 10.0


# ─────────────────────────────────────────────────────────────────────────────
# Strategy
# ─────────────────────────────────────────────────────────────────────────────

class BaseOverviewStrategy:
    """Per-(category, overview) strategy contract.

    Two flavours:

    1) **Column-row widgets** — declarative `widgets = [LiveGauge(...), ...]`.
       Dispatcher fetches the MFM's own row and the strategy's `render_widgets`
       rebuilds each widget block from that row.

    2) **Aggregate** — strategy sets `IS_AGGREGATE = True` and overrides
       `aggregate_render(dispatcher)` (async). Used by PCC Panel (fan-out
       across incomings/outgoings) and any other type that needs to assemble
       widgets from multiple sources.
    """

    widgets: list = []                # ordered list of widget dataclass instances
    interval_seconds: float = 1.0     # tick cadence for live widgets
    IS_AGGREGATE: bool = False        # set True to use aggregate_render()

    def __init__(self, mfm, query_string: bytes = b''):
        self.mfm = mfm
        self._query_string = query_string

    def is_configured(self) -> bool:
        return bool(self.widgets) or self.IS_AGGREGATE

    # ── Aggregate path (PCC Panel etc.) ───────────────────────────────────

    async def aggregate_render(self, dispatcher) -> dict:
        """Override in aggregate strategies. Return a dict of widget blocks
        (same shape as `render_widgets` would produce, plus any aggregate-only
        widgets like SLD topology). Async so the strategy can do its own
        per-child DB fetches via @database_sync_to_async helpers.
        """
        raise NotImplementedError

    async def aggregate_layout(self, dispatcher) -> list[dict]:
        """Optional layout descriptor for aggregate strategies (analogous to
        widget_descriptors). Return a list of {name, kind} entries."""
        return []

    async def handle_command(self, cmd: dict) -> dict | None:
        """Aggregate strategies may handle client commands (e.g. selecting a
        feeder). Return the widget-update payload to broadcast, or None to
        stay silent. Default: silent ack."""
        return None

    # ── helpers used by the dispatcher ─────────────────────────────────────

    def live_columns(self) -> list[str]:
        """Union of columns needed by every live (per-tick) widget."""
        live_kinds = (LiveGauge, LiveSpark, LiveBars, StaticKpi)
        cols: list[str] = []
        for w in self.widgets:
            if isinstance(w, live_kinds):
                for c in w.columns:
                    if c not in cols:
                        cols.append(c)
        return cols

    def render_widgets(self, row: dict) -> dict:
        """Build the per-widget envelope from a single fresh row."""
        live_kinds = (LiveGauge, LiveSpark, LiveBars, StaticKpi)
        out = {}
        for w in self.widgets:
            if not isinstance(w, live_kinds):
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

    def widget_descriptors(self) -> list[dict]:
        """Lightweight catalogue sent in the snapshot frame so clients know
        the page layout up front."""
        out = []
        for w in self.widgets:
            kind = type(w).__name__
            entry = {'name': w.name, 'kind': kind}
            cols = getattr(w, 'columns', None)
            if cols:
                entry['columns'] = list(cols)
            if isinstance(w, WindowedKpi):
                entry['ranges'] = list(w.ranges)
                entry['default_range'] = w.default_range
            out.append(entry)
        return out


class StubOverviewStrategy(BaseOverviewStrategy):
    """Marker class for overview strategies the user hasn't specified yet."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class _BaseOverviewDispatcher(AsyncWebsocketConsumer):
    """Dispatcher for the Overview page across all equipment types."""

    PAGE_CODE: str = 'overview'
    STRATEGIES: dict[str, type] = {}

    async def connect(self):
        self.mfm_id = self.scope['url_route']['kwargs']['mfm_id']
        try:
            self.mfm = await self._get_mfm(self.mfm_id)
        except MFM.DoesNotExist:
            await self.accept()
            await self._send_error(f'MFM {self.mfm_id} not found')
            await self.close(code=4404)
            return
        if DATA_HAS_PANEL_ID and not self.mfm.panel_id:
            await self.accept()
            await self._send_error('MFM has no panel_id configured')
            await self.close(code=4400)
            return

        StrategyCls, type_code = lookup_strategy(self.STRATEGIES, self.mfm)
        if StrategyCls is None:
            await self.accept()
            await self._send_error(
                f"Page 'overview' not configured for category '{type_code}'"
            )
            await self.close(code=4404)
            return

        self.strategy = StrategyCls(self.mfm, self.scope.get('query_string', b''))

        qs = parse_qs(self.scope.get('query_string', b'').decode())
        try:
            self.interval_seconds = float(
                qs.get('interval', [str(self.strategy.interval_seconds)])[0]
            )
        except ValueError:
            self.interval_seconds = self.strategy.interval_seconds

        self.last_ts = None
        self.running = True
        await self.accept()

        if not self.strategy.is_configured():
            await self._send_json({
                'type': 'snapshot',
                'mfm_id': self.mfm.id, 'mfm_name': self.mfm.name,
                'panel_id': self.mfm.panel_id,
                'mfm_type': type_code, 'page': 'overview',
                'widgets': {}, 'layout': [],
                'pending': True,
                'note': f"Overview strategy for type '{type_code}' not yet configured",
            })
            return

        # Initial snapshot
        try:
            if self.strategy.IS_AGGREGATE:
                widgets = await self.strategy.aggregate_render(self)
                layout  = await self.strategy.aggregate_layout(self)
                ts = widgets.pop('_ts', None) if isinstance(widgets, dict) else None
            else:
                row = await self._fetch_live()
                widgets = self.strategy.render_widgets(row or {})
                layout  = self.strategy.widget_descriptors()
                ts = row.get('ts') if row else None
                if row:
                    self.last_ts = row.get('ts')
        except Exception as exc:
            await self._send_error(str(exc))
            await self.close(code=4500)
            return

        await self._send_json({
            'type': 'snapshot',
            'mfm_id': self.mfm.id, 'mfm_name': self.mfm.name,
            'panel_id': self.mfm.panel_id,
            'mfm_type': type_code, 'page': 'overview',
            'ts': ts,
            'layout': layout,
            'widgets': widgets,
        })

        self._task = asyncio.create_task(self._tick_loop())
        # TODO: spawn slow-cadence loop for WindowedKpi / Narrative widgets

    async def disconnect(self, code):
        self.running = False
        task = getattr(self, '_task', None)
        if task:
            task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        """Client commands.

        For aggregate strategies the strategy handles the command and may
        return a widget-update payload to push back. For column-row strategies
        commands are still TODO (range filters etc.).
        """
        if not text_data:
            return
        try:
            cmd = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON command')
            return

        if self.strategy.IS_AGGREGATE:
            try:
                update = await self.strategy.handle_command(cmd)
            except Exception as exc:
                await self._send_error(str(exc))
                return
            if update:
                await self._send_json({
                    'type': 'widget_update',
                    **update,
                })
            return

        await self._send_json({
            'type': 'ack',
            'note': 'Overview client commands not yet implemented for column-row strategies',
            'received': cmd,
        })

    async def _tick_loop(self):
        while self.running:
            try:
                if self.strategy.IS_AGGREGATE:
                    widgets = await self.strategy.aggregate_render(self)
                    ts = widgets.pop('_ts', None) if isinstance(widgets, dict) else None
                    await self._send_json({
                        'type': 'tick',
                        'ts': ts,
                        'widgets': widgets,
                    })
                else:
                    row = await self._fetch_live()
                    if row and row.get('ts') != self.last_ts:
                        self.last_ts = row.get('ts')
                        await self._send_json({
                            'type': 'tick',
                            'ts': row.get('ts'),
                            'widgets': self.strategy.render_widgets(row),
                        })
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._send_error(str(exc))
            await asyncio.sleep(self.interval_seconds)

    # ── helpers ────────────────────────────────────────────────────────────

    async def _send_json(self, payload):
        await self.send(text_data=json.dumps(payload, default=_fallback))

    async def _send_error(self, message):
        await self._send_json({'type': 'error', 'message': message})

    @database_sync_to_async
    def _get_mfm(self, mfm_id):
        return MFM.objects.select_related('mfm_type').get(id=mfm_id)

    @database_sync_to_async
    def _fetch_live(self):
        cols = self.strategy.live_columns()
        return fetch_live(
            self.mfm.db_link, self.mfm.table_name, self.mfm.panel_id,
            columns=cols,
        )
