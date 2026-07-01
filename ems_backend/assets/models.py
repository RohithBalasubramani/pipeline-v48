"""Registry models for the `assets` app (Django default DB).

Mirrors the `lt_panels` app one-to-one, with MFM → Asset renaming:

    Asset3DModel (asset_3d_model)     GLB 3D-model catalog, looked up by `key`
       ▲ default_asset_3d
    AssetType (asset_type)            equipment categories (lt_transformer,
                                      ht_transformer, dg, ups)
       ▲ asset_type
    Asset (asset)                     every metered asset; db_link/table_name/
                                      asset_id + topology M2M ×4
    AssetParameter (asset_parameter)  timeseries-COLUMN defs per type
    AssetConfigField (asset_config_field)  static CONFIG field defs per type
    AssetConfigValue (asset_config_value)  static config VALUE per asset

Same principle as lt_panels: **type-defines-shape, entity-holds-data**.
The external timeseries readings live in per-asset tables in the same
PostgreSQL DB and are read (never written) through `services.py`.
"""
from django.db import models

from lt_panels.data_db_link import default_db_link


class Asset3DModel(models.Model):
    """Catalog of GLB models served from MEDIA_ROOT/3d/glb/.

    Parallel to lt_panels.Asset3D but kept independent so the two apps stay
    decoupled. Multiple Assets bind to one row; lookups go by stable `key`.
    """
    CATEGORY_CHOICES = [
        ('lt_transformer', 'LT Transformer'),
        ('ht_transformer', 'HT Transformer'),
        ('dg',             'Diesel Generator'),
        ('ups',            'UPS'),
        ('overview',       'Overview / Other'),
    ]

    key      = models.SlugField(max_length=64, unique=True,
                                help_text='Stable identifier, e.g. "ups-01-v1". Used by frontend to fetch by key.')
    name     = models.CharField(max_length=100)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default='ups')
    file     = models.FileField(upload_to='3d/glb/', help_text='GLB file uploaded via admin')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_3d_model'
        verbose_name = 'Asset 3D model'
        verbose_name_plural = 'Asset 3D models'
        ordering = ['category', 'key']

    def __str__(self):
        return f'{self.name} ({self.key})'


class AssetType(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    default_asset_3d = models.ForeignKey(
        Asset3DModel, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='default_for_types',
        help_text='3D model shown for any Asset of this type unless overridden on the Asset itself.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_type'
        verbose_name = 'Asset Type'
        verbose_name_plural = 'Asset Types'

    def __str__(self):
        return f'{self.name} ({self.code})'


class Asset(models.Model):
    name = models.CharField(max_length=100)
    asset_type = models.ForeignKey(AssetType, on_delete=models.PROTECT, related_name='assets')
    db_link = models.CharField(
        max_length=255,
        default=default_db_link,                                  # target_version1/compat (env-driven); NOT the old lt_panels DB
        help_text='libpq connection string used to fetch timeseries values (target_version1, schema compat).',
    )
    table_name = models.CharField(
        max_length=100,
        default='asset_readings',
        help_text='Timeseries table name in the external DB, e.g. asset_ups_01.',
    )
    asset_id = models.CharField(
        max_length=100, blank=True, default='', db_index=True,
        help_text="Filter value for the timeseries table's panel_id column, "
                  "e.g. 'MFM-UPS-047'.",
    )
    group = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Logical grouping this asset rolls up into on fan-out/overview '
                  'pages (e.g. "Power Backup", "HT Yard"). Static metadata.',
    )

    incoming = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')
    outgoing = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')
    spare    = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')
    coupler  = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')

    asset_3d_override = models.ForeignKey(
        Asset3DModel, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='override_for_assets',
        help_text='Per-Asset override; if unset, falls back to asset_type.default_asset_3d.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset'
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'

    def __str__(self):
        return self.name

    def resolve_asset_3d(self):
        """Override → AssetType default. Returns Asset3DModel or None."""
        if self.asset_3d_override_id:
            return self.asset_3d_override
        return self.asset_type.default_asset_3d

    def get_config(self, key, default=None):
        """Resolve a static-config value for this Asset, typed per its field.

        Resolution order: per-Asset AssetConfigValue → field's default_value →
        the ``default`` arg. Returns the value cast to the field's data_type.
        """
        field = AssetConfigField.objects.filter(asset_type_id=self.asset_type_id, key=key).first()
        if field is None:
            return default
        cv = AssetConfigValue.objects.filter(asset_id=self.id, field_id=field.id).first()
        if cv is not None and cv.value != '':
            return field.cast(cv.value)
        if field.default_value != '':
            return field.cast(field.default_value)
        return default


class AssetParameter(models.Model):
    KIND_CHOICES = [
        ('measured', 'Measured'),
        ('derived', 'Derived'),
    ]

    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE, related_name='parameters')
    name = models.CharField(max_length=100, help_text='Display name, e.g. "Battery State of Charge"')
    column_name = models.CharField(
        max_length=100, db_index=True,
        help_text='Exact column in the timeseries table, e.g. battery_soc_pct',
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='measured')
    unit = models.CharField(max_length=20, blank=True, default='')
    spec = models.CharField(max_length=20, blank=True, default='', help_text='Spec reference')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_parameter'
        verbose_name = 'Asset Parameter'
        verbose_name_plural = 'Asset Parameters'
        unique_together = [('asset_type', 'column_name')]

    def __str__(self):
        return f'{self.asset_type.code}.{self.column_name}'


# ─────────────────────────────────────────────────────────────────────────────
# Static per-Asset config — EAV (entity-attribute-value) store
# ─────────────────────────────────────────────────────────────────────────────
# Same two-table pattern as lt_panels (ConfigField/ConfigValue):
#   AssetConfigField — WHICH static attributes a given Asset *type* exposes.
#   AssetConfigValue — the concrete value of a field for a specific Asset.
# STATIC config only (nameplate, thresholds, ratings) — never timeseries.

class AssetConfigField(models.Model):
    """A static-config field definition, scoped to an Asset type."""
    DATA_TYPES = [
        ('number', 'Number'),
        ('text',   'Text'),
        ('bool',   'Boolean'),
    ]

    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE,
                                   related_name='config_fields')
    key = models.CharField(max_length=100, help_text='Machine name, e.g. "rated_kva".')
    label = models.CharField(max_length=120, help_text='Display name, e.g. "Rated Capacity".')
    section = models.CharField(
        max_length=80, blank=True, default='General',
        help_text='Group header this field renders under.',
    )
    display_order = models.PositiveIntegerField(default=0)
    data_type = models.CharField(max_length=10, choices=DATA_TYPES, default='number')
    unit = models.CharField(max_length=20, blank=True, default='')
    default_value = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Fallback used when an Asset has no AssetConfigValue for this field.',
    )
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_config_field'
        verbose_name = 'Asset config field'
        verbose_name_plural = 'Asset config fields'
        unique_together = [('asset_type', 'key')]
        ordering = ['asset_type', 'display_order', 'key']

    def __str__(self):
        return f'{self.asset_type.code}.{self.key}'

    @staticmethod
    def _cast(raw: str, data_type: str):
        if raw is None or raw == '':
            return None
        if data_type == 'number':
            try:
                f = float(raw)
                return int(f) if f.is_integer() else f
            except (TypeError, ValueError):
                return None
        if data_type == 'bool':
            return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')
        return raw  # text

    def cast(self, raw: str):
        return self._cast(raw, self.data_type)


class AssetConfigValue(models.Model):
    """The value of one AssetConfigField for one specific Asset."""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='config_values')
    field = models.ForeignKey(AssetConfigField, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Stored as text; cast per field.data_type on read.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_config_value'
        verbose_name = 'Asset config value'
        verbose_name_plural = 'Asset config values'
        unique_together = [('asset', 'field')]

    def __str__(self):
        return f'{self.asset.name} · {self.field.key} = {self.value}'

    @property
    def typed_value(self):
        return self.field.cast(self.value)
