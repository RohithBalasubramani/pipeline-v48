from django.db import models

from .data_db_link import default_db_link


class Asset3D(models.Model):
    """Catalog of GLB models served from MEDIA_ROOT/3d/glb/.

    Multiple MFMs (and any number of overview pages) bind to one row.
    Lookups go by stable `key` (slug) so the frontend can hard-code
    overview-page references without depending on FK ids.
    """
    CATEGORY_CHOICES = [
        ('lt_panel',    'LT Panel'),
        ('ht_panel',    'HT Panel'),
        ('ups',         'UPS'),
        ('transformer', 'Transformer'),
        ('apfc',        'APFC'),
        ('dg',          'Diesel Generator'),
        ('overview',    'Overview / Other'),
    ]

    key      = models.SlugField(max_length=64, unique=True,
                                help_text='Stable identifier, e.g. "pcc1a-v1". Used by frontend to fetch by key.')
    name     = models.CharField(max_length=100)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default='lt_panel')
    file     = models.FileField(upload_to='3d/glb/', help_text='GLB file uploaded via admin')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lt_asset_3d'
        verbose_name = '3D Asset'
        verbose_name_plural = '3D Assets'
        ordering = ['category', 'key']

    def __str__(self):
        return f'{self.name} ({self.key})'


class MFMType(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default='')
    default_asset_3d = models.ForeignKey(
        Asset3D, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='default_for_types',
        help_text='3D model shown for any MFM of this type unless overridden on the MFM itself.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lt_mfm_type'
        verbose_name = 'MFM Type'
        verbose_name_plural = 'MFM Types'

    def __str__(self):
        return f'{self.name} ({self.code})'


class MFM(models.Model):
    name = models.CharField(max_length=100)
    mfm_type = models.ForeignKey(MFMType, on_delete=models.PROTECT, related_name='mfms')
    db_link = models.CharField(
        max_length=255,
        default=default_db_link,                                  # target_version1/compat (env-driven); NOT the old lt_panels DB
        help_text='libpq connection string used to fetch the time-series DATA (target_version1, schema compat)',
    )
    table_name = models.CharField(
        max_length=100,
        default='panel_readings',
        help_text='Timeseries table name, e.g. panel_readings',
    )
    panel_id = models.CharField(
        max_length=100, blank=True, default='', db_index=True,
        help_text='Filter value for panel_id column in the timeseries table',
    )
    load_group = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Logical load category this MFM rolls up into on the PCC Panel '
                  'energy-distribution Sankey (e.g. "UPS backed loads", '
                  '"Lamination heaters"). Static metadata, not from the timeseries.',
    )

    incoming = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')
    outgoing = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')
    spare    = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')
    coupler  = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')
    # Power-quality / reactive-compensation equipment attached to this panel
    # (HHF filters, APFC banks). NOT load feeders — deliberately separate from
    # `outgoing` so they stay out of feeder fan-outs / event & energy totals.
    power_quality = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')

    asset_3d_override = models.ForeignKey(
        Asset3D, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='override_for_mfms',
        help_text='Per-MFM override; if unset, falls back to mfm_type.default_asset_3d.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lt_mfm'
        verbose_name = 'MFM'
        verbose_name_plural = 'MFMs'

    def __str__(self):
        return self.name

    def resolve_asset_3d(self):
        """Override → MFMType default. Returns Asset3D or None."""
        if self.asset_3d_override_id:
            return self.asset_3d_override
        return self.mfm_type.default_asset_3d

    def get_config(self, key, default=None):
        """Resolve a static-config value for this MFM, typed per its field.

        Resolution order: per-MFM ConfigValue → field's default_value →
        the ``default`` arg. Returns the value cast to the field's data_type
        (number/bool/text). Used to replace hardcoded NAMEPLATE constants.
        """
        field = ConfigField.objects.filter(mfm_type_id=self.mfm_type_id, key=key).first()
        if field is None:
            return default
        cv = ConfigValue.objects.filter(mfm_id=self.id, field_id=field.id).first()
        if cv is not None and cv.value != '':
            return field.cast(cv.value)
        if field.default_value != '':
            return field.cast(field.default_value)
        return default


class Parameter(models.Model):
    KIND_CHOICES = [
        ('measured', 'Measured'),
        ('derived', 'Derived'),
    ]

    mfm_type = models.ForeignKey(MFMType, on_delete=models.CASCADE, related_name='parameters')
    name = models.CharField(max_length=100, help_text='Display name, e.g. "Active Power Total"')
    column_name = models.CharField(
        max_length=100, db_index=True,
        help_text='Exact column in the timeseries table, e.g. active_power_total_kw',
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='measured')
    unit = models.CharField(max_length=20, blank=True, default='')
    spec = models.CharField(max_length=20, blank=True, default='', help_text='Spec reference, e.g. M5, PQ1, 1.1, 8.5')
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lt_parameter'
        verbose_name = 'Parameter'
        verbose_name_plural = 'Parameters'
        unique_together = [('mfm_type', 'column_name')]

    def __str__(self):
        return f'{self.mfm_type.code}.{self.column_name}'


# ─────────────────────────────────────────────────────────────────────────────
# Static per-MFM config — EAV (entity-attribute-value) store
# ─────────────────────────────────────────────────────────────────────────────
# Two tables that together replace the hardcoded NAMEPLATE / threshold dicts
# scattered through the consumers:
#
#   ConfigField  — the "fields" table. Defines WHICH config attributes exist
#                  for each MFM *type* (e.g. transformer → nominal_voltage_v,
#                  rated_kva; ups → backup_time_min). One row per (type, key).
#   ConfigValue  — the "values" table. The concrete value of a field for a
#                  specific MFM. One row per (mfm, field).
#
# This is STATIC config (nameplate, thresholds, contract limits) — NOT the
# per-second timeseries data, which stays in the external mfm_* tables and is
# described by the separate `Parameter` model.

class ConfigField(models.Model):
    """A static-config field definition, scoped to an MFM type."""
    DATA_TYPES = [
        ('number', 'Number'),
        ('text',   'Text'),
        ('bool',   'Boolean'),
    ]

    mfm_type = models.ForeignKey(MFMType, on_delete=models.CASCADE,
                                 related_name='config_fields')
    key = models.CharField(
        max_length=100,
        help_text='Machine name, e.g. "rated_kva", "nominal_voltage_v".',
    )
    label = models.CharField(max_length=120, help_text='Display name, e.g. "Rated Capacity".')
    # 2-level hierarchy for the nameplate / config UI: fields are grouped
    # under a section header (e.g. "Rating & Identity", "Source & Metering").
    section = models.CharField(
        max_length=80, blank=True, default='General',
        help_text='Group header this field renders under, e.g. "Rating & Identity".',
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text='Sort order within the section (sections sort by their min order).',
    )
    data_type = models.CharField(max_length=10, choices=DATA_TYPES, default='number')
    unit = models.CharField(max_length=20, blank=True, default='',
                            help_text='e.g. "kVA", "V", "MVAh".')
    default_value = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Fallback used when an MFM has no ConfigValue for this field.',
    )
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lt_config_field'
        verbose_name = 'Config field'
        verbose_name_plural = 'Config fields'
        unique_together = [('mfm_type', 'key')]
        ordering = ['mfm_type', 'display_order', 'key']

    def __str__(self):
        return f'{self.mfm_type.code}.{self.key}'

    @staticmethod
    def _cast(raw: str, data_type: str):
        """Cast a stored string value to its declared type. Returns None on
        empty/uncastable input so callers can fall back cleanly."""
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


class ConfigValue(models.Model):
    """The value of one ConfigField for one specific MFM."""
    mfm = models.ForeignKey(MFM, on_delete=models.CASCADE, related_name='config_values')
    field = models.ForeignKey(ConfigField, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Stored as text; cast per field.data_type on read.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lt_config_value'
        verbose_name = 'Config value'
        verbose_name_plural = 'Config values'
        unique_together = [('mfm', 'field')]

    def __str__(self):
        return f'{self.mfm.name} · {self.field.key} = {self.value}'

    @property
    def typed_value(self):
        return self.field.cast(self.value)
