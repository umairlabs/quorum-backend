import uuid
from decimal import Decimal
from rest_framework import serializers
from apps.users.models import User
from .models import Asset, AssetCategory, AssetUnit, AssetAssignmentHistory


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

class AssetCategorySerializer(serializers.ModelSerializer):
    displayId = serializers.CharField(source='display_id', read_only=True)
    assetCount = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = AssetCategory
        fields = ['id', 'displayId', 'name', 'description', 'status', 'assetCount', 'createdAt']

    def get_assetCount(self, obj) -> int:
        return obj.assets.count()


# ---------------------------------------------------------------------------
# Nested read-only pieces
# ---------------------------------------------------------------------------

class AssignedUserSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    employeeId = serializers.CharField(source='employee_id', read_only=True)
    name = serializers.SerializerMethodField()
    avatarInitials = serializers.SerializerMethodField()

    def get_name(self, user: User) -> str:
        full_name = f"{user.first_name} {user.last_name}".strip()
        return full_name or user.email

    def get_avatarInitials(self, user: User) -> str:
        if user.first_name and user.last_name:
            return f"{user.first_name[0]}{user.last_name[0]}".upper()
        return user.email[:2].upper()


class AssignmentHistoryItemSerializer(serializers.ModelSerializer):
    employeeName = serializers.CharField(source='employee_name')
    assignedDate = serializers.DateField(source='assigned_date')
    returnedDate = serializers.DateField(source='returned_date', allow_null=True)

    class Meta:
        model = AssetAssignmentHistory
        fields = ['id', 'employeeName', 'assignedDate', 'returnedDate', 'status']


class FinancialsSerializer(serializers.Serializer):
    purchaseValue    = serializers.DecimalField(source='purchase_cost', max_digits=12, decimal_places=2)
    purchaseDate     = serializers.DateField(source='purchase_date')
    currentValue     = serializers.DecimalField(source='current_value', max_digits=12, decimal_places=2)
    depreciationPercent = serializers.DecimalField(
        source='depreciation_percent', max_digits=5, decimal_places=2, read_only=True
    )
    salvageValue     = serializers.DecimalField(source='salvage_value', max_digits=12, decimal_places=2, read_only=True)
    usefulLifeYears  = serializers.IntegerField(source='useful_life_years', read_only=True)
    depreciationMethod = serializers.CharField(source='depreciation_method', read_only=True)
    annualDepreciation = serializers.SerializerMethodField()
    monthlyDepreciation = serializers.SerializerMethodField()
    accumulatedDepreciation = serializers.SerializerMethodField()
    currentBookValue = serializers.SerializerMethodField()
    depreciationStatus = serializers.SerializerMethodField()

    def get_dep_data(self, obj):
        from apps.depreciation.services import DepreciationService
        return DepreciationService.get_asset_depreciation_data(obj)

    def get_annualDepreciation(self, obj):
        return self.get_dep_data(obj)['annualDepreciation']

    def get_monthlyDepreciation(self, obj):
        return self.get_dep_data(obj)['monthlyDepreciation']

    def get_accumulatedDepreciation(self, obj):
        return self.get_dep_data(obj)['accumulatedDepreciation']

    def get_currentBookValue(self, obj):
        return self.get_dep_data(obj)['currentBookValue']

    def get_depreciationStatus(self, obj):
        return self.get_depreciation_status(obj)

    def get_depreciation_status(self, obj):
        return self.get_dep_data(obj)['depreciationStatus']


# ---------------------------------------------------------------------------
# AssetUnit
# ---------------------------------------------------------------------------

class AssetUnitSerializer(serializers.ModelSerializer):
    displayId    = serializers.SerializerMethodField()
    assetId      = serializers.PrimaryKeyRelatedField(source='asset', read_only=True)
    unitNumber   = serializers.IntegerField(source='unit_number', read_only=True)
    serialNumber = serializers.SerializerMethodField()
    assignedTo   = serializers.PrimaryKeyRelatedField(source='assigned_to', read_only=True)
    assignedUser = serializers.SerializerMethodField()
    purchaseId   = serializers.PrimaryKeyRelatedField(source='purchase', read_only=True)
    purchaseNumber = serializers.SerializerMethodField()
    createdAt    = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt    = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = AssetUnit
        fields = [
            'id', 'displayId', 'assetId', 'unitNumber', 'serialNumber', 'status',
            'location', 'assignedTo', 'assignedUser', 'purchaseId', 'purchaseNumber',
            'createdAt', 'updatedAt',
        ]

    def get_displayId(self, obj) -> str:
        if obj.display_id and str(obj.display_id).startswith('SER-'):
            return str(obj.display_id)
        if obj.serial_number and str(obj.serial_number).startswith('SER-'):
            obj.display_id = str(obj.serial_number)
            obj.save(update_fields=['display_id'])
            return str(obj.display_id)
        try:
            from apps.common.utils import generate_display_id
            obj.display_id = generate_display_id(obj.__class__, 'SER')
            obj.serial_number = obj.display_id
            obj.save(update_fields=['display_id', 'serial_number'])
            return str(obj.display_id)
        except Exception:
            return f"SER-{obj.unit_number:03d}"

    def get_serialNumber(self, obj) -> str:
        return self.get_displayId(obj)

    def get_assignedUser(self, obj):
        if obj.assigned_to:
            return AssignedUserSerializer(obj.assigned_to).data
        return None
    
    def get_purchaseNumber(self, obj):
        if obj.purchase:
            return obj.purchase.purchase_number
        return None


class AssetUnitWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetUnit
        fields = ['status', 'location']


class AssignUnitSerializer(serializers.Serializer):
    user_id       = serializers.UUIDField(required=False, allow_null=True)
    employee_name = serializers.CharField()
    assigned_date = serializers.DateField(required=False)


# ---------------------------------------------------------------------------
# Assets (List & Detail)
# ---------------------------------------------------------------------------

class AssetListSerializer(serializers.ModelSerializer):
    displayId           = serializers.CharField(source='display_id', read_only=True)
    assetId             = serializers.CharField(source='formatted_asset_id', read_only=True)
    iconKey             = serializers.CharField(source='icon_key', read_only=True)
    category            = serializers.CharField(source='category.name')
    value               = serializers.DecimalField(source='current_value', max_digits=12, decimal_places=2)
    purchaseCost        = serializers.DecimalField(source='purchase_cost', max_digits=12, decimal_places=2)
    purchaseDate        = serializers.DateField(source='purchase_date')
    salvageValue        = serializers.DecimalField(source='salvage_value', max_digits=12, decimal_places=2, read_only=True)
    usefulLifeYears     = serializers.IntegerField(source='useful_life_years', read_only=True)
    depreciationMethod  = serializers.CharField(source='depreciation_method', read_only=True)
    warrantyStartDate   = serializers.DateField(source='warranty_start_date', read_only=True)
    warrantyEndDate     = serializers.DateField(source='warranty_end_date', read_only=True)
    warrantyStatus      = serializers.CharField(source='warranty_status', read_only=True)
    units               = serializers.SerializerMethodField()
    totalQuantity       = serializers.IntegerField(source='total_quantity',       read_only=True)
    availableQuantity   = serializers.IntegerField(source='available_quantity',   read_only=True)
    assignedQuantity    = serializers.IntegerField(source='assigned_quantity',    read_only=True)
    maintenanceQuantity = serializers.IntegerField(source='maintenance_quantity', read_only=True)
    supplier            = serializers.SerializerMethodField()
    department          = serializers.SerializerMethodField()
    location            = serializers.SerializerMethodField()
    currentEmployee     = serializers.SerializerMethodField()
    serialNumber        = serializers.SerializerMethodField()
    status              = serializers.SerializerMethodField()
    createdAt           = serializers.DateTimeField(source='created_at',          read_only=True)
    updatedAt           = serializers.DateTimeField(source='updated_at',          read_only=True)

    class Meta:
        model = Asset
        fields = [
            'id', 'displayId', 'assetId', 'iconKey', 'name', 'category', 'brand', 'model', 'color',
            'purchaseCost', 'purchaseDate', 'salvageValue', 'usefulLifeYears', 'depreciationMethod', 'value',
            'warrantyStartDate', 'warrantyEndDate', 'warrantyStatus',
            'supplier', 'department', 'location', 'currentEmployee', 'serialNumber', 'status',
            'units', 'totalQuantity', 'availableQuantity', 'assignedQuantity', 'maintenanceQuantity',
            'createdAt', 'updatedAt',
        ]

    def get_units(self, obj):
        if not obj.units.exists():
            obj.ensure_default_unit()
        return AssetUnitSerializer(obj.units.all(), many=True).data

    def get_supplier(self, obj):
        first_unit = obj.units.filter(purchase__isnull=False).select_related('purchase__supplier').first()
        if first_unit and first_unit.purchase and first_unit.purchase.supplier:
            return first_unit.purchase.supplier.company or first_unit.purchase.supplier.name
        return None

    def get_department(self, obj):
        first_unit = obj.units.filter(assigned_to__isnull=False).select_related('assigned_to').first()
        if first_unit and first_unit.assigned_to and first_unit.assigned_to.department:
            return first_unit.assigned_to.department
        return None

    def get_location(self, obj):
        first_unit = obj.units.exclude(location='').first()
        if first_unit and first_unit.location:
            return first_unit.location
        return None

    def get_currentEmployee(self, obj):
        first_unit = obj.units.filter(assigned_to__isnull=False).select_related('assigned_to').first()
        if first_unit and first_unit.assigned_to:
            user = first_unit.assigned_to
            name = f"{user.first_name} {user.last_name}".strip()
            return name or user.email
        return None

    def get_serialNumber(self, obj) -> str:
        first_unit = obj.units.first()
        if first_unit:
            if first_unit.display_id and str(first_unit.display_id).startswith('SER-'):
                return str(first_unit.display_id)
            if first_unit.serial_number and str(first_unit.serial_number).startswith('SER-'):
                return str(first_unit.serial_number)
            try:
                from apps.common.utils import generate_display_id
                first_unit.display_id = generate_display_id(first_unit.__class__, 'SER')
                first_unit.serial_number = first_unit.display_id
                first_unit.save(update_fields=['display_id', 'serial_number'])
                return str(first_unit.display_id)
            except Exception:
                return f"SER-{first_unit.unit_number:03d}"
        return ''

    def get_status(self, obj) -> str:
        units = obj.units.all()
        if not units.exists():
            return 'AVAILABLE'
        statuses = set(u.status for u in units)
        if AssetUnit.Status.AVAILABLE in statuses:
            return 'AVAILABLE'
        if AssetUnit.Status.ASSIGNED in statuses:
            return 'ASSIGNED'
        if AssetUnit.Status.MAINTENANCE in statuses:
            return 'MAINTENANCE'
        return 'SCRAPPED'


class AssetDetailSerializer(serializers.ModelSerializer):
    displayId           = serializers.CharField(source='display_id', read_only=True)
    assetId             = serializers.CharField(source='formatted_asset_id', read_only=True)
    iconKey             = serializers.CharField(source='icon_key', read_only=True)
    category            = AssetCategorySerializer(read_only=True)
    purchaseDate        = serializers.DateField(source='purchase_date')
    purchaseCost        = serializers.DecimalField(source='purchase_cost', max_digits=12, decimal_places=2)
    salvageValue        = serializers.DecimalField(source='salvage_value', max_digits=12, decimal_places=2, read_only=True)
    usefulLifeYears     = serializers.IntegerField(source='useful_life_years', read_only=True)
    depreciationMethod  = serializers.CharField(source='depreciation_method', read_only=True)
    warrantyStartDate   = serializers.DateField(source='warranty_start_date', read_only=True)
    warrantyEndDate     = serializers.DateField(source='warranty_end_date', read_only=True)
    warrantyStatus      = serializers.CharField(source='warranty_status', read_only=True)
    techSpecs           = serializers.JSONField(source='tech_specs', required=False)
    financials          = serializers.SerializerMethodField()
    units               = serializers.SerializerMethodField()
    totalQuantity       = serializers.IntegerField(source='total_quantity',       read_only=True)
    availableQuantity   = serializers.IntegerField(source='available_quantity',   read_only=True)
    assignedQuantity    = serializers.IntegerField(source='assigned_quantity',    read_only=True)
    maintenanceQuantity = serializers.IntegerField(source='maintenance_quantity', read_only=True)
    supplier            = serializers.SerializerMethodField()
    department          = serializers.SerializerMethodField()
    location            = serializers.SerializerMethodField()
    currentEmployee     = serializers.SerializerMethodField()
    serialNumber        = serializers.SerializerMethodField()
    status              = serializers.SerializerMethodField()
    createdAt           = serializers.DateTimeField(source='created_at',          read_only=True)
    updatedAt           = serializers.DateTimeField(source='updated_at',          read_only=True)

    class Meta:
        model = Asset
        fields = [
            'id', 'displayId', 'assetId', 'iconKey', 'name', 'category', 'brand', 'model', 'color',
            'purchaseDate', 'purchaseCost', 'salvageValue', 'usefulLifeYears', 'depreciationMethod',
            'warrantyStartDate', 'warrantyEndDate', 'warrantyStatus',
            'supplier', 'department', 'location', 'currentEmployee', 'serialNumber', 'status',
            'techSpecs', 'financials', 'units', 'totalQuantity', 'availableQuantity',
            'assignedQuantity', 'maintenanceQuantity', 'createdAt', 'updatedAt',
        ]

    def get_units(self, obj):
        if not obj.units.exists():
            obj.ensure_default_unit()
        return AssetUnitSerializer(obj.units.all(), many=True).data

    def get_financials(self, obj):
        return FinancialsSerializer(obj).data

    def get_supplier(self, obj):
        first_unit = obj.units.filter(purchase__isnull=False).select_related('purchase__supplier').first()
        if first_unit and first_unit.purchase and first_unit.purchase.supplier:
            return first_unit.purchase.supplier.company or first_unit.purchase.supplier.name
        return None

    def get_department(self, obj):
        first_unit = obj.units.filter(assigned_to__isnull=False).select_related('assigned_to').first()
        if first_unit and first_unit.assigned_to and first_unit.assigned_to.department:
            return first_unit.assigned_to.department
        return None

    def get_location(self, obj):
        first_unit = obj.units.exclude(location='').first()
        if first_unit and first_unit.location:
            return first_unit.location
        return None

    def get_currentEmployee(self, obj):
        first_unit = obj.units.filter(assigned_to__isnull=False).select_related('assigned_to').first()
        if first_unit and first_unit.assigned_to:
            user = first_unit.assigned_to
            name = f"{user.first_name} {user.last_name}".strip()
            return name or user.email
        return None

    def get_serialNumber(self, obj) -> str:
        first_unit = obj.units.first()
        if first_unit:
            if first_unit.display_id and str(first_unit.display_id).startswith('SER-'):
                return str(first_unit.display_id)
            if first_unit.serial_number and str(first_unit.serial_number).startswith('SER-'):
                return str(first_unit.serial_number)
            try:
                from apps.common.utils import generate_display_id
                first_unit.display_id = generate_display_id(first_unit.__class__, 'SER')
                first_unit.serial_number = first_unit.display_id
                first_unit.save(update_fields=['display_id', 'serial_number'])
                return str(first_unit.display_id)
            except Exception:
                return f"SER-{first_unit.unit_number:03d}"
        return ''

    def get_status(self, obj) -> str:
        units = obj.units.all()
        if not units.exists():
            return 'AVAILABLE'
        statuses = set(u.status for u in units)
        if AssetUnit.Status.AVAILABLE in statuses:
            return 'AVAILABLE'
        if AssetUnit.Status.ASSIGNED in statuses:
            return 'ASSIGNED'
        if AssetUnit.Status.MAINTENANCE in statuses:
            return 'MAINTENANCE'
        return 'SCRAPPED'


class AssetWriteSerializer(serializers.ModelSerializer):
    categoryId        = serializers.CharField(source='category')
    brand             = serializers.CharField(required=False, allow_blank=True)
    model             = serializers.CharField(required=False, allow_blank=True)
    color             = serializers.CharField(required=False, allow_blank=True)
    purchaseDate      = serializers.DateField(source='purchase_date', required=False, allow_null=True)
    purchaseCost      = serializers.DecimalField(
        source='purchase_cost', max_digits=12, decimal_places=2,
        required=False, allow_null=True, default=0
    )
    salvageValue      = serializers.DecimalField(source='salvage_value', max_digits=12, decimal_places=2, required=False, default=0)
    usefulLifeYears   = serializers.IntegerField(source='useful_life_years', required=False, default=5)
    depreciationMethod = serializers.CharField(source='depreciation_method', required=False, default='STRAIGHT_LINE')
    warrantyStartDate = serializers.DateField(source='warranty_start_date', required=False, allow_null=True)
    warrantyEndDate   = serializers.DateField(source='warranty_end_date', required=False, allow_null=True)
    techSpecs         = serializers.JSONField(source='tech_specs', required=False)

    class Meta:
        model = Asset
        fields = [
            'name', 'categoryId', 'brand', 'model', 'color',
            'purchaseDate', 'purchaseCost', 'salvageValue', 'usefulLifeYears', 'depreciationMethod',
            'warrantyStartDate', 'warrantyEndDate', 'techSpecs'
        ]

    def validate_categoryId(self, value):
        import uuid as uuid_mod
        try:
            uuid_mod.UUID(str(value))
            cat = AssetCategory.objects.filter(pk=value).first()
            if cat:
                return cat
        except (ValueError, AttributeError):
            pass
        cat = AssetCategory.objects.filter(name__iexact=str(value)).first()
        if cat:
            return cat
        raise serializers.ValidationError(f"Category '{value}' does not exist. Please select a valid category.")

    def create(self, validated_data):
        from apps.depreciation.services import DepreciationService
        validated_data.setdefault('purchase_cost', Decimal('0.00'))
        validated_data.setdefault('salvage_value', Decimal('0.00'))
        validated_data.setdefault('useful_life_years', 5)
        validated_data.setdefault('depreciation_method', 'STRAIGHT_LINE')
        
        calc = DepreciationService.calculate_depreciation(
            purchase_cost=validated_data.get('purchase_cost', Decimal('0.00')),
            salvage_value=validated_data.get('salvage_value', Decimal('0.00')),
            useful_life_years=validated_data.get('useful_life_years', 5),
            purchase_date=validated_data.get('purchase_date')
        )
        validated_data['current_value'] = calc['currentBookValue']
        asset = Asset.objects.create(**validated_data)
        
        # Ensure default physical unit exists for the new asset
        if not asset.units.exists():
            from apps.common.utils import generate_display_id
            disp_id = generate_display_id(AssetUnit, 'SER')
            AssetUnit.objects.create(
                asset=asset,
                unit_number=1,
                display_id=disp_id,
                serial_number=disp_id,
                status=AssetUnit.Status.AVAILABLE,
                location='HQ'
            )
        return asset

    def update(self, instance, validated_data):
        from apps.depreciation.services import DepreciationService
        cost = validated_data.get('purchase_cost', instance.purchase_cost)
        salvage = validated_data.get('salvage_value', instance.salvage_value)
        life = validated_data.get('useful_life_years', instance.useful_life_years)
        p_date = validated_data.get('purchase_date', instance.purchase_date)

        calc = DepreciationService.calculate_depreciation(
            purchase_cost=cost,
            salvage_value=salvage,
            useful_life_years=life,
            purchase_date=p_date
        )
        validated_data['current_value'] = calc['currentBookValue']
        return super().update(instance, validated_data)


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------

class AssignmentListSerializer(serializers.ModelSerializer):
    displayId    = serializers.CharField(source='display_id', read_only=True)
    unitId       = serializers.CharField(source='unit.id', read_only=True)
    parentAssetId = serializers.CharField(source='unit.asset.id', read_only=True, allow_null=True)
    assetId      = serializers.SerializerMethodField()
    serialNumber = serializers.SerializerMethodField()
    assetName    = serializers.SerializerMethodField()
    brand        = serializers.SerializerMethodField()
    model        = serializers.SerializerMethodField()
    location     = serializers.SerializerMethodField()
    employeeId   = serializers.SerializerMethodField()
    assetIcon    = serializers.SerializerMethodField()
    employeeInitials = serializers.SerializerMethodField()
    status       = serializers.SerializerMethodField()
    assignedDate = serializers.DateField(source='assigned_date')
    expectedReturnDate = serializers.DateField(source='expected_return_date', allow_null=True)
    returnedDate = serializers.DateField(source='returned_date', allow_null=True)
    employeeName = serializers.CharField(source='employee_name')
    # Receipt fields — critical for employee confirm-receipt flow
    receiptStatus = serializers.CharField(source='receipt_status', read_only=True)
    receivedAt    = serializers.DateTimeField(source='received_at', read_only=True, allow_null=True)
    unitStatus    = serializers.SerializerMethodField()
    hasActiveMaintenance = serializers.SerializerMethodField()

    class Meta:
        model = AssetAssignmentHistory
        fields = [
            'id', 'displayId', 'unitId', 'parentAssetId', 'assetId', 'serialNumber', 'assetName', 'brand', 'model',
            'employeeName', 'employeeId', 'employeeInitials', 'department', 'location',
            'assignedDate', 'expectedReturnDate', 'returnedDate', 'status', 'notes', 'assetIcon',
            'receiptStatus', 'receivedAt', 'unitStatus', 'hasActiveMaintenance',
        ]

    def get_assetId(self, obj) -> str:
        if obj.unit and obj.unit.asset:
            return obj.unit.asset.display_id or obj.unit.asset.formatted_asset_id
        return ''

    def get_serialNumber(self, obj) -> str:
        if obj.unit:
            if obj.unit.display_id and str(obj.unit.display_id).startswith('SER-'):
                return str(obj.unit.display_id)
            if obj.unit.serial_number and str(obj.unit.serial_number).startswith('SER-'):
                return str(obj.unit.serial_number)
            try:
                from apps.common.utils import generate_display_id
                obj.unit.display_id = generate_display_id(obj.unit.__class__, 'SER')
                obj.unit.serial_number = obj.unit.display_id
                obj.unit.save(update_fields=['display_id', 'serial_number'])
                return str(obj.unit.display_id)
            except Exception:
                return f"SER-{obj.unit.unit_number:03d}"
        snap = obj.unit_serial_snapshot or ''
        if snap.startswith('SER-'):
            return snap
        return 'SER-001' if snap else '—'

    def get_assetName(self, obj) -> str:
        if obj.unit and obj.unit.asset:
            return obj.unit.asset.name
        return obj.asset_name_snapshot or 'Asset'

    def get_brand(self, obj) -> str:
        if obj.unit and obj.unit.asset:
            return obj.unit.asset.brand or ''
        return ''

    def get_model(self, obj) -> str:
        if obj.unit and obj.unit.asset:
            return obj.unit.asset.model or ''
        return ''

    def get_location(self, obj) -> str:
        if obj.unit and obj.unit.location:
            return obj.unit.location
        if obj.user and obj.user.location:
            return obj.user.location
        return 'HQ'

    def get_employeeId(self, obj) -> str:
        if obj.user and getattr(obj.user, 'employee_id', None):
            return obj.user.employee_id
        return ''

    def get_assetIcon(self, obj) -> str:
        if obj.unit and obj.unit.asset.category:
            return obj.unit.asset.category.name.lower()
        return 'device'

    def get_employeeInitials(self, obj) -> str:
        name = (obj.employee_name or '').strip()
        if not name:
            return '?'
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[-1][0]}".upper()
        return name[:2].upper()

    def get_status(self, obj) -> str:
        return 'Assigned' if obj.status == AssetAssignmentHistory.Status.ACTIVE else 'Returned'

    def get_unitStatus(self, obj) -> str:
        if obj.unit:
            return obj.unit.status
        return ''

    def get_hasActiveMaintenance(self, obj) -> bool:
        if not obj.unit:
            return False
        if obj.unit.status == 'MAINTENANCE':
            return True
        from apps.maintenance.models import MaintenanceRequest
        return MaintenanceRequest.objects.filter(
            asset_unit=obj.unit
        ).exclude(
            status__in=['RESOLVED', 'COMPLETED', 'VERIFIED', 'CANCELLED', 'UNREPAIRABLE', 'NOT_REPAIRABLE']
        ).exists()


def is_valid_uuid(val):
    if not val:
        return False
    try:
        uuid.UUID(str(val).strip())
        return True
    except Exception:
        return False


class AssignmentWriteSerializer(serializers.Serializer):
    unitId             = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    assetId            = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    employeeId         = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    employeeName       = serializers.CharField(source='employee_name', required=False, allow_blank=True)
    department         = serializers.CharField(required=False, allow_blank=True)
    location           = serializers.CharField(required=False, allow_blank=True)
    assignedDate       = serializers.DateField(source='assigned_date', required=False)
    expectedReturnDate = serializers.DateField(source='expected_return_date', required=False, allow_null=True)
    notes              = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        from apps.users.models import User
        init_data = getattr(self, 'initial_data', {}) or {}
        unit_id_input = attrs.get('unitId') or init_data.get('unitId') or init_data.get('unit_id')
        asset_id_input = attrs.get('assetId') or init_data.get('assetId') or init_data.get('asset_id')

        def resolve_unit(raw_id):
            if not raw_id:
                return None
            target_str = str(raw_id).strip()

            if '-unit-' in target_str:
                parts = target_str.split('-unit-')
                asset_part, unit_part = parts[0], parts[1]
                if is_valid_uuid(unit_part):
                    u = AssetUnit.objects.filter(pk=unit_part).first()
                    if u:
                        return u
                if is_valid_uuid(asset_part):
                    u = AssetUnit.objects.filter(asset_id=asset_part, status=AssetUnit.Status.AVAILABLE).first() or AssetUnit.objects.filter(asset_id=asset_part).first()
                    if u:
                        return u

            if is_valid_uuid(target_str):
                u = AssetUnit.objects.filter(pk=target_str).first()
                if u:
                    return u
                u = AssetUnit.objects.filter(asset_id=target_str, status=AssetUnit.Status.AVAILABLE).first() or AssetUnit.objects.filter(asset_id=target_str).first()
                if u:
                    return u

            u = AssetUnit.objects.filter(serial_number__iexact=target_str).first()
            if u:
                return u

            for asset in Asset.objects.all():
                if asset.formatted_asset_id.upper() == target_str.upper():
                    u = AssetUnit.objects.filter(asset=asset, status=AssetUnit.Status.AVAILABLE).first() or AssetUnit.objects.filter(asset=asset).first()
                    if not u:
                        next_num = AssetUnit.objects.filter(asset=asset).count() + 1
                        from apps.common.utils import generate_display_id
                        disp_id = generate_display_id(AssetUnit, 'SER')
                        u = AssetUnit.objects.create(
                            asset=asset,
                            unit_number=next_num,
                            display_id=disp_id,
                            serial_number=disp_id,
                            status=AssetUnit.Status.AVAILABLE,
                            location='HQ'
                        )
                    return u

            return None

        unit = resolve_unit(unit_id_input) or resolve_unit(asset_id_input)

        if not unit:
            target_asset_id = asset_id_input or unit_id_input
            if target_asset_id and is_valid_uuid(str(target_asset_id)):
                asset_obj = Asset.objects.filter(pk=target_asset_id).first()
                if asset_obj:
                    next_num = AssetUnit.objects.filter(asset=asset_obj).count() + 1
                    from apps.common.utils import generate_display_id
                    disp_id = generate_display_id(AssetUnit, 'SER')
                    unit = AssetUnit.objects.create(
                        asset=asset_obj,
                        unit_number=next_num,
                        display_id=disp_id,
                        serial_number=disp_id,
                        status=AssetUnit.Status.AVAILABLE,
                        location='HQ'
                    )

        if not unit:
            raise serializers.ValidationError({"unitId": "A valid asset unit is required for assignment."})

        if unit.status == AssetUnit.Status.SCRAPPED:
            raise serializers.ValidationError({"unitId": "Cannot assign a scrapped or retired asset."})

        attrs['unit'] = unit

        emp_id = attrs.get('employeeId') or init_data.get('employeeId') or init_data.get('user_id')
        user_obj = None

        if emp_id:
            emp_str = str(emp_id).strip()
            user_obj = User.objects.filter(employee_id__iexact=emp_str).first()
            if not user_obj and is_valid_uuid(emp_str):
                user_obj = User.objects.filter(pk=emp_str).first()

        if not user_obj:
            emp_name = attrs.get('employee_name') or init_data.get('employeeName') or init_data.get('employee_name')
            if emp_name:
                emp_name = str(emp_name).strip()
                user_obj = User.objects.filter(first_name__iexact=emp_name).first()
                if not user_obj and ' ' in emp_name:
                    parts = emp_name.split()
                    user_obj = User.objects.filter(first_name__iexact=parts[0], last_name__iexact=parts[-1]).first()

        if user_obj:
            attrs['user'] = user_obj
            attrs['user_id'] = user_obj.pk
            if not attrs.get('employee_name'):
                full_name = f"{user_obj.first_name} {user_obj.last_name}".strip()
                attrs['employee_name'] = full_name or user_obj.email
            if not attrs.get('department') and user_obj.department:
                attrs['department'] = user_obj.department

        if not attrs.get('employee_name'):
            emp_name = init_data.get('employeeName') or init_data.get('employee_name')
            if emp_name:
                attrs['employee_name'] = str(emp_name).strip()

        return attrs


class AssignmentTransferSerializer(serializers.Serializer):
    employeeId   = serializers.UUIDField(required=False, allow_null=True)
    employeeName = serializers.CharField(required=True)
    department   = serializers.CharField(required=False, allow_blank=True, default='')
    transferDate = serializers.DateField(required=False, allow_null=True)
    notes        = serializers.CharField(required=False, allow_blank=True, default='')
AssignmentSerializer = AssignmentListSerializer

# ------------------------------------------------------------------
# Asset Request Serializers
# ------------------------------------------------------------------
from .models import AssetRequest

class AssetRequestSerializer(serializers.ModelSerializer):
    requestNumber = serializers.CharField(source='request_number', read_only=True)
    employeeId = serializers.CharField(source='employee.id', read_only=True)
    employeeName = serializers.CharField(source='employee_name', read_only=True)
    categoryName = serializers.CharField(source='category_name')
    requestedAsset = serializers.CharField(source='requested_asset')
    rejectionReason = serializers.CharField(source='rejection_reason', read_only=True)
    assignedUnitId = serializers.CharField(source='assigned_unit.id', read_only=True, allow_null=True)
    assignedUnitSerial = serializers.CharField(source='assigned_unit.serial_number', read_only=True, allow_null=True)
    assignedUnitName = serializers.SerializerMethodField()
    approvedAt = serializers.DateTimeField(source='approved_at', read_only=True)
    assignedAt = serializers.DateTimeField(source='assigned_at', read_only=True)
    receivedAt = serializers.DateTimeField(source='received_at', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = AssetRequest
        fields = [
            'id', 'requestNumber', 'employeeId', 'employeeName', 'department',
            'categoryName', 'requestedAsset', 'reason', 'priority', 'notes',
            'status', 'rejectionReason', 'assignedUnitId', 'assignedUnitSerial',
            'assignedUnitName', 'approvedAt', 'assignedAt', 'receivedAt', 'createdAt'
        ]

    def get_assignedUnitName(self, obj) -> str:
        if obj.assigned_unit and obj.assigned_unit.asset:
            return obj.assigned_unit.asset.name
        return ''


class AssetRequestCreateSerializer(serializers.ModelSerializer):
    categoryName = serializers.CharField(source='category_name', required=False)
    category_name = serializers.CharField(required=False)
    requestedAsset = serializers.CharField(source='requested_asset', required=False)
    requested_asset = serializers.CharField(required=False)
    unitId = serializers.CharField(required=False, allow_null=True)
    unit_id = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = AssetRequest
        fields = ['categoryName', 'category_name', 'requestedAsset', 'requested_asset', 'reason', 'priority', 'notes', 'unitId', 'unit_id']

    def validate(self, data):
        cat = data.get('category_name')
        req_asset = data.get('requested_asset')
        if not cat:
            data['category_name'] = 'General'
        if not req_asset:
            raise serializers.ValidationError({'requestedAsset': 'Requested asset description is required.'})
        return data


class AssetRequestAssignSerializer(serializers.Serializer):
    unit_id = serializers.CharField()

    def validate_unit_id(self, value):
        import uuid
        val_str = str(value).strip()
        if '-unit-' in val_str:
            val_str = val_str.split('-unit-')[-1]
        try:
            return uuid.UUID(val_str)
        except (ValueError, AttributeError):
            raise serializers.ValidationError('Must be a valid UUID.')


class ConfirmReceiptSerializer(serializers.Serializer):
    condition = serializers.CharField(required=False, default='Good Condition')
    notes = serializers.CharField(required=False, allow_blank=True, default='')
