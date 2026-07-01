"""REST endpoints for the lt_panels app.

Contains `MFMViewSet` and the `assets` view (flat hierarchy of major
assets: transformers / DGs / UPS). Adjacent concerns live in their own
modules to keep this file focused:

  page_registry.py        — `_PAGES` + `pages_for_mfm()` (drives the
                            `pages` action below + routing.py)
  electrical_equipment.py — static sidebar tree + the
                            `electrical_equipment` REST view (`/api/ems/`)
"""
import re

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ParseError

from .models import MFM, Asset3D
from .serializers import MFMSerializer, ParameterSerializer, Asset3DSerializer
from .services import fetch_live, fetch_history, fetch_config_row
from .page_registry import pages_for_mfm
from .detail_registry import details_for_mfm
from .electrical_equipment import (
    _build_name_to_mfm_id,
    _attach_mfm_ids,
    _count_leaves,
    _count_matched,
)


# Column-name allowlist for client-supplied `?columns=` parameters on
# the REST `history/` action. Defense-in-depth before passing to
# services.fetch_*; the services layer also drops columns that don't
# exist on the actual table, but this regex stops bad characters
# reaching SQL even if introspection is bypassed.
_VALID_COLUMN_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,62}$')


def _filter_columns_param(cols_param):
    """Split a `?columns=a,b,c` parameter and drop anything that isn't a
    SQL-safe identifier. Returns (valid_columns, rejected_columns).
    Empty string / None returns ([], []) so the caller can decide whether
    to use the strategy default.
    """
    if not cols_param:
        return [], []
    requested = [c.strip() for c in cols_param.split(',') if c.strip()]
    valid    = [c for c in requested if _VALID_COLUMN_NAME_RE.match(c)]
    rejected = [c for c in requested if not _VALID_COLUMN_NAME_RE.match(c)]
    return valid, rejected


# Per-MFM-type → config table mapping for the `config` action. Tables
# created by `lt_panel_simulator.py --init-db` and seeded one row per
# MFM. See BACKEND_API_AND_WEBSOCKETS.md Part 1.5.
_CONFIG_TABLE_BY_TYPE = {
    'transformer': 'transformer_config',
    'ups':         'ups_config',
    'lt_panel':    'lt_panel_config',
    'ht_panel':    'ht_panel_config',
    'apfc':        'apfc_config',
}


class MFMViewSet(viewsets.ReadOnlyModelViewSet):
    """List MFMs and serve live / historical readings from each MFM's db_link."""

    queryset = (
        MFM.objects
        .select_related('mfm_type', 'mfm_type__default_asset_3d', 'asset_3d_override')
        .prefetch_related('mfm_type__parameters', 'incoming', 'outgoing', 'spare', 'coupler', 'power_quality')
        .all()
    )
    serializer_class = MFMSerializer

    @action(detail=True, methods=['get'], url_path='asset3d')
    def asset3d(self, request, pk=None):
        """Return the resolved 3D asset for this MFM (override -> type default)."""
        mfm = self.get_object()
        asset = mfm.resolve_asset_3d()
        if not asset:
            raise NotFound('No 3D asset bound to this MFM or its MFMType')
        return Response(Asset3DSerializer(asset, context={'request': request}).data)

    @action(detail=True, methods=['get'])
    def pages(self, request, pk=None):
        """Return the page list this MFM should render (per its MFMType)."""
        mfm = self.get_object()
        pages = pages_for_mfm(mfm, request=request)
        return Response({
            'mfm_id': mfm.id,
            'mfm_name': mfm.name,
            'mfm_type': mfm.mfm_type.code,
            'count': len(pages),
            'pages': pages,
        })

    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """Return the type-specific detail sections this MFM should render.

        Mirrors `pages` — sections come from `detail_registry._DETAILS` and
        are filtered by which dispatcher has a strategy for the MFM's type.
        Stub strategies (no `fields`) come back with `pending=True`.
        """
        mfm = self.get_object()
        sections = details_for_mfm(mfm)
        return Response({
            'mfm_id': mfm.id,
            'mfm_name': mfm.name,
            'mfm_type': mfm.mfm_type.code,
            'count': len(sections),
            'details': sections,
        })

    @action(detail=True, methods=['get'])
    def parameters(self, request, pk=None):
        mfm = self.get_object()
        params = mfm.mfm_type.parameters.all()
        return Response({
            'mfm_id': mfm.id,
            'mfm_type': mfm.mfm_type.code,
            'count': params.count(),
            'parameters': ParameterSerializer(params, many=True).data,
        })

    @action(detail=True, methods=['get'])
    def live(self, request, pk=None):
        mfm = self.get_object()
        if not mfm.panel_id:
            raise ParseError('MFM has no panel_id configured')
        try:
            row = fetch_live(mfm.db_link, mfm.table_name, mfm.panel_id)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        if row is None:
            raise NotFound('No data found for this MFM')

        params_by_col = {p.column_name: p for p in mfm.mfm_type.parameters.all()}
        enriched = []
        for col, val in row.items():
            p = params_by_col.get(col)
            enriched.append({
                'column': col,
                'value': val,
                'name': p.name if p else col,
                'unit': p.unit if p else '',
                'kind': p.kind if p else None,
                'spec': p.spec if p else '',
            })
        return Response({
            'mfm_id': mfm.id,
            'panel_id': mfm.panel_id,
            'ts': row.get('ts'),
            'data': enriched,
        })

    @action(detail=True, methods=['get'])
    def config(self, request, pk=None):
        """Return per-MFM static config row — thresholds, nameplate, ratings.

        Frontend uses this for chart reference lines (Max-V / Min-V / Max-A /
        Min-A bands), the Nominal V tile, PF Target, rated kVA, subsidy
        budgets, busbar / thermal limits, etc. Config is type-specific —
        served from `transformer_config` / `ups_config` / `lt_panel_config`
        / `ht_panel_config` / `apfc_config`.
        """
        mfm = self.get_object()
        if not mfm.panel_id:
            raise ParseError('MFM has no panel_id configured')

        table = _CONFIG_TABLE_BY_TYPE.get(mfm.mfm_type.code)
        if not table:
            return Response({
                'mfm_id': mfm.id, 'panel_id': mfm.panel_id,
                'mfm_type': mfm.mfm_type.code,
                'config': {},
                'note': f"No config table mapped for MFM type '{mfm.mfm_type.code}'",
            })

        try:
            row = fetch_config_row(mfm.db_link, table, mfm.panel_id)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'mfm_id': mfm.id,
            'panel_id': mfm.panel_id,
            'mfm_type': mfm.mfm_type.code,
            'config_table': table,
            'config': row or {},
        })

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        mfm = self.get_object()
        if not mfm.panel_id:
            raise ParseError('MFM has no panel_id configured')
        try:
            minutes = int(request.query_params.get('minutes', 60))
        except ValueError:
            raise ParseError('minutes must be an integer')
        cols_param = request.query_params.get('columns')
        valid_cols, rejected = _filter_columns_param(cols_param)
        if rejected:
            raise ParseError(
                f'invalid column names: {", ".join(rejected)} — '
                f'column identifiers must match {_VALID_COLUMN_NAME_RE.pattern}'
            )
        # `None` lets services use the default; an explicit (possibly empty)
        # list means "use exactly these".
        columns = valid_cols if cols_param else None
        try:
            rows = fetch_history(mfm.db_link, mfm.table_name, mfm.panel_id,
                                 minutes=minutes, columns=columns)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({
            'mfm_id': mfm.id,
            'panel_id': mfm.panel_id,
            'minutes': minutes,
            'count': len(rows),
            'rows': rows,
        })


# ─────────────────────────────────────────────────────────────────────────────
# 3D Asset catalog — `/api/asset3d/`
# ─────────────────────────────────────────────────────────────────────────────
# GLB models served from MEDIA_ROOT/3d/glb/. Frontend uses these in two ways:
#   • Per-MFM: GET /api/mfm/<id>/asset3d/  → resolved via override → type default
#   • Overview pages: GET /api/asset3d/<key>/  → frontend hard-codes the key
#
# Each MFM's resolved asset is also embedded inline as `asset_3d` on the MFM
# detail/list payload.

class Asset3DViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Asset3D.objects.all()
    serializer_class = Asset3DSerializer
    lookup_field = 'key'  # so /api/asset3d/pcc1a-v1/ works


# ─────────────────────────────────────────────────────────────────────────────
# Assets hierarchy — `/api/assets/`
# ─────────────────────────────────────────────────────────────────────────────
# Flat hierarchy of major asset categories (Transformers / DGs / UPS), used
# by the Assets page on the frontend. Same binding rules as `/api/ems/`:
# each leaf carries `mfm_id` when its `mfm_name` (or `label`) matches an
# MFM in the DB.

ASSETS_TREE = [
    {
        "id": "asset-trf", "label": "Transformers", "slug": "transformers",
        "children": [
            {"id": "asset-trf-main", "label": "Main Transformer 33KV-20MVA", "slug": "main-33kv-20mva"},
            {"id": "asset-trf-01",   "label": "Transformer-01", "slug": "trf-01", "mfm_name": "Transformer 1"},
            {"id": "asset-trf-02",   "label": "Transformer-02", "slug": "trf-02", "mfm_name": "Transformer 2"},
            {"id": "asset-trf-03",   "label": "Transformer-03", "slug": "trf-03", "mfm_name": "Transformer 3"},
            {"id": "asset-trf-04",   "label": "Transformer-04", "slug": "trf-04", "mfm_name": "Transformer 4"},
            {"id": "asset-trf-05",   "label": "Transformer-05", "slug": "trf-05", "mfm_name": "Transformer 5"},
            {"id": "asset-trf-06",   "label": "Transformer-06", "slug": "trf-06", "mfm_name": "Transformer 6"},
            {"id": "asset-trf-07",   "label": "Transformer-07", "slug": "trf-07", "mfm_name": "Transformer 7"},
            {"id": "asset-trf-08",   "label": "Transformer-08", "slug": "trf-08", "mfm_name": "Transformer 8"},
        ],
    },
    {
        "id": "asset-dg", "label": "Diesel Generators", "slug": "diesel-generators",
        "children": [
            {"id": "asset-dg-01", "label": "Diesel Generator-01", "slug": "dg-01"},
            {"id": "asset-dg-02", "label": "Diesel Generator-02", "slug": "dg-02"},
            {"id": "asset-dg-03", "label": "Diesel Generator-03", "slug": "dg-03"},
            {"id": "asset-dg-04", "label": "Diesel Generator-04", "slug": "dg-04"},
            {"id": "asset-dg-05", "label": "Diesel Generator-05", "slug": "dg-05"},
            {"id": "asset-dg-06", "label": "Diesel Generator-06", "slug": "dg-06"},
            {"id": "asset-dg-07", "label": "Diesel Generator-07", "slug": "dg-07"},
            {"id": "asset-dg-08", "label": "Diesel Generator-08", "slug": "dg-08"},
        ],
    },
    {
        "id": "asset-ups", "label": "UPS", "slug": "ups",
        "children": [
            {"id": "asset-ups-01", "label": "UPS-01", "slug": "ups-01", "mfm_name": "UPS-01 CL:600KVA"},
            {"id": "asset-ups-02", "label": "UPS-02", "slug": "ups-02", "mfm_name": "UPS-02 CL:600KVA"},
            {"id": "asset-ups-03", "label": "UPS-03", "slug": "ups-03", "mfm_name": "UPS-03 CL:600KVA"},
            {"id": "asset-ups-04", "label": "UPS-04", "slug": "ups-04", "mfm_name": "UPS-04 CL:600KVA"},
            {"id": "asset-ups-05", "label": "UPS-05", "slug": "ups-05", "mfm_name": "UPS-05 CL:600KVA"},
            {"id": "asset-ups-06", "label": "UPS-06", "slug": "ups-06", "mfm_name": "UPS-06 CL:600KVA"},
            {"id": "asset-ups-07", "label": "UPS-07", "slug": "ups-07", "mfm_name": "UPS-07 CL:600KVA"},
            {"id": "asset-ups-08", "label": "UPS-08", "slug": "ups-08", "mfm_name": "UPS-08 CL:600KVA"},
            {"id": "asset-ups-09", "label": "UPS-09", "slug": "ups-09", "mfm_name": "UPS-09 CL:600KVA"},
            {"id": "asset-ups-10", "label": "UPS-10", "slug": "ups-10", "mfm_name": "UPS-10 CL:600KVA"},
            {"id": "asset-ups-11", "label": "UPS-11", "slug": "ups-11", "mfm_name": "UPS-11 CL:600KVA"},
            {"id": "asset-ups-12", "label": "UPS-12", "slug": "ups-12", "mfm_name": "UPS-12 CL:600KVA"},
        ],
    },
]


@api_view(['GET'])
def assets(request):
    """Return the Assets hierarchy (Transformers / Diesel Generators / UPS).

    Leaves carry `mfm_id` where the explicit `mfm_name` (or label) matches
    an MFM in the DB. Same binding logic as `/api/ems/` — helpers are
    imported from `electrical_equipment.py`.
    """
    name_to_id = _build_name_to_mfm_id()
    tree = _attach_mfm_ids(ASSETS_TREE, name_to_id)
    return Response({
        'count': len(tree),
        'leaf_count': _count_leaves(tree),
        'matched_mfm_count': _count_matched(tree),
        'tree': tree,
    })


# ─────────────────────────────────────────────────────────────────────────────
# BMS hierarchy — `/api/bms/`
# ─────────────────────────────────────────────────────────────────────────────
# Building Management Systems navigation tree — PCW, Compressed Air, AHUs,
# Chillers, CSUs, etc. Sections without listed children are rendered as
# top-level leaves (clickable, no expand) so the frontend can route to a
# placeholder/landing page.

BMS_TREE = [
    # ── HVAC — parent of Chillers, AHU, CSU, Air Washer, Air Washer Exhaust ──
    {"id": "bms-hvac", "label": "HVAC", "slug": "hvac", "children": [
        {"id": "bms-hvac-overview", "label": "Overview", "slug": "overview"},

        {"id": "bms-hvac-chillers", "label": "Chillers", "slug": "chillers", "children": [
            {"id": "bms-hvac-chillers-overview", "label": "Overview", "slug": "overview"},
            {"id": "bms-hvac-chiller-1", "label": "Chiller-1", "slug": "chiller-1", "mfm_name": "Chiller & CHW, CWP-1"},
            {"id": "bms-hvac-chiller-2", "label": "Chiller-2", "slug": "chiller-2", "mfm_name": "Chiller & CHW, CWP-2"},
            {"id": "bms-hvac-chiller-3", "label": "Chiller-3", "slug": "chiller-3", "mfm_name": "Chiller & CHW, CWP-3"},
            {"id": "bms-hvac-chiller-4", "label": "Chiller-4", "slug": "chiller-4", "mfm_name": "Chiller & CHW, CWP-4"},
        ]},

        {"id": "bms-hvac-ahu", "label": "AHU", "slug": "ahu", "children": [
            {"id": "bms-hvac-ahu-overview", "label": "Overview", "slug": "overview"},
            *[{"id": f"bms-hvac-ahu-{i}", "label": f"AHU-{i}",
               "slug": f"ahu-{i}", "mfm_name": f"AHU-{i}"} for i in range(1, 12)],
        ]},

        {"id": "bms-hvac-csu", "label": "CSU", "slug": "csu", "children": [
            {"id": "bms-hvac-csu-overview", "label": "Overview", "slug": "overview"},
            {"id": "bms-hvac-csu-1", "label": "CSU-1", "slug": "csu-1", "mfm_name": "Curing Line CSU-01"},
            {"id": "bms-hvac-csu-2", "label": "CSU-2", "slug": "csu-2", "mfm_name": "Curing Line CSU-02"},
        ]},

        {"id": "bms-hvac-air-washer", "label": "Air Washer", "slug": "air-washer", "children": [
            {"id": "bms-hvac-aw-overview", "label": "Overview", "slug": "overview"},
            *[{"id": f"bms-hvac-aw-{i}", "label": f"Air Washer-{i}",
               "slug": f"air-washer-{i}", "mfm_name": f"Air Washer-{i}"} for i in range(1, 7)],
        ]},

        {"id": "bms-hvac-aw-exhaust", "label": "Air Washer Exhaust",
         "slug": "air-washer-exhaust", "children": [
            {"id": "bms-hvac-awx-overview", "label": "Overview", "slug": "overview"},
            *[{"id": f"bms-hvac-awx-{i}", "label": f"AW Exhaust-{i}",
               "slug": f"aw-exhaust-{i}",
               "mfm_name": f"Air Washer Exhaust-{i:02d}"} for i in range(1, 7)],
        ]},
    ]},

    # ── CDA — Compressed Dry Air (Air Compressor + Air Dryer subgroups) ─────
    {"id": "bms-cda", "label": "CDA", "slug": "cda", "children": [
        {"id": "bms-cda-overview", "label": "Overview", "slug": "overview"},

        {"id": "bms-cda-air-compressor", "label": "Air Compressor",
         "slug": "air-compressor", "children": [
            *[{"id": f"bms-cda-ac-{i}", "label": f"Air Compressor-{i}",
               "slug": f"air-compressor-{i}",
               "mfm_name": f"Air Compressor-{i:02d}"} for i in range(1, 4)],
        ]},

        {"id": "bms-cda-air-dryer", "label": "Air Dryer",
         "slug": "air-dryer", "children": [
            *[{"id": f"bms-cda-ad-{i}", "label": f"Air Dryer-{i}",
               "slug": f"air-dryer-{i}",
               "mfm_name": f"Air Dryer-{i:02d}"} for i in range(1, 4)],
        ]},
    ]},

    # ── PCW — group (Overview + Vaccum Degasser + Pressurization) ───────────
    {"id": "bms-pcw", "label": "PCW", "slug": "pcw", "children": [
        {"id": "bms-pcw-overview", "label": "Overview", "slug": "overview"},
        {"id": "bms-pcw-vaccum-degasser", "label": "Vaccum Degasser Unit",
         "slug": "vaccum-degasser-unit", "mfm_name": "Vaccum Degasser Unit"},
        {"id": "bms-pcw-pressurization", "label": "Pressurization Unit",
         "slug": "pressurization-unit",  "mfm_name": "Pressurization Unit"},
    ]},

    # ── Top-level leaf ──────────────────────────────────────────────────────
    {"id": "bms-gae", "label": "General Air Exhaust Unit",
     "slug": "general-air-exhaust", "mfm_name": "General Exhaust"},
]


@api_view(['GET'])
def bms(request):
    """Return the BMS (Building Management Systems) hierarchy.

    Same binding logic as `/api/ems/` and `/api/assets/`. Empty top-level
    sections (no `children` key) come back as leaves — the frontend can
    route them to a placeholder page.
    """
    name_to_id = _build_name_to_mfm_id()
    tree = _attach_mfm_ids(BMS_TREE, name_to_id)
    return Response({
        'count': len(tree),
        'leaf_count': _count_leaves(tree),
        'matched_mfm_count': _count_matched(tree),
        'tree': tree,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Overview-page bootstrap — `/api/overview/<slug>/`
# ─────────────────────────────────────────────────────────────────────────────
# Hard-coded slug → MFM-name + 3D-asset-key map. The frontend hard-codes
# the slug per overview page (e.g. /electrical/pcc-panels/panel-1a) and
# calls this endpoint to fetch the 3D model + topology bootstrap. Live KPIs
# still come from the per-MFM endpoints (or the WS overview consumer).
#
# To add a new overview page: append a dict to `_OVERVIEW_PAGES` with the
# MFM name (exact match against MFM.name) and the Asset3D key.

_OVERVIEW_PAGES = {
    'pcc-panel-1a': {'name': 'PCC Panel 1 A', 'mfm_name': 'PCC Panel 1 A', 'asset_3d_key': 'pcc1a-v1'},
    # Add more entries here as GLBs are uploaded for each panel half (1B, 2A/B, 3A/B, ...).
}


def _mfm_ref(m):
    """Mini-dict for an MFM connection, matching the inline shape on MFMSerializer."""
    return {'id': m.id, 'name': m.name, 'panel_id': m.panel_id, 'mfm_type': m.mfm_type.code}


@api_view(['GET'])
def overview_pages(request):
    """List every overview-page slug with its MFM id (if resolvable) and asset key."""
    name_to_id = _build_name_to_mfm_id()
    pages = []
    for slug, cfg in _OVERVIEW_PAGES.items():
        pages.append({
            'slug': slug,
            'name': cfg['name'],
            'mfm_id': name_to_id.get(cfg['mfm_name'].strip().lower()),
            'asset_3d_key': cfg['asset_3d_key'],
        })
    return Response({'count': len(pages), 'pages': pages})


@api_view(['GET'])
def overview_page(request, slug):
    """Bootstrap payload for one overview page.

    Returns the panel's MFM (with topology) and its resolved 3D asset.
    The `asset_3d` here is resolved by the hard-coded `asset_3d_key` —
    NOT by the MFM-binding resolver — so overview pages stay independent
    of any per-MFM override the admin might set for other UI surfaces.
    """
    from .models import MFM as _MFM, Asset3D as _Asset3D
    cfg = _OVERVIEW_PAGES.get(slug)
    if not cfg:
        raise NotFound(f'Unknown overview slug "{slug}". Known: {sorted(_OVERVIEW_PAGES)}')

    mfm = (
        _MFM.objects
        .select_related('mfm_type')
        .prefetch_related('incoming__mfm_type', 'outgoing__mfm_type',
                          'spare__mfm_type', 'coupler__mfm_type',
                          'power_quality__mfm_type')
        .filter(name=cfg['mfm_name'])
        .first()
    )
    if not mfm:
        raise NotFound(f'No MFM named "{cfg["mfm_name"]}"')

    asset = _Asset3D.objects.filter(key=cfg['asset_3d_key']).first()
    asset_payload = Asset3DSerializer(asset, context={'request': request}).data if asset else None

    return Response({
        'slug':  slug,
        'name':  cfg['name'],
        'mfm':   {'id': mfm.id, 'name': mfm.name, 'panel_id': mfm.panel_id,
                  'mfm_type': mfm.mfm_type.code, 'table_name': mfm.table_name},
        'asset_3d': asset_payload,
        'incoming': [_mfm_ref(m) for m in mfm.incoming.all()],
        'outgoing': [_mfm_ref(m) for m in mfm.outgoing.all()],
        'spare':    [_mfm_ref(m) for m in mfm.spare.all()],
        'coupler':  [_mfm_ref(m) for m in mfm.coupler.all()],
        'power_quality': [_mfm_ref(m) for m in mfm.power_quality.all()],
    })
