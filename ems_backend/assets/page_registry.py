"""Single source of truth for which pages exist per asset type — `assets` app.

Architecture note — this is the key divergence from lt_panels:

  lt_panels: ONE global `_PAGES` list; every type gets every page; per-type
             variation hides in each page's STRATEGIES map.
  assets:    pages are TYPE-SPECIFIC. `PAGES_BY_TYPE[code]` lists the pages
             for that asset type. `COMMON_PAGES` (just `overview`) is merged
             into every type. The STRATEGIES map survives only on `overview`.

`COMMON_PAGES` + `PAGES_BY_TYPE` drive:
  1. `routing.py` (programmatic `websocket_urlpatterns` derivation)
  2. The `pages` action on `AssetViewSet` (per-asset page list with WS URLs)

Adding a page = add a dict under the right type in `PAGES_BY_TYPE` (or to
`COMMON_PAGES` if it's truly shared). Endpoint paths must be globally unique
across all types so routing stays unambiguous — prefix them with the type
(e.g. `ups-battery`); `overview` is the one shared endpoint.

WebSocket URLs are built per request as: ``ws/asset/{asset_id}/{endpoint_path}/``.
"""
from .consumers import (
    OverviewDispatcher,
    UpsBatteryAutonomyDispatcher,
    UpsSourceTransferDispatcher,
    UpsOutputCapacityDispatcher,
    LtTransformerThermalDispatcher,
    LtTransformerLossAnalysisDispatcher,
    LtTransformerUtilizationDispatcher,
    HtTransformerThermalDispatcher,
    DgRuntimeDispatcher,
)
from .consumers._dispatch import resolve_category


# Pages every asset type gets, regardless of type. `overview` is the only
# truly-shared page, so it's the only one keeping a per-type STRATEGIES map.
COMMON_PAGES = [
    {
        'code': 'overview',
        'name': 'Overview',
        'description': 'Headline KPIs + status — common to every asset type.',
        'websockets': [
            {'name': 'Overview Live', 'endpoint_path': 'overview',
             'dispatcher': OverviewDispatcher,
             'description': 'Live headline columns; strategy picked per asset type.'},
        ],
    },
]


# Type-specific pages. Each page belongs to exactly one asset type, so its
# dispatcher is bound to that type (STRATEGY, not STRATEGIES).
PAGES_BY_TYPE = {
    'ups': [
        {
            'code': 'ups-battery-autonomy',
            'name': 'Battery & Autonomy',
            'description': 'Battery DC bus, thermal, SOC/runtime scores and autonomy index.',
            'websockets': [
                {'name': 'Battery & Autonomy Live', 'endpoint_path': 'ups-battery-autonomy',
                 'dispatcher': UpsBatteryAutonomyDispatcher,
                 'description': 'Live stream of the 14 battery & autonomy columns.'},
            ],
        },
        {
            'code': 'ups-source-transfer',
            'name': 'Source & Transfer',
            'description': 'Bypass/sync permissives, transfer readiness and transfer history.',
            'websockets': [
                {'name': 'Source & Transfer Live', 'endpoint_path': 'ups-source-transfer',
                 'dispatcher': UpsSourceTransferDispatcher,
                 'description': 'Live stream of the 12 source & transfer columns.'},
            ],
        },
        {
            'code': 'ups-output-capacity',
            'name': 'Output Load & Capacity',
            'description': 'kW capacity target/headroom and capacity scores.',
            'websockets': [
                {'name': 'Output & Capacity Live', 'endpoint_path': 'ups-output-capacity',
                 'dispatcher': UpsOutputCapacityDispatcher,
                 'description': 'Live stream of the 7 output load & capacity columns.'},
            ],
        },
    ],
    'lt_transformer': [
        {
            'code': 'lt-transformer-thermal',
            'name': 'Thermal & Life',
            'description': 'Hotspot stress, transformer life, derating, efficiency trend + heatmap.',
            'websockets': [
                {'name': 'Thermal & Life', 'endpoint_path': 'lt-transformer-thermal',
                 'dispatcher': LtTransformerThermalDispatcher,
                 'description': 'Widget envelope: kpi_cards · thermal_monitor (live) · '
                                'thermal_series (range×sampling) · peak_heatmap (today/week/month).'},
            ],
        },
        {
            'code': 'lt-transformer-loss',
            'name': 'Loss Analysis',
            'description': 'Hourly loss inspector + stacked loss timeline + load-vs-loss performance map.',
            'websockets': [
                {'name': 'Loss Analysis', 'endpoint_path': 'lt-transformer-loss',
                 'dispatcher': LtTransformerLossAnalysisDispatcher,
                 'description': 'Widget envelope: loss_inspector (pick an hour of today) · '
                                'loss_timeline (range×sampling) · performance_map (load×loss scatter + operating point).'},
            ],
        },
        {
            'code': 'lt-transformer-utilization',
            'name': 'Utilization',
            'description': 'TUF / live load / peak-today / efficiency + 24h hourly load history.',
            'websockets': [
                {'name': 'Utilization', 'endpoint_path': 'lt-transformer-utilization',
                 'dispatcher': LtTransformerUtilizationDispatcher,
                 'description': 'Widget envelope: kpi_cards (live) · load_history (fixed 24h hourly).'},
            ],
        },
    ],
    'ht_transformer': [
        {
            'code': 'ht-transformer-thermal',
            'name': 'Thermal & Loading',
            'description': 'Oil / winding temperature + loading (stub).',
            'websockets': [
                {'name': 'Thermal Live', 'endpoint_path': 'ht-transformer-thermal',
                 'dispatcher': HtTransformerThermalDispatcher,
                 'description': 'Currently stubbed (pending: true).'},
            ],
        },
    ],
    'dg': [
        {
            'code': 'dg-runtime',
            'name': 'Runtime & Fuel',
            'description': 'Run hours, fuel level, battery, load (stub).',
            'websockets': [
                {'name': 'Runtime Live', 'endpoint_path': 'dg-runtime',
                 'dispatcher': DgRuntimeDispatcher,
                 'description': 'Currently stubbed (pending: true).'},
            ],
        },
    ],
}


def _strategy_for(dispatcher, type_code, fallback_code):
    """Resolve the strategy class a dispatcher would use for this asset type.

    Single-type pages expose `STRATEGY`; the shared overview exposes a
    `STRATEGIES` map keyed by type. Returns the class or None.
    """
    if dispatcher is None:
        return None
    single = getattr(dispatcher, 'STRATEGY', None)
    if single is not None:
        return single
    strategies = getattr(dispatcher, 'STRATEGIES', {})
    return strategies.get(type_code) or strategies.get(fallback_code)


def _is_pending(strategy_cls) -> bool:
    """A page is `pending` (placeholder) when its strategy declares nothing to
    render — no columns (live pages), no widgets (overview), not aggregate."""
    if strategy_cls is None:
        return True
    return not (
        getattr(strategy_cls, 'columns', None)
        or getattr(strategy_cls, 'widgets', None)
        or getattr(strategy_cls, 'IS_AGGREGATE', False)
    )


def pages_for_asset(asset, request=None):
    """Build the page list for an Asset: COMMON_PAGES + its type's pages.

    Public function — imported by `views.AssetViewSet.pages`.
    """
    type_code = resolve_category(asset)
    fallback_code = asset.asset_type.code
    type_pages = PAGES_BY_TYPE.get(type_code) or PAGES_BY_TYPE.get(fallback_code) or []
    pages = COMMON_PAGES + type_pages

    host, proto = None, 'ws'
    if request is not None:
        host = request.get_host()
        proto = 'wss' if request.is_secure() else 'ws'

    out = []
    for i, page in enumerate(pages):
        ws_list = []
        for j, ws in enumerate(page.get('websockets', [])):
            ws_path = f"ws/asset/{asset.id}/{ws['endpoint_path']}/"
            strategy_cls = _strategy_for(ws.get('dispatcher'), type_code, fallback_code)
            entry = {
                'name': ws['name'],
                'endpoint_path': ws['endpoint_path'],
                'description': ws.get('description', ''),
                'order': j + 1,
                'ws_url': '/' + ws_path,
                'pending': _is_pending(strategy_cls),
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
    """Yield each unique (endpoint_path, dispatcher) pair across ALL pages
    (common + every type). Deduped by endpoint_path so `overview` is emitted
    once. Used by `routing.py` to build `websocket_urlpatterns`.
    """
    seen = set()
    all_pages = list(COMMON_PAGES)
    for type_pages in PAGES_BY_TYPE.values():
        all_pages.extend(type_pages)
    for page in all_pages:
        for ws in page.get('websockets', []):
            ep = ws['endpoint_path']
            if ep in seen:
                continue
            seen.add(ep)
            yield ep, ws['dispatcher']
