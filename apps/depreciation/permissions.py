from rest_framework.permissions import BasePermission

class IsManagerOrAdmin(BasePermission):
    """
    Allows access only to authenticated Admin or Manager roles.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        role = getattr(request.user, 'role', '')
        if isinstance(role, str):
            role = role.upper().replace(' ', '_')
            
        allowed = [
            'SYSTEM_ADMIN',
            'SUPER_ADMIN',
            'ADMIN',
            'OPERATIONS_MANAGER',
            'MANAGER',
        ]
        return role in allowed or getattr(request.user, 'is_staff', False) or getattr(request.user, 'is_superuser', False)


class CanViewFinancials(BasePermission):
    """
    Allows read-only access to financial depreciation data for authorized roles.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
            
        role = getattr(request.user, 'role', '')
        if isinstance(role, str):
            role = role.upper().replace(' ', '_')
            
        disallowed = ['EMPLOYEE', 'EXTERNAL_TECHNICIAN', 'TECHNICIAN']
        if role in disallowed:
            return False
            
        return True
