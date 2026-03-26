# views.py (fixed for normalized models + multi-location formset)
import json
import os
import random
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Sum, Count
from django.http import JsonResponse, HttpResponseBadRequest, FileResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods
from .models import (
    RecoveryProject,
    ProjectLocations,
    ProjectStatusIndicators,
    AreaCouncils,
)
from .forms import (
    RecoveryProjectForm,
    ProjectLocationFormSet,
    ProjectStatusIndicatorFormSet,
)
# ==================== HELPERS ====================
def parse_coord(value):
    if value is None:
        return None
    value = str(value).strip()
    if value in ["", "N/A", "n/a", "-", "None"]:
        return None
    value = value.replace(",", "").split()[0]
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
def calculate_progress(start_date, end_date):
    """Calculate project progress percentage based on time elapsed. Returns 0–100"""
    if not start_date or not end_date:
        return 0
    total_days = (end_date - start_date).days
    elapsed_days = (date.today() - start_date).days
    if total_days <= 0:
        return 100
    progress = (elapsed_days / total_days) * 100
    return max(0, min(int(progress), 100))
def calculate_status(progress_pct):
    if progress_pct >= 75:
        return "green"
    elif progress_pct >= 40:
        return "yellow"
    return "red"
def calculate_indicator_progress(project: RecoveryProject) -> int:
    """
    Calculates progress percentage from up to 5 status indicators in ProjectStatusIndicators.
    Each indicator is expected to be a numeric value (typically 0–1).
    Returns 0–100
    """
    qs = (
        ProjectStatusIndicators.objects
        .filter(project=project)
        .order_by("id") # deterministic
    )
    values = []
    for row in qs[:5]:
        try:
            values.append(float(row.status_indicator or 0))
        except (TypeError, ValueError):
            values.append(0.0)
    while len(values) < 5:
        values.append(0.0)
    avg = sum(values) / 5.0
    pct = avg * 100.0
    return max(0, min(int(pct), 100))
# ==================== PROJECT DATA ====================
def get_projects():
    """
    Dashboard uses ALL locations per project for the map.
    We still expose the first location as the summary location for the table/filter,
    but each project now includes a `locations` array.
    """
    projects = []

    loc_qs = (
        ProjectLocations.objects
        .select_related("project")
        .order_by("project_id", "id")
    )

    locations_by_project = {}
    first_location = {}

    for loc in loc_qs:
        pid = getattr(loc, "project_id", None)
        if pid is None:
            continue

        lat = parse_coord(loc.gps_latitude)
        lng = parse_coord(loc.gps_longtitude)

        locations_by_project.setdefault(pid, []).append({
            "id": loc.id,
            "province": loc.province,
            "island": loc.island,
            "area_council": loc.area_council,
            "project_site": loc.project_site,
            "lat": lat,
            "lng": lng,
        })

        if pid not in first_location:
            first_location[pid] = loc

    for p in RecoveryProject.objects.all():
        approved = p.project_total_funding_vt or Decimal("0")
        expenditure = p.project_expenditure or Decimal("0")
        remaining = approved - expenditure
        if remaining < 0:
            remaining = Decimal("0")

        spent_pct = int((expenditure / approved) * 100) if approved > 0 else 0
        spent_pct = max(0, min(spent_pct, 100))

        progress_pct = calculate_indicator_progress(p)
        status = calculate_status(progress_pct)

        loc = first_location.get(p.project_id)
        lat = parse_coord(loc.gps_latitude) if loc else None
        lng = parse_coord(loc.gps_longtitude) if loc else None

        projects.append({
            "id": p.project_id,
            "name": p.project_title,
            "ministry": p.implementing_agency,
            "gip": p.gip,
            "funder": p.funding_agency,
            "area_council": loc.area_council if loc else None,
            "disaster_type": p.type_of_disaster_operation,
            "island": loc.island if loc else None,
            "approved": int(approved),
            "expenditure": int(expenditure),
            "remaining": int(remaining),
            "spent_pct": spent_pct,
            "progress_pct": progress_pct,
            "status": status,
            "start_date": p.start_date.strftime("%d %b %Y") if p.start_date else None,
            "completion_date": p.completion_date.strftime("%d %b %Y") if p.completion_date else None,

            # keep these for backward compatibility / summary use
            "lat": lat,
            "lng": lng,

            # NEW: all project locations
            "locations": locations_by_project.get(p.project_id, []),

            "description": p.project_description,
        })

    return projects

# ==================== FUNDING SOURCES ====================
def get_funding_sources():
    qs = (
        RecoveryProject.objects
        .values("funding_agency")
        .annotate(total=Sum("project_total_funding_vt"))
        .order_by("-total")
    )
    grand_total = sum(row["total"] or 0 for row in qs) or Decimal("1")
    sources = []
    for row in qs:
        amount = row["total"] or Decimal("0")
        pct = int((amount / grand_total) * 100)
        sources.append({
            "name": row["funding_agency"] or "Unknown",
            "amount": int(amount),
            "pct": pct,
            "on": True,
        })
    return sources
def get_funding_pie():
    """Returns raw VT values (Chart.js calculates %)"""
    qs = (
        RecoveryProject.objects
        .values("funding_agency")
        .annotate(total=Sum("project_total_funding_vt"))
        .order_by("-total")
    )
    data = []
    for row in qs:
        if row["total"]:
            data.append({
                "label": row["funding_agency"] or "Unknown",
                "value": int(row["total"])
            })
    return data
# ==================== PROJECT STATUS PIE ====================
def get_status_pie():
    completed = 0
    ongoing = 0
    delayed = 0
    today = date.today()
    for p in RecoveryProject.objects.all():
        progress = calculate_progress(p.start_date, p.completion_date)
        if progress >= 100:
            completed += 1
        elif p.completion_date and today > p.completion_date:
            delayed += 1
        else:
            ongoing += 1
    return [
        {"label": "Ongoing", "value": ongoing},
        {"label": "Completed", "value": completed},
        {"label": "Delayed", "value": delayed},
    ]
# ==================== MINISTRY SUMMARY ====================
def get_ministry_summary():
    data = []
    qs = (
        RecoveryProject.objects
        .values("implementing_agency")
        .annotate(
            num_projects=Count("project_id"),
            approved=Sum("project_total_funding_vt"),
            expenditure=Sum("project_expenditure"),
        )
        .order_by("implementing_agency")
    )
    for row in qs:
        approved = row["approved"] or Decimal("0")
        expenditure = row["expenditure"] or Decimal("0")
        remaining = approved - expenditure
        if remaining < 0:
            remaining = Decimal("0")
        spent_pct = int((expenditure / approved) * 100) if approved > 0 else 0
        spent_pct = max(0, min(spent_pct, 100))
        projects = RecoveryProject.objects.filter(
            implementing_agency=row["implementing_agency"]
        )
        if projects.exists():
            avg_progress = sum(calculate_indicator_progress(p) for p in projects) / projects.count()
        else:
            avg_progress = 0
        status = calculate_status(avg_progress)
        data.append({
            "ministry": row["implementing_agency"],
            "num_projects": row["num_projects"],
            "approved": int(approved),
            "expenditure": int(expenditure),
            "remaining": int(remaining),
            "spent_pct": spent_pct,
            "avg_progress_pct": int(avg_progress),
            "status": status,
        })
    return data
# ==================== OVERALL STATS ====================
def get_recovery_budget():
    return RecoveryProject.objects.aggregate(
        total=Sum("project_total_funding_vt")
    )["total"] or Decimal("0")
def get_disbursed_budget():
    return RecoveryProject.objects.aggregate(
        total=Sum("project_expenditure")
    )["total"] or Decimal("0")
def get_sector_budget():
    qs = (
        RecoveryProject.objects
        .values("sector")
        .annotate(total=Sum("project_total_funding_vt"))
        .order_by("-total")
    )
    data = []
    for row in qs:
        if row["total"]:
            data.append({
                "label": row["sector"] or "Unspecified",
                "value": int(row["total"])
            })
    return data
# ==================== CONTEXT BUILDER ====================
def common_context():
    recovery_budget = get_recovery_budget()
    disbursed_budget = get_disbursed_budget()
    disbursed_pct = int((disbursed_budget / recovery_budget) * 100) if recovery_budget > 0 else 0
    disbursed_pct = max(0, min(disbursed_pct, 100))
    projects = get_projects()
    ministry_projects = {}
    for p in projects:
        ministry = p["ministry"]
        ministry_projects.setdefault(ministry, []).append({
            "project_title": p["name"],
            "gip": p["gip"],
            "funding_source": p["funder"],
            "progress_pct": p["progress_pct"],
            "status": p["status"],
        })
    return {
        "RECOVERY_BUDGET": int(recovery_budget),
        "DISBURSED_BUDGET": int(disbursed_budget),
        "DISBURSED_PCT": disbursed_pct,
        "RECOVERY_PROJECTS_COUNT": RecoveryProject.objects.count(),
        "FUNDING_SOURCES": get_funding_sources(),
        "PIE_ONE_JSON": mark_safe(json.dumps(get_funding_pie())),
        "PIE_TWO_JSON": mark_safe(json.dumps(get_status_pie())),
        "STATUS_PIE_JSON": mark_safe(json.dumps(get_status_pie())),
        "SECTOR_JSON": mark_safe(json.dumps(get_sector_budget())),
        "PROJECTS": projects,
        "PROJECTS_JSON": mark_safe(json.dumps(projects)),
        "MINISTRY_DATA": get_ministry_summary(),
        "MINISTRY_PROJECTS": mark_safe(json.dumps(ministry_projects)),
    }
# ==================== DASHBOARD VIEWS ====================
def overview(request):
    return render(request, "dashboard/overview.html", common_context())
def projects(request):
    return render(request, "dashboard/projects.html", common_context())
def location(request):
    return render(request, "dashboard/location.html", common_context())
def timeline(request):
    return render(request, "dashboard/timeline.html", common_context())
# ==================== AREA COUNCIL JSON ====================
@require_GET
def area_councils_json(request):
    data = list(AreaCouncils.objects.values("province", "island", "area_council"))
    return JsonResponse(data, safe=False)
# ==================== DATA ENTRY (MULTI-LOCATION + STATUS FORMSETS) ====================
from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
import random
@login_required(login_url="login")
@transaction.atomic
def create_project(request):
    """
    Creates a RecoveryProject with:
      - multiple locations (ProjectLocationFormSet) [prefix default: 'form' so your JS works]
      - multiple status indicators with description (ProjectStatusIndicatorFormSet) [prefix: 'stat']
    """
    if request.method == "POST":
        form = RecoveryProjectForm(request.POST, request.FILES)
        # Keep default prefix "form" so your existing template JS keeps working
        location_formset = ProjectLocationFormSet(
            request.POST,
            queryset=ProjectLocations.objects.none()
        )
        # Separate prefix to avoid collisions with the locations formset
        status_formset = ProjectStatusIndicatorFormSet(
            request.POST,
            queryset=ProjectStatusIndicators.objects.none(),
            prefix="stat"
        )
        if form.is_valid() and location_formset.is_valid() and status_formset.is_valid():
            project = form.save(commit=False)
            # --- Generate + save unique 9-digit project_id (never starts with 0) ---
            saved = False
            for _ in range(50):
                project.project_id = random.randint(100_000_000, 999_999_999)
                try:
                    project.save()
                    saved = True
                    break
                except IntegrityError:
                    continue
            if not saved:
                messages.error(request, "Could not generate a unique Project ID. Please try again.")
                return render(request, "dataentry/entry-form.html", {
                    "form": form,
                    "location_formset": location_formset,
                    "status_formset": status_formset,
                })
            # --- Save many locations ---
            locs = location_formset.save(commit=False)
            for loc in locs:
                loc.project = project
                loc.save()
            for obj in location_formset.deleted_objects:
                obj.delete()
            # --- Save status indicators (with descriptions) ---
            inds = status_formset.save(commit=False)
            for ind in inds:
                ind.project = project
                ind.save()
            # ✅ Success message (will show after redirect)
            messages.success(request, "Project saved successfully ✅")
            return redirect("data-entry")
        # ❌ Validation failed
        messages.error(request, "Please fix the errors below and try again.")
        return render(request, "dataentry/entry-form.html", {
            "form": form,
            "location_formset": location_formset,
            "status_formset": status_formset,
        })
    # ---- GET request ----
    form = RecoveryProjectForm()
    location_formset = ProjectLocationFormSet(queryset=ProjectLocations.objects.none())
    status_formset = ProjectStatusIndicatorFormSet(
        queryset=ProjectStatusIndicators.objects.none(),
        prefix="stat"
    )
    return render(request, "dataentry/entry-form.html", {
        "form": form,
        "location_formset": location_formset,
        "status_formset": status_formset,
    })
# ==================== LOGIN VIEW ====================
class DashboardLoginView(LoginView):
    template_name = "auth/login.html"
    redirect_authenticated_user = True
    def get_success_url(self):
        return reverse_lazy("overview")
# ==================== DATA UPDATE (TABULATOR GRID) ====================
# NOTE:
# - Your grid currently edits ONLY indicator values (status_indicator1..5),
# not descriptions. If you want grid-editing for descriptions too, we can add fields.
EDITABLE_FIELDS = {
    "sector": "text",
    "program": "text",
    "project_title": "text",
    "project_description": "text",
    "funding_status": "text",
    "gip": "text",
    "central_tender_board_link": "text",
    "funding_agency": "text",
    "implementing_agency": "text",
    "project_total_funding_us": "decimal2",
    "project_total_funding_vt": "int",
    "project_expenditure": "int",
    "start_date": "date",
    "completion_date": "date",
    "project_timeframe_days": "int",
    "province": "text",
    "island": "text",
    "area_council": "text",
    "project_site": "text",
    "gps_longtitude": "text",
    "gps_latitude": "text",
    "type_of_disaster_operation": "text",
    "key_risks_to_implementation": "text",
    "status_indicator1": "text",
    "status_indicator2": "text",
    "status_indicator3": "text",
    "status_indicator4": "text",
    "status_indicator5": "text",
}
@login_required(login_url="login")
def recovery_projects_table(request):
    return render(request, "dataentry/update-form.html")
@require_GET
@login_required(login_url="login")
def recovery_projects_api_list(request):
    page = int(request.GET.get("page", 1))
    size = int(request.GET.get("size", 50))
    qs = RecoveryProject.objects.all().order_by("-project_id")
    paginator = Paginator(qs, size)
    page_obj = paginator.get_page(page)
    project_ids = [p.project_id for p in page_obj.object_list]
    # Primary location per project = first by id
    locs = (
        ProjectLocations.objects
        .filter(project_id__in=project_ids)
        .order_by("project_id", "id")
    )
    loc_map = {}
    for loc in locs:
        if loc.project_id not in loc_map:
            loc_map[loc.project_id] = loc
    ind_map = {}
    inds = (
        ProjectStatusIndicators.objects
        .filter(project_id__in=project_ids)
        .order_by("project_id", "id")
    )
    for row in inds:
        ind_map.setdefault(row.project_id, []).append(row)
    def ind_val(project_id, idx):
        rows = ind_map.get(project_id, [])[:5]
        try:
            v = rows[idx].status_indicator
            return str(v) if v is not None else None
        except IndexError:
            return None
    rows = []
    for p in page_obj.object_list:
        loc = loc_map.get(p.project_id)
        rows.append({
            "id": p.project_id,
            "sector": p.sector,
            "program": p.program,
            "project_title": p.project_title,
            "project_description": p.project_description,
            "funding_status": p.funding_status,
            "funding_agency": p.funding_agency,
            "implementing_agency": p.implementing_agency,
            "gip": p.gip,
            "central_tender_board_link": p.central_tender_board_link,
            "project_total_funding_us": str(p.project_total_funding_us) if p.project_total_funding_us is not None else None,
            "project_total_funding_vt": p.project_total_funding_vt,
            "project_expenditure": p.project_expenditure,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "completion_date": p.completion_date.isoformat() if p.completion_date else None,
            "project_timeframe_days": p.project_timeframe_days,
            "province": loc.province if loc else None,
            "island": loc.island if loc else None,
            "area_council": loc.area_council if loc else None,
            "project_site": loc.project_site if loc else None,
            "gps_longtitude": str(loc.gps_longtitude) if (loc and loc.gps_longtitude is not None) else None,
            "gps_latitude": str(loc.gps_latitude) if (loc and loc.gps_latitude is not None) else None,
            "type_of_disaster_operation": p.type_of_disaster_operation,
            "key_risks_to_implementation": p.key_risks_to_implementation,
            "status_indicator1": ind_val(p.project_id, 0),
            "status_indicator2": ind_val(p.project_id, 1),
            "status_indicator3": ind_val(p.project_id, 2),
            "status_indicator4": ind_val(p.project_id, 3),
            "status_indicator5": ind_val(p.project_id, 4),
        })
    return JsonResponse({
        "data": rows,
        "last_page": paginator.num_pages,
    })


@login_required(login_url="login")
@require_http_methods(["PATCH", "DELETE"])
@csrf_protect
def recovery_projects_api_detail(request, pk):
    project = get_object_or_404(RecoveryProject, project_id=pk)
    # -------- DELETE --------
    if request.method == "DELETE":
        ProjectStatusIndicators.objects.filter(project=project).delete()
        ProjectLocations.objects.filter(project=project).delete()
        project.delete()
        return JsonResponse({"ok": True, "id": pk})
    # -------- PATCH --------
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    field = payload.get("field")
    value = payload.get("value")
    if field not in EDITABLE_FIELDS:
        return HttpResponseBadRequest("Field not editable")
    field_type = EDITABLE_FIELDS[field]
    raw = ("" if value is None else str(value)).strip()
    try:
        if field_type == "date":
            val = None if raw == "" else datetime.strptime(raw, "%Y-%m-%d").date()
        elif field_type == "decimal2":
            val = None if raw == "" else Decimal(raw)
        elif field_type == "int":
            val = None if raw == "" else int(raw)
        else:
            val = raw
    except (ValueError, InvalidOperation):
        return HttpResponseBadRequest("Invalid value")
    LOCATION_FIELDS = {
        "province", "island", "area_council", "project_site",
        "gps_longtitude", "gps_latitude",
    }
    INDICATOR_FIELDS = {
        "status_indicator1", "status_indicator2", "status_indicator3",
        "status_indicator4", "status_indicator5",
    }
    # ---- Indicators (pivoted 1..5) ----
    if field in INDICATOR_FIELDS:
        idx = int(field.replace("status_indicator", "")) - 1 # 0..4
        indicators = list(
            ProjectStatusIndicators.objects
            .filter(project=project)
            .order_by("id")
        )
        while len(indicators) <= idx:
            indicators.append(
                ProjectStatusIndicators.objects.create(
                    project=project,
                    status_indicator=None,
                    description=None,
                )
            )
        row = indicators[idx]
        if raw == "":
            row.status_indicator = None
        else:
            try:
                row.status_indicator = Decimal(raw)
            except (InvalidOperation, ValueError):
                return HttpResponseBadRequest("Invalid value")
        row.save(update_fields=["status_indicator"])
        out_val = str(row.status_indicator) if row.status_indicator is not None else None
        return JsonResponse({"ok": True, "id": project.project_id, "field": field, "value": out_val})
    # ---- Location fields (primary location only) ----
    if field in LOCATION_FIELDS:
        loc = (
            ProjectLocations.objects
            .filter(project=project)
            .order_by("id")
            .first()
        )
        if not loc:
            loc = ProjectLocations.objects.create(project=project)
        if field in ("gps_longtitude", "gps_latitude"):
            if raw == "":
                setattr(loc, field, None)
            else:
                try:
                    setattr(loc, field, Decimal(raw))
                except (InvalidOperation, ValueError):
                    return HttpResponseBadRequest("Invalid value")
        else:
            setattr(loc, field, val)
        loc.save(update_fields=[field])
        out_val = str(getattr(loc, field)) if getattr(loc, field) is not None else None
        return JsonResponse({"ok": True, "id": project.project_id, "field": field, "value": out_val})
    # ---- Project fields ----
    setattr(project, field, val)
    project.save(update_fields=[field])
    if hasattr(val, "isoformat"):
        out_val = val.isoformat()
    elif isinstance(val, Decimal):
        out_val = str(val)
    else:
        out_val = val
    return JsonResponse({"ok": True, "id": project.project_id, "field": field, "value": out_val})
# ==================== ATTACHMENT DOWNLOAD ====================
@login_required(login_url="login")
def download_gip(request, pk):
    p = get_object_or_404(RecoveryProject, project_id=pk)
    path_str = getattr(p, "gip_attachment", None)
    if not path_str:
        raise Http404("No attachment")
    file_path = str(path_str)
    if not os.path.exists(file_path):
        raise Http404("File missing")
    return FileResponse(
        open(file_path, "rb"),
        as_attachment=True,
        filename=os.path.basename(file_path),
    )
# ==================== PROJECT LOCATIONS API ====================
@require_GET
@login_required(login_url="login")
def project_locations_api_list(request, project_id):
    locations = ProjectLocations.objects.filter(project_id=project_id).order_by("id")
    rows = []
    for loc in locations:
        rows.append({
            "id": loc.id,
            "province": loc.province,
            "island": loc.island,
            "area_council": loc.area_council,
            "project_site": loc.project_site,
            "gps_longtitude": str(loc.gps_longtitude) if loc.gps_longtitude is not None else None,
            "gps_latitude": str(loc.gps_latitude) if loc.gps_latitude is not None else None,
        })
    return JsonResponse({"data": rows}, safe=False)

@login_required(login_url="login")
@require_http_methods(["PATCH", "DELETE"])
@csrf_protect
def project_locations_api_detail(request, pk):
    loc = get_object_or_404(ProjectLocations, id=pk)
    if request.method == "DELETE":
        loc.delete()
        return JsonResponse({"ok": True, "id": pk})
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    field = payload.get("field")
    value = payload.get("value")
    LOCATION_EDITABLE_FIELDS = {
        "province": "text",
        "island": "text",
        "area_council": "text",
        "project_site": "text",
        "gps_longtitude": "decimal",
        "gps_latitude": "decimal",
    }
    if field not in LOCATION_EDITABLE_FIELDS:
        return HttpResponseBadRequest("Field not editable")
    field_type = LOCATION_EDITABLE_FIELDS[field]
    raw = ("" if value is None else str(value)).strip()
    try:
        if field_type == "decimal":
            val = None if raw == "" else Decimal(raw)
        else:
            val = raw
    except (ValueError, InvalidOperation):
        return HttpResponseBadRequest("Invalid value")
    setattr(loc, field, val)
    loc.save(update_fields=[field])
    out_val = str(val) if val is not None else None
    return JsonResponse({"ok": True, "id": loc.id, "field": field, "value": out_val})

@login_required(login_url="login")
@require_http_methods(["POST"])
@csrf_protect
def project_locations_api_create(request, project_id):
    project = get_object_or_404(RecoveryProject, project_id=project_id)
    loc = ProjectLocations.objects.create(project=project)
    return JsonResponse({
        "id": loc.id,
        "province": loc.province,
        "island": loc.island,
        "area_council": loc.area_council,
        "project_site": loc.project_site,
        "gps_longtitude": str(loc.gps_longtitude) if loc.gps_longtitude is not None else None,
        "gps_latitude": str(loc.gps_latitude) if loc.gps_latitude is not None else None,
    })

# ==================== PROJECT STATUS INDICATORS API ====================
@require_GET
@login_required(login_url="login")
def project_status_indicators_api_list(request, project_id):
    indicators = ProjectStatusIndicators.objects.filter(project_id=project_id).order_by("id")
    rows = []
    for ind in indicators:
        rows.append({
            "id": ind.id,
            "status_indicator": str(ind.status_indicator) if ind.status_indicator is not None else None,
            "description": ind.description,
            "attachment": os.path.basename(ind.attachment.name) if ind.attachment else None,
            "attachment_url": ind.attachment.url if ind.attachment else None,
        })
    return JsonResponse({"data": rows}, safe=False)

@login_required(login_url="login")
@require_http_methods(["PATCH", "POST", "DELETE"])
@csrf_protect
def project_status_indicators_api_detail(request, pk):
    ind = get_object_or_404(ProjectStatusIndicators, id=pk)

    if request.method == "DELETE":
        if ind.attachment:
            ind.attachment.delete(save=False)
        ind.delete()
        return JsonResponse({"ok": True, "id": pk})

    # ---------- FILE UPLOAD ----------
    if request.method == "POST" and request.FILES.get("attachment"):
        uploaded_file = request.FILES["attachment"]

        if ind.attachment:
            ind.attachment.delete(save=False)

        ind.attachment = uploaded_file
        ind.save(update_fields=["attachment"])

        return JsonResponse({
            "ok": True,
            "id": ind.id,
            "field": "attachment",
            "value": os.path.basename(ind.attachment.name) if ind.attachment else None,
            "attachment": os.path.basename(ind.attachment.name) if ind.attachment else None,
            "attachment_url": ind.attachment.url if ind.attachment else None,
        })

    # ---------- NORMAL JSON PATCH ----------
    if request.method != "PATCH":
        return HttpResponseBadRequest("Invalid upload request")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    field = payload.get("field")
    value = payload.get("value")

    IND_EDITABLE_FIELDS = {
        "status_indicator": "decimal",
        "description": "text",
    }

    if field not in IND_EDITABLE_FIELDS:
        return HttpResponseBadRequest("Field not editable")

    field_type = IND_EDITABLE_FIELDS[field]
    raw = ("" if value is None else str(value)).strip()

    try:
        if field_type == "decimal":
            val = None if raw == "" else Decimal(raw)
        else:
            val = raw
    except (ValueError, InvalidOperation):
        return HttpResponseBadRequest("Invalid value")

    setattr(ind, field, val)
    ind.save(update_fields=[field])

    out_val = str(val) if val is not None else None

    return JsonResponse({
        "ok": True,
        "id": ind.id,
        "field": field,
        "value": out_val,
        "attachment": os.path.basename(ind.attachment.name) if ind.attachment else None,
        "attachment_url": ind.attachment.url if ind.attachment else None,
    })

@login_required(login_url="login")
@require_http_methods(["POST"])
@csrf_protect
def project_status_indicators_api_create(request, project_id):
    project = get_object_or_404(RecoveryProject, project_id=project_id)
    ind = ProjectStatusIndicators.objects.create(project=project)
    return JsonResponse({
        "id": ind.id,
        "status_indicator": str(ind.status_indicator) if ind.status_indicator is not None else None,
        "description": ind.description,
        "attachment": os.path.basename(ind.attachment.name) if ind.attachment else None,
        "attachment_url": ind.attachment.url if ind.attachment else None,
    })

@login_required(login_url="login")
def download_status_indicator_attachment(request, pk):
    ind = get_object_or_404(ProjectStatusIndicators, id=pk)

    if not ind.attachment:
        raise Http404("No attachment")

    return FileResponse(
        ind.attachment.open("rb"),
        as_attachment=True,
        filename=os.path.basename(ind.attachment.name),
    )
