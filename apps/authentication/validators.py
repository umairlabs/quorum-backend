import re
from rest_framework.exceptions import ValidationError
from apps.users.models import User


ROLE_MAP = {
    'admin': User.Role.SYSTEM_ADMIN,
    'system_admin': User.Role.SYSTEM_ADMIN,
    'manager': User.Role.OPERATIONS_MANAGER,
    'operations_manager': User.Role.OPERATIONS_MANAGER,
    'technician': User.Role.EXTERNAL_TECHNICIAN,
    'external_technician': User.Role.EXTERNAL_TECHNICIAN,
    'employee': User.Role.EMPLOYEE,
}


def validate_password_complexity(password: str) -> str:
    """
    Validates password: must not be empty.
    """
    if not password or not str(password).strip():
        raise ValidationError("Password cannot be empty.")
    return password

def normalize_role(role_input: str) -> str:
    """
    Normalizes frontend role input string into canonical backend role enum.
    """
    if not role_input or not isinstance(role_input, str):
        raise ValidationError("Role is required.")

    clean_role = role_input.strip().lower()
    if clean_role not in ROLE_MAP:
        raise ValidationError("Invalid role specified.")

    return ROLE_MAP[clean_role]