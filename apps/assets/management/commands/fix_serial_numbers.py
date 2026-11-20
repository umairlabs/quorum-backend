"""
Management command: fix_serial_numbers
Fixes ALL AssetUnit serial numbers and ensures all assets have proper physical units with SER-xxx.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.assets.models import Asset, AssetUnit, AssetAssignmentHistory
from apps.audit.models import AuditLog


class Command(BaseCommand):
    help = 'Fix ALL AssetUnit serial numbers and ensure all assets have units in clean SER-xxx format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving to database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Ensure all assets have at least 1 unit
        for asset in Asset.objects.all():
            if not asset.units.exists():
                if not dry_run:
                    asset.ensure_default_unit()
                self.stdout.write(f"Provisioned default unit for asset '{asset.name}'")

        units = list(AssetUnit.objects.order_by('created_at', 'id').all())
        if not units:
            self.stdout.write(self.style.SUCCESS('No units found.'))
            return

        self.stdout.write(f'Processing {len(units)} unit(s)...')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes saved.'))
            return

        with transaction.atomic():
            # First temporarily clear serial numbers to avoid any unique constraint collision during renumbering
            for idx, unit in enumerate(units, start=1):
                unit.serial_number = f"TEMP-{unit.id}"
                unit.save(update_fields=['serial_number'])

            # Now assign clean SER-001, SER-002 sequentially to every unit
            for idx, unit in enumerate(units, start=1):
                target_ser = f"SER-{idx:03d}"
                unit.display_id = target_ser
                unit.serial_number = target_ser
                unit.save(update_fields=['display_id', 'serial_number'])

                # Update related assignment history snapshots
                AssetAssignmentHistory.objects.filter(unit=unit).update(
                    unit_serial_snapshot=target_ser
                )

                # Update related audit logs
                AuditLog.objects.filter(asset_unit=unit).update(
                    serial_number_snapshot=target_ser
                )

                self.stdout.write(
                    self.style.SUCCESS(f'  Unit #{idx} ({unit.asset.name if unit.asset else "Asset"}) -> {target_ser}')
                )

        self.stdout.write(self.style.SUCCESS(f'\nSuccess! All {len(units)} units updated to SER-xxx format.'))
