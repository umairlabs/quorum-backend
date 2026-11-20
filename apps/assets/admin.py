from django.contrib import admin
from .models import Asset, AssetCategory, AssetUnit, AssetAssignmentHistory


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name']


class AssetUnitInline(admin.TabularInline):
    model = AssetUnit
    extra = 0
    fields = ['unit_number', 'serial_number', 'status', 'assigned_to']


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'total_quantity', 'available_quantity', 'current_value']
    list_filter = ['category']
    search_fields = ['name', 'id']
    inlines = [AssetUnitInline]


@admin.register(AssetUnit)
class AssetUnitAdmin(admin.ModelAdmin):
    list_display = ['serial_number', 'asset', 'unit_number', 'status', 'assigned_to']
    list_filter = ['status']
    search_fields = ['serial_number', 'asset__name', 'asset__id']


@admin.register(AssetAssignmentHistory)
class AssetAssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = ['unit', 'employee_name', 'assigned_date', 'returned_date', 'status']
    list_filter = ['status']