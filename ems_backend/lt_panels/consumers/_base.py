"""Base classes for the column-row live consumer pattern.

Two pieces:

  BaseLiveStrategy   — plain Python object that declares what a single
                       (type, page) pair sends. Holds `columns`, `status_rules`,
                       `window_seconds`, `interval_seconds`, and a `compute_status`
                       hook. No I/O; the dispatcher does the DB work.

  _BaseLiveDispatcher — the actual AsyncWebsocketConsumer registered against
                        each page's URL. Loads the MFM, picks the right strategy
                        based on `mfm.mfm_type.code`, and runs the snapshot+tick
                        loop using the strategy's column list.

Subclassing pattern:

  class VoltageCurrentDispatcher(_BaseLiveDispatcher):
      PAGE_CODE = 'voltage-current'
      STRATEGIES = {
          'lt_panel':    LtPanelVoltageCurrent,
          'transformer': TransformerVoltageCurrent,   # TODO: spec
          ...
      }
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

from ..models import MFM
from ..services import fetch_live, fetch_window, DATA_HAS_PANEL_ID
from ..derivations import run as _run_derivation, RECOVERY_FN as _RECOVERY_FN
from ._dispatch import lookup_strategy
from ._serializer import fallback as _fallback


logger = logging.getLogger(__name__)


# Same allowlist as views._VALID_COLUMN_NAME_RE — duplicated here to keep
# the consumer layer independent of the REST layer. Both paths must agree.
_VALID_COLUMN_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,62}$')


# Lower bound for POSIX seconds → treat anything below as "not a real epoch
# timestamp" (year 2001, before this project existed). Below this we'd be
# guessing whether the caller meant milliseconds or epoch microseconds —
# refuse to guess; force callers to be explicit.
_MIN_EPOCH_SECONDS = 1_000_000_000


def _to_dt(value) -> datetime | None:
    """Coerce a row's `ts` field to a tz-aware datetime for window math.

    Accepted shapes:
      - tz-aware `datetime` (the normal case — TIMESTAMPTZ column)
      - ISO string with `Z` or `+HH:MM` offset (REST fallback / debugging)
      - int / float — POSIX seconds since epoch, treated as UTC

    Rejected (returns None, logs warning):
      - naïve `datetime` — schema should use TIMESTAMPTZ
      - naïve ISO string — same reason
      - int / float below year 2001 — probably milliseconds; refuse to guess
      - bool (a Python int subclass — would otherwise become 1970-01-01T00:00:01Z)
    """
    if value is None:
        return None
    # bool MUST be checked before int (it's a subclass)
    if isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value
        logger.warning(
            'naïve datetime arrived in _to_dt — schema should use '
            'TIMESTAMPTZ. Rejecting %r', value,
        )
        return None
    if isinstance(value, (int, float)):
        if value < _MIN_EPOCH_SECONDS:
            logger.warning(
                'numeric ts %r below epoch-seconds threshold — refusing to '
                'guess between seconds/ms/µs. Pass tz-aware datetime instead.',
                value,
            )
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
        logger.warning(
            'naïve ISO timestamp in _to_dt — caller should send tz-aware. '
            'Rejecting %r', value,
        )
        return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy
# ─────────────────────────────────────────────────────────────────────────────

class BaseLiveStrategy:
    """Per-(category, page) live strategy contract. Pure Python, no DB I/O.

    Two flavours:

    1) **Column-row** (default) — declarative `columns = [...]` and
       `status_rules = {...}`. Dispatcher fetches one row at the MFM's
       own table, runs the delta-queue snapshot/tick loop.

    2) **Aggregate** — strategy sets `IS_AGGREGATE = True` and overrides
       `aggregate_render(dispatcher, initial)`. Used when one WS needs
       data from MULTIPLE MFMs (PCC Panel RTM streams every connected
       feeder's queue). The strategy does its own DB fetching and queue
       bookkeeping; the dispatcher just runs the loop.
    """

    columns: list[str] = []
    status_rules: dict = {}
    # DB-keyed recovery: {real_column → derivations resolver value_key}. When the real column is missing/None on the
    # feeder's DB (e.g. compat dropped current_neutral), fill it from the resolver's best-possible formula for THAT db
    # (real recovery where the inputs survive, honest-degrade None where they don't). See derivations/registry.py.
    derived: dict = {}
    window_seconds: int = 60
    interval_seconds: float = 1.0
    IS_AGGREGATE: bool = False

    def __init__(self, mfm, query_string: bytes = b''):
        self.mfm = mfm
        # ?columns= override on the URL — defense-in-depth against
        # user-supplied identifiers reaching SQL. Drop anything that
        # isn't a SQL-safe column name; the services layer also does a
        # final introspection check but this stops bad chars earlier.
        qs = parse_qs(query_string.decode() if query_string else '')
        cols_param = qs.get('columns', [None])[0]
        if cols_param:
            requested = [c.strip() for c in cols_param.split(',') if c.strip()]
            valid    = [c for c in requested if _VALID_COLUMN_NAME_RE.match(c)]
            rejected = [c for c in requested if not _VALID_COLUMN_NAME_RE.match(c)]
            if rejected:
                logger.warning(
                    'WS ?columns= rejected non-identifier values: %s '
                    '(mfm_id=%s page=%s)',
                    rejected, getattr(mfm, 'id', None),
                    type(self).__name__,
                )
            self.columns = valid
        else:
            # Copy class attr to instance so subclass mutations don't leak across instances
            self.columns = list(self.columns)

        # DETERMINISTIC RECOVERY BASELINE — auto-derive {column → fn} from the columns THIS strategy fetches ∩ the central
        # RECOVERY_FN registry. Selection is NOT an AI guess: a column is "dropped" iff the live row returns None, and
        # fill_derived only fills None. So any recoverable column this consumer lists auto-recovers, with no per-consumer
        # declaration. (Replaces the old hardcoded `derived={}` class-attrs.)
        ai_derived = {}
        # ?derived= — the AI may EXTEND the baseline (prompt-specific recoveries). urlencoded JSON {column → fn}.
        derived_param = qs.get('derived', [None])[0]
        if derived_param:
            try:
                parsed = json.loads(derived_param)
            except (ValueError, TypeError):
                parsed = {}
            if isinstance(parsed, dict):
                ai_derived = {k: v for k, v in parsed.items() if isinstance(k, str) and isinstance(v, str)}
        auto = {c: _RECOVERY_FN[c] for c in self.columns if c in _RECOVERY_FN}
        self.derived = {**ai_derived, **auto}                  # deterministic baseline wins over the AI extension

    def is_configured(self) -> bool:
        """False = stub strategy, dispatcher should send an empty 'pending' frame."""
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

    def fill_derived(self, row):
        """In-place fill of any `derived` column the feeder's DB doesn't carry, via the generic derivations executor.
        Only fills when the real column is absent/None (a present real value always wins); leaves it None when the
        executor also can't recover it (honest-degrade, never fabricated)."""
        if not row or not self.derived:
            return row
        for col, fn in self.derived.items():
            if row.get(col) is not None:
                continue
            v = _run_derivation(fn, {"row": row})
            if v is not None:
                row[col] = v
        return row

    # ── Aggregate path hooks ──────────────────────────────────────────

    async def aggregate_render(self, dispatcher, initial: bool) -> dict:
        """Override in aggregate strategies. On `initial=True` return the
        full snapshot widget envelope; on subsequent calls return the
        delta tick (or empty dict to skip emitting a tick this round)."""
        raise NotImplementedError

    async def handle_command(self, cmd: dict) -> dict | None:
        """Aggregate strategies may handle client commands (e.g. selecting
        a feeder). Return a widget-update payload to broadcast or None."""
        return None


class StubStrategy(BaseLiveStrategy):
    """Marker class for (type, page) pairs not yet specified by the user.

    Inherits empty `columns` so `is_configured()` returns False and the
    dispatcher sends a 'pending' snapshot rather than crashing.
    """
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class _BaseLiveDispatcher(AsyncWebsocketConsumer):
    """Common dispatcher for all column-row pages.

    Subclasses set:
      PAGE_CODE  — e.g. 'voltage-current'
      STRATEGIES — {mfm_type.code: StrategyCls}
    """

    PAGE_CODE: str = ''
    STRATEGIES: dict[str, type] = {}

    # Circuit-breaker: after this many consecutive tick failures, close
    # the WS with 4500 and stop. Frontend gets an explicit "give up"
    # signal instead of an indefinite stream of error frames.
    _MAX_CONSECUTIVE_ERRORS: int = 10

    # ── lifecycle ──────────────────────────────────────────────────────────

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
                f"Page '{self.PAGE_CODE}' not configured for category '{type_code}'"
            )
            await self.close(code=4404)
            return

        self.strategy = StrategyCls(self.mfm, self.scope.get('query_string', b''))

        # ?window= and ?interval= URL overrides take precedence over strategy defaults
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

        # Stub strategies (no columns yet) → send an empty 'pending' frame and stop
        if not self.strategy.is_configured():
            await self._send_json({
                'type': 'snapshot',
                'mfm_id': self.mfm.id,
                'mfm_name': self.mfm.name,
                'panel_id': self.mfm.panel_id,
                'mfm_type': type_code,
                'page': self.PAGE_CODE,
                'window_seconds': self.window_seconds,
                'capacity': 0,
                'columns': [],
                'count': 0, 'queue': [], 'status': {},
                'pending': True,
                'note': f"Strategy '{type_code}/{self.PAGE_CODE}' not yet configured",
            })
            return

        # Aggregate strategies (PCC Panel RTM etc.) — dispatcher just runs the
        # loop; the strategy does its own multi-source fetching + queue mgmt.
        if self.strategy.IS_AGGREGATE:
            try:
                widgets = await self.strategy.aggregate_render(self, initial=True)
            except ValueError as exc:
                # Bad request (e.g. unsupported range/sampling combo on the
                # voltage-current dispatcher). Reject with 4400 — same
                # contract the history sockets use. Don't lump in with 4500
                # server-errors below.
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
                'mfm_id': self.mfm.id,
                'mfm_name': self.mfm.name,
                'panel_id': self.mfm.panel_id,
                'mfm_type': type_code,
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

        for _row in snapshot:                                  # DB-keyed recovery of any dropped columns
            self.strategy.fill_derived(_row)
        latest_status = self.strategy.compute_status(snapshot[-1]) if snapshot else {}
        if snapshot:
            self.last_ts = snapshot[-1].get('ts')

        # Server-side mirror of the client's queue (timestamps only).
        # Used to compute the dequeue count on each tick.
        self._queue_ts: deque = deque(_to_dt(r.get('ts')) for r in snapshot if r.get('ts') is not None)

        await self._send_json({
            'type': 'snapshot',
            'mfm_id': self.mfm.id,
            'mfm_name': self.mfm.name,
            'panel_id': self.mfm.panel_id,
            'mfm_type': type_code,
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
        """Forward client commands to aggregate strategies (selected feeder etc.).

        Column-row strategies don't accept commands today; they get an ack frame.
        """
        if not text_data:
            return
        try:
            cmd = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON command')
            return
        if not getattr(self, 'strategy', None) or not self.strategy.IS_AGGREGATE:
            # Don't reflect the full client payload — keep the ack minimal.
            # `received_keys` gives the client enough context to debug
            # without giving an attacker a reflected-payload amplifier.
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
        """Aggregate strategies: ask the strategy for the next delta; emit a
        tick frame if it returns anything non-empty.

        Sleeps FIRST — snapshot already covered initial state; an immediate
        tick would just race with client commands sent right after connect.

        Circuit-breaker: closes the WS with 4500 after
        `_MAX_CONSECUTIVE_ERRORS` consecutive failures so the frontend
        doesn't see infinite error frames on a permanently-broken backend.
        """
        consec_errors = 0
        while self.running:
            await asyncio.sleep(self.interval_seconds)
            try:
                widgets = await self.strategy.aggregate_render(self, initial=False)
                if widgets:
                    ts = widgets.pop('_ts', None) if isinstance(widgets, dict) else None
                    await self._send_json({
                        'type': 'tick',
                        'ts': ts,
                        'widgets': widgets,
                    })
                consec_errors = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consec_errors += 1
                logger.warning(
                    '_aggregate_loop error %d/%d for mfm=%s page=%s: %s',
                    consec_errors, self._MAX_CONSECUTIVE_ERRORS,
                    getattr(self.mfm, 'id', None), self.PAGE_CODE, exc,
                )
                await self._send_error(str(exc))
                if consec_errors >= self._MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        '_aggregate_loop circuit-break for mfm=%s page=%s',
                        getattr(self.mfm, 'id', None), self.PAGE_CODE,
                    )
                    await self.close(code=4500)
                    return

    async def _stream_loop(self):
        """Tick loop — emits delta-queue ops (enqueue/dequeue) per interval.

        On each iteration:
          1. fetch latest row; enqueue it if its ts differs from last sent
          2. drop any front-of-queue timestamps older than now - window_seconds
          3. if either enqueue or dequeue happened, send a tick frame

        Circuit-breaker: closes the WS with 4500 after
        `_MAX_CONSECUTIVE_ERRORS` consecutive failures so the frontend
        doesn't see infinite error frames on a permanently-broken backend.
        """
        consec_errors = 0
        while self.running:
            try:
                row = await self._fetch_live()
                self.strategy.fill_derived(row)   # DB-keyed recovery of dropped columns

                enqueue: list = []
                if row and row.get('ts') != self.last_ts:
                    self.last_ts = row.get('ts')
                    ts_dt = _to_dt(row.get('ts'))
                    if ts_dt is not None:
                        self._queue_ts.append(ts_dt)
                    enqueue = [row]

                # Slide the window — pop expired front entries
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
                    '_stream_loop error %d/%d for mfm=%s page=%s: %s',
                    consec_errors, self._MAX_CONSECUTIVE_ERRORS,
                    getattr(self.mfm, 'id', None), self.PAGE_CODE, exc,
                )
                await self._send_error(str(exc))
                if consec_errors >= self._MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        '_stream_loop circuit-break for mfm=%s page=%s',
                        getattr(self.mfm, 'id', None), self.PAGE_CODE,
                    )
                    await self.close(code=4500)
                    return
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
        return fetch_live(
            self.mfm.db_link, self.mfm.table_name, self.mfm.panel_id,
            columns=self.strategy.columns,
        )

    @database_sync_to_async
    def _fetch_window(self):
        return fetch_window(
            self.mfm.db_link, self.mfm.table_name, self.mfm.panel_id,
            seconds=self.window_seconds, columns=self.strategy.columns,
        )
