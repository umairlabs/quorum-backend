from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification
from apps.users.models import User

@receiver(post_save, sender=Notification)
def notification_post_save_push(sender, instance, created, **kwargs):
    """
    Firebase push notification handler.
    
    This signal is connected to the Notification model but Firebase push notifications
    are now OPTIONAL and must be explicitly enabled via environment variables.
    
    To enable push notifications:
    1. Set FIREBASE_CREDENTIALS_PATH in your environment
    2. Ensure firebase_admin is installed: pip install firebase-admin
    3. The service account JSON will be loaded from the path specified
    """
    if not created:
        return
    
    # Check if Firebase is actually enabled in settings
    from django.conf import settings
    firebase_creds_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
    
    if not firebase_creds_path:
        # Firebase notifications are disabled
        return
    
    try:
        from .services import send_push_notification
        data = {
            'notification_id': str(instance.id),
            'type': str(instance.type or ''),
            'sub_type': str(instance.sub_type or ''),
            'related_request_id': str(instance.related_request_id or ''),
            'related_request_number': str(instance.related_request_number or ''),
        }
        if instance.user:
            send_push_notification(
                user=instance.user,
                title=instance.title,
                body=instance.message,
                data=data
            )
        elif instance.target_role:
            role_users = User.objects.filter(role__iexact=instance.target_role)
            for role_user in role_users:
                send_push_notification(
                    user=role_user,
                    title=instance.title,
                    body=instance.message,
                    data=data
                )
    except Exception as e:
        print(f"[PushNotificationSignal] Error sending push notification: {e}")

