"""Seed the 12 UPS assets into the Django default DB.

Idempotent — re-running updates the table_name / asset_id mapping without
creating duplicates. Each UPS reads from its own timeseries table
(mfm_ups_047 … mfm_ups_058) in the external `lt_panels` DB, filtered by
panel_id (MFM-UPS-047 … MFM-UPS-058).

Run:  python manage.py seed_ups_assets
"""
from django.core.management.base import BaseCommand

from assets.models import AssetType, Asset
from lt_panels.data_db_link import default_db_link


# (display name, panel_id filter value, timeseries table)
_UPS = [
    (f'UPS-{i:02d}', f'MFM-UPS-{46 + i:03d}', f'mfm_ups_{46 + i:03d}')
    for i in range(1, 13)
]
_DB_LINK = default_db_link()                                       # target_version1/compat (env-driven); NOT the old lt_panels DB


class Command(BaseCommand):
    help = 'Seed the 12 UPS assets (idempotent).'

    def handle(self, *args, **options):
        ups_type, created = AssetType.objects.get_or_create(
            code='ups', defaults={'name': 'UPS'},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created AssetType 'ups'"))

        n_created = n_updated = 0
        for name, panel_id, table in _UPS:
            obj, was_created = Asset.objects.update_or_create(
                name=name,
                defaults={
                    'asset_type': ups_type,
                    'db_link': _DB_LINK,
                    'table_name': table,
                    'asset_id': panel_id,
                },
            )
            if was_created:
                n_created += 1
            else:
                n_updated += 1
            self.stdout.write(f'  {name:8s} → {table:14s} (panel_id={panel_id})')

        self.stdout.write(self.style.SUCCESS(
            f'Done: {n_created} created, {n_updated} updated. '
            f'Total UPS assets: {Asset.objects.filter(asset_type=ups_type).count()}'
        ))
