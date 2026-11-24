"""
One-time setup script that can be called via API endpoint.
Creates proper Purchase records which automatically generate AssetUnits.
"""
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from apps.users.models import User
from apps.assets.models import AssetCategory, Asset
from apps.purchases.models import Supplier, Purchase, Payment
from apps.company_settings.models import CompanySettings


def populate_database():
    """Main function to populate all sample data via proper Purchase flow"""
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

        # Create asset TEMPLATES (catalog items - not counted in dashboard)
        asset_templates = create_asset_templates(categories)
        results['created']['asset_templates'] = len(asset_templates)

        # Create suppliers
        suppliers = create_suppliers()
        results['created']['suppliers'] = len(suppliers)

        # Create PURCHASES (which create AssetUnits - these ARE counted in dashboard)
        purchases = create_purchases(asset_templates, suppliers)
        results['created']['purchases'] = len(purchases)
        
        # Count actual purchased units created
        from apps.assets.models import AssetUnit
        total_units = AssetUnit.objects.count()
        results['created']['purchased_units'] = total_units

        # Create some assignments
        assignments = create_assignments(employees)
        results['created']['assignments'] = len(assignments)

    except Exception as e:
        results['status'] = 'error'
        results['errors'].append(str(e))
        import traceback
        results['errors'].append(traceback.format_exc())

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


def create_asset_templates(categories):
    """
    Create TEMPLATE/CATALOG items (these are NOT purchased units yet).
    These won't show in dashboard until they're purchased.
    """
    templates_data = [
        {
            'name': 'MacBook Pro 16" M3',
            'category': categories[0],  # Laptops
            'brand': 'Apple',
            'model': 'MacBook Pro 16-inch 2024',
            'color': 'Space Gray',
            'purchase_date': date.today(),  # Required field
            'purchase_cost': Decimal('450000.00'),
            'current_value': Decimal('450000.00'),
            'salvage_value': Decimal('100000.00'),
            'useful_life_years': 4,
            'warranty_start_date': None,
            'warranty_end_date': None,
            'tech_specs': {
                'processor': 'Apple M3 Max',
                'ram': '32GB',
                'storage': '1TB SSD',
            },
        },
        {
            'name': 'Dell XPS 15',
            'category': categories[0],
            'brand': 'Dell',
            'model': 'XPS 15 9530',
            'color': 'Platinum Silver',
            'purchase_date': date.today(),
            'purchase_cost': Decimal('280000.00'),
            'current_value': Decimal('280000.00'),
            'salvage_value': Decimal('60000.00'),
            'useful_life_years': 4,
            'tech_specs': {
                'processor': 'Intel Core i7',
                'ram': '16GB',
                'storage': '512GB SSD',
            },
        },
        {
            'name': 'HP EliteDesk 800',
            'category': categories[1],  # Desktops
            'brand': 'HP',
            'model': 'EliteDesk 800 G9',
            'color': 'Black',
            'purchase_date': date.today(),
            'purchase_cost': Decimal('180000.00'),
            'current_value': Decimal('180000.00'),
            'salvage_value': Decimal('40000.00'),
            'useful_life_years': 5,
            'tech_specs': {
                'processor': 'Intel Core i7',
                'ram': '32GB',
                'storage': '1TB SSD',
            },
        },
        {
            'name': 'Dell UltraSharp 27"',
            'category': categories[2],  # Monitors
            'brand': 'Dell',
            'model': 'U2723DE',
            'color': 'Black',
            'purchase_date': date.today(),
            'purchase_cost': Decimal('85000.00'),
            'current_value': Decimal('85000.00'),
            'salvage_value': Decimal('15000.00'),
            'useful_life_years': 5,
            'tech_specs': {
                'resolution': '4K UHD',
                'panel': 'IPS',
            },
        },
        {
            'name': 'iPhone 15 Pro',
            'category': categories[3],  # Phones
            'brand': 'Apple',
            'model': 'iPhone 15 Pro',
            'color': 'Natural Titanium',
            'purchase_date': date.today(),
            'purchase_cost': Decimal('420000.00'),
            'current_value': Decimal('420000.00'),
            'salvage_value': Decimal('100000.00'),
            'useful_life_years': 3,
            'tech_specs': {
                'storage': '256GB',
                'chip': 'A17 Pro',
            },
        },
        {
            'name': 'Ergonomic Office Chair',
            'category': categories[5],  # Furniture
            'brand': 'Herman Miller',
            'model': 'Aeron',
            'color': 'Black',
            'purchase_date': date.today(),
            'purchase_cost': Decimal('180000.00'),
            'current_value': Decimal('180000.00'),
            'salvage_value': Decimal('30000.00'),
            'useful_life_years': 10,
            'tech_specs': {
                'type': 'Ergonomic',
            },
        },
    ]

    created_templates = []
    for template_data in templates_data:
        asset, created = Asset.objects.get_or_create(
            name=template_data['name'],
            category=template_data['category'],
            brand=template_data['brand'],
            defaults=template_data
        )
        created_templates.append(asset)

    return created_templates


def create_suppliers():
    """Create sample suppliers"""
    suppliers_data = [
        {
            'name': 'Ahmed Khan',
            'company': 'TechVision Pakistan',
            'email': 'sales@techvision.pk',
            'phone': '+92-300-9876543',
            'address': 'Saddar, Karachi',
        },
        {
            'name': 'Sara Ali',
            'company': 'Digital Solutions Ltd',
            'email': 'info@digitalsolutions.com.pk',
            'phone': '+92-301-8765432',
            'address': 'Gulberg, Lahore',
        },
        {
            'name': 'Office Furniture Co',
            'company': 'Premium Office Supplies',
            'email': 'orders@premiumoffice.pk',
            'phone': '+92-21-5555555',
            'address': 'DHA Phase 2, Karachi',
        },
    ]

    suppliers = []
    for supp_data in suppliers_data:
        supplier, created = Supplier.objects.get_or_create(
            company=supp_data['company'],
            defaults=supp_data
        )
        suppliers.append(supplier)

    return suppliers


def create_purchases(asset_templates, suppliers):
    """
    Create Purchase records which will automatically generate AssetUnits.
    THIS is what shows up in the dashboard as 'Total Assets'!
    """
    from apps.assets.services import AssetService
    
    purchases_data = [
        {
            'asset': asset_templates[0],  # MacBook Pro
            'supplier': suppliers[0],
            'quantity': 5,
            'purchase_date': date.today() - timedelta(days=180),
            'warranty_days': 365,
        },
        {
            'asset': asset_templates[1],  # Dell XPS
            'supplier': suppliers[0],
            'quantity': 3,
            'purchase_date': date.today() - timedelta(days=120),
            'warranty_days': 365,
        },
        {
            'asset': asset_templates[2],  # HP EliteDesk
            'supplier': suppliers[1],
            'quantity': 4,
            'purchase_date': date.today() - timedelta(days=90),
            'warranty_days': 1095,  # 3 years
        },
        {
            'asset': asset_templates[3],  # Dell Monitor
            'supplier': suppliers[0],
            'quantity': 8,
            'purchase_date': date.today() - timedelta(days=200),
            'warranty_days': 1095,
        },
        {
            'asset': asset_templates[4],  # iPhone
            'supplier': suppliers[1],
            'quantity': 4,
            'purchase_date': date.today() - timedelta(days=60),
            'warranty_days': 365,
        },
        {
            'asset': asset_templates[5],  # Office Chair
            'supplier': suppliers[2],
            'quantity': 10,
            'purchase_date': date.today() - timedelta(days=300),
            'warranty_days': 3650,  # 10 years
        },
    ]

    created_purchases = []
    for purch_data in purchases_data:
        asset = purch_data['asset']
        supplier = purch_data['supplier']
        quantity = purch_data['quantity']
        purchase_date = purch_data['purchase_date']
        warranty_days = purch_data.get('warranty_days', 0)

        # Update asset warranty dates based on purchase
        if warranty_days > 0:
            asset.warranty_start_date = purchase_date
            asset.warranty_end_date = purchase_date + timedelta(days=warranty_days)
            asset.purchase_date = purchase_date
            asset.save()

        # Check if purchase already exists
        existing = Purchase.objects.filter(
            asset=asset,
            supplier=supplier,
            purchase_date=purchase_date,
            quantity=quantity
        ).first()
        
        if existing:
            created_purchases.append(existing)
            continue

        # Create purchase
        purchase = Purchase.objects.create(
            asset=asset,
            supplier=supplier,
            quantity=quantity,
            purchase_price=asset.purchase_cost,
            purchase_date=purchase_date,
            status=Purchase.Status.COMPLETED,
            notes=f'Sample data purchase - {quantity} units',
        )

        # THIS is the magic: AssetService.create_units creates the AssetUnit records
        AssetService.create_units(
            asset=asset,
            quantity=quantity,
            purchase=purchase
        )

        # Create full payment
        Payment.objects.create(
            purchase=purchase,
            amount=purchase.total_amount,
            payment_date=purchase_date,
            method=Payment.Method.BANK_TRANSFER,
            reference=f'TXN-{purchase.purchase_number}',
            notes='Full payment - sample data',
        )

        created_purchases.append(purchase)

    return created_purchases


def create_assignments(employees):
    """Create sample assignments using PURCHASED units"""
    from apps.assets.models import AssetUnit, AssetAssignmentHistory
    
    # Get some available units (that were created via purchases)
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
            
            # Update unit status
            unit.status = AssetUnit.Status.ASSIGNED
            unit.assigned_to = employee
            unit.save()
            
            assignments.append(assignment)

    return assignments
