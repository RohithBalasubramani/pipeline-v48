"""seed_registry — populate the MFM registry (lt_mfm / lt_mfm_type) from the REAL device registry so ws/mfm/<id>/
resolves to a live neuract data table.

The single source of truth is the pipeline's `asset_candidates()` (reads meta_data_version1 read-only, filtered to real
neuract tables, ids contiguous 1..N in table order). This command REUSES that exact function, so MFM.id == the pipeline's
mfm_id by construction — the host's ws/mfm/<mfm_id>/ lookup lines up with what 1b resolved. Nothing is invented here.

Each MFM row:
  id         = asset_candidates mfm_id (explicit pk, so it matches the pipeline)
  name       = device human name
  table_name = the neuract data table (gic_..._p1) — what the strategy SELECTs from
  db_link    = default_db_link() → target_version1 / schema neuract (the live tunnel)
  panel_id   = '' (neuract tables are one-meter-per-table; services skips the panel_id filter — DATA_HAS_PANEL_ID=0)
  mfm_type   = the strategy code the consumers dispatch on: UPS→ups, Transformer→transformer, APFCR→apfc, else lt_panel
               (every gic_ table shares the same 72-col schema, so lt_panel safely reads any of them).

  python manage.py seed_registry            # idempotent upsert by id
  python manage.py seed_registry --dry-run  # print plan, write nothing
  python manage.py seed_registry --wipe     # delete existing MFM rows first (old simulator seed)
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from lt_panels.data_db_link import default_db_link        # importing this also bootstraps pipeline_v48 onto sys.path
from lt_panels.models import MFM, MFMType
from layer1b.resolve.asset_candidates import asset_candidates, as_asset

# inferred equipment class (asset_candidates) → the strategy code the dispatcher selects on (mfm_type.code).
# Only ups / transformer / apfc have dedicated strategies; everything else reads the standard schema → lt_panel.
CLASS_TO_CODE = {'UPS': 'ups', 'Transformer': 'transformer', 'APFCR': 'apfc'}
CODE_NAME = {'ups': 'UPS', 'transformer': 'Transformer', 'apfc': 'APFC', 'lt_panel': 'LT Panel'}


def code_for(cls: str) -> str:
    return CLASS_TO_CODE.get(cls or '', 'lt_panel')


class Command(BaseCommand):
    help = 'Seed lt_mfm / lt_mfm_type from the real device registry (meta_data_version1), matching pipeline mfm_id.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='print the plan, write nothing')
        parser.add_argument('--wipe', action='store_true', help='delete existing MFM rows before seeding')

    def handle(self, *args, **opts):
        assets = [as_asset(c) for c in asset_candidates()]
        codes = sorted({code_for(a['class']) for a in assets})
        link = default_db_link()
        self.stdout.write(f'{len(assets)} real assets from registry; mfm_type codes: {codes}')
        self.stdout.write(f'db_link → {link}')

        if opts['dry_run']:
            for a in assets[:12]:
                self.stdout.write(f"  id={a['mfm_id']:<4} {code_for(a['class']):<11} {a['name'][:40]:<40} → {a['table']}")
            self.stdout.write(f'  … and {max(0, len(assets) - 12)} more. (dry-run: nothing written)')
            return

        with transaction.atomic():
            if opts['wipe']:
                n, _ = MFM.objects.all().delete()
                self.stdout.write(f'wiped {n} existing MFM rows')
            types = {c: MFMType.objects.update_or_create(code=c, defaults={'name': CODE_NAME.get(c, c)})[0]
                     for c in codes}
            created = updated = 0
            for a in assets:
                _, was_created = MFM.objects.update_or_create(
                    id=a['mfm_id'],
                    defaults={
                        'name': a['name'],
                        'mfm_type': types[code_for(a['class'])],
                        'db_link': link,
                        'table_name': a['table'],
                        'load_group': a['load_group'] or '',
                        'panel_id': '',
                    },
                )
                created += was_created
                updated += not was_created

        self.stdout.write(self.style.SUCCESS(
            f'seeded {created} new + {updated} updated MFM rows across {len(types)} types'))
