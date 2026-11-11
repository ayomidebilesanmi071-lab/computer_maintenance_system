"""Reporting routes.

Every report is built from live database rows via
:class:`~services.report_service.ReportService`; the same rows feed the HTML
table and the CSV download, so an export can never disagree with the screen.
"""

from datetime import date

from flask import Blueprint, Response, render_template, request

from forms import ReportFilterForm
from models.roles import PERM_REPORT_EXPORT, PERM_REPORT_VIEW
from routes.decorators import export_requested, permission_required, validated_filters
from services.report_service import ReportService

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

#: Report registry used by the index page and the navigation menu.
REPORTS = (
    {
        "endpoint": "reports.equipment_inventory",
        "title": "Equipment Inventory Report",
        "description": "Every registered asset with its type, department, "
                       "location, condition and operational status.",
        "icon": "▤",
    },
    {
        "endpoint": "reports.fault_summary",
        "title": "Fault Report Summary",
        "description": "Faults with equipment, category, priority, status and "
                       "the officer they are assigned to.",
        "icon": "⚠",
    },
    {
        "endpoint": "reports.maintenance_history",
        "title": "Maintenance History Report",
        "description": "Work performed on each asset: type, date, technician, "
                       "work done and outcome.",
        "icon": "🛠",
    },
    {
        "endpoint": "reports.preventive_schedule",
        "title": "Preventive Maintenance Report",
        "description": "Scheduled servicing, the officer responsible, schedule "
                       "status and completion dates.",
        "icon": "📅",
    },
    {
        "endpoint": "reports.equipment_condition",
        "title": "Equipment Condition Report",
        "description": "Assets grouped by condition: Excellent, Good, Fair, "
                       "Poor and Damaged.",
        "icon": "◍",
    },
)


def _form() -> ReportFilterForm:
    form = ReportFilterForm(request.args)
    validated_filters(form, label="report")
    return form


def _csv(filename_stem: str, headers, rows) -> Response:
    """Wrap CSV text in a download response."""
    payload = ReportService.to_csv(headers, rows)
    filename = f"{filename_stem}-{date.today().isoformat()}.csv"
    return Response(
        payload,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@reports_bp.route("/")
@permission_required(PERM_REPORT_VIEW)
def index():
    """Report hub."""
    return render_template(
        "reports/index.html",
        reports=REPORTS,
        totals=ReportService.summary_totals(),
    )


@reports_bp.route("/equipment")
@permission_required(PERM_REPORT_VIEW)
def equipment_inventory():
    form = _form()
    filters = form.equipment_filters()
    items = ReportService.equipment_inventory(**filters)

    if export_requested():
        if not _can_export():
            return _export_denied()
        return _csv(
            "equipment-inventory",
            ReportService.INVENTORY_HEADERS,
            ReportService.inventory_rows(items),
        )

    return render_template(
        "reports/equipment.html",
        form=form,
        items=items,
        filters=filters,
        generated_at=date.today(),
    )


@reports_bp.route("/faults")
@permission_required(PERM_REPORT_VIEW)
def fault_summary():
    form = _form()
    filters = form.fault_filters()
    items = ReportService.fault_summary(**filters)

    if export_requested():
        if not _can_export():
            return _export_denied()
        return _csv(
            "fault-summary",
            ReportService.FAULT_HEADERS,
            ReportService.fault_rows(items),
        )

    return render_template(
        "reports/faults.html",
        form=form,
        items=items,
        filters=filters,
        generated_at=date.today(),
    )


@reports_bp.route("/maintenance")
@permission_required(PERM_REPORT_VIEW)
def maintenance_history():
    form = _form()
    filters = form.maintenance_filters()
    items = ReportService.maintenance_history(**filters)

    if export_requested():
        if not _can_export():
            return _export_denied()
        return _csv(
            "maintenance-history",
            ReportService.MAINTENANCE_HEADERS,
            ReportService.maintenance_rows(items),
        )

    total_cost = sum(float(item.cost) for item in items if item.cost is not None)
    return render_template(
        "reports/maintenance.html",
        form=form,
        items=items,
        filters=filters,
        total_cost=total_cost,
        generated_at=date.today(),
    )


@reports_bp.route("/preventive")
@permission_required(PERM_REPORT_VIEW)
def preventive_schedule():
    form = _form()
    filters = form.schedule_filters()
    items = ReportService.preventive_schedule(**filters)

    if export_requested():
        if not _can_export():
            return _export_denied()
        return _csv(
            "preventive-maintenance",
            ReportService.SCHEDULE_HEADERS,
            ReportService.schedule_rows(items),
        )

    return render_template(
        "reports/preventive.html",
        form=form,
        items=items,
        filters=filters,
        generated_at=date.today(),
    )


@reports_bp.route("/conditions")
@permission_required(PERM_REPORT_VIEW)
def equipment_condition():
    form = _form()
    filters = form.equipment_filters()
    grouped = ReportService.equipment_condition_report(**filters)

    if export_requested():
        if not _can_export():
            return _export_denied()
        return _csv(
            "equipment-condition",
            ReportService.CONDITION_HEADERS,
            ReportService.condition_rows(grouped),
        )

    return render_template(
        "reports/conditions.html",
        form=form,
        grouped=grouped,
        filters=filters,
        total=sum(len(rows) for rows in grouped.values()),
        generated_at=date.today(),
    )


# ----------------------------------------------------------------- helpers
def _can_export() -> bool:
    from flask_login import current_user

    return current_user.is_authenticated and current_user.can(PERM_REPORT_EXPORT)


def _export_denied():
    from flask import abort, flash

    flash("You do not have permission to export reports.", "error")
    abort(403)
