from django.urls import path
from .views import AuditLogListView, AuditLogDetailView, AuditLogStatsView

urlpatterns = [
    path('', AuditLogListView.as_view(), name='audit_log_list'),
    path('stats/', AuditLogStatsView.as_view(), name='audit_log_stats'),
    path('<str:pk>/', AuditLogDetailView.as_view(), name='audit_log_detail'),
]
