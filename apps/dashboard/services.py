from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.utils.timesince import timesince
from datetime import datetime, timedelta
from decimal import Decimal

from apps.assets.models import Asset, AssetUnit, AssetAssignmentHistory
from apps.maintenance.models import MaintenanceRequest
from apps.users.models import User

_CATEGORY_ICON_MAP = {
    'laptop': 'laptop_mac',
    'desktop': 'computer',
    'monitor': 'desktop_windows',
    'mobile': 'smartphone',
    'printer': 'print',
    'furniture': 'desk',
}

def _asset_icon(asset):
    if not asset or not getattr(asset, 'category', None):
        return 'devices'
    return _CATEGORY_ICON_MAP.get(asset.category.name.lower(), 'devices')

_TICKET_STATUS_MAP = {
    MaintenanceRequest.Status.PENDING: 'Open',
    MaintenanceRequest.Status.IN_PROGRESS: 'In Progress',
    MaintenanceRequest.Status.COMPLETED: 'Resolved',
    MaintenanceRequest.Status.VERIFIED: 'Resolved',
    MaintenanceRequest.Status.CANCELLED: 'Resolved',
}

def _format_ticket_date(dt):
    return dt.strftime('%b %d, %Y') if dt else ''

def _format_relative_time(dt):
    if not dt:
        return ''
    now = timezone.now()
    delta = now - dt
    if delta.total_seconds() < 24 * 3600:
        return f'{timesince(dt, now)} ago'
    return dt.strftime('%b %d, %Y')

def _date_to_datetime(d):
    if isinstance(d, datetime):
        return d
    dt = timezone.datetime.combine(d, timezone.datetime.min.time())
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


class DashboardService:

    @staticmethod
    def get_summary_stats():
        total_assets = Asset.objects.count()
        total_units = AssetUnit.objects.count()

        unit_mnt_count = AssetUnit.objects.filter(status=AssetUnit.Status.MAINTENANCE).count()
        maintenance_count = unit_mnt_count
        # Total open maintenance tickets (for reference — different from physical units in repair)
        total_maint_tickets = MaintenanceRequest.objects.exclude(
            status__in=['RESOLVED', 'COMPLETED', 'VERIFIED', 'CANCELLED', 'UNREPAIRABLE', 'NOT_REPAIRABLE']
        ).count()

        assigned_count = AssetUnit.objects.filter(status=AssetUnit.Status.ASSIGNED).count()
        active_assignments = AssetAssignmentHistory.objects.filter(status=AssetAssignmentHistory.Status.ACTIVE).count()
        scrapped_count = AssetUnit.objects.filter(status=AssetUnit.Status.SCRAPPED).count()
        available_units_count = AssetUnit.objects.filter(status=AssetUnit.Status.AVAILABLE).count()

        available_count = available_units_count
        if total_units > 0:
            total_count = total_units
        else:
            total_count = total_assets
            available_count = total_assets

        cost_agg = Asset.objects.aggregate(
            purchase=Sum('purchase_cost'),
            current=Sum('current_value')
        )
        purchase_val = float(cost_agg['purchase'] or Decimal('0.00'))
        current_val = float(cost_agg['current'] or Decimal('0.00'))

        # Fetch purchase summary details
        total_spent = 0.0
        total_purchases_val = 0.0
        total_outstanding = 0.0
        try:
            from apps.purchases.models import Purchase
            purchases = Purchase.objects.all()
            total_purchases_val = float(sum(p.total_amount for p in purchases))
            total_spent = float(sum(p.paid_amount for p in purchases))
            total_outstanding = float(sum(p.remaining_amount for p in purchases))
        except Exception:
            pass

        return {
            'totalAssets': total_count,
            'totalAssetModels': total_assets,
            'assignedCount': assigned_count,
            'activeAssignments': active_assignments,
            'availableCount': available_count,
            'maintenanceCount': maintenance_count,
            'maintenanceTickets': total_maint_tickets,
            'scrappedCount': scrapped_count,
            'retiredCount': scrapped_count,
            'totalPurchaseValue': purchase_val,
            'totalCurrentValue': current_val,
            'totalSpent': total_spent,
            'totalPurchasesValue': total_purchases_val,
            'totalOutstanding': total_outstanding,
        }

    @staticmethod
    def get_status_distribution(summary_stats):
        total = (
            summary_stats.get('availableCount', 0) +
            summary_stats.get('assignedCount', 0) +
            summary_stats.get('maintenanceCount', 0) +
            summary_stats.get('scrappedCount', 0)
        )
        if total == 0:
            total = summary_stats.get('totalAssets', 0)
        if total == 0:
            return []

        def calc_pct(count):
            return round((count / total) * 100, 1) if total > 0 else 0.0

        return [
            {
                'label': 'Available',
                'count': summary_stats['availableCount'],
                'percentage': calc_pct(summary_stats['availableCount']),
                'color': 'bg-primary',
                'hexColor': '#091426'
            },
            {
                'label': 'Assigned',
                'count': summary_stats['assignedCount'],
                'percentage': calc_pct(summary_stats['assignedCount']),
                'color': 'bg-secondary',
                'hexColor': '#505f76'
            },
            {
                'label': 'Maintenance',
                'count': summary_stats['maintenanceCount'],
                'percentage': calc_pct(summary_stats['maintenanceCount']),
                'color': 'bg-on-tertiary-container',
                'hexColor': '#a38c6a'
            },
            {
                'label': 'Scrapped',
                'count': summary_stats['scrappedCount'],
                'percentage': calc_pct(summary_stats['scrappedCount']),
                'color': 'bg-surface-variant',
                'hexColor': '#e0e3e5'
            },
        ]

    @staticmethod
    def get_value_overview(date_from=None, date_to=None):
        """
        Generate asset value time-series data between date_from and date_to.
        Both should be datetime.date objects. Defaults to the last 12 months.
        """
        from datetime import date, timedelta
        import calendar

        today = date.today()
        if not date_to:
            date_to = today
        if not date_from:
            year = date_to.year
            month = date_to.month - 11
            while month <= 0:
                month += 12
                year -= 1
            date_from = date(year, month, 1)

        assets = list(Asset.objects.all())
        purchases = []
        try:
            from apps.purchases.models import Purchase
            purchases = list(Purchase.objects.select_related('asset').all())
        except Exception:
            pass

        months_abbr = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        x_labels = []
        purchase_points = []
        current_points = []

        # Determine granularity: daily for ≤ 60 days, monthly otherwise
        delta_days = (date_to - date_from).days

        if delta_days <= 60:
            # Daily or every-3-days sampling, target ~12 points
            step = max(1, delta_days // 11)
            point_dates = []
            cur = date_from
            while cur <= date_to:
                point_dates.append(cur)
                cur += timedelta(days=step)
            if point_dates[-1] != date_to:
                point_dates.append(date_to)
            label_fmt = '%b %d'
        else:
            # Monthly sampling
            point_dates = []
            year = date_from.year
            month = date_from.month
            while True:
                _, last_day = calendar.monthrange(year, month)
                snap = date(year, month, last_day)
                snap = min(snap, date_to)
                point_dates.append(snap)
                if snap >= date_to:
                    break
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            label_fmt = None  # use month abbreviation

        linked_asset_ids = set(p.asset_id for p in purchases if p.asset_id)

        for snap in point_dates:
            if label_fmt:
                x_labels.append(snap.strftime(label_fmt))
            else:
                x_labels.append(months_abbr[snap.month - 1])

            p_tot = 0.0
            # Cumulative spend from Purchase orders on or before snapshot date
            for p in purchases:
                p_date = p.purchase_date or (p.created_at.date() if p.created_at else None)
                if p_date and p_date <= snap:
                    p_tot += float(p.total_amount)

            # Plus standalone Assets on or before snapshot date not linked to a Purchase
            for asset in assets:
                if asset.id in linked_asset_ids:
                    continue
                p_date_asset = asset.purchase_date or (asset.created_at.date() if asset.created_at else None)
                if p_date_asset and p_date_asset <= snap:
                    p_tot += float(asset.purchase_cost or 0)

            # Cumulative Current (Net Book Value) of registered assets on or before snapshot date
            c_tot = 0.0
            for asset in assets:
                p_date_asset = asset.purchase_date or (asset.created_at.date() if asset.created_at else None)
                if not p_date_asset or p_date_asset > snap:
                    continue
                p_cost = float(asset.purchase_cost or 0)
                salvage = float(asset.salvage_value or 0)
                useful_life = asset.useful_life_years or 5

                days_elapsed = max(0, (snap - p_date_asset).days)
                years_elapsed = days_elapsed / 365.25
                annual_dep = max(0.0, (p_cost - salvage) / useful_life) if useful_life > 0 else 0.0
                acc_dep = min(max(0.0, p_cost - salvage), annual_dep * years_elapsed)
                cur_val = max(salvage, p_cost - acc_dep)
                c_tot += cur_val

            purchase_points.append(round(p_tot, 2))
            current_points.append(round(c_tot, 2))

        return {
            'xLabels': x_labels,
            'series': [
                {
                    'label': 'Purchase Value',
                    'values': purchase_points,
                    'strokeColor': '#3B82F6',
                    'legendColor': 'bg-blue-500'
                },
                {
                    'label': 'Current Value',
                    'values': current_points,
                    'strokeColor': '#94A3B8',
                    'legendColor': 'bg-slate-400'
                }
            ]
        }
    @staticmethod
    def get_recent_maintenance_tickets(user=None, limit=5):
        qs = MaintenanceRequest.objects.select_related('asset', 'asset__category')
        if user and getattr(user, 'role', '') == User.Role.EXTERNAL_TECHNICIAN:
            qs = qs.filter(Q(requested_by=user) | Q(priority__in=['HIGH', 'CRITICAL']) | Q(status__in=['PENDING', 'IN_PROGRESS']))

        requests = qs.order_by('-created_at')[:limit]

        tickets = []
        for req in requests:
            asset_name = req.asset.name if (req.asset and req.asset.name) else (getattr(req, 'asset_name_snapshot', '') or 'Asset')
            tickets.append({
                'id': req.request_id if req.request_id.startswith('#') else f'#{req.request_id}',
                'rawId': str(req.id),
                'assetIcon': _asset_icon(req.asset),
                'assetName': asset_name,
                'problem': req.component_or_issue_type,
                'technician': req.requested_by_name or 'External Tech',
                'priority': req.priority,
                'status': _TICKET_STATUS_MAP.get(req.status, req.status),
                'date': _format_ticket_date(req.created_at),
            })
        return tickets

    @staticmethod
    def get_recent_activity(limit=20):
        events = []

        assignments = (
            AssetAssignmentHistory.objects
            .select_related('unit', 'unit__asset')
            .order_by('-assigned_date')[:limit * 2]
        )
        for a in assignments:
            asset_name = 'Asset'
            if a.unit and a.unit.asset and a.unit.asset.name:
                asset_name = a.unit.asset.name
            elif getattr(a, 'asset_name_snapshot', ''):
                asset_name = a.asset_name_snapshot

            events.append({
                'timestamp': _date_to_datetime(a.assigned_date),
                'dotColor': 'bg-primary',
                'type': 'Asset Assigned',
                'assetName': asset_name,
                'description': f'Asset <b>{asset_name}</b> assigned to <b>{a.employee_name}</b>.',
            })

            if a.returned_date:
                events.append({
                    'timestamp': _date_to_datetime(a.returned_date),
                    'dotColor': 'bg-secondary',
                    'type': 'Asset Returned',
                    'assetName': asset_name,
                    'description': f'Asset <b>{asset_name}</b> returned by <b>{a.employee_name}</b>.',
                })

        tickets = (
            MaintenanceRequest.objects
            .select_related('asset')
            .order_by('-created_at')[:limit * 2]
        )
        for t in tickets:
            asset_name = t.asset.name if (t.asset and t.asset.name) else (getattr(t, 'asset_name_snapshot', '') or 'Asset')
            events.append({
                'timestamp': t.created_at,
                'dotColor': 'bg-on-tertiary-container',
                'type': 'Maintenance Ticket',
                'assetName': asset_name,
                'description': f'Ticket <b>#{t.request_id}</b> created for <b>{asset_name}</b>.',
            })

        events.sort(key=lambda e: e['timestamp'], reverse=True)
        top_events = events[:limit]

        return [
            {
                'dotColor': e['dotColor'],
                'type': e['type'],
                'assetName': e['assetName'],
                'description': e['description'],
                'highlighted': [],
                'time': _format_relative_time(e['timestamp']),
            }
            for e in top_events
        ]

    @staticmethod
    @staticmethod
    def get_employee_summary_stats(user):
        from apps.assets.models import AssetUnit, AssetAssignmentHistory, AssetRequest
        from apps.maintenance.models import MaintenanceRequest
        from apps.notifications.models import Notification

        assigned_count = AssetAssignmentHistory.objects.filter(user=user, status=AssetAssignmentHistory.Status.ACTIVE).count()
        pending_requests = AssetRequest.objects.filter(employee=user, status=AssetRequest.Status.PENDING).count()
        approved_requests = AssetRequest.objects.filter(employee=user, status=AssetRequest.Status.APPROVED).count()
        maint_count = MaintenanceRequest.objects.filter(requested_by=user).count()
        unread_notifs = Notification.objects.filter(user=user, is_read=False).count()

        return {
            'totalAssets': assigned_count,
            'assignedCount': assigned_count,
            'availableCount': 0,
            'maintenanceCount': maint_count,
            'scrappedCount': 0,
            'retiredCount': 0,
            'totalPurchaseValue': 0.0,
            'totalCurrentValue': 0.0,
            'totalSpent': 0.0,
            'totalOutstanding': 0.0,
            # Employee specific fields
            'myAssignedAssets': assigned_count,
            'pendingRequests': pending_requests,
            'approvedRequests': approved_requests,
            'maintenanceRequests': maint_count,
            'unreadNotifications': unread_notifs,
        }

    @staticmethod
    def get_dashboard_summary(user=None, date_from=None, date_to=None):
        if user and getattr(user, 'role', '') == User.Role.EMPLOYEE:
            summary = DashboardService.get_employee_summary_stats(user)
        else:
            summary = DashboardService.get_summary_stats()
        status_dist = DashboardService.get_status_distribution(summary)
        val_overview = DashboardService.get_value_overview(date_from=date_from, date_to=date_to)
        tickets = DashboardService.get_recent_maintenance_tickets(user=user)
        activity = DashboardService.get_recent_activity()

        return {
            'summary': summary,
            'statusDistribution': status_dist,
            'valueOverview': val_overview,
            'recentMaintenanceTickets': tickets,
            'recentActivity': activity,
        }
