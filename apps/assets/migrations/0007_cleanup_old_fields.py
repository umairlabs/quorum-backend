import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0006_migrate_asset_data'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='asset',
            name='assets_status_326766_idx',
        ),
        migrations.AlterField(
            model_name='assetassignmenthistory',
            name='unit',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignment_history', to='assets.assetunit'),
        ),
        migrations.RemoveField(
            model_name='assetassignmenthistory',
            name='asset',
        ),
        migrations.RemoveField(
            model_name='asset',
            name='assigned_to',
        ),
        migrations.RemoveField(
            model_name='asset',
            name='available_quantity',
        ),
        migrations.RemoveField(
            model_name='asset',
            name='damaged_quantity',
        ),
        migrations.RemoveField(
            model_name='asset',
            name='location',
        ),
        migrations.RemoveField(
            model_name='asset',
            name='serial_number',
        ),
        migrations.RemoveField(
            model_name='asset',
            name='status',
        ),
        migrations.RemoveField(
            model_name='asset',
            name='total_quantity',
        ),
        migrations.AddIndex(
            model_name='assetunit',
            index=models.Index(fields=['status'], name='asset_units_status_4b3bfe_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='assetunit',
            unique_together={('asset', 'unit_number')},
        ),
    ]