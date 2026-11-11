"""Department and equipment-category (master data) routes."""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import func, or_, select
from flask_login import current_user

from extensions import db
from forms import DepartmentFilterForm, DepartmentForm, EquipmentCategoryForm
from models.department import Department
from models.equipment import Equipment, EquipmentCategory
from models.roles import (
    PERM_CATEGORY_MANAGE,
    PERM_DEPARTMENT_MANAGE,
    PERM_EQUIPMENT_VIEW,
)
from routes.decorators import permission_required
from services import audit_service
from services.errors import DuplicateError

departments_bp = Blueprint("departments", __name__, url_prefix="/departments")


@departments_bp.route("/")
@permission_required(PERM_EQUIPMENT_VIEW)
def index():
    """List departments with their equipment totals."""
    form = DepartmentFilterForm(request.args)
    search = (request.args.get("search") or "").strip()

    stmt = (
        select(Department, func.count(Equipment.id))
        .join(Equipment, Equipment.department_id == Department.id, isouter=True)
        .group_by(Department.id)
        .order_by(Department.name)
    )
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(Department.name.ilike(pattern), Department.location.ilike(pattern))
        )
    rows = db.session.execute(stmt).all()

    return render_template(
        "departments/list.html",
        rows=rows,
        form=form,
        search=search,
        total_equipment=db.session.scalar(select(func.count(Equipment.id))) or 0,
    )


@departments_bp.route("/new", methods=["GET", "POST"])
@permission_required(PERM_DEPARTMENT_MANAGE)
def create():
    """Create a department."""
    form = DepartmentForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        existing = db.session.scalars(
            select(Department).where(func.lower(Department.name) == name.lower())
        ).first()
        if existing is not None:
            flash(f"A department named '{name}' already exists.", "error")
        else:
            department = Department(
                name=name,
                description=(form.description.data or "").strip() or None,
                location=(form.location.data or "").strip() or None,
            )
            db.session.add(department)
            db.session.flush()
            audit_service.AuditService.log(
                current_user,
                audit_service.ACTION_CREATE,
                "department",
                department.id,
                f"{current_user.role_label} created department {department.name}.",
            )
            db.session.commit()
            flash(f"Department '{department.name}' created.", "success")
            return redirect(url_for("departments.index"))

    return render_template("departments/form.html", form=form, department=None)


@departments_bp.route("/<int:department_id>/edit", methods=["GET", "POST"])
@permission_required(PERM_DEPARTMENT_MANAGE)
def edit(department_id: int):
    """Rename / re-describe a department."""
    department = db.session.get(Department, department_id)
    if department is None:
        abort(404)

    form = DepartmentForm(obj=None)
    if form.validate_on_submit():
        name = form.name.data.strip()
        clash = db.session.scalars(
            select(Department).where(func.lower(Department.name) == name.lower())
        ).first()
        if clash is not None and clash.id != department.id:
            flash(f"Another department already uses the name '{name}'.", "error")
        else:
            previous = department.name
            department.name = name
            department.description = (form.description.data or "").strip() or None
            department.location = (form.location.data or "").strip() or None
            audit_service.AuditService.log(
                current_user,
                audit_service.ACTION_UPDATE,
                "department",
                department.id,
                f"{current_user.role_label} updated department {previous}"
                + (f" (renamed to {name})." if previous != name else "."),
            )
            db.session.commit()
            flash("Department updated.", "success")
            return redirect(url_for("departments.index"))
    elif request.method == "GET":
        form.load_department(department)

    return render_template("departments/form.html", form=form, department=department)


# ------------------------------------------------------------ categories
@departments_bp.route("/categories")
@permission_required(PERM_EQUIPMENT_VIEW)
def categories():
    """Equipment-type catalogue used by the registration form."""
    items = db.session.scalars(
        select(EquipmentCategory).order_by(EquipmentCategory.name)
    ).all()
    counts = dict(
        db.session.execute(
            select(Equipment.equipment_type, func.count(Equipment.id)).group_by(
                Equipment.equipment_type
            )
        ).all()
    )
    return render_template(
        "departments/categories.html",
        items=items,
        counts=counts,
        form=EquipmentCategoryForm(),
    )


@departments_bp.route("/categories/new", methods=["POST"])
@permission_required(PERM_CATEGORY_MANAGE)
def create_category():
    """Add an equipment type."""
    form = EquipmentCategoryForm()
    if not form.validate_on_submit():
        flash("Enter a valid equipment type name.", "error")
        return redirect(url_for("departments.categories"))

    name = form.name.data.strip()
    existing = db.session.scalars(
        select(EquipmentCategory).where(func.lower(EquipmentCategory.name) == name.lower())
    ).first()
    if existing is not None:
        flash(f"'{name}' is already in the equipment type catalogue.", "error")
        return redirect(url_for("departments.categories"))

    category = EquipmentCategory(
        name=name, description=(form.description.data or "").strip() or None
    )
    db.session.add(category)
    db.session.flush()
    audit_service.AuditService.log(
        current_user,
        audit_service.ACTION_CREATE,
        "equipment_category",
        category.id,
        f"{current_user.role_label} added equipment type {category.name}.",
    )
    db.session.commit()
    flash(f"Equipment type '{category.name}' added.", "success")
    return redirect(url_for("departments.categories"))
