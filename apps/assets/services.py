import logging
import uuid
from datetime import date

from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import Asset, AssetCategory, AssetUnit, AssetAssignmentHistory

logger = logging.getLogger(__name__)


class AssetCategoryService:
    @staticmethod
    def list_categories():
        return AssetCategory.objects.all()

    @staticmethod
    def get_category(pk):
        return get_object_or_404(AssetCategory, pk=pk)

    @staticmethod
    def create_category(validated_data) -> AssetCategory:
        return AssetCategory.objects.create(**validated_data)

    @staticmethod
    def update_category(category, validated_data) -> AssetCategory:
        for field, value in validated_data.items():
            setattr(category, field, value)
        category.save()
        return category

    @staticmethod
    def delete_category(category) -> None:
        category.delete()


class AssetService:
    @staticmethod
    def list_assets(category_id=None, search=None, status=None, department=None, location=None, employee=None, warranty_status=None):
        from django.db.models import Q
        queryset = Asset.objects.select_related('category').prefetch_related(
            'units', 'units__assigned_to', 'units__purchase', 'units__purchase__supplier'
        ).distinct()

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if search:
            q = search.strip()
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(brand__icontains=q) |
                Q(model__icontains=q) |
                Q(category__name__icontains=q) |
                Q(units__serial_number__icontains=q) |
                Q(units__purchase__purchase_number__icontains=q) |
                Q(units__purchase__supplier__company__icontains=q)
            )

        if status:
            queryset = queryset.filter(units__status__iexact=status)

        if department:
            queryset = queryset.filter(units__assigned_to__department__icontains=department)

        if location:
            queryset = queryset.filter(units__location__icontains=location)

        if employee:
            queryset = queryset.filter(
                Q(units__assigned_to__first_name__icontains=employee) |
                Q(units__assigned_to__last_name__icontains=employee) |
                Q(units__assigned_to__email__icontains=employee)
            )

        return queryset

    @staticmethod
    def get_asset(pk):
        return get_object_or_404(
            Asset.objects.select_related('category').prefetch_related('units__assigned_to'),
            pk=pk
        )

    @staticmethod
    def create_asset(validated_data, request=None) -> Asset:
        purchase_cost = validated_data.get('purchase_cost') or 0
        validated_data.setdefault('purchase_cost', purchase_cost)
        validated_data['current_value'] = purchase_cost
        if not validated_data.get('purchase_date'):
            validated_data['purchase_date'] = date.today()

        asset = Asset.objects.create(**validated_data)

        try:
            from apps.audit.services import AuditLogService
            AuditLogService.log_action(
                action='ASSET_CREATED',
                module='ASSETS',
                asset=asset,
                asset_name=asset.name,
                description=f"Inventory product '{asset.name}' was added to catalogue.",
                new_value={
                    'name': asset.name,
                    'category': asset.category.name if asset.category else '',
                    'brand': asset.brand,
                    'model': asset.model
                },
                request=request
            )
        except Exception as e:
            logger.warning(f"Audit creation failed: {e}")

        try:
                from apps.notifications.services import create_system_notification
                from apps.users.models import User
                create_system_notification(
                    title='New Asset Added',
                    message=f"New asset '{asset.name}' was added to catalogue.",
                    notification_type='ASSETS',
                    sub_type='ASSET_CREATED',
                    related_asset_id=asset.id,
                    related_asset_name=asset.name,
                    target_role=User.Role.OPERATIONS_MANAGER,
                )
        except Exception as e:
                logger.warning(f"Notification asset_created failed: {e}")

        return asset

    @staticmethod
    def update_asset(asset: Asset, validated_data, request=None) -> Asset:
        old_data = {
            'name': asset.name,
            'brand': asset.brand,
            'model': asset.model,
            'category': asset.category.name if asset.category else ''
        }
        for field, value in validated_data.items():
            setattr(asset, field, value)
        asset.save()

        try:
            from apps.audit.services import AuditLogService
            AuditLogService.log_action(
                action='ASSET_UPDATED',
                module='ASSETS',
                asset=asset,
                asset_name=asset.name,
                description=f"Asset details for '{asset.name}' updated.",
                old_value=old_data,
                new_value={
                    'name': asset.name,
                    'brand': asset.brand,
                    'model': asset.model,
                    'category': asset.category.name if asset.category else ''
                },
                request=request
            )
        except Exception as e:
            logger.warning(f"Audit update failed: {e}")

        try:
            from apps.notifications.services import create_system_notification
            from apps.users.models import User
            create_system_notification(
                title='Asset Updated',
                message=f"Asset '{asset.name}' details were updated.",
                notification_type='ASSETS',
                sub_type='ASSET_UPDATED',
                related_asset_id=asset.id,
                related_asset_name=asset.name,
                target_role=User.Role.OPERATIONS_MANAGER,
            )
        except Exception as e:
            logger.warning(f"Notification asset_updated failed: {e}")

        return asset

    @staticmethod
    @transaction.atomic
    def delete_asset(asset: Asset, request=None) -> None:
        asset_name = asset.name
        asset.purchases.all().delete()
        asset.units.all().delete()
        asset.delete()
        try:
            from apps.audit.services import AuditLogService
            AuditLogService.log_action(
                action='ASSET_RETIRED',
                module='ASSETS',
                asset_name=asset_name,
                description=f"Asset definition '{asset_name}' deleted/retired from catalogue.",
                request=request
            )
        except Exception as e:
            logger.warning(f"Audit delete failed: {e}")

    # ------------------------------------------------------------------
    # AssetUnit management
    # ------------------------------------------------------------------

    @staticmethod
    def list_units(asset: Asset, status=None):
        queryset = asset.units.select_related('assigned_to', 'purchase').all()
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    @staticmethod
    def create_units(asset: Asset, quantity: int, purchase=None) -> list:
        """
        Create `quantity` number of AssetUnit records for the given asset,
        typically called when a Purchase is created.
        """
        from django.db.models import Max
        from apps.common.utils import generate_display_id
        units = []
        max_unit = AssetUnit.objects.filter(asset=asset).aggregate(Max('unit_number'))['unit_number__max'] or 0

        current_num = max_unit
        for _ in range(int(quantity or 0)):
            current_num += 1
            disp_id = generate_display_id(AssetUnit, 'SER')
            unit = AssetUnit.objects.create(
                asset=asset,
                purchase=purchase,
                status=AssetUnit.Status.AVAILABLE,
                unit_number=current_num,
                display_id=disp_id,
                serial_number=disp_id,
            )
            units.append(unit)
        return units

    @staticmethod
    def get_unit(unit_id) -> AssetUnit:
        return get_object_or_404(
            AssetUnit.objects.select_related('asset', 'assigned_to'),
            pk=unit_id
        )

    @staticmethod
    def update_unit(unit: AssetUnit, validated_data, request=None) -> AssetUnit:
        old_status = unit.status
        old_location = unit.location
        for field, value in validated_data.items():
            setattr(unit, field, value)
        unit.save()

        if old_status != unit.status:
            try:
                from apps.audit.services import AuditLogService
                act = 'ASSET_SCRAPPED' if unit.status == AssetUnit.Status.SCRAPPED else 'ASSET_UPDATED'
                AuditLogService.log_action(
                    action=act,
                    module='ASSETS',
                    asset=unit.asset,
                    asset_unit=unit,
                    asset_name=unit.asset.name if unit.asset else '',
                    serial_number=unit.serial_number,
                    description=f"Physical unit {unit.serial_number} status updated to {unit.status}.",
                    old_value={'status': old_status, 'location': old_location},
                    new_value={'status': unit.status, 'location': unit.location},
                    request=request
                )
            except Exception as e:
                logger.warning(f"Audit unit status update failed: {e}")

        return unit

    @staticmethod
    def assign_unit(unit: AssetUnit, user_id=None, employee_name='', assigned_date=None, expected_return_date=None, notes='', request=None) -> AssetUnit:
        old_status = unit.status
        old_assigned = unit.assigned_to.email if unit.assigned_to else None

        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Auto-resolve user_id from employee_name if not provided
        if not user_id and employee_name:
            name_parts = employee_name.strip().split()
            candidate = None
            if len(name_parts) >= 2:
                candidate = User.objects.filter(
                    first_name__iexact=name_parts[0],
                    last_name__iexact=name_parts[-1]
                ).first()
            if not candidate:
                candidate = User.objects.filter(
                    first_name__iexact=name_parts[0]
                ).first()
            if not candidate:
                candidate = User.objects.filter(
                    email__icontains=name_parts[0]
                ).first()
            if candidate:
                user_id = candidate.pk

        unit.status = AssetUnit.Status.ASSIGNED
        unit.assigned_to_id = user_id
        unit.save()

        user_obj = None
        dept = ''
        if user_id:
            user_obj = User.objects.filter(pk=user_id).first()
            if user_obj:
                dept = getattr(user_obj, 'department', '') or ''
                if not employee_name:
                    employee_name = f"{user_obj.first_name} {user_obj.last_name}".strip() or user_obj.email

        AssetAssignmentHistory.objects.create(
            unit=unit,
            user=user_obj,
            employee_name=employee_name or 'Employee',
            department=dept,
            assigned_date=assigned_date or date.today(),
            expected_return_date=expected_return_date,
            notes=notes or '',
            status=AssetAssignmentHistory.Status.ACTIVE
        )

        try:
            from apps.audit.services import AuditLogService
            AuditLogService.log_action(
                action='ASSET_ASSIGNED',
                module='ASSIGNMENTS',
                asset=unit.asset,
                asset_unit=unit,
                asset_name=unit.asset.name if unit.asset else '',
                serial_number=unit.serial_number,
                description=f"Asset {unit.asset.name if unit.asset else 'Asset'} (SN: {unit.serial_number}) assigned to {employee_name}.",
                old_value={'status': old_status, 'assigned_to': old_assigned or 'None'},
                new_value={'status': 'ASSIGNED', 'assigned_to': employee_name},
                request=request
            )
        except Exception as e:
            logger.warning(f"Audit assign_unit failed: {e}")

        try:
            from apps.notifications.services import create_system_notification
            asset_name = unit.asset.name if (unit and unit.asset) else 'Asset'
            sn = unit.serial_number or ''
            create_system_notification(
                title='Asset Assigned',
                message=f'Asset {asset_name} ({sn}) has been assigned to {employee_name}.',
                notification_type='ASSIGNMENTS',
                sub_type='ASSIGNMENT_CREATED',
                related_asset_id=unit.asset.id if (unit and unit.asset) else None,
                related_asset_name=asset_name,
                user=user_obj,
            )
        except Exception as e:
            logger.warning(f"Notification trigger failed: {e}")

        return unit

    @staticmethod
    def return_unit(unit: AssetUnit, request=None) -> AssetUnit:
        old_status = unit.status
        unit.status = AssetUnit.Status.AVAILABLE
        unit.assigned_to = None
        unit.save()

        active_history = unit.assignment_history.filter(status=AssetAssignmentHistory.Status.ACTIVE).first()
        emp_name = 'Worker'
        if active_history:
            emp_name = active_history.employee_name or 'Worker'
            active_history.status = AssetAssignmentHistory.Status.RETURNED
            active_history.returned_date = date.today()
            active_history.save()

        try:
            from apps.audit.services import AuditLogService
            AuditLogService.log_action(
                action='ASSET_RETURNED',
                module='ASSIGNMENTS',
                asset=unit.asset,
                asset_unit=unit,
                asset_name=unit.asset.name if unit.asset else '',
                serial_number=unit.serial_number,
                description=f"Asset {unit.asset.name if unit.asset else 'Asset'} (SN: {unit.serial_number}) returned by {emp_name}.",
                old_value={'status': old_status, 'assigned_to': emp_name},
                new_value={'status': 'AVAILABLE', 'assigned_to': 'None'},
                request=request
            )
        except Exception as e:
            logger.warning(f"Audit return_unit failed: {e}")

        try:
            from apps.notifications.services import create_system_notification
            asset_name = unit.asset.name if (unit and unit.asset) else 'Asset'
            sn = unit.serial_number or ''
            create_system_notification(
                title='Asset Returned',
                message=f'Asset {asset_name} ({sn}) has been returned by {emp_name}.',
                notification_type='ASSIGNMENTS',
                sub_type='ASSIGNMENT_RETURN',
                related_asset_id=unit.asset.id if (unit and unit.asset) else None,
                related_asset_name=asset_name,
                user=active_history.user if active_history else None,
            )
        except Exception as e:
            logger.warning(f"Notification trigger failed: {e}")

        return unit


class AssignmentService:
    @staticmethod
    def list_assignments(status=None, department=None, search=None, location=None, employee=None, asset=None):
        from django.db.models import Q
        queryset = AssetAssignmentHistory.objects.select_related(
            'unit', 'unit__asset', 'unit__asset__category', 'user'
        ).order_by('-assigned_date')

        if status:
            status_map = {'assigned': 'ACTIVE', 'active': 'ACTIVE', 'returned': 'RETURNED'}
            normalised = status_map.get(status.lower(), status.upper())
            queryset = queryset.filter(status=normalised)

        if department:
            queryset = queryset.filter(department__icontains=department)

        if location:
            queryset = queryset.filter(unit__location__icontains=location)

        if employee:
            queryset = queryset.filter(
                Q(employee_name__icontains=employee) | Q(user__email__icontains=employee)
            )

        if asset:
            queryset = queryset.filter(
                Q(unit__asset__id=asset) | Q(unit__id=asset) | Q(unit__asset__name__icontains=asset)
            )

        if search:
            q = search.strip()
            queryset = queryset.filter(
                Q(employee_name__icontains=q) |
                Q(unit_serial_snapshot__icontains=q) |
                Q(unit__serial_number__icontains=q) |
                Q(asset_name_snapshot__icontains=q) |
                Q(unit__asset__name__icontains=q) |
                Q(department__icontains=q) |
                Q(user__email__icontains=q)
            )

        return queryset

    @staticmethod
    @transaction.atomic
    def transfer_assignment(assignment: AssetAssignmentHistory, new_user_id, new_employee_name, new_department=None, transfer_date=None, notes=None, request=None) -> AssetAssignmentHistory:
        old_emp = assignment.employee_name
        assignment.status = AssetAssignmentHistory.Status.RETURNED
        assignment.returned_date = transfer_date or date.today()
        assignment.save()

        unit = assignment.unit
        if unit:
            unit.status = AssetUnit.Status.ASSIGNED
            unit.assigned_to_id = new_user_id
            unit.save()

        new_assignment = AssetAssignmentHistory.objects.create(
            unit=unit,
            user_id=new_user_id,
            employee_name=new_employee_name,
            department=new_department or (unit.assigned_to.department if (unit and unit.assigned_to) else ''),
            assigned_date=transfer_date or date.today(),
            notes=notes or f"Transferred from {assignment.employee_name}",
            status=AssetAssignmentHistory.Status.ACTIVE,
        )

        try:
            from apps.audit.services import AuditLogService
            AuditLogService.log_action(
                action='ASSET_TRANSFERRED',
                module='ASSIGNMENTS',
                asset=unit.asset if unit else None,
                asset_unit=unit,
                asset_name=unit.asset.name if (unit and unit.asset) else '',
                serial_number=unit.serial_number if unit else '',
                description=f"Asset '{unit.asset.name if (unit and unit.asset) else 'Asset'}' transferred from {old_emp} to {new_employee_name}.",
                old_value={'employee_name': old_emp, 'status': 'ASSIGNED'},
                new_value={'employee_name': new_employee_name, 'status': 'ASSIGNED'},
                request=request
            )
        except Exception as e:
            logger.warning(f"Audit transfer_assignment failed: {e}")

        try:
            from apps.notifications.services import create_system_notification
            asset_name = unit.asset.name if (unit and unit.asset) else 'Asset'
            sn = unit.serial_number if unit else ''
            create_system_notification(
                title='Asset Transferred',
                message=f'Asset {asset_name} ({sn}) transferred from {assignment.employee_name} to {new_employee_name}.',
                notification_type='ASSIGNMENTS',
                sub_type='ASSIGNMENT_TRANSFER',
                related_asset_id=unit.asset.id if (unit and unit.asset) else None,
                related_asset_name=asset_name,
                related_assignment_id=new_assignment.id,
                user=new_assignment.user,
            )
        except Exception as e:
            logger.warning(f"Notification trigger failed: {e}")

        return new_assignment

    @staticmethod
    def get_assignment(pk):
        return get_object_or_404(
            AssetAssignmentHistory.objects.select_related(
                'unit', 'unit__asset', 'unit__asset__category', 'user'
            ),
            pk=pk,
        )

    @staticmethod
    def create_assignment(validated_data, request=None) -> AssetAssignmentHistory:
        unit: AssetUnit = validated_data['unit']
        AssetService.assign_unit(
            unit,
            user_id=validated_data.get('user_id'),
            employee_name=validated_data['employee_name'],
            assigned_date=validated_data.get('assigned_date'),
            expected_return_date=validated_data.get('expected_return_date'),
            notes=validated_data.get('notes', ''),
            request=request
        )
        return unit.assignment_history.filter(status=AssetAssignmentHistory.Status.ACTIVE).first()

    @staticmethod
    def update_assignment(assignment: AssetAssignmentHistory, validated_data) -> AssetAssignmentHistory:
        validated_data.pop('unit', None)
        for field, value in validated_data.items():
            setattr(assignment, field, value)
        assignment.save()
        return assignment

    @staticmethod
    def return_assignment(assignment: AssetAssignmentHistory, request=None) -> AssetAssignmentHistory:
        if assignment.status == AssetAssignmentHistory.Status.RETURNED:
            return assignment
        AssetService.return_unit(assignment.unit, request=request)
        assignment.refresh_from_db()
        return assignment

    @staticmethod
    def get_stats() -> dict:
        today = date.today()
        first_of_month = today.replace(day=1)

        total_active = AssetAssignmentHistory.objects.filter(
            status=AssetAssignmentHistory.Status.ACTIVE
        ).count()

        pending_returns = AssetAssignmentHistory.objects.filter(
            status=AssetAssignmentHistory.Status.ACTIVE,
            expected_return_date__lte=today,
            expected_return_date__isnull=False,
        ).count()

        returned_this_month = AssetAssignmentHistory.objects.filter(
            status=AssetAssignmentHistory.Status.RETURNED,
            returned_date__gte=first_of_month,
        ).count()

        return {
            'total_active': total_active,
            'pending_returns': pending_returns,
            'returned_this_month': returned_this_month,
        }

    @staticmethod
    def delete_assignment(assignment: AssetAssignmentHistory) -> None:
        assignment.delete()

# ------------------------------------------------------------------
# Asset Request Service
# ------------------------------------------------------------------

def _get_authorized_managers():
    """
    Return all User objects whose role is manager/admin OR who have been
    granted the 'request.view' individual permission.

    We query every user whose role is operations_manager or system_admin
    (they have all permissions by default) PLUS any user who has
    'request.view' explicitly in their individual permissions JSON field.
    """
    from apps.users.models import User
    from django.db.models import Q

    manager_roles = [
        User.Role.OPERATIONS_MANAGER,
        User.Role.SYSTEM_ADMIN,
    ]

    # Users whose role already grants full access
    role_based = Q(role__in=manager_roles)

    # Users with the explicit individual permission 'request.view'
    # (stored as a JSON list; we do a contains search)
    perm_based = Q(permissions__contains='request.view')

    return list(
        User.objects.filter(
            (role_based | perm_based),
            is_active=True,
        ).distinct()
    )


class AssetRequestService:
    @staticmethod
    def list_requests(user=None, status=None, search=None):
        from .models import AssetRequest
        from apps.users.models import User
        from django.db.models import Q

        qs = AssetRequest.objects.select_related(
            'employee', 'assigned_unit', 'assigned_unit__asset'
        ).order_by('-created_at')

        # Ownership enforcement: Employees can ONLY view their own requests
        if user and getattr(user, 'role', '') == User.Role.EMPLOYEE:
            qs = qs.filter(employee=user)

        if status:
            qs = qs.filter(status__iexact=status)

        if search:
            q = search.strip()
            qs = qs.filter(
                Q(request_number__icontains=q) |
                Q(requested_asset__icontains=q) |
                Q(category_name__icontains=q) |
                Q(employee_name__icontains=q) |
                Q(reason__icontains=q)
            )
        return qs

    @staticmethod
    def get_request(pk, user=None):
        from .models import AssetRequest
        from apps.users.models import User
        from django.core.exceptions import PermissionDenied
        req = AssetRequest.objects.select_related(
            'employee', 'assigned_unit', 'assigned_unit__asset'
        ).get(pk=pk)
        if user and getattr(user, 'role', '') == User.Role.EMPLOYEE and req.employee_id != user.id:
            raise PermissionDenied('You are not authorized to access this request.')
        return req

    @staticmethod
    @transaction.atomic
    def create_request(user, validated_data):
        from .models import AssetRequest, AssetUnit
        from apps.notifications.models import Notification
        from apps.notifications.services import create_system_notification, send_push_notification
        import uuid

        count = AssetRequest.objects.count() + 1001
        while True:
            req_num = f'REQ-{count}'
            if not AssetRequest.objects.filter(request_number=req_num).exists():
                break
            count += 1
        emp_name = f'{user.first_name} {user.last_name}'.strip() or user.email

        unit_id = validated_data.get('unitId') or validated_data.get('unit_id')
        assigned_unit = None
        if unit_id:
            unit_str = str(unit_id).strip()
            if '-unit-' in unit_str:
                unit_str = unit_str.split('-unit-')[-1]
            try:
                assigned_unit = AssetUnit.objects.filter(id=uuid.UUID(unit_str)).first()
            except (ValueError, TypeError):
                pass

        req = AssetRequest.objects.create(
            request_number=req_num,
            employee=user,
            employee_name=emp_name,
            department=getattr(user, 'department', '') or '',
            category_name=validated_data.get('category_name', ''),
            requested_asset=validated_data.get('requested_asset', ''),
            reason=validated_data.get('reason', ''),
            priority=validated_data.get('priority', AssetRequest.Priority.NORMAL),
            notes=validated_data.get('notes', ''),
            status=AssetRequest.Status.PENDING,
            assigned_unit=assigned_unit,
        )

        # ------------------------------------------------------------------
        # 1. Notify the submitting employee — goes through create_system_notification
        #    so the push notification is sent automatically (via the
        #    post_save signal on Notification).
        # ------------------------------------------------------------------
        try:
            create_system_notification(
                title='Asset Request Submitted',
                message=(
                    f'Your asset request {req_num} for {req.requested_asset} '
                    f'has been submitted and is pending approval.'
                ),
                notification_type=Notification.NotificationType.ASSETS,
                sub_type='ASSET_REQUEST_SUBMITTED',
                related_request_id=req.id,
                related_request_number=req_num,
                user=user,
            )
        except Exception as e:
            logger.warning(f'[AssetRequest] Employee submission notification failed: {e}')

        # ------------------------------------------------------------------
        # 2. Notify each authorized manager/admin individually.
        #    We bulk_create the DB rows for speed, then loop to send push
        #    notifications to each manager.
        # ------------------------------------------------------------------
        try:
            mgr_message = (
                f'New asset request {req_num} submitted by {emp_name} '
                f'for {req.requested_asset} (Priority: {req.priority}).'
            )
            managers = _get_authorized_managers()
            bulk_notifications = [
                Notification(
                    user=mgr,
                    title='New Asset Request Submitted',
                    message=mgr_message,
                    type=Notification.NotificationType.ASSETS,
                    sub_type='ASSET_REQUEST_NEW',
                    related_request_id=req.id,
                    related_request_number=req_num,
                )
                for mgr in managers
            ]
            if bulk_notifications:
                Notification.objects.bulk_create(bulk_notifications, ignore_conflicts=True)
                for mgr in managers:
                    send_push_notification(
                        user=mgr,
                        title='New Asset Request Submitted',
                        body=mgr_message,
                        data={'type': Notification.NotificationType.ASSETS}
                    )
        except Exception as e:
            logger.warning(f'[AssetRequest] Manager notification failed: {e}')

        return req

    @classmethod
    @transaction.atomic
    def approve_request(cls, request_obj, user):
        from .models import AssetRequest, AssetUnit
        from apps.notifications.models import Notification
        from apps.notifications.services import create_system_notification
        from django.utils import timezone

        request_obj.approved_at = timezone.now()
        request_obj.assigned_by = user

        # If a unit was already selected/attached and is available, auto-assign it directly upon approval
        if request_obj.assigned_unit and request_obj.assigned_unit.status == AssetUnit.Status.AVAILABLE:
            return cls.assign_unit(request_obj, request_obj.assigned_unit, user)
        else:
            request_obj.status = AssetRequest.Status.APPROVED
            request_obj.save()

            # Notify employee about approval
            try:
                create_system_notification(
                    title='Asset Request Approved',
                    message=(
                        f'Your request {request_obj.request_number} for '
                        f'{request_obj.requested_asset} has been approved. '
                        f'Waiting for asset assignment.'
                    ),
                    notification_type=Notification.NotificationType.ASSETS,
                    sub_type='ASSET_REQUEST_APPROVED',
                    related_request_id=request_obj.id,
                    related_request_number=request_obj.request_number,
                    user=request_obj.employee,
                )
            except Exception as e:
                logger.warning(f'[AssetRequest] Approve notification failed: {e}')

            return request_obj

    @staticmethod
    @transaction.atomic
    def reject_request(request_obj, reason, user):
        from .models import AssetRequest
        from apps.notifications.models import Notification
        from apps.notifications.services import create_system_notification

        request_obj.status = AssetRequest.Status.REJECTED
        request_obj.rejection_reason = reason or 'Request rejected by manager.'
        request_obj.assigned_by = user
        request_obj.save()

        # Notify employee only.
        try:
            create_system_notification(
                title='Asset Request Rejected',
                message=(
                    f'Your request {request_obj.request_number} for '
                    f'{request_obj.requested_asset} has been rejected. '
                    f'Reason: {request_obj.rejection_reason}'
                ),
                notification_type=Notification.NotificationType.ASSETS,
                sub_type='ASSET_REQUEST_REJECTED',
                related_request_id=request_obj.id,
                related_request_number=request_obj.request_number,
                user=request_obj.employee,
            )
        except Exception as e:
            logger.warning(f'[AssetRequest] Reject notification failed: {e}')

        return request_obj

    @staticmethod
    @transaction.atomic
    def assign_unit(request_obj, unit, user):
        from .models import AssetRequest, AssetUnit, AssetAssignmentHistory
        from apps.notifications.models import Notification
        from apps.notifications.services import create_system_notification
        from django.utils import timezone
        from datetime import date

        if unit.status != AssetUnit.Status.AVAILABLE:
            raise ValueError('Selected asset unit is not available for assignment.')

        unit.status = AssetUnit.Status.ASSIGNED
        unit.assigned_to = request_obj.employee
        unit.save()

        emp_name = (
            request_obj.employee_name
            or f'{request_obj.employee.first_name} {request_obj.employee.last_name}'.strip()
            or request_obj.employee.email
        )

        # Create assignment history with PENDING_RECEIPT status
        assignment = AssetAssignmentHistory.objects.create(
            unit=unit,
            user=request_obj.employee,
            employee_name=emp_name,
            department=request_obj.department or getattr(request_obj.employee, 'department', ''),
            assigned_date=date.today(),
            notes=f'Assigned via Request {request_obj.request_number}',
            status=AssetAssignmentHistory.Status.ACTIVE,
            receipt_status=AssetAssignmentHistory.ReceiptStatus.PENDING_RECEIPT,
        )

        request_obj.assigned_unit = unit
        request_obj.status = AssetRequest.Status.ASSIGNED
        request_obj.assigned_at = timezone.now()
        request_obj.assigned_by = user
        request_obj.save()

        asset_title = unit.asset.name if unit.asset else 'Asset'
        sn = unit.serial_number or ''

        # Notify employee only — they need to confirm receipt.
        try:
            create_system_notification(
                title='Asset Assigned',
                message=(
                    f'Your {asset_title} (Serial: {sn}) has been assigned to you. '
                    f'Please confirm receipt in My Assets.'
                ),
                notification_type=Notification.NotificationType.ASSIGNMENTS,
                sub_type='ASSET_REQUEST_ASSIGNED',
                related_asset_id=unit.asset_id,
                related_asset_name=asset_title,
                related_assignment_id=assignment.id,
                related_request_id=request_obj.id,
                related_request_number=request_obj.request_number,
                user=request_obj.employee,
            )
        except Exception as e:
            logger.warning(f'[AssetRequest] Assign notification failed: {e}')

        return request_obj

    @staticmethod
    @transaction.atomic
    def confirm_receipt(user, request_id=None, assignment_id=None, condition='Good Condition', notes=''):
        from .models import AssetRequest, AssetAssignmentHistory
        from apps.notifications.models import Notification
        from apps.notifications.services import send_push_notification
        from django.utils import timezone
        from django.core.exceptions import PermissionDenied

        now = timezone.now()
        updated_item = None
        asset_name_for_notif = 'asset'
        req_number_for_notif = ''
        req_id_for_notif = None

        if assignment_id:
            assignment = AssetAssignmentHistory.objects.select_related(
                'unit', 'unit__asset', 'user'
            ).get(pk=assignment_id)
            if (assignment.user_id != user.id
                    and assignment.unit
                    and assignment.unit.assigned_to_id != user.id):
                raise PermissionDenied('You are not authorized to confirm receipt for this asset.')

            assignment.receipt_status = AssetAssignmentHistory.ReceiptStatus.RECEIVED
            assignment.received_at = now
            assignment.received_condition = condition
            assignment.receipt_notes = notes
            assignment.save()
            updated_item = assignment

            if assignment.unit and assignment.unit.asset:
                asset_name_for_notif = assignment.unit.asset.name

            # Find matching asset request and update it
            if assignment.unit:
                reqs = AssetRequest.objects.filter(
                    assigned_unit=assignment.unit,
                    employee=user,
                    status=AssetRequest.Status.ASSIGNED,
                )
                for req in reqs:
                    req.status = AssetRequest.Status.RECEIVED
                    req.received_at = now
                    req.save()
                    req_number_for_notif = req.request_number
                    req_id_for_notif = req.id

        elif request_id:
            req = AssetRequest.objects.select_related('employee', 'assigned_unit').get(pk=request_id)
            if req.employee_id != user.id:
                raise PermissionDenied('You are not authorized to confirm receipt for this request.')

            req.status = AssetRequest.Status.RECEIVED
            req.received_at = now
            req.save()
            updated_item = req
            req_number_for_notif = req.request_number
            req_id_for_notif = req.id

            if req.assigned_unit and req.assigned_unit.asset:
                asset_name_for_notif = req.assigned_unit.asset.name

            # Update assignment history
            if req.assigned_unit:
                histories = AssetAssignmentHistory.objects.filter(
                    unit=req.assigned_unit,
                    user=user,
                    status=AssetAssignmentHistory.Status.ACTIVE,
                )
                for h in histories:
                    h.receipt_status = AssetAssignmentHistory.ReceiptStatus.RECEIVED
                    h.received_at = now
                    h.received_condition = condition
                    h.receipt_notes = notes
                    h.save()

        # ------------------------------------------------------------------
        # Notify each authorized manager/admin individually (no broadcast).
        # The employee does NOT get a redundant "you confirmed your own
        # receipt" notification here.
        # ------------------------------------------------------------------
        try:
            emp_name = f'{user.first_name} {user.last_name}'.strip() or user.email
            mgr_message = (
                f'{emp_name} has confirmed receipt of {asset_name_for_notif} '
                f'(Condition: {condition}).'
            )
            if req_number_for_notif:
                mgr_message += f' Request: {req_number_for_notif}.'

            managers = _get_authorized_managers()
            bulk_notifications = [
                Notification(
                    user=mgr,
                    title='Asset Receipt Confirmed',
                    message=mgr_message,
                    type=Notification.NotificationType.ASSIGNMENTS,
                    sub_type='ASSET_RECEIPT_CONFIRMED',
                    related_request_id=req_id_for_notif,
                    related_request_number=req_number_for_notif,
                )
                for mgr in managers
            ]
            if bulk_notifications:
                Notification.objects.bulk_create(bulk_notifications, ignore_conflicts=True)
                for mgr in managers:
                    send_push_notification(
                        user=mgr,
                        title='Asset Receipt Confirmed',
                        body=mgr_message,
                        data={'type': Notification.NotificationType.ASSIGNMENTS}
                    )
        except Exception as e:
            logger.warning(f'[AssetRequest] Receipt-confirmed manager notification failed: {e}')

        return updated_item