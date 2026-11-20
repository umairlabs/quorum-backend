import os
import sys
import django

# Setup django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, r'C:\Users\HORIZON laptop\Desktop\api')
django.setup()

from apps.assets.models import Asset, AssetUnit, AssetAssignmentHistory, AssetRequest, AssetCategory
from apps.maintenance.models import MaintenanceRequest
from apps.purchases.models import Purchase, Supplier, Payment
from apps.users.models import User
from apps.common.utils import generate_display_id

def backfill():
    print("Backfilling AssetCategory...")
    for idx, obj in enumerate(AssetCategory.objects.filter(display_id__isnull=True).order_by('created_at', 'name'), 1):
        obj.display_id = generate_display_id(AssetCategory, 'CAT')
        obj.save(update_fields=['display_id'])
        print(f"  AssetCategory: {obj.name} -> {obj.display_id}")

    print("Backfilling Asset...")
    for idx, obj in enumerate(Asset.objects.filter(display_id__isnull=True).order_by('created_at', 'purchase_date'), 1):
        obj.display_id = generate_display_id(Asset, 'AST')
        obj.save(update_fields=['display_id'])
        print(f"  Asset: {obj.name} -> {obj.display_id}")

    print("Backfilling AssetUnit...")
    for idx, obj in enumerate(AssetUnit.objects.filter(display_id__isnull=True).order_by('created_at', 'unit_number'), 1):
        obj.display_id = generate_display_id(AssetUnit, 'SER')
        obj.save(update_fields=['display_id'])
        print(f"  AssetUnit: {obj.serial_number} -> {obj.display_id}")

    print("Backfilling AssetAssignmentHistory...")
    for idx, obj in enumerate(AssetAssignmentHistory.objects.filter(display_id__isnull=True).order_by('assigned_date'), 1):
        obj.display_id = generate_display_id(AssetAssignmentHistory, 'ASG')
        obj.save(update_fields=['display_id'])
        print(f"  Assignment: {obj.employee_name} -> {obj.display_id}")

    print("Backfilling AssetRequest...")
    for idx, obj in enumerate(AssetRequest.objects.filter(display_id__isnull=True).order_by('created_at'), 1):
        obj.display_id = generate_display_id(AssetRequest, 'REQ')
        obj.save(update_fields=['display_id'])
        print(f"  AssetRequest: {obj.requested_asset} -> {obj.display_id}")

    print("Backfilling MaintenanceRequest...")
    for idx, obj in enumerate(MaintenanceRequest.objects.filter(display_id__isnull=True).order_by('created_at'), 1):
        obj.display_id = generate_display_id(MaintenanceRequest, 'MNT')
        obj.save(update_fields=['display_id'])
        print(f"  MaintenanceRequest: {obj.issue_description[:30]} -> {obj.display_id}")

    print("Backfilling Supplier...")
    for idx, obj in enumerate(Supplier.objects.filter(display_id__isnull=True).order_by('created_at', 'company'), 1):
        obj.display_id = generate_display_id(Supplier, 'SUP')
        obj.save(update_fields=['display_id'])
        print(f"  Supplier: {obj.company} -> {obj.display_id}")

    print("Backfilling Purchase...")
    for idx, obj in enumerate(Purchase.objects.filter(display_id__isnull=True).order_by('created_at', 'purchase_date'), 1):
        obj.display_id = generate_display_id(Purchase, 'PO')
        obj.save(update_fields=['display_id'])
        print(f"  Purchase: {obj.purchase_number} -> {obj.display_id}")

    print("Backfilling Payment...")
    for idx, obj in enumerate(Payment.objects.filter(display_id__isnull=True).order_by('created_at', 'payment_date'), 1):
        obj.display_id = generate_display_id(Payment, 'PAY')
        obj.save(update_fields=['display_id'])
        print(f"  Payment: {obj.invoice_number} -> {obj.display_id}")

    print("Backfilling User...")
    # First sync users with existing employee_id
    for obj in User.objects.filter(display_id__isnull=True, employee_id__isnull=False).exclude(employee_id=''):
        obj.display_id = obj.employee_id
        obj.save(update_fields=['display_id'])
        print(f"  User (existing emp_id): {obj.email} -> {obj.display_id}")

    # Next generate for remaining users
    for obj in User.objects.filter(display_id__isnull=True).order_by('created_at'):
        new_emp_id = generate_display_id(User, 'EMP')
        obj.display_id = new_emp_id
        obj.employee_id = new_emp_id
        obj.save(update_fields=['display_id', 'employee_id'])
        print(f"  User (new emp_id): {obj.email} -> {obj.display_id}")

    print("Backfill completed successfully!")

if __name__ == '__main__':
    backfill()
