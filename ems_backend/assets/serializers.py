from rest_framework import serializers
from .models import AssetType, Asset, AssetParameter, Asset3DModel


class AssetParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetParameter
        fields = ['id', 'name', 'column_name', 'kind', 'unit', 'spec', 'description']


class Asset3DModelSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Asset3DModel
        fields = ['id', 'key', 'name', 'category', 'url', 'description']

    def get_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        rel = obj.file.url
        return request.build_absolute_uri(rel) if request else rel


class AssetTypeSerializer(serializers.ModelSerializer):
    parameters = AssetParameterSerializer(many=True, read_only=True)
    default_asset_3d = Asset3DModelSerializer(read_only=True)

    class Meta:
        model = AssetType
        fields = ['id', 'code', 'name', 'description', 'default_asset_3d', 'parameters']


class _AssetRefSerializer(serializers.ModelSerializer):
    """Nested mini-object for incoming/outgoing/spare/coupler connections."""
    asset_type = serializers.CharField(source='asset_type.code', read_only=True)

    class Meta:
        model = Asset
        fields = ['id', 'name', 'asset_id', 'asset_type']


class AssetSerializer(serializers.ModelSerializer):
    asset_type = AssetTypeSerializer(read_only=True)
    incoming = _AssetRefSerializer(many=True, read_only=True)
    outgoing = _AssetRefSerializer(many=True, read_only=True)
    spare    = _AssetRefSerializer(many=True, read_only=True)
    coupler  = _AssetRefSerializer(many=True, read_only=True)
    asset_3d = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'asset_type', 'db_link', 'table_name', 'asset_id',
            'group', 'incoming', 'outgoing', 'spare', 'coupler', 'asset_3d',
        ]

    def get_asset_3d(self, obj):
        asset = obj.resolve_asset_3d()
        if not asset:
            return None
        return Asset3DModelSerializer(asset, context=self.context).data
