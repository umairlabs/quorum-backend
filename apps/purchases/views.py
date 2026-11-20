from apps.authentication.permissions import RBACPermission
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.assets.permissions import RBACPermission
from .serializers import (
    SupplierSerializer,
    SupplierWriteSerializer,
    PurchaseSerializer,
    PurchaseWriteSerializer,
    PaymentSerializer,
    PaymentCreateSerializer,
    AssetSearchResultSerializer,
)
from .services import SupplierService, PurchaseService


class PurchasePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

class SupplierListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request):
        suppliers = SupplierService.list_suppliers()
        paginator = PurchasePagination()
        page = paginator.paginate_queryset(suppliers, request)
        serializer = SupplierSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = SupplierWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supplier = SupplierService.create_supplier(serializer.validated_data)
        return Response(SupplierSerializer(supplier).data, status=status.HTTP_201_CREATED)


class SupplierDetailView(APIView):
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request, pk):
        supplier = SupplierService.get_supplier(pk)
        return Response(SupplierSerializer(supplier).data)

    def patch(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        supplier = SupplierService.get_supplier(pk)
        serializer = SupplierWriteSerializer(supplier, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        supplier = SupplierService.update_supplier(supplier, serializer.validated_data)
        return Response(SupplierSerializer(supplier).data)

    def delete(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        supplier = SupplierService.get_supplier(pk)
        SupplierService.delete_supplier(supplier)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Purchases
# ---------------------------------------------------------------------------

class PurchaseListCreateView(APIView):
    permission_classes = [IsAuthenticated, RBACPermission]
    required_permissions = {'GET': 'purchase.view', 'POST': 'purchase.create'}
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request):
        purchases = PurchaseService.list_purchases(
            status=request.query_params.get('status'),
            supplier_id=request.query_params.get('supplier'),
            payment_status=request.query_params.get('payment_status'),
            search=request.query_params.get('search'),
        )
        paginator = PurchasePagination()
        page = paginator.paginate_queryset(purchases, request)
        serializer = PurchaseSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = PurchaseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = PurchaseService.create_purchase(serializer.validated_data, request=request)
        return Response(PurchaseSerializer(purchase).data, status=status.HTTP_201_CREATED)


class PurchaseDetailView(APIView):
    permission_classes = [IsAuthenticated, RBACPermission]
    required_permissions = {'GET': 'purchase.view', 'PATCH': 'purchase.edit', 'PUT': 'purchase.edit', 'DELETE': 'purchase.delete'}
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request, pk):
        purchase = PurchaseService.get_purchase(pk)
        return Response(PurchaseSerializer(purchase).data)

    def patch(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        purchase = PurchaseService.get_purchase(pk)
        serializer = PurchaseWriteSerializer(purchase, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        purchase = PurchaseService.update_purchase(purchase, serializer.validated_data)
        return Response(PurchaseSerializer(purchase).data)

    def delete(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        purchase = PurchaseService.get_purchase(pk)
        PurchaseService.delete_purchase(purchase)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PurchasePaymentView(APIView):
    """GET/POST /api/purchases/<id>/payments/ — list/add payment installments."""
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request, pk):
        purchase = PurchaseService.get_purchase(pk)
        payments = purchase.payments.all()
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        purchase = PurchaseService.get_purchase(pk)
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PurchaseService.add_payment(purchase, serializer.validated_data)

        purchase.refresh_from_db()
        return Response(PurchaseSerializer(purchase).data, status=status.HTTP_201_CREATED)


class OutstandingPurchasesView(APIView):
    """GET /api/purchases/outstanding/ — list all suppliers with UNPAID/PARTIAL purchases."""
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request):
        purchases = PurchaseService.list_purchases()
        outstanding_purchases = [p for p in purchases if p.payment_status in ['UNPAID', 'PARTIAL']]

        # Aggregate outstanding dues per supplier
        supplier_dues = {}
        total_outstanding = 0

        for p in outstanding_purchases:
            supplier_id = p.supplier.id
            if supplier_id not in supplier_dues:
                supplier_dues[supplier_id] = {
                    'supplier': p.supplier,
                    'outstanding_balance': 0,
                    'active_dues_count': 0
                }
            supplier_dues[supplier_id]['outstanding_balance'] += p.remaining_amount
            supplier_dues[supplier_id]['active_dues_count'] += 1
            total_outstanding += p.remaining_amount

        # Format output list
        results = []
        for s_id, data in supplier_dues.items():
            s_serialized = SupplierSerializer(data['supplier']).data
            results.append({
                'supplier': s_serialized,
                'outstandingBalance': float(data['outstanding_balance']),
                'activeDuesCount': data['active_dues_count']
            })

        # Order by highest outstanding balance
        results.sort(key=lambda x: x['outstandingBalance'], reverse=True)

        paginator = PurchasePagination()
        page = paginator.paginate_queryset(results, request)
        response = paginator.get_paginated_response(page)
        
        response.data['totalOutstanding'] = float(total_outstanding)
        response.data['outstandingCount'] = len(results)
        return response


class SupplierPaymentView(APIView):
    """
    GET  /api/purchases/suppliers/<uuid:pk>/pay/ — List all payments made to a supplier.
    POST /api/purchases/suppliers/<uuid:pk>/pay/ — Record supplier-level payment installment.
    """
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request, pk):
        """Return all payment records linked to any purchase of this supplier."""
        supplier = SupplierService.get_supplier(pk)
        payments = Payment.objects.filter(
            purchase__supplier=supplier
        ).select_related('purchase').order_by('-payment_date', '-created_at')
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        supplier = SupplierService.get_supplier(pk)
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        created_payments = PurchaseService.add_supplier_payment(supplier, serializer.validated_data)
        serialized_payments = PaymentSerializer(created_payments, many=True)

        return Response({
            "detail": f"Successfully allocated payment across {len(created_payments)} purchase order(s).",
            "payments": serialized_payments.data
        }, status=status.HTTP_201_CREATED)


class PurchaseSummaryView(APIView):
    """GET /api/purchases/summary/ — dashboard/page summary counters."""
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request):
        purchases = PurchaseService.list_purchases()
        total_spent = sum(p.total_amount for p in purchases)
        total_outstanding = sum(p.remaining_amount for p in purchases)
        
        return Response({
            "totalPurchases": len(purchases),
            "totalSpent": float(total_spent),
            "totalOutstanding": float(total_outstanding)
        })


from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from .models import Payment
from .invoice_generator import generate_invoice_pdf

class PaymentInvoiceView(APIView):
    """GET /api/purchases/payments/<uuid:payment_id>/invoice/ — download/view auto-invoice PDF."""
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request, payment_id):
        payment = get_object_or_404(Payment.objects.select_related('purchase', 'purchase__asset', 'purchase__asset__category', 'purchase__supplier'), pk=payment_id)
        try:
            pdf_bytes = generate_invoice_pdf(payment)
        except Exception as e:
            return Response({"detail": f"Invoice generation failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"Invoice_{payment.invoice_number or payment_id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


# ---------------------------------------------------------------------------
# Asset search (used by the purchase-create form's asset picker)
# ---------------------------------------------------------------------------

class AssetSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '')
        assets = PurchaseService.search_assets(query)
        return Response(AssetSearchResultSerializer(assets, many=True).data)