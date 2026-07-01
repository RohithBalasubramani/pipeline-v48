"""Shared base for polymorphic history consumers.

Same dispatcher → strategy pattern as the live consumers (`_base.py`), but
for date-bucketed time-series with a range/sampling control:

  Strategy declares:
    columns          — base columns to aggregate (avg/min/max per bucket)
    extra_aggregates — dict of {alias: SQL fragment} for non-avg/min/max aggs
    compute_kpis     — optional callable(buckets) → dict of headline KPIs

  Dispatcher handles:
    - load MFM, lookup strategy by mfm_type.code
    - parse range/sampling/refresh from URL query string
    - send initial snapshot + start refresh loop
    - accept mid-connection client commands to switch range/sampling
"""

import asyncio
import json
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from ..models import MFM
from ..services import fetch_bucketed, resolve_range, VALID_SAMPLINGS, LOCAL_TZ, DATA_HAS_PANEL_ID
from ._dispatch import lookup_strategy
from ._serializer import fallback as _fallback


# IST hour → shift label. Shift A: 00–08, B: 08–16, C: 16–00.
_SHIFT_LABELS = {0: 'A', 8: 'B', 16: 'C'}


def _annotate_shift_label(buckets):
    """Tag each bucket with `shift` (A/B/C) based on its IST hour. Used only
    for sampling='shift' so the frontend doesn't have to redo TZ math."""
    from datetime import datetime
    for b in buckets:
        ts = b.get('bucket')
        if isinstance(ts, datetime):
            ist_hour = ts.astimezone(LOCAL_TZ).hour
            b['shift'] = _SHIFT_LABELS.get(ist_hour)
    return buckets


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Strategy
# ─────────────────────────────────────────────────────────────────────────────

class BaseHistoryStrategy:
    """Per-(type, history-page) strategy contract."""

    columns: list[str] = []
    extra_aggregates: dict[str, str] = {}

    def __init__(self, mfm):
        self.mfm = mfm

    def is_configured(self) -> bool:
        return bool(self.columns) or bool(self.extra_aggregates)

    def compute_kpis(self, buckets: list[dict]) -> dict:
        return {}

    def extra_snapshot(self, start, end) -> dict:
        """Optional hook for adding fields to the history snapshot frame
        that don't fit the bucketed-aggregate shape (e.g. discrete event
        records reconstructed from raw samples). Return {} to skip.

        Strategy has access to `self.mfm` (db_link / table / panel_id);
        the dispatcher passes the resolved window.
        """
        return {}


class StubHistoryStrategy(BaseHistoryStrategy):
    """Marker for (type, history-page) pairs the user hasn't specified yet."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class _BaseHistoryDispatcher(AsyncWebsocketConsumer):
    """Common dispatcher for all polymorphic history pages.

    Subclasses set:
      PAGE_CODE  — e.g. 'voltage-history'
      STRATEGIES — {mfm_type.code: BaseHistoryStrategy subclass}
    """

    PAGE_CODE: str = ''
    STRATEGIES: dict[str, type] = {}
    DEFAULT_SAMPLING = 'hour'
    DEFAULT_RANGE = 'today'
    DEFAULT_REFRESH_SECONDS = 30

    # Sub-filter sampling that pairs with each range preset. If the client
    # passes a `range` without `sampling`, we pick the first allowed value
    # here. Mid-connection range switches do the same. The order matters:
    # index 0 is the default for that preset.
    _SAMPLING_BY_RANGE: dict[str, tuple[str, ...]] = {
        'today':       ('hourly', 'shift'),
        'yesterday':   ('hourly', 'shift'),
        'this_week':   ('day',),
        'last_week':   ('day',),
        'last_7d':     ('day',),
        'this_month':  ('week',),
        'last_month':  ('week',),
        'last_30d':    ('week',),
    }

    # Circuit-breaker: after this many consecutive refresh failures, close
    # the WS with 4500. Same threshold as the live dispatcher.
    _MAX_CONSECUTIVE_ERRORS: int = 10

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
        self.strategy = StrategyCls(self.mfm)

        qs = parse_qs(self.scope['query_string'].decode())
        self.preset = qs.get('range', [self.DEFAULT_RANGE])[0]
        self.start_param = qs.get('start', [None])[0]
        self.end_param = qs.get('end', [None])[0]
        # Default sampling depends on the chosen range — today/yesterday
        # default to 'hourly' (3h), this_week to 'day', this_month to 'week'.
        default_sampling = self._SAMPLING_BY_RANGE.get(self.preset, (self.DEFAULT_SAMPLING,))[0]
        self.sampling = qs.get('sampling', [default_sampling])[0]
        try:
            self.refresh_seconds = float(
                qs.get('refresh', [str(self.DEFAULT_REFRESH_SECONDS)])[0]
            )
        except ValueError:
            self.refresh_seconds = self.DEFAULT_REFRESH_SECONDS

        if self.sampling not in VALID_SAMPLINGS:
            await self.accept()
            await self._send_error(f"Invalid sampling '{self.sampling}'")
            await self.close(code=4400)
            return
        allowed = self._SAMPLING_BY_RANGE.get(self.preset)
        if allowed is not None and self.sampling not in allowed:
            await self.accept()
            await self._send_error(
                f"sampling='{self.sampling}' not allowed for range='{self.preset}'. "
                f"Allowed: {', '.join(allowed)}"
            )
            await self.close(code=4400)
            return

        try:
            self.start, self.end = resolve_range(self.preset, self.start_param, self.end_param)
        except Exception as exc:
            await self.accept()
            await self._send_error(f'Bad date range: {exc}')
            await self.close(code=4400)
            return

        self.running = True
        await self.accept()

        if not self.strategy.is_configured():
            await self._send_json({
                'type': 'snapshot',
                'mfm_id': self.mfm.id, 'mfm_name': self.mfm.name,
                'panel_id': self.mfm.panel_id, 'mfm_type': type_code,
                'page': self.PAGE_CODE,
                'range': self.preset, 'sampling': self.sampling,
                'columns': [], 'count': 0, 'buckets': [], 'kpis': {},
                'pending': True,
                'note': f"Strategy '{type_code}/{self.PAGE_CODE}' not yet configured",
            })
            return

        await self._send_buckets(initial=True)
        self._task = asyncio.create_task(self._refresh_loop())

    async def disconnect(self, code):
        self.running = False
        task = getattr(self, '_task', None)
        if task:
            task.cancel()

    async def receive(self, text_data=None, bytes_data=None):
        """Mid-connection range/sampling switch.

        Wire format:
          {"range": "this_week", "sampling": "day"}
          {"start": "2026-04-01T00:00:00Z", "end": "...", "sampling": "hour"}
        """
        if not text_data:
            return
        try:
            cmd = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error('Invalid JSON command')
            return
        # If the client switches range without sending sampling, pick the
        # default sub-filter for that range (e.g. range='this_month' →
        # sampling='week'). If client passes both, validate the combo.
        new_range = cmd.get('range')
        allowed = self._SAMPLING_BY_RANGE.get(new_range) if new_range else None
        if 'sampling' in cmd:
            new_sampling = cmd['sampling']
        elif allowed:
            new_sampling = allowed[0]
        else:
            new_sampling = self.sampling
        if new_sampling not in VALID_SAMPLINGS:
            await self._send_error(f'Invalid sampling: {new_sampling}')
            return
        if allowed is not None and new_sampling not in allowed:
            await self._send_error(
                f"sampling='{new_sampling}' not allowed for range='{new_range}'. "
                f"Allowed: {', '.join(allowed)}"
            )
            return
        try:
            new_start, new_end = resolve_range(
                new_range, cmd.get('start'), cmd.get('end')
            )
        except Exception as exc:
            await self._send_error(f'Bad date range: {exc}')
            return
        self.sampling = new_sampling
        self.start, self.end = new_start, new_end
        if 'range' in cmd:
            self.preset = cmd['range']
        await self._send_buckets(initial=True)

    async def _refresh_loop(self):
        """Slow-poll refresh of bucketed data.

        Circuit-breaker: closes the WS with 4500 after
        `_MAX_CONSECUTIVE_ERRORS` consecutive failures so the frontend
        doesn't see infinite error frames on a permanently-broken backend.
        """
        consec_errors = 0
        while self.running:
            await asyncio.sleep(self.refresh_seconds)
            try:
                await self._send_buckets(initial=False)
                consec_errors = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                consec_errors += 1
                logger.warning(
                    '_refresh_loop error %d/%d for mfm=%s page=%s: %s',
                    consec_errors, self._MAX_CONSECUTIVE_ERRORS,
                    getattr(self.mfm, 'id', None), self.PAGE_CODE, exc,
                )
                await self._send_error(str(exc))
                if consec_errors >= self._MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        '_refresh_loop circuit-break for mfm=%s page=%s',
                        getattr(self.mfm, 'id', None), self.PAGE_CODE,
                    )
                    await self.close(code=4500)
                    return

    async def _send_buckets(self, initial: bool):
        buckets = await self._fetch_buckets()
        if self.sampling == 'shift':
            _annotate_shift_label(buckets)
        kpis = self.strategy.compute_kpis(buckets)
        # Optional extra payload (e.g. discrete sag/swell event records).
        # Run the strategy's hook in a worker thread because it usually
        # does DB I/O via the pool.
        extra = await database_sync_to_async(
            self.strategy.extra_snapshot
        )(self.start, self.end)
        frame = {
            'type': 'snapshot' if initial else 'update',
            'mfm_id': self.mfm.id, 'mfm_name': self.mfm.name,
            'panel_id': self.mfm.panel_id,
            'mfm_type': self.mfm.mfm_type.code,
            'page': self.PAGE_CODE,
            'range': self.preset, 'start': self.start, 'end': self.end,
            'sampling': self.sampling,
            'columns': self.strategy.columns,
            'count': len(buckets),
            'buckets': buckets,
            'kpis': kpis,
        }
        if extra:
            frame.update(extra)
        await self._send_json(frame)

    async def _send_json(self, payload):
        await self.send(text_data=json.dumps(payload, default=_fallback))

    async def _send_error(self, message):
        await self._send_json({'type': 'error', 'message': message})

    @database_sync_to_async
    def _get_mfm(self, mfm_id):
        return MFM.objects.select_related('mfm_type').get(id=mfm_id)

    @database_sync_to_async
    def _fetch_buckets(self):
        return fetch_bucketed(
            self.mfm.db_link, self.mfm.table_name, self.mfm.panel_id,
            columns=self.strategy.columns,
            start=self.start, end=self.end,
            sampling=self.sampling,
            extra_aggregates=self.strategy.extra_aggregates or None,
        )


def argmax_bucket(buckets, key, prefer='max'):
    """Return (value, bucket_ts) for the row maximising/minimising `key`."""
    if not buckets:
        return None, None
    best, best_ts = None, None
    for b in buckets:
        v = b.get(key)
        if v is None:
            continue
        if best is None or (prefer == 'max' and v > best) or (prefer == 'min' and v < best):
            best, best_ts = v, b.get('bucket')
    return best, best_ts
