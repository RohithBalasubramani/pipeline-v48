"""Power Quality summary — PCC Panel strategy (aggregate / fleet PQ view).

Drives the entire 'Harmonics & PQ' tab on PCC Panel pages with 4 widgets:

  header_kpis        IEEE state + PQ exposure summary + selected feeder details
  pq_priority        Ranked outgoings by composite PQ risk score
  fleet_matrix       6-metric × N-feeder heatmap + 'current focus' selector
  pq_exposure_share  4-category breakdown (I-THD / V-THD / True PF gap / Neutral stress)

Per-widget client commands:
  {"select_feeder": <mfm_id>}                — pick a feeder; updates header.selected
                                                + pq_priority highlight + matrix column
  {"fleet_matrix": {"focus": "h5"}}          — change matrix focus metric
                                                ('i_thd' | 'v_thd' | 'h5' | 'h7'
                                                 | 'k_factor' | 'pf_gap')

Cadence: 5s (PQ values change slowly).
"""
import asyncio
import logging

from channels.db import database_sync_to_async

from .._base import BaseLiveStrategy
from .._timefilters import (
    SAMPLING_BY_RANGE, canonical_range, canonical_sampling,
    default_sampling_for, validate_range_sampling, build_bucket_edges,
)
from ...services import (
    fetch_live, fetch_bucketed,
    fetch_bool_event_combo_per_bucket, fetch_bool_event_combo_records,
    DATA_HAS_PANEL_ID,
)


# ── PQ event-flag boolean columns (simulator-maintained) → wire labels ──
# Rising-edge of each flag = one event, counted per bucket over the window —
# same model as the Voltage & Current event timeline. Column-tolerant: feeders
# whose table lacks a flag (e.g. mfm_ups_*) simply contribute 0.
_PQ_EVENT_COLS: list[tuple[str, str]] = [
    ('i_thd_event_active',     'i_thd'),
    ('v_thd_event_active',     'v_thd'),
    ('h5_event_active',        'h5'),
    ('h7_event_active',        'h7'),
    ('k_factor_event_active',  'k_factor'),
    ('pf_gap_event_active',    'pf_gap'),
]
_PQ_EVENT_TYPES = [lbl for _, lbl in _PQ_EVENT_COLS]
_MAX_PQ_EVENTS_PER_FEEDER = 100

# Neutral stress doesn't have a simulator boolean flag, so we synthesize it
# in-flight: per bucket, count feeders whose MAX kpi_neutral_to_phase_ratio_pct
# in that bucket breached _NEUTRAL_RATIO_LIMIT. Appended to inspector +
# event_timeline categories alongside the 6 boolean event types.
_NEUTRAL_KEY = 'neutral'
_NEUTRAL_RATIO_COL = 'kpi_neutral_to_phase_ratio_pct'

# Categories surfaced to the frontend (PQ inspector + event_timeline buckets).
# Boolean event types come from _PQ_EVENT_COLS; `neutral` is synthesized.
_INSPECTOR_CATEGORIES = _PQ_EVENT_TYPES + [_NEUTRAL_KEY]

# Per-event display label + the simulator's breach rule (for the inspector UI).
_PQ_EVENT_META = {
    'i_thd':    ('I-THD',    'I-THD > 8%'),
    'v_thd':    ('V-THD',    'V-THD > 5%'),
    'h5':       ('H5',       'H5 > 6%'),
    'h7':       ('H7',       'H7 > 4%'),
    'k_factor': ('K-Factor', 'K > 8'),
    'pf_gap':   ('PF gap',   'True PF < 0.9'),
    'neutral':  ('Neutral',  'Neutral/phase ratio > 10%'),
}


logger = logging.getLogger(__name__)


# ── Thresholds (PQ exposure categories) ────────────────────────────────────
_I_THD_LIMIT  = 8.0      # I-THD exposure if > this %
_V_THD_LIMIT  = 5.0      # V-THD exposure if > this %
_H5_LIMIT      = 6.0     # H5  driver if > this %  (matches _PQ_EVENT_META rule)
_H7_LIMIT      = 4.0     # H7  driver if > this %  (matches _PQ_EVENT_META rule)
_TRUE_PF_LIMIT = 0.9     # True PF gap if PF < this
_NEUTRAL_RATIO_LIMIT = 10.0   # Neutral stress if neutral/phase % > this

# IEEE 519 pass criteria (mirrors what the simulator labels)
_IEEE_PASS_LIMIT = 5.0   # combined V-THD must be ≤ 5%

# PQ Priority score weights (tunable)
_SCORE_W_I_THD   = 10.0
_SCORE_W_PF_GAP  = 300.0   # × (1 − PF)
_SCORE_W_K_FACT  = 2.0


# Columns we pull per outgoing
_PQ_COLS = [
    'thd_compliance_v_avg', 'thd_compliance_i_avg',
    'thd_voltage_r_pct', 'thd_voltage_y_pct', 'thd_voltage_b_pct',
    'thd_current_r_pct', 'thd_current_y_pct', 'thd_current_b_pct',
    'harmonic_5th_pct', 'harmonic_7th_pct',
    'harmonic_3rd_pct', 'harmonic_11th_pct', 'harmonic_13th_pct',
    'k_factor', 'harmonic_loss_factor_fhl',
    'power_factor_total', 'kpi_true_pf', 'kpi_displacement_pf',
    'thd_compliance_ieee519',
    'kpi_neutral_to_phase_ratio_pct',
    'flicker_pst', 'crest_factor_voltage', 'crest_factor_current',
]


def _short_label(idx: int, name: str) -> str:
    n = (name or '').lower()
    if 'ups' in n:  return f'U{idx+1}'
    if 'bpdb' in n: return f'B{idx+1}'
    if 'hhf' in n:  return f'H{idx+1}'
    if 'pdb' in n:  return f'P{idx+1}'
    return f'F{idx+1}'


def _pq_score(i_thd, pf, k):
    """PQ Priority score — higher means worse."""
    s = 0.0
    if i_thd is not None: s += i_thd * _SCORE_W_I_THD
    if pf is not None:    s += max(0.0, 1.0 - pf) * _SCORE_W_PF_GAP
    if k is not None:     s += k * _SCORE_W_K_FACT
    return round(s, 1)


def _severity_for_score(score):
    if score >= 140: return 'high'
    if score >= 110: return 'medium'
    return 'low'


def _selected_feeder_status(i_thd, pf, k):
    """Top-of-card badge: danger / watch / good."""
    if (i_thd is not None and i_thd > 10) or (pf is not None and pf < 0.86) or (k is not None and k > 12):
        return 'danger'
    if (i_thd is not None and i_thd > 7) or (pf is not None and pf < 0.92) or (k is not None and k > 8):
        return 'watch'
    return 'good'


def _ieee_pass(v_thd_avg):
    """IEEE 519 voltage compliance — V-THD ≤ 5%."""
    return v_thd_avg is not None and v_thd_avg <= _IEEE_PASS_LIMIT


def _dominant_driver(m: dict) -> str:
    """Worst-breach label among the secondary PQ drivers — one of
    'OK' | 'H5' | 'H7' | 'V' | 'PF' | 'N'. I-THD has its own column in the
    table so it's excluded here. The "worst" is the breach furthest over its
    threshold (multiplicative)."""
    breaches: list[tuple[str, float]] = []
    if m.get('v_thd') is not None and m['v_thd'] > _V_THD_LIMIT:
        breaches.append(('V',  m['v_thd'] / _V_THD_LIMIT))
    if m.get('h5') is not None and m['h5'] > _H5_LIMIT:
        breaches.append(('H5', m['h5'] / _H5_LIMIT))
    if m.get('h7') is not None and m['h7'] > _H7_LIMIT:
        breaches.append(('H7', m['h7'] / _H7_LIMIT))
    if m.get('true_pf') is not None and m['true_pf'] < _TRUE_PF_LIMIT:
        breaches.append(('PF', (_TRUE_PF_LIMIT - m['true_pf']) / _TRUE_PF_LIMIT))
    if m.get('neutral_ratio') is not None and m['neutral_ratio'] > _NEUTRAL_RATIO_LIMIT:
        breaches.append(('N',  m['neutral_ratio'] / _NEUTRAL_RATIO_LIMIT))
    if not breaches:
        return 'OK'
    return max(breaches, key=lambda x: x[1])[0]


_MATRIX_FOCUSES = ['i_thd', 'v_thd', 'h5', 'h7', 'k_factor', 'pf_gap']
_DEFAULT_FOCUS = 'i_thd'


class PccPanelPowerQualitySummary(BaseLiveStrategy):
    IS_AGGREGATE = True
    interval_seconds = 5.0

    def __init__(self, mfm, query_string: bytes = b''):
        super().__init__(mfm, query_string)
        self._selected_feeder_id: int | None = None
        self._matrix_focus = _DEFAULT_FOCUS
        # event_timeline range × sampling (frontend vocab, shared _timefilters)
        self._range = 'today'
        self._sampling = default_sampling_for('today')
        self._cstart = None
        self._cend = None
        self._selected_bucket: str | None = None   # "at HH:MM" bucket for the inspector
        self._cfg_cache = None                      # DB-driven PQ thresholds (lt_config_value), lazily fetched + cached

    # ── DB helpers ───────────────────────────────────────────────────

    @database_sync_to_async
    def _fetch_cfg(self):
        """This panel's PQ thresholds/bands from the DB (per-MFM lt_config_value → field default → the hardcoded
        module constant). Editing a panel's PQ limits is now a DB row, not a code change. Only keys read inside ASYNC
        render methods live here — module-level helpers (_dominant_driver, _pq_score, _ieee_pass) and the sync
        _render_* methods still read the module constants directly (they cannot reach self.mfm). [make config DB-driven]"""
        return {
            'neutral_ratio_limit': self.mfm.get_config('neutral_ratio_limit', _NEUTRAL_RATIO_LIMIT),
        }

    async def _cfg(self):
        if self._cfg_cache is None:
            self._cfg_cache = await self._fetch_cfg()
        return self._cfg_cache

    @database_sync_to_async
    def _load_outgoings(self):
        return list(self.mfm.outgoing.select_related('mfm_type').all())

    @database_sync_to_async
    def _fetch_outgoing_rows(self, outgoings):
        """One DB roundtrip per outgoing. Returns list[(mfm, row)].

        Individual feeder failures are isolated: a broken `db_link` or a
        missing per-MFM table degrades that one feeder to an empty row,
        not the whole tab. Failures are logged with mfm_id / table /
        panel_id / error so ops can identify the bad feeder from the
        journal instead of guessing from a blank cell in the UI.
        """
        out = []
        for og in outgoings:
            row = {}
            if og.panel_id:
                try:
                    row = fetch_live(og.db_link, og.table_name, og.panel_id,
                                     columns=_PQ_COLS) or {}
                except Exception as exc:
                    logger.warning(
                        'PCC PQ feeder fetch failed — mfm_id=%s name=%r '
                        'table=%s panel_id=%s: %s',
                        og.id, og.name, og.table_name, og.panel_id, exc,
                    )
                    row = {}
            out.append((og, row))
        return out

    # ── Per-feeder shape ─────────────────────────────────────────────

    @staticmethod
    def _row_metrics(row: dict) -> dict:
        """Project an outgoing's row into the 6 matrix metrics + score inputs."""
        i_thd = row.get('thd_compliance_i_avg')
        v_thd = row.get('thd_compliance_v_avg')
        pf    = row.get('kpi_true_pf') or row.get('power_factor_total')
        k     = row.get('k_factor')
        h5    = row.get('harmonic_5th_pct')
        h7    = row.get('harmonic_7th_pct')
        pf_gap = ((1.0 - pf) * 100.0) if pf is not None else None
        return {
            'i_thd': round(i_thd, 1) if i_thd is not None else None,
            'v_thd': round(v_thd, 1) if v_thd is not None else None,
            'h5':    round(h5, 1)    if h5 is not None else None,
            'h7':    round(h7, 1)    if h7 is not None else None,
            'k_factor': round(k, 1)  if k is not None else None,
            'pf_gap': round(pf_gap, 1) if pf_gap is not None else None,
            'true_pf': round(pf, 3) if pf is not None else None,
            'neutral_ratio': row.get('kpi_neutral_to_phase_ratio_pct'),
        }

    # ── Per-widget renderers ─────────────────────────────────────────

    def _render_header_kpis(self, fleet, selected_idx):
        # IEEE state: passing / failing / watch
        passing, fail, watch = 0, 0, 0
        for og, m in fleet:
            if _ieee_pass(m['v_thd']):
                passing += 1
            elif m['v_thd'] is not None and m['v_thd'] > _IEEE_PASS_LIMIT * 1.2:
                fail += 1
            else:
                watch += 1
        total = len(fleet)

        # PQ exposure summary (averages)
        i_thds = [m['i_thd'] for og, m in fleet if m['i_thd'] is not None]
        v_thds = [m['v_thd'] for og, m in fleet if m['v_thd'] is not None]
        avg_i = round(sum(i_thds) / len(i_thds), 1) if i_thds else None
        avg_v = round(sum(v_thds) / len(v_thds), 1) if v_thds else None

        # Selected feeder block
        sel_block = None
        if 0 <= selected_idx < len(fleet):
            og, m = fleet[selected_idx]
            status = _selected_feeder_status(m['i_thd'], m['true_pf'], m['k_factor'])
            sel_block = {
                'mfm_id': og.id,
                'name': og.name,
                'subtitle': (
                    f"{og.panel_id} - "
                    f"H5 {m['h5'] if m['h5'] is not None else '—'}% - "
                    f"H7 {m['h7'] if m['h7'] is not None else '—'}%"
                ),
                'status': status,
                'i_thd_pct': m['i_thd'],
                'v_thd_pct': m['v_thd'],
                'true_pf':   m['true_pf'],
                'k_factor':  m['k_factor'],
            }

        # PQ exposure card uses the selected feeder's status as the overall badge
        exposure_status = sel_block['status'] if sel_block else (
            'danger' if fail else ('watch' if watch else 'good')
        )

        return {
            'ieee_state': {
                'passing': passing, 'total': total,
                'fail': fail, 'watch': watch,
                'label': 'IEEE 519',
            },
            'pq_exposure': {
                'status': exposure_status,
                'selected_feeder': sel_block['name'] if sel_block else None,
                'avg_i_thd_pct': avg_i,
                'avg_v_thd_pct': avg_v,
            },
            'selected_feeder': sel_block,
        }

    def _render_pq_priority(self, fleet, selected_idx, i_thd_peaks: dict | None = None):
        i_thd_peaks = i_thd_peaks or {}
        rows = []
        for og, m in fleet:
            score = _pq_score(m['i_thd'], m['true_pf'], m['k_factor'])
            pk = i_thd_peaks.get(og.id)
            rows.append({
                'mfm_id':    og.id,
                'name':      og.name,
                'score':     score,
                'severity':  _severity_for_score(score),
                'i_thd_pct': m['i_thd'],
                'v_thd_pct': m['v_thd'],
                'i_thd_pk_pct':    round(pk, 1) if pk is not None else None,
                'dominant_driver': _dominant_driver(m),
                'pf':        m['true_pf'],
            })
        # Sort desc by score, stable so equal scores keep original order
        rows.sort(key=lambda r: -r['score'])
        # Re-rank after sort and mark selected
        sel_id = fleet[selected_idx][0].id if 0 <= selected_idx < len(fleet) else None
        for i, r in enumerate(rows):
            r['rank'] = i + 1
            r['selected'] = (r['mfm_id'] == sel_id)
        return {'rows': rows}

    def _render_fleet_matrix(self, fleet, selected_idx):
        feeders = [
            {'mfm_id': og.id, 'label': _short_label(i, og.name), 'name': og.name,
             'selected': (i == selected_idx)}
            for i, (og, _) in enumerate(fleet)
        ]
        # Per-metric value row
        values = {key: [] for key in _MATRIX_FOCUSES}
        for og, m in fleet:
            for key in _MATRIX_FOCUSES:
                values[key].append(m[key])
        return {
            'config': {
                'focus_options': _MATRIX_FOCUSES,
                'current_focus': self._matrix_focus,
            },
            'metric_labels': {
                'i_thd': 'I-THD (%)', 'v_thd': 'V-THD (%)',
                'h5': 'H5 (%)', 'h7': 'H7 (%)',
                'k_factor': 'K-Factor', 'pf_gap': 'PF gap (%)',
            },
            'metrics':  ['i_thd', 'v_thd', 'h5', 'h7', 'k_factor', 'pf_gap'],
            'feeders':  feeders,
            'values':   values,
        }

    def _render_pq_exposure_share(self, selected_counts):
        """PQ Inspector issue breakdown — the 7 PQ category counts at the
        bucket selected in the shared `timeline_filter`. No own filter: it
        renders under the single page-level constraint."""
        counts = selected_counts
        total = sum(counts.values()) or 1
        return {
            'categories': [
                {'key': t, 'label': _PQ_EVENT_META[t][0], 'rule': _PQ_EVENT_META[t][1],
                 'count': counts[t], 'pct': round(counts[t] / total * 100.0, 1)}
                for t in _INSPECTOR_CATEGORIES
            ],
            'total_issues': sum(counts.values()),
            'thresholds': {
                'i_thd_pct':  _I_THD_LIMIT,
                'v_thd_pct':  _V_THD_LIMIT,
                'true_pf':    _TRUE_PF_LIMIT,
                'neutral_ratio_pct': _NEUTRAL_RATIO_LIMIT,
            },
            'footer': (
                'Harmonic review should start with I-THD and H5/H7 drivers, '
                'then verify true PF and neutral heating.'
            ),
        }

    # ── PQ event timeline (rising-edge counts over the window) ───────

    @database_sync_to_async
    def _fetch_feeder_pq_events(self, og, start, end, bucket_seconds):
        """Per-bucket PQ event counts + capped discrete records for one feeder.
        Column-tolerant — feeders whose table lacks the flags return empty."""
        if DATA_HAS_PANEL_ID and not og.panel_id:
            return {}, []
        counts = fetch_bool_event_combo_per_bucket(
            og.db_link, og.table_name, og.panel_id,
            _PQ_EVENT_COLS, start, end, bucket_seconds)
        records = fetch_bool_event_combo_records(
            og.db_link, og.table_name, og.panel_id,
            _PQ_EVENT_COLS, start, end, max_events_per_type=_MAX_PQ_EVENTS_PER_FEEDER)
        return counts, records

    @database_sync_to_async
    def _fetch_feeder_thd_buckets(self, og, start, end, sampling):
        """Bucketed V/I-THD + neutral-ratio for one feeder.
        Drives both the trend-line overlays (Worst I-THD / Worst V-THD per
        bucket), the per-bucket synthesized `neutral` event count
        (neutral-ratio MAX > _NEUTRAL_RATIO_LIMIT), and the window peak I-THD
        used by `pq_priority.i_thd_pk_pct`."""
        if DATA_HAS_PANEL_ID and not og.panel_id:
            return []
        try:
            return fetch_bucketed(
                og.db_link, og.table_name, og.panel_id,
                columns=['thd_compliance_i_avg', 'thd_compliance_v_avg', _NEUTRAL_RATIO_COL],
                start=start, end=end, sampling=sampling)
        except Exception:
            return []

    async def _render_event_timeline(self, outgoings):
        c = await self._cfg()
        neutral_ratio_limit = c['neutral_ratio_limit']
        edges = build_bucket_edges(
            self._range, self._sampling, custom_start=self._cstart, custom_end=self._cend)
        window_start, window_end = edges[0][0], edges[-1][1]
        # Fetch event counts at a FINE granularity that divides every edge and
        # aligns to IST hour/day boundaries — then range-sum into the actual
        # edges below. Using the edge size directly would mis-bucket weekly
        # (SQL floors to UNIX-Thursday weeks while edges are month-anchored),
        # so a day/hour grain keeps attribution correct for all samplings.
        edge_seconds = (edges[0][1] - edges[0][0]).total_seconds()
        fine_seconds  = 86400 if edge_seconds >= 7 * 86400 else 3600
        fine_sampling = 'day' if edge_seconds >= 7 * 86400 else 'hour'

        per_feeder, thd_per_feeder = await asyncio.gather(
            asyncio.gather(*[
                self._fetch_feeder_pq_events(og, window_start, window_end, fine_seconds)
                for og in outgoings]),
            asyncio.gather(*[
                self._fetch_feeder_thd_buckets(og, window_start, window_end, fine_sampling)
                for og in outgoings]),
        )

        # Per-bucket panel totals = sum over feeders (range-based, TZ-safe).
        # Plus worst-THD overlays = max V/I-THD across feeders in the bucket
        # and the synthesized `neutral` count = # of feeders whose MAX
        # neutral-ratio in this bucket breached neutral_ratio_limit (DB-driven).
        buckets = []
        for (s, e, lbl) in edges:
            agg = {
                'bucket':     lbl,
                'bucket_iso': s.isoformat(),
                **{t: 0 for t in _INSPECTOR_CATEGORIES},
            }
            for counts, _recs in per_feeder:
                for ts, slot in counts.items():
                    if s <= ts < e:
                        for t in _PQ_EVENT_TYPES:
                            agg[t] += slot.get(t, 0)
            worst_i = worst_v = None
            neutral_breach_feeders = 0
            for rows in thd_per_feeder:
                feeder_max_n = None
                for r in rows:
                    b = r.get('bucket')
                    if b is None or not (s <= b < e):
                        continue
                    mi = r.get('thd_compliance_i_avg_max')
                    mv = r.get('thd_compliance_v_avg_max')
                    mn = r.get(f'{_NEUTRAL_RATIO_COL}_max')
                    if mi is not None and (worst_i is None or mi > worst_i): worst_i = mi
                    if mv is not None and (worst_v is None or mv > worst_v): worst_v = mv
                    if mn is not None and (feeder_max_n is None or mn > feeder_max_n):
                        feeder_max_n = mn
                if feeder_max_n is not None and feeder_max_n > neutral_ratio_limit:
                    neutral_breach_feeders += 1
            agg['worst_i_thd_pct'] = round(worst_i, 1) if worst_i is not None else None
            agg['worst_v_thd_pct'] = round(worst_v, 1) if worst_v is not None else None
            agg[_NEUTRAL_KEY] = neutral_breach_feeders
            buckets.append(agg)

        # Per-feeder window peak I-THD — exposed via the result dict so
        # `_render_pq_priority` can ship it as `i_thd_pk_pct` without a second
        # round-trip. Max over all buckets of `thd_compliance_i_avg_max`.
        i_thd_peaks: dict[int, float | None] = {}
        for og, rows in zip(outgoings, thd_per_feeder):
            peak = None
            for r in rows:
                mi = r.get('thd_compliance_i_avg_max')
                if mi is not None and (peak is None or mi > peak):
                    peak = mi
            i_thd_peaks[og.id] = peak

        # Discrete records, tagged with the source feeder.
        events = []
        for og, (_counts, recs) in zip(outgoings, per_feeder):
            for r in recs:
                events.append({'ts': r['ts'], 'type': r['type'], 'mfm_id': og.id, 'name': og.name})
        events.sort(key=lambda x: x['ts'])

        totals = {t: sum(b[t] for b in buckets) for t in _INSPECTOR_CATEGORIES}

        # Selected bucket ("at HH:MM") drives the PQ Inspector. Default to the
        # latest bucket; reset if the current selection isn't in this window
        # (e.g. after a range switch changes the labels).
        bucket_options = [b['bucket'] for b in buckets]
        if self._selected_bucket not in bucket_options:
            self._selected_bucket = bucket_options[-1] if bucket_options else None
        sel = next((b for b in buckets if b['bucket'] == self._selected_bucket), None)
        selected_counts = {t: (sel[t] if sel else 0) for t in _INSPECTOR_CATEGORIES}

        # Anchor = the start of the most recent bucket — the "Now" tick on the
        # frontend timeline. Mirrors the FE's `event_timeline.anchor_iso`.
        anchor_iso = edges[-1][0].isoformat() if edges else window_end.isoformat()

        # ONE shared filter constraint for the whole page — emitted once as the
        # top-level `timeline_filter` widget; both the event timeline and the
        # PQ inspector render under it (neither carries its own filter).
        # `range`, `sampling`, `anchor_iso` are *also* duplicated inside the
        # `event_timeline` block (frontend convenience — they already exist as
        # the single source of truth on `timeline_filter`).
        return {
            'filter': {
                'range_options':    list(SAMPLING_BY_RANGE.keys()),
                'current_range':    self._range,
                'sampling_options': list(SAMPLING_BY_RANGE[self._range]),
                'current_sampling': self._sampling,
                'bucket_options':   bucket_options,
                'selected_bucket':  self._selected_bucket,
                'window_start':     window_start.isoformat(),
                'window_end':       window_end.isoformat(),
                'anchor_iso':       anchor_iso,
            },
            'event_timeline': {
                'range':       self._range,
                'sampling':    self._sampling,
                'anchor_iso':  anchor_iso,
                'buckets':     buckets,
                'events':      events,
                'totals':      totals,
                'total_events': sum(totals.values()),
            },
            'selected_counts': selected_counts,
            '_i_thd_peaks':    i_thd_peaks,   # internal — consumed by pq_priority
        }

    # ── Harmonic signature (selected feeder vs fleet average) ────────

    _SIGNATURE_AXES = [
        ('h3',  'harmonic_3rd_pct'),  ('h5',  'harmonic_5th_pct'),
        ('h7',  'harmonic_7th_pct'),  ('h11', 'harmonic_11th_pct'),
        ('h13', 'harmonic_13th_pct'), ('k',   'k_factor'),
    ]

    def _render_signature(self, rows, sel_idx):
        """Radar profile: selected feeder's harmonics + fleet average."""
        fleet_avg = {}
        for key, col in self._SIGNATURE_AXES:
            vals = [r.get(col) for _, r in rows if r.get(col) is not None]
            fleet_avg[key] = round(sum(vals) / len(vals), 1) if vals else None
        sel_name, sel_vals = None, {k: None for k, _ in self._SIGNATURE_AXES}
        if 0 <= sel_idx < len(rows):
            og, r = rows[sel_idx]
            sel_name = og.name
            sel_vals = {key: (round(r[col], 1) if r.get(col) is not None else None)
                        for key, col in self._SIGNATURE_AXES}
        return {
            'axes':   [k for k, _ in self._SIGNATURE_AXES],
            'labels': {'h3': 'H3', 'h5': 'H5', 'h7': 'H7',
                       'h11': 'H11', 'h13': 'H13', 'k': 'K'},
            'selected':  {'name': sel_name, 'values': sel_vals},
            'fleet_avg': fleet_avg,
        }

    # ── Aggregate render ─────────────────────────────────────────────

    async def aggregate_render(self, dispatcher, initial: bool):
        outgoings = await self._load_outgoings()
        rows = await self._fetch_outgoing_rows(outgoings)
        fleet = [(og, self._row_metrics(row)) for og, row in rows]

        # Resolve selected feeder index. Default to the worst-score feeder
        # if nothing's selected yet.
        sel_idx = -1
        if self._selected_feeder_id is not None:
            for i, (og, _) in enumerate(fleet):
                if og.id == self._selected_feeder_id:
                    sel_idx = i; break
        if sel_idx < 0 and fleet:
            scored = sorted(
                range(len(fleet)),
                key=lambda i: -_pq_score(
                    fleet[i][1]['i_thd'], fleet[i][1]['true_pf'], fleet[i][1]['k_factor']),
            )
            sel_idx = scored[0]
            self._selected_feeder_id = fleet[sel_idx][0].id

        tl = await self._render_event_timeline(outgoings)
        # Pull the internal-only peaks dict before shipping the rest as widgets.
        i_thd_peaks = tl.pop('_i_thd_peaks', {})

        return {
            'timeline_filter':   tl['filter'],          # the ONE shared constraint
            'event_timeline':    tl['event_timeline'],  # renders under timeline_filter
            'pq_exposure_share': self._render_pq_exposure_share(tl['selected_counts']),
            'header_kpis':       self._render_header_kpis(fleet, sel_idx),
            'pq_priority':       self._render_pq_priority(fleet, sel_idx, i_thd_peaks),
            'fleet_matrix':      self._render_fleet_matrix(fleet, sel_idx),
            'signature':         self._render_signature(rows, sel_idx),
        }

    # ── Client commands ──────────────────────────────────────────────

    async def handle_command(self, cmd):
        # Timeline bucket pick by ISO timestamp — frontend ergonomic alias for
        # `timeline_filter: {bucket: "HH:MM"}`. Rebuild edges under the current
        # range/sampling, find the bucket whose [start, end) contains the ts,
        # and stash its label as the selected bucket.
        if 'timeline_time' in cmd:
            from datetime import datetime
            raw = cmd['timeline_time']
            try:
                ts = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
            except (TypeError, ValueError):
                raise ValueError(f"timeline_time must be an ISO-8601 timestamp, got {raw!r}")
            edges = build_bucket_edges(
                self._range, self._sampling,
                custom_start=self._cstart, custom_end=self._cend,
            )
            picked = next((lbl for (s, e, lbl) in edges if s <= ts < e), None)
            if picked is None and edges:
                # Falls outside the window — clamp to the nearest bucket label.
                picked = edges[-1][2] if ts >= edges[-1][1] else edges[0][2]
            self._selected_bucket = picked
            data = await self.aggregate_render(None, initial=False)
            return {'widget': '__all__', 'data': data}

        # Select a feeder
        if 'select_feeder' in cmd:
            try:
                self._selected_feeder_id = int(cmd['select_feeder'])
            except (TypeError, ValueError):
                raise ValueError(f"select_feeder must be an int, got {cmd['select_feeder']!r}")
            data = await self.aggregate_render(None, initial=False)
            return {'widget': '__all__', 'data': data}

        # Change matrix focus metric
        if 'fleet_matrix' in cmd and isinstance(cmd['fleet_matrix'], dict):
            sub = cmd['fleet_matrix']
            if 'focus' in sub:
                if sub['focus'] not in _MATRIX_FOCUSES:
                    raise ValueError(
                        f"Invalid focus '{sub['focus']}'. Use one of: {_MATRIX_FOCUSES}")
                self._matrix_focus = sub['focus']
            data = await self.aggregate_render(None, initial=False)
            return {'widget': 'fleet_matrix', 'data': data['fleet_matrix']}

        # The ONE page filter — range × sampling (with subfilters) + bucket.
        # Drives the timeline AND the PQ inspector, so re-render the whole
        # frame. Accept `timeline_filter` (canonical) and `event_timeline`
        # (alias) so either key works.
        flt = cmd.get('timeline_filter') if isinstance(cmd.get('timeline_filter'), dict) \
            else (cmd.get('event_timeline') if isinstance(cmd.get('event_timeline'), dict) else None)
        if flt is not None:
            sub = flt
            if 'range' in sub or 'sampling' in sub or 'start_date' in sub or 'end_date' in sub:
                new_range = (canonical_range(sub['range']) or sub['range']) if 'range' in sub else self._range
                if 'sampling' in sub and sub['sampling']:
                    new_sampling = canonical_sampling(sub['sampling']) or sub['sampling']
                elif 'range' in sub:
                    new_sampling = default_sampling_for(new_range)
                else:
                    new_sampling = self._sampling
                err = validate_range_sampling(new_range, new_sampling)
                if err:
                    raise ValueError(err)
                self._range, self._sampling = new_range, new_sampling
                self._cstart = sub.get('start_date', sub.get('start', self._cstart))
                self._cend   = sub.get('end_date',   sub.get('end',   self._cend))
                if new_range == 'custom-range' and not (self._cstart and self._cend):
                    raise ValueError("range='custom-range' requires start_date and end_date")
                # Range/sampling change → bucket labels change; reset selection.
                self._selected_bucket = None
            if 'bucket' in sub:                       # "at HH:MM" selector
                self._selected_bucket = sub['bucket']
            data = await self.aggregate_render(None, initial=False)
            return {'widget': '__all__', 'data': data}

        return None
