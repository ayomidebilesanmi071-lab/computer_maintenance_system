"""Maintenance routes: repair history and preventive-maintenance schedules."""

from datetime import date

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from extensions import db
from forms import (
    CompleteScheduleForm,
    MaintenanceFilterForm,
    MaintenanceForm,
    ScheduleFilterForm,
    ScheduleForm,
    ScheduleStatusForm,
)
from models.constants import SCHEDULE_IN_PROGRESS
from models.roles import (
    PERM_MAINTENANCE_CREATE,
    PERM_MAINTENANCE_EDIT,
    PERM_MAINTENANCE_VIEW,
    PERM_SCHEDULE_MANAGE,
    PERM_SCHEDULE_VIEW,
)
from routes.decorators import permission_required, validated_filters
from services import audit_service
from services.errors import NotFoundError, ServiceError, TransitionError
from services.maintenance_service import MaintenanceService, ScheduleService

maintenance_bp = Blueprint("maintenance", __name__, url_prefix="/maintenance")


# ============================================================ records (CRUD)
@maintenance_bp.route("/")
@permission_required(PERM_MAINTENANCE_VIEW)
def index():
    """Paginated maintenance history with filters."""
    form = MaintenanceFilterForm(request.args)
    filters = validated_filters(form)
    page = request.args.get("page", 1, type=int)
    pagination = MaintenanceService.paginate(page, current_app.config["PER_PAGE"], **filters)
    return render_template(
        "maintenance/list.html",
        pagination=pagination,
        records=pagination.items,
        form=form,
        filters=filters,
        active_filters=len(filters),
    )


@maintenance_bp.route("/new", methods=["GET", "POST"])
@permission_required(PERM_MAINTENANCE_CREATE)
def create():
    """Record maintenance work that was performed."""
    form = MaintenanceForm()
    if request.method == "GET":
        form.equipment_id.data = request.args.get("equipment_id", type=int) or 0
        form.fault_report_id.data = request.args.get("fault_report_id", type=int) or 0
        form.maintenance_date.data = date.today()

    if form.validate_on_submit():
        try:
            record = MaintenanceService.record_maintenance(form.to_data(), actor=current_user)
            db.session.commit()
            flash("Maintenance record saved.", "success")
            return redirect(url_for("maintenance.detail", record_id=record.id))
        except ServiceError as error:
            db.session.rollback()
            flash(str(error), "error")

    return render_template("maintenance/create.html", form=form)


@maintenance_bp.route("/<int:record_id>")
@permission_required(PERM_MAINTENANCE_VIEW)
def detail(record_id: int):
    """One maintenance record with its links."""
    try:
        record = MaintenanceService.get(record_id)
    except NotFoundError:
        abort(404)

    return render_template(
        "maintenance/detail.html",
        record=record,
        audit_entries=audit_service.AuditService.history(
            "maintenance_record", record.id, limit=20
        ),
    )


@maintenance_bp.route("/<int:record_id>/edit", methods=["GET", "POST"])
@permission_required(PERM_MAINTENANCE_EDIT)
def edit(record_id: int):
    """Correct an existing maintenance record."""
    try:
        record = MaintenanceService.get(record_id)
    except NotFoundError:
        abort(404)

    form = MaintenanceForm()
    if form.validate_on_submit():
        try:
            MaintenanceService.update_record(record, form.to_data(), actor=current_user)
            db.session.commit()
            flash("Maintenance record updated.", "success")
            return redirect(url_for("maintenance.detail", record_id=record.id))
        except ServiceError as error:
            db.session.rollback()
            flash(str(error), "error")
    elif request.method == "GET":
        form.load_record(record)

    return render_template("maintenance/edit.html", form=form, record=record)


# ============================================================== schedules
@maintenance_bp.route("/schedules")
@permission_required(PERM_SCHEDULE_VIEW)
def schedules():
    """Preventive-maintenance schedule list."""
    if ScheduleService.refresh_statuses():
        db.session.commit()

    form = ScheduleFilterForm(request.args)
    filters = validated_filters(form)
    page = request.args.get("page", 1, type=int)

    stmt = _schedule_statement(**filters)
    pagination = db.paginate(stmt, page=page, per_page=current_app.config["PER_PAGE"],
                             error_out=False)

    return render_template(
        "maintenance/schedules.html",
        pagination=pagination,
        schedules=pagination.items,
        form=form,
        filters=filters,
        active_filters=len(filters),
        due_soon=ScheduleService.upcoming(14),
    )


@maintenance_bp.route("/schedules/new", methods=["GET", "POST"])
@permission_required(PERM_SCHEDULE_MANAGE)
def create_schedule():
    """Plan a preventive-maintenance activity."""
    form = ScheduleForm()
    if request.method == "GET":
        form.equipment_id.data = request.args.get("equipment_id", type=int) or 0
        form.scheduled_date.data = request.args.get("scheduled_date", type=date.today)
        form.assigned_to.data = request.args.get("assigned_to", type=int) or 0

    if form.validate_on_submit():
        try:
            schedule = ScheduleService.create(form.to_data(), actor=current_user)
            db.session.commit()
            flash("Maintenance schedule created.", "success")
            return redirect(url_for("maintenance.schedule_detail", schedule_id=schedule.id))
        except ServiceError as error:
            db.session.rollback()
            flash(str(error), "error")

    return render_template("maintenance/schedule_form.html", form=form, schedule=None)


@maintenance_bp.route("/schedules/<int:schedule_id>")
@permission_required(PERM_SCHEDULE_VIEW)
def schedule_detail(schedule_id: int):
    """Schedule detail with completion controls."""
    try:
        schedule = ScheduleService.get(schedule_id)
    except NotFoundError:
        abort(404)

    complete_form = CompleteScheduleForm()
    complete_form.maintenance_date.data = date.today()
    complete_form.outcome.data = "Completed - Equipment Working"

    return render_template(
        "maintenance/schedule_detail.html",
        schedule=schedule,
        complete_form=complete_form,
        status_form=ScheduleStatusForm(),
        audit_entries=audit_service.AuditService.history(
            "maintenance_schedule", schedule.id, limit=20
        ),
    )


@maintenance_bp.route("/schedules/<int:schedule_id>/edit", methods=["GET", "POST"])
@permission_required(PERM_SCHEDULE_MANAGE)
def edit_schedule(schedule_id: int):
    """Reschedule / reassign a preventive-maintenance activity."""
    try:
        schedule = ScheduleService.get(schedule_id)
    except NotFoundError:
        abort(404)

    form = ScheduleForm()
    if form.validate_on_submit():
        try:
            ScheduleService.update(schedule, form.to_data(), actor=current_user)
            db.session.commit()
            flash("Schedule updated.", "success")
            return redirect(url_for("maintenance.schedule_detail", schedule_id=schedule.id))
        except ServiceError as error:
            db.session.rollback()
            flash(str(error), "error")
    elif request.method == "GET":
        form.load_schedule(schedule)

    return render_template(
        "maintenance/schedule_form.html", form=form, schedule=schedule
    )


@maintenance_bp.route("/schedules/<int:schedule_id>/complete", methods=["POST"])
@permission_required(PERM_SCHEDULE_MANAGE)
def complete_schedule(schedule_id: int):
    """Complete a schedule, optionally recording the maintenance entry."""
    try:
        schedule = ScheduleService.get(schedule_id)
    except NotFoundError:
        abort(404)

    form = CompleteScheduleForm()
    if not form.validate_on_submit():
        flash("Please check the completion details.", "error")
        return redirect(url_for("maintenance.schedule_detail", schedule_id=schedule.id))

    try:
        ScheduleService.complete(
            schedule,
            actor=current_user,
            record_maintenance=form.record_maintenance.data == "yes",
            extra={
                "maintenance_date": form.maintenance_date.data,
                "outcome": form.outcome.data,
                "work_performed": form.work_performed.data
                or schedule.instructions
                or f"Preventive maintenance completed ({schedule.maintenance_type}).",
                "cost": form.cost.data,
            },
        )
        db.session.commit()
        flash("Schedule marked as completed.", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("maintenance.schedule_detail", schedule_id=schedule.id))


@maintenance_bp.route("/schedules/<int:schedule_id>/status", methods=["POST"])
@permission_required(PERM_SCHEDULE_MANAGE)
def schedule_status(schedule_id: int):
    """Start or cancel a schedule."""
    try:
        schedule = ScheduleService.get(schedule_id)
    except NotFoundError:
        abort(404)

    form = ScheduleStatusForm()
    if not form.validate_on_submit():
        flash("Could not update the schedule status.", "error")
        return redirect(url_for("maintenance.schedule_detail", schedule_id=schedule.id))

    try:
        if form.status.data == "Cancelled":
            ScheduleService.cancel(schedule, actor=current_user, reason=form.notes.data or "")
        else:
            ScheduleService.update(schedule, {"status": form.status.data}, actor=current_user)
        db.session.commit()
        flash(f"Schedule is now '{schedule.status}'.", "success")
    except (ServiceError, TransitionError) as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("maintenance.schedule_detail", schedule_id=schedule.id))


# ----------------------------------------------------------------- helpers
def _schedule_statement(**filters):
    """Filtered schedule query (mirrors the report service's logic)."""
    from sqlalchemy import select

    from models.department import Department
    from models.equipment import Equipment
    from models.maintenance import MaintenanceSchedule

    stmt = (
        select(MaintenanceSchedule)
        .join(Equipment, MaintenanceSchedule.equipment_id == Equipment.id, isouter=True)
        .join(Department, Equipment.department_id == Department.id, isouter=True)
    )
    if filters.get("status"):
        stmt = stmt.where(MaintenanceSchedule.status == filters["status"])
    if filters.get("department_id"):
        stmt = stmt.where(Equipment.department_id == int(filters["department_id"]))
    if filters.get("assigned_to"):
        stmt = stmt.where(MaintenanceSchedule.assigned_to == int(filters["assigned_to"]))
    if filters.get("date_from"):
        stmt = stmt.where(MaintenanceSchedule.scheduled_date >= filters["date_from"])
    if filters.get("date_to"):
        stmt = stmt.where(MaintenanceSchedule.scheduled_date <= filters["date_to"])
    search = (filters.get("search") or "").strip()
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Equipment.asset_tag.ilike(pattern) | Equipment.equipment_name.ilike(pattern)
        )
    return stmt.order_by(MaintenanceSchedule.scheduled_date.asc())
