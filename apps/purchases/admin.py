from django.contrib import admin
from .models import Supplier, Purchase, Payment


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['company', 'name', 'email', 'phone', 'status']
    list_filter = ['status']
    search_fields = ['company', 'name', 'email']


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['purchase_number', 'asset', 'supplier', 'quantity', 'purchase_price', 'status']
    list_filter = ['status']
    search_fields = ['purchase_number']
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['purchase', 'amount', 'payment_date', 'method']
    list_filter = ['method']