from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models.deletion import ProtectedError
from .models import AssetUnit

from .permissions import RBACPermission
from .serializers import (
    AssetCategorySerializer,
    AssetListSerializer,
    AssetDetailSerializer,
    AssetWriteSerializer,
    AssetUnitSerializer,
    AssetUnitWriteSerializer,
    AssignUnitSerializer,
    AssignmentSerializer,
    AssignmentWriteSerializer,
    AssignmentTransferSerializer,
    AssetRequestSerializer,
    AssetRequestCreateSerializer,
    AssetRequestAssignSerializer,
    ConfirmReceiptSerializer,
)
from .services import AssetService, AssetCategoryService, AssignmentService, AssetRequestService


class AssetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 500


class AssignmentPagination(PageNumberPagination):
    """Separate paginator for assignments so export (?page_size=9999) works
    without raising the asset list's cap."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 9999


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

class AssetCategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        categories = AssetCategoryService.list_categories()
        return Response(AssetCategorySerializer(categories, many=True).data)

    def post(self, request):
        self.required_roles = ['system_admin', 'operations_manager']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        serializer = AssetCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = AssetCategoryService.create_category(serializer.validated_data)
        return Response(AssetCategorySerializer(category).data, status=status.HTTP_201_CREATED)


class AssetCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        category = AssetCategoryService.get_category(pk)
        return Response(AssetCategorySerializer(category).data)

    def patch(self, request, pk):
        self.required_roles = ['system_admin', 'operations_manager']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        category = AssetCategoryService.get_category(pk)
        serializer = AssetCategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = AssetCategoryService.update_category(category, serializer.validated_data)
        return Response(AssetCategorySerializer(category).data)

    def delete(self, request, pk):
        self.required_roles = ['system_admin', 'operations_manager']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        category = AssetCategoryService.get_category(pk)
        try:
            AssetCategoryService.delete_category(category)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete a category that still has assets assigned to it."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Assets (types)
# ---------------------------------------------------------------------------

class AssetListCreateView(APIView):
    permission_classes = [IsAuthenticated, RBACPermission]
    required_permissions = {'GET': 'asset.view', 'POST': 'asset.create'}
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request):
        queryset = AssetService.list_assets(
            category_id=request.query_params.get('category'),
            search=request.query_params.get('search'),
            status=request.query_params.get('status'),
            department=request.query_params.get('department'),
            location=request.query_params.get('location'),
            employee=request.query_params.get('employee'),
            warranty_status=request.query_params.get('warranty_status'),
        )
        paginator = AssetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AssetListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        serializer = AssetWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = AssetService.create_asset(serializer.validated_data, request=request)
        return Response(AssetDetailSerializer(asset).data, status=status.HTTP_201_CREATED)


class AssetDetailView(APIView):
    permission_classes = [IsAuthenticated, RBACPermission]
    required_permissions = {'GET': 'asset.view', 'PATCH': 'asset.edit', 'PUT': 'asset.edit', 'DELETE': 'asset.delete'}
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request, pk):
        asset = AssetService.get_asset(pk)
        return Response(AssetDetailSerializer(asset).data)

    def patch(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        asset = AssetService.get_asset(pk)
        serializer = AssetWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        asset = AssetService.update_asset(asset, serializer.validated_data, request=request)
        return Response(AssetDetailSerializer(asset).data)

    def delete(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        asset = AssetService.get_asset(pk)
        AssetService.delete_asset(asset, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Asset Units
# ---------------------------------------------------------------------------

class AssetUnitListView(APIView):
    """GET /api/assets/<asset_id>/units/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        asset = AssetService.get_asset(pk)
        units = AssetService.list_units(asset, status=request.query_params.get('status'))
        return Response(AssetUnitSerializer(units, many=True).data)


class AssetUnitDetailView(APIView):
    """GET/PATCH /api/assets/units/<unit_id>/"""
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request, unit_id):
        unit = AssetService.get_unit(unit_id)
        return Response(AssetUnitSerializer(unit).data)

    def patch(self, request, unit_id):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        unit = AssetService.get_unit(unit_id)
        serializer = AssetUnitWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        unit = AssetService.update_unit(unit, serializer.validated_data, request=request)
        return Response(AssetUnitSerializer(unit).data)


class AssetUnitAssignView(APIView):
    """POST /api/assets/units/<unit_id>/assign/"""
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def post(self, request, unit_id):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        unit = AssetService.get_unit(unit_id)
        serializer = AssignUnitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = AssetService.assign_unit(
            unit,
            user_id=serializer.validated_data.get('user_id'),
            employee_name=serializer.validated_data['employee_name'],
            assigned_date=serializer.validated_data.get('assigned_date'),
            request=request
        )
        return Response(AssetUnitSerializer(unit).data)


class AssetUnitReturnView(APIView):
    """POST /api/assets/units/<unit_id>/return/"""
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def post(self, request, unit_id):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        unit = AssetService.get_unit(unit_id)
        unit = AssetService.return_unit(unit, request=request)
        return Response(AssetUnitSerializer(unit).data)


# ---------------------------------------------------------------------------
# Assignments — standalone Assignments page
# ---------------------------------------------------------------------------

class AssignmentListCreateView(APIView):
    """
    GET  /api/assignments/              → full history (all statuses)
    GET  /api/assignments/?status=Assigned   → active only
    GET  /api/assignments/?status=Returned   → returned only
    GET  /api/assignments/?department=IT     → department filter
    GET  /api/assignments/?search=ali        → employee name search
    GET  /api/assignments/?page_size=9999    → full export (no server-side cap up to 9999)
    POST /api/assignments/              → create new assignment (admin/manager only)
    """
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request):
        queryset = AssignmentService.list_assignments(
            status=request.query_params.get('status'),
            department=request.query_params.get('department'),
            location=request.query_params.get('location'),
            employee=request.query_params.get('employee'),
            asset=request.query_params.get('asset'),
            search=request.query_params.get('search'),
        )

        paginator = AssetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AssignmentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        serializer = AssignmentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = AssignmentService.create_assignment(serializer.validated_data, request=request)
        return Response(AssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)


class AssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def get(self, request, pk):
        assignment = AssignmentService.get_assignment(pk)
        return Response(AssignmentSerializer(assignment).data)

    def patch(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        assignment = AssignmentService.get_assignment(pk)
        serializer = AssignmentWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        assignment = AssignmentService.update_assignment(assignment, serializer.validated_data)
        return Response(AssignmentSerializer(assignment).data)

    def delete(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        assignment = AssignmentService.get_assignment(pk)
        AssignmentService.delete_assignment(assignment)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssignmentReturnView(APIView):
    """
    PATCH /api/assignments/<pk>/return/

    Marks the assignment as Returned and frees the unit.
    Idempotent — safe to call twice on an already-returned assignment.
    """
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def patch(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        assignment = AssignmentService.get_assignment(pk)
        assignment = AssignmentService.return_assignment(assignment, request=request)
        return Response(AssignmentSerializer(assignment).data)


class AssignmentStatsView(APIView):
    """
    GET /api/assignments/stats/

    Returns three counters for the dashboard stats cards:
      - total_active        active (ACTIVE) assignments right now
      - pending_returns     active assignments whose expected_return_date has passed
      - returned_this_month assignments returned during the current calendar month
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(AssignmentService.get_stats())


# ---------------------------------------------------------------------------
# Asset search (used by the purchase-create form's asset picker)
# GET /api/assets/search/?q=<query>
# ---------------------------------------------------------------------------

class AssetSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .serializers import AssetListSerializer
        query = request.query_params.get('q', '').strip()
        assets = AssetService.list_assets(search=query if query else None)[:20]
        return Response(AssetListSerializer(assets, many=True).data)

class AssignmentTransferView(APIView):
    """
    POST /api/assignments/<pk>/transfer/
    Transfers active assignment to a new employee and preserves history.
    """
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin', 'operations_manager']

    def post(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        assignment = AssignmentService.get_assignment(pk)
        serializer = AssignmentTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_assignment = AssignmentService.transfer_assignment(
            assignment,
            new_user_id=serializer.validated_data.get('employeeId'),
            new_employee_name=serializer.validated_data['employeeName'],
            new_department=serializer.validated_data.get('department', ''),
            transfer_date=serializer.validated_data.get('transferDate'),
            notes=serializer.validated_data.get('notes', ''),
            request=request
        )
        return Response(AssignmentSerializer(new_assignment).data)


# ---------------------------------------------------------------------------
# Employee Asset Requests & Receipts Views
# ---------------------------------------------------------------------------
from .serializers import (
    AssetRequestSerializer,
    AssetRequestCreateSerializer,
    AssetRequestAssignSerializer,
    ConfirmReceiptSerializer,
)

class AssetRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_param = request.query_params.get('status')
        search_param = request.query_params.get('search')
        requests_qs = AssetRequestService.list_requests(user=request.user, status=status_param, search=search_param)
        serializer = AssetRequestSerializer(requests_qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AssetRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_req = AssetRequestService.create_request(request.user, serializer.validated_data)
        return Response(AssetRequestSerializer(new_req).data, status=status.HTTP_201_CREATED)


class AssetRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            req = AssetRequestService.get_request(pk, user=request.user)
            return Response(AssetRequestSerializer(req).data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)

    def delete(self, request, pk):
        from .models import AssetRequest
        from django.core.exceptions import PermissionDenied
        try:
            req = AssetRequestService.get_request(pk, user=request.user)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)
        # Only employee who owns the request (or manager/admin) can delete
        # Employees can only delete their own PENDING requests
        role = getattr(request.user, 'role', '')
        if role == 'employee':
            if req.employee_id != request.user.id:
                return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
            if req.status not in [AssetRequest.Status.PENDING, AssetRequest.Status.REJECTED]:
                return Response(
                    {'detail': 'Only PENDING or REJECTED requests can be deleted.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        req.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssetRequestApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if getattr(request.user, 'role', '') not in ['system_admin', 'operations_manager', 'SUPER_ADMIN', 'ADMIN', 'MANAGER']:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        req = AssetRequestService.get_request(pk)
        updated_req = AssetRequestService.approve_request(req, user=request.user)
        return Response(AssetRequestSerializer(updated_req).data, status=status.HTTP_200_OK)


class AssetRequestRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if getattr(request.user, 'role', '') not in ['system_admin', 'operations_manager', 'SUPER_ADMIN', 'ADMIN', 'MANAGER']:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        req = AssetRequestService.get_request(pk)
        reason = request.data.get('reason', '')
        updated_req = AssetRequestService.reject_request(req, reason, user=request.user)
        return Response(AssetRequestSerializer(updated_req).data, status=status.HTTP_200_OK)


class AssetRequestAssignUnitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if getattr(request.user, 'role', '') not in ['system_admin', 'operations_manager', 'SUPER_ADMIN', 'ADMIN', 'MANAGER']:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = AssetRequestAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit_id = serializer.validated_data['unit_id']
        unit = AssetService.get_unit(unit_id)
        req = AssetRequestService.get_request(pk)
        try:
            updated_req = AssetRequestService.assign_unit(req, unit, user=request.user)
            return Response(AssetRequestSerializer(updated_req).data, status=status.HTTP_200_OK)
        except ValueError as ve:
            return Response({'detail': str(ve)}, status=status.HTTP_400_BAD_REQUEST)


class ConfirmReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ConfirmReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id = request.data.get('requestId') or request.data.get('request_id')
        assignment_id = request.data.get('assignmentId') or request.data.get('assignment_id')
        condition = serializer.validated_data.get('condition', 'Good Condition')
        notes = serializer.validated_data.get('notes', '')

        try:
            res = AssetRequestService.confirm_receipt(
                user=request.user,
                request_id=request_id,
                assignment_id=assignment_id,
                condition=condition,
                notes=notes
            )
            return Response({'detail': 'Receipt confirmed successfully.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MyAssignedAssetsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import AssetAssignmentHistory
        from .serializers import AssignmentListSerializer
        from django.db.models import Q

        user = request.user

        # Build name variants from the logged-in user's profile
        full_name       = f"{user.first_name} {user.last_name}".strip()
        first_name      = (user.first_name or '').strip()
        last_name       = (user.last_name  or '').strip()
        email_local     = user.email.split('@')[0] if user.email else ''

        # Match by user FK OR by employee_name (handles cases where admin
        # assigned by name without linking a user account)
        name_filter = Q(user=user)
        if full_name:
            name_filter |= Q(employee_name__iexact=full_name)
        if first_name:
            name_filter |= Q(employee_name__icontains=first_name)
        if last_name:
            name_filter |= Q(employee_name__icontains=last_name)
        if email_local:
            name_filter |= Q(employee_name__icontains=email_local)

        qs = (
            AssetAssignmentHistory.objects
            .filter(name_filter, status=AssetAssignmentHistory.Status.ACTIVE)
            .select_related('unit', 'unit__asset', 'user')
            .order_by('-assigned_date')
            .distinct()
        )

        # Auto-link user FK on any unlinked records we just found
        unlinked = qs.filter(user__isnull=True)
        if unlinked.exists():
            unlinked.update(user=user)

        # Auto-heal active assignment records where unit was unlinked/null
        from .models import Asset, AssetUnit
        for item in qs:
            if not item.unit:
                matched_unit = None
                if item.unit_serial_snapshot:
                    matched_unit = AssetUnit.objects.filter(serial_number=item.unit_serial_snapshot).first()
                if not matched_unit:
                    matched_asset = None
                    if item.asset_name_snapshot:
                        matched_asset = Asset.objects.filter(name__iexact=item.asset_name_snapshot).first()
                        if not matched_asset:
                            base_name = item.asset_name_snapshot.rstrip('0123456789').strip()
                            if base_name:
                                matched_asset = Asset.objects.filter(name__icontains=base_name).first()
                        if not matched_asset:
                            for word in item.asset_name_snapshot.split():
                                if len(word) >= 3:
                                    matched_asset = Asset.objects.filter(name__icontains=word).first()
                                    if matched_asset:
                                        break
                        if not matched_asset:
                            from .models import AssetCategory
                            from datetime import date
                            cat = AssetCategory.objects.first()
                            if not cat:
                                cat = AssetCategory.objects.create(name='General', code='GEN')
                            matched_asset = Asset.objects.create(
                                name=item.asset_name_snapshot,
                                category=cat,
                                purchase_date=item.assigned_date or date.today(),
                                purchase_cost=0,
                                current_value=0,
                            )
                    else:
                        matched_asset = Asset.objects.first()

                    if matched_asset:
                        from django.db.models import Max
                        max_num = AssetUnit.objects.filter(asset=matched_asset).aggregate(Max('unit_number'))['unit_number__max'] or 0
                        matched_unit = AssetUnit.objects.create(
                            asset=matched_asset,
                            unit_number=max_num + 1,
                            serial_number=item.unit_serial_snapshot or f"SN-{str(item.id)[:8]}",
                            status='ASSIGNED',
                            assigned_to=item.user or user
                        )
                if matched_unit:
                    item.unit = matched_unit
                    item.save(update_fields=['unit'])

        serializer = AssignmentListSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request):
        """
        Employee removes an assignment record from their My Assets view.
        Allowed for any ACTIVE assignment owned by the logged-in user.
        PENDING_RECEIPT → mark as returned (frees the unit).
        RECEIVED        → mark as returned (already confirmed).
        """
        from .models import AssetAssignmentHistory, AssetUnit
        assignment_id = (
            request.data.get('assignment_id')
            or request.query_params.get('assignment_id')
        )
        if not assignment_id:
            return Response({'detail': 'assignment_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            assignment = AssetAssignmentHistory.objects.select_related('unit').get(
                pk=assignment_id, user=request.user
            )
        except AssetAssignmentHistory.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Mark assignment as returned so it disappears from ACTIVE list
        from datetime import date
        assignment.status = AssetAssignmentHistory.Status.RETURNED
        assignment.returned_date = date.today()
        assignment.save(update_fields=['status', 'returned_date'])

        # Free the unit back to AVAILABLE if it was assigned to this user
        if assignment.unit and assignment.unit.status == AssetUnit.Status.ASSIGNED:
            assignment.unit.status = AssetUnit.Status.AVAILABLE
            assignment.unit.assigned_to = None
            assignment.unit.save(update_fields=['status', 'assigned_to'])

        return Response({'detail': 'Assignment removed from your list.'}, status=status.HTTP_200_OK)



# ---------------------------------------------------------------------------
# One-time Database Setup (for demo/testing)
# ---------------------------------------------------------------------------

class PopulateSampleDataView(APIView):
    """
    One-time endpoint to populate the database with sample data.
    Only accessible to system admins.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Check if user is system admin
        if not request.user.is_superuser and request.user.role != 'system_admin':
            return Response(
                {'error': 'Only system administrators can populate sample data'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            from apps.assets.management.commands.populate_via_api import populate_database
            results = populate_database()
            return Response(results, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
