from apps.authentication.permissions import RBACPermission

# Re-exported here so views.py can do `from .permissions import RBACPermission`
# and stay consistent with the authentication app's pattern.
__all__ = ['RBACPermission']