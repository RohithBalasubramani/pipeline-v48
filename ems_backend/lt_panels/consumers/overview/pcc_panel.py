"""Overview — PCC Panel strategy (aggregate / fan-out).

PCC Panel overview is a Single-Line Diagram view: it pulls data from the
panel's own bus measurement AND from each incoming/outgoing MFM. Three
widget blocks:

  header_status   {all, critical, warning, normal}    — counts across panel + children
  header_kpis     Main MFM kW · Incoming kW (count) · Outgoing kW (count) ·
                  Avg PF · Meter Gap (main − sum_outgoings) · Alerts
  sld             {incoming: [...], outgoing: [...]}  — per-child mfm_id, name,
                  type, kW, breaker_state, status
  selected_feeder Set on demand via client command:
                    {"select_feeder": <mfm_id>}
                  Server replies with:
                    {"type":"widget_update","widget":"selected_feeder","data":{...}}

Cadence: 2 s (cheaper than 1 s — fan-out queries the timeseries DB once per
child per tick).
"""
import asyncio

from channels.db import database_sync_to_async

from .._overview_base import BaseOverviewStrategy
from ...services import fetch_live, DATA_HAS_PANEL_ID


# Columns we try to read on each child (column-tolerant fetch silently drops
# any that don't exist on that type's table).
_CHILD_LIVE_COLS = [
    'active_power_total_kw',
    'reactive_power_total_kvar',
    'apparent_power_total_kva',
    'power_factor_total',
    'kpi_kw_load_pct_of_rated',
    'breaker_state',          # TODO: confirm — drives CLOSED / WATCH / OPEN
    'health_status',          # TODO: confirm — Normal / Watch / Critical
    'active_energy_today_kwh',
]

_PANEL_OWN_COLS = [
    'active_power_total_kw',          # Main MFM kW
    'power_factor_total',             # Avg PF
    'reactive_power_total_kvar',
    'apparent_power_total_kva',
    'health_status',                  # TODO
    'alerts_critical_count',          # TODO
    'alerts_total_count',             # TODO
]


def _label_pf_status(pf):
    if pf is None: return None
    if pf >= 0.95: return 'Live'
    if pf >= 0.90: return 'Watch'
    return 'Critical'


def _label_alerts(critical, total):
    if critical and critical > 0: return 'Critical'
    if total and total > 0:       return 'Watch'
    return 'Normal'


def _label_health(status):
    """Pass-through with sensible default."""
    if not status: return 'Normal'
    return str(status)


class PccPanelOverview(BaseOverviewStrategy):
    IS_AGGREGATE = True
    interval_seconds = 2.0

    def __init__(self, mfm, query_string: bytes = b''):
        super().__init__(mfm, query_string)
        self._selected_feeder_id: int | None = None

    # ── DB helpers ─────────────────────────────────────────────────────

    @database_sync_to_async
    def _load_topology(self):
        """Snapshot of the panel's incoming + outgoing M2M (with type info)."""
        return {
            'incoming': list(self.mfm.incoming.select_related('mfm_type').all()),
            'outgoing': list(self.mfm.outgoing.select_related('mfm_type').all()),
        }

    @database_sync_to_async
    def _fetch_panel_row(self):
        if DATA_HAS_PANEL_ID and not self.mfm.panel_id:
            return None
        return fetch_live(
            self.mfm.db_link, self.mfm.table_name, self.mfm.panel_id,
            columns=_PANEL_OWN_COLS,
        )

    @database_sync_to_async
    def _fetch_children_rows(self, children):
        """One DB roundtrip per child. Returns [{mfm_id, name, type, ...row}]."""
        out = []
        for c in children:
            row = None
            if c.panel_id:
                try:
                    row = fetch_live(c.db_link, c.table_name, c.panel_id,
                                     columns=_CHILD_LIVE_COLS) or {}
                except Exception as exc:
                    row = {'_error': str(exc)}
            out.append({
                'mfm_id': c.id,
                'name': c.name,
                'type': c.mfm_type.code,
                'panel_id': c.panel_id,
                'row': row or {},
            })
        return out

    @database_sync_to_async
    def _fetch_one_feeder(self, mfm_id):
        from ...models import MFM
        try:
            child = MFM.objects.select_related('mfm_type').get(id=mfm_id)
        except MFM.DoesNotExist:
            return None
        if DATA_HAS_PANEL_ID and not child.panel_id:
            return {
                'mfm_id': child.id, 'name': child.name,
                'type': child.mfm_type.code,
                'pending': True, 'note': 'no panel_id configured',
            }
        row = fetch_live(child.db_link, child.table_name, child.panel_id,
                         columns=_CHILD_LIVE_COLS) or {}
        return self._render_feeder_block(child, row)

    @staticmethod
    def _render_feeder_block(child, row):
        return {
            'mfm_id': child.id,
            'name': child.name,
            'subtitle': f"{child.name} - {child.panel_id}",
            'type': child.mfm_type.code,
            'status': _label_health(row.get('health_status')),
            'kw':       row.get('active_power_total_kw'),
            'kvar':     row.get('reactive_power_total_kvar'),
            'kva':      row.get('apparent_power_total_kva'),
            'load_pct': row.get('kpi_kw_load_pct_of_rated'),
            'pf':       row.get('power_factor_total'),
            'kwh':      row.get('active_energy_today_kwh'),
            'ts':       row.get('ts'),
        }

    # ── Aggregate render ───────────────────────────────────────────────

    async def aggregate_render(self, dispatcher):
        topo = await self._load_topology()
        # Fan out: panel's own row + each incoming + each outgoing in parallel
        panel_row, in_rows, out_rows = await asyncio.gather(
            self._fetch_panel_row(),
            self._fetch_children_rows(topo['incoming']),
            self._fetch_children_rows(topo['outgoing']),
        )
        panel_row = panel_row or {}

        # Aggregate KPIs
        in_total_kw  = sum((r['row'].get('active_power_total_kw') or 0.0) for r in in_rows)
        out_total_kw = sum((r['row'].get('active_power_total_kw') or 0.0) for r in out_rows)
        main_kw      = panel_row.get('active_power_total_kw')
        meter_gap    = (main_kw - out_total_kw) if main_kw is not None else None

        # Status counters across panel + children
        statuses = [_label_health(panel_row.get('health_status'))]
        statuses += [_label_health(r['row'].get('health_status')) for r in in_rows]
        statuses += [_label_health(r['row'].get('health_status')) for r in out_rows]
        counts = {
            'all':      len(statuses),
            'critical': sum(1 for s in statuses if s == 'Critical'),
            'warning':  sum(1 for s in statuses if s in ('Watch', 'Warning')),
            'normal':   sum(1 for s in statuses if s == 'Normal'),
        }

        avg_pf = panel_row.get('power_factor_total')
        alerts_crit  = panel_row.get('alerts_critical_count')
        alerts_total = panel_row.get('alerts_total_count')

        # SLD entries
        def sld_entry(c, role):
            row = c['row']
            return {
                'mfm_id':        c['mfm_id'],
                'name':          c['name'],
                'type':          c['type'],
                'role':          role,
                'kw':            row.get('active_power_total_kw'),
                'pf':            row.get('power_factor_total'),
                'breaker_state': row.get('breaker_state'),
                'status':        _label_health(row.get('health_status')),
            }

        widgets = {
            'header_status': counts,
            'header_kpis': {
                'main_mfm_kw':      main_kw,
                'main_mfm_status':  _label_health(panel_row.get('health_status')),
                'incoming_kw':      round(in_total_kw, 2),
                'incoming_count':   len(in_rows),
                'outgoing_kw':      round(out_total_kw, 2),
                'outgoing_count':   len(out_rows),
                'avg_pf':           avg_pf,
                'avg_pf_status':    _label_pf_status(avg_pf),
                'meter_gap_kw':     round(meter_gap, 2) if meter_gap is not None else None,
                'meter_gap_status': 'Review' if (meter_gap is not None and abs(meter_gap) > 50) else 'OK',
                'alerts_critical':  alerts_crit,
                'alerts_total':     alerts_total,
                'alerts_status':    _label_alerts(alerts_crit, alerts_total),
            },
            'sld': {
                'incoming': [sld_entry(c, 'incoming') for c in in_rows],
                'outgoing': [sld_entry(c, 'outgoing') for c in out_rows],
            },
            '_ts': panel_row.get('ts'),
        }

        # If a feeder is selected, refresh its detail block too
        if self._selected_feeder_id is not None:
            sf = await self._fetch_one_feeder(self._selected_feeder_id)
            if sf:
                widgets['selected_feeder'] = sf

        return widgets

    async def aggregate_layout(self, dispatcher):
        return [
            {'name': 'header_status',   'kind': 'StatusCounters'},
            {'name': 'header_kpis',     'kind': 'KpiStrip'},
            {'name': 'sld',             'kind': 'SingleLineDiagram'},
            {'name': 'selected_feeder', 'kind': 'FeederDetail',
             'cmd': 'select_feeder', 'arg': 'mfm_id'},
        ]

    async def handle_command(self, cmd):
        """Recognised commands:
          {"select_feeder": <mfm_id>}   — pick a feeder to detail
          {"clear_feeder": true}        — drop the selection
        """
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
        sf = await self._fetch_one_feeder(mfm_id)
        return {'widget': 'selected_feeder', 'data': sf}
