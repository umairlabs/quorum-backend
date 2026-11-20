from django.test import TestCase
from apps.dashboard.services import DashboardService

class DashboardServiceTest(TestCase):
    def test_get_status_distribution_percentage_calculation(self):
        summary_stats = {
            'totalAssets': 65,
            'availableCount': 12,
            'assignedCount': 1,
            'maintenanceCount': 3,
            'scrappedCount': 0,
        }
        distribution = DashboardService.get_status_distribution(summary_stats)
        
        total_pct = sum(item['percentage'] for item in distribution)
        # 12/16 = 75.0%, 1/16 = 6.3%, 3/16 = 18.8%, 0/16 = 0.0% -> sum = 100.1% (within rounding threshold)
        self.assertAlmostEqual(total_pct, 100.0, delta=1.0)
        self.assertEqual(distribution[0]['percentage'], 75.0)
        self.assertEqual(distribution[1]['percentage'], 6.2)
        self.assertEqual(distribution[2]['percentage'], 18.8)
        self.assertEqual(distribution[3]['percentage'], 0.0)

    def test_unrepairable_counted_as_scrapped(self):
        from apps.assets.models import Asset, AssetCategory
        from apps.maintenance.models import MaintenanceRequest
        from datetime import date

        cat = AssetCategory.objects.create(name='Laptops')
        asset = Asset.objects.create(
            name='Test Laptop',
            category=cat,
            purchase_date=date.today(),
            purchase_cost=1000.0,
            current_value=800.0,
        )
        MaintenanceRequest.objects.create(
            request_id='MNT-TEST-001',
            asset=asset,
            component_or_issue_type='Screen',
            issue_description='Broken screen',
            maintenance_type=MaintenanceRequest.MaintenanceType.CORRECTIVE,
            priority=MaintenanceRequest.Priority.HIGH,
            status=MaintenanceRequest.Status.NOT_REPAIRABLE,
        )

        stats = DashboardService.get_summary_stats()
        self.assertGreaterEqual(stats['scrappedCount'], 1)

