import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class AssetCategory(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'asset_categories'
        verbose_name_plural = 'Asset Categories'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.display_id})" if self.display_id else self.name

    def save(self, *args, **kwargs):
        if not self.display_id:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(AssetCategory, 'CAT')
        super().save(*args, **kwargs)


class Asset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)

    name = models.CharField(max_length=255)
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name='assets')

    brand = models.CharField(max_length=100, blank=True, default='')
    model = models.CharField(max_length=100, blank=True, default='')
    color = models.CharField(max_length=50, blank=True, default='')
    warranty_start_date = models.DateField(null=True, blank=True)
    warranty_end_date = models.DateField(null=True, blank=True)

    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2)
    current_value = models.DecimalField(max_digits=12, decimal_places=2)

    salvage_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    useful_life_years = models.PositiveIntegerField(default=5)
    depreciation_method = models.CharField(max_length=50, default='STRAIGHT_LINE')

    tech_specs = models.JSONField(blank=True, null=True, default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assets'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['category'])]

    def __str__(self):
        return f'{self.name} ({self.display_id or self.id})'

    def save(self, *args, **kwargs):
        if not self.display_id:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(Asset, 'AST')
        super().save(*args, **kwargs)

    def ensure_default_unit(self):
        if not self.units.exists():
            from apps.common.utils import generate_display_id
            disp_id = generate_display_id(AssetUnit, 'SER')
            return AssetUnit.objects.create(
                asset=self,
                unit_number=1,
                display_id=disp_id,
                serial_number=disp_id,
                status=AssetUnit.Status.AVAILABLE,
                location='HQ'
            )
        return self.units.first()

    @property
    def formatted_asset_id(self) -> str:
        if self.display_id and str(self.display_id).startswith('AST-'):
            return self.display_id
        try:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(Asset, 'AST')
            self.save(update_fields=['display_id'])
            return self.display_id
        except Exception:
            s = str(self.id).replace('-', '').upper()
            return f'AST-{s[:3]}'

    # Auto icon detection
    _ICON_KEYWORD_MAP = [
        # Computers & peripherals
        (['laptop', 'notebook'],                          'laptop_mac'),
        (['desktop', 'pc', 'computer', 'workstation'],   'computer'),
        (['server', 'rack'],                              'dns'),
        (['tablet', 'ipad', 'tab'],                      'tablet'),
        # Displays
        (['monitor', 'screen', 'display'],                'monitor'),
        (['projector'],                                   'video_projector'),
        # Mobile & communication
        (['phone', 'mobile', 'smartphone', 'iphone'],    'smartphone'),
        (['headphone', 'headset', 'earphone'],            'headphones'),
        (['walkie'],                                      'radio'),
        # Printing & scanning
        (['printer', 'print'],                            'print'),
        (['scanner', 'scan'],                             'document_scanner'),
        (['copier', 'photocopy'],                         'content_copy'),
        # Audio & video
        (['speaker', 'audio', 'sound'],                  'speaker'),
        (['camera', 'webcam', 'cctv'],                   'photo_camera'),
        (['tv', 'television'],                            'tv'),
        # Input devices
        (['keyboard'],                                    'keyboard'),
        (['mouse'],                                       'mouse'),
        # Networking
        (['router', 'switch', 'network', 'wifi', 'hub'], 'router'),
        (['ups', 'battery', 'power'],                    'battery_charging_full'),
        # Furniture & fixtures
        (['chair', 'seat'],                               'chair'),
        (['desk', 'table'],                               'table_restaurant'),
        (['cabinet', 'locker', 'rack', 'shelf'],          'shelves'),
        (['sofa', 'couch'],                               'weekend'),
        # Vehicles
        (['car', 'vehicle', 'truck', 'van', 'bike'],     'directions_car'),
        # Tools & equipment
        (['tool', 'drill', 'machine'],                   'handyman'),
        (['ac', 'air condition', 'hvac', 'heater', 'fan'], 'ac_unit'),
        (['refrigerator', 'fridge'],                     'kitchen'),
        # Storage
        (['hard disk', 'ssd', 'storage', 'usb', 'pen drive', 'flash'], 'storage'),
        (['cable', 'wire'],                               'cable'),
        # Safety
        (['cctv', 'security', 'alarm'],                  'security'),
        (['fire extinguisher'],                           'fire_extinguisher'),
    ]

    @property
    def icon_key(self) -> str:
        """Auto-detect icon name from asset name and category. No DB column - always computed."""
        search_text = ' '.join([
            (self.name or '').lower(),
            (self.category.name if self.category else '').lower(),
            (self.brand or '').lower(),
            (self.model or '').lower(),
        ])
        for keywords, icon in self._ICON_KEYWORD_MAP:
            if any(kw in search_text for kw in keywords):
                return icon
        return 'inventory_2'  # generic fallback

    @property
    def warranty_status(self) -> str:
        if not self.warranty_start_date or not self.warranty_end_date:
            return 'No Warranty'
        from datetime import date
        today = date.today()
        if today > self.warranty_end_date:
            return 'Expired'
        diff = (self.warranty_end_date - today).days
        if diff <= 30:
            return 'Expiring Soon'
        return 'Active' 

    @property
    def depreciation_percent(self) -> Decimal:
        if not self.purchase_cost:
            return Decimal('0.00')
        diff = self.purchase_cost - self.current_value
        return round((diff / self.purchase_cost) * 100, 2)

    @property
    def total_quantity(self) -> int:
        return self.units.count()

    @property
    def available_quantity(self) -> int:
        return self.units.filter(status=AssetUnit.Status.AVAILABLE).count()

    @property
    def assigned_quantity(self) -> int:
        return self.units.filter(status=AssetUnit.Status.ASSIGNED).count()

    @property
    def maintenance_quantity(self) -> int:
        return self.units.filter(status=AssetUnit.Status.MAINTENANCE).count()


class AssetUnit(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        ASSIGNED = 'ASSIGNED', 'Assigned'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        SCRAPPED = 'SCRAPPED', 'Scrapped'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='units')

    unit_number = models.PositiveIntegerField()
    serial_number = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    location = models.CharField(max_length=150, blank=True, default='')

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_units'
    )

    purchase = models.ForeignKey(
        'purchases.Purchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_units'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_units'
        ordering = ['asset', 'unit_number']
        unique_together = [('asset', 'unit_number')]
        indexes = [models.Index(fields=['status'])]

    def __str__(self):
        return f'{self.asset.name} - Unit #{self.unit_number} ({self.serial_number})'

    def save(self, *args, **kwargs):
        if not self.display_id or not str(self.display_id).startswith('SER-'):
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(AssetUnit, 'SER')
        if not self.serial_number or not str(self.serial_number).startswith('SER-'):
            self.serial_number = self.display_id
        super().save(*args, **kwargs)


class AssetAssignmentHistory(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        RETURNED = 'RETURNED', 'Returned'

    class ReceiptStatus(models.TextChoices):
        PENDING_RECEIPT = 'PENDING_RECEIPT', 'Pending Receipt'
        RECEIVED = 'RECEIVED', 'Received'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    unit = models.ForeignKey(AssetUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='assignment_history')
    asset_name_snapshot = models.CharField(max_length=255, blank=True, default='')
    unit_serial_snapshot = models.CharField(max_length=100, blank=True, default='')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_assignments'
    )
    employee_name = models.CharField(max_length=200)
    department = models.CharField(max_length=100, blank=True, default='')

    assigned_date = models.DateField()
    expected_return_date = models.DateField(null=True, blank=True)
    returned_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    receipt_status = models.CharField(max_length=30, choices=ReceiptStatus.choices, default=ReceiptStatus.PENDING_RECEIPT)
    received_at = models.DateTimeField(null=True, blank=True)
    received_condition = models.CharField(max_length=50, blank=True, default='Good Condition')
    receipt_notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'asset_assignment_history'
        ordering = ['-assigned_date']

    def __str__(self):
        return f'{self.display_id or self.unit_serial_snapshot} -> {self.employee_name} ({self.status})'

    def save(self, *args, **kwargs):
        if not self.display_id:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(AssetAssignmentHistory, 'ASG')
        if self.unit:
            if not self.unit_serial_snapshot:
                self.unit_serial_snapshot = self.unit.serial_number
            if self.unit.asset and not self.asset_name_snapshot:
                self.asset_name_snapshot = self.unit.asset.name
        super().save(*args, **kwargs)


class AssetRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        ASSIGNED = 'ASSIGNED', 'Assigned'
        RECEIVED = 'RECEIVED', 'Received'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        NORMAL = 'NORMAL', 'Normal'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    request_number = models.CharField(max_length=50, unique=True, db_index=True)

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='asset_requests'
    )
    employee_name = models.CharField(max_length=200, blank=True, default='')
    department = models.CharField(max_length=150, blank=True, default='')

    category_name = models.CharField(max_length=150)
    requested_asset = models.CharField(max_length=255)
    reason = models.TextField()
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    notes = models.TextField(blank=True, default='')

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    rejection_reason = models.TextField(blank=True, default='')

    assigned_unit = models.ForeignKey(
        AssetUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asset_requests'
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_asset_requests'
    )

    approved_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asset_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.display_id or self.request_number} - {self.requested_asset} ({self.status})'

    def save(self, *args, **kwargs):
        if not self.display_id:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(AssetRequest, 'REQ')
        if not self.request_number:
            self.request_number = self.display_id
        super().save(*args, **kwargs)
