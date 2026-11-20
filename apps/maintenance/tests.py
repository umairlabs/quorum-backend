from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from apps.assets.models import Asset, AssetUnit, AssetCategory
from apps.maintenance.models import MaintenanceRequest
from apps.users.models import User

class MaintenanceUnitWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='admin@test.com',
            password='Password123!',
            role=User.Role.SYSTEM_ADMIN
        )
        self.client.force_authenticate(user=self.user)

        self.category = AssetCategory.objects.create(name='Laptops')
        self.asset = Asset.objects.create(
            name='Dell Latitude 7420',
            category=self.category,
            brand='Dell',
            model='Latitude 7420',
            purchase_date='2026-01-01',
            purchase_cost=1200.00,
            current_value=1200.00
        )

        self.unit1 = AssetUnit.objects.create(
            asset=self.asset,
            unit_number=1,
            serial_number='SN-DELL-001',
            status=AssetUnit.Status.AVAILABLE
        )
        self.unit2 = AssetUnit.objects.create(
            asset=self.asset,
            unit_number=2,
            serial_number='SN-DELL-002',
            status=AssetUnit.Status.AVAILABLE
        )

    def test_create_maintenance_request_updates_specific_unit_status(self):
        payload = {
            'assetId': str(self.asset.id),
            'unitId': str(self.unit1.id),
            'componentOrIssueType': 'Screen Flickering',
            'issueDescription': 'The laptop display flickers constantly when opened.',
            'maintenanceType': 'CORRECTIVE',
            'priority': 'HIGH'
        }
        res = self.client.post('/api/maintenance/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.unit1.refresh_from_db()
        self.unit2.refresh_from_db()

        self.assertEqual(self.unit1.status, AssetUnit.Status.MAINTENANCE)
        self.assertEqual(self.unit2.status, AssetUnit.Status.AVAILABLE)

        req_id = res.data['id']
        req = MaintenanceRequest.objects.get(pk=req_id)
        self.assertEqual(req.asset_unit, self.unit1)

    def test_resolve_maintenance_request_resets_unit_to_available(self):
        req = MaintenanceRequest.objects.create(
            asset=self.asset,
            asset_unit=self.unit1,
            component_or_issue_type='Fan Noise',
            issue_description='Fan spins at maximum speed constantly.',
            maintenance_type='CORRECTIVE',
            priority='MEDIUM',
            status=MaintenanceRequest.Status.IN_PROGRESS
        )
        self.unit1.status = AssetUnit.Status.MAINTENANCE
        self.unit1.save()

        payload = {
            'status': 'RESOLVED',
            'workDone': 'Cleaned dust and replaced heat sink thermal paste.',
            'technicianNotes': 'Tested load temperature, stable at 45C.'
        }
        res = self.client.patch(f'/api/maintenance/{req.id}/work-update/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.unit1.refresh_from_db()
        self.unit2.refresh_from_db()

        self.assertEqual(self.unit1.status, AssetUnit.Status.AVAILABLE)
        self.assertEqual(self.unit2.status, AssetUnit.Status.AVAILABLE)

    def test_unrepairable_maintenance_request_scraps_specific_unit(self):
        req = MaintenanceRequest.objects.create(
            asset=self.asset,
            asset_unit=self.unit1,
            component_or_issue_type='Motherboard Burned',
            issue_description='Severe liquid damage causing total component short.',
            maintenance_type='CORRECTIVE',
            priority='CRITICAL',
            status=MaintenanceRequest.Status.IN_PROGRESS
        )
        self.unit1.status = AssetUnit.Status.MAINTENANCE
        self.unit1.save()

        payload = {
            'status': 'NOT_REPAIRABLE',
            'workDone': 'Inspected motherboard, irreparable corrosion.',
            'technicianNotes': 'Recommended for scrapping.'
        }
        res = self.client.patch(f'/api/maintenance/{req.id}/work-update/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.unit1.refresh_from_db()
        self.unit2.refresh_from_db()

        self.assertEqual(self.unit1.status, AssetUnit.Status.SCRAPPED)
        self.assertEqual(self.unit2.status, AssetUnit.Status.AVAILABLE)
