"""Base classes for the column-row live consumer pattern.

Direct port of `lt_panels/consumers/_base.py` (MFM → Asset, panel_id →
asset_id). Two pieces:

  BaseLiveStrategy   — declares what a single (category, page) pair sends:
                       `columns`, `status_rules`, `window_seconds`,
                       `interval_seconds`, and a `compute_status` hook. No I/O.

  _BaseLiveDispatcher — the AsyncWebsocketConsumer registered against each
                        page's URL. Loads the Asset, picks the strategy by
                        category, runs the snapshot+tick loop.

Two subclassing patterns — assets pages come in both flavours:

  1) Single-type page (most asset pages). The page belongs to one asset type,
     so there's no per-type lookup — point it straight at its strategy:

       class ChillerEfficiencyDispatcher(_BaseLiveDispatcher):
           PAGE_CODE  = 'chiller-efficiency'
           ASSET_TYPE = 'chiller'          # optional guard (rejects wrong type)
           STRATEGY   = ChillerEfficiency  # single strategy, no map

  2) Shared page (e.g. overview, common to every type). Keep the per-type map:

       class OverviewDispatcher(_BaseLiveDispatcher):
           PAGE_CODE  = 'overview'
           STRATEGIES = {'chiller': ChillerOverview, 'ahu': AhuOverview, ...}
"""

import asyncio
import json
import logging
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from ..models import Asset
from ..services import fetch_live, fetch_window
from ._dispatch import lookup_strategy, resolve_category
from ._serializer import fallback as _fallback


logger = logging.getLogger(__name__)


# Same allowlist as views._VALID_COLUMN_NAME_RE — duplicated to keep the
# consumer layer independent of the REST layer. Both paths must agree.
_VALID_COLUMN_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,62}$')

# Below this POSIX-seconds value, treat the input as "not a real epoch"
# (year 2001) and refuse to guess seconds/ms/µs.
_MIN_EPOCH_SECONDS = 1_000_000_000


def _to_dt(value) -> datetime | None:
    """Coerce a row's `ts` field to a tz-aware datetime for window math.

    Accepts tz-aware datetime, ISO string with offset, or POSIX seconds.
    Rejects naïve datetimes/strings, sub-2001 numbers, and bool.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # bool is an int subclass — check first
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value
        logger.warning('naïve datetime in _to_dt — use TIMESTAMPTZ. Rejecting %r', value)
        return None
    if isinstance(value, (int, float)):
        if value < _MIN_EPOCH_SECONDS:
            logger.warning('numeric ts %r below epoch-seconds threshold — refusing to guess.', value)
            return None
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            logger.warning('epoch-seconds out of range: %r → %s', value, exc)
            return None
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
        if dt.tzinfo is not None:
            return dt
        logger.warning('naïve ISO timestamp in _to_dt — send tz-aware. Rejecting %r', value)
        return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy
# ─────────────────────────────────────────────────────────────────────────────

class BaseLiveStrategy:
    """Per-(category, page) live strategy contract. Pure Python, no DB I/O.

    Column-row (default): declarative `columns` + `status_rules`; the
    dispatcher fetches and runs the delta-queue loop. Aggregate: set
    `IS_AGGREGATE = True` and override `aggregate_render` to fan out across
    multiple assets.
    """

    columns: list[str] = []
    status_rules: dict = {}
    window_seconds: int = 60
    interval_seconds: float = 1.0
    IS_AGGREGATE: bool = False

    def __init__(self, asset, query_string: bytes = b''):
        self.asset = asset
        qs = parse_qs(query_string.decode() if query_string else '')
        cols_param = qs.get('columns', [None])[0]
        if cols_param:
            requested = [c.strip() for c in cols_param.split(',') if c.strip()]
            valid    = [c for c in requested if _VALID_COLUMN_NAME_RE.match(c)]
            rejected = [c for c in requested if not _VALID_COLUMN_NAME_RE.match(c)]
            if rejected:
                logger.warning(
                    'WS ?columns= rejected non-identifier values: %s (asset_id=%s page=%s)',
                    rejected, getattr(asset, 'id', None), type(self).__name__,
                )
            self.columns = valid
        else:
            self.columns = list(self.columns)

    def is_configured(self) -> bool:
        """False = stub strategy; dispatcher sends an empty 'pending' frame."""
        return bool(self.columns) or self.IS_AGGREGATE

    def compute_status(self, row: dict) -> dict[str, str]:
        """Apply self.status_rules to a single row. Override for custom logic."""
        out = {}
        for col, rule in self.status_rules.items():
            if col not in row:
                continue
            label = rule(row[col]) if callable(rule) else row.get(rule)
            if label:
                out[col] = label
        return out

    # ── Aggregate path hooks ──────────────────────────────────────────

    async def aggregate_render(self, dispatcher, initial: bool) -> dict:
        raise NotImplementedError

    async def handle_command(self, cmd: dict) -> dict | None:
        return None


class StubStrategy(BaseLiveStrategy):
    """Marker for (type, page) pairs not yet specified. Empty `columns`
    makes `is_configured()` return False so the dispatcher sends a 'pending'
    snapshot rather than crashing."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class _BaseLiveDispatcher(AsyncWebsocketConsumer):
    """Common dispatcher for all column-row pages.

    Subclasses set:
      PAGE_CODE  — e.g. 'asset-status'
      STRATEGIES — {asset_type.code: StrategyCls}
    """

    PAGE_CODE: str = ''
    # Single-type pages set STRATEGY (one strategy, no per-type lookup).
    # Shared pages (overview) set STRATEGIES = {asset_type.code: StrategyCls}.
    # Set exactly one of the two on a concrete dispatcher.
    STRATEGY: type | None = None
    STRATEGIES: dict[str, type] = {}
    # Optional guard for single-type pages: reject assets whose category
    # isn't this type with a clean 4404 instead of serving the wrong shape.
    ASSET_TYPE: str | None = None

    _MAX_CONSECUTIVE_ERRORS: int = 10

    # ── lifecycle ──────────────────────────────────────────────────────────

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
            # Single-type page — strategy is fixed; just validate the asset's type.
            type_code = resolve_category(self.asset)
            if self.ASSET_TYPE and self.ASSET_TYPE not in (type_code, self.asset.asset_type.code):
                await self.accept()
                await self._send_error(
                    f"Page '{self.PAGE_CODE}' is for '{self.ASSET_TYPE}' assets, not '{type_code}'"
                )
                await self.close(code=4404)
                return
            StrategyCls = self.STRATEGY
        else:
            # Shared page — pick the strategy for this asset's category.
            StrategyCls, type_code = lookup_strategy(self.STRATEGIES, self.asset)
            if StrategyCls is None:
                await self.accept()
                await self._send_error(
                    f"Page '{self.PAGE_CODE}' not configured for category '{type_code}'"
                )
                await self.close(code=4404)
                return

        self.strategy = StrategyCls(self.asset, self.scope.get('query_string', b''))

        qs = parse_qs(self.scope.get('query_string', b'').decode())
        try:
            self.window_seconds = int(qs.get('window', [str(self.strategy.window_seconds)])[0])
        except ValueError:
            self.window_seconds = self.strategy.window_seconds
        try:
            self.interval_seconds = float(qs.get('interval', [str(self.strategy.interval_seconds)])[0])
        except ValueError:
            self.interval_seconds = self.strategy.interval_seconds

        self.last_ts = None
        self.running = True
        await self.accept()

        # Stub strategies → empty 'pending' frame, then stop.
        if not self.strategy.is_configured():
            await self._send_json({
                'type': 'snapshot',
                'asset_id': self.asset.id,
                'asset_name': self.asset.name,
                'asset_key': self.asset.asset_id,
                'asset_type': type_code,
                'page': self.PAGE_CODE,
                'window_seconds': self.window_seconds,
                'capacity': 0,
                'columns': [],
                'count': 0, 'queue': [], 'status': {},
                'pending': True,
                'note': f"Strategy '{type_code}/{self.PAGE_CODE}' not yet configured",
            })
            return

        # Aggregate strategies — dispatcher just runs the loop.
        if self.strategy.IS_AGGREGATE:
            try:
                widgets = await self.strategy.aggregate_render(self, initial=True)
            except ValueError as exc:
                await self._send_error(str(exc))
                await self.close(code=4400)
                return
            except Exception as exc:
                await self._send_error(str(exc))
                await self.close(code=4500)
                return
            ts = widgets.pop('_ts', None) if isinstance(widgets, dict) else None
            await self._send_json({
                'type': 'snapshot',
                'asset_id': self.asset.id,
                'asset_name': self.asset.name,
                'asset_key': self.asset.asset_id,
                'asset_type': type_code,
                'page': self.PAGE_CODE,
                'window_seconds': self.window_seconds,
                'capacity': self.window_seconds,
                'ts': ts,
                'widgets': widgets,
            })
            self._task = asyncio.create_task(self._aggregate_loop())
            return

        try:
            snapshot = await self._fetch_window()
        except Exception as exc:
            await self._send_error(str(exc))
            await self.close(code=4500)
            return

        latest_status = self.strategy.compute_status(snapshot[-1]) if snapshot else {}
        if snapshot:
            self.last_ts = snapshot[-1].get('ts')

        self._queue_ts: deque = deque(_to_dt(r.get('ts')) for r in snapshot if r.get('ts') is not None)

        await self._send_json({
            'type': 'snapshot',
            'asset_id': self.asset.id,
            'asset_name': self.asset.name,
            'asset_key': self.asset.asset_id,
            'asset_type': type_code,
            'page': self.PAGE_CODE,
            'window_seconds': self.window_seconds,
            'capacity': self.window_seconds,
            'columns': self.strategy.columns,
            'count': len(snapshot),
            'queue': snapshot,
            'status': latest_status,
        })

        self._task = asyncio.create_task(self._stream_loop())

    async def disconnect(self, code):
        self.running = False
        task = getattr(self, '_task', None)
        if task:
            task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        """Forward client commands to aggregate strategies; column-row
        strategies get a minimal ack."""
        if not text_data:
            return
        try:
            cmd = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON command')
            return
        if not getattr(self, 'strategy', None) or not self.strategy.IS_AGGREGATE:
            await self._send_json({
                'type': 'ack',
                'note': 'Live client commands not implemented for column-row strategies',
                'received_keys': list(cmd.keys())[:10] if isinstance(cmd, dict) else [],
            })
            return
        try:
            update = await self.strategy.handle_command(cmd)
        except Exception as exc:
            await self._send_error(str(exc))
            return
        if update:
            await self._send_json({'type': 'widget_update', **update})

    async def _aggregate_loop(self):
        consec_errors = 0
        while self.running:
            await asyncio.sleep(self.interval_seconds)
            try:
                widgets = await self.strategy.aggregate_render(self, initial=False)
                if widgets:
                    ts = widgets.pop('_ts', None) if isinstance(widgets, dict) else None
                    await self._send_json({'type': 'tick', 'ts': ts, 'widgets': widgets})
                consec_errors = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consec_errors += 1
                logger.warning(
                    '_aggregate_loop error %d/%d for asset=%s page=%s: %s',
                    consec_errors, self._MAX_CONSECUTIVE_ERRORS,
                    getattr(self.asset, 'id', None), self.PAGE_CODE, exc,
                )
                await self._send_error(str(exc))
                if consec_errors >= self._MAX_CONSECUTIVE_ERRORS:
                    logger.error('_aggregate_loop circuit-break for asset=%s page=%s',
                                 getattr(self.asset, 'id', None), self.PAGE_CODE)
                    await self.close(code=4500)
                    return

    async def _stream_loop(self):
        """Tick loop — emits delta-queue ops (enqueue/dequeue) per interval."""
        consec_errors = 0
        while self.running:
            try:
                row = await self._fetch_live()

                enqueue: list = []
                if row and row.get('ts') != self.last_ts:
                    self.last_ts = row.get('ts')
                    ts_dt = _to_dt(row.get('ts'))
                    if ts_dt is not None:
                        self._queue_ts.append(ts_dt)
                    enqueue = [row]

                cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.window_seconds)
                dequeued = 0
                while self._queue_ts and self._queue_ts[0] < cutoff:
                    self._queue_ts.popleft()
                    dequeued += 1

                if enqueue or dequeued:
                    await self._send_json({
                        'type': 'tick',
                        'enqueue': enqueue,
                        'dequeue': dequeued,
                        'queue_size': len(self._queue_ts),
                        'status': self.strategy.compute_status(row) if row else {},
                    })
                consec_errors = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consec_errors += 1
                logger.warning(
                    '_stream_loop error %d/%d for asset=%s page=%s: %s',
                    consec_errors, self._MAX_CONSECUTIVE_ERRORS,
                    getattr(self.asset, 'id', None), self.PAGE_CODE, exc,
                )
                await self._send_error(str(exc))
                if consec_errors >= self._MAX_CONSECUTIVE_ERRORS:
                    logger.error('_stream_loop circuit-break for asset=%s page=%s',
                                 getattr(self.asset, 'id', None), self.PAGE_CODE)
                    await self.close(code=4500)
                    return
            await asyncio.sleep(self.interval_seconds)

    # ── helpers ────────────────────────────────────────────────────────────

    async def _send_json(self, payload):
        await self.send(text_data=json.dumps(payload, default=_fallback))

    async def _send_error(self, message):
        await self._send_json({'type': 'error', 'message': message})

    @database_sync_to_async
    def _get_asset(self, asset_pk):
        return Asset.objects.select_related('asset_type').get(id=asset_pk)

    @database_sync_to_async
    def _fetch_live(self):
        return fetch_live(
            self.asset.db_link, self.asset.table_name, self.asset.asset_id,
            columns=self.strategy.columns,
        )

    @database_sync_to_async
    def _fetch_window(self):
        return fetch_window(
            self.asset.db_link, self.asset.table_name, self.asset.asset_id,
            seconds=self.window_seconds, columns=self.strategy.columns,
        )
