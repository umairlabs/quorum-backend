import uuid
from django.db import models
from django.conf import settings
from apps.users.models import User

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        ASSETS = 'ASSETS', 'Assets'
        ASSIGNMENTS = 'ASSIGNMENTS', 'Assignments'
        WARRANTY = 'WARRANTY', 'Warranty'
        SYSTEM = 'SYSTEM', 'System'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    target_role = models.CharField(max_length=50, blank=True, default='', choices=User.Role.choices)
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=50, choices=NotificationType.choices, default=NotificationType.SYSTEM)
    sub_type = models.CharField(max_length=100, blank=True, default='')

    related_asset_id = models.UUIDField(null=True, blank=True)
    related_asset_name = models.CharField(max_length=255, blank=True, default='')
    
    related_maintenance_id = models.UUIDField(null=True, blank=True)
    related_maintenance_request_id = models.CharField(max_length=50, blank=True, default='')

    related_request_id = models.UUIDField(null=True, blank=True)
    related_request_number = models.CharField(max_length=50, blank=True, default='')

    related_assignment_id = models.UUIDField(null=True, blank=True)

    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.type}] {self.title}'


class UserNotificationPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Maintenance
    maintenance_new_ticket = models.BooleanField(default=True)
    maintenance_assigned_to_tech = models.BooleanField(default=True)
    maintenance_status_changed = models.BooleanField(default=True)
    maintenance_high_priority = models.BooleanField(default=True)
    maintenance_critical_alert = models.BooleanField(default=True)
    maintenance_completed = models.BooleanField(default=True)
    maintenance_updated = models.BooleanField(default=True)

    # Assets
    asset_assigned = models.BooleanField(default=True)
    asset_transferred = models.BooleanField(default=True)
    asset_returned = models.BooleanField(default=True)
    asset_retired = models.BooleanField(default=True)
    asset_scrapped = models.BooleanField(default=True)
    asset_maintenance_activity = models.BooleanField(default=True)

    # Assignments
    assignment_new = models.BooleanField(default=True)
    assignment_transfer = models.BooleanField(default=True)
    assignment_return = models.BooleanField(default=True)

    # Warranty
    warranty_expiring_soon = models.BooleanField(default=True)
    warranty_expired = models.BooleanField(default=True)

    # System
    system_important_alerts = models.BooleanField(default=True)
    system_required_actions = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_notification_preferences'

    def __str__(self):
        return f'Notification Preferences for {self.user.email}'
class FCMDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fcm_devices'
    )
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fcm_devices'

    def __str__(self):
        return f'{self.user.email} - {self.token[:20]}...'