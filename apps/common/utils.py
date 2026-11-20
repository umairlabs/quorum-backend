import re


def generate_display_id(model_class, prefix: str, field_name: str = 'display_id') -> str:
    """
    Generates sequential display IDs like AST-001, MNT-002, PO-003.
    Extracts numerical suffixes across existing records to calculate the true numeric maximum.
    """
    existing_ids = model_class.objects.filter(
        **{f'{field_name}__startswith': f'{prefix}-'}
    ).values_list(field_name, flat=True)

    max_num = 0
    pattern = re.compile(rf'^{re.escape(prefix)}-(\d+)$')
    for val in existing_ids:
        if val:
            match = pattern.match(str(val))
            if match:
                try:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue

    new_number = max_num + 1
    return f'{prefix}-{new_number:03d}'
