"""
Data migration to strip backend-appended unit suffixes from asset names.

Old code used to create Asset records with names like:
  "Dell Latitude 7420 #100 (PO-56195)"
  "Iphone #3 (PO-LOCAL-1787397116304)"

This migration strips those suffixes so all units of the same product
share the same clean base name (e.g. "Dell Latitude 7420", "Iphone").
"""
import re
from django.db import migrations


def clean_asset_names(apps, schema_editor):
    Asset = apps.get_model('assets', 'Asset')

    # Pattern: strip " #<number> (PO-xxx)" and " (PO-xxx)" suffixes
    suffix_pattern = re.compile(
        r'\s*#\d+(\s*\(PO-[^)]*\))?\s*$'
        r'|\s*\(PO-[^)]*\)\s*$',
        re.IGNORECASE
    )

    updated = []
    for asset in Asset.objects.all():
        clean = suffix_pattern.sub('', asset.name).strip()
        if clean and clean != asset.name:
            asset.name = clean
            updated.append(asset)

    if updated:
        Asset.objects.bulk_update(updated, ['name'])


def reverse_clean(apps, schema_editor):
    # Cannot reverse a data clean — names are gone
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0008_make_asset_tag_nullable'),
    ]

    operations = [
        migrations.RunPython(clean_asset_names, reverse_clean),
    ]
