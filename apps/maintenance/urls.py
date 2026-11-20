from django.urls import path
from .views import (
    MaintenanceListCreateView,
    MaintenanceDetailView,
    MaintenanceStatusUpdateView,
    MaintenanceWorkUpdateView,
    MaintenanceStatsView,
)

app_name = 'maintenance'

urlpatterns = [
    path('', MaintenanceListCreateView.as_view(), name='maintenance-list'),
    path('stats/', MaintenanceStatsView.as_view(), name='maintenance-stats'),
    path('<uuid:pk>/', MaintenanceDetailView.as_view(), name='maintenance-detail'),
    path('<uuid:pk>/status/', MaintenanceStatusUpdateView.as_view(), name='maintenance-status'),
    path('<uuid:pk>/work-update/', MaintenanceWorkUpdateView.as_view(), name='maintenance-work-update'),
]
