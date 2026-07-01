"""Repoint the MFM.db_link DEFAULT from the deprecated `lt_panels` socket DB to the live data
(target_version1 / schema compat), env-driven via lt_panels.data_db_link.default_db_link. Existing rows unaffected."""
import lt_panels.data_db_link
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lt_panels', '0011_mfm_power_quality'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mfm',
            name='db_link',
            field=models.CharField(
                default=lt_panels.data_db_link.default_db_link,
                help_text='libpq connection string used to fetch the time-series DATA (target_version1, schema compat)',
                max_length=255,
            ),
        ),
    ]
