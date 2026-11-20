import uuid
from decimal import Decimal

from django.db import models

from apps.assets.models import Asset


class Supplier(models.Model):
    """Matches frontend Supplier interface."""
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    name = models.CharField(max_length=200, blank=True, default='')
    company = models.CharField(max_length=200)
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    address = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    # Flexible custom fields
    specifications = models.JSONField(blank=True, null=True, default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suppliers'
        ordering = ['company']

    def __str__(self):
        return f"{self.company} ({self.display_id or self.name})"

    def save(self, *args, **kwargs):
        if not self.display_id:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(Supplier, 'SUP')
        super().save(*args, **kwargs)

    @property
    def total_purchases(self) -> int:
        return self.purchases.count()

    @property
    def total_amount(self) -> Decimal:
        total = Decimal('0.00')
        for purchase in self.purchases.all():
            total += purchase.total_amount
        return total


class Purchase(models.Model):
    """
    Matches frontend Purchase interface.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class PaymentStatus(models.TextChoices):
        UNPAID = 'UNPAID', 'Unpaid'
        PARTIAL = 'PARTIAL', 'Partial'
        PAID = 'PAID', 'Paid'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    purchase_number = models.CharField(max_length=50, unique=True, db_index=True)  # e.g. "PO-2026-001"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='purchases')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchases')

    quantity = models.PositiveIntegerField(default=1)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)  # price per unit
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # per unit, optional

    purchase_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'purchases'
        ordering = ['-purchase_date', '-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['asset']),
            models.Index(fields=['supplier']),
        ]

    def __str__(self):
        return f"{self.display_id or self.purchase_number} - {self.asset.name} x{self.quantity}"

    def save(self, *args, **kwargs):
        if not self.display_id:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(Purchase, 'PO')
        if not self.purchase_number:
            self.purchase_number = self._generate_purchase_number()
        super().save(*args, **kwargs)

    def _generate_purchase_number(self) -> str:
        year = self.purchase_date.year if self.purchase_date else 2026
        prefix = f'PO-{year}-'
        existing_numbers = set(
            Purchase.objects.filter(purchase_number__startswith=prefix)
            .values_list('purchase_number', flat=True)
        )
        max_num = 0
        for num_str in existing_numbers:
            if not num_str:
                continue
            suffix = num_str[len(prefix):]
            if suffix.isdigit():
                val = int(suffix)
                if val > max_num:
                    max_num = val
        next_num = max_num + 1
        candidate = f'{prefix}{next_num:03d}'
        while candidate in existing_numbers:
            next_num += 1
            candidate = f'{prefix}{next_num:03d}'
        return candidate

    @property
    def total_amount(self) -> Decimal:
        return self.purchase_price * self.quantity

    @property
    def paid_amount(self) -> Decimal:
        total = Decimal('0.00')
        for payment in self.payments.all():
            total += payment.amount
        return total

    @property
    def remaining_amount(self) -> Decimal:
        return max(Decimal('0.00'), self.total_amount - self.paid_amount)

    @property
    def payment_status(self) -> str:
        remaining = self.remaining_amount
        if remaining <= Decimal('0.00'):
            return self.PaymentStatus.PAID
        if self.paid_amount > Decimal('0.00'):
            return self.PaymentStatus.PARTIAL
        return self.PaymentStatus.UNPAID


class Payment(models.Model):
    """
    Individual installment against a Purchase.
    """
    class Method(models.TextChoices):
        CASH = 'CASH', 'Cash'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
        CHEQUE = 'CHEQUE', 'Cheque'
        MOBILE_WALLET = 'MOBILE_WALLET', 'Mobile Wallet'
        ONLINE = 'ONLINE', 'Online'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='payments')

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    method = models.CharField(max_length=30, choices=Method.choices, default=Method.BANK_TRANSFER)
    reference = models.CharField(max_length=100, blank=True, default='')  # transaction id / reference
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True, null=True, blank=True)
    payment_details = models.JSONField(blank=True, null=True, default=dict)
    notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'purchase_payments'
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.display_id or self.invoice_number} - {self.amount} on {self.payment_date}"

    def save(self, *args, **kwargs):
        if not self.display_id:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(Payment, 'PAY')
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)

    def _generate_invoice_number(self) -> str:
        year = self.payment_date.year if self.payment_date else 2026
        prefix = f'INV-{year}-'
        existing_numbers = set(
            Payment.objects.filter(invoice_number__startswith=prefix)
            .values_list('invoice_number', flat=True)
        )
        max_num = 0
        for num_str in existing_numbers:
            if not num_str:
                continue
            suffix = num_str[len(prefix):]
            if suffix.isdigit():
                val = int(suffix)
                if val > max_num:
                    max_num = val
        next_num = max_num + 1
        candidate = f'{prefix}{next_num:04d}'
        while candidate in existing_numbers:
            next_num += 1
            candidate = f'{prefix}{next_num:04d}'
        return candidate
