"""Report filter controls.

One filter form drives every report; each report view simply ignores the fields
that are not relevant to it, so users get a consistent control bar everywhere.
"""

from datetime import date, timedelta

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, SubmitField
from wtforms.validators import Optional

from forms.base import (
    ChoiceFormMixin,
    FilterFormMixin,
    category_choices,
    department_filter_choices,
    staff_choices,
)
from models.constants import (
    CONDITIONS,
    EQUIPMENT_TYPES,
    FAULT_CATEGORIES,
    FAULT_PRIORITIES,
    MAINTENANCE_OUTCOMES,
    MAINTENANCE_TYPES,
    OPERATIONAL_STATUSES,
    SCHEDULE_STATUSES,
)


class ReportFilterForm(FilterFormMixin, ChoiceFormMixin, FlaskForm):
    """Date range + department + status filters for all reports."""

    populated_choice_fields = ("department_id", "assigned_to", "equipment_type")

    date_from = DateField("From", validators=[Optional()])
    date_to = DateField("To", validators=[Optional()])
    department_id = SelectField("Department", coerce=int)
    equipment_type = SelectField("Equipment type", coerce=str)
    condition = SelectField(
        "Condition", choices=[("", "All conditions")] + [(c, c) for c in CONDITIONS],
        coerce=str,
    )
    operational_status = SelectField(
        "Operational status",
        choices=[("", "All statuses")] + [(s, s) for s in OPERATIONAL_STATUSES],
        coerce=str,
    )
    fault_category = SelectField(
        "Fault category",
        choices=[("", "All categories")] + [(c, c) for c in FAULT_CATEGORIES],
        coerce=str,
    )
    priority = SelectField(
        "Priority",
        choices=[("", "All priorities")] + [(p, p) for p in FAULT_PRIORITIES],
        coerce=str,
    )
    fault_status = SelectField(
        "Fault status",
        choices=[("", "All statuses")]
        + [(s, s) for s in ("Reported", "Acknowledged", "Under Repair",
                            "Awaiting Parts", "Resolved", "Closed")],
        coerce=str,
    )
    maintenance_type = SelectField(
        "Maintenance type",
        choices=[("", "All types")] + [(t, t) for t in MAINTENANCE_TYPES],
        coerce=str,
    )
    outcome = SelectField(
        "Maintenance outcome",
        choices=[("", "All outcomes")] + [(o, o) for o in MAINTENANCE_OUTCOMES],
        coerce=str,
    )
    schedule_status = SelectField(
        "Schedule status",
        choices=[("", "All statuses")] + [(s, s) for s in SCHEDULE_STATUSES],
        coerce=str,
    )
    assigned_to = SelectField("Assigned officer", coerce=int)
    submit = SubmitField("Generate report")

    def choices_for_department_id(self):
        return department_filter_choices()

    def choices_for_assigned_to(self):
        return [(0, "Any officer")] + staff_choices()

    def choices_for_equipment_type(self):
        choices = category_choices()
        return [("", "All types")] + (choices or [(name, name) for name in EQUIPMENT_TYPES])

    # --- convenience ------------------------------------------------------
    def set_default_period(self, days: int = 30) -> None:
        """Pre-fill a sensible date range when the user supplies none."""
        if not self.date_from.data:
            self.date_from.data = date.today() - timedelta(days=days)
        if not self.date_to.data:
            self.date_to.data = date.today()

    def equipment_filters(self) -> dict:
        return {
            key: value
            for key, value in self.to_filters().items()
            if key in {"department_id", "equipment_type", "condition",
                       "operational_status", "date_from", "date_to"}
        }

    def fault_filters(self) -> dict:
        data = self.to_filters()
        if data.get("fault_status"):
            data["status"] = data.pop("fault_status")
        return {
            key: value
            for key, value in data.items()
            if key in {"status", "priority", "fault_category", "department_id",
                       "assigned_to", "date_from", "date_to"}
        }

    def maintenance_filters(self) -> dict:
        data = self.to_filters()
        # The form exposes one officer dropdown; the maintenance service calls
        # that column ``technician_id``.
        if data.get("assigned_to"):
            data["technician_id"] = data.pop("assigned_to")
        return {
            key: value
            for key, value in data.items()
            if key in {"maintenance_type", "outcome", "department_id",
                       "technician_id", "date_from", "date_to"}
        }

    def schedule_filters(self) -> dict:
        data = self.to_filters()
        if data.get("schedule_status"):
            data["status"] = data.pop("schedule_status")
        return {
            key: value
            for key, value in data.items()
            if key in {"status", "department_id", "assigned_to",
                       "date_from", "date_to"}
        }
