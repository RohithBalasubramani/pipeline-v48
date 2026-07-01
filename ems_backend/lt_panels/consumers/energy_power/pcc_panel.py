"""Energy & Power — PCC Panel strategy (aggregate / multi-widget).

Four widgets driving the Energy & Power tab:

  period_energy        "Cumulative Energy" card — Active MWh + Reactive MVArh
                       + SEC vs (pro-rated) subsidy limit.
                       Filter: monthly | weekly | daily
  energy_trend         "Energy Consumption Trend" — bucketed energy.
                       Filter: range × sampling (frontend vocab) + mode
                               (total | by_equipment).
  live_load            "Today live power analysis" — current kVA/kW/kVAr vs
                       rated, worst peak, load factor. No filter (live tick).
  panel_power_profile  "Daily Power Demand by Feeder" — per-feeder kW demand
                       lines + worst-peak / load-factor KPIs.
                       Filter: last-30-days | last-7-days | today

Per-widget filter commands (server replies {type:'widget_update', widget, data}):
  {"cumulative_energy":   {"period": "weekly"}}
  {"energy_trend":        {"range": "last-7-days", "sampling": "daily", "mode": "by_equipment"}}
  {"power_demand":        {"preset": "last-7-days"}}

Cadence: 5 s — live_load refreshes; the rest are still fresh enough.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from channels.db import database_sync_to_async

from .._base import BaseLiveStrategy
from .._timefilters import (
    SAMPLING_BY_RANGE, canonical_range, canonical_sampling,
    default_sampling_for, validate_range_sampling, build_bucket_edges,
)
from ...services import fetch_live, fetch_bucketed, DATA_HAS_PANEL_ID


# ── Hardcoded nameplate constants (TODO: move to MFM model fields) ─────────
# Scaled to the simulator's data magnitudes (panel runs ~2800 MVAh/month,
# ~5000 kVA live) so the progress bars read sensibly. These are placeholders
# until per-MFM nameplate config lands.
NAMEPLATE = {
    'subsidy_limit_mvah_per_month': 3200.0,    # Cumulative Energy monthly limit
    'rated_kva':                    6000.0,    # Live power-analysis rated capacity
    'rated_kw':                     5500.0,    # Live Load progress-bar limit
    'contract_kwh_per_day':       120000.0,    # Energy Trend red dashed line
    'rated_kwh_per_day':          100000.0,    # Energy Trend grey dashed line
    'sec_target_kwh_per_unit':       207.0,    # Specific Energy Consumption target
    'critical_demand_kw':           1600.0,    # Power-demand chart red dashed line
}

# Pre-computed period-energy columns the simulator maintains (latest reading
# IS the period total — no MAX-MIN delta needed, so no non-monotonic artifacts).
_PERIOD_ENERGY_COLS = {
    'monthly': ('active_energy_this_month_kwh', 'apparent_energy_this_month_kvah',
                'reactive_energy_this_month_kvarh'),
    'weekly':  ('active_energy_this_week_kwh',  'apparent_energy_this_week_kvah',
                'reactive_energy_this_week_kvarh'),
    'daily':   ('active_energy_today_kwh',      'apparent_energy_today_kvah',
                'reactive_energy_today_kvarh'),
}

# Pro-rating factors for the subsidy limit at sub-monthly periods.
_DAYS_PER_MONTH = 30.44
_WEEKS_PER_MONTH = 52.0 / 12.0          # ≈ 4.333

# Cumulative-Energy period → resolve_range preset.
_PERIOD_TO_RANGE = {'monthly': 'this_month', 'weekly': 'this_week', 'daily': 'today'}
_PERIODS = ('monthly', 'weekly', 'daily')
_DEFAULT_PERIOD = 'monthly'

# Energy-Trend default range (sampling auto-defaults per range).
_DEFAULT_TREND_RANGE = 'last-7-days'

# Power-Demand presets → (range, sampling).
_DEMAND_PRESETS = {
    'last-30-days': ('last-30-days', 'daily'),
    'last-7-days':  ('last-7-days',  'daily'),
    'today':        ('today',        'hourly'),
}
_DEFAULT_DEMAND_PRESET = 'last-7-days'

_ENERGY_COL = 'active_energy_import_kwh'
_REACTIVE_ENERGY_COL = 'reactive_energy_import_kvarh'
_APPARENT_ENERGY_COL = 'apparent_energy_kvah'

# Inner SQL sampling: fetch fine enough to re-aggregate into bucket edges.
def _inner_sampling(frontend_sampling: str) -> str:
    return 'day' if frontend_sampling == 'weekly' else 'hour'


# Equipment families the frontend mapper expects as fixed columns. A panel
# may not have all three (e.g. PCC-1A has no HHF) — absent families emit 0.
_FAMILIES = ('ups', 'bpdp', 'hhf')


def _family(name: str) -> str | None:
    """Classify a feeder into a ups/bpdp/hhf family by name prefix.
    Returns None for feeders that belong to none (e.g. PDB / Spare) — those
    still count toward the panel-level active/reactive totals but don't
    appear in the per-family breakdown."""
    n = (name or '').lower()
    if 'ups' in n:                    return 'ups'
    if 'bpdb' in n or 'bpdp' in n:    return 'bpdp'
    if 'hhf' in n:                    return 'hhf'
    return None


def _on_track_status(used_pct: float | None) -> str:
    if used_pct is None:    return 'Unknown'
    if used_pct < 80:       return 'On track'
    if used_pct < 95:       return 'Watch'
    return 'Over'


def _sum_in_range(rows, ts_key, val_key, start, end):
    return sum((r.get(val_key) or 0) for r in rows
               if r.get(ts_key) is not None and start <= r[ts_key] < end)


def _energy_in_range(rows, avg_key, start, end, inner_hours):
    """Energy (kWh/kVArh/kVAh) over an edge window, computed as
    avg_power × duration summed across inner buckets.

    We deliberately do NOT use MAX(counter)-MIN(counter) energy deltas:
    the simulator's cumulative energy counters have discontinuities (data
    was regenerated mid-month, resetting the baseline), so deltas spike to
    phantom values across the boundary. Average-power × time is immune to
    counter resets and is the textbook energy integral approximation.
    """
    total = 0.0
    for r in rows:
        ts = r.get(ts_key := 'bucket')
        if ts is None or not (start <= ts < end):
            continue
        avg = r.get(avg_key)
        if avg is not None:
            total += avg * inner_hours
    return total


def _weighted_avg_in_range(rows, ts_key, avg_key, start, end):
    num = den = 0.0
    for r in rows:
        ts = r.get(ts_key)
        if ts is None or not (start <= ts < end):
            continue
        n = r.get('samples') or 0
        a = r.get(avg_key)
        if a is not None and n:
            num += a * n; den += n
    return (num / den) if den else None


def _max_in_range(rows, ts_key, max_key, start, end):
    vals = [r.get(max_key) for r in rows
            if r.get(ts_key) is not None and start <= r[ts_key] < end
            and r.get(max_key) is not None]
    return max(vals) if vals else None


class PccPanelEnergyPower(BaseLiveStrategy):
    IS_AGGREGATE = True
    interval_seconds = 5.0

    def __init__(self, mfm, query_string: bytes = b''):
        super().__init__(mfm, query_string)
        self._period          = _DEFAULT_PERIOD
        self._trend_range     = _DEFAULT_TREND_RANGE
        self._trend_sampling  = default_sampling_for(_DEFAULT_TREND_RANGE)
        self._trend_cstart    = None
        self._trend_cend      = None
        self._demand_preset   = _DEFAULT_DEMAND_PRESET
        self._np_cache        = None            # DB-driven nameplate/capacity (lt_config_value), lazily fetched + cached

    # ── DB helpers ───────────────────────────────────────────────────

    @database_sync_to_async
    def _fetch_nameplate(self):
        """This panel's nameplate/capacity ratings from the DB (per-MFM lt_config_value → field default → the hardcoded
        NAMEPLATE constant). Editing a panel's ratings is now a DB row, not a code change. [make config DB-driven]"""
        return {k: self.mfm.get_config(k, v) for k, v in NAMEPLATE.items()}

    async def _nameplate(self):
        if self._np_cache is None:
            self._np_cache = await self._fetch_nameplate()
        return self._np_cache

    @database_sync_to_async
    def _load_topology(self):
        return {
            'panel': self.mfm,
            'incoming': list(self.mfm.incoming.select_related('mfm_type').all()),
            'outgoing': list(self.mfm.outgoing.select_related('mfm_type').all()),
        }

    @database_sync_to_async
    def _fetch_panel_live(self):
        if DATA_HAS_PANEL_ID and not self.mfm.panel_id:
            return None
        return fetch_live(self.mfm.db_link, self.mfm.table_name, self.mfm.panel_id,
                          columns=['active_power_total_kw', 'reactive_power_total_kvar',
                                   'apparent_power_total_kva', 'kpi_load_factor',
                                   'peak_demand_today_kw', 'peak_demand_at_time',
                                   'kpi_kw_load_pct_of_rated'])

    @database_sync_to_async
    def _fetch_period_energy(self, panel, period):
        """Latest reading of the pre-computed period-energy counters.

        The simulator maintains today / this_week / this_month rolling totals,
        so the period energy is just the newest value — no MAX-MIN delta and
        therefore none of the non-monotonic-counter artifacts.
        """
        if DATA_HAS_PANEL_ID and not panel.panel_id:
            return {'active_kwh': None, 'reactive_kvarh': None,
                    'apparent_kvah': None, 'sec': None}
        a_col, ap_col, r_col = _PERIOD_ENERGY_COLS[period]
        row = fetch_live(panel.db_link, panel.table_name, panel.panel_id,
                         columns=[a_col, ap_col, r_col, 'specific_energy_consumption']) or {}
        return {
            'active_kwh':     row.get(a_col),
            'apparent_kvah':  row.get(ap_col),
            'reactive_kvarh': row.get(r_col),
            'sec':            row.get('specific_energy_consumption'),
        }

    @database_sync_to_async
    def _fetch_panel_energy_rows(self, panel, start, end, inner_sampling):
        """Inner-bucketed power stats (avg/min/max) for the panel itself.
        Energy is derived from avg power × time in the renderer."""
        if DATA_HAS_PANEL_ID and not panel.panel_id:
            return []
        return fetch_bucketed(
            panel.db_link, panel.table_name, panel.panel_id,
            columns=['active_power_total_kw', 'reactive_power_total_kvar',
                     'apparent_power_total_kva'],
            start=start, end=end, sampling=inner_sampling,
        )

    @database_sync_to_async
    def _fetch_outgoing_rows(self, outgoings, start, end, inner_sampling, with_energy):
        """Per-outgoing inner-bucketed kW (avg/min/max). ``with_energy`` is
        retained for call-site clarity but energy is derived from avg power."""
        out = {}
        for og in outgoings:
            if DATA_HAS_PANEL_ID and not og.panel_id:
                out[og.id] = []
                continue
            try:
                out[og.id] = fetch_bucketed(
                    og.db_link, og.table_name, og.panel_id,
                    columns=['active_power_total_kw'],
                    start=start, end=end, sampling=inner_sampling,
                )
            except Exception:
                out[og.id] = []
        return out

    @database_sync_to_async
    def _find_driver(self, outgoings):
        best, best_kw = None, -1.0
        for og in outgoings:
            if DATA_HAS_PANEL_ID and not og.panel_id:
                continue
            try:
                row = fetch_live(og.db_link, og.table_name, og.panel_id,
                                 columns=['active_power_total_kw']) or {}
                kw = row.get('active_power_total_kw')
                if kw is not None and kw > best_kw:
                    best_kw, best = kw, og
            except Exception:
                continue
        return best, best_kw

    # ── Feeder AGGREGATION (the panel's own table is an empty stub, so panel-level power/energy = Σ its outgoing feeders,
    #    the same source the trend/demand already use; without this the Cumulative-Energy + Live-Power cards read null) ──

    @database_sync_to_async
    def _fetch_aggregate_live(self, outgoings):
        """Panel live power = Σ the outgoing feeders' CURRENT power. Returns {} when no feeder reads (→ card degrades)."""
        active = reactive = apparent = 0.0
        seen = False
        for og in outgoings:
            if DATA_HAS_PANEL_ID and not og.panel_id:
                continue
            try:
                row = fetch_live(og.db_link, og.table_name, og.panel_id,
                                 columns=['active_power_total_kw', 'reactive_power_total_kvar',
                                          'apparent_power_total_kva']) or {}
            except Exception:
                continue
            a, r, ap = (row.get('active_power_total_kw'), row.get('reactive_power_total_kvar'),
                        row.get('apparent_power_total_kva'))
            if a is not None or ap is not None:
                seen = True
            active += a or 0.0
            reactive += r or 0.0
            apparent += ap or 0.0
        if not seen:
            return {}
        return {'active_power_total_kw': active, 'reactive_power_total_kvar': reactive,
                'apparent_power_total_kva': apparent}

    @database_sync_to_async
    def _fetch_aggregate_energy(self, outgoings, start, end, inner_sampling):
        """Panel period energy = Σ over the outgoing feeders of (avg power × time) across the period — avg-power×time
        (same basis as the trend, immune to counter resets), works where the panel's own table is empty. Returns
        {active_kwh, reactive_kvarh, apparent_kvah}; apparent from √(P²+Q²). None fields when no feeder has data."""
        inner_hours = 1 if inner_sampling == 'hour' else 24
        active_kwh = reactive_kvarh = 0.0
        seen = False
        for og in outgoings:
            if DATA_HAS_PANEL_ID and not og.panel_id:
                continue
            try:
                rows = fetch_bucketed(og.db_link, og.table_name, og.panel_id,
                                      columns=['active_power_total_kw', 'reactive_power_total_kvar'],
                                      start=start, end=end, sampling=inner_sampling)
            except Exception:
                continue
            if rows:
                seen = True
                active_kwh     += _energy_in_range(rows, 'active_power_total_kw_avg', start, end, inner_hours)
                reactive_kvarh += _energy_in_range(rows, 'reactive_power_total_kvar_avg', start, end, inner_hours)
        if not seen:
            return {'active_kwh': None, 'reactive_kvarh': None, 'apparent_kvah': None}
        return {'active_kwh': active_kwh, 'reactive_kvarh': reactive_kvarh,
                'apparent_kvah': (active_kwh ** 2 + reactive_kvarh ** 2) ** 0.5}

    @database_sync_to_async
    def _fetch_aggregate_peak(self, outgoings, start, end):
        """Worst panel apparent-power peak over [start,end] = max over hourly buckets of the SUMMED feeder apparent."""
        by_bucket: dict = {}
        for og in outgoings:
            if DATA_HAS_PANEL_ID and not og.panel_id:
                continue
            try:
                rows = fetch_bucketed(og.db_link, og.table_name, og.panel_id,
                                      columns=['apparent_power_total_kva'], start=start, end=end, sampling='hour')
            except Exception:
                continue
            for r in rows:
                b, v = r.get('bucket'), r.get('apparent_power_total_kva_max')
                if b is not None and v is not None:
                    by_bucket[b] = by_bucket.get(b, 0.0) + v
        if not by_bucket:
            return None, None
        peak_at = max(by_bucket, key=by_bucket.get)
        return by_bucket[peak_at], peak_at

    # ── Cumulative Energy ────────────────────────────────────────────

    async def _render_period_energy(self, topo=None):
        if topo is None:
            topo = await self._load_topology()
        from ...services import resolve_range
        start, end = resolve_range(_PERIOD_TO_RANGE[self._period], None, None)
        # The PCC panel's OWN table is an empty stub → aggregate the outgoing feeders (avg-power×time) for the period total.
        inner = 'hour' if self._period == 'daily' else 'day'
        e = await self._fetch_aggregate_energy(topo['outgoing'], start, end, inner)
        active_mwh     = (e['active_kwh']     / 1000.0) if e['active_kwh']     is not None else None
        reactive_mvarh = (e['reactive_kvarh'] / 1000.0) if e['reactive_kvarh'] is not None else None
        apparent_mvah  = (e['apparent_kvah']  / 1000.0) if e['apparent_kvah']  is not None else None

        # Pro-rate the subsidy limit to the selected period. Nameplate ratings are DB-driven (lt_config_value → default).
        np = await self._nameplate()
        month_limit = np['subsidy_limit_mvah_per_month']
        if self._period == 'monthly':
            limit_mvah = month_limit
        elif self._period == 'weekly':
            limit_mvah = month_limit / _WEEKS_PER_MONTH
        else:  # daily
            limit_mvah = month_limit / _DAYS_PER_MONTH

        used_pct = (apparent_mvah / limit_mvah * 100.0) if (apparent_mvah and limit_mvah) else None
        headroom_mvah = (limit_mvah - apparent_mvah) if (apparent_mvah is not None) else None
        sec_kwh_per_unit = np['sec_target_kwh_per_unit']   # neuract feeders carry no SEC column → nameplate target (DB)

        return {
            'config': {
                'periods': list(_PERIODS),
                'current_period': self._period,
                'window_start': start.isoformat(),
                'window_end':   end.isoformat(),
            },
            'value_mvah':     round(apparent_mvah, 2) if apparent_mvah is not None else None,
            'limit_mvah':     round(limit_mvah, 2),
            'pct_used':       round(used_pct, 2) if used_pct is not None else None,
            'headroom_mvah':  round(headroom_mvah, 2) if headroom_mvah is not None else None,
            'active_mwh':     round(active_mwh, 2) if active_mwh is not None else None,
            'reactive_mvarh': round(reactive_mvarh, 2) if reactive_mvarh is not None else None,
            'sec_kwh_per_t':  sec_kwh_per_unit,
            'sec_target':     np['sec_target_kwh_per_unit'],
            'status':         _on_track_status(used_pct),
            'summary': (
                f"{self._period.capitalize()} subsidy headroom is "
                f"{round(headroom_mvah,1) if headroom_mvah is not None else '—'} MVAh "
                f"and rated capacity used is "
                f"{round(used_pct,1) if used_pct is not None else '—'}%."
            ),
        }

    # ── Energy Consumption Trend ─────────────────────────────────────

    async def _render_energy_trend(self, topo=None):
        """Energy Consumption Trend. Each bucket carries BOTH the panel-level
        active/reactive energy AND the per-equipment-family energy
        (ups/bpdp/hhf) inline, plus the rated/contracted reference values
        scaled to the bucket's duration. The frontend's "Total Energy" vs
        "By Equipment" toggle is a pure display choice over the same data."""
        if topo is None:
            topo = await self._load_topology()
        edges = build_bucket_edges(
            self._trend_range, self._trend_sampling,
            custom_start=self._trend_cstart, custom_end=self._trend_cend,
        )
        window_start, window_end = edges[0][0], edges[-1][1]
        inner = _inner_sampling(self._trend_sampling)
        inner_hours = 1 if inner == 'hour' else 24

        panel_rows = await self._fetch_panel_energy_rows(topo['panel'], window_start, window_end, inner)
        per_og = await self._fetch_outgoing_rows(
            topo['outgoing'], window_start, window_end, inner, with_energy=True)

        # Pre-group outgoing rows by family.
        fam_rows: dict[str, list] = {f: [] for f in _FAMILIES}
        for og in topo['outgoing']:
            fam = _family(og.name)
            if fam:
                fam_rows[fam].extend(per_og.get(og.id, []))

        np = await self._nameplate()
        buckets = []
        for (s, e, lbl) in edges:
            bucket = {
                'bucket':   lbl,
                'active':   round(_energy_in_range(panel_rows, 'active_power_total_kw_avg', s, e, inner_hours), 1),
                'reactive': round(_energy_in_range(panel_rows, 'reactive_power_total_kvar_avg', s, e, inner_hours), 1),
                # Reference lines scaled to this bucket's duration (kWh). Nameplate ratings DB-driven.
                'rated':      round(np['rated_kwh_per_day']    * (e - s).total_seconds() / 86_400, 1),
                'contracted': round(np['contract_kwh_per_day'] * (e - s).total_seconds() / 86_400, 1),
            }
            for fam in _FAMILIES:
                bucket[fam] = round(_energy_in_range(fam_rows[fam], 'active_power_total_kw_avg', s, e, inner_hours), 1)
            buckets.append(bucket)

        return {
            'config': {
                'range_options':    list(SAMPLING_BY_RANGE.keys()),
                'current_range':    self._trend_range,
                'sampling_options': list(SAMPLING_BY_RANGE[self._trend_range]),
                'current_sampling': self._trend_sampling,
                'window_start':     window_start.isoformat(),
                'window_end':       window_end.isoformat(),
            },
            'buckets': buckets,
        }

    # ── Today live power analysis ────────────────────────────────────

    async def _render_live_load(self, topo=None):
        if topo is None:
            topo = await self._load_topology()
        row = await self._fetch_aggregate_live(topo['outgoing']) or {}
        active_kw   = row.get('active_power_total_kw')
        reactive_kvar = row.get('reactive_power_total_kvar')
        apparent_kva  = row.get('apparent_power_total_kva')
        rated_kva   = (await self._nameplate())['rated_kva']
        pct_used    = (apparent_kva / rated_kva * 100.0) if (apparent_kva and rated_kva) else None

        # Worst peak over the trailing 7 days = max of the SUMMED feeder apparent per hourly bucket.
        now = datetime.now(timezone.utc)
        peak_kva, peak_at = await self._fetch_aggregate_peak(topo['outgoing'], now - timedelta(days=7), now)
        # Load factor = current apparent load ÷ trailing-7d peak (utilisation of the panel's own recent peak).
        load_factor = (apparent_kva / peak_kva * 100.0) if (apparent_kva and peak_kva) else None

        return {
            'apparent_kva':   round(apparent_kva, 1) if apparent_kva is not None else None,
            'rated_kva':      rated_kva,
            'pct_used':       round(pct_used, 1) if pct_used is not None else None,
            'worst_peak_kva': round(peak_kva, 1) if peak_kva is not None else None,
            'worst_peak_at':  peak_at,
            'active_kw':      round(active_kw, 1) if active_kw is not None else None,
            'reactive_kvar':  round(reactive_kvar, 1) if reactive_kvar is not None else None,
            'load_factor_pct': round(load_factor, 1) if load_factor is not None else None,
            'summary': (
                f"Live apparent power is "
                f"{round(apparent_kva,0) if apparent_kva is not None else '—'} kVA against "
                f"{round(rated_kva,0)} kVA rated capacity."
            ),
        }

    # ── Daily Power Demand by Feeder ─────────────────────────────────

    async def _render_power_demand(self, topo=None):
        if topo is None:
            topo = await self._load_topology()
        preset_range, preset_sampling = _DEMAND_PRESETS[self._demand_preset]
        edges = build_bucket_edges(preset_range, preset_sampling)
        window_start, window_end = edges[0][0], edges[-1][1]
        inner = _inner_sampling(preset_sampling)

        per_og = await self._fetch_outgoing_rows(
            topo['outgoing'], window_start, window_end, inner, with_energy=False)

        # Map each feeder → family (skip unclassified PDB/Spare feeders).
        fam_feeders: dict[str, list] = {f: [] for f in _FAMILIES}
        for og in topo['outgoing']:
            fam = _family(og.name)
            if fam:
                fam_feeders[fam].append(og)

        # Per-bucket family demand = SUM of feeders' avg demand (3 UPS running
        # together draw 3× one UPS — sum, don't average). Worst peak tracks
        # the highest single-feeder instantaneous reading.
        buckets = []
        worst_peak_kw, worst_peak_at, worst_peak_feeder = None, None, None
        agg_per_bucket = []
        for (s, e, lbl) in edges:
            bucket = {'bucket': lbl}
            total = 0.0
            for fam in _FAMILIES:
                fam_kw = 0.0
                for og in fam_feeders[fam]:
                    rows = per_og.get(og.id, [])
                    avg_kw = _weighted_avg_in_range(rows, 'bucket', 'active_power_total_kw_avg', s, e)
                    if avg_kw is not None:
                        fam_kw += avg_kw
                    mx_kw = _max_in_range(rows, 'bucket', 'active_power_total_kw_max', s, e)
                    if mx_kw is not None and (worst_peak_kw is None or mx_kw > worst_peak_kw):
                        worst_peak_kw, worst_peak_at, worst_peak_feeder = mx_kw, lbl, og.name
                bucket[fam] = round(fam_kw, 1)
                total += fam_kw
            agg_per_bucket.append(total)
            buckets.append(bucket)

        agg_peak = max(agg_per_bucket) if agg_per_bucket else None
        mean_demand = (sum(agg_per_bucket) / len(agg_per_bucket)) if agg_per_bucket else None
        load_factor_pct = (mean_demand / agg_peak * 100.0) if (mean_demand and agg_peak) else None

        return {
            'config': {
                'presets': list(_DEMAND_PRESETS.keys()),
                'current_preset': self._demand_preset,
                'window_start': window_start.isoformat(),
                'window_end':   window_end.isoformat(),
            },
            'buckets': buckets,
            'critical_kw': (await self._nameplate())['critical_demand_kw'],
            'kpis': {
                'worst_peak_kw':     round(worst_peak_kw, 1) if worst_peak_kw is not None else None,
                'worst_peak_at':     worst_peak_at,
                'worst_peak_feeder': worst_peak_feeder,
                'load_factor_pct':   round(load_factor_pct, 1) if load_factor_pct is not None else None,
            },
            'summary': (
                f"Worst peak {round(worst_peak_kw,0) if worst_peak_kw is not None else '—'} kW"
                f"{f' ({worst_peak_feeder})' if worst_peak_feeder else ''}; "
                f"load factor {round(load_factor_pct,0) if load_factor_pct is not None else '—'}%."
            ),
        }

    # ── Aggregate render ─────────────────────────────────────────────

    async def aggregate_render(self, dispatcher, initial: bool):
        topo = await self._load_topology()
        period_energy, energy_trend, live_load, power_demand = await asyncio.gather(
            self._render_period_energy(topo),
            self._render_energy_trend(topo),
            self._render_live_load(topo),
            self._render_power_demand(topo),
        )
        return {
            'cumulative':     period_energy,
            'energy_trend':   energy_trend,
            'live_power':     live_load,
            'demand_profile': power_demand,
        }

    # ── Client commands (per-widget filter switches) ─────────────────

    async def handle_command(self, cmd):
        # Cumulative Energy — monthly / weekly / daily
        if 'cumulative' in cmd and isinstance(cmd['cumulative'], dict):
            period = cmd['cumulative'].get('period', self._period)
            if period not in _PERIODS:
                raise ValueError(f"Invalid period '{period}'. Use one of: {list(_PERIODS)}")
            self._period = period
            return {'widget': 'cumulative', 'data': await self._render_period_energy()}

        # Energy Consumption Trend — range × sampling
        if 'energy_trend' in cmd and isinstance(cmd['energy_trend'], dict):
            sub = cmd['energy_trend']
            new_range = self._trend_range
            if 'range' in sub:
                new_range = canonical_range(sub['range']) or sub['range']
            if 'sampling' in sub and sub['sampling']:
                new_sampling = canonical_sampling(sub['sampling']) or sub['sampling']
            elif 'range' in sub:
                new_sampling = default_sampling_for(new_range)
            else:
                new_sampling = self._trend_sampling
            err = validate_range_sampling(new_range, new_sampling)
            if err:
                raise ValueError(err)
            self._trend_range, self._trend_sampling = new_range, new_sampling
            self._trend_cstart = sub.get('start_date', sub.get('start', self._trend_cstart))
            self._trend_cend   = sub.get('end_date',   sub.get('end',   self._trend_cend))
            if new_range == 'custom-range' and not (self._trend_cstart and self._trend_cend):
                raise ValueError("range='custom-range' requires start_date and end_date")
            return {'widget': 'energy_trend', 'data': await self._render_energy_trend()}

        # Daily Power Demand by Feeder — preset
        if 'demand_profile' in cmd and isinstance(cmd['demand_profile'], dict):
            preset = cmd['demand_profile'].get('preset', self._demand_preset)
            if preset not in _DEMAND_PRESETS:
                raise ValueError(f"Invalid preset '{preset}'. Use one of: {list(_DEMAND_PRESETS)}")
            self._demand_preset = preset
            return {'widget': 'demand_profile', 'data': await self._render_power_demand()}

        return None
