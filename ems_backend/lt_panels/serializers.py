from rest_framework import serializers
from .models import MFMType, MFM, Parameter, Asset3D


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = ['id', 'name', 'column_name', 'kind', 'unit', 'spec', 'description']


class Asset3DSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Asset3D
        fields = ['id', 'key', 'name', 'category', 'url', 'description']

    def get_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        rel = obj.file.url  # /media/3d/glb/<filename>
        return request.build_absolute_uri(rel) if request else rel


class MFMTypeSerializer(serializers.ModelSerializer):
    parameters = ParameterSerializer(many=True, read_only=True)
    default_asset_3d = Asset3DSerializer(read_only=True)

    class Meta:
        model = MFMType
        fields = ['id', 'code', 'name', 'description', 'default_asset_3d', 'parameters']


class _MFMRefSerializer(serializers.ModelSerializer):
    """Nested mini-object for incoming/outgoing/spare connections."""
    mfm_type = serializers.CharField(source='mfm_type.code', read_only=True)

    class Meta:
        model = MFM
        fields = ['id', 'name', 'panel_id', 'mfm_type']


class MFMSerializer(serializers.ModelSerializer):
    mfm_type = MFMTypeSerializer(read_only=True)
    incoming = _MFMRefSerializer(many=True, read_only=True)
    outgoing = _MFMRefSerializer(many=True, read_only=True)
    spare    = _MFMRefSerializer(many=True, read_only=True)
    coupler  = _MFMRefSerializer(many=True, read_only=True)
    power_quality = _MFMRefSerializer(many=True, read_only=True)
    asset_3d = serializers.SerializerMethodField()

    class Meta:
        model = MFM
        fields = [
            'id', 'name', 'mfm_type', 'db_link', 'table_name', 'panel_id',
            'incoming', 'outgoing', 'spare', 'coupler', 'power_quality', 'asset_3d',
        ]

    def get_asset_3d(self, obj):
        asset = obj.resolve_asset_3d()
        if not asset:
            return None
        return Asset3DSerializer(asset, context=self.context).data
