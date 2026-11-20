from django.db.models import Q
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from apps.authentication.permissions import RBACPermission
from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 500


class AuditLogListView(APIView):
    """
    GET /api/audit-logs/
    Immutable audit history log list endpoint.
    Supports server-side filtering, search, and pagination.
    """
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin']

    def get(self, request):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        queryset = AuditLog.objects.all().order_by('-created_at')

        # Filters
        action = request.query_params.get('action')
        if action and action.upper() != 'ALL':
            queryset = queryset.filter(action=action.upper())

        module = request.query_params.get('module')
        if module and module.upper() != 'ALL':
            queryset = queryset.filter(module=module.upper())

        asset_id = request.query_params.get('asset_id') or request.query_params.get('asset')
        if asset_id:
            queryset = queryset.filter(Q(asset_id=asset_id) | Q(asset_unit__asset_id=asset_id))

        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        date_from = request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)

        # Search query
        search = request.query_params.get('search') or request.query_params.get('q')
        if search:
            s = search.strip()
            queryset = queryset.filter(
                Q(audit_id__icontains=s) |
                Q(user_name_snapshot__icontains=s) |
                Q(user_role_snapshot__icontains=s) |
                Q(asset_name_snapshot__icontains=s) |
                Q(serial_number_snapshot__icontains=s) |
                Q(description__icontains=s)
            )

        paginator = AuditLogPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AuditLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AuditLogDetailView(APIView):
    """
    GET /api/audit-logs/<pk>/
    """
    permission_classes = [IsAuthenticated]
    required_roles = ['system_admin']

    def get(self, request, pk):
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        try:
            audit_log = AuditLog.objects.get(Q(id=pk) | Q(audit_id=pk))
            return Response(AuditLogSerializer(audit_log).data)
        except AuditLog.DoesNotExist:
            return Response({"detail": "Audit log record not found."}, status=status.HTTP_404_NOT_FOUND)


class AuditLogStatsView(APIView):
    """
    GET /api/audit-logs/stats/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        total = AuditLog.objects.count()
        assets_count = AuditLog.objects.filter(module=AuditLog.Module.ASSETS).count()
        assignments_count = AuditLog.objects.filter(module=AuditLog.Module.ASSIGNMENTS).count()
        maintenance_count = AuditLog.objects.filter(module=AuditLog.Module.MAINTENANCE).count()

        return Response({
            'total': total,
            'assets': assets_count,
            'assignments': assignments_count,
            'maintenance': maintenance_count
        })
