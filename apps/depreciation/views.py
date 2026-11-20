from apps.authentication.permissions import RBACPermission
import uuid
from decimal import Decimal

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.assets.models import Asset
from .services import DepreciationService
from .serializers import (
    AssetDepreciationSerializer,
    UpdateDepreciationSerializer,
)
from .permissions import CanViewFinancials, IsManagerOrAdmin


class DepreciationListAPIView(APIView):
    """
    GET /api/depreciation/
    Returns list of depreciation calculations for all assets with search and filtering.
    """
    permission_classes = [IsAuthenticated, CanViewFinancials]

    def get(self, request):
        queryset = Asset.objects.select_related('category').prefetch_related('units').all()

        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(name__icontains=search) | queryset.filter(brand__icontains=search) | queryset.filter(model__icontains=search)

        status_filter = request.query_params.get('status', '').strip().upper()
        category_filter = request.query_params.get('category', '').strip()

        results = []
        for asset in queryset:
            data = DepreciationService.get_asset_depreciation_data(asset)
            
            if status_filter and status_filter != 'ALL':
                if data['depreciationStatus'] != status_filter:
                    continue

            if category_filter and category_filter != 'ALL':
                if data['category'].lower() != category_filter.lower():
                    continue

            results.append(data)

        serializer = AssetDepreciationSerializer(results, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AssetDepreciationDetailAPIView(APIView):
    """
    GET /api/depreciation/<asset_id>/
    PATCH /api/depreciation/<asset_id>/
    """
    permission_classes = [IsAuthenticated, CanViewFinancials]

    def get_permissions(self):
        if self.request.method in ['PATCH', 'PUT', 'POST']:
            return [IsAuthenticated(), IsManagerOrAdmin()]
        return [IsAuthenticated(), CanViewFinancials()]

    def get_asset(self, asset_id):
        # Handle string or UUID
        clean_id = str(asset_id).split('-unit-')[0]
        try:
            return get_object_or_404(Asset, pk=clean_id)
        except Exception:
            return get_object_or_404(Asset, pk=asset_id)

    def get(self, request, asset_id):
        asset = self.get_asset(asset_id)
        data = DepreciationService.get_asset_depreciation_data(asset)
        serializer = AssetDepreciationSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, asset_id):
        asset = self.get_asset(asset_id)
        
        # Accept both camelCase and snake_case inputs
        payload = request.data.copy()
        if 'salvage_value' in payload and 'salvageValue' not in payload:
            payload['salvageValue'] = payload['salvage_value']
        if 'useful_life_years' in payload and 'usefulLifeYears' not in payload:
            payload['usefulLifeYears'] = payload['useful_life_years']
        if 'depreciation_method' in payload and 'depreciationMethod' not in payload:
            payload['depreciationMethod'] = payload['depreciation_method']

        serializer = UpdateDepreciationSerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        salvage_value = serializer.validated_data['salvageValue']
        useful_life = serializer.validated_data['usefulLifeYears']
        method = serializer.validated_data.get('depreciationMethod', 'STRAIGHT_LINE')

        if salvage_value > asset.purchase_cost:
            return Response(
                {"error": f"Salvage value ({salvage_value}) cannot exceed the asset purchase cost ({asset.purchase_cost})."},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated_data = DepreciationService.update_asset_depreciation(
            asset=asset,
            salvage_value=salvage_value,
            useful_life_years=useful_life,
            depreciation_method=method,
            user=request.user,
            request=request
        )

        resp_serializer = AssetDepreciationSerializer(updated_data)
        return Response(resp_serializer.data, status=status.HTTP_200_OK)
