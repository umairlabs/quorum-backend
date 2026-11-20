import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.assets.models import AssetUnit
units = AssetUnit.objects.select_related('asset').all()[:20]
for u in units:
    print(f"Asset: {u.asset.name:30s} | Serial: {u.serial_number} | Status: {u.status}")
