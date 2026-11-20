import secrets
import uuid
from rest_framework import serializers
from .models import User
from apps.authentication.validators import validate_password_complexity, normalize_role


class UserSerializer(serializers.ModelSerializer):
    displayId = serializers.CharField(source='display_id', read_only=True)
    firstName = serializers.CharField(source='first_name', read_only=True)
    lastName = serializers.CharField(source='last_name', read_only=True)
    fullName = serializers.SerializerMethodField()
    employeeId = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active')
    avatarInitials = serializers.SerializerMethodField()
    phoneNumber = serializers.CharField(source='phone_number', read_only=True)
    joiningDate = serializers.DateField(source='joining_date', read_only=True, allow_null=True)
    jobTitle = serializers.CharField(source='job_title', read_only=True)
    emergencyContact = serializers.CharField(source='emergency_contact', read_only=True)
    profileImage = serializers.CharField(source='profile_image', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    lastLogin = serializers.DateTimeField(source='last_login', read_only=True, allow_null=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'displayId', 'employeeId', 'email', 'firstName', 'lastName', 'fullName', 'role',
            'isActive', 'department', 'jobTitle', 'location', 'avatarInitials',
            'phoneNumber', 'joiningDate', 'address', 'emergencyContact', 'notes', 'profileImage',
            'createdAt', 'lastLogin', 'permissions',
        ]

    def get_employeeId(self, obj) -> str:
        if obj.employee_id:
            return obj.employee_id
        if not obj.id:
            return ''
        return f"EMP-{str(obj.id).split('-')[0].upper()}"

    def get_fullName(self, obj) -> str:
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        if full_name:
            return full_name
        if obj.email and not obj.email.endswith('@company.local'):
            return obj.email
        return 'Employee'

    def get_permissions(self, obj):
        if hasattr(obj, 'get_effective_permissions'):
            return obj.get_effective_permissions()
        return []

    def get_avatarInitials(self, obj) -> str:
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        if not full_name:
            if obj.email and not obj.email.endswith('@company.local'):
                return obj.email[:2].upper()
            return 'EM'
        parts = full_name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[-1][0]}".upper()
        return full_name[:2].upper()


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    phoneNumber = serializers.CharField(source='phone_number', required=False, allow_blank=True)
    joiningDate = serializers.DateField(source='joining_date', required=False, allow_null=True)
    jobTitle = serializers.CharField(source='job_title', required=False, allow_blank=True)
    emergencyContact = serializers.CharField(source='emergency_contact', required=False, allow_blank=True)
    profileImage = serializers.CharField(source='profile_image', required=False, allow_blank=True)
    employeeId = serializers.CharField(source='employee_id', required=False, allow_blank=True)
    role = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id', 'employeeId', 'employee_id', 'email', 'first_name', 'last_name', 'role', 'department',
            'jobTitle', 'location', 'phoneNumber', 'joiningDate', 'address', 'emergencyContact',
            'notes', 'profileImage', 'password',
        ]

    def validate_employeeId(self, value):
        if value:
            val = value.strip().upper()
            if User.objects.filter(employee_id=val).exists():
                raise serializers.ValidationError('Employee ID already exists.')
            return val
        return value

    def validate_email(self, value):
        if value:
            val = value.strip().lower()
            if User.objects.filter(email=val).exists():
                raise serializers.ValidationError('A user with this email already exists.')
            return val
        return ''

    def validate_password(self, value):
        if value:
            validate_password_complexity(value)
        return value

    def validate_role(self, value):
        if not value:
            return User.Role.EMPLOYEE
        return normalize_role(value)

    def create(self, validated_data):
        from .services import generate_next_employee_id
        password = validated_data.pop('password', None) or secrets.token_urlsafe(12)

        email = validated_data.get('email', '')
        if not email:
            email = 'emp-' + str(uuid.uuid4().hex[:8]) + '@company.local'

        emp_id = validated_data.get('employee_id') or generate_next_employee_id()

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role') or User.Role.EMPLOYEE,
            department=validated_data.get('department', ''),
            job_title=validated_data.get('job_title', ''),
            location=validated_data.get('location', ''),
            phone_number=validated_data.get('phone_number', ''),
            joining_date=validated_data.get('joining_date'),
            address=validated_data.get('address', ''),
            emergency_contact=validated_data.get('emergency_contact', ''),
            notes=validated_data.get('notes', ''),
            profile_image=validated_data.get('profile_image', ''),
            must_change_password=False,
            is_active=True,
        )
        user.employee_id = emp_id
        user.save(update_fields=['employee_id'])
        return user


class UpdateUserSerializer(serializers.ModelSerializer):
    phoneNumber = serializers.CharField(source='phone_number', required=False, allow_blank=True)
    joiningDate = serializers.DateField(source='joining_date', required=False, allow_null=True)
    jobTitle = serializers.CharField(source='job_title', required=False, allow_blank=True)
    emergencyContact = serializers.CharField(source='emergency_contact', required=False, allow_blank=True)
    profileImage = serializers.CharField(source='profile_image', required=False, allow_blank=True)
    employeeId = serializers.CharField(source='employee_id', required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'role', 'is_active',
            'department', 'jobTitle', 'location', 'phoneNumber', 'joiningDate',
            'address', 'emergencyContact', 'notes', 'profileImage', 'employeeId',
        ]
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
            'first_name': {'required': False},
            'last_name': {'required': False},
            'role': {'required': False},
            'is_active': {'required': False},
        }

    def validate_employeeId(self, value):
        if value:
            val = value.strip().upper()
            qs = User.objects.filter(employee_id=val)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('Employee ID already exists.')
            return val
        return value

    def validate_email(self, value):
        if value:
            val = value.strip().lower()
            qs = User.objects.filter(email=val)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError('A user with this email already exists.')
            return val
        return value


class UserPermissionsSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(source='id', read_only=True)
    role = serializers.CharField(read_only=True)
    permissions = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )

    def validate_permissions(self, value):
        from .models import ALL_SYSTEM_PERMISSIONS
        invalid = [code for code in value if code not in ALL_SYSTEM_PERMISSIONS]
        if invalid:
            raise serializers.ValidationError(f"Invalid permission codes: {', '.join(invalid)}")
        return value
