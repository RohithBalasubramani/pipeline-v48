"""REST endpoints for the `assets` app.

Mirrors `lt_panels.views.MFMViewSet` → `AssetViewSet` (read-only + live /
history / pages / parameters / asset3d actions), plus a 3D-model catalog
viewset. Domain trees (sidebar hierarchies) are intentionally left out of
the skeleton — add them the same way lt_panels does once the asset
navigation is specced.
"""
import re

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ParseError

from .models import Asset, Asset3DModel
from .serializers import AssetSerializer, AssetParameterSerializer, Asset3DModelSerializer
from .services import fetch_live, fetch_history
from .page_registry import pages_for_asset


_VALID_COLUMN_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,62}$')


def _filter_columns_param(cols_param):
    if not cols_param:
        return [], []
    requested = [c.strip() for c in cols_param.split(',') if c.strip()]
    valid    = [c for c in requested if _VALID_COLUMN_NAME_RE.match(c)]
    rejected = [c for c in requested if not _VALID_COLUMN_NAME_RE.match(c)]
    return valid, rejected


class AssetViewSet(viewsets.ReadOnlyModelViewSet):
    """List Assets and serve live / historical readings from each db_link."""

    queryset = (
        Asset.objects
        .select_related('asset_type', 'asset_type__default_asset_3d', 'asset_3d_override')
        .prefetch_related('asset_type__parameters', 'incoming', 'outgoing', 'spare', 'coupler')
        .all()
    )
    serializer_class = AssetSerializer

    @action(detail=True, methods=['get'], url_path='asset3d')
    def asset3d(self, request, pk=None):
        """Return the resolved 3D model for this Asset (override → type default)."""
        asset = self.get_object()
        model = asset.resolve_asset_3d()
        if not model:
            raise NotFound('No 3D model bound to this Asset or its AssetType')
        return Response(Asset3DModelSerializer(model, context={'request': request}).data)

    @action(detail=True, methods=['get'])
    def pages(self, request, pk=None):
        """Return the page list this Asset should render (per its AssetType)."""
        asset = self.get_object()
        pages = pages_for_asset(asset, request=request)
        return Response({
            'asset_id': asset.id,
            'asset_name': asset.name,
            'asset_type': asset.asset_type.code,
            'count': len(pages),
            'pages': pages,
        })

    @action(detail=True, methods=['get'])
    def parameters(self, request, pk=None):
        asset = self.get_object()
        params = asset.asset_type.parameters.all()
        return Response({
            'asset_id': asset.id,
            'asset_type': asset.asset_type.code,
            'count': params.count(),
            'parameters': AssetParameterSerializer(params, many=True).data,
        })

    @action(detail=True, methods=['get'])
    def live(self, request, pk=None):
        asset = self.get_object()
        if not asset.asset_id:
            raise ParseError('Asset has no asset_id configured')
        try:
            row = fetch_live(asset.db_link, asset.table_name, asset.asset_id)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        if row is None:
            raise NotFound('No data found for this Asset')

        params_by_col = {p.column_name: p for p in asset.asset_type.parameters.all()}
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
            'asset_id': asset.id,
            'asset_key': asset.asset_id,
            'ts': row.get('ts'),
            'data': enriched,
        })

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        asset = self.get_object()
        if not asset.asset_id:
            raise ParseError('Asset has no asset_id configured')
        try:
            minutes = int(request.query_params.get('minutes', 60))
        except ValueError:
            raise ParseError('minutes must be an integer')
        cols_param = request.query_params.get('columns')
        valid_cols, rejected = _filter_columns_param(cols_param)
        if rejected:
            raise ParseError(
                f'invalid column names: {", ".join(rejected)} — '
                f'identifiers must match {_VALID_COLUMN_NAME_RE.pattern}'
            )
        columns = valid_cols if cols_param else None
        try:
            rows = fetch_history(asset.db_link, asset.table_name, asset.asset_id,
                                 minutes=minutes, columns=columns)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({
            'asset_id': asset.id,
            'asset_key': asset.asset_id,
            'minutes': minutes,
            'count': len(rows),
            'rows': rows,
        })


class Asset3DModelViewSet(viewsets.ReadOnlyModelViewSet):
    """GLB 3D-model catalog. Looked up by stable `key` (e.g. /api/asset-3d/chiller-01-v1/)."""
    queryset = Asset3DModel.objects.all()
    serializer_class = Asset3DModelSerializer
    lookup_field = 'key'
