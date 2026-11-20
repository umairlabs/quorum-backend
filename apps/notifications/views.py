from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Notification, UserNotificationPreference, FCMDevice
from .serializers import NotificationSerializer, UserNotificationPreferenceSerializer, FCMDeviceSerializer
from apps.users.models import User
from apps.maintenance.models import MaintenanceRequest

# Roles that are considered management-level (receive operational notifications)
MANAGER_ROLES = {
    User.Role.SYSTEM_ADMIN,
    User.Role.OPERATIONS_MANAGER,
    'system_admin',
    'operations_manager',
    'SYSTEM_ADMIN',
    'OPERATIONS_MANAGER',
    'SUPER_ADMIN',
    'super_admin',
    'ADMIN',
    'admin',
    'MANAGER',
    'manager',
}

TECHNICIAN_ROLES = {
    User.Role.EXTERNAL_TECHNICIAN,
    'external_technician',
    'EXTERNAL_TECHNICIAN',
    'TECH',
    'tech',
    'TECHNICIAN', 
    'technician',
}


def _is_manager_or_admin(role: str) -> bool:
    return role in MANAGER_ROLES or role.upper() in {r.upper() for r in MANAGER_ROLES}


def _is_technician(role: str) -> bool:
    return role in TECHNICIAN_ROLES or role.upper() in {r.upper() for r in TECHNICIAN_ROLES}


def _is_employee(role: str) -> bool:
    r = role.upper()
    return r == 'EMPLOYEE'


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = (getattr(user, 'role', '') or '').strip()

        if _is_technician(role):
            # ----------------------------------------------------------------
            # Technicians: their own user-targeted notifications PLUS
            # all MAINTENANCE type notifications (they handle maintenance work).
            # ----------------------------------------------------------------
            qs = Notification.objects.filter(
                Q(user=user) |
                Q(type=Notification.NotificationType.MAINTENANCE)
            )

        elif _is_employee(role):
            # ----------------------------------------------------------------
            # Employees: ONLY notifications that are explicitly addressed to
            # this user (user=<this user>).
            # They must NEVER see role-broadcast or un-owned notifications.
            # ----------------------------------------------------------------
            qs = Notification.objects.filter(user=user)

        elif _is_manager_or_admin(role):
            # ----------------------------------------------------------------
            # Managers / Admins: their own user-targeted notifications PLUS
            # notifications that were broadcast to their role.
            # They do NOT see employee-owned notifications of other users.
            # ----------------------------------------------------------------
            role_lower = role.lower()
            qs = Notification.objects.filter(
                Q(user=user) |
                Q(target_role__iexact=role) |
                Q(target_role__iexact=role_lower)
            )

        else:
            # Unknown / unrecognised role — show only own notifications (safe default)
            qs = Notification.objects.filter(user=user)

        # ----------------------------------------------------------------
        # Apply per-user notification preference filters
        # ----------------------------------------------------------------
        pref, _ = UserNotificationPreference.objects.get_or_create(user=user)
        excluded_sub_types = []

        if not pref.maintenance_new_ticket:
            excluded_sub_types.extend(['MAINTENANCE_NEW', 'MAINTENANCE_CREATED'])
        if not pref.maintenance_assigned_to_tech:
            excluded_sub_types.append('MAINTENANCE_ASSIGNED')
        if not pref.maintenance_status_changed:
            excluded_sub_types.extend(['MAINTENANCE_STATUS_CHANGED', 'MAINTENANCE_STATUS'])
        if not pref.maintenance_high_priority:
            excluded_sub_types.extend(['MAINTENANCE_HIGH_PRIORITY', 'MAINTENANCE_HIGH'])
        if not pref.maintenance_critical_alert:
            excluded_sub_types.append('MAINTENANCE_CRITICAL')
        if not pref.maintenance_completed:
            excluded_sub_types.append('MAINTENANCE_COMPLETED')
        if not pref.maintenance_updated:
            excluded_sub_types.append('MAINTENANCE_UPDATED')

        if not pref.asset_assigned:
            excluded_sub_types.append('ASSET_ASSIGNED')
        if not pref.asset_transferred:
            excluded_sub_types.append('ASSET_TRANSFERRED')
        if not pref.asset_returned:
            excluded_sub_types.append('ASSET_RETURNED')
        if not pref.asset_retired:
            excluded_sub_types.append('ASSET_RETIRED')
        if not pref.asset_scrapped:
            excluded_sub_types.append('ASSET_SCRAPPED')
        if not pref.asset_maintenance_activity:
            excluded_sub_types.append('ASSET_MAINTENANCE_ACTIVITY')

        if not pref.assignment_new:
            excluded_sub_types.append('ASSIGNMENT_NEW')
        if not pref.assignment_transfer:
            excluded_sub_types.append('ASSIGNMENT_TRANSFER')
        if not pref.assignment_return:
            excluded_sub_types.append('ASSIGNMENT_RETURN')

        if not pref.warranty_expiring_soon:
            excluded_sub_types.extend(['WARRANTY_EXPIRING', 'WARRANTY_EXPIRING_SOON'])
        if not pref.warranty_expired:
            excluded_sub_types.append('WARRANTY_EXPIRED')

        if not pref.system_important_alerts:
            excluded_sub_types.extend(['SYSTEM_IMPORTANT', 'SYSTEM_ALERT', 'SYSTEM_NOTICE'])
        if not pref.system_required_actions:
            excluded_sub_types.extend(['SYSTEM_REQUIRED_ACTIONS', 'SYSTEM_ACTION'])

        if excluded_sub_types:
            query_filter = Q()
            for st in excluded_sub_types:
                query_filter |= Q(sub_type__iexact=st)
            qs = qs.exclude(query_filter)

        excluded_types = []
        if (not pref.maintenance_new_ticket and not pref.maintenance_assigned_to_tech and
                not pref.maintenance_status_changed and not pref.maintenance_high_priority and
                not pref.maintenance_critical_alert and not pref.maintenance_completed and
                not pref.maintenance_updated):
            excluded_types.append(Notification.NotificationType.MAINTENANCE)

        if (not pref.asset_assigned and not pref.asset_transferred and not pref.asset_returned and
                not pref.asset_retired and not pref.asset_scrapped and not pref.asset_maintenance_activity):
            excluded_types.append(Notification.NotificationType.ASSETS)

        if not pref.assignment_new and not pref.assignment_transfer and not pref.assignment_return:
            excluded_types.append(Notification.NotificationType.ASSIGNMENTS)

        if not pref.warranty_expiring_soon and not pref.warranty_expired:
            excluded_types.append(Notification.NotificationType.WARRANTY)

        if not pref.system_important_alerts and not pref.system_required_actions:
            excluded_types.append(Notification.NotificationType.SYSTEM)

        if excluded_types:
            qs = qs.exclude(type__in=excluded_types)

        # ----------------------------------------------------------------
        # Optional query-param filters (type / is_read)
        # ----------------------------------------------------------------
        notification_type = self.request.query_params.get('type')
        if notification_type and notification_type.upper() != 'ALL':
            if notification_type.upper() == 'UNREAD':
                qs = qs.filter(is_read=False)
            elif notification_type.upper() == 'READ':
                qs = qs.filter(is_read=True)
            else:
                qs = qs.filter(type__iexact=notification_type)

        is_read_param = self.request.query_params.get('is_read')
        if is_read_param is not None:
            if is_read_param.lower() == 'true':
                qs = qs.filter(is_read=True)
            elif is_read_param.lower() == 'false':
                qs = qs.filter(is_read=False)

        return qs.order_by('-created_at')

    def _get_owned_notification(self, pk):
        """
        Fetch a notification by PK and verify the requesting user owns it.
        A user 'owns' a notification if:
          - notification.user == request.user, OR
          - notification.target_role matches the user's role (manager/admin broadcast)
        Returns the notification or raises Http404 / PermissionDenied.
        """
        try:
            notification = Notification.objects.get(pk=pk)
        except Notification.DoesNotExist:
            return None

        user = self.request.user
        role = (getattr(user, 'role', '') or '').strip()

        # Direct ownership
        if notification.user_id and str(notification.user_id) == str(user.id):
            return notification

        # Role-broadcast ownership (manager/admin)
        if notification.target_role and _is_manager_or_admin(role):
            role_lower = role.lower()
            if (notification.target_role.lower() == role.lower() or
                    notification.target_role.lower() == role_lower):
                return notification

        # Technician: all maintenance notifications are accessible to them
        if _is_technician(role) and notification.type == Notification.NotificationType.MAINTENANCE:
            return notification

        return None  # not owned

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get', 'patch', 'put'], url_path='unread-count')
    def unread_count(self, request):
        qs = self.get_queryset().filter(is_read=False)
        return Response({'unread_count': qs.count()})

    @action(detail=True, methods=['post', 'patch', 'put'], url_path='read')
    def mark_read(self, request, pk=None):
        notification = self._get_owned_notification(pk)
        if notification is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=['post', 'patch', 'put'], url_path='unread')
    def mark_unread(self, request, pk=None):
        notification = self._get_owned_notification(pk)
        if notification is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        notification.is_read = False
        notification.save(update_fields=['is_read'])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=['post', 'patch', 'put'], url_path='mark-all-read')
    def mark_all_read(self, request):
        qs = self.get_queryset().filter(is_read=False)
        updated_count = qs.update(is_read=True)
        return Response({
            'detail': f'{updated_count} notifications marked as read.',
            'updated_count': updated_count
        })

    @action(detail=False, methods=['delete', 'post'], url_path='delete-all')
    def delete_all(self, request):
        qs = self.get_queryset()
        deleted_count, _ = qs.delete()
        return Response({
            'detail': f'{deleted_count} notifications deleted.',
            'deleted_count': deleted_count
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """Override destroy to enforce ownership before deletion."""
        pk = kwargs.get('pk')
        notification = self._get_owned_notification(pk)
        if notification is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get', 'post', 'patch', 'put'], url_path='preferences')
    def preferences(self, request):
        user = request.user
        pref, created = UserNotificationPreference.objects.get_or_create(user=user)

        if request.method in ['POST', 'PATCH', 'PUT']:
            serializer = UserNotificationPreferenceSerializer(pref, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        serializer = UserNotificationPreferenceSerializer(pref)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='register-device')
    def register_device(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'detail': 'Token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        device, created = FCMDevice.objects.update_or_create(
            token=token,
            defaults={'user': request.user}
        )
        return Response(
            {'detail': 'Device registered.', 'created': created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
