from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Supplier, Purchase, Payment


class SupplierService:
    @staticmethod
    def list_suppliers():
        return Supplier.objects.all()

    @staticmethod
    def get_supplier(pk):
        return get_object_or_404(Supplier, pk=pk)

    @staticmethod
    def create_supplier(validated_data) -> Supplier:
        return Supplier.objects.create(**validated_data)

    @staticmethod
    def update_supplier(supplier: Supplier, validated_data) -> Supplier:
        for field, value in validated_data.items():
            setattr(supplier, field, value)
        supplier.save()
        return supplier

    @staticmethod
    def delete_supplier(supplier: Supplier) -> None:
        supplier.delete()


class PurchaseService:
    @staticmethod
    def list_purchases(status=None, supplier_id=None, payment_status=None, search=None):
        queryset = Purchase.objects.select_related('asset', 'supplier').prefetch_related('payments')

        if status:
            queryset = queryset.filter(status=status)
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        if search:
            queryset = queryset.filter(purchase_number__icontains=search)

        if payment_status:
            queryset = [p for p in queryset if p.payment_status == payment_status.upper()]

        return queryset

    @staticmethod
    def get_purchase(pk):
        return get_object_or_404(
            Purchase.objects.select_related('asset', 'supplier').prefetch_related('payments'),
            pk=pk
        )

    @staticmethod
    @transaction.atomic
    def create_purchase(validated_data, request=None) -> Purchase:
        initial_paid_amount = validated_data.pop('paidAmount', Decimal('0.00'))
        payment_method = validated_data.pop('paymentMethod', None) or Payment.Method.BANK_TRANSFER
        payment_details = validated_data.pop('paymentDetails', {}) or {}

        purchase = Purchase.objects.create(**validated_data)

        # Create AssetUnits for this purchase
        from apps.assets.services import AssetService
        AssetService.create_units(
            asset=purchase.asset,
            quantity=purchase.quantity,
            purchase=purchase
        )

        # Determine reference and payment date from details if available
        reference = (
            payment_details.get('transactionReference') or
            payment_details.get('transactionId') or
            payment_details.get('chequeNumber') or
            ''
        )
        from django.utils.dateparse import parse_date
        raw_pay_date = payment_details.get('paymentDate')
        if raw_pay_date and isinstance(raw_pay_date, str):
            pay_date = parse_date(raw_pay_date.split('T')[0]) or purchase.purchase_date
        elif raw_pay_date:
            pay_date = raw_pay_date
        else:
            pay_date = purchase.purchase_date

        if (initial_paid_amount and initial_paid_amount > Decimal('0.00')) or payment_details:
            Payment.objects.create(
                purchase=purchase,
                amount=initial_paid_amount if initial_paid_amount > Decimal('0.00') else purchase.total_amount,
                payment_date=pay_date,
                method=payment_method,
                reference=reference,
                payment_details=payment_details,
            )

        try:
            from apps.audit.services import AuditLogService
            AuditLogService.log_action(
                action='ASSET_PURCHASED',
                module='PURCHASES',
                asset=purchase.asset,
                asset_name=purchase.asset.name if purchase.asset else '',
                description=f"Purchased {purchase.quantity} physical units of '{purchase.asset.name if purchase.asset else 'Asset'}' under PO {purchase.purchase_number}.",
                new_value={
                    'purchase_number': purchase.purchase_number,
                    'quantity': purchase.quantity,
                    'total_cost': str(purchase.total_amount)
                },
                request=request
            )
        except Exception:
            pass

        try:
            from apps.notifications.services import create_system_notification
            asset_name = purchase.asset.name if purchase.asset else 'Asset'
            create_system_notification(
                title='Asset Purchased',
                message=f"Purchased {purchase.quantity} physical unit(s) of '{asset_name}' (PO: {purchase.purchase_number}).",
                notification_type='ASSETS',
                sub_type='ASSET_PURCHASED',
                related_asset_id=purchase.asset.id if purchase.asset else None,
                related_asset_name=asset_name
            )
        except Exception as e:
            pass

        return purchase

    @staticmethod
    def update_purchase(purchase: Purchase, validated_data) -> Purchase:
        validated_data.pop('paidAmount', None)
        for field, value in validated_data.items():
            setattr(purchase, field, value)
        purchase.save()
        return purchase

    @staticmethod
    def delete_purchase(purchase: Purchase) -> None:
        purchase.delete()

    @staticmethod
    def add_payment(purchase: Purchase, payment_data) -> Payment:
        return Payment.objects.create(purchase=purchase, **payment_data)

    @staticmethod
    @transaction.atomic
    def add_supplier_payment(supplier, payment_data) -> list:
        from decimal import Decimal
        amount_to_allocate = Decimal(str(payment_data.get('amount', 0)))
        payment_date = payment_data.get('payment_date')
        method = payment_data.get('method', Payment.Method.CASH)
        reference = payment_data.get('reference', '')
        notes = payment_data.get('notes', '')

        # Get all completed purchases for the supplier
        all_completed = Purchase.objects.filter(
            supplier=supplier,
            status=Purchase.Status.COMPLETED
        ).select_related('asset', 'supplier').prefetch_related('payments').order_by('purchase_date', 'created_at')

        outstanding = [p for p in all_completed if p.payment_status in ['UNPAID', 'PARTIAL']]
        created_payments = []

        for p in outstanding:
            if amount_to_allocate <= Decimal('0.00'):
                break
            
            remaining = p.remaining_amount
            if remaining <= Decimal('0.00'):
                continue
            
            allocate = min(amount_to_allocate, remaining)
            pay_record = Payment.objects.create(
                purchase=p,
                amount=allocate,
                payment_date=payment_date,
                method=method,
                reference=reference,
                notes=notes
            )
            created_payments.append(pay_record)
            amount_to_allocate -= allocate

        return created_payments

    @staticmethod
    def search_assets(query: str):
        from apps.assets.models import Asset
        return Asset.objects.filter(name__icontains=query).select_related('category')[:20]
