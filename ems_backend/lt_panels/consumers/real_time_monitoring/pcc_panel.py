"""Real Time Monitoring — PCC Panel strategy (aggregate / fan-out).

Streams a 30-second per-feeder time-series for every connected MFM (incoming
+ outgoing). 2-second tick rate.

Wire format:

  Snapshot (sent once on connect)
    widgets.config            {window_seconds, interval_seconds, columns, labels, section_contracts}
                              section_contracts = recovered per-section sanctioned contract (Σ members' rated_kw,
                              rated_kw = kW ÷ load%-of-rated) — real per-panel value, NOT the SECTION_CONTRACT_KW default
    widgets.feeders           [{mfm_id, name, type, role, label, queue: [rows]}]
    widgets.selected_feeder   null  (or the snapshot of the selected one if pre-set)

  Tick (every interval_seconds)
    widgets.feeders_enqueue   [{mfm_id, row}]   one new sample per feeder
    widgets.dequeue           int               # of expired front samples per feeder
    widgets.selected_feeder   {...}             refreshed if a selection is active

  Client commands (sent over the same WS)
    {"select_feeder": <mfm_id>}    pin a feeder for the detail card
    {"clear_feeder": true}         drop the selection

Each feeder row carries the 6 metrics shown in the table:
  kw / kvar / pf / volt / amp / i_unbal
"""
import asyncio
from collections import deque
from datetime import datetime, timezone, timedelta

from channels.db import database_sync_to_async

from .._base import BaseLiveStrategy, _to_dt
from ...services import fetch_live, fetch_window, _now, DATA_HAS_PANEL_ID
from ...derivations import resolve as resolve_derivation


# Logical metric → physical column on each child MFM's table.
# Column-tolerant fetch silently substitutes None when a column is missing
# (e.g. a transformer table may carry voltage_hv_avg instead of voltage_avg).
_METRIC_COLS = {
    'kw':      'active_power_total_kw',
    'kvar':    'reactive_power_total_kvar',
    'pf':      'power_factor_total',
    'volt':    'voltage_avg',
    'amp':     'current_avg',
    'i_unbal': 'current_unbalance_pct',
}
_METRIC_LABELS = {
    'kw':      'KW',
    'kvar':    'KVAR',
    'pf':      'PF',
    'volt':    'VOLT',
    'amp':     'AMP',
    'i_unbal': 'I UNBAL',
}
# Feeder load as % of its rated capacity — drives the kw/kvar/amp severity
# bands (a raw kW number has no universal threshold, but "% of rated" does).
_LOAD_PCT_COL = 'kpi_kw_load_pct_of_rated'
_FETCH_COLS = list(_METRIC_COLS.values()) + [_LOAD_PCT_COL]


def _short_label(idx: int, role: str, name: str) -> str:
    """Build a 2-3 char row label like U1, U2, B1, H1 from name + position."""
    n = (name or '').lower()
    if 'ups' in n:
        return f'U{idx+1}'
    if 'bpdb' in n:
        return f'B{idx+1}'
    if 'hhf' in n:
        return f'H{idx+1}'
    if 'pdb' in n:
        return f'P{idx+1}'
    if 'transformer' in n or 'incomer' in n or 'solar' in n:
        return f'I{idx+1}'
    return f'F{idx+1}'   # generic feeder


# ── Severity bands (HARDCODED thresholds — TODO: move to per-MFM config) ──
# Severity scale, best→worst: low < normal < moderate < critical.
# The frontend maps band → cell colour; the band per metric is computed here
# so the colouring is correct regardless of which metric the user selects
# (previously the frontend hard-coded thresholds and mis-banded everything).
_NOMINAL_LN_V = 415 / 1.7320508          # ≈ 239.6 V L-N nominal
_BAND_ORDER = {'low': 0, 'normal': 1, 'moderate': 2, 'critical': 3}


def _band_load_pct(pct) -> str:
    """Band a feeder's load (% of rated capacity) — used for kw/kvar/amp."""
    if pct is None:   return 'normal'   # table lacks the load-% column
    if pct < 60:      return 'low'
    if pct < 80:      return 'normal'
    if pct < 95:      return 'moderate'
    return 'critical'


def _band_for(metric: str, v, load_pct=None) -> str | None:
    """Classify one metric value into low/normal/moderate/critical.

    kw / kvar / amp are banded by the feeder's load % of rated capacity
    (``load_pct``) — the universal loading-severity signal — because their
    raw magnitudes have no panel-independent threshold.
    """
    if v is None:
        return None
    if metric in ('kw', 'kvar', 'amp'):  # loading metrics — band by % of rated
        return _band_load_pct(load_pct)
    if metric == 'i_unbal':              # % current unbalance — lower is better
        if v < 1:  return 'low'
        if v < 2:  return 'normal'
        if v < 6:  return 'moderate'
        return 'critical'
    if metric == 'pf':                   # power factor — higher (→1) is better
        if v >= 0.98: return 'low'
        if v >= 0.95: return 'normal'
        if v >= 0.90: return 'moderate'
        return 'critical'
    if metric == 'volt':                 # L-N volts — banded by % deviation from nominal
        dev = abs(v - _NOMINAL_LN_V) / _NOMINAL_LN_V * 100.0
        if dev < 2:  return 'low'
        if dev < 5:  return 'normal'
        if dev < 10: return 'moderate'
        return 'critical'
    return 'normal'


def _row_to_metrics(row: dict | None) -> dict:
    """Project a child's raw row into the 6 RTM metrics + ts + severity bands.

    Each row carries:
      - the 6 metric values (kw/kvar/pf/volt/amp/i_unbal)
      - ``bands``: {metric: low|normal|moderate|critical} per metric
      - ``band``: the worst band across metrics (drives the "All Metrics" view)
    """
    if not row:
        return {k: None for k in _METRIC_COLS} | {'ts': None, 'load_pct': None,
                                                   'bands': {}, 'band': None}
    out = {logical: row.get(col) for logical, col in _METRIC_COLS.items()}
    out['ts'] = row.get('ts')
    load_pct = row.get(_LOAD_PCT_COL)
    out['load_pct'] = load_pct
    bands = {m: _band_for(m, out[m], load_pct) for m in _METRIC_COLS}
    out['bands'] = bands
    present = [b for b in bands.values() if b is not None]
    out['band'] = max(present, key=lambda b: _BAND_ORDER[b]) if present else None
    return out


class PccPanelRealTimeMonitoring(BaseLiveStrategy):
    IS_AGGREGATE = True
    interval_seconds = 2.0
    window_seconds = 30

    def __init__(self, mfm, query_string: bytes = b''):
        super().__init__(mfm, query_string)
        self._initialized = False
        self._feeders: list = []                                # ordered [(mfm, role, label)]
        self._queues: dict[int, deque] = {}                     # mfm_id → deque[row]
        self._selected_feeder_id: int | None = None

    # ── DB helpers ───────────────────────────────────────────────────

    @database_sync_to_async
    def _load_topology(self):
        """One DB roundtrip — list incomings + outgoings (with type info)."""
        incoming = list(self.mfm.incoming.select_related('mfm_type').all())
        outgoing = list(self.mfm.outgoing.select_related('mfm_type').all())
        result = []
        for i, m in enumerate(incoming):
            result.append((m, 'incoming', _short_label(i, 'incoming', m.name)))
        for i, m in enumerate(outgoing):
            result.append((m, 'outgoing', _short_label(i, 'outgoing', m.name)))
        return result

    @database_sync_to_async
    def _bootstrap_queues(self):
        """Fetch initial window per feeder. One DB roundtrip per feeder."""
        for child, _role, _label in self._feeders:
            if DATA_HAS_PANEL_ID and not child.panel_id:
                self._queues[child.id] = deque()
                continue
            try:
                rows = fetch_window(
                    child.db_link, child.table_name, child.panel_id,
                    seconds=self.window_seconds, columns=_FETCH_COLS,
                )
            except Exception:
                rows = []
            self._queues[child.id] = deque(_row_to_metrics(r) for r in rows)

    @database_sync_to_async
    def _fetch_latest_per_feeder(self):
        """One DB roundtrip per feeder. Returns [{mfm_id, row}] for those
        whose latest ts is newer than the last we enqueued."""
        out = []
        for child, _role, _label in self._feeders:
            if DATA_HAS_PANEL_ID and not child.panel_id:
                continue
            try:
                row = fetch_live(child.db_link, child.table_name, child.panel_id,
                                 columns=_FETCH_COLS)
            except Exception:
                continue
            if row is None:
                continue
            metrics = _row_to_metrics(row)
            q = self._queues.get(child.id)
            last_ts = q[-1].get('ts') if q else None
            if metrics.get('ts') == last_ts:
                continue
            out.append({'mfm_id': child.id, 'row': metrics})
            q.append(metrics)
        return out

    @database_sync_to_async
    def _fetch_one_feeder(self, mfm_id):
        """For the selected-feeder detail card — fetch a richer row."""
        from ...models import MFM
        try:
            child = MFM.objects.select_related('mfm_type').get(id=mfm_id)
        except MFM.DoesNotExist:
            return None
        if DATA_HAS_PANEL_ID and not child.panel_id:
            return {'mfm_id': child.id, 'name': child.name,
                    'type': child.mfm_type.code,
                    'pending': True, 'note': 'no panel_id configured'}
        row = fetch_live(child.db_link, child.table_name, child.panel_id,
                         columns=_FETCH_COLS) or {}
        m = _row_to_metrics(row)
        # Compose a subtitle similar to the screenshot ("MFM_025 - kVAr 89 - I unbal 7%")
        bits = [child.panel_id]
        if m.get('kvar') is not None: bits.append(f"kVAr {m['kvar']:.0f}")
        if m.get('i_unbal') is not None: bits.append(f"I unbal {m['i_unbal']:.1f}%")
        return {
            'mfm_id': child.id,
            'name': child.name,
            'subtitle': ' - '.join(bits),
            'type': child.mfm_type.code,
            'now': m,
            'status': 'live',
        }

    # ── Window mgmt ──────────────────────────────────────────────────

    def _slide_window(self) -> int:
        """Drop expired front rows from every queue. Returns the count
        dropped per feeder (it's the same N for all by construction)."""
        cutoff = _now() - timedelta(seconds=self.window_seconds)
        dropped = 0
        # All feeders should have similar timestamps, so we use the first
        # feeder's queue to determine how many to pop, then pop the same
        # number from each (keeping queues aligned for the frontend).
        if not self._queues:
            return 0
        # Find the max number to pop across all feeders
        max_drop = 0
        for q in self._queues.values():
            d = 0
            while q and (_to_dt(q[0].get('ts')) or cutoff + timedelta(seconds=1)) < cutoff:
                q.popleft()
                d += 1
            max_drop = max(max_drop, d)
        return max_drop

    # ── Aggregate render ─────────────────────────────────────────────

    async def aggregate_render(self, dispatcher, initial: bool):
        if not self._initialized or initial:
            self._feeders = await self._load_topology()
            await self._bootstrap_queues()
            self._initialized = True

            feeders_payload = []
            contract_inputs = []
            for child, role, label in self._feeders:
                q = self._queues.get(child.id, deque())
                feeders_payload.append({
                    'mfm_id': child.id,
                    'name': child.name,
                    'type': child.mfm_type.code,
                    'role': role,
                    'label': label,
                    'queue': list(q),
                })
                # Each feeder's per-section sanctioned contract = Σ members' NAMEPLATE rated kW (asset_nameplate keyed by
                # the feeder's neuract table). Rated is a stable per-feeder nameplate value — no live sample needed; the
                # kw/load_pct are kept for back-compat logging only (the resolver ignores them). [RN-01/DID-03]
                latest = q[-1] if q else {}
                contract_inputs.append({
                    'name': child.name, 'role': role, 'type': child.mfm_type.code,
                    'table': child.table_name,
                    'kw': latest.get('kw'), 'load_pct': latest.get('load_pct'),
                })
            # §J frame-override: the per-section contract the heatmap/rail render. The frontend mapper reads
            # `config.section_contracts` and merges it over the CMD V2 default, so each panel shows its OWN contract.
            # DB-keyed: honest-degrade to {} on the LIVE `compat` data (no rated/load-pct is logged in neuract); would be
            # real (Σ rated) only on the DEPRECATED lt_panels simulator — no live feeder reads that anymore.
            _panel_db = self._feeders[0][0].db_link if self._feeders else None
            _sc = resolve_derivation(_panel_db, 'sectionContracts', {'feeders': contract_inputs})
            section_contracts = _sc['value'] if _sc else {}
            widgets = {
                'config': {
                    'window_seconds': self.window_seconds,
                    'interval_seconds': self.interval_seconds,
                    'columns': list(_METRIC_COLS.keys()),
                    'labels': dict(_METRIC_LABELS),
                    'section_contracts': section_contracts,
                },
                'feeders': feeders_payload,
                'selected_feeder': None,
            }
            if self._selected_feeder_id:
                widgets['selected_feeder'] = await self._fetch_one_feeder(self._selected_feeder_id)
            return widgets

        # Tick: enqueue new samples, drop expired ones
        new_samples = await self._fetch_latest_per_feeder()
        dropped = self._slide_window()
        if not new_samples and not dropped and not self._selected_feeder_id:
            return {}    # nothing changed — skip emitting a tick
        widgets = {
            'feeders_enqueue': new_samples,
            'dequeue': dropped,
        }
        if self._selected_feeder_id:
            widgets['selected_feeder'] = await self._fetch_one_feeder(self._selected_feeder_id)
        return widgets

    # ── Client commands ──────────────────────────────────────────────

    async def handle_command(self, cmd):
        if cmd.get('clear_feeder'):
            self._selected_feeder_id = None
            return {'widget': 'selected_feeder', 'data': None}
        mfm_id = cmd.get('select_feeder')
        if mfm_id is None:
            return None
        try:
            mfm_id = int(mfm_id)
        except (TypeError, ValueError):
            raise ValueError(f'select_feeder must be an int, got {mfm_id!r}')
        self._selected_feeder_id = mfm_id
        data = await self._fetch_one_feeder(mfm_id)
        return {'widget': 'selected_feeder', 'data': data}
