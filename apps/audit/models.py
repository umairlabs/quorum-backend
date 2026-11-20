import uuid
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        # Asset Catalog & Physical Units
        ASSET_CREATED = 'ASSET_CREATED', 'Asset Created'
        ASSET_UPDATED = 'ASSET_UPDATED', 'Asset Updated'
        ASSET_PURCHASED = 'ASSET_PURCHASED', 'Asset Purchased'
        ASSET_RETIRED = 'ASSET_RETIRED', 'Asset Retired'
        ASSET_SCRAPPED = 'ASSET_SCRAPPED', 'Asset Scrapped'
        USER_PERMISSIONS_UPDATED = 'USER_PERMISSIONS_UPDATED', 'User Permissions Updated'

        # Assignments
        ASSET_ASSIGNED = 'ASSET_ASSIGNED', 'Asset Assigned'
        ASSET_TRANSFERRED = 'ASSET_TRANSFERRED', 'Asset Transferred'
        ASSET_RETURNED = 'ASSET_RETURNED', 'Asset Returned'

        # Maintenance
        MAINTENANCE_CREATED = 'MAINTENANCE_CREATED', 'Maintenance Created'
        MAINTENANCE_ASSIGNED = 'MAINTENANCE_ASSIGNED', 'Maintenance Assigned'
        MAINTENANCE_STARTED = 'MAINTENANCE_STARTED', 'Maintenance Started'
        MAINTENANCE_RESOLVED = 'MAINTENANCE_RESOLVED', 'Maintenance Resolved'
        MAINTENANCE_CLOSED = 'MAINTENANCE_CLOSED', 'Maintenance Closed'

    class Module(models.TextChoices):
        ASSETS = 'ASSETS', 'Assets'
        ASSIGNMENTS = 'ASSIGNMENTS', 'Assignments'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        PURCHASES = 'PURCHASES', 'Purchases'
        USERS = 'USERS', 'Users'
        SETTINGS = 'SETTINGS', 'Settings'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit_id = models.CharField(max_length=50, unique=True, db_index=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    user_name_snapshot = models.CharField(max_length=200, blank=True, default='System')
    user_role_snapshot = models.CharField(max_length=100, blank=True, default='System Administrator')

    action = models.CharField(max_length=50, choices=Action.choices, db_index=True)
    module = models.CharField(max_length=50, choices=Module.choices, default=Module.ASSETS, db_index=True)

    asset = models.ForeignKey(
        'assets.Asset',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    asset_unit = models.ForeignKey(
        'assets.AssetUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    asset_name_snapshot = models.CharField(max_length=255, blank=True, default='')
    serial_number_snapshot = models.CharField(max_length=100, blank=True, default='')

    description = models.TextField(blank=True, default='')
    old_value = models.JSONField(blank=True, default=dict)
    new_value = models.JSONField(blank=True, default=dict)

    ip_address = models.CharField(max_length=45, blank=True, default='')
    metadata = models.JSONField(blank=True, default=dict)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action']),
            models.Index(fields=['module']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.audit_id} - {self.action} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
