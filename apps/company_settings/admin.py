from django.contrib import admin
from .models import CompanySettings


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = [
        'company_name',
        'official_email',
        'currency',
        'date_format',
        'time_zone',
        'updated_by',
        'updated_at',
    ]
    readonly_fields = ['updated_by', 'updated_at', 'created_at']

    fieldsets = (
        ('Company Info', {
            'fields': ('company_name', 'logo_url', 'official_email', 'company_phone', 'company_address'),
        }),
        ('Preferences', {
            'fields': ('currency', 'time_zone', 'date_format'),
        }),
        ('Metadata', {
            'fields': ('updated_by', 'updated_at', 'created_at'),
        }),
    )

    def has_add_permission(self, request):
        # Enforce singleton — disallow adding a second row from admin
        return not CompanySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent accidental deletion of the singleton
        return False
