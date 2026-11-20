from rest_framework import serializers

from apps.assets.models import Asset
from apps.assets.serializers import AssetCategorySerializer
from .models import Supplier, Purchase, Payment



class SupplierSerializer(serializers.ModelSerializer):
    displayId = serializers.CharField(source='display_id', read_only=True)
    totalPurchases = serializers.IntegerField(source='total_purchases', read_only=True)
    totalAmount = serializers.DecimalField(source='total_amount', max_digits=12, decimal_places=2, read_only=True)
    specifications = serializers.JSONField(required=False)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Supplier
        fields = [
            'id', 'displayId', 'name', 'company', 'email', 'phone', 'address', 'status',
            'specifications', 'totalPurchases', 'totalAmount', 'createdAt', 'updatedAt',
        ]


class SupplierWriteSerializer(serializers.ModelSerializer):
    specifications = serializers.JSONField(required=False)

    class Meta:
        model = Supplier
        fields = ['name', 'company', 'email', 'phone', 'address', 'status', 'specifications']


# ---------------------------------------------------------------------------
# Payment (nested inside Purchase, and standalone create)
# ---------------------------------------------------------------------------

class PaymentSerializer(serializers.ModelSerializer):
    displayId = serializers.CharField(source='display_id', read_only=True)
    paymentDate = serializers.DateField(source='payment_date')
    invoiceNumber = serializers.CharField(source='invoice_number', read_only=True)
    paymentDetails = serializers.JSONField(source='payment_details', required=False)
    purchaseNumber = serializers.CharField(source='purchase.purchase_number', read_only=True)
    purchaseId = serializers.UUIDField(source='purchase.id', read_only=True)
    totalAmount = serializers.SerializerMethodField()
    paidAmount = serializers.SerializerMethodField()
    remainingAmount = serializers.SerializerMethodField()
    purchaseTotalAmount = serializers.SerializerMethodField()
    purchasePaidAmount = serializers.SerializerMethodField()
    purchaseRemainingAmount = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id', 'displayId', 'amount', 'paymentDate', 'method', 'reference', 'invoiceNumber',
            'paymentDetails', 'notes', 'purchaseId', 'purchaseNumber',
            'totalAmount', 'paidAmount', 'remainingAmount',
            'purchaseTotalAmount', 'purchasePaidAmount', 'purchaseRemainingAmount',
        ]

    def get_totalAmount(self, obj):
        return float(obj.purchase.total_amount) if obj.purchase else float(obj.amount)

    def get_paidAmount(self, obj):
        return float(obj.amount)

    def get_purchaseTotalAmount(self, obj):
        return float(obj.purchase.total_amount) if obj.purchase else float(obj.amount)

    def get_purchasePaidAmount(self, obj):
        return float(obj.purchase.paid_amount) if obj.purchase else float(obj.amount)

    def get_purchaseRemainingAmount(self, obj):
        return float(obj.purchase.remaining_amount) if obj.purchase else 0.0

    def get_remainingAmount(self, obj):
        if not obj.purchase:
            return 0.0
        from django.db import models
        earlier_sum = obj.purchase.payments.filter(
            models.Q(payment_date__lt=obj.payment_date) |
            models.Q(payment_date=obj.payment_date, created_at__lte=obj.created_at)
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        rem = float(obj.purchase.total_amount) - float(earlier_sum)
        return max(0.0, round(rem, 2))


class PaymentCreateSerializer(serializers.ModelSerializer):
    paymentDate = serializers.DateField(source='payment_date')
    paymentDetails = serializers.JSONField(source='payment_details', required=False)

    class Meta:
        model = Payment
        fields = ['amount', 'paymentDate', 'method', 'reference', 'paymentDetails', 'notes']


# ---------------------------------------------------------------------------
# Asset search (lightweight — used in the purchase-create form's asset picker)
# ---------------------------------------------------------------------------

class AssetSearchResultSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the purchase-create asset picker."""
    category = serializers.CharField(source='category.name')

    class Meta:
        model = Asset
        fields = ['id', 'name', 'category']


# ---------------------------------------------------------------------------
# Purchase — read shape (matches frontend Purchase interface exactly)
# ---------------------------------------------------------------------------

class PurchaseSerializer(serializers.ModelSerializer):
    displayId = serializers.CharField(source='display_id', read_only=True)
    purchaseNumber = serializers.CharField(source='purchase_number', read_only=True)
    asset = AssetSearchResultSerializer(read_only=True)
    supplier = SupplierSerializer(read_only=True)

    purchasePrice = serializers.DecimalField(source='purchase_price', max_digits=12, decimal_places=2)
    salePrice = serializers.DecimalField(
        source='sale_price', max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    totalAmount = serializers.DecimalField(source='total_amount', max_digits=12, decimal_places=2, read_only=True)
    paidAmount = serializers.DecimalField(source='paid_amount', max_digits=12, decimal_places=2, read_only=True)
    remainingAmount = serializers.DecimalField(
        source='remaining_amount', max_digits=12, decimal_places=2, read_only=True
    )
    paymentStatus = serializers.CharField(source='payment_status', read_only=True)
    purchaseDate = serializers.DateField(source='purchase_date')

    payments = PaymentSerializer(many=True, read_only=True)

    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Purchase
        fields = [
            'id', 'displayId', 'purchaseNumber', 'asset', 'supplier', 'quantity',
            'purchasePrice', 'salePrice', 'totalAmount', 'paidAmount',
            'remainingAmount', 'purchaseDate', 'status', 'paymentStatus',
            'notes', 'payments', 'createdAt', 'updatedAt',
        ]


class AssetPrimaryKeyField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        if isinstance(data, str) and '-unit-' in data:
            data = data.split('-unit-')[0]
        return super().to_internal_value(data)


# ---------------------------------------------------------------------------
# Purchase — write shape (create / update)
# ---------------------------------------------------------------------------

class PurchaseWriteSerializer(serializers.ModelSerializer):
    assetId = AssetPrimaryKeyField(source='asset', queryset=Asset.objects.all())
    supplierId = serializers.PrimaryKeyRelatedField(source='supplier', queryset=Supplier.objects.all())
    purchasePrice = serializers.DecimalField(source='purchase_price', max_digits=12, decimal_places=2)
    salePrice = serializers.DecimalField(
        source='sale_price', max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    purchaseDate = serializers.DateField(source='purchase_date')

    # Optional initial payment at creation time (maps to a Payment row)
    paidAmount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0, write_only=True
    )
    paymentMethod = serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    paymentDetails = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = Purchase
        fields = [
            'assetId', 'supplierId', 'quantity', 'purchasePrice', 'salePrice',
            'paidAmount', 'paymentMethod', 'paymentDetails', 'purchaseDate', 'status', 'notes',
        ]