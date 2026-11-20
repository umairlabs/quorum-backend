from django.urls import path
from .views import DepreciationListAPIView, AssetDepreciationDetailAPIView

app_name = 'depreciation'

urlpatterns = [
    path('', DepreciationListAPIView.as_view(), name='depreciation-list'),
    path('<uuid:asset_id>/', AssetDepreciationDetailAPIView.as_view(), name='depreciation-detail'),
]
