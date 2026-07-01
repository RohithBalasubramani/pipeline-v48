"""seed_config — populate neuract.lt_config_field (the per-MFM-type static-config field defs) so the ems_backend
get_config() layer is REPRODUCIBLE, not admin-entered-into-the-live-DB-only.

THE gap this closes: migrations 0009/0010 create lt_config_field + lt_config_value as EMPTY tables, and NO other seed
command / fixture / data-migration ever created a row. So a DB rebuilt from migrations+seeds came up with ZERO config
fields → every consumer's get_config(key, default) silently degraded to its hardcoded code default. This command makes
the 14 keys the consumers read a reproducible ConfigField per (mfm_type, key), sourcing each field's default_value from
the SAME literal the code falls back to (so behavior is identical, but now DB-editable + rebuildable).

Scope: all 14 keys live on the 'lt_panel' MFM type (the PCC panels: PCC Panel 1..4). It seeds FIELD DEFINITIONS +
DEFAULTS only — NOT per-MFM ConfigValue overrides (those are real site data an admin sets per panel). The two
energy-distribution rated-load keys are read with NO code default (→ None), so their field default is left BLANK on
purpose: honest None until a human seeds the real per-panel rating. NO fabricated denominator. [make config DB-driven]

  python manage.py seed_config          # upsert every ConfigField + print the per-section breakdown
"""
from django.core.management.base import BaseCommand

from lt_panels.data_db_link import default_db_link   # noqa: F401 — bootstraps pipeline_v48 onto sys.path (idiom parity)
from lt_panels.models import MFMType, ConfigField


# The 14 static-config fields the ems_backend consumers read via mfm.get_config(). Each row mirrors the code fallback:
#   (key, label, section, unit, data_type, default_value_or_None, display_order)
# default_value_or_None: the SAME literal the consumer passes as get_config(key, <default>); None → leave BLANK (the two
# energy-distribution keys are called with no default → None → honest blank, admin sets the real per-panel rating).
_LT_PANEL_FIELDS = [
    # ── Rating & Identity (energy_power NAMEPLATE — pcc_panel.py) ──────────────────────────────────────────────────
    ('rated_kva',                    'Rated Capacity',            'Rating & Identity', 'kVA',       'number',  6000.0,   10),
    ('rated_kw',                     'Rated Load',                'Rating & Identity', 'kW',        'number',  5500.0,   20),
    ('critical_demand_kw',           'Critical Demand',           'Rating & Identity', 'kW',        'number',  1600.0,   30),
    ('subsidy_limit_mvah_per_month', 'Subsidy Energy Limit',      'Rating & Identity', 'MVAh/mo',   'number',  3200.0,   40),
    ('contract_kwh_per_day',         'Contract Energy / Day',     'Rating & Identity', 'kWh/day',   'number',  120000.0, 50),
    ('rated_kwh_per_day',            'Rated Energy / Day',        'Rating & Identity', 'kWh/day',   'number',  100000.0, 60),
    ('sec_target_kwh_per_unit',      'Specific Energy Target',    'Rating & Identity', 'kWh/unit',  'number',  207.0,    70),
    # ── PQ Event Thresholds (voltage_current + power_quality_summary — pcc_panel.py) ──────────────────────────────
    ('event_sag_pct_of_nominal',     'Sag Threshold',             'PQ Event Thresholds', '% Vnom',  'number',  92,       110),
    ('event_swell_pct_of_nominal',   'Swell Threshold',           'PQ Event Thresholds', '% Vnom',  'number',  108,      120),
    ('event_i_unbalance_pct',        'Current Unbalance Limit',   'PQ Event Thresholds', '%',       'number',  8,        130),
    ('event_neutral_pct_of_phase',   'Neutral Current Limit',     'PQ Event Thresholds', '% phase', 'number',  15,       140),
    ('neutral_ratio_limit',          'Neutral Stress Ratio Limit','PQ Event Thresholds', '%',       'number',  10.0,     150),
    # ── Energy Distribution (energy_distribution — pcc_panel.py; per-panel rated loads, NO code default → blank) ───
    ('incoming_live_load_kw',        'Incoming Rated Load',       'Energy Distribution', 'kW',      'number',  None,     210),
    ('outgoing_live_load_kw',        'Outgoing Rated Load',       'Energy Distribution', 'kW',      'number',  None,     220),
]

# key = MFMType.code the fields attach to. 'lt_panel' == the PCC panels (seed_mfms: 'LT Panel' → 'lt_panel').
_FIELDS_BY_TYPE = {'lt_panel': _LT_PANEL_FIELDS}


class Command(BaseCommand):
    help = "Seed lt_config_field for the ems_backend get_config() layer (reproducible per-MFM-type static config)."

    def handle(self, *args, **opts):
        total = 0
        for type_code, fields in _FIELDS_BY_TYPE.items():
            mtype = MFMType.objects.filter(code=type_code).first()
            if mtype is None:
                self.stderr.write(self.style.WARNING(f"MFMType code={type_code!r} not found — skipped (run seed_mfms first)."))
                continue
            for key, label, section, unit, data_type, default, order in fields:
                ConfigField.objects.update_or_create(
                    mfm_type=mtype, key=key,
                    defaults={
                        'label': label, 'section': section, 'unit': unit,
                        'data_type': data_type, 'display_order': order,
                        'default_value': '' if default is None else str(default),
                    },
                )
                total += 1
                blank = '  (blank — admin sets per-panel)' if default is None else ''
                self.stdout.write(f"  {type_code}.{key} = {'' if default is None else default}{blank}")
        self.stdout.write(self.style.SUCCESS(f"seeded {total} ConfigField rows across {len(_FIELDS_BY_TYPE)} MFM type(s)."))
