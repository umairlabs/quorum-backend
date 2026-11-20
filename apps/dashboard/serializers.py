from rest_framework import serializers

class SummaryStatsSerializer(serializers.Serializer):
    totalAssets = serializers.IntegerField()
    totalAssetModels = serializers.IntegerField(required=False, default=0)
    assignedCount = serializers.IntegerField()
    activeAssignments = serializers.IntegerField(required=False, default=0)
    availableCount = serializers.IntegerField()
    maintenanceCount = serializers.IntegerField()
    maintenanceTickets = serializers.IntegerField(required=False, default=0)
    scrappedCount = serializers.IntegerField()
    retiredCount = serializers.IntegerField()
    totalPurchaseValue = serializers.FloatField()
    totalCurrentValue = serializers.FloatField()
    totalSpent = serializers.FloatField(required=False, default=0.0)
    totalPurchasesValue = serializers.FloatField(required=False, default=0.0)
    totalOutstanding = serializers.FloatField(required=False, default=0.0)

class StatusDistributionItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    count = serializers.IntegerField()
    percentage = serializers.FloatField()
    color = serializers.CharField()
    hexColor = serializers.CharField()

class ChartSeriesItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    values = serializers.ListField(child=serializers.FloatField())
    strokeColor = serializers.CharField()
    legendColor = serializers.CharField()

class ValueOverviewSerializer(serializers.Serializer):
    xLabels = serializers.ListField(child=serializers.CharField())
    series = ChartSeriesItemSerializer(many=True)

class MaintenanceTicketSerializer(serializers.Serializer):
    id = serializers.CharField()
    rawId = serializers.CharField(required=False)
    assetIcon = serializers.CharField()
    assetName = serializers.CharField()
    problem = serializers.CharField()
    technician = serializers.CharField()
    priority = serializers.CharField(required=False)
    status = serializers.CharField()
    date = serializers.CharField()

class ActivityItemSerializer(serializers.Serializer):
    dotColor = serializers.CharField()
    type = serializers.CharField(required=False)
    assetName = serializers.CharField(required=False)
    description = serializers.CharField()
    highlighted = serializers.ListField(child=serializers.CharField(), required=False)
    time = serializers.CharField()

class DashboardSummarySerializer(serializers.Serializer):
    summary = SummaryStatsSerializer()
    statusDistribution = StatusDistributionItemSerializer(many=True)
    valueOverview = ValueOverviewSerializer()
    recentMaintenanceTickets = MaintenanceTicketSerializer(many=True)
    recentActivity = ActivityItemSerializer(many=True)
