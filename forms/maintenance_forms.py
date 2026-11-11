"""Maintenance record and preventive-schedule forms."""

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from forms.base import (
    ChoiceFormMixin,
    FilterFormMixin,
    department_filter_choices,
    equipment_choices,
    staff_choices,
)
from models.constants import (
    CONDITIONS,
    MAINTENANCE_OUTCOMES,
    MAINTENANCE_TYPES,
    SCHEDULE_STATUSES,
)


class MaintenanceForm(ChoiceFormMixin, FlaskForm):
    """Record maintenance / repair work that was carried out."""

    populated_choice_fields = ("equipment_id", "fault_report_id", "technician_id")

    equipment_id = SelectField(
        "Equipment",
        coerce=int,
        validators=[DataRequired(message="Select the equipment.")],
    )
    fault_report_id = SelectField(
        "Related fault report (optional)", coerce=int, validators=[Optional()]
    )
    maintenance_type = SelectField(
        "Maintenance type",
        choices=[(t, t) for t in MAINTENANCE_TYPES],
        validators=[DataRequired()],
    )
    maintenance_date = DateField(
        "Date of maintenance",
        validators=[DataRequired(message="Enter the maintenance date.")],
    )
    start_time = TimeField("Start time (optional)", validators=[Optional()])
    completion_time = TimeField("Completion time (optional)", validators=[Optional()])
    technician_id = SelectField(
        "Technician", coerce=int, validators=[DataRequired(message="Select the technician.")]
    )
    diagnosis = TextAreaField(
        "Diagnosis / problem found",
        validators=[Optional(), Length(max=4000)],
        render_kw={"rows": 3},
    )
    work_performed = TextAreaField(
        "Work performed",
        validators=[
            DataRequired(message="Describe the work performed."),
            Length(min=5, max=4000, message="Give at least 5 characters of detail."),
        ],
        render_kw={"rows": 4},
    )
    parts_replaced = StringField("Parts replaced", validators=[Optional(), Length(max=255)])
    cost = DecimalField(
        "Cost (optional)",
        places=2,
        validators=[Optional(), NumberRange(min=0, message="Cost cannot be negative.")],
    )
    condition_after = SelectField(
        "Equipment condition after maintenance",
        choices=[(c, c) for c in CONDITIONS],
        validators=[Optional()],
    )
    outcome = SelectField(
        "Maintenance outcome",
        choices=[(o, o) for o in MAINTENANCE_OUTCOMES],
        validators=[DataRequired()],
    )
    notes = TextAreaField("Additional notes", validators=[Optional(), Length(max=4000)],
                          render_kw={"rows": 2})
    submit = SubmitField("Save maintenance record")

    def choices_for_equipment_id(self):
        return [(0, "Select equipment")] + equipment_choices()

    def choices_for_fault_report_id(self):
        from sqlalchemy import select

        from extensions import db
        from models.fault import FaultReport

        rows = db.session.scalars(
            select(FaultReport).order_by(FaultReport.created_at.desc()).limit(200)
        ).all()
        return [(0, "Not linked to a fault")] + [
            (row.id, f"{row.reference_number} - {row.fault_title}") for row in rows
        ]

    def choices_for_technician_id(self):
        return [(0, "Select technician")] + staff_choices()

    def to_data(self) -> dict:
        return {
            "equipment_id": self.equipment_id.data,
            "fault_report_id": self.fault_report_id.data or None,
            "maintenance_type": self.maintenance_type.data,
            "maintenance_date": self.maintenance_date.data,
            "start_time": self.start_time.data,
            "completion_time": self.completion_time.data,
            "technician_id": self.technician_id.data,
            "diagnosis": self.diagnosis.data,
            "work_performed": self.work_performed.data,
            "parts_replaced": self.parts_replaced.data,
            "cost": self.cost.data,
            "condition_after": self.condition_after.data,
            "outcome": self.outcome.data,
            "notes": self.notes.data,
        }

    def load_record(self, record) -> None:
        self.equipment_id.data = record.equipment_id
        self.fault_report_id.data = record.fault_report_id or 0
        self.maintenance_type.data = record.maintenance_type
        self.maintenance_date.data = record.maintenance_date
        self.start_time.data = record.start_time
        self.completion_time.data = record.completion_time
        self.technician_id.data = record.technician_id
        self.diagnosis.data = record.diagnosis
        self.work_performed.data = record.work_performed
        self.parts_replaced.data = record.parts_replaced
        self.cost.data = record.cost
        self.condition_after.data = record.condition_after or record.equipment.condition
        self.outcome.data = record.outcome
        self.notes.data = record.notes


class ScheduleForm(ChoiceFormMixin, FlaskForm):
    """Create or edit a preventive-maintenance schedule."""

    populated_choice_fields = ("equipment_id", "assigned_to")

    equipment_id = SelectField(
        "Equipment",
        coerce=int,
        validators=[DataRequired(message="Select the equipment.")],
    )
    maintenance_type = SelectField(
        "Maintenance type",
        choices=[(t, t) for t in MAINTENANCE_TYPES],
        validators=[DataRequired()],
    )
    scheduled_date = DateField(
        "Scheduled date",
        validators=[DataRequired(message="Enter the scheduled date.")],
    )
    assigned_to = SelectField(
        "Assigned officer",
        coerce=int,
        validators=[DataRequired(message="Select the responsible officer.")],
    )
    instructions = TextAreaField(
        "Instructions",
        validators=[Optional(), Length(max=4000)],
        render_kw={"rows": 3,
                   "placeholder": "e.g. Blow out dust, check fan speeds, run disk diagnostics."},
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=4000)],
                          render_kw={"rows": 2})
    submit = SubmitField("Save schedule")

    def choices_for_equipment_id(self):
        return [(0, "Select equipment")] + equipment_choices(pending_only=True)

    def choices_for_assigned_to(self):
        return [(0, "Select officer")] + staff_choices()

    def to_data(self) -> dict:
        return {
            "equipment_id": self.equipment_id.data,
            "maintenance_type": self.maintenance_type.data,
            "scheduled_date": self.scheduled_date.data,
            "assigned_to": self.assigned_to.data,
            "instructions": self.instructions.data,
            "notes": self.notes.data,
        }

    def load_schedule(self, schedule) -> None:
        self.equipment_id.data = schedule.equipment_id
        self.maintenance_type.data = schedule.maintenance_type
        self.scheduled_date.data = schedule.scheduled_date
        self.assigned_to.data = schedule.assigned_to
        self.instructions.data = schedule.instructions
        self.notes.data = schedule.notes


class CompleteScheduleForm(FlaskForm):
    """Complete a schedule, optionally recording the maintenance entry."""

    maintenance_date = DateField(
        "Completion date",
        validators=[DataRequired(message="Enter the completion date.")],
    )
    outcome = SelectField(
        "Outcome",
        choices=[(o, o) for o in MAINTENANCE_OUTCOMES],
        validators=[DataRequired()],
    )
    work_performed = TextAreaField(
        "Work performed",
        validators=[Optional(), Length(max=4000)],
        render_kw={"rows": 3,
                   "placeholder": "Leave blank to reuse the schedule instructions."},
    )
    cost = DecimalField(
        "Cost (optional)",
        places=2,
        validators=[Optional(), NumberRange(min=0)],
    )
    record_maintenance = SelectField(
        "Create a maintenance record",
        choices=[("yes", "Yes - record this service in the maintenance history"),
                 ("no", "No - just mark the schedule complete")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Complete schedule")


class ScheduleStatusForm(FlaskForm):
    """Change a schedule's status (mark in progress / cancel)."""

    status = SelectField(
        "Schedule status",
        choices=[(s, s) for s in SCHEDULE_STATUSES],
        validators=[DataRequired()],
    )
    notes = StringField("Reason (optional)", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Update schedule")


class MaintenanceFilterForm(FilterFormMixin, ChoiceFormMixin, FlaskForm):
    """Filter controls for the maintenance history list."""

    populated_choice_fields = ("department_id", "technician_id")

    search = StringField(
        "Search",
        render_kw={"placeholder": "Asset tag, equipment name or work performed"},
    )
    maintenance_type = SelectField(
        "Maintenance type",
        choices=[("", "All types")] + [(t, t) for t in MAINTENANCE_TYPES],
        coerce=str,
    )
    outcome = SelectField(
        "Outcome",
        choices=[("", "All outcomes")] + [(o, o) for o in MAINTENANCE_OUTCOMES],
        coerce=str,
    )
    department_id = SelectField("Department", coerce=int)
    technician_id = SelectField("Technician", coerce=int)
    date_from = DateField("From", validators=[Optional()])
    date_to = DateField("To", validators=[Optional()])
    submit = SubmitField("Apply filters")

    def choices_for_department_id(self):
        return department_filter_choices()

    def choices_for_technician_id(self):
        return [(0, "Any technician")] + staff_choices()


class ScheduleFilterForm(FilterFormMixin, ChoiceFormMixin, FlaskForm):
    """Filter controls for the preventive-maintenance schedule list."""

    populated_choice_fields = ("department_id", "assigned_to")

    search = StringField(
        "Search", render_kw={"placeholder": "Asset tag or equipment name"}
    )
    status = SelectField(
        "Schedule status",
        choices=[("", "All statuses")] + [(s, s) for s in SCHEDULE_STATUSES],
        coerce=str,
    )
    department_id = SelectField("Department", coerce=int)
    assigned_to = SelectField("Assigned officer", coerce=int)
    date_from = DateField("Scheduled from", validators=[Optional()])
    date_to = DateField("Scheduled to", validators=[Optional()])
    submit = SubmitField("Apply filters")

    def choices_for_department_id(self):
        return department_filter_choices()

    def choices_for_assigned_to(self):
        return [(0, "Any officer")] + staff_choices()
