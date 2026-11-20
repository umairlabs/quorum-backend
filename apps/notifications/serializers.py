from rest_framework import serializers
from .models import Notification, UserNotificationPreference, FCMDevice


class NotificationSerializer(serializers.ModelSerializer):
    userId = serializers.CharField(source='user_id', read_only=True, allow_null=True)
    targetRole = serializers.CharField(source='target_role', read_only=True)
    subType = serializers.CharField(source='sub_type', read_only=True)
    relatedAssetId = serializers.CharField(source='related_asset_id', read_only=True, allow_null=True)
    relatedAssetName = serializers.CharField(source='related_asset_name', read_only=True)
    relatedMaintenanceId = serializers.CharField(source='related_maintenance_id', read_only=True, allow_null=True)
    relatedMaintenanceRequestId = serializers.CharField(source='related_maintenance_request_id', read_only=True)
    relatedAssignmentId = serializers.CharField(source='related_assignment_id', read_only=True, allow_null=True)
    # Asset-request specific linking fields
    relatedRequestId = serializers.CharField(source='related_request_id', read_only=True, allow_null=True)
    relatedRequestNumber = serializers.CharField(source='related_request_number', read_only=True)
    isRead = serializers.BooleanField(source='is_read')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'userId', 'targetRole', 'title', 'message', 'type', 'subType',
            'relatedAssetId', 'relatedAssetName', 'relatedMaintenanceId',
            'relatedMaintenanceRequestId', 'relatedAssignmentId',
            'relatedRequestId', 'relatedRequestNumber',
            'isRead', 'createdAt'
        ]


class UserNotificationPreferenceSerializer(serializers.ModelSerializer):
    userId = serializers.CharField(source='user_id', read_only=True)

    maintenanceNewTicket = serializers.BooleanField(source='maintenance_new_ticket', required=False)
    maintenanceAssignedToTech = serializers.BooleanField(source='maintenance_assigned_to_tech', required=False)
    maintenanceStatusChanged = serializers.BooleanField(source='maintenance_status_changed', required=False)
    maintenanceHighPriority = serializers.BooleanField(source='maintenance_high_priority', required=False)
    maintenanceCriticalAlert = serializers.BooleanField(source='maintenance_critical_alert', required=False)
    maintenanceCompleted = serializers.BooleanField(source='maintenance_completed', required=False)
    maintenanceUpdated = serializers.BooleanField(source='maintenance_updated', required=False)

    assetAssigned = serializers.BooleanField(source='asset_assigned', required=False)
    assetTransferred = serializers.BooleanField(source='asset_transferred', required=False)
    assetReturned = serializers.BooleanField(source='asset_returned', required=False)
    assetRetired = serializers.BooleanField(source='asset_retired', required=False)
    assetScrapped = serializers.BooleanField(source='asset_scrapped', required=False)
    assetMaintenanceActivity = serializers.BooleanField(source='asset_maintenance_activity', required=False)

    assignmentNew = serializers.BooleanField(source='assignment_new', required=False)
    assignmentTransfer = serializers.BooleanField(source='assignment_transfer', required=False)
    assignmentReturn = serializers.BooleanField(source='assignment_return', required=False)

    warrantyExpiringSoon = serializers.BooleanField(source='warranty_expiring_soon', required=False)
    warrantyExpired = serializers.BooleanField(source='warranty_expired', required=False)

    systemImportantAlerts = serializers.BooleanField(source='system_important_alerts', required=False)
    systemRequiredActions = serializers.BooleanField(source='system_required_actions', required=False)

    class Meta:
        model = UserNotificationPreference
        fields = [
            'id', 'userId',
            'maintenanceNewTicket', 'maintenanceAssignedToTech', 'maintenanceStatusChanged',
            'maintenanceHighPriority', 'maintenanceCriticalAlert', 'maintenanceCompleted', 'maintenanceUpdated',
            'assetAssigned', 'assetTransferred', 'assetReturned', 'assetRetired', 'assetScrapped', 'assetMaintenanceActivity',
            'assignmentNew', 'assignmentTransfer', 'assignmentReturn',
            'warrantyExpiringSoon', 'warrantyExpired',
            'systemImportantAlerts', 'systemRequiredActions',
        ]


class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = ['id', 'token', 'created_at']
        read_only_fields = ['id', 'created_at']