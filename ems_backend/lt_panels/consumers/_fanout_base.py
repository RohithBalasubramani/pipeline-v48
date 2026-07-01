"""Base classes for the Energy Distribution page (fan-out per outgoing feeder).

Structurally different from the column-row consumers — this one walks the MFM's
`outgoing` M2M graph and emits one entry per outgoing equipment, each carrying
its current active-power reading. Per-type strategy is trivial: it just declares
the column name on that type that means "live active power" so the dispatcher
can read the right field from each child's table.
"""

import asyncio
import json
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from ..models import MFM
from ..services import fetch_live, DATA_HAS_PANEL_ID
from ._dispatch import lookup_strategy, resolve_category
from ._serializer import fallback as _fallback


# ─────────────────────────────────────────────────────────────────────────────
# Strategy
# ─────────────────────────────────────────────────────────────────────────────

class BaseFanOutStrategy:
    """Per-type strategy for the energy-distribution page.

    Subclasses set:
      power_column     — column on this type's table that means 'live active power kW'
      status_callable  — optional callable(value, mfm) -> label
    """

    power_column: str = ''
    interval_seconds: float = 2.0   # cheaper than 1s — fan-out is expensive

    def __init__(self, mfm):
        self.mfm = mfm

    def is_configured(self) -> bool:
        return bool(self.power_column)


class StubFanOutStrategy(BaseFanOutStrategy):
    """Marker for outgoings whose type has no fan-out strategy configured."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Parent-level aggregate strategy (richer view, e.g. PCC Panel Energy & Dist.)
# ─────────────────────────────────────────────────────────────────────────────

class BaseAggregateEDStrategy:
    """Per-(parent-category) aggregate strategy for the energy-distribution
    page when the parent should render a richer view (header KPIs +
    consumers ranking + Sankey + AI summary), not just per-outgoing live kW.

    Subclasses implement aggregate_render() and may handle range-switch
    commands via handle_command().
    """

    interval_seconds: float = 30.0    # slow — totals change slowly

    def __init__(self, mfm, query_string: bytes = b''):
        self.mfm = mfm
        self._query_string = query_string

    async def aggregate_render(self, dispatcher, initial: bool) -> dict:
        raise NotImplementedError

    async def handle_command(self, cmd: dict) -> dict | None:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class _BaseFanOutDispatcher(AsyncWebsocketConsumer):
    """Energy-Distribution dispatcher.

    Subclasses set:
      PAGE_CODE  — 'energy-distribution'
      STRATEGIES — {mfm_type.code: BaseFanOutStrategy subclass}

    The dispatcher itself drives the loop. Every interval, it walks
    `mfm.outgoing` and asks each child's strategy for its `power_column`,
    then queries that child's timeseries table for the latest value.
    """

    PAGE_CODE: str = 'energy-distribution'
    STRATEGIES: dict[str, type] = {}              # per-outgoing fan-out
    PARENT_STRATEGIES: dict[str, type] = {}       # parent-level aggregate
    DEFAULT_INTERVAL_SECONDS = 2.0

    async def connect(self):
        self.mfm_id = self.scope['url_route']['kwargs']['mfm_id']
        try:
            self.mfm = await self._get_mfm(self.mfm_id)
        except MFM.DoesNotExist:
            await self.accept()
            await self._send_error(f'MFM {self.mfm_id} not found')
            await self.close(code=4404)
            return

        # Parent-level aggregate path (e.g. PCC Panel Energy & Distribution)
        from ._dispatch import resolve_category
        parent_category = resolve_category(self.mfm)
        ParentCls = self.PARENT_STRATEGIES.get(parent_category)
        if ParentCls is not None:
            self.parent_strategy = ParentCls(
                self.mfm, self.scope.get('query_string', b'')
            )
            self.interval_seconds = float(getattr(
                self.parent_strategy, 'interval_seconds',
                self.DEFAULT_INTERVAL_SECONDS,
            ))
            self.running = True
            await self.accept()
            try:
                widgets = await self.parent_strategy.aggregate_render(self, initial=True)
            except Exception as exc:
                await self._send_error(str(exc))
                await self.close(code=4500)
                return
            ts = widgets.pop('_ts', None) if isinstance(widgets, dict) else None
            await self._send_json({
                'type': 'snapshot',
                'mfm_id': self.mfm.id, 'mfm_name': self.mfm.name,
                'panel_id': self.mfm.panel_id,
                'mfm_type': parent_category,
                'page': 'energy-distribution',
                'ts': ts,
                'widgets': widgets,
            })
            self._task = asyncio.create_task(self._aggregate_loop())
            return

        # Per-outgoing fan-out path (existing behaviour)
        outgoings = await self._load_outgoings(self.mfm)
        if not outgoings:
            await self.accept()
            await self._send_error('MFM has no outgoing feeders')
            await self.close(code=4404)
            return

        # Build per-outgoing strategy instances. If a child's category has no
        # strategy, we keep it but mark its row as 'pending' rather than
        # skipping silently. Outgoings get the same category resolution
        # (name-prefix aware) as the parent dispatcher.
        self.outgoing_specs = []
        for og in outgoings:
            StrategyCls, _ = lookup_strategy(self.STRATEGIES, og)
            strategy = StrategyCls(og) if StrategyCls else StubFanOutStrategy(og)
            self.outgoing_specs.append((og, strategy))

        qs = parse_qs(self.scope.get('query_string', b'').decode())
        try:
            self.interval_seconds = float(
                qs.get('interval', [str(self.DEFAULT_INTERVAL_SECONDS)])[0]
            )
        except ValueError:
            self.interval_seconds = self.DEFAULT_INTERVAL_SECONDS

        self.running = True
        await self.accept()
        await self._emit('snapshot')
        self._task = asyncio.create_task(self._tick_loop())

    async def disconnect(self, code):
        self.running = False
        task = getattr(self, '_task', None)
        if task:
            task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        """Forward client commands to the parent aggregate strategy
        (range switches, etc.). Per-outgoing fan-out doesn't accept commands."""
        if not text_data:
            return
        try:
            cmd = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON command')
            return
        if not getattr(self, 'parent_strategy', None):
            await self._send_json({
                'type': 'ack',
                'note': 'Per-outgoing fan-out does not accept commands',
                'received': cmd,
            })
            return
        try:
            update = await self.parent_strategy.handle_command(cmd)
        except Exception as exc:
            await self._send_error(str(exc))
            return
        if update:
            await self._send_json({'type': 'widget_update', **update})

    async def _aggregate_loop(self):
        """Parent aggregate path: ask the strategy for the next render and
        emit a tick frame. Sleeps FIRST — snapshot already covered the
        initial state; an immediate tick would just race with client
        commands sent right after connect."""
        while self.running:
            await asyncio.sleep(self.interval_seconds)
            try:
                widgets = await self.parent_strategy.aggregate_render(self, initial=False)
                if widgets:
                    ts = widgets.pop('_ts', None) if isinstance(widgets, dict) else None
                    await self._send_json({
                        'type': 'tick',
                        'ts': ts,
                        'widgets': widgets,
                    })
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._send_error(str(exc))

    async def _tick_loop(self):
        while self.running:
            try:
                await self._emit('tick')
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._send_error(str(exc))
            await asyncio.sleep(self.interval_seconds)

    async def _emit(self, frame_type: str):
        rows = await self._collect_outgoings()
        total = sum((r.get('active_power_kw') or 0.0) for r in rows)
        await self._send_json({
            'type': frame_type,
            'mfm_id': self.mfm.id,
            'mfm_name': self.mfm.name,
            'panel_id': self.mfm.panel_id,
            'mfm_type': self.mfm.mfm_type.code,
            'page': 'energy-distribution',
            'count': len(rows),
            'total_kw': total,
            'outgoings': rows,
        })

    @database_sync_to_async
    def _collect_outgoings(self):
        rows = []
        for og, strategy in self.outgoing_specs:
            entry = {
                'id': og.id,
                'name': og.name,
                'type': og.mfm_type.code,
            }
            if not strategy.is_configured() or (DATA_HAS_PANEL_ID and not og.panel_id):
                entry['active_power_kw'] = None
                entry['status'] = 'pending'
                rows.append(entry)
                continue
            try:
                row = fetch_live(
                    og.db_link, og.table_name, og.panel_id,
                    columns=[strategy.power_column],
                )
                entry['active_power_kw'] = (row or {}).get(strategy.power_column)
            except Exception as exc:
                entry['active_power_kw'] = None
                entry['error'] = str(exc)
            rows.append(entry)
        return rows

    # ── helpers ────────────────────────────────────────────────────────────

    async def _send_json(self, payload):
        await self.send(text_data=json.dumps(payload, default=_fallback))

    async def _send_error(self, message):
        await self._send_json({'type': 'error', 'message': message})

    @database_sync_to_async
    def _get_mfm(self, mfm_id):
        return MFM.objects.select_related('mfm_type').get(id=mfm_id)

    @sync_to_async
    def _load_outgoings(self, mfm):
        return list(mfm.outgoing.select_related('mfm_type').all())
