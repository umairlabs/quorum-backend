import re


def generate_next_employee_id() -> str:
    """
    Finds the highest existing EMP-XXX number and generates the next one, e.g. EMP-001, EMP-002, etc.
    """
    from .models import User

    emp_ids = User.objects.filter(employee_id__startswith='EMP-').values_list('employee_id', flat=True)
    max_num = 0
    for eid in emp_ids:
        if not eid:
            continue
        match = re.search(r'EMP-(\d+)', eid)
        if match:
            try:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass

    next_num = max_num + 1
    return f"EMP-{next_num:03d}"

from django.utils import timezone
from django.utils.timesince import timesince

from apps.assets.models import AssetAssignmentHistory
from apps.maintenance.models import MaintenanceRequest


# ---------------------------------------------------------------------------
# Icon mapping — best-effort, category name -> material icon.
# Mirrors the intent of the frontend's getCategoryIcon() util so tickets
# rendered from the backend look consistent with the rest of the app.
# ---------------------------------------------------------------------------
_CATEGORY_ICON_MAP = {
    'laptop': 'laptop_mac',
    'desktop': 'computer',
    'monitor': 'desktop_windows',
    'mobile': 'smartphone',
    'printer': 'print',
    'furniture': 'desk',
}


def _asset_icon(asset) -> str:
    if not asset or not asset.category:
        return 'devices'
    return _CATEGORY_ICON_MAP.get(asset.category.name.lower(), 'devices')


# ---------------------------------------------------------------------------
# Status mapping — backend has 5 statuses, frontend TicketStatus only
# recognises 'Open' | 'In Progress' | 'Resolved'.
# ---------------------------------------------------------------------------
_TICKET_STATUS_MAP = {
    MaintenanceRequest.Status.PENDING: 'Open',
    MaintenanceRequest.Status.IN_PROGRESS: 'In Progress',
    MaintenanceRequest.Status.COMPLETED: 'Resolved',
    MaintenanceRequest.Status.VERIFIED: 'Resolved',
    MaintenanceRequest.Status.CANCELLED: 'Resolved',
}


def _format_ticket_date(dt) -> str:
    return dt.strftime('%b %d, %Y')


def _format_relative_time(dt) -> str:
    """
    "2 hours ago" for anything within the last 24h, otherwise an absolute
    "Oct 23, 2023"-style date — matches the mix seen in the frontend's
    static example data.
    """
    now = timezone.now()
    delta = now - dt
    if delta.total_seconds() < 24 * 3600:
        return f"{timesince(dt, now)} ago"
    return dt.strftime('%b %d, %Y')


def _date_to_datetime(d):
    """
    Convert a plain `date` (assigned_date / returned_date on
    AssetAssignmentHistory) into an aware datetime at midnight, so it can be
    sorted/compared against the `created_at` datetimes coming from other
    event sources (MaintenanceRequest).
    """
    dt = timezone.datetime.combine(d, timezone.datetime.min.time())
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


class DashboardService:

    # ------------------------------------------------------------------
    # Recent Maintenance Tickets
    # ------------------------------------------------------------------
    @staticmethod
    def get_recent_maintenance_tickets(limit: int = 4) -> list[dict]:
        requests = (
            MaintenanceRequest.objects
            .select_related('asset', 'asset__category')
            .order_by('-created_at')[:limit]
        )

        tickets = []
        for req in requests:
            tickets.append({
                'id': f"#{req.request_id}",
                'assetIcon': _asset_icon(req.asset),
                'assetName': req.asset.name if req.asset else 'Unknown Asset',
                'problem': req.component_or_issue_type,
                # NOTE: MaintenanceRequest has no dedicated `technician` field
                # yet — falling back to whoever raised the request. If a
                # proper "assigned technician" field is added to the model,
                # swap this out.
                'technician': req.requested_by_name or 'Unassigned',
                'status': _TICKET_STATUS_MAP.get(req.status, req.status),
                'date': _format_ticket_date(req.created_at),
            })
        return tickets

    # ------------------------------------------------------------------
    # Recent Activity — merges assignment events + maintenance ticket
    # creation into a single reverse-chronological feed.
    # ------------------------------------------------------------------
    @staticmethod
    def get_recent_activity(limit: int = 5) -> list[dict]:
        events = []

        # Assignment history: one row per assign; a filled-in returned_date
        # also produces a "returned" event.
        assignments = (
            AssetAssignmentHistory.objects
            .select_related('asset')
            .order_by('-assigned_date')[:limit * 2]
        )
        for a in assignments:
            asset_name = a.asset.name if a.asset else 'Unknown Asset'

            events.append({
                'timestamp': _date_to_datetime(a.assigned_date),
                'dotColor': 'bg-primary',
                'description': f'Asset <b>{asset_name}</b> assigned to <b>{a.employee_name}</b>.',
            })

            if a.returned_date:
                events.append({
                    'timestamp': _date_to_datetime(a.returned_date),
                    'dotColor': 'bg-secondary',
                    'description': f'Asset <b>{asset_name}</b> returned by <b>{a.employee_name}</b>.',
                })

        # Maintenance ticket creation events
        tickets = (
            MaintenanceRequest.objects
            .select_related('asset')
            .order_by('-created_at')[:limit * 2]
        )
        for t in tickets:
            asset_name = t.asset.name if t.asset else 'Unknown Asset'
            events.append({
                'timestamp': t.created_at,
                'dotColor': 'bg-on-tertiary-container',
                'description': f'Ticket <b>#{t.request_id}</b> created for <b>{asset_name}</b>.',
            })

        # Sort newest-first and take the top N
        events.sort(key=lambda e: e['timestamp'], reverse=True)
        top_events = events[:limit]

        return [
            {
                'dotColor': e['dotColor'],
                'description': e['description'],
                'highlighted': [],
                'time': _format_relative_time(e['timestamp']),
            }
            for e in top_events
        ]

    # ------------------------------------------------------------------
    # Combined summary for the single dashboard endpoint
    # ------------------------------------------------------------------
    @staticmethod
    def get_dashboard_summary() -> dict:
        return {
            'recentMaintenanceTickets': DashboardService.get_recent_maintenance_tickets(),
            'recentActivity': DashboardService.get_recent_activity(),
        }