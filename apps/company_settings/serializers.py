from rest_framework import serializers
from .models import CompanySettings


class CompanySettingsSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CompanySettings
        fields = [
            'id',
            'company_name',
            'logo_url',
            'official_email',
            'company_phone',
            'company_address',
            'currency',
            'time_zone',
            'date_format',
            'updated_by',
            'updated_by_name',
            'updated_at',
            'created_at',
        ]
        read_only_fields = ['id', 'updated_by', 'updated_by_name', 'updated_at', 'created_at']

    def get_updated_by_name(self, obj):
        if obj.updated_by:
            full_name = f"{obj.updated_by.first_name} {obj.updated_by.last_name}".strip()
            return full_name or obj.updated_by.email
        return None


class CompanySettingsUpdateSerializer(serializers.ModelSerializer):
    """Used for PUT — all fields optional (partial updates allowed)."""

    class Meta:
        model = CompanySettings
        fields = [
            'company_name',
            'official_email',
            'company_phone',
            'company_address',
            'currency',
            'time_zone',
            'date_format',
        ]

    def validate_currency(self, value):
        valid = [c[0] for c in CompanySettings.Currency.choices]
        if value not in valid:
            raise serializers.ValidationError(
                f"Invalid currency. Choose from: {', '.join(valid)}"
            )
        return value

    def validate_date_format(self, value):
        valid = [d[0] for d in CompanySettings.DateFormat.choices]
        if value not in valid:
            raise serializers.ValidationError(
                f"Invalid date format. Choose from: {', '.join(valid)}"
            )
        return value


class LogoUploadSerializer(serializers.Serializer):
    logo = serializers.ImageField()
