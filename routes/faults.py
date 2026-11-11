"""Fault reporting routes.

The detail page is the ICT officer's workbench: it shows the record, the status
history, the investigation notes, linked repairs and audit entries, and offers
every workflow control (acknowledge, assign, re-prioritise, update status, add
notes, record a repair, resolve, close).
"""

import os

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user

from extensions import db
from forms import (
    AssignFaultForm,
    FaultFilterForm,
    FaultForm,
    FaultNoteForm,
    FaultPriorityForm,
    FaultResolutionForm,
    FaultStatusForm,
)
from models.roles import PERM_FAULT_CREATE, PERM_FAULT_MANAGE, PERM_FAULT_VIEW
from routes.decorators import permission_required, validated_filters
from services import audit_service
from services.errors import NotFoundError, ServiceError
from services.fault_service import FaultService
from services.upload_service import AttachmentService

faults_bp = Blueprint("faults", __name__, url_prefix="/faults")


@faults_bp.route("/")
@permission_required(PERM_FAULT_VIEW)
def index():
    """Searchable, filterable, paginated fault list."""
    form = FaultFilterForm(request.args)
    filters = validated_filters(form)
    page = request.args.get("page", 1, type=int)
    pagination = FaultService.paginate(page, current_app.config["PER_PAGE"], **filters)
    return render_template(
        "faults/list.html",
        pagination=pagination,
        fault_reports=pagination.items,
        form=form,
        filters=filters,
        active_filters=len(filters),
    )


@faults_bp.route("/new", methods=["GET", "POST"])
@permission_required(PERM_FAULT_CREATE)
def create():
    """Record a new fault against an existing asset."""
    form = FaultForm()
    # Allow the equipment detail page to pre-select the asset.
    if request.method == "GET":
        equipment_id = request.args.get("equipment_id", type=int)
        if equipment_id:
            form.equipment_id.data = equipment_id

    if form.validate_on_submit():
        try:
            attachment = AttachmentService.save(form.attachment.data)
        except ServiceError as error:
            attachment = None
            flash(str(error), "error")
        else:
            try:
                fault = FaultService.create(form.to_data(), actor=current_user)
                if attachment:
                    fault.attachment_filename = attachment
                db.session.commit()
                flash(
                    f"Fault {fault.reference_number} recorded successfully.",
                    "success",
                )
                return redirect(url_for("faults.detail", fault_id=fault.id))
            except ServiceError as error:
                db.session.rollback()
                if attachment:
                    AttachmentService.delete(attachment)
                flash(str(error), "error")

    return render_template("faults/create.html", form=form)


@faults_bp.route("/<int:fault_id>")
@permission_required(PERM_FAULT_VIEW)
def detail(fault_id: int):
    """The fault workbench."""
    try:
        fault = FaultService.get(fault_id)
    except NotFoundError:
        abort(404)

    status_form = FaultStatusForm()
    status_form.load_transitions(fault)

    return render_template(
        "faults/detail.html",
        fault=fault,
        status_form=status_form,
        assign_form=AssignFaultForm(),
        priority_form=FaultPriorityForm(),
        note_form=FaultNoteForm(),
        resolution_form=FaultResolutionForm(),
        maintenance_records=fault.maintenance_records,
        status_history=fault.status_history,
        notes_list=fault.notes,
        audit_entries=audit_service.AuditService.history("fault_report", fault.id, limit=25),
        can_manage=current_user.can(PERM_FAULT_MANAGE),
    )


@faults_bp.route("/<int:fault_id>/assign", methods=["POST"])
@permission_required(PERM_FAULT_MANAGE)
def assign(fault_id: int):
    """Assign (or unassign) the fault."""
    fault = _require_fault(fault_id)
    form = AssignFaultForm()
    if not form.validate_on_submit():
        flash("Could not change the assignment.", "error")
        return redirect(url_for("faults.detail", fault_id=fault.id))

    try:
        FaultService.assign(
            fault,
            form.assigned_to.data or None,
            actor=current_user,
            notes=form.notes.data or "",
        )
        db.session.commit()
        flash(f"Assignment updated ({fault.assignee_name}).", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("faults.detail", fault_id=fault.id))


@faults_bp.route("/<int:fault_id>/priority", methods=["POST"])
@permission_required(PERM_FAULT_MANAGE)
def priority(fault_id: int):
    """Change the priority of a fault."""
    fault = _require_fault(fault_id)
    form = FaultPriorityForm()
    if not form.validate_on_submit():
        flash("Could not change the priority.", "error")
        return redirect(url_for("faults.detail", fault_id=fault.id))

    try:
        FaultService.change_priority(
            fault, form.priority.data, actor=current_user, notes=form.notes.data or ""
        )
        db.session.commit()
        flash(f"Priority set to {fault.priority}.", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("faults.detail", fault_id=fault.id))


@faults_bp.route("/<int:fault_id>/status", methods=["POST"])
@permission_required(PERM_FAULT_MANAGE)
def change_status(fault_id: int):
    """Move the fault through its lifecycle, recording the change."""
    fault = _require_fault(fault_id)
    form = FaultStatusForm()
    form.load_transitions(fault)

    if not form.validate_on_submit():
        flash("That status change was not valid for this fault.", "error")
        return redirect(url_for("faults.detail", fault_id=fault.id))

    try:
        FaultService.change_status(
            fault,
            form.status.data,
            actor=current_user,
            notes=form.resolution_notes.data or "",
        )
        db.session.commit()
        flash(f"Fault {fault.reference_number} is now '{fault.status}'.", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("faults.detail", fault_id=fault.id))


@faults_bp.route("/<int:fault_id>/notes", methods=["POST"])
@permission_required(PERM_FAULT_MANAGE)
def add_note(fault_id: int):
    """Append a troubleshooting / investigation note."""
    fault = _require_fault(fault_id)
    form = FaultNoteForm()
    if not form.validate_on_submit():
        flash("Enter a note before saving.", "error")
        return redirect(url_for("faults.detail", fault_id=fault.id))

    try:
        FaultService.add_note(fault, current_user, form.body.data)
        db.session.commit()
        flash("Investigation note added.", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("faults.detail", fault_id=fault.id))


@faults_bp.route("/<int:fault_id>/resolution", methods=["POST"])
@permission_required(PERM_FAULT_MANAGE)
def resolution(fault_id: int):
    """Store resolution notes without changing the status."""
    fault = _require_fault(fault_id)
    form = FaultResolutionForm()
    if not form.validate_on_submit():
        flash("Enter the resolution details before saving.", "error")
        return redirect(url_for("faults.detail", fault_id=fault.id))

    try:
        FaultService.record_resolution_notes(fault, current_user, form.resolution_notes.data)
        db.session.commit()
        flash("Resolution notes saved.", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("faults.detail", fault_id=fault.id))


@faults_bp.route("/<int:fault_id>/attachment")
@permission_required(PERM_FAULT_VIEW)
def attachment(fault_id: int):
    """Download the optional supporting document."""
    fault = _require_fault(fault_id)
    if not fault.has_attachment:
        abort(404)

    # ``os.path.basename`` + ``send_from_directory`` keep the lookup inside the
    # upload folder, so a tampered file name can never escape it.
    filename = os.path.basename(fault.attachment_filename)
    folder = current_app.config["UPLOAD_FOLDER"]
    if not os.path.exists(os.path.join(folder, filename)):
        abort(404)
    return send_from_directory(folder, filename, as_attachment=True)


def _require_fault(fault_id: int):
    try:
        return FaultService.get(fault_id)
    except NotFoundError:
        abort(404)
