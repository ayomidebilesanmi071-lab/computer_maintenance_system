"""Department and equipment-category (master data) forms."""

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class DepartmentForm(FlaskForm):
    """Create or rename a department."""

    name = StringField(
        "Department name",
        validators=[
            DataRequired(message="Department name is required."),
            Length(min=2, max=120),
        ],
        render_kw={"placeholder": "e.g. Accounts Department"},
    )
    description = TextAreaField(
        "Description", validators=[Optional(), Length(max=255)],
        render_kw={"rows": 2},
    )
    location = StringField(
        "Usual location",
        validators=[Optional(), Length(max=120)],
        render_kw={"placeholder": "e.g. Second floor, Main building"},
    )
    submit = SubmitField("Save department")

    def load_department(self, department) -> None:
        self.name.data = department.name
        self.description.data = department.description
        self.location.data = department.location


class EquipmentCategoryForm(FlaskForm):
    """Create an equipment type (required before equipment can use it)."""

    name = StringField(
        "Equipment type",
        validators=[
            DataRequired(message="Equipment type name is required."),
            Length(min=2, max=64),
        ],
        render_kw={"placeholder": "e.g. Tablet"},
    )
    description = StringField(
        "Description", validators=[Optional(), Length(max=255)]
    )
    submit = SubmitField("Save equipment type")


class DepartmentFilterForm(FlaskForm):
    """Search box for the department list (GET, no CSRF)."""

    class Meta(FlaskForm.Meta):
        csrf = False

    search = StringField("Search", render_kw={"placeholder": "Department name or location"})
    submit = SubmitField("Search")
