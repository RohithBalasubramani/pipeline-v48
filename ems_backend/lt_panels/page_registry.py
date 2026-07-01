"""Single source of truth for which pages exist and which dispatchers
serve them.

`_PAGES` here drives:
  1. `routing.py` (programmatic `websocket_urlpatterns` derivation)
  2. The `pages` action on `MFMViewSet` (per-MFM page list with WS URLs)

Adding a new page = add a dict to `_PAGES` here. `routing.py` updates
automatically; `MFMViewSet.pages` picks it up on the next request.

Pages/WebSocket endpoints are coupled to the consumer module layout under
`lt_panels/consumers/`. Per-page availability for a given MFMType is
derived from each Dispatcher's `STRATEGIES` dict — a stub strategy still
advertises the page so the frontend can render a placeholder.

WebSocket URLs are built per request as: ``ws/mfm/{mfm_id}/{endpoint_path}/``.
"""
from .consumers import (
    OverviewDispatcher,
    RealTimeMonitoringDispatcher,
    VoltageCurrentDispatcher,
    EnergyPowerDispatcher,
    EnergyPowerHistoryDispatcher,
    EnergyDistributionDispatcher,
    PowerQualitySummaryDispatcher,
    VoltageHistoryDispatcher,
    CurrentHistoryDispatcher,
    DemandProfileDispatcher,
    LoadAnomaliesDispatcher,
)
from .consumers._dispatch import resolve_category


_PAGES = [
    {
        'code': 'overview',
        'name': 'Overview',
        'description': 'Headline KPIs + status widgets (gauges, sparks, AI summary).',
        'websockets': [
            {'name': 'Overview Live', 'endpoint_path': 'overview',
             'dispatcher': OverviewDispatcher,
             'description': 'Per-widget envelope (live tick + range/event widgets).'},
        ],
    },
    {
        'code': 'real-time-monitoring',
        'name': 'Real Time Monitoring',
        'description': 'Live Power/Energy + Voltage + Current (60-sec rolling window).',
        'websockets': [
            {'name': 'Live Stream', 'endpoint_path': 'real-time-monitoring',
             'dispatcher': RealTimeMonitoringDispatcher,
             'description': 'Single live stream of all RTM columns at 1-sec cadence.'},
        ],
    },
    {
        'code': 'energy-power',
        'name': 'Energy & Power',
        'description': "Today's energy KPIs + Power Energy Analysis bars + Load Anomalies chart.",
        'websockets': [
            {'name': 'Energy & Power KPIs (Live)', 'endpoint_path': 'energy-power',
             'dispatcher': EnergyPowerDispatcher,
             'description': "Today's Energy + Input vs Output live KPI stream (delta queue)."},
            {'name': 'Power Energy Analysis (History)', 'endpoint_path': 'demand-profile',
             'dispatcher': DemandProfileDispatcher,
             'description': 'Hourly-bucketed active/reactive/demand bars with range/sampling filters.'},
            {'name': 'Load Anomalies (History)', 'endpoint_path': 'load-anomalies',
             'dispatcher': LoadAnomaliesDispatcher,
             'description': 'Bucketed actual/expected load + surge/dip event markers.'},
            {'name': 'Energy & Power History', 'endpoint_path': 'energy-power-history',
             'dispatcher': EnergyPowerHistoryDispatcher,
             'description': 'Bucketed Active/Reactive bars + Load Anomalies trace + window KPIs (Today/Week/Month).'},
        ],
    },
    {
        'code': 'energy-distribution',
        'name': 'Energy Distribution',
        'description': 'Per-outgoing-feeder live kW breakdown.',
        'websockets': [
            {'name': 'Energy Distribution (Live)', 'endpoint_path': 'energy-distribution',
             'dispatcher': EnergyDistributionDispatcher,
             'description': 'Fans out across mfm.outgoing; one live kW per feeder.'},
        ],
    },
    {
        'code': 'voltage-current',
        'name': 'Voltage & Current',
        'description': 'Live V/I + deviation/unbalance/sag/swell history.',
        'websockets': [
            {'name': 'Live V/I (with status)', 'endpoint_path': 'voltage-current',
             'dispatcher': VoltageCurrentDispatcher,
             'description': 'Voltage Live Health + Current Live Health (delta queue, status labels).'},
            {'name': 'Voltage History', 'endpoint_path': 'voltage-history',
             'dispatcher': VoltageHistoryDispatcher,
             'description': 'Time-bucketed phase voltages + sag/swell + Primary Event KPIs.'},
            {'name': 'Current History', 'endpoint_path': 'current-history',
             'dispatcher': CurrentHistoryDispatcher,
             'description': 'Time-bucketed phase currents + Peak/Avg/Unbalance/Neutral KPIs.'},
        ],
    },
    {
        'code': 'power-quality',
        'name': 'Power Quality',
        'description': 'Harmonics & PQ — one socket: filtered event timeline, PQ '
                       'inspector, fleet matrix, priority, and harmonic signature.',
        'websockets': [
            # Single endpoint for the whole Harmonics & PQ tab. It carries the
            # PQ Inspector (pq_exposure_share), the filtered event_timeline
            # (counts + worst-THD line overlays + bucket selector), fleet_matrix,
            # pq_priority, and the harmonic `signature` (radar). The former
            # distortion-harmonics + power-quality-history endpoints are folded
            # in here, so the page opens just this one WS.
            {'name': 'Power Quality (Live)', 'endpoint_path': 'power-quality-summary',
             'dispatcher': PowerQualitySummaryDispatcher,
             'description': 'PQ inspector + event timeline (range/sampling/bucket) + '
                            'fleet matrix + priority + harmonic signature.'},
        ],
    },
]


def _page_supports_type(page: dict, type_code: str, fallback_code: str | None = None) -> bool:
    """A page is shown for a type only if at least one of its non-history
    WebSockets has a strategy registered for that type (or the fallback
    mfm_type.code, when category resolution found a name-prefix category).
    History WSes (dispatcher=None) are type-agnostic and don't gate page
    visibility."""
    keys = [type_code]
    if fallback_code and fallback_code != type_code:
        keys.append(fallback_code)
    has_dispatcher = False
    for ws in page.get('websockets', []):
        d = ws.get('dispatcher')
        if d is None:
            continue
        has_dispatcher = True
        s = getattr(d, 'STRATEGIES', {})
        if any(k in s for k in keys):
            return True
    return not has_dispatcher


def pages_for_mfm(mfm, request=None):
    """Build the page list for an MFM with full WebSocket URLs.

    A page is included iff this MFM's type has at least one strategy
    registered on one of the page's dispatchers (history-only pages always
    included). Each WS entry advertises whether its strategy is `pending`
    so the frontend can render a placeholder rather than wait for data.

    Public function (no underscore) — imported by `views.MFMViewSet.pages`.
    """
    type_code = resolve_category(mfm)             # name-prefix aware
    fallback_code = mfm.mfm_type.code              # underlying MFMType
    pages = [p for p in _PAGES if _page_supports_type(p, type_code, fallback_code)]

    host, proto = None, 'ws'
    if request is not None:
        host = request.get_host()
        proto = 'wss' if request.is_secure() else 'ws'

    out = []
    for i, page in enumerate(pages):
        ws_list = []
        for j, ws in enumerate(page.get('websockets', [])):
            ws_path = f"ws/mfm/{mfm.id}/{ws['endpoint_path']}/"
            dispatcher = ws.get('dispatcher')
            strategies = getattr(dispatcher, 'STRATEGIES', {}) if dispatcher else {}
            # Try category first, fall back to underlying type code
            strategy_cls = strategies.get(type_code) or strategies.get(fallback_code)
            # Pending = strategy registered but is a stub (no columns / no
            # widgets / no power_column / not aggregate). Aggregate strategies
            # override aggregate_render() / handle_command() instead of
            # declaring columns — recognise them via IS_AGGREGATE.
            pending = False
            if strategy_cls is not None:
                cls_columns   = getattr(strategy_cls, 'columns', None)
                cls_widgets   = getattr(strategy_cls, 'widgets', None)
                cls_power_col = getattr(strategy_cls, 'power_column', None)
                cls_aggregate = getattr(strategy_cls, 'IS_AGGREGATE', False)
                pending = not (cls_columns or cls_widgets or cls_power_col or cls_aggregate)
            entry = {
                'name': ws['name'],
                'endpoint_path': ws['endpoint_path'],
                'description': ws.get('description', ''),
                'order': j + 1,
                'ws_url': '/' + ws_path,
                'pending': pending,
            }
            if host:
                entry['ws_url_abs'] = f'{proto}://{host}/{ws_path}'
            ws_list.append(entry)
        out.append({
            'code': page['code'],
            'name': page['name'],
            'order': i + 1,
            'description': page.get('description', ''),
            'websockets': ws_list,
        })
    return out


def iter_websocket_endpoints():
    """Yield each unique (endpoint_path, dispatcher) pair across all pages.

    Used by `routing.py` to programmatically build `websocket_urlpatterns`
    without duplicating the list. Endpoints that appear under multiple
    pages (e.g. `demand-profile` lives under Energy & Power) are emitted
    only once.
    """
    seen = set()
    for page in _PAGES:
        for ws in page.get('websockets', []):
            ep = ws['endpoint_path']
            if ep in seen:
                continue
            seen.add(ep)
            yield ep, ws['dispatcher']
