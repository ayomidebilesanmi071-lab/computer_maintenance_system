"""Equipment inventory forms: registration, editing and filtering."""

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional, Regexp

from forms.base import (
    ChoiceFormMixin,
    FilterFormMixin,
    category_choices,
    department_choices,
    department_filter_choices,
    user_choices,
)
from models.constants import CONDITIONS, EQUIPMENT_TYPES, OPERATIONAL_STATUSES

# Asset tags are matched case-insensitively by the service layer, so the form
# only needs to guarantee a sane character set.
ASSET_TAG_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9\-_/]{1,63}$"


class EquipmentForm(ChoiceFormMixin, FlaskForm):
    """Register or edit an equipment record."""

    populated_choice_fields = ("equipment_type", "department_id", "assigned_user_id")

    asset_tag = StringField(
        "Asset tag",
        validators=[
            DataRequired(message="Asset tag is required."),
            Length(min=2, max=64),
            Regexp(
                ASSET_TAG_PATTERN,
                message="Use letters, numbers, hyphens, underscores or slashes.",
            ),
        ],
        render_kw={"placeholder": "e.g. ICT-001"},
    )
    equipment_name = StringField(
        "Equipment name",
        validators=[DataRequired(message="Equipment name is required."), Length(max=150)],
        render_kw={"placeholder": "e.g. HP ProDesk 400 G7 Desktop Computer"},
    )
    equipment_type = SelectField(
        "Equipment type", coerce=str, validators=[DataRequired()]
    )
    manufacturer = StringField("Manufacturer", validators=[Optional(), Length(max=100)])
    model = StringField("Model", validators=[Optional(), Length(max=100)])
    serial_number = StringField("Serial number", validators=[Optional(), Length(max=100)])
    department_id = SelectField(
        "Department", coerce=int, validators=[DataRequired(message="Select a department.")]
    )
    location = StringField(
        "Physical location",
        validators=[Optional(), Length(max=120)],
        render_kw={"placeholder": "e.g. ICT Lab, Room 12"},
    )
    purchase_date = DateField("Purchase date", validators=[Optional()])
    warranty_expiry_date = DateField("Warranty expiry date", validators=[Optional()])
    assigned_user_id = SelectField(
        "Assigned to (optional)", coerce=int, validators=[Optional()]
    )
    condition = SelectField(
        "Condition", choices=[(c, c) for c in CONDITIONS], validators=[DataRequired()]
    )
    operational_status = SelectField(
        "Operational status",
        choices=[(s, s) for s in OPERATIONAL_STATUSES],
        validators=[DataRequired()],
    )
    description = TextAreaField(
        "Description / notes", validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 3},
    )
    submit = SubmitField("Save equipment")

    # --- dynamic choices -------------------------------------------------
    def choices_for_equipment_type(self):
        choices = category_choices()
        return choices or [(name, name) for name in EQUIPMENT_TYPES]

    def choices_for_department_id(self):
        return [(0, "Select a department")] + department_choices()

    def choices_for_assigned_user_id(self):
        return [(0, "Unassigned / shared")] + user_choices()

    # --- helpers ----------------------------------------------------------
    def load_equipment(self, equipment) -> None:
        """Pre-fill the form from an existing record (GET request)."""
        self.asset_tag.data = equipment.asset_tag
        self.equipment_name.data = equipment.equipment_name
        self.equipment_type.data = equipment.equipment_type
        self.manufacturer.data = equipment.manufacturer
        self.model.data = equipment.model
        self.serial_number.data = equipment.serial_number
        self.department_id.data = equipment.department_id
        self.location.data = equipment.location
        self.purchase_date.data = equipment.purchase_date
        self.warranty_expiry_date.data = equipment.warranty_expiry_date
        self.assigned_user_id.data = equipment.assigned_user_id or 0
        self.condition.data = equipment.condition
        self.operational_status.data = equipment.operational_status
        self.description.data = equipment.description

    def to_data(self) -> dict:
        """Return the payload the equipment service expects."""
        return {
            "asset_tag": self.asset_tag.data,
            "equipment_name": self.equipment_name.data,
            "equipment_type": self.equipment_type.data,
            "manufacturer": self.manufacturer.data,
            "model": self.model.data,
            "serial_number": self.serial_number.data,
            "department_id": self.department_id.data,
            "location": self.location.data,
            "purchase_date": self.purchase_date.data,
            "warranty_expiry_date": self.warranty_expiry_date.data,
            "assigned_user_id": self.assigned_user_id.data or None,
            "condition": self.condition.data,
            "operational_status": self.operational_status.data,
            "description": self.description.data,
        }


class EquipmentStatusForm(FlaskForm):
    """Change an asset's condition and/or operational status."""

    condition = SelectField(
        "Condition", choices=[(c, c) for c in CONDITIONS], validators=[DataRequired()]
    )
    operational_status = SelectField(
        "Operational status",
        choices=[(s, s) for s in OPERATIONAL_STATUSES],
        validators=[DataRequired()],
    )
    notes = StringField(
        "Reason for the change",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "e.g. Fault confirmed by ICT officer"},
    )
    submit = SubmitField("Update status")

    def load_equipment(self, equipment) -> None:
        self.condition.data = equipment.condition
        self.operational_status.data = equipment.operational_status


class RetireEquipmentForm(FlaskForm):
    """Confirmation form for retiring (never deleting) an asset."""

    reason = StringField(
        "Reason for retirement",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "e.g. Beyond economical repair"},
    )
    confirm = SelectField(
        "Confirm retirement",
        choices=[("no", "No, keep the record active"), ("yes", "Yes, retire this equipment")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Retire equipment")


class EquipmentFilterForm(FilterFormMixin, ChoiceFormMixin, FlaskForm):
    """Search / filter controls for the inventory list (GET, no CSRF)."""

    populated_choice_fields = ("equipment_type", "department_id")

    search = StringField(
        "Search",
        render_kw={"placeholder": "Asset tag, name, serial, manufacturer or model"},
    )
    equipment_type = SelectField("Equipment type", coerce=str)
    department_id = SelectField("Department", coerce=int)
    location = StringField("Location", render_kw={"placeholder": "e.g. Room 12"})
    condition = SelectField("Condition", choices=[("", "All conditions")] +
                            [(c, c) for c in CONDITIONS], coerce=str)
    operational_status = SelectField(
        "Operational status",
        choices=[("", "All statuses")] + [(s, s) for s in OPERATIONAL_STATUSES],
        coerce=str,
    )
    warranty = SelectField(
        "Warranty",
        choices=[
            ("", "Any warranty state"),
            ("active", "Under warranty"),
            ("expired", "Warranty expired"),
            ("missing", "No warranty recorded"),
        ],
        coerce=str,
    )
    date_from = DateField("Purchased from", validators=[Optional()])
    date_to = DateField("Purchased to", validators=[Optional()])
    submit = SubmitField("Apply filters")

    def choices_for_equipment_type(self):
        choices = category_choices()
        return [("", "All types")] + (choices or [(n, n) for n in EQUIPMENT_TYPES])

    def choices_for_department_id(self):
        return department_filter_choices()
