import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


ALL_SYSTEM_PERMISSIONS = [
    'asset.view', 'asset.create', 'asset.edit', 'asset.delete',
    'asset.assign', 'asset.transfer', 'asset.return', 'asset.retire', 'asset.history.view',
    'purchase.view', 'purchase.create', 'purchase.edit', 'purchase.delete',
    'assignment.view', 'assignment.create', 'assignment.transfer', 'assignment.return', 'assignment.history.view',
    'maintenance.view', 'maintenance.create', 'maintenance.manage', 'maintenance.status.update',
    'depreciation.view', 'depreciation.manage',
    'notification.view', 'notification.manage',
    'report.view',
]

DEFAULT_ROLE_PERMISSIONS = {
    'system_admin': ALL_SYSTEM_PERMISSIONS,
    'operations_manager': ALL_SYSTEM_PERMISSIONS,
    'external_technician': [
        'maintenance.view', 'maintenance.create', 'maintenance.manage', 'maintenance.status.update',
        'notification.view',
    ],
    'employee': [
        'asset.view',
        'maintenance.view',
        'notification.view',
    ],
}


class UserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier for authentication.
    """
    def create_user(self, email, password=None, role='external_technician', **extra_fields):
        if not email:
            raise ValueError('Users must have an email address.')
        email = self.normalize_email(email).lower()
        user = self.model(email=email, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.SYSTEM_ADMIN)
        extra_fields.setdefault('must_change_password', False)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SYSTEM_ADMIN = 'system_admin', 'System Admin'
        OPERATIONS_MANAGER = 'operations_manager', 'Operations Manager'
        EXTERNAL_TECHNICIAN = 'external_technician', 'External Technician'
        EMPLOYEE = 'employee', 'Employee'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=150, blank=True, default='')
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.EMPLOYEE)
    permissions = models.JSONField(default=list, blank=True)
    department = models.CharField(max_length=150, blank=True, default='')
    location = models.CharField(max_length=150, blank=True, default='')
    phone_number = models.CharField(max_length=30, blank=True, default='')
    joining_date = models.DateField(null=True, blank=True)
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    job_title = models.CharField(max_length=150, blank=True, default='')
    address = models.TextField(blank=True, default='')
    emergency_contact = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    profile_image = models.CharField(max_length=500, blank=True, default='')
    must_change_password = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    tokens_invalidated_at = models.DateTimeField(null=True, blank=True)
    tokens_valid_after = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    def get_effective_permissions(self):
        if self.role == self.Role.SYSTEM_ADMIN or self.is_superuser:
            return ALL_SYSTEM_PERMISSIONS
        if self.permissions is not None and isinstance(self.permissions, list) and len(self.permissions) > 0:
            return self.permissions
        role_key = (self.role or '').lower()
        return DEFAULT_ROLE_PERMISSIONS.get(role_key, [])

    def has_perm_code(self, code: str) -> bool:
        if self.role == self.Role.SYSTEM_ADMIN or self.is_superuser:
            return True
        eff = self.get_effective_permissions()
        return '*' in eff or code in eff

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email} ({self.display_id or self.role})"

    def save(self, *args, **kwargs):
        if not self.display_id:
            from apps.common.utils import generate_display_id
            self.display_id = generate_display_id(User, 'EMP')
        if not self.employee_id:
            self.employee_id = self.display_id
        super().save(*args, **kwargs)
