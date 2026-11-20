from .models import MaintenanceRequest


def generate_maintenance_request_id() -> str:
    """
    Generates a unique maintenance request ID in the format MNT-XXX.
    Finds the highest existing numeric suffix and increments it, ensuring no duplicates.
    """
    existing_ids = set(
        MaintenanceRequest.objects.filter(request_id__startswith='MNT-')
        .values_list('request_id', flat=True)
    )
    max_num = 0
    for req_id in existing_ids:
        parts = req_id.split('MNT-')
        if len(parts) == 2 and parts[1].isdigit():
            val = int(parts[1])
            if val > max_num:
                max_num = val

    next_num = max_num + 1
    while f"MNT-{str(next_num).zfill(3)}" in existing_ids:
        next_num += 1

    return f"MNT-{str(next_num).zfill(3)}"
