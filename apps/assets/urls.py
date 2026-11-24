from django.urls import path
from .views import (
    AssetCategoryListCreateView,
    AssetCategoryDetailView,
    AssetListCreateView,
    AssetDetailView,
    AssetUnitListView,
    AssetUnitDetailView,
    AssetUnitAssignView,
    AssetUnitReturnView,
    AssetSearchView,
    AssetRequestListCreateView,
    AssetRequestDetailView,
    AssetRequestApproveView,
    AssetRequestRejectView,
    AssetRequestAssignUnitView,
    ConfirmReceiptView,
    MyAssignedAssetsView,
    PopulateSampleDataView,
)

app_name = 'assets'

urlpatterns = [
    path('categories/', AssetCategoryListCreateView.as_view(), name='category-list'),
    path('categories/<uuid:pk>/', AssetCategoryDetailView.as_view(), name='category-detail'),

    # Request endpoints
    path('requests/', AssetRequestListCreateView.as_view(), name='request-list-create'),
    path('requests/<uuid:pk>/', AssetRequestDetailView.as_view(), name='request-detail'),
    path('requests/<uuid:pk>/approve/', AssetRequestApproveView.as_view(), name='request-approve'),
    path('requests/<uuid:pk>/reject/', AssetRequestRejectView.as_view(), name='request-reject'),
    path('requests/<uuid:pk>/assign-unit/', AssetRequestAssignUnitView.as_view(), name='request-assign-unit'),
    
    path('confirm-receipt/', ConfirmReceiptView.as_view(), name='confirm-receipt'),
    path('my-assigned/', MyAssignedAssetsView.as_view(), name='my-assigned-assets'),

    # One-time setup endpoint
    path('populate-sample-data/', PopulateSampleDataView.as_view(), name='populate-sample-data'),

    # search must come before <uuid:pk> to avoid being caught by the detail route
    path('search/', AssetSearchView.as_view(), name='asset-search'),

    path('', AssetListCreateView.as_view(), name='asset-list'),
    path('<uuid:pk>/', AssetDetailView.as_view(), name='asset-detail'),
    path('<uuid:pk>/units/', AssetUnitListView.as_view(), name='asset-units'),

    path('units/<uuid:unit_id>/', AssetUnitDetailView.as_view(), name='unit-detail'),
    path('units/<uuid:unit_id>/assign/', AssetUnitAssignView.as_view(), name='unit-assign'),
    path('units/<uuid:unit_id>/return/', AssetUnitReturnView.as_view(), name='unit-return'),
]
