from django.db import migrations


def sync_serial_numbers(apps, schema_editor):
    Asset = apps.get_model('assets', 'Asset')
    AssetUnit = apps.get_model('assets', 'AssetUnit')
    AssetAssignmentHistory = apps.get_model('assets', 'AssetAssignmentHistory')

    # Step 1: Ensure every asset has at least one unit
    for asset in Asset.objects.all():
        if not asset.units.exists():
            AssetUnit.objects.create(
                asset=asset,
                unit_number=1,
                display_id=f"TEMP-{asset.id}",
                serial_number=f"TEMP-{asset.id}",
                status='AVAILABLE',
                location='HQ'
            )

    units = list(AssetUnit.objects.order_by('created_at', 'id').all())
    
    # Step 2: Temporarily clear serial numbers to prevent unique constraint conflicts
    for idx, unit in enumerate(units, start=1):
        unit.serial_number = f"TEMP-SER-{unit.id}"
        unit.save(update_fields=['serial_number'])

    # Step 3: Assign clean sequential SER-xxx to all units
    for idx, unit in enumerate(units, start=1):
        target_ser = f"SER-{idx:03d}"
        unit.display_id = target_ser
        unit.serial_number = target_ser
        unit.save(update_fields=['display_id', 'serial_number'])

        AssetAssignmentHistory.objects.filter(unit=unit).update(
            unit_serial_snapshot=target_ser
        )


def reverse_sync(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0015_asset_display_id_assetassignmenthistory_display_id_and_more'),
    ]

    operations = [
        migrations.RunPython(sync_serial_numbers, reverse_sync),
    ]
