from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q

from apps.authentication.permissions import RBACPermission
from .models import User
from .serializers import UserSerializer, CreateUserSerializer, UpdateUserSerializer, UserPermissionsSerializer


class UserPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


class UserListCreateView(APIView):
    """
    GET  /api/users/                 -> list only EMPLOYEE role users (Employees page)
    GET  /api/users/?scope=admin     -> list only non-EMPLOYEE (admin) role users (Manage Users page)
    POST /api/users/                 -> create a new user/employee
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = request.query_params.get('scope')
        search = request.query_params.get('search', '').strip().lower()

        if scope == 'admin':
            self.required_roles = ['system_admin', 'operations_manager', 'super_admin', 'admin', 'manager']
            if not RBACPermission().has_permission(request, self):
                return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
            users = User.objects.exclude(role=User.Role.EMPLOYEE).order_by('-created_at')
        elif scope == 'all':
            users = User.objects.all().order_by('-created_at')
        elif scope in ['technician', 'technicians']:
            users = User.objects.filter(role=User.Role.EXTERNAL_TECHNICIAN).order_by('-created_at')
        elif scope in ['manager', 'managers']:
            users = User.objects.filter(role__in=[User.Role.OPERATIONS_MANAGER, User.Role.SYSTEM_ADMIN]).order_by('-created_at')
        else:
            users = User.objects.filter(role=User.Role.EMPLOYEE).order_by('-created_at')

        if search:
            users = users.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(department__icontains=search) |
                Q(job_title__icontains=search)
            )

        paginator = UserPagination()
        page = paginator.paginate_queryset(users, request)
        serializer = UserSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        self.required_roles = ['system_admin', 'operations_manager', 'super_admin', 'admin', 'manager']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    """
    GET    /api/users/<id>/   -> retrieve
    PATCH  /api/users/<id>/   -> update
    DELETE /api/users/<id>/   -> delete
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        return Response(UserSerializer(user).data)

    def patch(self, request, pk):
        self.required_roles = ['system_admin', 'operations_manager', 'super_admin', 'admin', 'manager']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, pk=pk)
        serializer = UpdateUserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(user).data)

    def delete(self, request, pk):
        self.required_roles = ['system_admin', 'operations_manager', 'super_admin', 'admin', 'manager']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, pk=pk)

        # Check active asset assignments
        try:
            from apps.assets.models import AssetAssignmentHistory
            user_name = f"{user.first_name} {user.last_name}".strip() or user.email
            has_active = AssetAssignmentHistory.objects.filter(
                Q(user=user) |
                (Q(employee_name__icontains=user_name) & Q(status=AssetAssignmentHistory.Status.ACTIVE))
            ).filter(status=AssetAssignmentHistory.Status.ACTIVE).exists()

            if has_active:
                return Response(
                    {"detail": "This employee currently has assigned assets. Return or reassign these assets before deleting the employee."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception:
            pass

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserStatusView(APIView):
    """PATCH /api/users/<id>/status/ -> toggle or set active/inactive."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        self.required_roles = ['system_admin', 'operations_manager', 'super_admin', 'admin', 'manager']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, pk=pk)
        if 'is_active' in request.data:
            user.is_active = bool(request.data['is_active'])
        else:
            user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return Response(UserSerializer(user).data)


class UserPermissionsView(APIView):
    """
    GET  /api/users/<uuid:pk>/permissions/ -> view user permissions
    PUT  /api/users/<uuid:pk>/permissions/ -> update user permissions
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        return Response({
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role,
            "permissions": user.get_effective_permissions()
        })

    def put(self, request, pk):
        self.required_roles = ['system_admin', 'super_admin', 'admin']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        user = get_object_or_404(User, pk=pk)

        if user.role == User.Role.SYSTEM_ADMIN or user.is_superuser:
            return Response(
                {"detail": "System Administrator permissions are managed by system role and cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserPermissionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_perms = user.get_effective_permissions()
        new_perms = serializer.validated_data['permissions']

        user.permissions = new_perms
        user.save(update_fields=['permissions'])

        try:
            from apps.audit.services import AuditLogService
            AuditLogService.log_action(
                action='USER_PERMISSIONS_UPDATED',
                module='USERS',
                description=f"Updated permissions for user {user.email} ({user.role})",
                user=request.user,
                old_value={"permissions": old_perms},
                new_value={"permissions": new_perms},
                request=request
            )
        except Exception as e:
            print("Audit log error:", e)

        return Response({
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role,
            "permissions": user.get_effective_permissions()
        })
