"""Repoint the Asset.db_link DEFAULT from the deprecated `lt_panels` socket DB to the live data
(target_version1 / schema compat), env-driven via lt_panels.data_db_link.default_db_link. Existing rows unaffected."""
import lt_panels.data_db_link
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0003_alter_asset_asset_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='asset',
            name='db_link',
            field=models.CharField(
                default=lt_panels.data_db_link.default_db_link,
                help_text='libpq connection string used to fetch timeseries values (target_version1, schema compat).',
                max_length=255,
            ),
        ),
    ]
