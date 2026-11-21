"""
AI service for Astra Asset Assistant.

Uses Groq API (free tier) if GROQ_API_KEY is set in settings.
Falls back to smart real-database-driven response generator if API key is not configured or fails.
"""
from decimal import Decimal
import json
import logging
import re
import urllib.request
import urllib.error
from datetime import date

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum as _DbSum

from apps.assets.models import Asset, AssetUnit, AssetAssignmentHistory, AssetRequest, AssetCategory
from apps.assets.services import (
    AssetService,
    AssignmentService,
    AssetRequestService,
    AssetCategoryService,
)
from apps.maintenance.models import MaintenanceRequest, MaintenanceTimelineEntry
from apps.purchases.models import Supplier, Purchase
from apps.purchases.services import PurchaseService
from apps.users.models import User

from .prompts import MAINTENANCE_GENERATION_SYSTEM_PROMPT, AI_ASSISTANT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL   = "google/gemini-2.0-flash-exp:free"

GROQ_API_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_MODEL   = "openrouter/free"

# ---------------------------------------------------------------------------
# Legacy Maintenance Issue Generator (used by existing modal feature)
# ---------------------------------------------------------------------------

_MOCK_RULES = [
    (["screen", "display", "monitor", "flicker", "blank", "pixel"],
     "Display Unit Malfunction",
     "The screen/display unit is experiencing issues that impair visibility and usability. This directly affects the user's ability to perform work tasks. The device requires immediate inspection of the display hardware and cable connections.",
     "HIGH"),
    (["keyboard", "key", "typing", "spacebar", "button"],
     "Keyboard Input Failure",
     "The keyboard is malfunctioning, preventing normal data entry. Missing or non-responsive keys create significant productivity barriers for the user. The keyboard requires replacement or repair by the IT team.",
     "MEDIUM"),
    (["battery", "charge", "charging", "power", "not turning on"],
     "Power System Failure - Battery or Charging Issue",
     "The device is experiencing power-related issues that prevent normal operation. The battery may be degraded or the charging circuitry is faulty. Immediate assessment and likely battery replacement is required.",
     "HIGH"),
    (["slow", "lag", "freeze", "hang", "performance"],
     "Performance Degradation - System Slowdown",
     "The device is exhibiting significant performance degradation, causing delays in completing work tasks. This may be caused by storage issues, memory constraints, or software conflicts. A hardware diagnostic and performance audit is recommended.",
     "MEDIUM"),
    (["fan", "heat", "hot", "overheating", "noise"],
     "Cooling System Malfunction - Thermal Issue",
     "The device cooling system is not operating correctly, leading to excessive heat buildup or abnormal fan noise. Continued use risks hardware damage from thermal stress. Immediate inspection and cleaning or fan replacement is required.",
     "HIGH"),
    (["crack", "broken", "physical", "damage", "drop", "fell"],
     "Physical Damage - Hardware Impact",
     "The device has sustained physical damage that may affect structural integrity and internal components. Continued use may worsen the damage or pose a safety risk. A full physical inspection and damage assessment is required.",
     "HIGH"),
    (["wifi", "internet", "network", "connection", "bluetooth"],
     "Network Connectivity Failure",
     "The device is unable to establish or maintain network connectivity, preventing access to critical business systems. This significantly impacts the user's ability to complete work. Network adapter diagnostics and driver/hardware inspection are required.",
     "HIGH"),
    (["mouse", "trackpad", "cursor", "click", "scroll"],
     "Pointing Device Malfunction",
     "The pointing device (mouse/trackpad) is not responding correctly, hindering navigation and interaction with the system. While a workaround may be possible with keyboard shortcuts, productivity is affected. Device replacement or driver update is recommended.",
     "LOW"),
]

_MOCK_DEFAULT = (
    "General Hardware Issue Reported",
    "A hardware issue has been reported that requires IT team assessment. The exact nature and impact will be determined upon inspection. Please prioritize based on the user's workflow impact.",
    "MEDIUM",
)


def _smart_mock(prompt: str) -> dict:
    lower = prompt.lower()
    for keywords, title, description, priority in _MOCK_RULES:
        if any(kw in lower for kw in keywords):
            return {"title": title, "description": description, "priority": priority}
    return {
        "title":       _MOCK_DEFAULT[0],
        "description": _MOCK_DEFAULT[1],
        "priority":    _MOCK_DEFAULT[2],
    }


def _call_groq(prompt: str, api_key: str) -> dict:
    payload = json.dumps({
        "model": model_to_use,
        "messages": [
            {"role": "system", "content": MAINTENANCE_GENERATION_SYSTEM_PROMPT},
            {"role": "user",   "content": f"Issue description: {prompt}"},
        ],
        "temperature": 0.3,
        "max_tokens": 400,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:8100",
            "X-Title": "Quorum Asset Management",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    content = body["choices"][0]["message"]["content"]
    return json.loads(content)


def generate_maintenance_issue(prompt: str) -> dict:
    api_key = (getattr(settings, "OPENROUTER_API_KEY", "") or getattr(settings, "GROQ_API_KEY", "")).strip()

    if api_key:
        try:
            result = _call_groq(prompt, api_key)
            if all(k in result for k in ("title", "description", "priority")):
                return result
        except Exception as exc:
            logger.error("OpenRouter maintenance generation call failed: %s", exc)

    return _smart_mock(prompt)


# ---------------------------------------------------------------------------
# Database Context Builder (Real DB Data Only)
# ---------------------------------------------------------------------------

def _build_authorized_db_context(user) -> dict:
    """
    Build a fresh, real database snapshot authorized for the requesting user.
    Includes exact PostgreSQL/SQLite database aggregate counts in inventory_summary.
    """
    # Database aggregate counts across full database (unrestricted by context slicing)
    total_catalogue_assets = Asset.objects.count()
    total_physical_units = AssetUnit.objects.count()

    available_units_count = AssetUnit.objects.filter(status=AssetUnit.Status.AVAILABLE).count()
    assigned_units_count = AssetUnit.objects.filter(status=AssetUnit.Status.ASSIGNED).count()
    maintenance_units_count = AssetUnit.objects.filter(status=AssetUnit.Status.MAINTENANCE).count()
    scrapped_units_count = AssetUnit.objects.filter(status=AssetUnit.Status.SCRAPPED).count()

    total_maintenance_requests = MaintenanceRequest.objects.count()
    pending_maint_count = MaintenanceRequest.objects.filter(status=MaintenanceRequest.Status.PENDING).count()
    in_progress_maint_count = MaintenanceRequest.objects.filter(status=MaintenanceRequest.Status.IN_PROGRESS).count()
    resolved_maint_count = MaintenanceRequest.objects.filter(status__in=['RESOLVED', 'COMPLETED', 'VERIFIED']).count()

    active_assignments_count = AssetAssignmentHistory.objects.filter(status=AssetAssignmentHistory.Status.ACTIVE).count()

    # Purchase aggregate counts — always from DB directly
    total_purchases_count     = Purchase.objects.count()
    completed_purchases_count = Purchase.objects.filter(status=Purchase.Status.COMPLETED).count()
    pending_purchases_count   = Purchase.objects.filter(status=Purchase.Status.PENDING).count()
    _units_agg = Purchase.objects.filter(status=Purchase.Status.COMPLETED).aggregate(
        total_units=_DbSum('quantity')
    )
    total_purchased_units = _units_agg['total_units'] or 0
    unique_asset_types_purchased = Purchase.objects.values('asset').distinct().count()

    # Employee counts — direct DB aggregates
    total_active_users_count = User.objects.filter(is_active=True).count()
    total_employees_count = User.objects.filter(is_active=True, role='employee').count()
    total_managers_count = User.objects.filter(is_active=True, role__in=['operations_manager', 'system_admin']).count()
    total_technicians_count = User.objects.filter(is_active=True, role='external_technician').count()

    inventory_summary = {
        # Standard names
        "total_assets": total_catalogue_assets,
        "total_physical_units": total_physical_units,
        "available_units": available_units_count,
        "assigned_units": assigned_units_count,
        "maintenance_units": maintenance_units_count,
        "scrapped_units": scrapped_units_count,
        # Teammate extensions
        "total_product_catalog_types": total_catalogue_assets,
        "total_physical_asset_units": total_physical_units,
        "physical_units_by_status": {
            "AVAILABLE": available_units_count,
            "ASSIGNED": assigned_units_count,
            "MAINTENANCE": maintenance_units_count,
            "SCRAPPED": scrapped_units_count,
        },
        "total_maintenance_tickets": total_maintenance_requests,
        "maintenance_tickets_by_status": {
            "PENDING": pending_maint_count,
            "IN_PROGRESS": in_progress_maint_count,
            "RESOLVED": resolved_maint_count,
        },
        "total_active_assignments": active_assignments_count,
        "total_purchases": total_purchases_count,
        "completed_purchases": completed_purchases_count,
        "pending_purchases": pending_purchases_count,
        "total_units_purchased": total_purchased_units,
        "total_purchased_units": total_purchased_units,
        "unique_asset_types_purchased": unique_asset_types_purchased,
        # Employee / user counts
        "total_active_users": total_active_users_count,
        "total_employees": total_employees_count,
        "total_managers_admins": total_managers_count,
        "total_technicians": total_technicians_count,
    }

    # 0. Asset Categories
    categories_qs = AssetCategory.objects.all()
    categories_list = [{"id": str(c.id), "name": c.name} for c in categories_qs]

    # 1. Assets (Product Definitions)
    assets_qs = Asset.objects.select_related('category').all()
    assets_list = []
    for a in assets_qs[:200]:
        assets_list.append({
            "id": str(a.id),
            "formatted_id": a.formatted_asset_id,
            "name": a.name,
            "category": a.category.name if a.category else "Uncategorized",
            "category_id": str(a.category.id) if a.category else None,
            "brand": a.brand,
            "model": a.model,
            "total_qty": a.total_quantity,
            "available_qty": a.available_quantity,
            "assigned_qty": a.assigned_quantity,
            "maintenance_qty": a.maintenance_quantity,
        })

    # 2. Asset Units (Physical Units with Serial Numbers)
    units_qs = AssetUnit.objects.select_related('asset', 'assigned_to').all()
    units_list = []
    for u in units_qs[:300]:
        units_list.append({
            "id": str(u.id),
            "asset_name": u.asset.name if u.asset else "Unknown",
            "serial_number": u.serial_number,
            "status": u.status,
            "location": u.location,
            "assigned_to_name": f"{u.assigned_to.first_name} {u.assigned_to.last_name}".strip() or u.assigned_to.email if u.assigned_to else None,
            "assigned_to_email": u.assigned_to.email if u.assigned_to else None,
            "assigned_to_id": str(u.assigned_to.id) if u.assigned_to else None,
        })

    # 3. Active & Recent Assignments
    assignments_qs = AssetAssignmentHistory.objects.filter(status=AssetAssignmentHistory.Status.ACTIVE).select_related('unit', 'unit__asset')[:200]
    assignments_list = []
    for ass in assignments_qs:
        assignments_list.append({
            "id": str(ass.id),
            "asset_name": ass.asset_name_snapshot,
            "serial_number": ass.unit_serial_snapshot,
            "employee_name": ass.employee_name,
            "department": ass.department,
            "status": ass.status,
            "assigned_date": str(ass.assigned_date),
        })

    # 4. Users / Employees
    users_qs = User.objects.filter(is_active=True)
    users_list = []
    employees_only_list = []
    for u in users_qs[:100]:
        full_name = f"{u.first_name} {u.last_name}".strip() or u.email
        entry = {
            "id": str(u.id),
            "email": u.email,
            "name": full_name,
            "role": u.role,
            "department": u.department,
            "employee_id": u.employee_id,
            "job_title": getattr(u, 'job_title', ''),
        }
        users_list.append(entry)
        if (u.role or '').lower() == 'employee':
            employees_only_list.append(entry)

    # 5. Maintenance Requests
    maint_qs = MaintenanceRequest.objects.select_related('asset', 'asset_unit', 'requested_by').all()[:200]
    maint_list = []
    for m in maint_qs:
        serial_number = "N/A"
        if m.asset_unit and m.asset_unit.serial_number:
            serial_number = m.asset_unit.serial_number
        elif m.asset:
            if hasattr(m.asset, 'units'):
                first_unit = m.asset.units.first()
                if first_unit and first_unit.serial_number:
                    serial_number = first_unit.serial_number
            if serial_number == "N/A" and hasattr(m.asset, 'serial_number') and m.asset.serial_number:
                serial_number = m.asset.serial_number

        created_date_str = m.created_at.strftime('%Y-%m-%d') if m.created_at else "N/A"

        maint_list.append({
            "id": str(m.id),
            "request_id": m.request_id,
            "asset_name": m.asset_name_snapshot or (m.asset.name if m.asset else "Asset"),
            "serial_number": serial_number,
            "issue": m.component_or_issue_type,
            "issue_description": m.issue_description,
            "priority": m.priority,
            "status": m.status,
            "technician": m.assigned_technician or "Unassigned",
            "requested_by": m.requested_by_name or (f"{m.requested_by.first_name} {m.requested_by.last_name}".strip() if m.requested_by else "N/A"),
            "created_at": created_date_str,
        })

    # 6. Recent Purchases (Purchase Orders)
    purchases_qs = Purchase.objects.select_related('asset', 'supplier').order_by('-purchase_date')[:50]
    purchases_list = []
    for p in purchases_qs:
        purchases_list.append({
            "id": str(p.id),
            "purchase_number": p.purchase_number,
            "asset_name": p.asset.name if p.asset else "Unknown",
            "supplier": p.supplier.company if p.supplier else "Unknown",
            "quantity": p.quantity,
            "unit_price": float(p.purchase_price),
            "total_amount": float(p.purchase_price * p.quantity),
            "status": p.status,
            "purchase_date": str(p.purchase_date),
        })

    # 7. Asset Requests
    req_qs = AssetRequest.objects.all()[:30]
    req_list = []
    for r in req_qs:
        req_list.append({
            "id": str(r.id),
            "request_number": r.request_number,
            "employee_name": r.employee_name,
            "requested_asset": r.requested_asset,
            "priority": r.priority,
            "status": r.status,
        })

    # 7. Suppliers
    suppliers_qs = Supplier.objects.all()
    suppliers_list = [
        {
            "id": str(s.id),
            "company": s.company,
            "name": s.name,
            "status": s.status
        }
        for s in suppliers_qs
    ]

    # 8. Purchases (Recent Purchase Orders)
    purchases_qs = Purchase.objects.select_related('asset', 'supplier').all()[:50]
    purchases_list = []
    for p in purchases_qs:
        purchases_list.append({
            "id": str(p.id),
            "purchase_number": p.purchase_number,
            "asset_name": p.asset.name if p.asset else "Unknown",
            "asset_id": str(p.asset.id) if p.asset else None,
            "supplier_name": p.supplier.company if p.supplier else "Unknown",
            "supplier_id": str(p.supplier.id) if p.supplier else None,
            "quantity": p.quantity,
            "unit_price": float(p.purchase_price),
            "total_amount": float(p.total_amount),
            "purchase_date": str(p.purchase_date),
            "status": p.status,
            "payment_status": p.payment_status,
        })

    return {
        "user": {
            "email": user.email,
            "name": f"{user.first_name} {user.last_name}".strip() or user.email,
            "role": user.role,
        },
        "inventory_summary": inventory_summary,
        "categories": categories_list,
        "assets": assets_list,
        "physical_units": units_list,
        "assignments": assignments_list,
        "employees": users_list,
        "employees_only": employees_only_list,
        "maintenance_tickets": maint_list,
        "purchases": purchases_list,
        "asset_requests": req_list,
        "suppliers": suppliers_list,
        "purchases": purchases_list,
    }


# ---------------------------------------------------------------------------
# OpenRouter AI Assistant Endpoint Implementation
# ---------------------------------------------------------------------------

def _call_openrouter_assistant(message: str, history: list, db_context: dict, api_key: str, max_retries: int = 1) -> dict:
    context_str = json.dumps(db_context, indent=2)
    sys_content = AI_ASSISTANT_SYSTEM_PROMPT + "\n\nCURRENT REAL DATABASE SNAPSHOT:\n" + context_str

    messages = [
        {"role": "system", "content": sys_content}
    ]

    for item in history[-6:]:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})

    last_exc = None
    fast_models = ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemini-flash-1.5-8b:free", "openrouter/free"]
    for attempt, model_to_use in enumerate(fast_models, 1):
        payload = json.dumps({
            "model": model_to_use,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2500,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")

        req = urllib.request.Request(
            OPENROUTER_API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Quorum Asset Management",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            content = body["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:
            last_exc = exc
            logger.warning(f"OpenRouter attempt {attempt}/{max_retries} failed: {exc}")
            continue

    raise last_exc if last_exc is not None else RuntimeError("OpenRouter: all retries failed with no exception captured.")


def _call_groq_assistant(message: str, history: list, db_context: dict, api_key: str) -> dict:
    context_str = json.dumps(db_context, indent=2)
    sys_content = AI_ASSISTANT_SYSTEM_PROMPT + "\n\nCURRENT REAL DATABASE SNAPSHOT:\n" + context_str

    messages = [
        {"role": "system", "content": sys_content}
    ]

    for item in history[-6:]:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})

    payload = json.dumps({
        "model": model_to_use,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 2500,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:8100",
            "X-Title": "Quorum Asset Management",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=8) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    content = body["choices"][0]["message"]["content"]
    return json.loads(content)


# Backwards compatibility alias
_call_groq_assistant = _call_openrouter_assistant


# ---------------------------------------------------------------------------
# Helper: Extract Add Asset Details from Command
# ---------------------------------------------------------------------------

def _extract_add_asset_details(message: str, db_categories: list) -> tuple:
    msg = message.strip()
    msg_clean = msg.rstrip(".,;!")
    msg_lower = msg_clean.lower()

    asset_name = ""
    category_name = ""

    # 1. Category extraction
    cat_match1 = re.search(r'\b(?:category\s+name|category)\s+(?:is|:|=)?\s+["\']?([^"\'.,;!\n]+?)["\']?(?:\.|\s+and\b|\s+with\b|$)', msg_clean, re.IGNORECASE)
    if cat_match1:
        category_name = clean_extracted_category(cat_match1.group(1))

    if not category_name:
        cat_match2 = re.search(r'\b(?:under|in|with)\s+(?:the\s+)?category\s+(?:name\s+)?(?:is|:|=)?\s*["\']?([^"\'.,;!\n]+?)["\']?(?:\.|\s+and\b|\s+with\b|$)', msg_clean, re.IGNORECASE)
        if cat_match2:
            category_name = clean_extracted_category(cat_match2.group(1))

    if not category_name:
        cat_match3 = re.search(r'\b(?:under|in)\s+([A-Za-z0-9_\- ]+?)(?:\s+category)?(?:\.|\s+and\b|$)', msg_clean, re.IGNORECASE)
        if cat_match3:
            cand = clean_extracted_category(cat_match3.group(1))
            if cand.lower() not in ["asset", "the asset", "an asset", "product", "item", "new asset"]:
                category_name = cand

    # 2. Asset Name extraction
    named_match = re.search(r'\b(?:named|called|title[d]?)\s+["\']?([^"\'.,;!\n]+?)["\']?(?:\.|\s+(?:under|in|category|and|with)\b|$)', msg_clean, re.IGNORECASE)
    if named_match:
        asset_name = clean_extracted_text(named_match.group(1))
    else:
        name_match2 = re.search(r'(?<!category\s)(?<!category\s\s)\b(?:asset\s+|product\s+)?name\s+(?:is|:|=)\s+["\']?([^"\'.,;!\n]+?)["\']?(?:\.|\s+and\b|\s+with\b|\s+under\b|\s+in\b|$)', msg_clean, re.IGNORECASE)
        if name_match2:
            asset_name = clean_extracted_text(name_match2.group(1))

    if not asset_name:
        create_match = re.search(r'(?:add|create)\s+(?:a\s+new\s+|an?\s+)?(?:asset|product|item|device|unit)?\s*["\']?([^"\'.,;!\n]+?)["\']?(?:\.|\s+(?:under|in|category|and|with)\b|$)', msg_clean, re.IGNORECASE)
        if create_match:
            candidate = clean_extracted_text(create_match.group(1))
            candidate = re.sub(r'^(?:a\s+new\s+|an?\s+|the\s+)?(?:asset|product|item|device|unit)\s+', '', candidate, flags=re.IGNORECASE).strip()
            if candidate and candidate.lower() not in ["asset", "an asset", "new asset", "product", "item"]:
                asset_name = candidate

    # Clean asset_name of lingering category clauses
    if asset_name:
        asset_name = re.sub(r'\s+(?:and|with)\s+(?:the\s+)?category.*$', '', asset_name, flags=re.IGNORECASE).strip()
        asset_name = re.sub(r'\s+under\s+category.*$', '', asset_name, flags=re.IGNORECASE).strip()
        asset_name = re.sub(r'\s+in\s+category.*$', '', asset_name, flags=re.IGNORECASE).strip()
        asset_name = re.sub(r'\s+and\s+category\s+name.*$', '', asset_name, flags=re.IGNORECASE).strip()
        asset_name = clean_extracted_text(asset_name)

    cat_obj = None
    if category_name:
        for c in db_categories:
            c_name = c['name'] if isinstance(c, dict) else c.name
            if c_name.lower() == category_name.lower():
                cat_obj = c if isinstance(c, dict) else {'id': str(c.id), 'name': c.name}
                category_name = c_name
                break

    brand = ""
    model = ""

    # Explicit "brand X" or "brand is X" extraction
    brand_match = re.search(r'\bbrand\s+(?:is|:|=)?\s*["\']?([^"\'.,;!\n]+?)["\']?(?:\.|\s+and\b|\s+with\b|\s+model\b|\s+under\b|\s+in\b|$)', msg_clean, re.IGNORECASE)
    if brand_match:
        brand = clean_extracted_text(brand_match.group(1))

    # Explicit "model X" or "model is X" extraction
    model_match = re.search(r'\bmodel\s+(?:is|:|=)?\s*["\']?([^"\'.,;!\n]+?)["\']?(?:\.|\s+and\b|\s+with\b|\s+under\b|\s+in\b|$)', msg_clean, re.IGNORECASE)
    if model_match:
        model = clean_extracted_text(model_match.group(1))

    # Fallback keyword-based brand detection if not explicitly specified
    if not brand:
        if "dell" in msg_lower:
            brand = "Dell"
        elif "hp" in msg_lower:
            brand = "HP"
        elif "lenovo" in msg_lower:
            brand = "Lenovo"
        elif "apple" in msg_lower:
            brand = "Apple"

    # Fallback: if brand detected via keyword and asset name starts with it, extract model from name
    if not model and brand and asset_name and asset_name.lower().startswith(brand.lower()):
        model = asset_name[len(brand):].strip()

    return asset_name, category_name, cat_obj, brand, model


def clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = t.rstrip(".,;!")
    return t.strip()


def clean_extracted_category(cat_raw: str) -> str:
    cat = clean_extracted_text(cat_raw)
    if not cat:
        return ""
    cat = re.sub(r'^(?:with\s+)?(?:the\s+)?(?:category\s+)?(?:name\s+)?(?:is|:|=)?\s*', '', cat, flags=re.IGNORECASE).strip()
    cat = re.sub(r'^(?:name\s+)+', '', cat, flags=re.IGNORECASE).strip()
    return clean_extracted_text(cat)


def _extract_purchase_details(message: str, db_context: dict) -> dict:
    from decimal import Decimal
    msg = message.strip()
    msg_lower = msg.lower()

    # Quantity extraction: e.g. "Quantity is 1", "10 USB units", "purchase 10"
    qty = 1
    qty_match = re.search(r'\b(?:quantity|qty)\s*(?:is|:|=)?\s*(\d+)\b', msg_lower)
    if qty_match:
        qty = int(qty_match.group(1))
    else:
        qty_match2 = re.search(r'\b(?:purchase|buy)\s+(?:the\s+)?(\d+)\b', msg_lower)
        if qty_match2:
            qty = int(qty_match2.group(1))

    # Unit Price extraction: supporting commas e.g. "20,000" or "Rs. 20,000"
    unit_price = Decimal('0.00')
    price_match = re.search(r'(?:unit\s*price|price|rate|cost|rs\.?|pkr|at|for)\s*(?:is|:|=)?\s*(?:rs\.?|pkr)?\s*([\d,]+(?:\.\d+)?)\s*(?:each|per\s*unit|unit)?\b', msg_lower)
    if price_match:
        raw_num = price_match.group(1).replace(",", "").strip()
        try:
            val = Decimal(raw_num)
            if val > 0:
                unit_price = val
        except Exception:
            pass

    if unit_price == Decimal('0.00'):
        explicit_price = re.search(r'(?:rs\.?|pkr)\s*([\d,]+(?:\.\d+)?)', msg_lower)
        if explicit_price:
            try:
                unit_price = Decimal(explicit_price.group(1).replace(",", "").strip())
            except Exception:
                pass

    # Asset matching against real DB assets (sort by length descending so longer asset names match first)
    db_assets = db_context.get("assets", [])
    matched_asset = None

    sorted_assets = sorted(db_assets, key=lambda x: len(x.get("name", "")), reverse=True)
    for a in sorted_assets:
        aname = a.get("name", "").strip().lower()
        if not aname:
            continue
        if re.search(r'\b' + re.escape(aname) + r'\b', msg_lower):
            matched_asset = a
            break

    # If not found by name, try matching by brand+model combination in DB
    if not matched_asset:
        brand_kw = re.search(r'\bbrand\s+(?:is|:|=)?\s*([A-Za-z0-9]+)', msg, re.IGNORECASE)
        model_kw = re.search(r'\bmodel\s+(?:is|:|=)?\s*([A-Za-z0-9_\- ]+?)(?:\.|,|\s+and\b|\s+with\b|$)', msg, re.IGNORECASE)
        b_val = brand_kw.group(1).strip().lower() if brand_kw else ""
        m_val = model_kw.group(1).strip().lower() if model_kw else ""
        if b_val or m_val:
            for a in db_assets:
                ab = (a.get("brand") or "").lower()
                am = (a.get("model") or "").lower()
                if (b_val and b_val in ab) or (m_val and m_val in am):
                    matched_asset = a
                    break

    # If still not found, try category match from message
    if not matched_asset:
        cat_kw = re.search(r'\bcategory\s+(?:is|:|=)?\s*([A-Za-z0-9_\- ]+?)(?:\.|,|\s+and\b|\s+brand\b|\s+model\b|$)', msg, re.IGNORECASE)
        cat_val = cat_kw.group(1).strip().lower() if cat_kw else ""
        if cat_val:
            for a in db_assets:
                ac = (a.get("category") or "").lower()
                if cat_val in ac or ac in cat_val:
                    matched_asset = a
                    break

    # If not found in snapshot, search Django DB directly by name
    if not matched_asset:
        raw_asset_name_match = re.search(r'(?:purchase|buy)\s+(?:the\s+)?(["\']?[A-Za-z0-9_\- ]+?["\']?)\s*(?:asset|units?|pcs?|item)?(?:\.|\s+(?:quantity|with|from|at|category|brand|model)|$)', msg, re.IGNORECASE)
        target_name = raw_asset_name_match.group(1).strip() if raw_asset_name_match else ""
        if target_name:
            from apps.assets.models import Asset as _Asset
            db_obj = _Asset.objects.filter(name__iexact=target_name).first()
            if not db_obj:
                db_obj = _Asset.objects.filter(name__icontains=target_name).first()
            if db_obj:
                matched_asset = {"id": str(db_obj.id), "name": db_obj.name, "category": db_obj.category.name if db_obj.category else "",
                                 "brand": db_obj.brand or "", "model": db_obj.model or ""}

    raw_asset_name = ""
    if not matched_asset:
        clean_name = re.sub(r'\b(purchase|buy|create|add|units?|pcs?|items?|assets?|the|at|from|for|price|unit\s*price|rs\.?|pkr|\d+)\b', '', msg_lower, flags=re.IGNORECASE).strip()
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        raw_asset_name = clean_name if clean_name else "requested asset"

    # Supplier matching
    db_suppliers = db_context.get("suppliers", [])
    matched_supplier = None
    for s in db_suppliers:
        scompany = s.get("company", "").strip().lower()
        sname = s.get("name", "").strip().lower() if s.get("name") else ""
        if (scompany and re.search(r'\b' + re.escape(scompany) + r'\b', msg_lower)) or (sname and re.search(r'\b' + re.escape(sname) + r'\b', msg_lower)):
            matched_supplier = s
            break

    # Default to first available supplier in system if no supplier specified in command
    if not matched_supplier and db_suppliers:
        matched_supplier = db_suppliers[0]

    return {
        "quantity": qty,
        "unit_price": unit_price,
        "matched_asset": matched_asset,
        "raw_asset_name": raw_asset_name,
        "matched_supplier": matched_supplier,
    }



# ---------------------------------------------------------------------------
# Smart Fallback AI Engine (Real Data Powered)
# ---------------------------------------------------------------------------

def _fallback_smart_assistant(user, message: str, db_context: dict) -> dict:
    msg_lower = message.lower()

    # 0. Check read-only purchase queries (e.g. "How many purchases do we have?", "Tell me about our recent purchases")
    if any(k in msg_lower for k in ["purchase", "purchases", "bought", "khareedari", "procurement"]) and \
       any(k in msg_lower for k in ["how many", "count", "total", "summary", "recent", "latest", "show", "tell", "list", "detail", "history", "which"]):
        purchases = db_context.get("purchases", [])
        summary = db_context.get("inventory_summary", {})
        total_p = summary.get("total_purchases", len(purchases))
        total_qty = summary.get("total_purchased_units", sum(p.get("quantity", 0) for p in purchases))
        unique_types = summary.get("unique_asset_types_purchased", len({p.get("asset_name") for p in purchases}))

        if not purchases and total_p == 0:
            return {
                "message": "Currently, there are **0 purchase orders** in the system.",
                "intent": "QUERY",
                "action": None
            }

        # "How many units have we purchased?" / "total purchased units"
        if any(k in msg_lower for k in ["unit", "units", "qty", "quantity", "stock"]) and \
           any(k in msg_lower for k in ["how many", "count", "total"]):
            return {
                "message": f"A total of **{total_qty} units** have been purchased across **{total_p} purchase order(s)** in the system.",
                "intent": "QUERY",
                "action": None
            }

        # "How many different asset types have we purchased?" / "unique assets purchased"
        if any(k in msg_lower for k in ["different", "unique", "type", "types", "kind", "kinds"]):
            return {
                "message": f"There are **{unique_types} unique asset type(s)** that have been purchased across **{total_p} purchase order(s)**.",
                "intent": "QUERY",
                "action": None
            }

        # "How many purchased assets" — this phrasing is ambiguous; clarify instead of guessing
        if "purchased asset" in msg_lower or "purchased assets" in msg_lower:
            return {
                "message": (
                    "The term **'purchased assets'** can mean different things. Here is a breakdown for clarity:\n\n"
                    f"- **Purchase Orders (POs)**: **{total_p}** — the number of purchase records in the system.\n"
                    f"- **Total Units Purchased**: **{total_qty}** — the total quantity of physical units bought across all POs.\n"
                    f"- **Unique Asset Types**: **{unique_types}** — the number of distinct asset catalogue types that appear in purchase orders.\n"
                    f"- **Physical Units in Inventory**: **{summary.get('total_physical_units', 'N/A')}** — current AssetUnit records (includes all statuses).\n\n"
                    "Which of these are you looking for?"
                ),
                "intent": "QUERY",
                "action": None
            }

        # "How many purchases do we have?" — count-only questions
        if any(k in msg_lower for k in ["how many", "count", "total"]) and \
           not any(k in msg_lower for k in ["show", "list", "tell", "detail", "recent", "latest"]):
            return {
                "message": f"There are **{total_p} purchase order(s)** in the system (total of **{total_qty} units** purchased).",
                "intent": "QUERY",
                "action": None
            }

        # "Show me / list / tell me / recent / latest purchases"
        lines = [f"Found **{total_p} purchase order(s)** ({total_qty} total units purchased):\n"]
        for p in purchases[:10]:
            lines.append(f"- **PO #{p.get('purchase_number')}**: {p.get('quantity')}x **{p.get('asset_name')}** from {p.get('supplier_name')} | Amount: Rs. {p.get('total_amount', 0):,.2f} | Date: {p.get('purchase_date')} | Status: **{p.get('status')}**")

        return {
            "message": "\n".join(lines),
            "intent": "QUERY",
            "action": None
        }


    # 0.1 Check purchase action commands (e.g., "Purchase the PC asset. Quantity is 1 and the unit price is Rs. 20,000.")
    if any(k in msg_lower for k in ["purchase", "buy", "khareed"]):
        parsed = _extract_purchase_details(message, db_context)
        qty = parsed["quantity"]
        unit_price = parsed["unit_price"]
        matched_asset = parsed["matched_asset"]
        raw_asset_name = parsed["raw_asset_name"]
        matched_supplier = parsed["matched_supplier"]

        # Validate asset existence in catalogue
        if not matched_asset:
            asset_display = raw_asset_name.strip() if raw_asset_name else "requested asset"
            db_assets = db_context.get("assets", [])
            if db_assets:
                asset_list = "\n".join([
                    f"- **{a['name']}**" + (f" (Brand: {a['brand']}, Model: {a['model']})" if a.get('brand') else "")
                    for a in db_assets[:10]
                ])
                return {
                    "message": (
                        f"Asset **'{asset_display}'** was not found in the catalogue.\n\n"
                        f"Before purchasing, the product definition must exist in the catalogue.\n\n"
                        f"**Available assets in catalogue:**\n{asset_list}\n\n"
                        f"Please use the exact asset name, or create the asset definition first."
                    ),
                    "intent": "QUERY",
                    "action": None
                }
            return {
                "message": f"Asset **'{asset_display}'** was not found in catalogue. Please create the asset definition first.",
                "intent": "QUERY",
                "action": None
            }

        # Validate supplier
        if not matched_supplier:
            avail_suppliers = ", ".join([f"**{s['company']}**" for s in db_context.get("suppliers", [])])
            return {
                "message": f"Please specify a valid supplier to continue with the purchase.\n\nAvailable suppliers in system: {avail_suppliers if avail_suppliers else 'None'}",
                "intent": "QUERY",
                "action": None
            }

        if unit_price <= Decimal('0.00'):
            return {
                "message": f"Please specify the unit price for purchasing **{matched_asset['name']}** (e.g. *\"unit price is Rs. 20,000\"*).",
                "intent": "QUERY",
                "action": None
            }

        total_amount = Decimal(qty) * unit_price

        lines = [
            "Please confirm this purchase:\n",
            f"- **Asset**: {matched_asset['name']}",
            f"- **Quantity**: {qty}",
            f"- **Unit Price**: Rs. {unit_price:,.2f}",
            f"- **Total Amount**: Rs. {total_amount:,.2f}",
            f"- **Supplier**: {matched_supplier['company']}"
        ]

        return {
            "message": "\n".join(lines),
            "intent": "ACTION_PROPOSAL",
            "action": {
                "type": "CREATE_PURCHASE",
                "params": {
                    "asset_id": matched_asset["id"],
                    "asset_name": matched_asset["name"],
                    "supplier_id": matched_supplier["id"],
                    "supplier_name": matched_supplier["company"],
                    "quantity": qty,
                    "unit_price": float(unit_price),
                    "total_amount": float(total_amount),
                },
                "summary": f"Purchase {qty} {matched_asset['name']} unit(s) at Rs. {unit_price:,.2f} each from {matched_supplier['company']} (Total: Rs. {total_amount:,.2f})",
                "requires_confirmation": True
            }
        }

    # 0.5 Check for "create maintenance ticket" intent (must come before the query check below)
    if any(k in msg_lower for k in ["maintenance", "repair", "kharab", "servicing", "ticket", "work order"]) and \
       any(k in msg_lower for k in ["create", "report", "add", "raise", "log", "banao", "bana do"]):
        db_assets = db_context.get("assets", [])
        matched_asset = None
        sorted_assets = sorted(db_assets, key=lambda x: len(x.get("name", "")), reverse=True)
        for a in sorted_assets:
            aname = a.get("name", "").strip().lower()
            if aname and re.search(r'\b' + re.escape(aname) + r'\b', msg_lower):
                matched_asset = a
                break

        if not matched_asset:
            return {
                "message": "Please specify which asset has the issue (e.g. *\"Create a maintenance ticket for Printer, screen issue\"*).",
                "intent": "GENERAL",
                "action": None
            }

        issue_result = generate_maintenance_issue(message)

        lines = [
            "Please confirm creating this maintenance ticket:\n",
            f"- **Asset**: {matched_asset['name']}",
            f"- **Issue**: {issue_result['title']}",
            f"- **Priority**: {issue_result['priority']}",
            f"- **Description**: {issue_result['description']}"
        ]

        return {
            "message": "\n".join(lines),
            "intent": "ACTION_PROPOSAL",
            "action": {
                "type": "CREATE_MAINTENANCE",
                "params": {
                    "asset_id": matched_asset["id"],
                    "asset_name": matched_asset["name"],
                    "title": issue_result["title"],
                    "description": issue_result["description"],
                    "priority": issue_result["priority"],
                },
                "summary": f"Create maintenance ticket for {matched_asset['name']}: {issue_result['title']}",
                "requires_confirmation": True
            }
        }

    # 1. Check maintenance tickets / under maintenance queries
    if any(k in msg_lower for k in ["maintenance", "repair", "kharab", "under maintenance", "in maintenance", "servicing", "ticket", "work order"]):
        tickets = db_context.get("maintenance_tickets", [])
        active_statuses = {"PENDING", "TODO", "IN_PROGRESS", "REVIEW"}

        # Filter to active tickets only for "currently/active/pending" queries;
        # for generic count/listing queries ("how many", "show", "list", "recent", "tell")
        # return ALL tickets so the count is accurate.
        if any(k in msg_lower for k in ["currently", "under maintenance", "active", "pending", "in progress"]):
            filtered_tickets = [t for t in tickets if t.get("status") in active_statuses]
        else:
            filtered_tickets = tickets

        total_count = len(tickets)
        filtered_count = len(filtered_tickets)

        if total_count == 0:
            return {
                "message": "Currently, there are **0 maintenance requests** in the system.",
                "intent": "QUERY",
                "action": None
            }

        # Count-only question ("how many")
        summary = db_context.get("inventory_summary", {})
        maint_units = summary.get("physical_units_by_status", {}).get("MAINTENANCE", len([u for u in db_context.get("physical_units", []) if u.get("status") == "MAINTENANCE"]))
        active_count = len([t for t in tickets if t.get("status") in active_statuses])

        if any(k in msg_lower for k in ["how many", "count", "total", "kithnay", "kitne"]) and \
           not any(k in msg_lower for k in ["show", "list", "tell", "detail", "recent"]):
            return {
                "message": f"Currently, there are **{maint_units} physical asset unit(s)** in maintenance status (with **{active_count} active maintenance ticket(s)** logged, and **{total_count} total ticket(s)** overall).",
                "intent": "QUERY",
                "action": None
            }

        label = "active maintenance request(s)" if any(k in msg_lower for k in ["currently", "under maintenance", "active", "pending", "in progress"]) else "maintenance request(s)"
        lines = [f"Currently, there are **{maint_units} physical asset unit(s)** in maintenance status (with **{filtered_count} {label}** logged):\n"]
        for t in filtered_tickets[:15]:
            sn = t.get('serial_number') or 'N/A'
            req_id = t.get('request_id') or 'N/A'
            status = t.get('status') or 'N/A'
            priority = t.get('priority') or 'N/A'
            created_date = t.get('created_at') or 'N/A'
            lines.append(f"- **{t.get('asset_name', 'Asset')}** (SN: `{sn}`) | Ticket: `{req_id}` | Status: **{status}** | Priority: **{priority}** | Date: {created_date}")

        return {
            "message": "\n".join(lines),
            "intent": "QUERY",
            "action": None
        }

    # 2. Check general stats or count questions
    if any(k in msg_lower for k in ["how many", "count", "total", "summary", "kithnay", "kitne"]):
        if any(w in msg_lower for w in ["asset", "unit", "device", "physical", "available", "assigned", "maintenance", "scrapped"]):
            summary = db_context.get("inventory_summary") or {}
            total_assets = summary.get("total_assets") or summary.get("total_product_catalog_types", Asset.objects.count())
            total_units = summary.get("total_physical_units") or summary.get("total_physical_asset_units", AssetUnit.objects.count())
            status_map = summary.get("physical_units_by_status", {})
            available_units = summary.get("available_units") or status_map.get("AVAILABLE", AssetUnit.objects.filter(status=AssetUnit.Status.AVAILABLE).count())
            assigned_units = summary.get("assigned_units") or status_map.get("ASSIGNED", AssetUnit.objects.filter(status=AssetUnit.Status.ASSIGNED).count())
            maintenance_units = summary.get("maintenance_units") or status_map.get("MAINTENANCE", AssetUnit.objects.filter(status=AssetUnit.Status.MAINTENANCE).count())
            scrapped_units = summary.get("scrapped_units") or status_map.get("SCRAPPED", AssetUnit.objects.filter(status=AssetUnit.Status.SCRAPPED).count())

            lines = [
                "Here is the current inventory summary:\n",
                f"- **Total Product Catalog Types**: {total_assets}",
                f"- **Total Physical Units**: {total_units}",
                f"- **Available Units**: {available_units}",
                f"- **Assigned Units**: {assigned_units}",
                f"- **In Maintenance**: {maintenance_units}",
                f"- **Scrapped Units**: {scrapped_units}",
            ]

            return {
                "message": "\n".join(lines),
                "intent": "QUERY",
                "action": None
            }

    # 3. Specific Employee assignment lookup (e.g. "Warda ke assets", "Show assets of Ali")
    emp_match = re.search(r'(?:of|for|ko|ke|k)\s+([a-zA-Z0-9_\-]+)', msg_lower)
    if emp_match:
        target_name = emp_match.group(1).lower()
        if target_name not in ["asset", "assets", "me", "my", "all", "the", "create", "add"]:
            units = db_context.get("physical_units", [])
            assigned = [u for u in units if u.get("assigned_to_name") and target_name in u["assigned_to_name"].lower()]
            if assigned:
                emp_real_name = assigned[0]["assigned_to_name"]
                lines = [f"Found **{len(assigned)} physical asset unit(s)** assigned to **{emp_real_name}**:\n"]
                for u in assigned:
                    lines.append(f"- **{u['asset_name']}** (Serial: `{u['serial_number']}`) - Status: {u['status']}")
                return {
                    "message": "\n".join(lines),
                    "intent": "QUERY",
                    "action": None
                }

    # 3.5 Action: Return Asset (must come before generic checks)
    if "return" in msg_lower or "wapis" in msg_lower or "wapas" in msg_lower:
        units = db_context.get("physical_units", [])
        assigned_units = [u for u in units if u.get("status") == "ASSIGNED"]

        matched_unit = None
        for u in assigned_units:
            sn = u.get("serial_number", "").strip().lower()
            if sn and sn in msg_lower:
                matched_unit = u
                break

        name_matches = []
        if not matched_unit:
            sorted_units = sorted(assigned_units, key=lambda x: len(x.get("asset_name", "")), reverse=True)
            for u in sorted_units:
                aname = u.get("asset_name", "").strip().lower()
                if aname and re.search(r'\b' + re.escape(aname) + r'\b', msg_lower):
                    name_matches.append(u)

            if len(name_matches) == 1:
                matched_unit = name_matches[0]
            elif len(name_matches) > 1:
                lines = [f"There are **{len(name_matches)} assigned units** matching that asset name. Please specify the serial number of the one you want to return:\n"]
                for u in name_matches:
                    lines.append(f"- **{u['asset_name']}** (Serial: `{u['serial_number']}`) - Assigned to: {u.get('assigned_to_name', 'N/A')}")
                return {
                    "message": "\n".join(lines),
                    "intent": "QUERY",
                    "action": None
                }

        if not matched_unit:
            return {
                "message": "I couldn't find an assigned unit matching that description. Please specify the exact asset name or serial number (e.g. *\"Return the Printer\"*).",
                "intent": "GENERAL",
                "action": None
            }

        return {
            "message": f"Please confirm returning this asset:\n\n- **Asset**: {matched_unit['asset_name']}\n- **Serial Number**: `{matched_unit['serial_number']}`\n- **Currently Assigned To**: {matched_unit.get('assigned_to_name', 'N/A')}",
            "intent": "ACTION_PROPOSAL",
            "action": {
                "type": "RETURN_ASSET",
                "params": {
                    "unit_id": matched_unit["id"],
                    "asset_name": matched_unit["asset_name"],
                    "serial_number": matched_unit["serial_number"],
                },
                "summary": f"Return {matched_unit['asset_name']} ({matched_unit['serial_number']})",
                "requires_confirmation": True
            }
        }

    # 4. Action: Assign Asset
    if "assign" in msg_lower:
        units = db_context.get("physical_units", [])
        avail = [u for u in units if u.get("status") == "AVAILABLE"]
        users = db_context.get("employees", [])

        # ── Step 1: Try to find asset from message ────────────────────────
        matched_unit = None
        for u in avail:
            sn = u.get("serial_number", "").strip().lower()
            if sn and sn in msg_lower:
                matched_unit = u
                break

        unit_name_matches = []
        if not matched_unit:
            sorted_units = sorted(avail, key=lambda x: len(x.get("asset_name", "")), reverse=True)
            for u in sorted_units:
                aname = u.get("asset_name", "").strip().lower()
                if aname and re.search(r'\b' + re.escape(aname) + r'\b', msg_lower):
                    unit_name_matches.append(u)
            if len(unit_name_matches) == 1:
                matched_unit = unit_name_matches[0]
            elif len(unit_name_matches) > 1:
                lines = [f"There are **{len(unit_name_matches)} available units** matching that asset name. Please specify the serial number:\n"]
                for u in unit_name_matches:
                    lines.append(f"- **{u['asset_name']}** (Serial: `{u['serial_number']}`)")
                return {"message": "\n".join(lines), "intent": "QUERY", "action": None}

        # ── Step 2: Try to find employee from message ─────────────────────
        user_matches = [u for u in users if u["name"].lower() in msg_lower]
        if len(user_matches) > 1:
            lines = [f"There are **{len(user_matches)} employees** matching that name:\n"]
            for u in user_matches:
                lines.append(f"- **{u['name']}** ({u.get('email', 'N/A')}) — {u.get('department', 'N/A')}")
            return {"message": "\n".join(lines), "intent": "QUERY", "action": None}
        target_user = user_matches[0] if user_matches else None

        # ── Step 3: Ask for BOTH if neither provided ──────────────────────
        if not matched_unit and not target_user:
            lines = ["Sure! To assign an asset, I need two things:\n",
                     "1. **Which asset** (name or serial number)",
                     "2. **Which employee** (name)\n"]
            if avail:
                lines.append("**Available units you can assign:**")
                seen = {}
                for u in avail[:15]:
                    key = u.get("asset_name", "")
                    if key not in seen:
                        seen[key] = []
                    seen[key].append(u.get("serial_number", ""))
                for aname, serials in seen.items():
                    lines.append(f"- **{aname}** — Serial(s): " + ", ".join(f"`{s}`" for s in serials))
            lines.append("\n**Employees:**")
            emp_only = [u for u in users if (u.get("role") or "").lower() == "employee"]
            show_users = emp_only if emp_only else users[:10]
            for u in show_users:
                lines.append(f"- **{u['name']}**")
            lines.append('\n*Example: "Assign Laptop AST-B04B85-U001 to Ayeza"*')
            return {"message": "\n".join(lines), "intent": "GENERAL", "action": None}

        # ── Step 4: Asset found but employee missing ──────────────────────
        if matched_unit and not target_user:
            emp_only = [u for u in users if (u.get("role") or "").lower() == "employee"]
            show_users = emp_only if emp_only else users[:10]
            lines = [f"Got it — **{matched_unit['asset_name']}** (Serial: `{matched_unit['serial_number']}`) is available.\n",
                     "Now please tell me **which employee** to assign it to:\n"]
            for u in show_users:
                dept = f" — {u['department']}" if u.get("department") else ""
                lines.append(f"- **{u['name']}**{dept}")
            return {"message": "\n".join(lines), "intent": "GENERAL", "action": None}

        # ── Step 5: Employee found but asset missing ──────────────────────
        if not matched_unit and target_user:
            lines = [f"Got it — assigning to **{target_user['name']}**.\n",
                     "Please tell me **which asset** to assign (name or serial number):\n"]
            seen = {}
            for u in avail[:15]:
                key = u.get("asset_name", "")
                if key not in seen:
                    seen[key] = []
                seen[key].append(u.get("serial_number", ""))
            for aname, serials in seen.items():
                lines.append(f"- **{aname}** — Serial(s): " + ", ".join(f"`{s}`" for s in serials))
            return {"message": "\n".join(lines), "intent": "GENERAL", "action": None}

        # ── Step 6: Both found — propose action ───────────────────────────
        return {
            "message": (
                f"Please confirm this assignment:\n\n"
                f"- **Asset**: {matched_unit['asset_name']}\n"
                f"- **Serial Number**: `{matched_unit['serial_number']}`\n"
                f"- **Assign to**: {target_user['name']}\n"
                f"- **Status**: Available"
            ),
            "intent": "ACTION_PROPOSAL",
            "action": {
                "type": "ASSIGN_ASSET",
                "params": {
                    "unit_id":       matched_unit["id"],
                    "serial_number": matched_unit["serial_number"],
                    "asset_name":    matched_unit["asset_name"],
                    "user_id":       target_user["id"],
                    "employee_name": target_user["name"],
                },
                "summary": f"Assign {matched_unit['asset_name']} ({matched_unit['serial_number']}) to {target_user['name']}",
                "requires_confirmation": True
            }
        }

    # 4.5 Action: Scrap Asset
    if "scrap" in msg_lower or "dispose" in msg_lower or "condemn" in msg_lower:
        units = db_context.get("physical_units", [])
        eligible = [u for u in units if u.get("status") != "SCRAPPED"]

        matched_unit = None
        for u in eligible:
            sn = u.get("serial_number", "").strip().lower()
            if sn and sn in msg_lower:
                matched_unit = u
                break

        name_matches = []
        if not matched_unit:
            sorted_units = sorted(eligible, key=lambda x: len(x.get("asset_name", "")), reverse=True)
            for u in sorted_units:
                aname = u.get("asset_name", "").strip().lower()
                if aname and re.search(r'\b' + re.escape(aname) + r'\b', msg_lower):
                    name_matches.append(u)

            if len(name_matches) == 1:
                matched_unit = name_matches[0]
            elif len(name_matches) > 1:
                lines = [f"There are **{len(name_matches)} units** matching that asset name. Please specify the serial number of the one you want to scrap:\n"]
                for u in name_matches:
                    lines.append(f"- **{u['asset_name']}** (Serial: `{u['serial_number']}`) - Status: {u['status']}")
                return {
                    "message": "\n".join(lines),
                    "intent": "QUERY",
                    "action": None
                }

        if not matched_unit:
            return {
                "message": "I couldn't find a unit matching that description. Please specify the exact asset name or serial number (e.g. *\"Scrap unit AST-BA9D28-U001\"*).",
                "intent": "GENERAL",
                "action": None
            }

        return {
            "message": f"Please confirm scrapping this physical unit:\n\n- **Asset**: {matched_unit['asset_name']}\n- **Serial Number**: `{matched_unit['serial_number']}`\n- **Current Status**: {matched_unit['status']}",
            "intent": "ACTION_PROPOSAL",
            "action": {
                "type": "SCRAP_ASSET",
                "params": {
                    "unit_id": matched_unit["id"],
                    "asset_name": matched_unit["asset_name"],
                    "serial_number": matched_unit["serial_number"],
                },
                "summary": f"Scrap {matched_unit['asset_name']} ({matched_unit['serial_number']})",
                "requires_confirmation": True
            }
        }

    # 5. Action: Create/Add Asset
    if "add" in msg_lower or "create" in msg_lower:
        asset_name, category_name, cat_dict, brand, model = _extract_add_asset_details(message, db_context.get("categories", []))

        # ── No details at all — return empty ADD_ASSET form immediately ──────
        # User said "add asset" / "asset add karo" without providing name/category/brand/model
        # Frontend action-card will render the interactive form with validation.
        if not asset_name and not category_name and not brand and not model:
            db_categories = db_context.get("categories", [])
            cat_hint = ""
            if db_categories:
                sample = ", ".join(c["name"] for c in db_categories[:5])
                cat_hint = f"\n\nAvailable categories: {sample}{'...' if len(db_categories) > 5 else ''}"

            return {
                "message": (
                    "Sure! Please fill in the asset details in the form below.\n\n"
                    "**Required:** Asset Name, Category, Brand, Model\n"
                    "**Optional:** Color" + cat_hint
                ),
                "intent": "ACTION_PROPOSAL",
                "action": {
                    "type": "ADD_ASSET",
                    "params": {
                        "name":          "",
                        "category_id":   None,
                        "category_name": "",
                        "brand":         "",
                        "model":         "",
                        "color":         "",
                    },
                    "summary": "Add New Asset to Catalogue",
                    "requires_confirmation": True
                }
            }

        # ── Name provided but category missing → ask for category ────────────
        if asset_name and not category_name:
            db_categories = db_context.get("categories", [])
            if db_categories:
                cat_list = "\n".join([f"- **{c['name']}**" for c in db_categories[:15]])
                return {
                    "message": (
                        f"I need a bit more information before adding **{asset_name}**.\n\n"
                        f"Please tell me which **category** this asset belongs to.\n\n"
                        f"Available categories in the system:\n{cat_list}\n\n"
                        f"You can also specify a new category name and I will create it automatically.\n\n"
                        f"*Example: \"Add {asset_name} in category Electronics\"*"
                    ),
                    "intent": "GENERAL",
                    "action": None
                }
            else:
                return {
                    "message": (
                        f"Please tell me which **category** **{asset_name}** belongs to "
                        f"(e.g. *\"Add {asset_name} in category Electronics\"*)."
                    ),
                    "intent": "GENERAL",
                    "action": None
                }

        # ── All or partial details provided — return ADD_ASSET form pre-filled ─
        cat_display_name = category_name.strip() if category_name else ""
        cat_id = cat_dict["id"] if cat_dict else None

        return {
            "message": (
                f"Please review the asset details below. "
                f"Fill in any missing **required** fields, then confirm to create the asset."
            ),
            "intent": "ACTION_PROPOSAL",
            "action": {
                "type": "ADD_ASSET",
                "params": {
                    "name":          asset_name,
                    "category_id":   cat_id,
                    "category_name": cat_display_name,
                    "brand":         brand,
                    "model":         model,
                    "color":         "",
                },
                "summary": f"Add Asset '{asset_name}'" + (f" under '{cat_display_name}'" if cat_display_name else ""),
                "requires_confirmation": True
            }
        }

    # ── Safety net: employee queries with typos that slipped past deterministic ──
    _norm = message.lower()
    _norm = re.sub(r'\bemployess\b', 'employees', _norm)
    _norm = re.sub(r'\bemployese\b', 'employees', _norm)
    _norm = re.sub(r'\bemploye\b',   'employee',  _norm)
    _norm = re.sub(r'\bemplyee\b',   'employee',  _norm)
    _norm = re.sub(r'\bkitnia\b',    'kitne',     _norm)
    _norm = re.sub(r'\bkitna\b',     'kitne',     _norm)
    _norm = re.sub(r'\bkitnay\b',    'kitne',     _norm)
    if any(k in _norm for k in ["employee", "employees", "staff", "workers",
                                  "kitne employees", "total employees"]):
        emp_result = _deterministic_employee_count_query(message, db_context)
        if emp_result:
            return emp_result
        # If function still returned None, build direct response
        employees_only = db_context.get("employees_only", [])
        all_users      = db_context.get("employees", [])
        summary        = db_context.get("inventory_summary", {})
        total_emp      = summary.get("total_employees", len(employees_only))
        total_all      = summary.get("total_active_users", len(all_users))
        total_mgr      = summary.get("total_managers_admins", 0)
        total_tech     = summary.get("total_technicians", 0)
        lines = [
            f"There are **{total_emp} employee(s)** registered in the system.\n",
            f"*(Other roles: {total_mgr} manager/admin(s), {total_tech} technician(s) — {total_all} total active users)*"
        ]
        if employees_only:
            lines.append("\n**Employee list:**")
            for u in employees_only:
                dept = f" | Dept: {u['department']}" if u.get("department") else ""
                lines.append(f"- **{u['name']}** ({u['email']}){dept}")
        elif all_users:
            lines.append(f"\n*No users with role 'employee' found. Showing all {total_all} active users:*")
            for u in all_users[:10]:
                role_label = (u.get("role") or "").replace("_", " ").title()
                lines.append(f"- **{u['name']}** ({u['email']}) — {role_label}")
        return {
            "message": "\n".join(lines),
            "intent": "QUERY",
            "action": None
        }

    # Default fallback message
    return {
        "message": "Hello! I am **Quorum AI**, your intelligent Enterprise Asset Management Assistant.\n\nAsk me about your assets, physical units, assignments, maintenance tickets, purchases, and requests, or ask me to perform actions using natural language.\n\nHow can I help you today?",
        "intent": "GENERAL",
        "action": None
    }


# ---------------------------------------------------------------------------
# Public Chat Processing Function
# ---------------------------------------------------------------------------

def _deterministic_purchases_query(message: str, db_context: dict):
    """
    Answers purchase QUERY questions from real DB — counts, list, summary.
    Does NOT handle CREATE/ACTION commands — those go to _fallback_smart_assistant.

    Triggers ONLY on explicit info/query phrases like:
      "kitne purchase hain", "purchase list", "total purchases", "PO count", etc.
    Skips on ACTION commands:
      "purchase the X", "purchase karo", "buy X", "create purchase", etc.
    """
    msg_lower = message.lower()

    # ── Must contain a purchase-info keyword (narrow list) ────────────────
    info_keywords = [
        "kitne purchase", "purchase list", "total purchase", "purchase summary",
        "purchase order list", "po list", "po count", "purchased assets",
        "purchase mein kitne", "purchase ka total", "purchases dikhao",
        "show purchases", "list purchases", "procurement summary",
        "kitne po", "total po", "kharida hua",
    ]
    if not any(k in msg_lower for k in info_keywords):
        return None

    # ── Bail out on any action-intent signal ─────────────────────────────
    action_signals = [
        r'\bpurchase\s+the\b',
        r'\bpurchase\s+[a-z](?!s\b)',   # "purchase laptop" but not "purchases"
        r'\bbuy\s+\w',
        r'\bkhareed(o|na|en|ain|ay|ey)?\b',
        r'\bcreate\s+(a\s+)?purchase\b',
        r'\badd\s+(a\s+)?purchase\b',
        r'\bnew\s+purchase\b',
        r'\bplace\s+(an?\s+)?order\b',
    ]
    for pattern in action_signals:
        if re.search(pattern, msg_lower):
            return None

    # ── Return real purchase summary ──────────────────────────────────────
    summary     = db_context.get("inventory_summary", {})
    total_pos   = summary.get("total_purchases", 0)
    completed   = summary.get("completed_purchases", 0)
    pending     = summary.get("pending_purchases", 0)
    total_units = summary.get("total_units_purchased", 0)

    purchases_list = db_context.get("purchases", [])

    lines = [
        "Here is the real-time **Purchases** summary from the database:\n",
        f"- **Total Purchase Orders (POs)**: {total_pos}",
        f"- **Completed POs**: {completed}",
        f"- **Pending POs**: {pending}",
        f"- **Total Units Purchased** (from completed POs): {total_units}",
    ]

    list_keywords = ["list", "show", "detail", "batao", "dikhao", "recent", "latest"]
    if any(k in msg_lower for k in list_keywords) and purchases_list:
        lines.append(f"\n**Recent Purchase Orders** (last {min(len(purchases_list), 10)}):")
        for p in purchases_list[:10]:
            lines.append(
                f"- `{p['purchase_number']}` | **{p['asset_name']}** | "
                f"Qty: {p['quantity']} | "
                f"Rs. {p['total_amount']:,.0f} | "
                f"Supplier: {p['supplier']} | "
                f"Status: {p['status']} | "
                f"Date: {p['purchase_date']}"
            )

    return {
        "message": "\n".join(lines),
        "intent": "QUERY",
        "action": None
    }


def _deterministic_asset_availability_query(message: str, db_context: dict):
    """
    Answers specific brand/asset availability count queries directly from
    real physical_units data — ALWAYS filters by status == AVAILABLE.
    Bypasses LLM entirely so counts are never wrong.

    Triggers on: "Dell available", "kitne Dell", "how many HP laptops available", etc.
    """
    msg_lower = message.lower()

    # Only handle availability/count queries — not action commands
    action_keywords = ["add", "create", "assign", "return", "scrap", "purchase", "buy",
                       "banao", "bana do", "khareed"]
    if any(k in msg_lower for k in action_keywords):
        return None

    availability_keywords = ["available", "kitne", "kitnay", "how many", "count",
                              "show", "list", "kitni", "kya", "batao", "bata"]
    if not any(k in msg_lower for k in availability_keywords):
        return None

    units_list = db_context.get("physical_units", [])
    assets_list = db_context.get("assets", [])
    if not units_list and not assets_list:
        return None

    # Try to match a specific asset name from catalogue (longest match first)
    matched_asset_name = None
    sorted_assets = sorted(assets_list, key=lambda x: len(x.get("name", "")), reverse=True)
    for a in sorted_assets:
        aname = a.get("name", "").strip().lower()
        if aname and len(aname) > 2 and re.search(r'\b' + re.escape(aname) + r'\b', msg_lower):
            matched_asset_name = a.get("name", "")
            break

    # Fallback: common brand keywords
    brand_keywords = ["dell", "hp", "lenovo", "apple", "samsung", "canon", "epson",
                      "cisco", "logitech", "sony", "acer", "asus", "toshiba", "huawei"]
    detected_brand = None
    if not matched_asset_name:
        detected_brand = next(
            (b for b in brand_keywords if re.search(r'\b' + b + r'\b', msg_lower)), None
        )

    filter_term = matched_asset_name.lower() if matched_asset_name else detected_brand
    if not filter_term:
        return None

    # Filter physical units by asset name containing the filter term
    all_matching    = [u for u in units_list if filter_term in u.get("asset_name", "").lower()]
    if not all_matching:
        return None  # let fallback/LLM handle it — may be a general query

    available_units = [u for u in all_matching if u.get("status", "").upper() == "AVAILABLE"]
    assigned_units  = [u for u in all_matching if u.get("status", "").upper() == "ASSIGNED"]
    maint_units     = [u for u in all_matching if u.get("status", "").upper() == "MAINTENANCE"]
    scrapped_units  = [u for u in all_matching if u.get("status", "").upper() == "SCRAPPED"]

    display_name = matched_asset_name or detected_brand.capitalize()

    lines = [f"Here is the real-time availability for **{display_name}** units:\n"]
    lines.append(f"- **Available** (ready to assign): **{len(available_units)}**")
    lines.append(f"- **Assigned** (in use): {len(assigned_units)}")
    lines.append(f"- **In Maintenance**: {len(maint_units)}")
    lines.append(f"- **Scrapped**: {len(scrapped_units)}")
    lines.append(f"- **Total Physical Units**: {len(all_matching)}")

    if available_units:
        lines.append(f"\n**Available {display_name} units (ready for assignment):**")
        for u in available_units[:10]:
            loc = f" | Location: {u['location']}" if u.get("location") else ""
            lines.append(f"- Serial: `{u['serial_number']}`{loc}")
    else:
        lines.append(f"\n*No **{display_name}** units are currently available for assignment.*")

    return {
        "message": "\n".join(lines),
        "intent": "QUERY",
        "action": None
    }


def _deterministic_employee_name_search(message: str, db_context: dict):
    """
    Handles specific name-search queries:
      "is there any employee named Khan?"
      "kya Khan naam ka employee hai?"
      "find employee Ali"
      "employee named Ayeza available?"
    Returns single match detail or clear 'not found' — never dumps the full list.
    """
    msg_lower = message.lower()

    # ── Must look like a name-search query ───────────────────────────────
    name_search_patterns = [
        r'\bnamed?\s+(\w+)',                        # "named Khan", "name Khan"
        r'\bcalled\s+(\w+)',                        # "called Ali"
        r'\bemployee\s+(\w+)\s+(?:available|exist|there|hai|hy|hain|mile)',
        r'\bfind\s+(?:employee\s+)?(\w+)',          # "find Khan", "find employee Ali"
        r'\bsearch\s+(?:employee\s+)?(\w+)',        # "search employee Ali"
        r'\bkya\s+(\w+)\s+(?:naam|name)',           # "kya Khan naam ka"
        r'\b(\w+)\s+naam\s+ka\s+(?:koi\s+)?employee',  # "Khan naam ka employee"
        r'\bany\s+(?:employee\s+)?(?:named?|called)\s+(\w+)',  # "any employee named Khan"
        r'\bis\s+(?:there\s+)?(?:any\s+)?(?:employee\s+)?(?:named?|called)\s+(\w+)',
    ]

    target_name = None
    for pattern in name_search_patterns:
        m = re.search(pattern, msg_lower)
        if m:
            candidate = m.group(1).strip()
            # Skip generic words that are not actual names
            skip_words = {
                "employee", "employees", "staff", "worker", "user", "any", "the",
                "a", "an", "is", "are", "there", "available", "hai", "hain",
                "kya", "named", "name", "called", "find", "search", "show",
                "list", "all", "some", "this", "that",
            }
            if candidate and candidate not in skip_words and len(candidate) >= 2:
                target_name = candidate
                break

    if not target_name:
        return None

    # ── Search in all_users (all roles) ──────────────────────────────────
    all_users = db_context.get("employees", [])
    if not all_users:
        return None

    matches = [
        u for u in all_users
        if target_name in u.get("name", "").lower()
        or target_name in u.get("email", "").lower()
        or target_name in (u.get("employee_id") or "").lower()
    ]

    if not matches:
        return {
            "message": (
                f"No, there is no employee named **\"{target_name.capitalize()}\"** "
                f"in the system."
            ),
            "intent": "QUERY",
            "action": None,
        }

    if len(matches) == 1:
        u = matches[0]
        role_label = (u.get("role") or "").replace("_", " ").title()
        dept  = f"\n- **Department**: {u['department']}" if u.get("department") else ""
        empid = f"\n- **Employee ID**: {u['employee_id']}" if u.get("employee_id") else ""
        title = f"\n- **Job Title**: {u['job_title']}" if u.get("job_title") else ""
        return {
            "message": (
                f"Yes, **{u['name']}** is in the system.\n"
                f"- **Email**: {u['email']}\n"
                f"- **Role**: {role_label}"
                f"{dept}{empid}{title}"
            ),
            "intent": "QUERY",
            "action": None,
        }

    # Multiple matches
    lines = [f"Found **{len(matches)} user(s)** matching **\"{target_name.capitalize()}\"**:\n"]
    for u in matches:
        role_label = (u.get("role") or "").replace("_", " ").title()
        dept = f" | Dept: {u['department']}" if u.get("department") else ""
        lines.append(f"- **{u['name']}** ({u['email']}) — {role_label}{dept}")
    return {
        "message": "\n".join(lines),
        "intent": "QUERY",
        "action": None,
    }


def _deterministic_employee_count_query(message: str, db_context: dict):
    """
    Answers employee/user count and list queries directly from real DB data.
    Bypasses LLM so counts are always exact.

    Triggers on: "how many employees", "list employees", "show employees",
    "kitne employees", "employees batao", "total staff", etc.
    Also handles common typos: "employess", "employe", "emplyee", "kitnia", "kitna", etc.
    """
    msg_lower = message.lower()

    # ── Typo-tolerant matching ────────────────────────────────────────────
    # Normalize common typos before keyword check
    normalized = msg_lower
    # employee typos
    normalized = re.sub(r'\bemployess\b', 'employees', normalized)
    normalized = re.sub(r'\bemployese\b', 'employees', normalized)
    normalized = re.sub(r'\bemploye\b',   'employee',  normalized)
    normalized = re.sub(r'\bemplyee\b',   'employee',  normalized)
    normalized = re.sub(r'\bempoyee\b',   'employee',  normalized)
    normalized = re.sub(r'\bemploy\b',    'employee',  normalized)
    # kitne typos
    normalized = re.sub(r'\bkitnia\b',  'kitne', normalized)
    normalized = re.sub(r'\bkitna\b',   'kitne', normalized)
    normalized = re.sub(r'\bkitnay\b',  'kitne', normalized)
    normalized = re.sub(r'\bkitni\b',   'kitne', normalized)
    normalized = re.sub(r'\bkitnai\b',  'kitne', normalized)
    # "hia" / "hai" / "hn" — ignore, just presence of employee word is enough

    employee_keywords = [
        "employee", "employees", "staff", "workers",
        "kitne log", "kitne employees", "total employees",
        "employees batao", "list employees", "show employees",
        "how many people", "kaun kaun", "team members",
        "total users", "all users", "list users", "show users",
        "how many users", "kitne users",
        "how many employees", "kitne staff",
        "total staff", "team kitne", "log kitne",
    ]

    if not any(k in normalized for k in employee_keywords):
        return None

    # Skip if it's an assignment-specific query (handled elsewhere)
    assignment_keywords = ["assign", "return", "assets of", "ke assets", "k assets",
                           "has assets", "wala", "wali"]
    if any(k in normalized for k in assignment_keywords):
        return None

    summary = db_context.get("inventory_summary", {})
    total_employees = summary.get("total_employees", 0)
    total_managers  = summary.get("total_managers_admins", 0)
    total_techs     = summary.get("total_technicians", 0)
    total_all       = summary.get("total_active_users", 0)

    employees_only = db_context.get("employees_only", [])
    all_users      = db_context.get("employees", [])

    # Decide which list to show — if user specifically asked "employees" show employees_only
    show_all = any(k in normalized for k in ["all users", "all staff", "all people",
                                              "sab log", "poori team", "total users",
                                              "total staff", "managers", "admins",
                                              "technicians"])

    if show_all:
        display_list = all_users
        heading = f"There are **{total_all} active users** in the system across all roles:"
        lines = [heading + "\n"]
        role_groups: dict = {}
        for u in display_list:
            r = (u.get("role") or "unknown").replace("_", " ").title()
            role_groups.setdefault(r, []).append(u)
        for role_label, members in sorted(role_groups.items()):
            lines.append(f"**{role_label}** ({len(members)}):")
            for u in members:
                dept = f" — {u['department']}" if u.get("department") else ""
                lines.append(f"  - {u['name']} ({u['email']}){dept}")
    else:
        # Default: show employees (role == 'employee')
        heading = (
            f"There are **{total_employees} employee(s)** registered in the system.\n\n"
            f"*(Other roles: {total_managers} manager/admin(s), {total_techs} technician(s) — "
            f"{total_all} total active users)*"
        )
        lines = [heading]

        if employees_only:
            lines.append("\n**Employee list:**")
            for u in employees_only:
                dept  = f" | Dept: {u['department']}" if u.get("department") else ""
                empid = f" | ID: {u['employee_id']}" if u.get("employee_id") else ""
                title = f" | Title: {u['job_title']}" if u.get("job_title") else ""
                lines.append(f"- **{u['name']}** ({u['email']}){dept}{empid}{title}")
        else:
            lines.append("\n*No employees with role 'employee' found. "
                         "There may be users with other roles (admin/manager/technician).*")

    return {
        "message": "\n".join(lines),
        "intent": "QUERY",
        "action": None
    }


def _deterministic_employee_asset_query(message: str, db_context: dict):
    """
    Answers 'how many/which assets does X have' queries directly from real
    physical_units data, bypassing the LLM entirely so counts are always
    exact (never invented or miscounted by the model).
    """
    msg_lower = message.lower()
    if "asset" not in msg_lower:
        return None

    employees = db_context.get("employees", [])
    matched_emp = None
    for e in employees:
        name_parts = [p for p in e["name"].lower().split() if len(p) > 2]
        for part in name_parts:
            if re.search(r'\b' + re.escape(part) + r'\b', msg_lower):
                matched_emp = e
                break
        if matched_emp:
            break

    if not matched_emp:
        return None

    units = db_context.get("physical_units", [])
    assigned = [
        u for u in units
        if u.get("assigned_to_name")
        and u["assigned_to_name"].strip().lower() == matched_emp["name"].strip().lower()
        and u.get("status") == "ASSIGNED"
    ]

    if not assigned:
        return {
            "message": f"**{matched_emp['name']}** currently has **0 assets** assigned.",
            "intent": "QUERY",
            "action": None
        }

    lines = [f"**{matched_emp['name']}** currently has **{len(assigned)} asset(s)** assigned:\n"]
    for u in assigned:
        lines.append(f"- **{u['asset_name']}**, Serial Number: `{u['serial_number']}`, Status: {u['status']}")

    return {
        "message": "\n".join(lines),
        "intent": "QUERY",
        "action": None
    }


def _deterministic_maintenance_query(message: str, db_context: dict):
    """
    Answers maintenance-ticket related questions directly from the real
    maintenance_tickets data, bypassing the LLM so counts/lists are always
    exact (never invented or miscounted by the model).
    """
    msg_lower = message.lower()
    maintenance_keywords = ["maintenance", "repair", "kharab", "under maintenance", "in maintenance", "servicing", "ticket", "work order"]
    create_keywords = ["create", "report", "add", "raise", "log", "banao", "bana do"]

    if not any(k in msg_lower for k in maintenance_keywords):
        return None
    if any(k in msg_lower for k in create_keywords):
        return None

    tickets = db_context.get("maintenance_tickets", [])
    active_statuses = {"PENDING", "TODO", "IN_PROGRESS", "REVIEW"}

    active_trigger_words = ["currently", "under maintenance", "active", "pending", "in progress",
                             "kitne", "kitnay", "kitni", "kitna", "kitnai", "how many"]
    if any(w in msg_lower for w in active_trigger_words):
        filtered_tickets = [t for t in tickets if t.get("status") in active_statuses]
    else:
        filtered_tickets = tickets

    if not filtered_tickets:
        return {
            "message": "Currently, there are **0 assets under active maintenance** in the system.",
            "intent": "QUERY",
            "action": None
        }

    lines = [f"Currently, there are **{len(filtered_tickets)} asset(s) under maintenance** in the system:\n"]
    for t in filtered_tickets[:15]:
        sn = t.get('serial_number') or 'N/A'
        req_id = t.get('request_id') or 'N/A'
        status = t.get('status') or 'N/A'
        priority = t.get('priority') or 'N/A'
        created_date = t.get('created_at') or 'N/A'
        lines.append(f"- **{t.get('asset_name', 'Asset')}** (SN: `{sn}`) | Ticket: `{req_id}` | Status: **{status}** | Priority: **{priority}** | Date: {created_date}")

    return {
        "message": "\n".join(lines),
        "intent": "QUERY",
        "action": None
    }


def process_ai_chat(user, message: str, conversation_history: list = None) -> dict:
    if conversation_history is None:
        conversation_history = []

    db_context = _build_authorized_db_context(user)

    # Deterministic, always-accurate answers — bypass the LLM entirely so
    # counts/lists are never invented or miscounted by the model.

    # 0. Specific employee name search — MUST run before generic count query
    deterministic_emp_search = _deterministic_employee_name_search(message, db_context)
    if deterministic_emp_search:
        return deterministic_emp_search

    # 1. Employee count/list queries (most specific — run first)
    deterministic_emp_count = _deterministic_employee_count_query(message, db_context)
    if deterministic_emp_count:
        return deterministic_emp_count

    # 2. Employee asset assignment queries
    deterministic = _deterministic_employee_asset_query(message, db_context)
    if deterministic:
        return deterministic

    # 3. Maintenance queries
    deterministic_maint = _deterministic_maintenance_query(message, db_context)
    if deterministic_maint:
        return deterministic_maint

    # 4. Purchase queries
    deterministic_purchases = _deterministic_purchases_query(message, db_context)
    if deterministic_purchases:
        return deterministic_purchases

    # 5. Brand/asset availability count — always filter by AVAILABLE status
    deterministic_avail = _deterministic_asset_availability_query(message, db_context)
    if deterministic_avail:
        return deterministic_avail

    openrouter_key = (getattr(settings, "OPENROUTER_API_KEY", "") or getattr(settings, "GROQ_API_KEY", "")).strip()
    if openrouter_key:
        try:
            res = _call_openrouter_assistant(message, conversation_history, db_context, openrouter_key)
            if isinstance(res, dict) and "message" in res and res.get("intent") in ("QUERY", "ACTION_PROPOSAL", "GENERAL"):
                return _normalize_add_asset_params(res)
        except Exception as exc:
            logger.error("OpenRouter AI Assistant call failed: %s", exc)

    groq_key = getattr(settings, "GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            res = _call_groq_assistant(message, conversation_history, db_context, groq_key)
            if isinstance(res, dict) and "message" in res and res.get("intent") in ("QUERY", "ACTION_PROPOSAL", "GENERAL"):
                return _normalize_add_asset_params(res)
        except Exception as exc:
            logger.error("Groq AI Assistant call failed: %s", exc)
    logger.info("Using smart fallback AI engine with real DB context.")
    return _normalize_add_asset_params(_fallback_smart_assistant(user, message, db_context))


def _normalize_add_asset_params(res: dict) -> dict:
    """
    Normalize ADD_ASSET action params from LLM — handles camelCase vs snake_case
    and extracts category/brand/model from the message text if params are empty.
    """
    if not isinstance(res, dict):
        return res
    action = res.get("action")
    if not action or action.get("type") != "ADD_ASSET":
        return res

    params = action.get("params") or {}

    # Normalize camelCase → snake_case
    if not params.get("category_name") and params.get("categoryName"):
        params["category_name"] = params["categoryName"]
    if not params.get("category_id") and params.get("categoryId"):
        params["category_id"] = params["categoryId"]
    if not params.get("name") and params.get("assetName"):
        params["name"] = params["assetName"]

    # If category_name still empty, try to extract from the message text
    if not params.get("category_name"):
        msg_text = res.get("message", "")
        # Pattern: "Category: Electronics" or "category **Electronics**"
        cat_match = re.search(
            r'[Cc]ategory[:\s*]+\**([A-Za-z0-9_\- ]+?)\**(?:\n|\.|\,|\s{2}|$)',
            msg_text
        )
        if cat_match:
            extracted = cat_match.group(1).strip().rstrip('*').strip()
            if extracted and extracted.lower() not in ("name", "brand", "model", "color", "n/a", "none", "unknown"):
                params["category_name"] = extracted

    action["params"] = params
    res["action"] = action
    return res


# ---------------------------------------------------------------------------
# Public Action Execution Function
# ---------------------------------------------------------------------------

def execute_ai_action(user, action_type: str, params: dict) -> dict:
    """
    Executes an action proposed by AI after explicit user confirmation.
    Checks permissions and calls exact Django services.
    """
    action_type = (action_type or "").upper()

    user_role = (user.role or "").lower()
    is_admin_or_mgr = user.is_superuser or user_role in ["system_admin", "operations_manager", "admin", "manager"]

    if not is_admin_or_mgr and action_type not in ["CREATE_MAINTENANCE", "REQUEST_ASSET"]:
        return {
            "success": False,
            "message": f"Permission Denied: Your role ({user.role}) is not authorized to execute '{action_type}'.",
            "data": None
        }

    try:
        with transaction.atomic():
            if action_type == "ADD_ASSET":
                asset_name = (params.get("name") or params.get("asset_name") or "").strip()
                if not asset_name or asset_name.lower() in ["asset", "an asset", "new asset"]:
                    return {
                        "success": False,
                        "message": "Asset Name is required to create an asset.",
                        "data": None
                    }

                cat_id = params.get("category_id")
                cat_name = (params.get("category_name") or params.get("categoryName") or params.get("category") or "").strip()

                category_obj = None
                if cat_id:
                    category_obj = AssetCategory.objects.filter(pk=cat_id).first()
                if not category_obj and cat_name:
                    category_obj = AssetCategory.objects.filter(name__iexact=cat_name).first()
                
                # Search DB case-insensitively. If missing, CREATE the category in database
                if not category_obj and cat_name:
                    try:
                        category_obj, _ = AssetCategory.objects.get_or_create(
                            name__iexact=cat_name,
                            defaults={"name": cat_name}
                        )
                    except Exception as e:
                        logger.error(f"Failed to create category '{cat_name}': {e}")
                        return {
                            "success": False,
                            "message": f"Failed to resolve or create category '{cat_name}': {str(e)}",
                            "data": None
                        }

                if not category_obj:
                    if cat_name:
                        return {
                            "success": False,
                            "message": f"Unable to assign category '{cat_name}'. Asset creation aborted.",
                            "data": None
                        }
                    category_obj, _ = AssetCategory.objects.get_or_create(
                        name__iexact="Uncategorized",
                        defaults={"name": "Uncategorized"}
                    )

                # PASS REAL AssetCategory MODEL INSTANCE (not UUID string!)
                asset_data = {
                    "name": asset_name,
                    "category": category_obj,
                    "brand": params.get("brand", "").strip(),
                    "model": params.get("model", "").strip(),
                    "color": params.get("color", "").strip(),
                }

                asset = AssetService.create_asset(asset_data, request=None)
                return {
                    "success": True,
                    "message": f"✓ Asset definition created successfully in Catalogue.\n\n- **Asset ID**: `{asset.formatted_asset_id}`\n- **Asset Name**: {asset.name}\n- **Category**: {category_obj.name}",
                    "data": {
                        "asset_id": str(asset.id),
                        "formatted_id": asset.formatted_asset_id,
                        "name": asset.name,
                        "category": category_obj.name,
                        "status": "Created"
                    }
                }

            elif action_type == "CREATE_PURCHASE":
                asset_id = params.get("asset_id") or params.get("assetId")
                supplier_id = params.get("supplier_id") or params.get("supplierId")
                asset_name = params.get("asset_name") or params.get("assetName")
                supplier_name = params.get("supplier_name") or params.get("supplierName")
                quantity = int(params.get("quantity") or params.get("qty") or 1)
                unit_price = Decimal(str(params.get("unit_price") or params.get("unitPrice") or 0))

                asset_obj = None
                if asset_id:
                    asset_obj = Asset.objects.filter(pk=asset_id).first()
                if not asset_obj and asset_name:
                    asset_obj = Asset.objects.filter(name__icontains=asset_name).first()

                if not asset_obj:
                    return {
                        "success": False,
                        "message": "Asset definition not found in catalogue.",
                        "data": None
                    }

                supplier_obj = None
                if supplier_id:
                    supplier_obj = Supplier.objects.filter(pk=supplier_id).first()
                if not supplier_obj and supplier_name:
                    supplier_obj = Supplier.objects.filter(company__icontains=supplier_name).first()

                if not supplier_obj:
                    return {
                        "success": False,
                        "message": "Supplier not found in system.",
                        "data": None
                    }

                if quantity <= 0 or unit_price <= Decimal('0.00'):
                    return {
                        "success": False,
                        "message": "Invalid quantity or unit price for purchase.",
                        "data": None
                    }

                purchase_data = {
                    'asset': asset_obj,
                    'supplier': supplier_obj,
                    'quantity': quantity,
                    'purchase_price': unit_price,
                    'purchase_date': date.today(),
                    'status': Purchase.Status.COMPLETED,
                    'notes': f"Purchased via AI Assistant by {user.email}"
                }

                purchase = PurchaseService.create_purchase(purchase_data, request=None)

                if asset_obj.purchase_cost == Decimal('0.00'):
                    asset_obj.purchase_cost = unit_price
                    asset_obj.current_value = unit_price
                    asset_obj.save()

                return {
                    "success": True,
                    "message": f"Purchase **{purchase.purchase_number}** created successfully!\n\n- **Asset**: {asset_obj.name}\n- **Quantity**: {purchase.quantity} units\n- **Unit Price**: Rs. {purchase.purchase_price:,.2f}\n- **Total Amount**: Rs. {purchase.total_amount:,.2f}\n- **Supplier**: {supplier_obj.company}\n- **Payment Status**: {purchase.payment_status}\n- **Purchase Date**: {purchase.purchase_date}",
                    "data": {
                        "purchase_id": str(purchase.id),
                        "purchase_number": purchase.purchase_number,
                        "asset_name": asset_obj.name,
                        "quantity": purchase.quantity,
                        "total_amount": float(purchase.total_amount),
                        "payment_status": purchase.payment_status
                    }
                }

            elif action_type == "ASSIGN_ASSET":
                unit_id = params.get("unit_id") or params.get("unitId")
                user_id = params.get("user_id") or params.get("userId")
                employee_name = params.get("employee_name") or params.get("employeeName") or ""

                if not unit_id:
                    serial = params.get("serial_number") or params.get("serialNumber")
                    if serial:
                        unit = AssetUnit.objects.filter(serial_number=serial, status=AssetUnit.Status.AVAILABLE).first()
                    else:
                        asset_name = params.get("asset_name") or params.get("assetName")
                        unit = AssetUnit.objects.filter(asset__name__icontains=asset_name, status=AssetUnit.Status.AVAILABLE).first()
                else:
                    unit = AssetUnit.objects.filter(pk=unit_id).first()

                if not unit:
                    return {
                        "success": False,
                        "message": "The selected physical unit is no longer AVAILABLE in inventory.",
                        "data": None
                    }

                target_user = None
                if user_id:
                    target_user = User.objects.filter(pk=user_id).first()
                if not target_user and employee_name:
                    target_user = User.objects.filter(first_name__icontains=employee_name.split()[0]).first()

                assigned_name = f"{target_user.first_name} {target_user.last_name}".strip() if target_user else employee_name

                updated_unit = AssetService.assign_unit(
                    unit=unit,
                    user_id=target_user.id if target_user else None,
                    employee_name=assigned_name,
                    assigned_date=date.today(),
                    notes="Assigned via AI Assistant",
                    request=None
                )

                return {
                    "success": True,
                    "message": f"✓ **{updated_unit.asset.name}** has been successfully assigned to **{assigned_name}**.\n\n- **Serial Number**: `{updated_unit.serial_number}`\n- **Status**: Assigned\n- **Assigned Date**: {date.today()}",
                    "data": {
                        "unit_id": str(updated_unit.id),
                        "asset_name": updated_unit.asset.name,
                        "serial_number": updated_unit.serial_number,
                        "assigned_to": assigned_name,
                        "status": updated_unit.status
                    }
                }

            elif action_type == "RETURN_ASSET":
                unit_id = params.get("unit_id") or params.get("unitId")
                unit = AssetUnit.objects.filter(pk=unit_id).first()
                if not unit:
                    return {"success": False, "message": "Asset unit not found.", "data": None}

                returned_unit = AssetService.return_unit(unit=unit, request=None)
                return {
                    "success": True,
                    "message": f"✓ Asset **{returned_unit.asset.name}** (SN: `{returned_unit.serial_number}`) returned to AVAILABLE stock.",
                    "data": {
                        "unit_id": str(returned_unit.id),
                        "serial_number": returned_unit.serial_number,
                        "status": returned_unit.status
                    }
                }

            elif action_type == "APPROVE_REQUEST":
                req_id = params.get("request_id") or params.get("requestId")
                req_obj = AssetRequest.objects.filter(pk=req_id).first()
                if not req_obj:
                    return {"success": False, "message": "Asset request not found.", "data": None}

                approved = AssetRequestService.approve_request(req_obj, user)
                return {
                    "success": True,
                    "message": f"✓ Request `{approved.request_number}` for **{approved.requested_asset}** has been APPROVED.",
                    "data": {"request_number": approved.request_number, "status": approved.status}
                }

            elif action_type == "REJECT_REQUEST":
                req_id = params.get("request_id") or params.get("requestId")
                reason = params.get("reason", "Rejected via AI Assistant")
                req_obj = AssetRequest.objects.filter(pk=req_id).first()
                if not req_obj:
                    return {"success": False, "message": "Asset request not found.", "data": None}

                rejected = AssetRequestService.reject_request(req_obj, reason, user)
                return {
                    "success": True,
                    "message": f"✓ Request `{rejected.request_number}` rejected. Reason: {reason}",
                    "data": {"request_number": rejected.request_number, "status": rejected.status}
                }

            elif action_type == "CREATE_MAINTENANCE":
                asset_id = params.get("asset_id") or params.get("assetId")
                unit_id = params.get("unit_id") or params.get("unitId")
                serial_number = params.get("serial_number") or params.get("serialNumber")

                unit = None
                if unit_id:
                    unit = AssetUnit.objects.filter(pk=unit_id).first()
                elif serial_number:
                    unit = AssetUnit.objects.filter(serial_number=serial_number).first()
                
                asset = unit.asset if unit else (Asset.objects.filter(pk=asset_id).first() if asset_id else None)
                if not unit and asset:
                    unit = asset.units.filter(status=AssetUnit.Status.AVAILABLE).first()

                issue_title = params.get("title") or params.get("issueTitle") or "Hardware issue reported via AI"
                issue_desc = params.get("description") or issue_title
                priority = params.get("priority", "MEDIUM")

                mnt = MaintenanceRequest.objects.create(
                    asset=asset,
                    asset_unit=unit,
                    asset_name_snapshot=asset.name if asset else (unit.asset.name if unit and unit.asset else (params.get("asset_name") or params.get("assetName") or "Hardware Unit")),
                    component_or_issue_type=issue_title,
                    issue_description=issue_desc,
                    maintenance_type=params.get("maintenance_type", "CORRECTIVE"),
                    priority=priority,
                    status=MaintenanceRequest.Status.PENDING,
                    requested_by=user,
                    requested_by_name=f"{user.first_name} {user.last_name}".strip() or user.email
                )

                if unit:
                    unit.status = AssetUnit.Status.MAINTENANCE
                    unit.save()

                return {
                    "success": True,
                    "message": f"✓ Maintenance ticket `{mnt.request_id}` created successfully for unit {unit.serial_number if unit else (asset.name if asset else 'Asset')}.\n\n- **Issue**: {mnt.component_or_issue_type}\n- **Priority**: {mnt.priority}\n- **Status**: Pending Assessment",
                    "data": {
                        "ticket_id": str(mnt.id),
                        "request_id": mnt.request_id,
                        "status": mnt.status
                    }
                }

            elif action_type == "SCRAP_ASSET":
                unit_id = params.get("unit_id") or params.get("unitId")
                unit = AssetUnit.objects.filter(pk=unit_id).first()
                if not unit:
                    return {"success": False, "message": "Asset unit not found.", "data": None}
                
                unit.status = AssetUnit.Status.SCRAPPED
                unit.save()
                return {
                    "success": True,
                    "message": f"✓ Physical Unit **{unit.asset.name}** (SN: `{unit.serial_number}`) marked as SCRAPPED.",
                    "data": {"unit_id": str(unit.id), "status": unit.status}
                }

            else:
                return {"success": False, "message": f"Unsupported action type: {action_type}", "data": None}

    except Exception as exc:
        logger.error("Error executing AI action %s: %s", action_type, exc, exc_info=True)
        return {
            "success": False,
            "message": f"Execution failed: {str(exc)}",
            "data": None
        }

def get_ai_suggestions(user=None) -> list:
    """
    Dynamically generates at least 5 contextual AI prompt recommendations
    based on real database state (assets, employees, maintenance, purchases).
    """
    suggestions = []

    try:
        # 1. Real Available Asset Models
        available_units = AssetUnit.objects.filter(status='AVAILABLE').select_related('asset')
        if available_units.exists():
            first_unit = available_units.first()
            asset_name = first_unit.asset.name
            suggestions.append(f"How many {asset_name} units are available?")
        else:
            suggestions.append("How many assets are currently available?")

        # 2. Real Employee Assignment
        assignment = AssetAssignmentHistory.objects.filter(is_active=True).select_related('assigned_to').first()
        if assignment and assignment.assigned_to:
            emp_name = assignment.assigned_to.first_name or assignment.assigned_to.username
            suggestions.append(f"Show {emp_name}'s assigned assets")
        else:
            emp_user = User.objects.filter(is_active=True, role='EMPLOYEE').first()
            if emp_user:
                emp_name = emp_user.first_name or emp_user.username
                suggestions.append(f"Show {emp_name}'s assigned assets")
            else:
                suggestions.append("Show assigned assets by employee")

        # 3. Real Pending Maintenance Tickets
        pending_maint_count = MaintenanceRequest.objects.filter(status='PENDING').count()
        if pending_maint_count > 0:
            suggestions.append(f"Show {pending_maint_count} pending maintenance tickets")
        else:
            suggestions.append("Show all active maintenance tickets")

        # 4. Action suggestion based on stock or asset
        asset_template = Asset.objects.filter(is_active=True).first()
        if asset_template and assignment and assignment.assigned_to:
            emp_name = assignment.assigned_to.first_name or assignment.assigned_to.username
            suggestions.append(f"Assign {asset_template.name} to {emp_name}")
        elif asset_template:
            suggestions.append(f"Add a new {asset_template.name}")
        else:
            suggestions.append("Add a new laptop to inventory")

        # 5. Asset Category summary
        if AssetCategory.objects.count() > 0:
            suggestions.append("What asset categories are in stock?")
        else:
            suggestions.append("Show asset breakdown by category")

        # 6. Purchase orders
        if Purchase.objects.count() > 0:
            suggestions.append("Show recent purchase orders and suppliers")

    except Exception as e:
        logger.warning("Error generating dynamic AI suggestions: %s", e)

    # Fallback defaults if less than 5 suggestions
    defaults = [
        "How many assets are available?",
        "Show pending maintenance tickets",
        "Show assigned assets by employee",
        "Add a new laptop to inventory",
        "Show asset breakdown by category"
    ]

    for d in defaults:
        if len(suggestions) >= 6:
            break
        if d not in suggestions:
            suggestions.append(d)

    return suggestions[:6]
