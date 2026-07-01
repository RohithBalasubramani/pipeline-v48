"""Seed the 8 LT-transformer assets into the Django default DB.

Idempotent. Each reads from its own timeseries table (mfm_tf_11 … mfm_tf_18)
in the external `lt_panels` DB, filtered by panel_id (MFM-TF-11 … MFM-TF-18).
These 8 are the rows where transformer_config.asset_type = 'LT transformer'.

Run:  python manage.py seed_lt_transformer_assets
"""
from django.core.management.base import BaseCommand

from assets.models import AssetType, Asset
from lt_panels.data_db_link import default_db_link


# (display name, panel_id filter value, timeseries table)
_LT_TF = [
    (f'Transformer-{i:02d}', f'MFM-TF-{10 + i}', f'mfm_tf_{10 + i}')
    for i in range(1, 9)
]
_DB_LINK = default_db_link()                                       # target_version1/compat (env-driven); NOT the old lt_panels DB


class Command(BaseCommand):
    help = 'Seed the 8 LT-transformer assets (idempotent).'

    def handle(self, *args, **options):
        tf_type, created = AssetType.objects.get_or_create(
            code='lt_transformer', defaults={'name': 'LT Transformer'},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created AssetType 'lt_transformer'"))

        n_created = n_updated = 0
        for name, panel_id, table in _LT_TF:
            obj, was_created = Asset.objects.update_or_create(
                name=name,
                defaults={
                    'asset_type': tf_type,
                    'db_link': _DB_LINK,
                    'table_name': table,
                    'asset_id': panel_id,
                },
            )
            n_created += was_created
            n_updated += (not was_created)
            self.stdout.write(f'  {name:14s} → {table:12s} (panel_id={panel_id})')

        self.stdout.write(self.style.SUCCESS(
            f'Done: {n_created} created, {n_updated} updated. '
            f'Total LT-transformer assets: {Asset.objects.filter(asset_type=tf_type).count()}'
        ))
