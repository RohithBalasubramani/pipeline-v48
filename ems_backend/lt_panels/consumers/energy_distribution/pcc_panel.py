"""Energy & Distribution — PCC Panel strategy (parent-level aggregate).

Window-aggregated energy accounting view for PCC Panel pages. Different from
the per-outgoing live-kW fan-out used by transformer / lt_panel — this one
emits a single big widget envelope with:

  header     measured_input_kwh, delivered_kwh, loss_kwh + %, meter_gap_kwh + %,
             best_path
  consumers  ranked list of outgoings with delivered_kwh, share_pct,
             efficiency_pct, status
  sankey     5-layer node/link graph: incomers → measured_input → distribution
             → outgoings → load_groups (rolled up via MFM.load_group)
  ai_summary templated narrative

Range filter: today / this_week / this_month — switchable mid-connection
via {"range": "this_week"} command.

Cadence: 30 s (totals change slowly).
"""
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from channels.db import database_sync_to_async

from .._fanout_base import BaseAggregateEDStrategy
from ...services import fetch_energy_delta, resolve_range, DATA_HAS_PANEL_ID


_RANGES = ['today', 'yesterday', 'this_week', 'this_month', 'last_24h', 'last_7d']
_DEFAULT_RANGE = 'today'

# The cumulative energy meter on each MFM's table. delta = MAX - MIN over window.
_ENERGY_COL = 'active_energy_import_kwh'


def _meter_gap_status(pct: float | None) -> str:
    if pct is None:
        return 'OK'
    p = abs(pct)
    if p < 1.0:  return 'OK'
    if p < 5.0:  return 'Watch'
    return 'Review'


def _efficiency_status(pct: float | None) -> str:
    if pct is None:
        return 'Unknown'
    if pct >= 97.0: return 'Normal'
    if pct >= 95.0: return 'Watch'
    return 'Critical'


def _utilization_status(pct: float | None) -> str:
    """Rail bar status: > 100% overloaded vs. nameplate, 85–100% Watch, else Normal."""
    if pct is None:
        return 'Unknown'
    if pct > 100.0: return 'Critical'
    if pct >= 85.0: return 'Watch'
    return 'Normal'


def _capacity_kwh(mfm, side: str, hours: float) -> float | None:
    """Window capacity in kWh from the nameplate live-load rating.
        side='outgoing' → reads stashed `_rated_outgoing_kw` (PCC's rated output,
                          or a source's deliverable)
        side='incoming' → reads stashed `_rated_incoming_kw` (PCC's rated input,
                          or a feeder's rated draw)
    The rated values are pre-fetched on the MFM objects by `_load_topology`
    (sync) so this helper stays safe to call from async render code.
    Returns None when the field is unset on this MFM type — caller falls
    back to omitting capacity / utilization."""
    if hours <= 0:
        return None
    attr = '_rated_outgoing_kw' if side == 'outgoing' else '_rated_incoming_kw'
    kw = getattr(mfm, attr, None)
    if kw is None:
        return None
    try:
        return float(kw) * hours
    except (TypeError, ValueError):
        return None


class PccPanelEnergyDistribution(BaseAggregateEDStrategy):
    interval_seconds = 30.0

    def __init__(self, mfm, query_string: bytes = b''):
        super().__init__(mfm, query_string)
        # Parse ?range= from URL if present
        from urllib.parse import parse_qs
        qs = parse_qs(query_string.decode() if query_string else '')
        self._range = qs.get('range', [_DEFAULT_RANGE])[0]
        if self._range not in _RANGES:
            self._range = _DEFAULT_RANGE

    # ── DB helpers ───────────────────────────────────────────────────

    @database_sync_to_async
    def _load_topology(self):
        # Pre-stash rated kW from the EAV nameplate config on each MFM object
        # so the async render path can read them without touching the ORM.
        def _stash(mfm):
            mfm._rated_incoming_kw = mfm.get_config('incoming_live_load_kw')
            mfm._rated_outgoing_kw = mfm.get_config('outgoing_live_load_kw')
            return mfm
        panel = _stash(self.mfm)
        incoming = [_stash(m) for m in self.mfm.incoming.select_related('mfm_type').all()]
        outgoing = [_stash(m) for m in self.mfm.outgoing.select_related('mfm_type').all()]
        return {'panel': panel, 'incoming': incoming, 'outgoing': outgoing}

    @database_sync_to_async
    def _fetch_window_energy(self, mfms, start, end):
        """Per-MFM energy delta over [start, end]. Returns {mfm_id: float|None}."""
        out = {}
        for m in mfms:
            if DATA_HAS_PANEL_ID and not m.panel_id:
                out[m.id] = None
                continue
            try:
                out[m.id] = fetch_energy_delta(
                    m.db_link, m.table_name, m.panel_id,
                    _ENERGY_COL, start, end,
                )
            except Exception:
                out[m.id] = None
        return out

    @database_sync_to_async
    def _fetch_panel_energy(self, panel, start, end):
        if DATA_HAS_PANEL_ID and not panel.panel_id:
            return None
        try:
            return fetch_energy_delta(
                panel.db_link, panel.table_name, panel.panel_id,
                _ENERGY_COL, start, end,
            )
        except Exception:
            return None

    # ── Render ───────────────────────────────────────────────────────

    async def aggregate_render(self, dispatcher, initial: bool):
        # Window
        try:
            start, end = resolve_range(self._range, None, None)
        except Exception:
            start, end = resolve_range(_DEFAULT_RANGE, None, None)
            self._range = _DEFAULT_RANGE
        hours = max(0.0, (end - start).total_seconds() / 3600.0)

        topo = await self._load_topology()
        in_kwh, out_kwh, panel_kwh = await asyncio.gather(
            self._fetch_window_energy(topo['incoming'], start, end),
            self._fetch_window_energy(topo['outgoing'], start, end),
            self._fetch_panel_energy(topo['panel'], start, end),
        )

        # Aggregate totals
        sum_incoming = sum((v or 0.0) for v in in_kwh.values())
        sum_outgoing = sum((v or 0.0) for v in out_kwh.values())
        # Prefer the panel's own measured input over incomer sum if available
        measured_input = panel_kwh if panel_kwh is not None else sum_incoming
        delivered = sum_outgoing
        loss = (measured_input - delivered) if measured_input is not None else None
        loss_pct = (loss / measured_input * 100.0) if (loss is not None and measured_input) else None
        # Meter gap = Σ outgoing meters − allocated input (the cumulative
        # drift between sub-meter sums and what was allocated). If panel
        # has no own meter, fall back to (out − in).
        allocated = measured_input or sum_incoming
        meter_gap = (sum_outgoing - allocated) if allocated is not None else None
        meter_gap_pct = (meter_gap / allocated * 100.0) if (meter_gap is not None and allocated) else None

        # Per-consumer rows (ranked desc by delivered kWh).
        # capacity_kwh = the feeder's rated incoming live load × window hours;
        # utilization_pct = delivered_kwh / capacity_kwh × 100 — drives the rail's
        # per-row utilization bar on the frontend.
        consumers = []
        for og in topo['outgoing']:
            kwh = out_kwh.get(og.id)
            share = (kwh / delivered * 100.0) if (kwh is not None and delivered) else None
            allocated_in = (allocated * (share / 100.0)) if (share is not None and allocated) else None
            eff = (kwh / allocated_in * 100.0) if (allocated_in and kwh is not None) else None
            cap_kwh = _capacity_kwh(og, 'incoming', hours)
            util = (kwh / cap_kwh * 100.0) if (kwh is not None and cap_kwh) else None
            consumers.append({
                'mfm_id': og.id, 'name': og.name,
                'type': og.mfm_type.code,
                'load_group': og.load_group or 'Other',
                'delivered_kwh': round(kwh, 2) if kwh is not None else None,
                'share_pct': round(share, 2) if share is not None else None,
                'efficiency_pct': round(eff, 2) if eff is not None else None,
                'status': _efficiency_status(eff),
                'capacity_kwh':    round(cap_kwh, 2) if cap_kwh is not None else None,
                'utilization_pct': round(util,    2) if util    is not None else None,
            })
        consumers.sort(key=lambda c: -(c['delivered_kwh'] or 0))

        # Per-incomer rows — same shape as consumers[], drives the rail's left
        # column. capacity_kwh = source's rated outgoing live load × hours.
        incomers = []
        for inc in topo['incoming']:
            kwh = in_kwh.get(inc.id)
            cap_kwh = _capacity_kwh(inc, 'outgoing', hours)
            util = (kwh / cap_kwh * 100.0) if (kwh is not None and cap_kwh) else None
            incomers.append({
                'mfm_id': inc.id, 'name': inc.name,
                'type': inc.mfm_type.code,
                'source_group':    inc.load_group or inc.name,
                'kwh':             round(kwh, 2)     if kwh     is not None else None,
                'capacity_kwh':    round(cap_kwh, 2) if cap_kwh is not None else None,
                'utilization_pct': round(util,    2) if util    is not None else None,
                'status':          _utilization_status(util),
            })
        incomers.sort(key=lambda r: -(r['kwh'] or 0))

        # Panel-level "All / Total supplied" meter — header row in the rail.
        main_meter_capacity = _capacity_kwh(self.mfm, 'incoming', hours)
        main_meter_util = (
            (measured_input / main_meter_capacity * 100.0)
            if (measured_input is not None and main_meter_capacity) else None
        )

        best = consumers[0] if consumers else None

        # ── Sankey nodes + links (5 layers) ──────────────────────────
        nodes = []
        links = []

        # Layer 0: incomers (kind="source")
        for inc in topo['incoming']:
            kwh = in_kwh.get(inc.id) or 0.0
            nodes.append({
                'id': f'in-{inc.id}', 'label': inc.name,
                'kwh': round(kwh, 2), 'layer': 0, 'kind': 'source', 'mfm_id': inc.id,
            })
            links.append({'source': f'in-{inc.id}', 'target': 'measured', 'kwh': round(kwh, 2)})

        # Layer 1: measured input (kind="meter" — the panel's own main meter)
        nodes.append({
            'id': 'measured', 'label': f'Measured {self.mfm.name} input',
            'kwh': round(measured_input or 0.0, 2), 'layer': 1, 'kind': 'meter',
            'mfm_id': self.mfm.id,
        })
        # Layer 2: distribution allocation (kind="stage") — = measured_input by definition.
        nodes.append({
            'id': 'dist', 'label': 'Distribution allocation',
            'kwh': round(allocated or 0.0, 2), 'layer': 2, 'kind': 'stage',
        })
        links.append({'source': 'measured', 'target': 'dist', 'kwh': round(measured_input or 0.0, 2)})

        # Layer 3: individual outgoings (kind="load")
        for c in consumers:
            kwh = c['delivered_kwh'] or 0.0
            nodes.append({
                'id': f'out-{c["mfm_id"]}', 'label': c['name'],
                'kwh': kwh, 'layer': 3, 'kind': 'load', 'mfm_id': c['mfm_id'],
                'load_group': c['load_group'],
            })
            links.append({'source': 'dist', 'target': f'out-{c["mfm_id"]}', 'kwh': kwh})

        # Layer 4: load groups (rolled up, kind="stage")
        group_totals = defaultdict(float)
        for c in consumers:
            group_totals[c['load_group']] += (c['delivered_kwh'] or 0.0)
        for g, total in sorted(group_totals.items(), key=lambda kv: -kv[1]):
            gid = f'grp-{g.lower().replace(" ", "-").replace("—","").replace("/","")}'
            nodes.append({
                'id': gid, 'label': g, 'kwh': round(total, 2), 'layer': 4, 'kind': 'stage',
            })
            for c in consumers:
                if c['load_group'] == g and (c['delivered_kwh'] or 0) > 0:
                    links.append({
                        'source': f'out-{c["mfm_id"]}', 'target': gid,
                        'kwh': c['delivered_kwh'],
                    })

        # Loss node — balances the sankey so dist's outflows sum to measured_input.
        # Without this, dist → outgoings sums to `delivered` (< measured_input) and
        # the missing `loss_kwh` only lived in header. Now it's a real flow.
        if loss is not None and loss > 0:
            nodes.append({
                'id': 'loss', 'label': 'Loss', 'kwh': round(loss, 2),
                'layer': 4, 'kind': 'loss',
            })
            links.append({'source': 'dist', 'target': 'loss', 'kwh': round(loss, 2)})

        # ── AI summary (templated for now — wire LLM later) ──────────
        if best and best.get('share_pct') is not None:
            ai_text = (
                f"{best['name']} is the major consumer at {best['share_pct']:.1f}%; "
                f"watch {best['name']} loss and reconcile "
                f"{(meter_gap_pct or 0):+.1f}% meter gap."
            )
        else:
            ai_text = 'No consumer data available for the selected range.'

        return {
            'config': {
                'ranges': _RANGES,
                'default_range': _DEFAULT_RANGE,
                'current_range': self._range,
                'window_start': start.isoformat(),
                'window_end':   end.isoformat(),
            },
            'header': {
                'measured_input_kwh': round(measured_input, 2) if measured_input is not None else None,
                'delivered_kwh':      round(delivered, 2),
                'loss_kwh':           round(loss, 2) if loss is not None else None,
                'loss_pct':           round(loss_pct, 2) if loss_pct is not None else None,
                'meter_gap_kwh':      round(meter_gap, 2) if meter_gap is not None else None,
                'meter_gap_pct':      round(meter_gap_pct, 2) if meter_gap_pct is not None else None,
                'meter_gap_status':   _meter_gap_status(meter_gap_pct),
                'best_path':          {'mfm_id': best['mfm_id'], 'name': best['name'],
                                       'share_pct': best['share_pct']} if best else None,
                'main_meter': {
                    'mfm_id':          self.mfm.id,
                    'name':            self.mfm.name,
                    'kwh':             round(measured_input,       2) if measured_input       is not None else None,
                    'capacity_kwh':    round(main_meter_capacity,  2) if main_meter_capacity  is not None else None,
                    'utilization_pct': round(main_meter_util,      2) if main_meter_util      is not None else None,
                    'status':          _utilization_status(main_meter_util),
                },
            },
            'incomers':  incomers,
            'consumers': consumers,
            'sankey':    {'nodes': nodes, 'links': links},
            'ai_summary': {
                'badge': 'accounting',
                'text': ai_text,
            },
        }

    # ── Client commands ──────────────────────────────────────────────

    async def handle_command(self, cmd):
        new_range = cmd.get('range')
        if not new_range:
            return None
        if new_range not in _RANGES:
            raise ValueError(f"Invalid range '{new_range}'. Use one of: {_RANGES}")
        self._range = new_range
        widgets = await self.aggregate_render(None, initial=True)
        return {'widget': '__all__', 'data': widgets}
