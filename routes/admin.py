"""Administrator routes: account management and the audit trail.

Both areas are administrator-only, enforced server-side by
:func:`routes.decorators.permission_required`.  The audit log is strictly
append-only through the application: the only route that touches it is the
read-only listing below.
"""

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
from forms import AuditFilterForm, UserFilterForm, UserForm
from models.constants import ROLE_LABELS
from models.roles import PERM_AUDIT_VIEW, PERM_USER_MANAGE
from routes.decorators import permission_required, validated_filters
from services import audit_service
from services.dashboard_service import DashboardService
from services.errors import NotFoundError, ServiceError
from services.user_service import UserService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@permission_required(PERM_USER_MANAGE)
def users():
    """List, search and filter accounts."""
    form = UserFilterForm(request.args)
    filters = validated_filters(form)
    page = request.args.get("page", 1, type=int)
    pagination = UserService.paginate(page, current_app.config["PER_PAGE"], **filters)
    return render_template(
        "admin/users.html",
        pagination=pagination,
        users=pagination.items,
        form=form,
        filters=filters,
        role_counts=DashboardService.role_counts(),
        role_labels=ROLE_LABELS,
        active_filters=len(filters),
    )


@admin_bp.route("/users/new", methods=["GET", "POST"])
@permission_required(PERM_USER_MANAGE)
def create_user():
    """Create an account (administrator, ICT officer or viewer)."""
    form = UserForm(editing=False)
    if form.validate_on_submit():
        try:
            user = UserService.create_user(form.to_data(), actor=current_user)
            db.session.commit()
            flash(
                f"{ROLE_LABELS.get(user.role, user.role)} account created for "
                f"{user.full_name}.",
                "success",
            )
            return redirect(url_for("admin.users"))
        except ServiceError as error:
            db.session.rollback()
            flash(str(error), "error")

    return render_template("admin/user_form.html", form=form, user=None)


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@permission_required(PERM_USER_MANAGE)
def edit_user(user_id: int):
    """Edit an account, including an optional password reset."""
    try:
        user = UserService.get(user_id)
    except NotFoundError:
        abort(404)

    form = UserForm(editing=True)
    if form.validate_on_submit():
        try:
            UserService.update_user(user, form.to_data(), actor=current_user)
            db.session.commit()
            flash(f"Account for {user.full_name} updated.", "success")
            return redirect(url_for("admin.users"))
        except ServiceError as error:
            db.session.rollback()
            flash(str(error), "error")
    elif request.method == "GET":
        form.load_user(user)

    return render_template("admin/user_form.html", form=form, user=user)


@admin_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@permission_required(PERM_USER_MANAGE)
def deactivate_user(user_id: int):
    """Deactivate an account (never delete it)."""
    try:
        user = UserService.get(user_id)
        UserService.deactivate(user, actor=current_user)
        db.session.commit()
        flash(f"{user.full_name}'s account has been deactivated.", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/activate", methods=["POST"])
@permission_required(PERM_USER_MANAGE)
def activate_user(user_id: int):
    """Reactivate a previously deactivated account."""
    try:
        user = UserService.get(user_id)
        UserService.activate(user, actor=current_user)
        db.session.commit()
        flash(f"{user.full_name}'s account has been reactivated.", "success")
    except ServiceError as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("admin.users"))


@admin_bp.route("/audit")
@permission_required(PERM_AUDIT_VIEW)
def audit_log():
    """Read-only audit trail with filters."""
    form = AuditFilterForm(request.args)
    filters = validated_filters(form)
    page = request.args.get("page", 1, type=int)
    pagination = audit_service.AuditService.paginate(
        page, current_app.config["PER_PAGE"], **filters
    )
    return render_template(
        "admin/audit.html",
        pagination=pagination,
        entries=pagination.items,
        form=form,
        filters=filters,
        active_filters=len(filters),
    )
