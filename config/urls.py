from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.authentication.urls')),
    path('api/assets/', include('apps.assets.urls')),
    path('api/assignments/', include('apps.assets.assignment_urls')),
    path('api/users/', include('apps.users.urls')),
    path('api/maintenance/', include('apps.maintenance.urls')),
    path('api/purchases/', include('apps.purchases.urls')),
    path('api/dashboard/', include('apps.dashboard.urls')),
    path('api/company-settings/', include('apps.company_settings.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/depreciation/', include('apps.depreciation.urls')),
    path('api/audit-logs/', include('apps.audit.urls')),
    path('api/ai/', include('apps.ai.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
