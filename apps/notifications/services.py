from .models import Notification, FCMDevice
from apps.maintenance.models import MaintenanceRequest
from apps.assets.models import AssetAssignmentHistory, AssetUnit, Asset
from apps.users.models import User
from django.conf import settings

# Firebase messaging is imported conditionally when notifications are enabled
try:
    from firebase_admin import messaging  # type: ignore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    messaging = None


def send_push_notification(user, title, body, data=None):
    """
    Sends a push notification to all devices registered for this user.
    
    Requires:
    1. firebase_admin to be installed
    2. FIREBASE_CREDENTIALS_PATH environment variable set
    3. Firebase Admin SDK to be initialized in settings
    
    If Firebase is not configured, this function silently returns without sending.
    """
    if not user:
        return
    
    # Check if Firebase is actually configured
    firebase_creds_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
    if not firebase_creds_path or not FIREBASE_AVAILABLE:
        # Firebase notifications are disabled or not configured
        return

    tokens = list(FCMDevice.objects.filter(user=user).values_list('token', flat=True))
    if not tokens:
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in (data or {}).items()},
        tokens=tokens,
    )

    try:
        response = messaging.send_each_for_multicast(message)
        # Remove tokens that are no longer valid (app uninstalled, token expired, etc.)
        if response.failure_count > 0:
            invalid_tokens = []
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    invalid_tokens.append(tokens[idx])
            if invalid_tokens:
                FCMDevice.objects.filter(token__in=invalid_tokens).delete()
    except Exception as e:
        print(f"Error sending push notification: {e}")



def create_system_notification(title, message, notification_type, user=None, target_role='', sub_type='', related_asset_id=None, related_asset_name='', related_maintenance_id=None, related_maintenance_request_id='', related_assignment_id=None, related_request_id=None, related_request_number=''):
    """
    Creates a Notification row. Push delivery is NOT done here — the
    `notification_post_save_push` signal in signals.py automatically fires
    on every Notification creation (regardless of where it was created),
    so calling send_push_notification() here as well would double-send
    the push to the user's devices.
    """
    notification = Notification.objects.create(
        user=user,
        target_role=target_role,
        title=title,
        message=message,
        type=notification_type,
        sub_type=sub_type,
        related_asset_id=related_asset_id,
        related_asset_name=related_asset_name,
        related_maintenance_id=related_maintenance_id,
        related_maintenance_request_id=related_maintenance_request_id,
        related_assignment_id=related_assignment_id,
        related_request_id=related_request_id,
        related_request_number=related_request_number,
    )

    return notification


def seed_notifications_from_real_events():
    if Notification.objects.exists():
        return

    # 1. Maintenance Tickets
    for req in MaintenanceRequest.objects.all():
        if req.priority in [MaintenanceRequest.Priority.HIGH, MaintenanceRequest.Priority.CRITICAL]:
            Notification.objects.create(
                title=f'Critical Maintenance Ticket: {req.request_id}',
                message=f'High priority ticket {req.request_id} for asset {req.asset.name} requires immediate action.',
                type=Notification.NotificationType.MAINTENANCE,
                sub_type='MAINTENANCE_CRITICAL',
                related_asset_id=req.asset.id,
                related_asset_name=req.asset.name,
                related_maintenance_id=req.id,
                related_maintenance_request_id=req.request_id,
                target_role=User.Role.EXTERNAL_TECHNICIAN,
            )

        Notification.objects.create(
            title=f'Maintenance Ticket {req.request_id}',
            message=f'Maintenance request {req.request_id} for {req.asset.name} ({req.component_or_issue_type}) is currently {req.status}.',
            type=Notification.NotificationType.MAINTENANCE,
            sub_type='MAINTENANCE_ASSIGNED' if req.status == MaintenanceRequest.Status.PENDING else 'MAINTENANCE_UPDATED',
            related_asset_id=req.asset.id,
            related_asset_name=req.asset.name,
            related_maintenance_id=req.id,
            related_maintenance_request_id=req.request_id,
            target_role=User.Role.EXTERNAL_TECHNICIAN,
        )

    # 2. Asset Assignments
    for assign in AssetAssignmentHistory.objects.select_related('unit__asset').all()[:10]:
        asset_name = assign.unit.asset.name if assign.unit and assign.unit.asset else 'Asset'
        Notification.objects.create(
            title='Asset Assigned',
            message=f'{asset_name} (#{assign.unit.serial_number}) has been assigned to {assign.employee_name}.',
            type=Notification.NotificationType.ASSIGNMENTS,
            sub_type='ASSIGNMENT_NEW',
            related_asset_id=assign.unit.asset.id if assign.unit and assign.unit.asset else None,
            related_asset_name=asset_name,
            related_assignment_id=assign.id,
            user=assign.user,
            target_role=User.Role.OPERATIONS_MANAGER,
        )

    # 3. Asset Stock & Warranty Alerts
    for asset in Asset.objects.all()[:5]:
        Notification.objects.create(
            title='Warranty Expiry Alert',
            message=f'Warranty for {asset.name} is expiring soon.',
            type=Notification.NotificationType.WARRANTY,
            sub_type='WARRANTY_EXPIRING',
            related_asset_id=asset.id,
            related_asset_name=asset.name,
            target_role=User.Role.OPERATIONS_MANAGER,
        )

    # 4. System Notifications for Admin
    Notification.objects.create(
        title='System Update',
        message='Asset management system ledger synchronization completed successfully.',
        type=Notification.NotificationType.SYSTEM,
        sub_type='SYSTEM_NOTICE',
        target_role=User.Role.SYSTEM_ADMIN,
    )