import logging
from .models import AuditLog

logger = logging.getLogger(__name__)


class AuditLogService:

    @staticmethod
    def generate_audit_id() -> str:
        last = AuditLog.objects.order_by('-audit_id').first()
        if last and last.audit_id and last.audit_id.startswith('AUD-'):
            try:
                last_num = int(last.audit_id.split('-')[1])
            except (ValueError, IndexError):
                last_num = AuditLog.objects.count()
        else:
            last_num = AuditLog.objects.count()

        count = last_num + 1
        candidate = f"AUD-{count:06d}"
        while AuditLog.objects.filter(audit_id=candidate).exists():
            count += 1
            candidate = f"AUD-{count:06d}"
        return candidate

    @staticmethod
    def get_client_ip(request) -> str:
        if not request:
            return ""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip

    @classmethod
    def log_action(
        cls,
        action: str,
        module: str,
        description: str,
        user=None,
        asset=None,
        asset_unit=None,
        asset_name: str = '',
        serial_number: str = '',
        old_value=None,
        new_value=None,
        request=None,
        metadata=None
    ) -> AuditLog:
        """
        Creates an immutable AuditLog entry after a successful business operation.
        """
        try:
            audit_id = cls.generate_audit_id()

            user_obj = user
            if not user_obj and request and hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
                user_obj = request.user

            user_name = "System"
            user_role = "System Administrator"

            if user_obj and getattr(user_obj, 'is_authenticated', False):
                first = getattr(user_obj, 'first_name', '') or ''
                last = getattr(user_obj, 'last_name', '') or ''
                full = f"{first} {last}".strip()
                user_name = full or getattr(user_obj, 'email', '') or getattr(user_obj, 'username', 'User')

                raw_role = getattr(user_obj, 'role', 'SYSTEM_ADMIN')
                role_map = {
                    'system_admin': 'System Administrator',
                    'SYSTEM_ADMIN': 'System Administrator',
                    'operations_manager': 'Operations Manager',
                    'OPERATIONS_MANAGER': 'Operations Manager',
                    'external_technician': 'External Technician',
                    'EXTERNAL_TECHNICIAN': 'External Technician',
                    'employee': 'Employee',
                    'EMPLOYEE': 'Employee',
                }
                user_role = role_map.get(raw_role, str(raw_role).title().replace('_', ' '))

            final_asset_name = asset_name
            if not final_asset_name and asset and hasattr(asset, 'name'):
                final_asset_name = asset.name
            elif not final_asset_name and asset_unit and asset_unit.asset:
                final_asset_name = asset_unit.asset.name

            final_serial = serial_number
            if not final_serial and asset_unit and hasattr(asset_unit, 'serial_number'):
                final_serial = asset_unit.serial_number

            ip_addr = cls.get_client_ip(request)

            audit_log = AuditLog.objects.create(
                audit_id=audit_id,
                user=user_obj if getattr(user_obj, 'is_authenticated', False) else None,
                user_name_snapshot=user_name,
                user_role_snapshot=user_role,
                action=action,
                module=module,
                asset=asset,
                asset_unit=asset_unit,
                asset_name_snapshot=final_asset_name,
                serial_number_snapshot=final_serial,
                description=description,
                old_value=old_value or {},
                new_value=new_value or {},
                ip_address=ip_addr,
                metadata=metadata or {}
            )
            return audit_log
        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}", exc_info=True)
            return None