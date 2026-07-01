from django.contrib import admin

from .models import MFMType, MFM, Parameter, Asset3D, ConfigField, ConfigValue


@admin.register(Asset3D)
class Asset3DAdmin(admin.ModelAdmin):
    list_display  = ('key', 'name', 'category', 'file', 'updated_at')
    list_filter   = ('category',)
    search_fields = ('key', 'name', 'description')
    prepopulated_fields = {'key': ('name',)}


class ParameterInline(admin.TabularInline):
    model  = Parameter
    extra  = 0
    fields = ('name', 'column_name', 'kind', 'unit', 'spec')


class ConfigFieldInline(admin.TabularInline):
    model  = ConfigField
    extra  = 0
    fields = ('section', 'display_order', 'key', 'label', 'data_type', 'unit', 'default_value')
    ordering = ('section', 'display_order')


class ConfigValueInline(admin.TabularInline):
    model  = ConfigValue
    extra  = 0
    fields = ('field', 'value')
    autocomplete_fields = ('field',)


@admin.register(MFMType)
class MFMTypeAdmin(admin.ModelAdmin):
    list_display  = ('code', 'name', 'default_asset_3d')
    list_filter   = ('default_asset_3d',)
    search_fields = ('code', 'name')
    autocomplete_fields = ('default_asset_3d',)
    inlines = (ParameterInline, ConfigFieldInline)


@admin.register(MFM)
class MFMAdmin(admin.ModelAdmin):
    list_display  = ('name', 'mfm_type', 'panel_id', 'table_name', 'asset_3d_override')
    list_filter   = ('mfm_type', 'asset_3d_override')
    search_fields = ('name', 'panel_id', 'table_name')
    autocomplete_fields = ('mfm_type', 'asset_3d_override', 'incoming', 'outgoing', 'spare', 'coupler', 'power_quality')
    inlines = (ConfigValueInline,)


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display  = ('column_name', 'mfm_type', 'name', 'kind', 'unit', 'spec')
    list_filter   = ('mfm_type', 'kind')
    search_fields = ('column_name', 'name')


@admin.register(ConfigField)
class ConfigFieldAdmin(admin.ModelAdmin):
    list_display  = ('key', 'mfm_type', 'section', 'display_order', 'label', 'data_type', 'unit', 'default_value')
    list_filter   = ('mfm_type', 'section', 'data_type')
    search_fields = ('key', 'label', 'section')
    ordering      = ('mfm_type', 'section', 'display_order')


@admin.register(ConfigValue)
class ConfigValueAdmin(admin.ModelAdmin):
    list_display  = ('mfm', 'field', 'value')
    list_filter   = ('field__mfm_type', 'field')
    search_fields = ('mfm__name', 'field__key', 'value')
    autocomplete_fields = ('mfm', 'field')
