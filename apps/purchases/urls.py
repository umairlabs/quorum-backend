from django.urls import path
from .views import (
    SupplierListCreateView,
    SupplierDetailView,
    SupplierPaymentView,
    PurchaseListCreateView,
    PurchaseDetailView,
    PurchasePaymentView,
    AssetSearchView,
    OutstandingPurchasesView,
    PurchaseSummaryView,
    PaymentInvoiceView,
)

app_name = 'purchases'

urlpatterns = [
    path('suppliers/', SupplierListCreateView.as_view(), name='supplier-list'),
    path('suppliers/<uuid:pk>/', SupplierDetailView.as_view(), name='supplier-detail'),
    path('suppliers/<uuid:pk>/pay/', SupplierPaymentView.as_view(), name='supplier-pay'),

    path('outstanding/', OutstandingPurchasesView.as_view(), name='outstanding-list'),
    path('summary/', PurchaseSummaryView.as_view(), name='purchase-summary'),
    path('payments/<uuid:payment_id>/invoice/', PaymentInvoiceView.as_view(), name='payment-invoice'),

    path('', PurchaseListCreateView.as_view(), name='purchase-list'),
    path('<uuid:pk>/', PurchaseDetailView.as_view(), name='purchase-detail'),
    path('<uuid:pk>/payments/', PurchasePaymentView.as_view(), name='purchase-add-payment'),

    path('assets/search/', AssetSearchView.as_view(), name='asset-search'),
]