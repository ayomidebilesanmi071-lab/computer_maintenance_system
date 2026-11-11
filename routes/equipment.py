"""Equipment inventory routes (list, register, detail, edit, status, retire)."""

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
from forms import EquipmentFilterForm, EquipmentForm, EquipmentStatusForm, RetireEquipmentForm
from models.roles import (
    PERM_EQUIPMENT_CREATE,
    PERM_EQUIPMENT_EDIT,
    PERM_EQUIPMENT_RETIRE,
    PERM_EQUIPMENT_STATUS,
    PERM_EQUIPMENT_VIEW,
)
from routes.decorators import permission_required, validated_filters
from services import audit_service
from services.errors import NotFoundError, ServiceError
from services.equipment_service import EquipmentService

equipment_bp = Blueprint("equipment", __name__, url_prefix="/equipment")


@equipment_bp.route("/")
@permission_required(PERM_EQUIPMENT_VIEW)
def index():
    """Searchable, filterable, paginated inventory list."""
    form = EquipmentFilterForm(request.args)
    filters = validated_filters(form)
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config["PER_PAGE"]
    pagination = EquipmentService.paginate(page, per_page, **filters)

    return render_template(
        "equipment/list.html",
        pagination=pagination,
        equipment_items=pagination.items,
        form=form,
        filters=filters,
        active_filters=len(filters),
    )


@equipment_bp.route("/new", methods=["GET", "POST"])
@permission_required(PERM_EQUIPMENT_CREATE)
def create():
    """Register a new asset."""
    form = EquipmentForm()
    if form.validate_on_submit():
        try:
            equipment = EquipmentService.create(form.to_data(), actor=current_user)
            db.session.commit()
            flash(f"Equipment {equipment.asset_tag} registered successfully.", "success")
            return redirect(url_for("equipment.detail", equipment_id=equipment.id))
        except ServiceError as error:
            db.session.rollback()
            flash(str(error), "error")

    return render_template("equipment/create.html", form=form)


@equipment_bp.route("/<int:equipment_id>")
@permission_required(PERM_EQUIPMENT_VIEW)
def detail(equipment_id: int):
    """Full equipment record: assets, faults, maintenance, history, audit."""
    try:
        equipment = EquipmentService.get(equipment_id)
    except NotFoundError:
        abort(404)

    return render_template(
        "equipment/detail.html",
        equipment=equipment,
        status_form=EquipmentStatusForm(),
        retire_form=RetireEquipmentForm(),
        status_history=equipment.status_history,
        fault_reports=equipment.fault_reports,
        maintenance_records=equipment.maintenance_records,
        schedules=equipment.maintenance_schedules,
        audit_entries=audit_service.AuditService.history("equipment", equipment.id, limit=20),
    )


@equipment_bp.route("/<int:equipment_id>/edit", methods=["GET", "POST"])
@permission_required(PERM_EQUIPMENT_EDIT)
def edit(equipment_id: int):
    """Edit an existing asset."""
    try:
        equipment = EquipmentService.get(equipment_id)
    except NotFoundError:
        abort(404)

    form = EquipmentForm(obj=None)
    if form.validate_on_submit():
        try:
            EquipmentService.update(equipment, form.to_data(), actor=current_user)
            db.session.commit()
            flash(f"Equipment {equipment.asset_tag} updated.", "success")
            return redirect(url_for("equipment.detail", equipment_id=equipment.id))
        except ServiceError as error:
            db.session.rollback()
            flash(str(error), "error")
    elif request.method == "GET":
        form.load_equipment(equipment)

    return render_template("equipment/edit.html", form=form, equipment=equipment)


@equipment_bp.route("/<int:equipment_id>/status", methods=["POST"])
@permission_required(PERM_EQUIPMENT_STATUS)
def change_status(equipment_id: int):
    """Change the condition and/or operational status of an asset."""
    try:
        equipment = EquipmentService.get(equipment_id)
    except NotFoundError:
        abort(404)

    form = EquipmentStatusForm()
    if not form.validate_on_submit():
        flash("Please choose a valid condition and operational status.", "error")
        return redirect(url_for("equipment.detail", equipment_id=equipment.id))

    try:
        changed = []
        if form.condition.data != equipment.condition:
            EquipmentService.change_condition(
                equipment, form.condition.data, actor=current_user, notes=form.notes.data or ""
            )
            changed.append(f"condition → {form.condition.data}")
        if form.operational_status.data != equipment.operational_status:
            EquipmentService.change_status(
                equipment,
                form.operational_status.data,
                actor=current_user,
                notes=form.notes.data or "",
            )
            changed.append(f"status → {form.operational_status.data}")

        db.session.commit()
        if changed:
            flash(f"{equipment.asset_tag} updated ({', '.join(changed)}).", "success")
        else:
            flash("No changes were made.", "info")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")

    return redirect(url_for("equipment.detail", equipment_id=equipment.id))


@equipment_bp.route("/<int:equipment_id>/retire", methods=["POST"])
@permission_required(PERM_EQUIPMENT_RETIRE)
def retire(equipment_id: int):
    """Retire an asset.  Records are never deleted."""
    try:
        equipment = EquipmentService.get(equipment_id)
    except NotFoundError:
        abort(404)

    form = RetireEquipmentForm()
    if not form.validate_on_submit():
        flash("Please confirm the retirement.", "error")
        return redirect(url_for("equipment.detail", equipment_id=equipment.id))

    if form.confirm.data != "yes":
        flash("Retirement cancelled — the equipment record is unchanged.", "info")
        return redirect(url_for("equipment.detail", equipment_id=equipment.id))

    try:
        EquipmentService.retire(equipment, actor=current_user, notes=form.reason.data or "")
        db.session.commit()
        flash(f"Equipment {equipment.asset_tag} has been retired.", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")

    return redirect(url_for("equipment.detail", equipment_id=equipment.id))


@equipment_bp.route("/<int:equipment_id>/history")
@permission_required(PERM_EQUIPMENT_VIEW)
def history(equipment_id: int):
    """Dedicated page for an asset's condition/status change history."""
    try:
        equipment = EquipmentService.get(equipment_id)
    except NotFoundError:
        abort(404)

    return render_template(
        "equipment/history.html",
        equipment=equipment,
        status_history=equipment.status_history,
        audit_entries=audit_service.AuditService.history("equipment", equipment.id, limit=50),
    )
