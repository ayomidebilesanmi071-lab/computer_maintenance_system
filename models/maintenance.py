"""Maintenance and preventive-scheduling models.

``MaintenanceRecord`` documents work that was actually performed, while
``MaintenanceSchedule`` represents planned (preventive) work.  Both link back to
the equipment so a full service history can always be replayed.
"""

from datetime import datetime, timezone

from extensions import db
from models.constants import SCHEDULE_COMPLETED


def _utcnow():
    return datetime.now(timezone.utc)


class MaintenanceRecord(db.Model):
    """Work performed on an equipment item (repair, inspection, service)."""

    __tablename__ = "maintenance_records"

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(
        db.Integer,
        db.ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fault_report_id = db.Column(
        db.Integer, db.ForeignKey("fault_reports.id"), index=True
    )
    maintenance_type = db.Column(db.String(50), nullable=False)
    diagnosis = db.Column(db.Text)
    work_performed = db.Column(db.Text, nullable=False)
    parts_replaced = db.Column(db.String(255))
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    maintenance_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time)
    completion_time = db.Column(db.Time)
    cost = db.Column(db.Numeric(12, 2))
    condition_after = db.Column(db.String(20))
    outcome = db.Column(db.String(60), nullable=False)
    notes = db.Column(db.Text)
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey("maintenance_schedules.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    equipment = db.relationship(
        "Equipment", back_populates="maintenance_records", lazy="joined"
    )
    fault_report = db.relationship(
        "FaultReport", back_populates="maintenance_records", lazy="select"
    )
    technician = db.relationship(
        "User",
        foreign_keys=[technician_id],
        back_populates="maintenance_performed",
        lazy="select",
    )
    recorder = db.relationship(
        "User",
        foreign_keys=[recorded_by],
        back_populates="maintenance_recorded",
        lazy="select",
    )
    schedule = db.relationship(
        "MaintenanceSchedule", back_populates="maintenance_record", uselist=False
    )

    # --- Behaviour ----------------------------------------------------------
    @property
    def cost_display(self) -> str:
        if self.cost in (None, ""):
            return "—"
        return f"₦{float(self.cost):,.2f}"

    @property
    def technician_name(self) -> str:
        return self.technician.full_name if self.technician else "Unknown"

    @property
    def duration_display(self) -> str:
        if self.start_time and self.completion_time:
            return f"{self.start_time.strftime('%H:%M')} – {self.completion_time.strftime('%H:%M')}"
        return "—"

    @property
    def is_successful(self) -> bool:
        return self.outcome.startswith("Completed")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MaintenanceRecord #{self.id} {self.maintenance_type}>"


class MaintenanceSchedule(db.Model):
    """A planned (usually preventive) maintenance activity."""

    __tablename__ = "maintenance_schedules"

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(
        db.Integer,
        db.ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    maintenance_type = db.Column(db.String(50), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    instructions = db.Column(db.Text)
    status = db.Column(db.String(30), nullable=False, default="Scheduled", index=True)
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    equipment = db.relationship(
        "Equipment", back_populates="maintenance_schedules", lazy="joined"
    )
    assignee = db.relationship(
        "User",
        foreign_keys=[assigned_to],
        back_populates="assigned_schedules",
        lazy="select",
    )
    creator = db.relationship("User", foreign_keys=[created_by], lazy="select")
    maintenance_record = db.relationship(
        "MaintenanceRecord",
        back_populates="schedule",
        uselist=False,
        lazy="select",
    )

    # --- Behaviour ----------------------------------------------------------
    @property
    def is_completed(self) -> bool:
        return self.status == SCHEDULE_COMPLETED

    @property
    def assignee_name(self) -> str:
        return self.assignee.full_name if self.assignee else "Unassigned"

    @property
    def days_until(self) -> int:
        """Negative when the scheduled date is in the past."""
        from datetime import date

        return (self.scheduled_date - date.today()).days

    def mark_completed(self, notes: str = "") -> bool:
        """Flip the schedule to Completed (idempotent)."""
        if self.status == SCHEDULE_COMPLETED:
            return False
        self.status = SCHEDULE_COMPLETED
        self.completed_at = _utcnow()
        if notes:
            self.notes = notes
        return True

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MaintenanceSchedule #{self.id} {self.status}>"
