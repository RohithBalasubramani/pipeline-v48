"""Voltage & Current — PCC Panel strategy (aggregate / event-timeline view).

Drives the PCC Panel V&C tab — power-quality-event focused, not the live phase
voltage view used by transformer / lt_panel. Five widgets:

  event_timeline          24-hour stacked event timeline + worst V/I overlays
  other_panels_at_time    per-feeder snapshot at TIMELINE_TIME (V min/max,
                          I unbal, sag count, classified cause)
  selected_period         bucket dropdown + per-bucket KPIs
                          (affected / events / periods / clean)
  selected_period_mix     event-type breakdown for the selected bucket
  sag_events_by_panel     per-panel sag totals across the timeline window

Per-widget client commands:
  {"timeline_time": "2026-05-12T18:00:00+05:30"}        change timeline anchor
  {"selected_panel": {"mfm_id": <int>}}                 highlight a feeder
  {"selected_period": {"bucket": "18:00"}}              change which bucket
                                                         drives the right column

Cadence: 30s (event counts change slowly).
"""
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

from channels.db import database_sync_to_async

from .._base import BaseLiveStrategy
from .._timefilters import (
    SAMPLING_BY_RANGE as _SAMPLING_BY_RANGE,
    BUCKET_SECONDS_BY_SAMPLING as _BUCKET_SECONDS_BY_SAMPLING,
    canonical_range as _canonical_range,
    canonical_sampling as _canonical_sampling,
    default_sampling_for as _default_sampling_for,
    validate_range_sampling as _validate_range_sampling,
    build_bucket_edges as _build_bucket_edges,
)
from ...services import (
    fetch_live, fetch_bucketed,
    fetch_bool_event_combo_per_bucket, fetch_bool_event_combo_records,
    LOCAL_TZ,
    DATA_HAS_PANEL_ID,
)


# One sweep over the 4 event-flag boolean columns — same SQL CTE counts
# rising edges and pulls records in one round trip instead of 8.
_EVENT_COLS: list[tuple[str, str]] = [
    ('sag_event_active',                'sag'),
    ('swell_event_active',              'swell'),
    ('current_imbalance_event_active',  'current'),
    ('neutral_stress_event_active',     'neutral'),
]


# ── Tunables ───────────────────────────────────────────────────────────────
_BUCKET_HOURS = 3
_TIMELINE_HOURS = 24                # always show the trailing 24h
_NOMINAL_VOLTAGE_V = 415            # for V dip % calculation
_NOMINAL_VOLTAGE_LN_V = _NOMINAL_VOLTAGE_V / 1.7320508  # L-N nominal for sag/swell math
# Sag/swell thresholds (per-unit of L-N nominal). IEEE 1159 specifies
# 0.9 / 1.1, but the demo simulator's voltage data sits in ~234–245 V
# (~0.977–1.023 pu of 239.6 V L-N) and never crosses those bands.
# Using a tighter 0.98 / 1.02 envelope so the reconstructed event stream
# is non-empty against simulator data. Revert to 0.9 / 1.1 once real
# metering data lands. Each PCC outgoing feeder is queried independently
# using its own panel_id + table.
_SAG_THRESHOLD_V   = _NOMINAL_VOLTAGE_LN_V * 0.98
_SWELL_THRESHOLD_V = _NOMINAL_VOLTAGE_LN_V * 1.02
_MAX_EVENTS_PER_PANEL = 100         # cap per outgoing to avoid flood frames
_I_EVENT_THRESHOLD = 10.0           # current_unbalance_pct above this → 'current event'
_NEUTRAL_EVENT_THRESHOLD = 10.0     # kpi_neutral_to_phase_ratio_pct above → 'neutral stress'

# Cause classifier rule cutoffs
_V_DIP_PCT_TRIGGER = 5.0
_I_UNBAL_TRIGGER   = 6.0
_LIGHT_LOAD_I_UNBAL_LOW  = 4.0
_LIGHT_LOAD_I_UNBAL_HIGH = 7.0
_LIGHT_LOAD_V_DEV_MAX    = 3.0


def _short_label(idx, name):
    n = (name or '').lower()
    if 'ups' in n:  return f'U{idx+1}'
    if 'bpdb' in n: return f'B{idx+1}'
    if 'hhf' in n:  return f'H{idx+1}'
    if 'pdb' in n:  return f'P{idx+1}'
    if 'transformer' in n or 'incomer' in n or 'solar' in n: return f'I{idx+1}'
    return f'F{idx+1}'


def _classify_cause(v_min, v_max, i_unbal_pct, sag_count_in_bucket):
    """Rule-based cause classifier — order matters."""
    v_dip_pct = ((_NOMINAL_VOLTAGE_V - v_min) / _NOMINAL_VOLTAGE_V * 100.0) if v_min else 0.0
    i_u = i_unbal_pct or 0.0
    sag = sag_count_in_bucket or 0

    if sag > 0 or v_dip_pct > _V_DIP_PCT_TRIGGER:
        if i_u > _I_UNBAL_TRIGGER:
            return 'UPS inrush / bus dip'
        return 'voltage dip'
    if _LIGHT_LOAD_I_UNBAL_LOW <= i_u <= _LIGHT_LOAD_I_UNBAL_HIGH and v_dip_pct < _LIGHT_LOAD_V_DEV_MAX:
        return 'light-load or capacitor step'
    return 'normal'


def _highlight_for_cause(cause):
    if 'inrush' in cause or 'dip' in cause:
        return 'danger'
    if 'capacitor' in cause or 'light' in cause:
        return 'warn'
    return 'normal'


_FETCH_COLS = [
    'voltage_min', 'voltage_max', 'voltage_avg',
    'current_unbalance_pct', 'kpi_voltage_deviation_pct',
    'kpi_neutral_to_phase_ratio_pct',
    'sag_events_24h', 'swell_events_24h',
]


class PccPanelVoltageCurrent(BaseLiveStrategy):
    IS_AGGREGATE = True
    interval_seconds = 30.0

    def __init__(self, mfm, query_string: bytes = b''):
        super().__init__(mfm, query_string)
        self._timeline_time: datetime | None = None       # None → use 'now'
        self._selected_panel_id: int | None = None
        self._selected_bucket_label: str | None = None    # e.g. "18:00" or None → latest
        # ── Range × sampling (frontend vocabulary, see _SAMPLING_BY_RANGE) ──
        # We do NOT silently coerce on bad input — that hides frontend bugs.
        # Instead, ``self._init_error`` is set; ``aggregate_render`` raises
        # it as a ValueError so the dispatcher can close with 4400 + a clear
        # error frame (same contract the history sockets use).
        qs = parse_qs(query_string.decode() if query_string else '')
        raw_range    = qs.get('range',    ['today'])[0]
        raw_sampling = qs.get('sampling', [None])[0]
        # custom-range may use either `start`/`end` (ISO 8601) or
        # `start_date`/`end_date` (bare YYYY-MM-DD). Both honoured.
        self._custom_start: str | None = qs.get('start_date', qs.get('start', [None]))[0]
        self._custom_end:   str | None = qs.get('end_date',   qs.get('end',   [None]))[0]
        self._init_error: str | None = None
        self._range    = _canonical_range(raw_range) or raw_range
        self._sampling = (_canonical_sampling(raw_sampling) if raw_sampling
                          else _default_sampling_for(self._range))
        err = _validate_range_sampling(self._range, self._sampling)
        if err:
            self._init_error = err
        elif self._range == 'custom-range' and not (self._custom_start and self._custom_end):
            self._init_error = ("range='custom-range' requires start_date and end_date "
                                "(YYYY-MM-DD or ISO 8601)")
        self._cfg_cache = None          # DB-driven event thresholds (lt_config_value), lazily fetched + cached

    # ── DB helpers ────────────────────────────────────────────────────

    @database_sync_to_async
    def _fetch_cfg(self):
        """This panel's power-quality event thresholds from the DB (per-MFM lt_config_value → field default → the
        hardcoded literal). Editing a panel's PQ-event bands is now a DB row, not a code change. get_config is a
        SYNCHRONOUS ORM call — safe only inside this @database_sync_to_async helper; async renderers read the cache.
        [make config DB-driven]"""
        return {
            'event_sag_pct_of_nominal':   self.mfm.get_config('event_sag_pct_of_nominal',   92),
            'event_swell_pct_of_nominal': self.mfm.get_config('event_swell_pct_of_nominal', 108),
            'event_i_unbalance_pct':      self.mfm.get_config('event_i_unbalance_pct',      8),
            'event_neutral_pct_of_phase': self.mfm.get_config('event_neutral_pct_of_phase', 15),
        }

    async def _cfg(self):
        if self._cfg_cache is None:
            self._cfg_cache = await self._fetch_cfg()
        return self._cfg_cache

    @database_sync_to_async
    def _load_topology(self):
        return list(self.mfm.outgoing.select_related('mfm_type').all()) + \
               list(self.mfm.incoming.select_related('mfm_type').all())

    async def _fetch_panel_data(self, panel, start, end, bucket_seconds):
        """Fetch all per-bucket metrics for one panel:

          stats              MIN / MAX / AVG of V & I, rebucketed in Python
          sag, swell         rising-edge event counts per bucket (boolean source)
          current, neutral   rising-edge event counts per bucket (boolean source)
          events             discrete {ts,type} records for the timeline chart

        The 3 underlying SQL queries fan out in parallel via asyncio.gather —
        each gets its own pool connection and thread worker. For a 4-feeder
        panel that's 12 simultaneous queries instead of 12 sequential ones,
        which is the difference between ~6s and <1.5s on month-scale windows.
        """
        if DATA_HAS_PANEL_ID and not panel.panel_id:
            return {'stats': [], 'sag': {}, 'swell': {}, 'current': {}, 'neutral': {},
                    'events': []}

        # Inner sampling: match the request grain so the SQL aggregation
        # does the heavy lifting, not Python. For daily/weekly buckets we
        # pull daily rows (≤30/panel) and re-bucket cheaply. For sub-day
        # buckets (hourly/shift) we still need hourly rows because the
        # re-aggregation can't reconstruct sub-bucket min/max.
        inner_sampling = 'day' if bucket_seconds >= 86_400 else 'hour'
        stats_task   = database_sync_to_async(fetch_bucketed)(
            panel.db_link, panel.table_name, panel.panel_id,
            columns=['voltage_min', 'voltage_max', 'voltage_avg',
                     'current_avg',
                     'current_unbalance_pct', 'kpi_voltage_deviation_pct',
                     'kpi_neutral_to_phase_ratio_pct'],
            start=start, end=end, sampling=inner_sampling,
        )
        counts_task  = database_sync_to_async(fetch_bool_event_combo_per_bucket)(
            panel.db_link, panel.table_name, panel.panel_id,
            _EVENT_COLS, start, end, bucket_seconds,
        )
        # Records list (per-event dots on the timeline chart) only makes
        # visual sense for narrow windows — at 27+ daily buckets the dots
        # become unreadable, and pulling them costs another 9 M-row LAG
        # scan per panel. Skip when the window is wider than ~2 weeks;
        # the per-bucket COUNTS (used for the stacked bars) are unaffected.
        window_days = (end - start).total_seconds() / 86_400
        if window_days <= 14:
            records_task = database_sync_to_async(fetch_bool_event_combo_records)(
                panel.db_link, panel.table_name, panel.panel_id,
                _EVENT_COLS, start, end,
                max_events_per_type=_MAX_EVENTS_PER_PANEL,
            )
            stats, combo, events = await asyncio.gather(stats_task, counts_task, records_task)
        else:
            stats, combo = await asyncio.gather(stats_task, counts_task)
            events = []

        sag     = {ts: v.get('sag', 0)     for ts, v in combo.items()}
        swell   = {ts: v.get('swell', 0)   for ts, v in combo.items()}
        current = {ts: v.get('current', 0) for ts, v in combo.items()}
        neutral = {ts: v.get('neutral', 0) for ts, v in combo.items()}
        return {'stats': stats, 'sag': sag, 'swell': swell,
                'current': current, 'neutral': neutral, 'events': events}

    @database_sync_to_async
    def _fetch_panel_at_time(self, panel, t: datetime):
        """Latest row at-or-before ``t`` for one panel."""
        if DATA_HAS_PANEL_ID and not panel.panel_id:
            return None
        try:
            return fetch_live(panel.db_link, panel.table_name, panel.panel_id,
                              columns=_FETCH_COLS) or None
        except Exception:
            return None

    # ── Bucketing helper ──────────────────────────────────────────────

    def _make_bucket_edges(self) -> list[tuple[datetime, datetime, str]]:
        """Resolve (range, sampling) → chronological [(start, end, label)] via
        the shared time-filter builder (see consumers/_timefilters.py)."""
        return _build_bucket_edges(
            self._range, self._sampling,
            custom_start=self._custom_start, custom_end=self._custom_end,
            timeline_time=self._timeline_time,
        )

    @staticmethod
    def _aggregate_to_buckets(panel_data: dict,
                              bucket_edges: list[tuple[datetime, datetime, str]]) -> list[dict]:
        """Combine per-panel hourly stats with the per-3h event-count maps
        into a single 3-hour bucket list."""
        hour_rows = panel_data.get('stats', [])
        sag_map     = panel_data.get('sag', {})
        swell_map   = panel_data.get('swell', {})
        current_map = panel_data.get('current', {})
        neutral_map = panel_data.get('neutral', {})

        out = []
        for b_start, b_end, label in bucket_edges:
            # Stats: re-aggregate hourly rows that fall into this 3h bucket
            in_bucket = [r for r in hour_rows
                         if r.get('bucket') is not None and b_start <= r['bucket'] < b_end]

            worst_i = max((r.get('current_unbalance_pct_max') or 0) for r in in_bucket) if in_bucket else 0
            v_devs = [r.get('kpi_voltage_deviation_pct_max') for r in in_bucket
                      if r.get('kpi_voltage_deviation_pct_max') is not None] + \
                     [r.get('kpi_voltage_deviation_pct_min') for r in in_bucket
                      if r.get('kpi_voltage_deviation_pct_min') is not None]
            worst_v_dev = max(v_devs, key=abs, default=0)
            v_min_b = min((r.get('voltage_min_min') for r in in_bucket
                           if r.get('voltage_min_min') is not None), default=None)
            v_max_b = max((r.get('voltage_max_max') for r in in_bucket
                           if r.get('voltage_max_max') is not None), default=None)
            i_unbal_avg = None
            i_avg = None
            v_avg = None
            samples = sum((r.get('samples') or 0) for r in in_bucket)
            if samples:
                weighted = sum((r.get('current_unbalance_pct_avg') or 0) * (r.get('samples') or 0)
                               for r in in_bucket)
                i_unbal_avg = weighted / samples
                i_weighted = sum((r.get('current_avg_avg') or 0) * (r.get('samples') or 0)
                                 for r in in_bucket)
                i_avg = i_weighted / samples
                v_weighted = sum((r.get('voltage_avg_avg') or 0) * (r.get('samples') or 0)
                                 for r in in_bucket)
                v_avg = v_weighted / samples

            # Event counts: sum any SQL-bucket whose key falls inside our
            # Python bucket window. We can't rely on exact-key match because
            # the SQL grid (epoch-aligned multiples of bucket_seconds) and
            # the Python grid (IST-midnight / 1st-of-month anchored) only
            # coincide for daily/sub-day buckets — for weekly the two grids
            # are offset (UNIX-Thursdays vs. 1st-of-month) and an exact key
            # lookup misses every row.
            def _sum_in_range(m):
                return sum(v for ts, v in m.items() if b_start <= ts < b_end)
            sag_n     = _sum_in_range(sag_map)
            swell_n   = _sum_in_range(swell_map)
            current_n = _sum_in_range(current_map)
            neutral_n = _sum_in_range(neutral_map)

            out.append({
                'bucket_label': label, 'bucket_start': b_start, 'bucket_end': b_end,
                'sag':     sag_n,
                'swell':   swell_n,
                'current': current_n,
                'neutral': neutral_n,
                'worst_i_unbal_pct': round(worst_i, 1),
                'worst_v_dev_pct':   round(worst_v_dev, 2),
                'v_min': v_min_b, 'v_max': v_max_b,
                'v_avg':       round(v_avg, 1)       if v_avg       is not None else None,
                'i_unbal_avg': round(i_unbal_avg, 1) if i_unbal_avg is not None else None,
                'i_avg':       round(i_avg, 1)       if i_avg       is not None else None,
            })
        return out

    # ── Aggregate render ──────────────────────────────────────────────

    async def aggregate_render(self, dispatcher, initial: bool):
        # Surface query-string validation errors as a hard 4400 close. The
        # dispatcher (or `handle_command` path) turns ValueError into a
        # proper {type:"error"} frame for the client.
        if self._init_error:
            raise ValueError(self._init_error)
        c = await self._cfg()   # DB-driven event thresholds (informational payload)
        bucket_edges   = self._make_bucket_edges()
        window_start   = bucket_edges[0][0]
        window_end     = bucket_edges[-1][1]
        bucket_seconds = _BUCKET_SECONDS_BY_SAMPLING[self._sampling]

        panels = await self._load_topology()
        # Fetch per-panel data concurrently — each call does 6 DB queries
        # (stats + sag + swell + current + neutral + phase events)
        per_panel_data = await asyncio.gather(*[
            self._fetch_panel_data(p, window_start, window_end, bucket_seconds)
            for p in panels
        ])
        # Flatten per-panel event records into one chronological list tagged
        # with the source panel — drives per-event dots on the timeline chart.
        all_events: list = []
        for p, data in zip(panels, per_panel_data):
            label = _short_label(panels.index(p), p.name)
            for ev in data.get('events') or []:
                all_events.append({
                    'ts':     ev['ts'],
                    'type':   ev['type'],     # 'sag' | 'swell' | 'current' | 'neutral'
                    'mfm_id': p.id,
                    'panel':  label,
                })
        all_events.sort(key=lambda e: e['ts'])
        per_panel_3h = {p.id: self._aggregate_to_buckets(data, bucket_edges)
                        for p, data in zip(panels, per_panel_data)}

        # Resolve selected panel — default to the first outgoing with sag events,
        # else first outgoing
        outgoings = [p for p in panels if p in await self._outgoings_only(panels)]
        if self._selected_panel_id is None:
            best = None
            best_sag = -1
            for p in outgoings:
                total_sag = sum(b['sag'] for b in per_panel_3h.get(p.id, []))
                if total_sag > best_sag:
                    best_sag = total_sag; best = p
            if best:
                self._selected_panel_id = best.id

        # ── event_timeline (sum across OUTGOING feeders per bucket) ──
        # Must sum the SAME set as other_panels_at_time / sag_events_by_panel
        # (outgoings only) so the panel-level bucket total reconciles with
        # the per-feeder breakdown. Summing incomers here too — as it did
        # before — inflated the timeline by the incomer feeds' events
        # (Solar Incomer, TF incomer), which never appear in the feeder
        # table, breaking the invariant
        #   sum(other_panels_at_time per-feeder) == event_timeline total.
        timeline_buckets = []
        for i, (b_start, _b_end, label) in enumerate(bucket_edges):
            agg = {'bucket': label, 'sag': 0, 'swell': 0, 'current': 0, 'neutral': 0,
                   'worst_i_unbal_pct': 0.0, 'worst_v_dev_pct': 0.0}
            for p in outgoings:
                pb = per_panel_3h[p.id][i]
                agg['sag']     += pb['sag']
                agg['swell']   += pb['swell']
                agg['current'] += pb['current']
                agg['neutral'] += pb['neutral']
                if pb['worst_i_unbal_pct'] > agg['worst_i_unbal_pct']:
                    agg['worst_i_unbal_pct'] = pb['worst_i_unbal_pct']
                if abs(pb['worst_v_dev_pct']) > abs(agg['worst_v_dev_pct']):
                    agg['worst_v_dev_pct'] = pb['worst_v_dev_pct']
            timeline_buckets.append(agg)

        # affected = panels with at least 1 sag/swell across the window
        affected_panel_ids = set()
        for p in outgoings:
            if any(b['sag'] > 0 or b['swell'] > 0 for b in per_panel_3h.get(p.id, [])):
                affected_panel_ids.add(p.id)

        # ── Selected panel cause label (latest bucket with events) ───
        sel_cause = None
        sel_panel_obj = next((p for p in outgoings if p.id == self._selected_panel_id), None)
        if sel_panel_obj:
            for b in reversed(per_panel_3h.get(sel_panel_obj.id, [])):
                if b['sag'] > 0 or b['swell'] > 0 or b['current'] > 0:
                    sel_cause = _classify_cause(
                        b.get('v_min'), b.get('v_max'),
                        b.get('i_unbal_avg'), b.get('sag'),
                    )
                    break
            if sel_cause is None:
                sel_cause = 'normal'

        # ── selected_period: which bucket drives the right column ────
        bucket_options = [b['bucket'] for b in timeline_buckets]
        if self._selected_bucket_label not in bucket_options:
            self._selected_bucket_label = bucket_options[-1] if bucket_options else None
        sel_idx = bucket_options.index(self._selected_bucket_label) if self._selected_bucket_label else -1

        sel_bucket_agg = timeline_buckets[sel_idx] if sel_idx >= 0 else None

        # ── other_panels_at_time table (selected bucket) ─────────────
        rows = []
        for i, p in enumerate(outgoings):
            pb = per_panel_3h[p.id][sel_idx] if sel_idx >= 0 else {}
            cause = _classify_cause(pb.get('v_min'), pb.get('v_max'),
                                    pb.get('i_unbal_avg'), pb.get('sag'))
            rows.append({
                'mfm_id': p.id,
                'label':  _short_label(i, p.name),
                'name':   p.name,
                'v_min':  round(pb.get('v_min'), 1) if pb.get('v_min') is not None else None,
                'v_max':  round(pb.get('v_max'), 1) if pb.get('v_max') is not None else None,
                'voltage_v':   pb.get('v_avg'),               # bucket-avg L-N voltage
                'v_dev_pct':   pb.get('worst_v_dev_pct'),     # signed worst-magnitude deviation
                'current_a':   pb.get('i_avg'),
                'i_unbal_pct': pb.get('i_unbal_avg'),
                'sag':    pb.get('sag', 0),
                'swell':  pb.get('swell', 0),
                'current': pb.get('current', 0),              # I-imbalance events in this bucket
                'neutral': pb.get('neutral', 0),              # neutral-stress events in this bucket
                'cause':  cause,
                'highlight': _highlight_for_cause(cause),
                'selected': (p.id == self._selected_panel_id),
            })
        # SAG-FOCUS sort: rows with sag > 0 first (desc), then by cause severity
        rows.sort(key=lambda r: (-r['sag'], 0 if r['highlight'] == 'danger' else
                                              (1 if r['highlight'] == 'warn' else 2)))

        # ── selected_period_mix (event types in the selected bucket) ─
        mix_categories = []
        if sel_bucket_agg:
            for key, label in [('sag', 'Sag events'), ('swell', 'Swell events'),
                               ('current', 'Current events'), ('neutral', 'Neutral stress')]:
                mix_categories.append({'key': key, 'label': label,
                                       'count': sel_bucket_agg.get(key, 0)})

        # ── sag_events_by_panel (totals across timeline window) ──────
        sag_rows = []
        for i, p in enumerate(outgoings):
            bucket_at_sel = per_panel_3h[p.id][sel_idx] if sel_idx >= 0 else {}
            total_events = sum(b['sag'] + b['swell'] + b['current'] + b['neutral']
                               for b in per_panel_3h[p.id])
            sag_rows.append({
                'mfm_id': p.id, 'name': p.name,
                'bucket_count': bucket_at_sel.get('sag', 0),
                'total': total_events,
                'selected': (p.id == self._selected_panel_id),
            })
        sag_rows.sort(key=lambda r: (-r['bucket_count'], -r['total']))
        for i, r in enumerate(sag_rows):
            r['rank'] = i + 1

        sag_summary = {
            'sag': sum(b['sag'] for b in timeline_buckets),
            'panels_hit': sum(1 for r in sag_rows if r['bucket_count'] > 0),
            'worst_v_pct': min((b['worst_v_dev_pct'] for b in timeline_buckets), default=0,
                               key=lambda v: -abs(v)),
            'worst_i_pct': max((b['worst_i_unbal_pct'] for b in timeline_buckets), default=0),
        }

        # ── Selected period right card ───────────────────────────────
        affected_at_bucket = sum(1 for r in rows if r['highlight'] == 'danger')
        clean_at_bucket    = sum(1 for r in rows if r['highlight'] == 'normal' and r['sag'] == 0)
        events_at_bucket   = (sel_bucket_agg.get('sag', 0)
                              + sel_bucket_agg.get('swell', 0)
                              + sel_bucket_agg.get('current', 0)
                              + sel_bucket_agg.get('neutral', 0)) if sel_bucket_agg else 0

        # ── Headline KPI strip totals (window-wide, across all buckets) ──
        window_totals = {k: sum(b[k] for b in timeline_buckets)
                         for k in ('sag', 'swell', 'current', 'neutral')}
        total_events = sum(window_totals.values())
        # Worst voltage deviation across the window — signed, pick the
        # one with greatest magnitude. Worst I-unbalance — plain max.
        v_dev_vals = [b['worst_v_dev_pct'] for b in timeline_buckets
                      if b.get('worst_v_dev_pct') is not None]
        worst_v_dev = max(v_dev_vals, key=abs) if v_dev_vals else 0
        worst_i_unbal = max((b['worst_i_unbal_pct'] for b in timeline_buckets), default=0)

        return {
            'config': {
                'range':         self._range,
                'sampling':      self._sampling,
                'timeline_time': (self._timeline_time or window_end).isoformat(),
                'window_start':  window_start.isoformat(),
                'window_end':    window_end.isoformat(),
                'bucket_seconds': bucket_seconds,
                'selected_panel_mfm_id': self._selected_panel_id,
                'selected_bucket_label': self._selected_bucket_label,
            },
            'headline_kpis': {
                'total_events':       total_events,
                'sag_events':         window_totals['sag'],
                'swell_events':       window_totals['swell'],
                'current_events':     window_totals['current'],
                'neutral_events':     window_totals['neutral'],
                'worst_v_dev_pct':    round(worst_v_dev, 2)   if worst_v_dev   is not None else None,
                'worst_i_unbal_pct':  round(worst_i_unbal, 1) if worst_i_unbal is not None else None,
            },
            'event_timeline': {
                'title_status': f'{len(affected_panel_ids)} affected',
                'buckets': timeline_buckets,
                'events': all_events,    # per-event dots: {ts, type, mfm_id, panel}
                # Thresholds the simulator uses to flip its event-active
                # booleans. Informational only — counts/events now come
                # from the booleans directly, not from threshold detection here.
                'event_thresholds': {
                    'sag_pct_of_nominal':   c['event_sag_pct_of_nominal'],
                    'swell_pct_of_nominal': c['event_swell_pct_of_nominal'],
                    'i_unbalance_pct':      c['event_i_unbalance_pct'],
                    'neutral_pct_of_phase': c['event_neutral_pct_of_phase'],
                },
                'selected_panel': {
                    'mfm_id': self._selected_panel_id,
                    'name':   sel_panel_obj.name if sel_panel_obj else None,
                    'cause':  sel_cause,
                } if sel_panel_obj else None,
            },
            'other_panels_at_time': {
                'time_label': self._selected_bucket_label,
                'rows': rows,
            },
            'selected_period': {
                'bucket_options': bucket_options,
                'current_bucket': self._selected_bucket_label,
                'stable_panels':  clean_at_bucket,
                'affected':       affected_at_bucket,
                'events':         events_at_bucket,
                'periods':        len(timeline_buckets),
                'clean':          clean_at_bucket,
            },
            'selected_period_mix': {
                'categories': mix_categories,
            },
            'sag_events_by_panel': {
                'summary': sag_summary,
                'rows': sag_rows,
            },
        }

    @database_sync_to_async
    def _outgoings_only(self, all_panels):
        # Helper: re-fetch the outgoing FK set so we can distinguish from incomings
        return list(self.mfm.outgoing.all())

    # ── Client commands ──────────────────────────────────────────────

    async def handle_command(self, cmd):
        # Range/sampling switch — accepts the frontend's vocabulary
        # ('last-7-days', 'daily', …) verbatim, and the older internal
        # vocab as aliases. Invalid combos raise ValueError → the
        # dispatcher converts to a {type:"error"} frame.
        if 'range' in cmd or 'sampling' in cmd or 'start_date' in cmd or 'end_date' in cmd:
            raw_range    = cmd.get('range',    self._range)
            raw_sampling = cmd.get('sampling')
            new_range    = _canonical_range(raw_range) or raw_range
            new_sampling = (_canonical_sampling(raw_sampling) if raw_sampling
                            else (_default_sampling_for(new_range)
                                  if 'range' in cmd else self._sampling))
            err = _validate_range_sampling(new_range, new_sampling)
            if err:
                raise ValueError(err)
            self._range    = new_range
            self._sampling = new_sampling
            self._custom_start = cmd.get('start_date', cmd.get('start', self._custom_start))
            self._custom_end   = cmd.get('end_date',   cmd.get('end',   self._custom_end))
            if new_range == 'custom-range' and not (self._custom_start and self._custom_end):
                raise ValueError("range='custom-range' requires start_date and end_date "
                                 "(YYYY-MM-DD or ISO 8601)")
            # Reset selected bucket — labels change shape (HH:MM → D-N → A/B/C)
            # and a stale label would just confuse the aggregator.
            self._selected_bucket_label = None
            data = await self.aggregate_render(None, initial=False)
            return {'widget': '__all__', 'data': data}

        if 'timeline_time' in cmd:
            try:
                self._timeline_time = datetime.fromisoformat(cmd['timeline_time'])
                if self._timeline_time.tzinfo is None:
                    self._timeline_time = self._timeline_time.replace(tzinfo=timezone.utc)
            except ValueError as exc:
                raise ValueError(f'timeline_time must be ISO 8601: {exc}')
            data = await self.aggregate_render(None, initial=False)
            return {'widget': '__all__', 'data': data}

        if 'selected_panel' in cmd and isinstance(cmd['selected_panel'], dict):
            try:
                self._selected_panel_id = int(cmd['selected_panel'].get('mfm_id'))
            except (TypeError, ValueError):
                raise ValueError('selected_panel.mfm_id must be an int')
            data = await self.aggregate_render(None, initial=False)
            return {'widget': '__all__', 'data': data}

        if 'selected_period' in cmd and isinstance(cmd['selected_period'], dict):
            bucket = cmd['selected_period'].get('bucket')
            if not isinstance(bucket, str):
                raise ValueError('selected_period.bucket must be a string like "18:00"')
            self._selected_bucket_label = bucket
            data = await self.aggregate_render(None, initial=False)
            return {'widget': '__all__', 'data': data}

        return None
