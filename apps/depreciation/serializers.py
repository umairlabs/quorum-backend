from decimal import Decimal
from rest_framework import serializers


class DepreciationScheduleRowSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    yearLabel = serializers.CharField()
    openingBookValue = serializers.DecimalField(max_digits=12, decimal_places=2)
    depreciationExpense = serializers.DecimalField(max_digits=12, decimal_places=2)
    accumulatedDepreciation = serializers.DecimalField(max_digits=12, decimal_places=2)
    closingBookValue = serializers.DecimalField(max_digits=12, decimal_places=2)


class AssetDepreciationSerializer(serializers.Serializer):
    assetId = serializers.CharField()
    assetName = serializers.CharField()
    category = serializers.CharField(required=False, allow_blank=True)
    brand = serializers.CharField(required=False, allow_blank=True)
    model = serializers.CharField(required=False, allow_blank=True)
    serialNumber = serializers.CharField(required=False, allow_blank=True)
    purchasePrice = serializers.DecimalField(max_digits=12, decimal_places=2)
    purchaseDate = serializers.DateField(allow_null=True, required=False)
    salvageValue = serializers.DecimalField(max_digits=12, decimal_places=2)
    usefulLife = serializers.IntegerField()
    usefulLifeYears = serializers.IntegerField()
    depreciationMethod = serializers.CharField()
    annualDepreciation = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthlyDepreciation = serializers.DecimalField(max_digits=12, decimal_places=2)
    accumulatedDepreciation = serializers.DecimalField(max_digits=12, decimal_places=2)
    currentBookValue = serializers.DecimalField(max_digits=12, decimal_places=2)
    depreciationStatus = serializers.CharField()
    depreciationSchedule = DepreciationScheduleRowSerializer(many=True)


class UpdateDepreciationSerializer(serializers.Serializer):
    salvageValue = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.00'), required=True)
    usefulLifeYears = serializers.IntegerField(min_value=1, max_value=50, required=True)
    depreciationMethod = serializers.CharField(default='STRAIGHT_LINE', required=False)

    def validate_salvageValue(self, value):
        if value < Decimal('0.00'):
            raise serializers.ValidationError("Salvage value must be greater than or equal to 0.")
        return value

    def validate_usefulLifeYears(self, value):
        if value <= 0:
            raise serializers.ValidationError("Useful life must be greater than 0.")
        return value
