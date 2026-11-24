"""
Management command to populate the database with sample asset data.
Usage: python manage.py populate_sample_data
"""
from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User
from apps.assets.models import AssetCategory, Asset, AssetUnit, AssetAssignmentHistory
from apps.company_settings.models import CompanySettings


class Command(BaseCommand):
    help = 'Populates the database with sample asset data for testing and demo purposes'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to populate sample data...'))

        # Create company settings if not exists
        self.create_company_settings()

        # Create sample users (employees)
        employees = self.create_sample_employees()
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(employees)} sample employees'))

        # Create asset categories
        categories = self.create_asset_categories()
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(categories)} asset categories'))

        # Create assets with units
        assets = self.create_sample_assets(categories)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(assets)} assets with units'))

        # Create some assignments
        assignments = self.create_sample_assignments(employees)
        self.stdout.write(self.style.SUCCESS(f'✓ Created {len(assignments)} asset assignments'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Sample data populated successfully!'))
        self.stdout.write(self.style.SUCCESS('\nYou can now:'))
        self.stdout.write(self.style.SUCCESS('- View assets in the Assets module'))
        self.stdout.write(self.style.SUCCESS('- Check assignments in the Assignments module'))
        self.stdout.write(self.style.SUCCESS('- Explore employee data in the Employees section'))

    def create_company_settings(self):
        """Create or update company settings"""
        settings, created = CompanySettings.objects.get_or_create(
            id=1,
            defaults={
                'company_name': 'Quorum Technologies',
                'currency': 'PKR',
                'date_format': 'YYYY-MM-DD',
                'time_zone': 'Asia/Karachi',
                'official_email': 'info@quorum.test',
                'company_phone': '+92-21-1234567',
                'company_address': 'Karachi, Pakistan',
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created company settings'))
        return settings

    def create_sample_employees(self):
        """Create sample employee users"""
        employees_data = [
            {
                'email': 'sarah.ahmed@quorum.test',
                'first_name': 'Sarah',
                'last_name': 'Ahmed',
                'role': User.Role.OPERATIONS_MANAGER,
                'department': 'IT',
                'job_title': 'IT Manager',
                'phone_number': '+92-300-1234567',
                'location': 'Karachi HQ',
            },
            {
                'email': 'ali.hassan@quorum.test',
                'first_name': 'Ali',
                'last_name': 'Hassan',
                'role': User.Role.EMPLOYEE,
                'department': 'Engineering',
                'job_title': 'Senior Developer',
                'phone_number': '+92-301-2345678',
                'location': 'Karachi HQ',
            },
            {
                'email': 'fatima.malik@quorum.test',
                'first_name': 'Fatima',
                'last_name': 'Malik',
                'role': User.Role.EMPLOYEE,
                'department': 'Design',
                'job_title': 'UI/UX Designer',
                'phone_number': '+92-302-3456789',
                'location': 'Karachi HQ',
            },
            {
                'email': 'usman.khan@quorum.test',
                'first_name': 'Usman',
                'last_name': 'Khan',
                'role': User.Role.EMPLOYEE,
                'department': 'Marketing',
                'job_title': 'Marketing Manager',
                'phone_number': '+92-303-4567890',
                'location': 'Lahore Office',
            },
            {
                'email': 'ayesha.iqbal@quorum.test',
                'first_name': 'Ayesha',
                'last_name': 'Iqbal',
                'role': User.Role.EMPLOYEE,
                'department': 'HR',
                'job_title': 'HR Specialist',
                'phone_number': '+92-304-5678901',
                'location': 'Karachi HQ',
            },
            {
                'email': 'ahmed.raza@quorum.test',
                'first_name': 'Ahmed',
                'last_name': 'Raza',
                'role': User.Role.EMPLOYEE,
                'department': 'Engineering',
                'job_title': 'Junior Developer',
                'phone_number': '+92-305-6789012',
                'location': 'Karachi HQ',
            },
            {
                'email': 'zainab.ali@quorum.test',
                'first_name': 'Zainab',
                'last_name': 'Ali',
                'role': User.Role.EMPLOYEE,
                'department': 'Finance',
                'job_title': 'Accountant',
                'phone_number': '+92-306-7890123',
                'location': 'Lahore Office',
            },
        ]

        employees = []
        for emp_data in employees_data:
            user, created = User.objects.get_or_create(
                email=emp_data['email'],
                defaults={
                    **emp_data,
                    'joining_date': date.today() - timedelta(days=365),
                    'must_change_password': False,
                }
            )
            if created:
                user.set_password('Password123')
                user.save()
            employees.append(user)

        return employees

    def create_asset_categories(self):
        """Create asset categories"""
        categories_data = [
            {'name': 'Laptops', 'description': 'Portable computing devices for employees'},
            {'name': 'Desktop Computers', 'description': 'Fixed workstation computers'},
            {'name': 'Monitors', 'description': 'Display screens and monitors'},
            {'name': 'Mobile Phones', 'description': 'Smartphones and mobile devices'},
            {'name': 'Printers', 'description': 'Printing and scanning equipment'},
            {'name': 'Office Furniture', 'description': 'Desks, chairs, and office furniture'},
            {'name': 'Network Equipment', 'description': 'Routers, switches, and networking gear'},
            {'name': 'Servers', 'description': 'Server hardware and infrastructure'},
        ]

        categories = []
        for cat_data in categories_data:
            category, created = AssetCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults=cat_data
            )
            categories.append(category)

        return categories

    def create_sample_assets(self, categories):
        """Create sample assets with units"""
        assets_data = [
            # Laptops
            {
                'name': 'MacBook Pro 16" M3',
                'category': categories[0],  # Laptops
                'brand': 'Apple',
                'model': 'MacBook Pro 16-inch 2024',
                'color': 'Space Gray',
                'purchase_date': date.today() - timedelta(days=180),
                'purchase_cost': Decimal('450000.00'),
                'current_value': Decimal('420000.00'),
                'salvage_value': Decimal('100000.00'),
                'useful_life_years': 4,
                'warranty_start_date': date.today() - timedelta(days=180),
                'warranty_end_date': date.today() + timedelta(days=185),
                'tech_specs': {
                    'processor': 'Apple M3 Max',
                    'ram': '32GB',
                    'storage': '1TB SSD',
                    'display': '16-inch Liquid Retina XDR'
                },
                'quantity': 5,
            },
            {
                'name': 'Dell XPS 15',
                'category': categories[0],
                'brand': 'Dell',
                'model': 'XPS 15 9530',
                'color': 'Platinum Silver',
                'purchase_date': date.today() - timedelta(days=120),
                'purchase_cost': Decimal('280000.00'),
                'current_value': Decimal('265000.00'),
                'salvage_value': Decimal('60000.00'),
                'useful_life_years': 4,
                'warranty_start_date': date.today() - timedelta(days=120),
                'warranty_end_date': date.today() + timedelta(days=245),
                'tech_specs': {
                    'processor': 'Intel Core i7-13700H',
                    'ram': '16GB',
                    'storage': '512GB SSD',
                    'display': '15.6" FHD+'
                },
                'quantity': 3,
            },
            # Desktop Computers
            {
                'name': 'HP EliteDesk 800 G9',
                'category': categories[1],  # Desktop Computers
                'brand': 'HP',
                'model': 'EliteDesk 800 G9 Tower',
                'color': 'Black',
                'purchase_date': date.today() - timedelta(days=90),
                'purchase_cost': Decimal('180000.00'),
                'current_value': Decimal('172000.00'),
                'salvage_value': Decimal('40000.00'),
                'useful_life_years': 5,
                'warranty_start_date': date.today() - timedelta(days=90),
                'warranty_end_date': date.today() + timedelta(days=1005),
                'tech_specs': {
                    'processor': 'Intel Core i7-12700',
                    'ram': '32GB',
                    'storage': '1TB SSD',
                    'graphics': 'Integrated'
                },
                'quantity': 4,
            },
            # Monitors
            {
                'name': 'Dell UltraSharp 27" 4K',
                'category': categories[2],  # Monitors
                'brand': 'Dell',
                'model': 'U2723DE',
                'color': 'Black',
                'purchase_date': date.today() - timedelta(days=200),
                'purchase_cost': Decimal('85000.00'),
                'current_value': Decimal('78000.00'),
                'salvage_value': Decimal('15000.00'),
                'useful_life_years': 5,
                'warranty_start_date': date.today() - timedelta(days=200),
                'warranty_end_date': date.today() + timedelta(days=895),
                'tech_specs': {
                    'resolution': '3840 x 2160 (4K UHD)',
                    'panel_type': 'IPS',
                    'refresh_rate': '60Hz',
                    'ports': 'HDMI, DisplayPort, USB-C'
                },
                'quantity': 8,
            },
            # Mobile Phones
            {
                'name': 'iPhone 15 Pro',
                'category': categories[3],  # Mobile Phones
                'brand': 'Apple',
                'model': 'iPhone 15 Pro',
                'color': 'Natural Titanium',
                'purchase_date': date.today() - timedelta(days=60),
                'purchase_cost': Decimal('420000.00'),
                'current_value': Decimal('400000.00'),
                'salvage_value': Decimal('100000.00'),
                'useful_life_years': 3,
                'warranty_start_date': date.today() - timedelta(days=60),
                'warranty_end_date': date.today() + timedelta(days=305),
                'tech_specs': {
                    'storage': '256GB',
                    'display': '6.1" Super Retina XDR',
                    'camera': '48MP Main, 12MP Ultra Wide',
                    'chip': 'A17 Pro'
                },
                'quantity': 4,
            },
            # Printers
            {
                'name': 'HP LaserJet Pro MFP',
                'category': categories[4],  # Printers
                'brand': 'HP',
                'model': 'M428fdw',
                'color': 'White',
                'purchase_date': date.today() - timedelta(days=240),
                'purchase_cost': Decimal('95000.00'),
                'current_value': Decimal('85000.00'),
                'salvage_value': Decimal('15000.00'),
                'useful_life_years': 5,
                'warranty_start_date': date.today() - timedelta(days=240),
                'warranty_end_date': date.today() + timedelta(days=125),
                'tech_specs': {
                    'type': 'Multifunction Laser Printer',
                    'print_speed': '40 ppm',
                    'features': 'Print, Copy, Scan, Fax',
                    'connectivity': 'WiFi, Ethernet, USB'
                },
                'quantity': 2,
            },
            # Office Furniture
            {
                'name': 'Ergonomic Office Chair',
                'category': categories[5],  # Office Furniture
                'brand': 'Herman Miller',
                'model': 'Aeron',
                'color': 'Black',
                'purchase_date': date.today() - timedelta(days=300),
                'purchase_cost': Decimal('180000.00'),
                'current_value': Decimal('165000.00'),
                'salvage_value': Decimal('30000.00'),
                'useful_life_years': 10,
                'tech_specs': {
                    'type': 'Ergonomic Office Chair',
                    'features': 'Adjustable lumbar support, Mesh back',
                    'weight_capacity': '350 lbs',
                    'size': 'Size B (Medium)'
                },
                'quantity': 10,
            },
            {
                'name': 'Standing Desk',
                'category': categories[5],
                'brand': 'FlexiSpot',
                'model': 'E7 Pro Plus',
                'color': 'White',
                'purchase_date': date.today() - timedelta(days=270),
                'purchase_cost': Decimal('120000.00'),
                'current_value': Decimal('110000.00'),
                'salvage_value': Decimal('20000.00'),
                'useful_life_years': 10,
                'tech_specs': {
                    'type': 'Electric Standing Desk',
                    'height_range': '58cm - 123cm',
                    'weight_capacity': '125kg',
                    'desktop_size': '140cm x 70cm'
                },
                'quantity': 6,
            },
            # Network Equipment
            {
                'name': 'Cisco Catalyst Switch',
                'category': categories[6],  # Network Equipment
                'brand': 'Cisco',
                'model': 'Catalyst 9300-48P',
                'color': 'Gray',
                'purchase_date': date.today() - timedelta(days=360),
                'purchase_cost': Decimal('450000.00'),
                'current_value': Decimal('410000.00'),
                'salvage_value': Decimal('80000.00'),
                'useful_life_years': 7,
                'warranty_start_date': date.today() - timedelta(days=360),
                'warranty_end_date': date.today() + timedelta(days=1460),
                'tech_specs': {
                    'type': '48-Port Gigabit PoE+ Switch',
                    'ports': '48 x 1G, 4 x 10G SFP+',
                    'power_budget': '740W',
                    'stacking': 'Yes, up to 8 units'
                },
                'quantity': 2,
            },
        ]

        created_assets = []
        for asset_data in assets_data:
            quantity = asset_data.pop('quantity', 1)
            
            # Create the asset
            asset, created = Asset.objects.get_or_create(
                name=asset_data['name'],
                category=asset_data['category'],
                brand=asset_data['brand'],
                defaults=asset_data
            )
            
            if created:
                # Create units for this asset
                for i in range(1, quantity + 1):
                    AssetUnit.objects.create(
                        asset=asset,
                        unit_number=i,
                        status=AssetUnit.Status.AVAILABLE,
                        location='Karachi HQ' if i % 2 == 1 else 'Lahore Office',
                    )
                created_assets.append(asset)

        return created_assets

    def create_sample_assignments(self, employees):
        """Create sample asset assignments"""
        # Get some available units
        available_units = AssetUnit.objects.filter(status=AssetUnit.Status.AVAILABLE)[:5]
        
        assignments = []
        for i, unit in enumerate(available_units):
            if i < len(employees):
                employee = employees[i]
                
                # Create assignment
                assignment = AssetAssignmentHistory.objects.create(
                    unit=unit,
                    asset_name_snapshot=unit.asset.name,
                    unit_serial_snapshot=unit.serial_number,
                    user=employee,
                    employee_name=f"{employee.first_name} {employee.last_name}",
                    department=employee.department,
                    assigned_date=date.today() - timedelta(days=30 + i*10),
                    expected_return_date=None,
                    notes=f'Assigned for work purposes',
                    status=AssetAssignmentHistory.Status.ACTIVE,
                    receipt_status=AssetAssignmentHistory.ReceiptStatus.RECEIVED,
                    received_at=timezone.now() - timedelta(days=30 + i*10),
                    received_condition='Good Condition',
                )
                
                # Update unit status
                unit.status = AssetUnit.Status.ASSIGNED
                unit.assigned_to = employee
                unit.save()
                
                assignments.append(assignment)

        return assignments
