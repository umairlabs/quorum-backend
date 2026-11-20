from django.urls import path
from .views import (
    AssignmentListCreateView,
    AssignmentDetailView,
    AssignmentReturnView,
    AssignmentTransferView,
    AssignmentStatsView,
)

app_name = 'assignments'

urlpatterns = [
    # Stats — must come before <uuid:pk> so it isn't swallowed as a UUID
    path('stats/', AssignmentStatsView.as_view(), name='assignment-stats'),

    # List / create
    path('', AssignmentListCreateView.as_view(), name='assignment-list'),

    # Detail / update / delete
    path('<uuid:pk>/', AssignmentDetailView.as_view(), name='assignment-detail'),

    # Return an asset (marks assignment as Returned, frees the unit)
    path('<uuid:pk>/return/', AssignmentReturnView.as_view(), name='assignment-return'),
    path('<uuid:pk>/transfer/', AssignmentTransferView.as_view(), name='assignment-transfer'),
]
