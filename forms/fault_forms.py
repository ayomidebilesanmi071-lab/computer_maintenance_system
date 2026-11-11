"""Fault reporting forms: creation, workflow actions and filtering."""

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    FileField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional

from forms.base import (
    ChoiceFormMixin,
    FilterFormMixin,
    department_filter_choices,
    equipment_choices,
    staff_choices,
)
from models.constants import (
    FAULT_CATEGORIES,
    FAULT_PRIORITIES,
    FAULT_STATUSES,
)


class FaultForm(ChoiceFormMixin, FlaskForm):
    """Record a new fault against an existing piece of equipment."""

    populated_choice_fields = (
        "equipment_id",
        "assigned_to",
        "fault_category",
    )

    equipment_id = SelectField(
        "Affected equipment",
        coerce=int,
        validators=[DataRequired(message="Select the affected equipment.")],
    )
    fault_title = StringField(
        "Fault title",
        validators=[DataRequired(message="Fault title is required."), Length(max=150)],
        render_kw={"placeholder": "e.g. Desktop will not power on"},
    )
    fault_description = TextAreaField(
        "Fault description",
        validators=[
            DataRequired(message="Describe the fault."),
            Length(min=10, max=4000, message="Give at least 10 characters of detail."),
        ],
        render_kw={"rows": 5,
                   "placeholder": "Describe what happens, what you tried and any error messages."},
    )
    fault_category = SelectField(
        "Fault category", coerce=str, validators=[DataRequired()]
    )
    priority = SelectField(
        "Priority",
        choices=[(p, p) for p in FAULT_PRIORITIES],
        validators=[DataRequired()],
    )
    date_discovered = DateField(
        "Date discovered", validators=[DataRequired(message="Enter the date discovered.")]
    )
    assigned_to = SelectField(
        "Assign to ICT officer (optional)", coerce=int, validators=[Optional()]
    )
    attachment = FileField(
        "Supporting document (optional)",
        validators=[Optional()],
    )
    submit = SubmitField("Submit fault report")

    def choices_for_equipment_id(self):
        return [(0, "Select equipment")] + equipment_choices(pending_only=True)

    def choices_for_assigned_to(self):
        return [(0, "Leave unassigned")] + staff_choices()

    def choices_for_fault_category(self):
        return [(category, category) for category in FAULT_CATEGORIES]

    def to_data(self) -> dict:
        return {
            "equipment_id": self.equipment_id.data,
            "fault_title": self.fault_title.data,
            "fault_description": self.fault_description.data,
            "fault_category": self.fault_category.data,
            "priority": self.priority.data,
            "date_discovered": self.date_discovered.data,
            "assigned_to": self.assigned_to.data or None,
        }


class AssignFaultForm(ChoiceFormMixin, FlaskForm):
    """Assign (or unassign) a fault."""

    populated_choice_fields = ("assigned_to",)

    assigned_to = SelectField(
        "Assign to", coerce=int, validators=[DataRequired(message="Choose an officer.")]
    )
    notes = StringField("Assignment note (optional)", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Assign fault")

    def choices_for_assigned_to(self):
        return [(0, "Unassign")] + staff_choices()


class FaultPriorityForm(FlaskForm):
    """Change the priority of a fault."""

    priority = SelectField(
        "Priority",
        choices=[(p, p) for p in FAULT_PRIORITIES],
        validators=[DataRequired()],
    )
    notes = StringField("Reason (optional)", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Update priority")


class FaultStatusForm(FlaskForm):
    """Move a fault to another status.

    The choices are replaced per-fault by the route so only legal transitions
    are offered; the service layer re-checks the state machine regardless.
    """

    status = SelectField("New status", coerce=str, validators=[DataRequired()])
    resolution_notes = TextAreaField(
        "Resolution / change notes",
        validators=[Optional(), Length(max=4000)],
        render_kw={"rows": 3,
                   "placeholder": "Required when resolving a fault."},
    )
    submit = SubmitField("Update status")

    def load_transitions(self, fault) -> None:
        self.status.choices = [(status, status) for status in fault.available_transitions()]


class FaultNoteForm(FlaskForm):
    """Add an investigation / troubleshooting note."""

    body = TextAreaField(
        "Troubleshooting note",
        validators=[
            DataRequired(message="Enter the note."),
            Length(min=3, max=4000),
        ],
        render_kw={"rows": 3,
                   "placeholder": "What was investigated, tested or observed?"},
    )
    submit = SubmitField("Add note")


class FaultResolutionForm(FlaskForm):
    """Record resolution notes without changing the status."""

    resolution_notes = TextAreaField(
        "Resolution notes",
        validators=[
            DataRequired(message="Enter the resolution details."),
            Length(min=5, max=4000),
        ],
        render_kw={"rows": 3},
    )
    submit = SubmitField("Save resolution notes")


class FaultFilterForm(FilterFormMixin, ChoiceFormMixin, FlaskForm):
    """Search / filter controls for the fault list (GET, no CSRF)."""

    populated_choice_fields = ("department_id", "assigned_to")

    search = StringField(
        "Search",
        render_kw={"placeholder": "Reference, title, asset tag or equipment name"},
    )
    status = SelectField(
        "Status",
        choices=[("", "All statuses")] + [(s, s) for s in FAULT_STATUSES],
        coerce=str,
    )
    priority = SelectField(
        "Priority",
        choices=[("", "All priorities")] + [(p, p) for p in FAULT_PRIORITIES],
        coerce=str,
    )
    fault_category = SelectField(
        "Fault category",
        choices=[("", "All categories")] + [(c, c) for c in FAULT_CATEGORIES],
        coerce=str,
    )
    department_id = SelectField("Department", coerce=int)
    assigned_to = SelectField("Assigned officer", coerce=int)
    date_from = DateField("Reported from", validators=[Optional()])
    date_to = DateField("Reported to", validators=[Optional()])
    submit = SubmitField("Apply filters")

    def choices_for_department_id(self):
        return department_filter_choices()

    def choices_for_assigned_to(self):
        return [(0, "Any officer")] + staff_choices()
