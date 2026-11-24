"""
One-time setup script that can be called via API endpoint
"""
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from apps.users.models import User
from apps.assets.models import AssetCategory, Asset, AssetUnit, AssetAssignmentHistory
from apps.company_settings.models import CompanySettings


def populate_database():
    """Main function to populate all sample data"""
    results = {
        'status': 'success',
        'created': {},
        'errors': []
    }

    try:
        # Create company settings
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
        results['created']['company_settings'] = created

        # Create employees
        employees = create_employees()
        results['created']['employees'] = len(employees)

        # Create categories
        categories = create_categories()
        results['created']['categories'] = len(categories)

        # Create assets
        assets = create_assets(categories)
        results['created']['assets'] = len(assets)

        # Create assignments
        assignments = create_assignments(employees)
        results['created']['assignments'] = len(assignments)

    except Exception as e:
        results['status'] = 'error'
        results['errors'].append(str(e))

    return results


def create_employees():
    """Create sample employees"""
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


def create_categories():
    """Create asset categories"""
    categories_data = [
        {'name': 'Laptops', 'description': 'Portable computing devices'},
        {'name': 'Desktop Computers', 'description': 'Fixed workstations'},
        {'name': 'Monitors', 'description': 'Display screens'},
        {'name': 'Mobile Phones', 'description': 'Smartphones'},
        {'name': 'Printers', 'description': 'Printing equipment'},
        {'name': 'Office Furniture', 'description': 'Desks and chairs'},
        {'name': 'Network Equipment', 'description': 'Routers and switches'},
    ]

    categories = []
    for cat_data in categories_data:
        category, created = AssetCategory.objects.get_or_create(
            name=cat_data['name'],
            defaults=cat_data
        )
        categories.append(category)

    return categories


def create_assets(categories):
    """Create sample assets"""
    assets_data = [
        {
            'name': 'MacBook Pro 16" M3',
            'category': categories[0],
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
                'processor': 'Intel Core i7',
                'ram': '16GB',
                'storage': '512GB SSD',
            },
            'quantity': 3,
        },
        {
            'name': 'HP EliteDesk 800',
            'category': categories[1],
            'brand': 'HP',
            'model': 'EliteDesk 800 G9',
            'color': 'Black',
            'purchase_date': date.today() - timedelta(days=90),
            'purchase_cost': Decimal('180000.00'),
            'current_value': Decimal('172000.00'),
            'salvage_value': Decimal('40000.00'),
            'useful_life_years': 5,
            'tech_specs': {
                'processor': 'Intel Core i7',
                'ram': '32GB',
                'storage': '1TB SSD',
            },
            'quantity': 4,
        },
        {
            'name': 'Dell UltraSharp 27"',
            'category': categories[2],
            'brand': 'Dell',
            'model': 'U2723DE',
            'color': 'Black',
            'purchase_date': date.today() - timedelta(days=200),
            'purchase_cost': Decimal('85000.00'),
            'current_value': Decimal('78000.00'),
            'salvage_value': Decimal('15000.00'),
            'useful_life_years': 5,
            'tech_specs': {
                'resolution': '4K UHD',
                'panel': 'IPS',
            },
            'quantity': 8,
        },
        {
            'name': 'iPhone 15 Pro',
            'category': categories[3],
            'brand': 'Apple',
            'model': 'iPhone 15 Pro',
            'color': 'Natural Titanium',
            'purchase_date': date.today() - timedelta(days=60),
            'purchase_cost': Decimal('420000.00'),
            'current_value': Decimal('400000.00'),
            'salvage_value': Decimal('100000.00'),
            'useful_life_years': 3,
            'tech_specs': {
                'storage': '256GB',
                'chip': 'A17 Pro',
            },
            'quantity': 4,
        },
        {
            'name': 'Ergonomic Office Chair',
            'category': categories[5],
            'brand': 'Herman Miller',
            'model': 'Aeron',
            'color': 'Black',
            'purchase_date': date.today() - timedelta(days=300),
            'purchase_cost': Decimal('180000.00'),
            'current_value': Decimal('165000.00'),
            'salvage_value': Decimal('30000.00'),
            'useful_life_years': 10,
            'tech_specs': {
                'type': 'Ergonomic',
            },
            'quantity': 10,
        },
    ]

    created_assets = []
    for asset_data in assets_data:
        quantity = asset_data.pop('quantity', 1)
        
        asset, created = Asset.objects.get_or_create(
            name=asset_data['name'],
            category=asset_data['category'],
            brand=asset_data['brand'],
            defaults=asset_data
        )
        
        if created:
            for i in range(1, quantity + 1):
                AssetUnit.objects.create(
                    asset=asset,
                    unit_number=i,
                    status=AssetUnit.Status.AVAILABLE,
                    location='Karachi HQ' if i % 2 == 1 else 'Lahore Office',
                )
            created_assets.append(asset)

    return created_assets


def create_assignments(employees):
    """Create sample assignments"""
    available_units = AssetUnit.objects.filter(status=AssetUnit.Status.AVAILABLE)[:5]
    
    assignments = []
    for i, unit in enumerate(available_units):
        if i < len(employees):
            employee = employees[i]
            
            assignment = AssetAssignmentHistory.objects.create(
                unit=unit,
                asset_name_snapshot=unit.asset.name,
                unit_serial_snapshot=unit.serial_number,
                user=employee,
                employee_name=f"{employee.first_name} {employee.last_name}",
                department=employee.department,
                assigned_date=date.today() - timedelta(days=30 + i*10),
                notes='Assigned for work purposes',
                status=AssetAssignmentHistory.Status.ACTIVE,
                receipt_status=AssetAssignmentHistory.ReceiptStatus.RECEIVED,
                received_at=timezone.now() - timedelta(days=30 + i*10),
                received_condition='Good Condition',
            )
            
            unit.status = AssetUnit.Status.ASSIGNED
            unit.assigned_to = employee
            unit.save()
            
            assignments.append(assignment)

    return assignments
