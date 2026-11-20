from rest_framework import serializers

from apps.assets.models import Asset
from .models import MaintenanceRequest, MaintenanceTimelineEntry


class MaintenanceTimelineEntrySerializer(serializers.ModelSerializer):
    completedBy = serializers.CharField(source='completed_by', read_only=True, default='')
    workDone = serializers.CharField(source='work_done', read_only=True, default='')

    class Meta:
        model = MaintenanceTimelineEntry
        fields = ['id', 'status', 'label', 'timestamp', 'note', 'workDone', 'completedBy']


class MaintenanceHistoryItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    date = serializers.SerializerMethodField()
    issue = serializers.CharField(source='component_or_issue_type')
    action = serializers.CharField(source='notes')

    def get_date(self, obj):
        ref_date = obj.completed_at or obj.updated_at
        return ref_date.date().isoformat() if ref_date else None


class MaintenanceListSerializer(serializers.ModelSerializer):
    displayId = serializers.CharField(source='display_id', read_only=True)
    unitId = serializers.PrimaryKeyRelatedField(source='asset_unit', read_only=True)
    requestId = serializers.CharField(source='request_id')
    assetId = serializers.PrimaryKeyRelatedField(source='asset', read_only=True)
    assetName = serializers.SerializerMethodField()
    assetIcon = serializers.SerializerMethodField()
    assetTag = serializers.CharField(source='asset.asset_tag', read_only=True, default='')
    serialNumber = serializers.SerializerMethodField()
    componentOrIssueType = serializers.CharField(source='component_or_issue_type')
    issueDescription = serializers.CharField(source='issue_description')
    maintenanceType = serializers.CharField(source='maintenance_type')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    workDone = serializers.CharField(source='work_done', read_only=True, default='')
    technicianNotes = serializers.CharField(source='technician_notes', read_only=True, default='')
    assignedTechnician = serializers.CharField(source='assigned_technician', read_only=True, default='')

    class Meta:
        model = MaintenanceRequest
        fields = [
            'id', 'displayId', 'requestId', 'assetId', 'unitId', 'assetName', 'assetIcon', 'assetTag', 'serialNumber',
            'componentOrIssueType', 'issueDescription', 'maintenanceType',
            'priority', 'status', 'createdAt', 'updatedAt', 'workDone',
            'technicianNotes', 'assignedTechnician',
        ]

    def get_assetName(self, obj):
        return (obj.asset_name_snapshot
                or (obj.asset.name if obj.asset else None)
                or 'Asset')

    def get_assetIcon(self, obj):
        if obj.asset:
            return obj.asset.icon_key
        # fallback: detect from snapshot name
        name = (obj.asset_name_snapshot or '').lower()
        from apps.assets.models import Asset as _Asset
        mapping = _Asset._ICON_KEYWORD_MAP
        for keywords, icon in mapping:
            if any(kw in name for kw in keywords):
                return icon
        return 'inventory_2'

    def get_serialNumber(self, obj):
        if obj.asset_unit:
            u = obj.asset_unit
            if u.display_id and str(u.display_id).startswith('SER-'):
                return str(u.display_id)
            if u.serial_number and str(u.serial_number).startswith('SER-'):
                return str(u.serial_number)
            try:
                from apps.common.utils import generate_display_id
                u.display_id = generate_display_id(u.__class__, 'SER')
                u.serial_number = u.display_id
                u.save(update_fields=['display_id', 'serial_number'])
                return str(u.display_id)
            except Exception:
                return f"SER-{u.unit_number:03d}"
        if obj.asset:
            first_unit = obj.asset.units.first() if hasattr(obj.asset, 'units') else None
            if first_unit:
                if first_unit.display_id and str(first_unit.display_id).startswith('SER-'):
                    return str(first_unit.display_id)
                if first_unit.serial_number and str(first_unit.serial_number).startswith('SER-'):
                    return str(first_unit.serial_number)
                return f"SER-{first_unit.unit_number:03d}"
            if obj.asset.display_id and str(obj.asset.display_id).startswith('AST-'):
                return str(obj.asset.display_id)
        return ''


class MaintenanceDetailSerializer(serializers.ModelSerializer):
    displayId = serializers.CharField(source='display_id', read_only=True)
    unitId = serializers.PrimaryKeyRelatedField(source='asset_unit', read_only=True)
    requestId = serializers.CharField(source='request_id')
    assetId = serializers.PrimaryKeyRelatedField(source='asset', read_only=True)
    assetName = serializers.SerializerMethodField()
    assetIcon = serializers.SerializerMethodField()
    assetTag = serializers.CharField(source='asset.asset_tag', read_only=True, default='')
    serialNumber = serializers.SerializerMethodField()
    componentOrIssueType = serializers.CharField(source='component_or_issue_type')
    issueDescription = serializers.CharField(source='issue_description')
    maintenanceType = serializers.CharField(source='maintenance_type')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    completedAt = serializers.DateTimeField(source='completed_at', read_only=True)
    requestedBy = serializers.PrimaryKeyRelatedField(source='requested_by', read_only=True)
    requestedByName = serializers.CharField(source='requested_by_name', read_only=True)
    workDone = serializers.CharField(source='work_done', read_only=True, default='')
    technicianNotes = serializers.CharField(source='technician_notes', read_only=True, default='')
    assignedTechnician = serializers.CharField(source='assigned_technician', read_only=True, default='')

    timeline = MaintenanceTimelineEntrySerializer(many=True, read_only=True)
    assetMaintenanceHistory = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceRequest
        fields = [
            'id', 'displayId', 'requestId', 'assetId', 'unitId', 'assetName', 'assetIcon', 'assetTag', 'serialNumber',
            'componentOrIssueType', 'issueDescription', 'maintenanceType',
            'priority', 'status', 'createdAt', 'updatedAt', 'completedAt',
            'timeline', 'assetMaintenanceHistory', 'notes', 'workDone',
            'technicianNotes', 'assignedTechnician',
            'requestedBy', 'requestedByName', 'department',
        ]

    def get_assetName(self, obj):
        return (obj.asset_name_snapshot
                or (obj.asset.name if obj.asset else None)
                or 'Asset')

    def get_assetIcon(self, obj):
        if obj.asset:
            return obj.asset.icon_key
        name = (obj.asset_name_snapshot or '').lower()
        from apps.assets.models import Asset as _Asset
        for keywords, icon in _Asset._ICON_KEYWORD_MAP:
            if any(kw in name for kw in keywords):
                return icon
        return 'inventory_2'

    def get_serialNumber(self, obj):
        if obj.asset_unit:
            u = obj.asset_unit
            if u.display_id and str(u.display_id).startswith('SER-'):
                return str(u.display_id)
            if u.serial_number and str(u.serial_number).startswith('SER-'):
                return str(u.serial_number)
            try:
                from apps.common.utils import generate_display_id
                u.display_id = generate_display_id(u.__class__, 'SER')
                u.serial_number = u.display_id
                u.save(update_fields=['display_id', 'serial_number'])
                return str(u.display_id)
            except Exception:
                return f"SER-{u.unit_number:03d}"
        if obj.asset:
            first_unit = obj.asset.units.first() if hasattr(obj.asset, 'units') else None
            if first_unit:
                if first_unit.display_id and str(first_unit.display_id).startswith('SER-'):
                    return str(first_unit.display_id)
                if first_unit.serial_number and str(first_unit.serial_number).startswith('SER-'):
                    return str(first_unit.serial_number)
                return f"SER-{first_unit.unit_number:03d}"
            if obj.asset.display_id and str(obj.asset.display_id).startswith('AST-'):
                return str(obj.asset.display_id)
        return ''

    def get_assetMaintenanceHistory(self, obj):
        past = MaintenanceRequest.objects.filter(
            asset=obj.asset,
            status__in=[MaintenanceRequest.Status.COMPLETED, MaintenanceRequest.Status.VERIFIED, MaintenanceRequest.Status.RESOLVED],
        ).exclude(id=obj.id).order_by('-completed_at')
        return MaintenanceHistoryItemSerializer(past, many=True).data


class CreateMaintenanceRequestSerializer(serializers.Serializer):
    assetId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    unitId = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    componentOrIssueType = serializers.CharField(source='component_or_issue_type')
    issueDescription = serializers.CharField(source='issue_description')
    maintenanceType = serializers.ChoiceField(
        source='maintenance_type', choices=MaintenanceRequest.MaintenanceType.choices
    )
    priority = serializers.ChoiceField(choices=MaintenanceRequest.Priority.choices)
    assignedTechnician = serializers.CharField(source='assigned_technician', required=False, allow_blank=True, default='')

    def validate(self, attrs):
        import uuid
        from apps.assets.models import Asset, AssetUnit, AssetAssignmentHistory

        asset_id_raw = (attrs.get('assetId') or self.initial_data.get('assetId') or '').strip()
        unit_id_raw = (attrs.get('unitId') or self.initial_data.get('unitId') or '').strip()

        # Handle compound IDs like "<uuid>-unit-<uuid>"
        if '-unit-' in asset_id_raw:
            parts = asset_id_raw.split('-unit-')
            asset_id_raw = parts[0].strip()
            if not unit_id_raw and len(parts) > 1:
                unit_id_raw = parts[1].strip()

        asset_obj = None
        unit_obj = None

        # 1. Try unit_id_raw first
        if unit_id_raw:
            try:
                u_uuid = uuid.UUID(unit_id_raw)
                unit_obj = AssetUnit.objects.filter(pk=u_uuid).first()
                if not unit_obj:
                    assign = AssetAssignmentHistory.objects.filter(pk=u_uuid).first()
                    if assign and assign.unit:
                        unit_obj = assign.unit
            except (ValueError, TypeError):
                unit_obj = AssetUnit.objects.filter(serial_number__iexact=unit_id_raw).first()

        # 2. Try asset_id_raw
        if asset_id_raw:
            try:
                a_uuid = uuid.UUID(asset_id_raw)
                asset_obj = Asset.objects.filter(pk=a_uuid).first()

                # If not Asset, could it be AssetUnit?
                if not asset_obj and not unit_obj:
                    unit_obj = AssetUnit.objects.filter(pk=a_uuid).first()
                    if unit_obj:
                        asset_obj = unit_obj.asset

                # If not Asset or Unit, could it be AssetAssignmentHistory PK?
                if not asset_obj and not unit_obj:
                    assign = AssetAssignmentHistory.objects.filter(pk=a_uuid).first()
                    if assign:
                        if assign.unit:
                            unit_obj = assign.unit
                            asset_obj = assign.unit.asset
                        else:
                            if assign.unit_serial_snapshot:
                                unit_obj = AssetUnit.objects.filter(serial_number=assign.unit_serial_snapshot).first()
                                if unit_obj:
                                    asset_obj = unit_obj.asset

                            if not asset_obj and assign.asset_name_snapshot:
                                asset_obj = (
                                    Asset.objects.filter(name__iexact=assign.asset_name_snapshot).first()
                                    or Asset.objects.filter(name__icontains=assign.asset_name_snapshot).first()
                                )

                            if not asset_obj and assign.asset_name_snapshot:
                                for word in assign.asset_name_snapshot.split():
                                    if len(word) >= 3:
                                        asset_obj = Asset.objects.filter(name__icontains=word).first()
                                        if asset_obj:
                                            break

                            if not asset_obj:
                                from apps.assets.models import AssetCategory
                                from datetime import date
                                cat = AssetCategory.objects.first()
                                if not cat:
                                    cat = AssetCategory.objects.create(name='General', code='GEN')
                                asset_obj, _ = Asset.objects.get_or_create(
                                    name=assign.asset_name_snapshot or 'Assigned Asset',
                                    defaults={
                                        'category': cat,
                                        'purchase_date': getattr(assign, 'assigned_date', None) or date.today(),
                                        'purchase_cost': 0,
                                        'current_value': 0,
                                    }
                                )

                            if not unit_obj and assign.unit_serial_snapshot and asset_obj:
                                unit_obj = AssetUnit.objects.filter(serial_number=assign.unit_serial_snapshot).first()
                                if not unit_obj:
                                    from django.db.models import Max
                                    max_num = AssetUnit.objects.filter(asset=asset_obj).aggregate(Max('unit_number'))['unit_number__max'] or 0
                                    unit_obj = AssetUnit.objects.create(
                                        asset=asset_obj,
                                        unit_number=max_num + 1,
                                        serial_number=assign.unit_serial_snapshot,
                                        status='ASSIGNED',
                                        assigned_to=assign.user
                                    )
                                assign.unit = unit_obj
                                assign.save(update_fields=['unit'])
            except (ValueError, TypeError):
                asset_obj = (
                    Asset.objects.filter(name__iexact=asset_id_raw).first()
                    or Asset.objects.filter(name__icontains=asset_id_raw).first()
                )
                if not asset_obj:
                    unit_obj = AssetUnit.objects.filter(serial_number__iexact=asset_id_raw).first()
                    if unit_obj:
                        asset_obj = unit_obj.asset

        # 3. If unit_obj exists but asset_obj does not
        if unit_obj and not asset_obj and unit_obj.asset:
            asset_obj = unit_obj.asset

        # 4. If asset_obj exists but unit_obj does not
        if asset_obj and not unit_obj:
            request = self.context.get('request')
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                user_unit = AssetUnit.objects.filter(asset=asset_obj, assigned_to=request.user).first()
                if user_unit:
                    unit_obj = user_unit
            if not unit_obj:
                unit_obj = AssetUnit.objects.filter(asset=asset_obj).first()

        # 5. Final validation
        if not asset_obj and not unit_obj:
            raise serializers.ValidationError({'assetId': 'Selected asset or unit is invalid or does not exist.'})

        attrs['asset'] = asset_obj
        attrs['asset_unit'] = unit_obj
        return attrs


class UpdateMaintenanceStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MaintenanceRequest.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, default='')


class MaintenanceWorkUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MaintenanceRequest.Status.choices)
    workDone = serializers.CharField(source='work_done', required=True)
    technicianNotes = serializers.CharField(source='technician_notes', required=False, allow_blank=True, default='')
    technicianName = serializers.CharField(required=False, allow_blank=True, default='')


class MaintenanceStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    inProgress = serializers.IntegerField()
    completed = serializers.IntegerField()
