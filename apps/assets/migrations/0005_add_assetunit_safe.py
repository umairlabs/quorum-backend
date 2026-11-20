import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0004_asset_available_quantity_asset_damaged_quantity_and_more'),
        ('purchases', '0002_supplier_specifications_alter_supplier_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetUnit',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('unit_number', models.PositiveIntegerField()),
                ('serial_number', models.CharField(db_index=True, max_length=100, unique=True)),
                ('status', models.CharField(choices=[('AVAILABLE', 'Available'), ('ASSIGNED', 'Assigned'), ('MAINTENANCE', 'Maintenance'), ('SCRAPPED', 'Scrapped')], db_index=True, default='AVAILABLE', max_length=20)),
                ('location', models.CharField(blank=True, default='', max_length=150)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='units', to='assets.asset')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_units', to=settings.AUTH_USER_MODEL)),
                ('purchase', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_units', to='purchases.purchase')),
            ],
            options={
                'db_table': 'asset_units',
                'ordering': ['asset', 'unit_number'],
            },
        ),
        migrations.AddField(
            model_name='assetassignmenthistory',
            name='unit',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='assignment_history', to='assets.assetunit'),
        ),
    ]