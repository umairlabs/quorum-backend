import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from apps.audit.services import AuditLogService
from apps.audit.models import AuditLog

logger = logging.getLogger(__name__)


class DepreciationService:
    @staticmethod
    def calculate_depreciation(
        purchase_cost: Decimal,
        salvage_value: Decimal,
        useful_life_years: int,
        purchase_date: date = None,
        as_of_date: date = None
    ) -> dict:
        """
        Calculates straight-line depreciation, book value, status, and full yearly schedule.
        """
        if purchase_cost is None:
            purchase_cost = Decimal('0.00')
        else:
            purchase_cost = Decimal(str(purchase_cost))

        if salvage_value is None:
            salvage_value = Decimal('0.00')
        else:
            salvage_value = Decimal(str(salvage_value))

        if not useful_life_years or useful_life_years <= 0:
            useful_life_years = 5

        # Safeguard: salvage value cannot exceed purchase cost
        if salvage_value > purchase_cost:
            salvage_value = purchase_cost

        depreciable_base = max(Decimal('0.00'), purchase_cost - salvage_value)
        annual_depreciation = (depreciable_base / Decimal(str(useful_life_years))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        monthly_depreciation = (annual_depreciation / Decimal('12')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if as_of_date is None:
            as_of_date = date.today()

        if purchase_date is None:
            purchase_date = as_of_date

        # Determine elapsed time and current status
        if purchase_date > as_of_date:
            depreciation_status = 'NOT_STARTED'
            accumulated_depreciation = Decimal('0.00')
            current_book_value = purchase_cost
        else:
            days_diff = (as_of_date - purchase_date).days
            elapsed_years = Decimal(str(days_diff)) / Decimal('365.25')

            if elapsed_years >= Decimal(str(useful_life_years)):
                depreciation_status = 'FULLY_DEPRECIATED'
                accumulated_depreciation = depreciable_base
                current_book_value = salvage_value
            else:
                depreciation_status = 'ACTIVE'
                raw_acc = (elapsed_years * annual_depreciation).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                accumulated_depreciation = min(depreciable_base, raw_acc)
                current_book_value = max(salvage_value, purchase_cost - accumulated_depreciation)

        # Generate yearly depreciation schedule
        schedule = []
        start_year = purchase_date.year if purchase_date else as_of_date.year
        opening_value = purchase_cost
        total_acc = Decimal('0.00')

        for y in range(1, useful_life_years + 1):
            max_expense = max(Decimal('0.00'), opening_value - salvage_value)
            expense = min(annual_depreciation, max_expense)
            closing_value = max(salvage_value, opening_value - expense)
            total_acc += expense

            schedule.append({
                'year': y,
                'yearLabel': f"Year {y} ({start_year + y - 1})",
                'openingBookValue': opening_value,
                'depreciationExpense': expense,
                'accumulatedDepreciation': total_acc,
                'closingBookValue': closing_value,
            })
            opening_value = closing_value

        return {
            'purchasePrice': purchase_cost,
            'purchaseDate': purchase_date,
            'salvageValue': salvage_value,
            'usefulLife': useful_life_years,
            'usefulLifeYears': useful_life_years,
            'depreciationMethod': 'STRAIGHT_LINE',
            'annualDepreciation': annual_depreciation,
            'monthlyDepreciation': monthly_depreciation,
            'accumulatedDepreciation': accumulated_depreciation,
            'currentBookValue': current_book_value,
            'depreciationStatus': depreciation_status,
            'depreciationSchedule': schedule,
        }

    @classmethod
    def get_asset_depreciation_data(cls, asset) -> dict:
        salvage_val = getattr(asset, 'salvage_value', Decimal('0.00')) or Decimal('0.00')
        useful_life = getattr(asset, 'useful_life_years', 5) or 5
        method = getattr(asset, 'depreciation_method', 'STRAIGHT_LINE') or 'STRAIGHT_LINE'

        data = cls.calculate_depreciation(
            purchase_cost=asset.purchase_cost,
            salvage_value=salvage_val,
            useful_life_years=useful_life,
            purchase_date=asset.purchase_date
        )
        data['depreciationMethod'] = method
        data['assetId'] = str(asset.id)
        data['assetName'] = asset.name
        data['category'] = asset.category.name if asset.category else ''
        data['brand'] = asset.brand or ''
        data['model'] = asset.model or ''
        data['serialNumber'] = ''

        first_unit = asset.units.first()
        if first_unit:
            data['serialNumber'] = first_unit.serial_number

        return data

    @classmethod
    @transaction.atomic
    def update_asset_depreciation(
        cls,
        asset,
        salvage_value: Decimal,
        useful_life_years: int,
        depreciation_method: str = 'STRAIGHT_LINE',
        user=None,
        request=None
    ) -> dict:
        old_val = {
            'salvageValue': str(getattr(asset, 'salvage_value', Decimal('0.00'))),
            'usefulLifeYears': getattr(asset, 'useful_life_years', 5),
            'depreciationMethod': getattr(asset, 'depreciation_method', 'STRAIGHT_LINE'),
            'currentValue': str(asset.current_value),
        }

        # Calculate new book value and schedule
        calc_result = cls.calculate_depreciation(
            purchase_cost=asset.purchase_cost,
            salvage_value=salvage_value,
            useful_life_years=useful_life_years,
            purchase_date=asset.purchase_date
        )

        asset.salvage_value = salvage_value
        asset.useful_life_years = useful_life_years
        asset.depreciation_method = depreciation_method
        asset.current_value = calc_result['currentBookValue']
        asset.save(update_fields=['salvage_value', 'useful_life_years', 'depreciation_method', 'current_value', 'updated_at'])

        new_val = {
            'salvageValue': str(salvage_value),
            'usefulLifeYears': useful_life_years,
            'depreciationMethod': depreciation_method,
            'currentValue': str(asset.current_value),
        }

        # Create immutable Audit Log
        AuditLogService.log_action(
            action=AuditLog.Action.ASSET_UPDATED,
            module=AuditLog.Module.ASSETS,
            description=f"Depreciation configuration updated for asset '{asset.name}' (Salvage: Rs. {salvage_value}, Useful Life: {useful_life_years} yrs)",
            user=user,
            asset=asset,
            old_value=old_val,
            new_value=new_val,
            request=request
        )

        return cls.get_asset_depreciation_data(asset)
