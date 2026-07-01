from django.contrib import admin

from .models import (
    AssetType, Asset, AssetParameter, Asset3DModel,
    AssetConfigField, AssetConfigValue,
)


@admin.register(Asset3DModel)
class Asset3DModelAdmin(admin.ModelAdmin):
    list_display  = ('key', 'name', 'category', 'file', 'updated_at')
    list_filter   = ('category',)
    search_fields = ('key', 'name', 'description')
    prepopulated_fields = {'key': ('name',)}


class AssetParameterInline(admin.TabularInline):
    model  = AssetParameter
    extra  = 0
    fields = ('name', 'column_name', 'kind', 'unit', 'spec')


class AssetConfigFieldInline(admin.TabularInline):
    model  = AssetConfigField
    extra  = 0
    fields = ('section', 'display_order', 'key', 'label', 'data_type', 'unit', 'default_value')
    ordering = ('section', 'display_order')


class AssetConfigValueInline(admin.TabularInline):
    model  = AssetConfigValue
    extra  = 0
    fields = ('field', 'value')
    autocomplete_fields = ('field',)


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display  = ('code', 'name', 'default_asset_3d')
    list_filter   = ('default_asset_3d',)
    search_fields = ('code', 'name')
    autocomplete_fields = ('default_asset_3d',)
    inlines = (AssetParameterInline, AssetConfigFieldInline)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display  = ('name', 'asset_type', 'asset_id', 'table_name', 'asset_3d_override')
    list_filter   = ('asset_type', 'asset_3d_override')
    search_fields = ('name', 'asset_id', 'table_name')
    autocomplete_fields = ('asset_type', 'asset_3d_override', 'incoming', 'outgoing', 'spare', 'coupler')
    inlines = (AssetConfigValueInline,)


@admin.register(AssetParameter)
class AssetParameterAdmin(admin.ModelAdmin):
    list_display  = ('column_name', 'asset_type', 'name', 'kind', 'unit', 'spec')
    list_filter   = ('asset_type', 'kind')
    search_fields = ('column_name', 'name')


@admin.register(AssetConfigField)
class AssetConfigFieldAdmin(admin.ModelAdmin):
    list_display  = ('key', 'asset_type', 'section', 'display_order', 'label', 'data_type', 'unit', 'default_value')
    list_filter   = ('asset_type', 'section', 'data_type')
    search_fields = ('key', 'label', 'section')
    ordering      = ('asset_type', 'section', 'display_order')


@admin.register(AssetConfigValue)
class AssetConfigValueAdmin(admin.ModelAdmin):
    list_display  = ('asset', 'field', 'value')
    list_filter   = ('field__asset_type', 'field')
    search_fields = ('asset__name', 'field__key', 'value')
    autocomplete_fields = ('asset', 'field')
