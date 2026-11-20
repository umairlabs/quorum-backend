import uuid
from django.conf import settings
from django.db import models

from apps.assets.models import Asset, AssetUnit


class MaintenanceRequest(models.Model):
    """
    Matches frontend MaintenanceRequest interface.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        TODO = 'TODO', 'To Do'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        REVIEW = 'REVIEW', 'Under Review'
        COMPLETED = 'COMPLETED', 'Completed'
        VERIFIED = 'VERIFIED', 'Verified'
        CANCELLED = 'CANCELLED', 'Cancelled'
        UNREPAIRABLE = 'UNREPAIRABLE', 'Unrepairable'
        RESOLVED = 'RESOLVED', 'Resolved'
        NOT_REPAIRABLE = 'NOT_REPAIRABLE', 'Not Repairable'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    class MaintenanceType(models.TextChoices):
        PREVENTIVE = 'PREVENTIVE', 'Preventive'
        CORRECTIVE = 'CORRECTIVE', 'Corrective'
        EMERGENCY = 'EMERGENCY', 'Emergency'
        INSPECTION = 'INSPECTION', 'Inspection'
        UPGRADE = 'UPGRADE', 'Upgrade'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    request_id = models.CharField(max_length=50, unique=True, db_index=True)  # e.g. "MNT-001"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_requests'
    )
    asset_unit = models.ForeignKey(
        AssetUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_requests'
    )
    asset_name_snapshot = models.CharField(max_length=255, blank=True, default='')

    component_or_issue_type = models.CharField(max_length=200)
    issue_description = models.TextField()
    maintenance_type = models.CharField(max_length=20, choices=MaintenanceType.choices)
    priority = models.CharField(max_length=20, choices=Priority.choices, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    notes = models.TextField(blank=True, default='')  # resolution notes on completion
    work_done = models.TextField(blank=True, default='')
    technician_notes = models.TextField(blank=True, default='')
    assigned_technician = models.CharField(max_length=200, blank=True, default='')

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_requests'
    )
    requested_by_name = models.CharField(max_length=200, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'maintenance_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return f"{self.display_id or self.request_id} - {self.asset.name if self.asset else ''} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.display_id:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(MaintenanceRequest, 'MNT')
        if not self.request_id:
            self.request_id = self.display_id
        if self.asset_unit and not self.asset:
            self.asset = self.asset_unit.asset
        if self.asset and not self.asset_name_snapshot:
            self.asset_name_snapshot = self.asset.name
        super().save(*args, **kwargs)


class MaintenanceTimelineEntry(models.Model):
    """
    Matches frontend MaintenanceTimelineEntry interface.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    maintenance_request = models.ForeignKey(
        MaintenanceRequest,
        on_delete=models.CASCADE,
        related_name='timeline'
    )
    status = models.CharField(max_length=20, choices=MaintenanceRequest.Status.choices)
    label = models.CharField(max_length=200)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, default='')
    work_done = models.TextField(blank=True, default='')
    completed_by = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        db_table = 'maintenance_timeline_entries'
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.maintenance_request.display_id or self.maintenance_request.request_id} - {self.status}"
