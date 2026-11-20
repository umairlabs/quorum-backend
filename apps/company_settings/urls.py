from django.urls import path
from .views import CompanySettingsView, CompanyLogoUploadView

urlpatterns = [
    # GET  /api/company-settings/        → retrieve
    # PUT  /api/company-settings/        → update (system_admin only)
    path('', CompanySettingsView.as_view(), name='company-settings'),

    # POST /api/company-settings/logo/   → upload logo (system_admin only)
    path('logo/', CompanyLogoUploadView.as_view(), name='company-settings-logo'),
]
