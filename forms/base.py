"""Shared helpers for the CMIMS form layer.

Forms are the *first* line of defence (they produce friendly messages), but
they are never the only one: every rule is re-checked in the service layer,
because a crafted POST can bypass the browser entirely.

The choice helpers below query the database for dropdown contents so no
department, officer or equipment type is ever hard-coded into a template.
"""

from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import SelectField

from extensions import db
from models.constants import ROLE_ADMIN, ROLE_OFFICER, ROLES, ROLE_LABELS
from models.department import Department
from models.equipment import Equipment, EquipmentCategory
from models.user import User


# --------------------------------------------------------------------- choices
def department_choices():
    """``[(id, name), ...]`` for every department, alphabetically."""
    rows = db.session.scalars(select(Department).order_by(Department.name)).all()
    return [(department.id, department.name) for department in rows]


def department_filter_choices(blank_label="All departments"):
    """Filter dropdown where ``0`` means 'no department filter'."""
    return [(0, blank_label)] + department_choices()


def category_choices():
    rows = db.session.scalars(
        select(EquipmentCategory).order_by(EquipmentCategory.name)
    ).all()
    return [(row.name, row.name) for row in rows]


def staff_choices(officers_only=True, blank_label=None):
    """ICT officers (and administrators) available for assignment."""
    stmt = select(User).where(User.is_active.is_(True))
    if officers_only:
        stmt = stmt.where(User.role.in_((ROLE_OFFICER, ROLE_ADMIN)))
    rows = db.session.scalars(stmt.order_by(User.full_name)).all()
    return [(user.id, f"{user.full_name} ({user.role_label})") for user in rows]


def equipment_choices(pending_only=False, blank_label="Select equipment"):
    stmt = select(Equipment).order_by(Equipment.asset_tag)
    if pending_only:
        stmt = stmt.where(Equipment.operational_status != "Retired")
    rows = db.session.scalars(stmt).all()
    return [(row.id, f"{row.asset_tag} - {row.equipment_name}") for row in rows]


def user_choices(blank_label="Select a user"):
    rows = db.session.scalars(select(User).order_by(User.full_name)).all()
    return [(user.id, f"{user.full_name} ({user.role_label})") for user in rows]


def role_choices():
    return [(role, ROLE_LABELS.get(role, role)) for role in ROLES]


# ------------------------------------------------------------------ mixins
class ChoiceFormMixin:
    """Mixin for forms whose ``SelectField`` choices come from the database.

    Sub-classes list the fields they need populated in
    :attr:`populated_choice_fields`; ``__init__`` fills them from the live
    database so the dropdowns always match stored data.
    """

    populated_choice_fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.populated_choice_fields:
            field = self._fields.get(field_name)
            if field is None:
                continue
            choices = getattr(self, f"choices_for_{field_name}", None)
            if choices is not None:
                field.choices = choices()


class FilterFormMixin:
    """Mixin for read-only GET filter forms.

    * CSRF is disabled (nothing is mutated),
    * :meth:`to_filters` returns only the filters that were actually supplied,
      with blanks and zero sentinels removed, so services never receive
      meaningless values.
    """

    excluded_filter_fields = ("submit", "csrf_token")

    # Sub-classing FlaskForm.Meta keeps every other framework setting intact
    # while switching CSRF off: filter forms only ever issue GET requests.
    class Meta(FlaskForm.Meta):
        csrf = False

    def _blank_unsubmitted_choices(self) -> None:
        """Point every empty dropdown at its blank ("All ...") entry.

        A filter form is normally opened with no query string at all, so
        WTForms leaves every unset field at ``None``.  ``SelectField`` then
        fails its own choice check ("Not a valid choice") and the page would
        greet a plain visit with a bogus "invalid filters" warning.  The first
        entry of a filter dropdown is always its blank option, so use that.

        Called from :meth:`validate` rather than ``__init__`` because some
        sub-classes fill their choices after ``super().__init__()``.
        """
        for field in self._fields.values():
            if isinstance(field, SelectField) and not field.data and field.choices:
                field.data = field.choices[0][0]

    def validate(self, extra_validators=None):
        self._blank_unsubmitted_choices()
        return super().validate(extra_validators=extra_validators)

    def to_filters(self) -> dict:
        filters = {}
        for name, field in self._fields.items():
            if name in self.excluded_filter_fields or not field.data:
                continue
            filters[name] = field.data
        return filters
