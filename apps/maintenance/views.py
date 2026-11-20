from apps.authentication.permissions import RBACPermission
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MaintenanceRequest, MaintenanceTimelineEntry
from .serializers import (
    CreateMaintenanceRequestSerializer,
    MaintenanceDetailSerializer,
    MaintenanceListSerializer,
    MaintenanceStatsSerializer,
    UpdateMaintenanceStatusSerializer,
    MaintenanceWorkUpdateSerializer,
)


from .services import generate_maintenance_request_id


STATUS_LABELS = {
    MaintenanceRequest.Status.PENDING: 'Request Created',
    MaintenanceRequest.Status.IN_PROGRESS: 'Work Started',
    MaintenanceRequest.Status.COMPLETED: 'Work Completed',
    MaintenanceRequest.Status.RESOLVED: 'Work Resolved',
    MaintenanceRequest.Status.VERIFIED: 'Quality Verified',
    MaintenanceRequest.Status.CANCELLED: 'Request Cancelled',
    MaintenanceRequest.Status.UNREPAIRABLE: 'Marked Not Repairable',
    MaintenanceRequest.Status.NOT_REPAIRABLE: 'Marked Not Repairable',
}


class MaintenanceListCreateView(ListCreateAPIView):
    def get_queryset(self):
        from apps.users.models import User
        qs = MaintenanceRequest.objects.select_related('asset', 'asset_unit').all()
        user = self.request.user
        if user.is_authenticated and getattr(user, 'role', '') == User.Role.EMPLOYEE:
            qs = qs.filter(requested_by=user)
        return qs

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateMaintenanceRequestSerializer
        return MaintenanceListSerializer

    def create(self, request, *args, **kwargs):
        serializer = CreateMaintenanceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        asset_unit_obj = serializer.validated_data.get('asset_unit')
        if asset_unit_obj:
            active_maint = MaintenanceRequest.objects.filter(
                asset_unit=asset_unit_obj
            ).exclude(
                status__in=['RESOLVED', 'COMPLETED', 'VERIFIED', 'CANCELLED', 'UNREPAIRABLE', 'NOT_REPAIRABLE']
            ).first()
            if active_maint or asset_unit_obj.status == 'MAINTENANCE':
                req_num = f" (#{active_maint.request_id})" if active_maint else ""
                return Response(
                    {"detail": f"This asset unit ({asset_unit_obj.serial_number}) is already in maintenance{req_num}. It cannot be submitted again until repaired."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        maintenance_request = MaintenanceRequest.objects.create(
            request_id=generate_maintenance_request_id(),
            asset=serializer.validated_data['asset'],
            asset_unit=asset_unit_obj,
            component_or_issue_type=serializer.validated_data['component_or_issue_type'],
            issue_description=serializer.validated_data['issue_description'],
            maintenance_type=serializer.validated_data['maintenance_type'],
            priority=serializer.validated_data['priority'],
            status=MaintenanceRequest.Status.PENDING,
            assigned_technician=serializer.validated_data.get('assigned_technician', ''),
            requested_by=request.user if request.user.is_authenticated else None,
            requested_by_name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email if request.user.is_authenticated else '',
        )

        MaintenanceTimelineEntry.objects.create(
            maintenance_request=maintenance_request,
            status=MaintenanceRequest.Status.PENDING,
            label=STATUS_LABELS[MaintenanceRequest.Status.PENDING],
        )

        if maintenance_request.asset_unit:
            maintenance_request.asset_unit.status = 'MAINTENANCE'
            maintenance_request.asset_unit.save()

        try:
            from apps.audit.services import AuditLogService
            AuditLogService.log_action(
                action='MAINTENANCE_CREATED',
                module='MAINTENANCE',
                asset=maintenance_request.asset,
                asset_name=maintenance_request.asset.name if maintenance_request.asset else '',
                description=f"Maintenance ticket {maintenance_request.request_id} created for '{maintenance_request.asset.name if maintenance_request.asset else 'Asset'}'. Issue: {maintenance_request.component_or_issue_type}",
                request=request,
                new_value={
                    'ticket_id': maintenance_request.request_id,
                    'priority': maintenance_request.priority,
                    'type': maintenance_request.maintenance_type,
                    'status': maintenance_request.status
                }
            )
        except Exception:
            pass

        try:
            from apps.notifications.services import create_system_notification
            asset_name = maintenance_request.asset.name if maintenance_request.asset else 'Asset'
            create_system_notification(
                title=f"Maintenance Ticket Created ({maintenance_request.request_id})",
                message=f"Maintenance request {maintenance_request.request_id} created for '{asset_name}'. Issue: {maintenance_request.component_or_issue_type}.",
                notification_type='MAINTENANCE',
                sub_type='MAINTENANCE_CREATED',
                related_asset_id=maintenance_request.asset.id if maintenance_request.asset else None,
                related_asset_name=asset_name,
                related_maintenance_id=maintenance_request.id,
                related_maintenance_request_id=maintenance_request.request_id,
                target_role='external_technician'
            )
        except Exception:
            pass

        output = MaintenanceDetailSerializer(maintenance_request)
        return Response(output.data, status=status.HTTP_201_CREATED)


class MaintenanceDetailView(RetrieveUpdateDestroyAPIView):
    queryset = MaintenanceRequest.objects.select_related('asset', 'asset_unit').all()
    serializer_class = MaintenanceDetailSerializer


class MaintenanceStatusUpdateView(APIView):
    """PATCH /api/maintenance/<id>/status/"""

    def patch(self, request, pk):
        try:
            maintenance_request = MaintenanceRequest.objects.get(pk=pk)
        except MaintenanceRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = UpdateMaintenanceStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_status = maintenance_request.status
        new_status = serializer.validated_data['status']
        note = serializer.validated_data.get('note', '')

        maintenance_request.status = new_status
        if new_status in [
            MaintenanceRequest.Status.COMPLETED,
            MaintenanceRequest.Status.VERIFIED,
            MaintenanceRequest.Status.RESOLVED,
            MaintenanceRequest.Status.UNREPAIRABLE,
            MaintenanceRequest.Status.NOT_REPAIRABLE,
        ]:
            maintenance_request.completed_at = timezone.now()
            if note:
                maintenance_request.notes = note
        maintenance_request.save()

        MaintenanceTimelineEntry.objects.create(
            maintenance_request=maintenance_request,
            status=new_status,
            label=STATUS_LABELS.get(new_status, new_status),
            note=note,
            completed_by=(
                f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email
                if request.user.is_authenticated else ''
            ),
        )

        if maintenance_request.asset_unit:
            from apps.assets.models import AssetAssignmentHistory
            has_active_assign = AssetAssignmentHistory.objects.filter(
                unit=maintenance_request.asset_unit,
                status=AssetAssignmentHistory.Status.ACTIVE
            ).exists()

            if new_status in [MaintenanceRequest.Status.COMPLETED, MaintenanceRequest.Status.VERIFIED, MaintenanceRequest.Status.RESOLVED]:
                maintenance_request.asset_unit.status = 'ASSIGNED' if has_active_assign else 'AVAILABLE'
                maintenance_request.asset_unit.save()
            elif new_status in [MaintenanceRequest.Status.CANCELLED]:
                maintenance_request.asset_unit.status = 'ASSIGNED' if has_active_assign else 'AVAILABLE'
                maintenance_request.asset_unit.save()
            elif new_status in [MaintenanceRequest.Status.UNREPAIRABLE, MaintenanceRequest.Status.NOT_REPAIRABLE]:
                maintenance_request.asset_unit.status = 'SCRAPPED'
                maintenance_request.asset_unit.save()

        # Notification integration
        try:
            from apps.notifications.services import create_system_notification
            asset_name = maintenance_request.asset.name if maintenance_request.asset else 'Asset'
            create_system_notification(
                title=f"Maintenance Status Updated ({maintenance_request.request_id})",
                message=f"Ticket {maintenance_request.request_id} ({asset_name}) status changed to {new_status}.",
                notification_type='MAINTENANCE',
                sub_type='MAINTENANCE_STATUS_CHANGED',
                related_asset_id=maintenance_request.asset.id if maintenance_request.asset else None,
                related_asset_name=asset_name,
                related_maintenance_id=maintenance_request.id,
                related_maintenance_request_id=maintenance_request.request_id,
                target_role='operations_manager'
            )
        except Exception:
            pass

        output = MaintenanceDetailSerializer(maintenance_request)
        return Response(output.data, status=status.HTTP_200_OK)


class MaintenanceWorkUpdateView(APIView):
    """PATCH /api/maintenance/<id>/work-update/"""

    def patch(self, request, pk):
        try:
            maintenance_request = MaintenanceRequest.objects.get(pk=pk)
        except MaintenanceRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = MaintenanceWorkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_status = maintenance_request.status
        new_status = serializer.validated_data['status']
        work_done = serializer.validated_data.get('work_done', '')
        technician_notes = serializer.validated_data.get('technician_notes', '')
        tech_name = serializer.validated_data.get('technicianName', '') or (
            f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email
            if request.user.is_authenticated else 'Technician'
        )

        maintenance_request.status = new_status
        maintenance_request.work_done = work_done
        maintenance_request.technician_notes = technician_notes
        if work_done:
            maintenance_request.notes = work_done

        if new_status in [
            MaintenanceRequest.Status.COMPLETED,
            MaintenanceRequest.Status.VERIFIED,
            MaintenanceRequest.Status.RESOLVED,
            MaintenanceRequest.Status.UNREPAIRABLE,
            MaintenanceRequest.Status.NOT_REPAIRABLE,
        ]:
            maintenance_request.completed_at = timezone.now()

        maintenance_request.save()

        label_map = {
            MaintenanceRequest.Status.TODO: 'Work To Do',
            MaintenanceRequest.Status.IN_PROGRESS: 'Work In Progress',
            MaintenanceRequest.Status.REVIEW: 'Work Under Review',
            MaintenanceRequest.Status.RESOLVED: 'Work Resolved',
            MaintenanceRequest.Status.NOT_REPAIRABLE: 'Reported Not Repairable',
            MaintenanceRequest.Status.UNREPAIRABLE: 'Reported Not Repairable',
        }
        entry_label = label_map.get(new_status, STATUS_LABELS.get(new_status, new_status))

        MaintenanceTimelineEntry.objects.create(
            maintenance_request=maintenance_request,
            status=new_status,
            label=entry_label,
            note=technician_notes,
            work_done=work_done,
            completed_by=tech_name,
        )

        # Asset Lifecycle integration
        if maintenance_request.asset_unit:
            if new_status in [MaintenanceRequest.Status.RESOLVED, MaintenanceRequest.Status.COMPLETED, MaintenanceRequest.Status.VERIFIED]:
                maintenance_request.asset_unit.status = 'AVAILABLE'
                maintenance_request.asset_unit.save()
            elif new_status in [MaintenanceRequest.Status.UNREPAIRABLE, MaintenanceRequest.Status.NOT_REPAIRABLE]:
                maintenance_request.asset_unit.status = 'SCRAPPED'
                maintenance_request.asset_unit.save()

        # Audit log integration
        try:
            from apps.audit.services import AuditLogService
            action_map = {
                MaintenanceRequest.Status.TODO: 'MAINTENANCE_TODO',
                MaintenanceRequest.Status.IN_PROGRESS: 'MAINTENANCE_STARTED',
                MaintenanceRequest.Status.REVIEW: 'MAINTENANCE_REVIEW',
                MaintenanceRequest.Status.RESOLVED: 'MAINTENANCE_RESOLVED',
                MaintenanceRequest.Status.COMPLETED: 'MAINTENANCE_RESOLVED',
                MaintenanceRequest.Status.NOT_REPAIRABLE: 'MAINTENANCE_UPDATED',
                MaintenanceRequest.Status.UNREPAIRABLE: 'MAINTENANCE_UPDATED',
            }
            action_name = action_map.get(new_status, 'MAINTENANCE_UPDATED')

            AuditLogService.log_action(
                action=action_name,
                module='MAINTENANCE',
                asset=maintenance_request.asset,
                asset_name=maintenance_request.asset.name if maintenance_request.asset else '',
                description=f"Maintenance ticket {maintenance_request.request_id} work update submitted by {tech_name}. Status: {new_status}. Findings: {work_done}",
                request=request,
                old_value={'status': old_status},
                new_value={'status': new_status, 'work_done': work_done, 'notes': technician_notes}
            )
        except Exception:
            pass

        # Notification integration
        try:
            from apps.notifications.services import create_system_notification
            asset_name = maintenance_request.asset.name if maintenance_request.asset else 'Asset'
            create_system_notification(
                title=f"Maintenance Work Update ({maintenance_request.request_id})",
                message=f"Technician {tech_name} updated ticket {maintenance_request.request_id} ({asset_name}) to status {new_status}.",
                notification_type='MAINTENANCE',
                sub_type='MAINTENANCE_UPDATED',
                related_asset_id=maintenance_request.asset.id if maintenance_request.asset else None,
                related_asset_name=asset_name,
                related_maintenance_id=maintenance_request.id,
                related_maintenance_request_id=maintenance_request.request_id,
                target_role='operations_manager'
            )
        except Exception:
            pass

        output = MaintenanceDetailSerializer(maintenance_request)
        return Response(output.data, status=status.HTTP_200_OK)


class MaintenanceStatsView(APIView):
    """GET /api/maintenance/stats/"""

    def get(self, request):
        from apps.users.models import User
        qs = MaintenanceRequest.objects.all()
        # Employee sirf apne requests ki stats dekhe
        if request.user.is_authenticated and getattr(request.user, 'role', '') == User.Role.EMPLOYEE:
            qs = qs.filter(requested_by=request.user)
        data = {
            'total':      qs.count(),
            'pending':    qs.filter(status=MaintenanceRequest.Status.PENDING).count(),
            'inProgress': qs.filter(status=MaintenanceRequest.Status.IN_PROGRESS).count(),
            'completed':  qs.filter(
                status__in=[
                    MaintenanceRequest.Status.COMPLETED,
                    MaintenanceRequest.Status.VERIFIED,
                    MaintenanceRequest.Status.RESOLVED,
                ]
            ).count(),
        }
        return Response(MaintenanceStatsSerializer(data).data, status=status.HTTP_200_OK)