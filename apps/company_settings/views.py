import os
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.permissions import RBACPermission
from .models import CompanySettings
from .serializers import CompanySettingsSerializer, CompanySettingsUpdateSerializer, LogoUploadSerializer


def _get_or_create_settings():
    """Always return the singleton row (pk=1), creating it with defaults if absent."""
    obj, _ = CompanySettings.objects.get_or_create(pk=1)
    return obj


class CompanySettingsView(APIView):
    """
    GET  /api/company-settings/  → return current settings (or defaults)
    PUT  /api/company-settings/  → update settings — system_admin only
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        instance = _get_or_create_settings()
        serializer = CompanySettingsSerializer(instance)
        return Response(serializer.data)

    def put(self, request):
        self.required_roles = ['system_admin']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        instance = _get_or_create_settings()
        serializer = CompanySettingsUpdateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()

        # Track who last updated settings
        obj.updated_by = request.user
        obj.save(update_fields=['updated_by'])

        return Response(CompanySettingsSerializer(obj).data)


class CompanyLogoUploadView(APIView):
    """
    POST /api/company-settings/logo/  → upload logo image — system_admin only

    Accepts multipart/form-data with a `logo` field.
    Saves the file under MEDIA_ROOT/company/logos/ and stores the
    relative media URL in CompanySettings.logo_url.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        self.required_roles = ['system_admin']
        if not RBACPermission().has_permission(request, self):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = LogoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        logo_file = serializer.validated_data['logo']

        # Build a unique filename to avoid collisions
        ext = os.path.splitext(logo_file.name)[1].lower()
        filename = f"{uuid.uuid4().hex}{ext}"
        relative_path = os.path.join('company', 'logos', filename)
        save_path = os.path.join(settings.MEDIA_ROOT, 'company', 'logos', filename)

        # Ensure the target directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Write file to disk
        with open(save_path, 'wb+') as dest:
            for chunk in logo_file.chunks():
                dest.write(chunk)

        # Build the public URL
        logo_url = request.build_absolute_uri(
            settings.MEDIA_URL + relative_path.replace('\\', '/')
        )

        instance = _get_or_create_settings()
        instance.logo_url = logo_url
        instance.updated_by = request.user
        instance.save(update_fields=['logo_url', 'updated_by'])

        return Response(
            {"detail": "Logo uploaded successfully.", "logo_url": logo_url},
            status=status.HTTP_200_OK,
        )
