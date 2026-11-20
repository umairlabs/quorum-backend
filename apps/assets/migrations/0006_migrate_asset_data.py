from django.db import migrations


def copy_asset_data_to_units(apps, schema_editor):
    Asset = apps.get_model('assets', 'Asset')
    AssetUnit = apps.get_model('assets', 'AssetUnit')
    AssetAssignmentHistory = apps.get_model('assets', 'AssetAssignmentHistory')

    for asset in Asset.objects.all():
        serial = asset.serial_number or f"{asset.asset_tag}-U001"
        if AssetUnit.objects.filter(serial_number=serial).exists():
            serial = f"{serial}-{str(asset.id)[:6]}"

        unit = AssetUnit.objects.create(
            asset=asset,
            unit_number=1,
            serial_number=serial,
            status=asset.status or 'AVAILABLE',
            location=asset.location or '',
            assigned_to=asset.assigned_to,
        )

        AssetAssignmentHistory.objects.filter(asset=asset).update(unit=unit)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0005_add_assetunit_safe'),
    ]

    operations = [
        migrations.RunPython(copy_asset_data_to_units, reverse_noop),
    ]