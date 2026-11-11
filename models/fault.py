"""Fault reporting models.

``FaultReport`` owns the lifecycle of a reported problem, while
``FaultStatusHistory`` records every status transition (who, when, why) and
``FaultNote`` stores investigation / troubleshooting entries.
"""

from datetime import datetime, timezone

from extensions import db
from models.constants import (
    FAULT_REPORTED,
    FAULT_STATUS_TRANSITIONS,
    OPEN_FAULT_STATUSES,
)


def _utcnow():
    return datetime.now(timezone.utc)


class FaultReport(db.Model):
    """A problem reported against a piece of equipment."""

    __tablename__ = "fault_reports"

    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(32), nullable=False, unique=True, index=True)
    equipment_id = db.Column(
        db.Integer,
        db.ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reported_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    fault_title = db.Column(db.String(150), nullable=False)
    fault_description = db.Column(db.Text, nullable=False)
    fault_category = db.Column(db.String(64), nullable=False, index=True)
    priority = db.Column(db.String(20), nullable=False, default="Medium", index=True)
    status = db.Column(db.String(30), nullable=False, default=FAULT_REPORTED, index=True)
    date_discovered = db.Column(db.Date, nullable=False)
    resolution_notes = db.Column(db.Text)
    # Optional supporting document (screenshot / PDF).  Stored under
    # instance/uploads and never inside the static asset tree.
    attachment_filename = db.Column(db.String(255))
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # --- Relationships ------------------------------------------------------
    equipment = db.relationship(
        "Equipment", back_populates="fault_reports", lazy="joined"
    )
    reporter = db.relationship(
        "User",
        foreign_keys=[reported_by],
        back_populates="reported_faults",
        lazy="select",
    )
    assignee = db.relationship(
        "User",
        foreign_keys=[assigned_to],
        back_populates="assigned_faults",
        lazy="select",
    )
    status_history = db.relationship(
        "FaultStatusHistory",
        back_populates="fault",
        lazy="select",
        order_by="FaultStatusHistory.changed_at.asc()",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notes = db.relationship(
        "FaultNote",
        back_populates="fault",
        lazy="select",
        order_by="FaultNote.created_at.asc()",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    maintenance_records = db.relationship(
        "MaintenanceRecord",
        back_populates="fault_report",
        lazy="select",
        order_by="MaintenanceRecord.maintenance_date.desc()",
    )

    # --- Behaviour ----------------------------------------------------------
    @property
    def is_open(self) -> bool:
        return self.status in OPEN_FAULT_STATUSES

    @property
    def is_resolved(self) -> bool:
        return self.status in {"Resolved", "Closed"}

    @property
    def assignee_name(self) -> str:
        return self.assignee.full_name if self.assignee else "Unassigned"

    @property
    def reporter_name(self) -> str:
        return self.reporter.full_name if self.reporter else "Unknown"

    @property
    def has_attachment(self) -> bool:
        return bool(self.attachment_filename)

    @property
    def days_open(self) -> int:
        """How long the fault has been outstanding (in days)."""
        from datetime import date, datetime, timezone

        end = self.resolved_at.date() if self.resolved_at else date.today()
        start = self.created_at.date() if isinstance(self.created_at, datetime) else self.date_discovered
        return max((end - start).days, 0)

    def can_transition_to(self, new_status: str) -> bool:
        """Enforce the state machine declared in ``models.constants``."""
        allowed = FAULT_STATUS_TRANSITIONS.get(self.status, ())
        return new_status in allowed

    def available_transitions(self) -> tuple:
        """Statuses this fault may move to next (drives the UI dropdown)."""
        return FAULT_STATUS_TRANSITIONS.get(self.status, ())

    def apply_status(self, new_status: str) -> bool:
        """Move to ``new_status``.  Returns ``False`` if already there.

        The caller (service layer) is responsible for persisting the matching
        :class:`FaultStatusHistory` row - see
        ``services.fault_service.FaultService.change_status``.
        """
        if new_status == self.status:
            return False
        self.status = new_status
        if new_status == "Resolved":
            self.resolved_at = _utcnow()
        return True

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FaultReport {self.reference_number} [{self.status}]>"


class FaultStatusHistory(db.Model):
    """Auditable record of every fault status change."""

    __tablename__ = "fault_status_history"

    id = db.Column(db.Integer, primary_key=True)
    fault_report_id = db.Column(
        db.Integer,
        db.ForeignKey("fault_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    change_notes = db.Column(db.String(500))
    changed_at = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)

    fault = db.relationship("FaultReport", back_populates="status_history")
    changer = db.relationship("User", foreign_keys=[changed_by], lazy="select")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<FaultStatusHistory {self.previous_status} -> {self.new_status}>"
        )


class FaultNote(db.Model):
    """An investigation / troubleshooting note attached to a fault."""

    __tablename__ = "fault_notes"

    id = db.Column(db.Integer, primary_key=True)
    fault_report_id = db.Column(
        db.Integer,
        db.ForeignKey("fault_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    fault = db.relationship("FaultReport", back_populates="notes")
    author = db.relationship("User", foreign_keys=[author_id], lazy="select")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FaultNote #{self.id} fault={self.fault_report_id}>"
