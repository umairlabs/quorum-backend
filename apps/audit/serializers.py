from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    auditId = serializers.CharField(source='audit_id', read_only=True)
    userName = serializers.CharField(source='user_name_snapshot', read_only=True)
    userRole = serializers.CharField(source='user_role_snapshot', read_only=True)
    assetName = serializers.CharField(source='asset_name_snapshot', read_only=True)
    serialNumber = serializers.CharField(source='serial_number_snapshot', read_only=True)
    oldValue = serializers.JSONField(source='old_value', read_only=True)
    newValue = serializers.JSONField(source='new_value', read_only=True)
    ipAddress = serializers.CharField(source='ip_address', read_only=True)
    timestamp = serializers.DateTimeField(source='created_at', read_only=True)
    assetId = serializers.UUIDField(source='asset_id', read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'auditId',
            'userName',
            'userRole',
            'action',
            'module',
            'assetId',
            'assetName',
            'serialNumber',
            'description',
            'oldValue',
            'newValue',
            'ipAddress',
            'metadata',
            'timestamp',
        ]
        read_only_fields = fields
