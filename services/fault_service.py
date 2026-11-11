"""Fault reporting business logic.

Responsibilities kept here (not in the route handlers):

* generating unique reference numbers (``FR-2026-0001``),
* validating the status state machine and writing ``FaultStatusHistory``,
* assignment, priority changes and investigation notes,
* the rule that a fault cannot be resolved without an actual repair record.
"""

from datetime import date, datetime, timezone

from sqlalchemy import func, select

from extensions import db
from models.constants import (
    FAULT_RESOLVED,
    OPEN_FAULT_STATUSES,
)
from models.department import Department
from models.equipment import Equipment
from models.fault import FaultNote, FaultReport, FaultStatusHistory
from models.maintenance import MaintenanceRecord
from models.user import User
from services import audit_service
from services.errors import (
    NotFoundError,
    TransitionError,
    ValidationError,
)
from services.validation import coerce_date


def _utcnow():
    return datetime.now(timezone.utc)


class FaultService:
    """Domain service for equipment fault reports."""

    # ------------------------------------------------------------ retrieval
    @staticmethod
    def get(fault_id: int) -> FaultReport:
        fault = db.session.get(FaultReport, fault_id)
        if fault is None:
            raise NotFoundError("Fault report not found.")
        return fault

    @classmethod
    def get_by_reference(cls, reference: str) -> FaultReport:
        stmt = select(FaultReport).where(
            func.upper(FaultReport.reference_number) == reference.strip().upper()
        )
        fault = db.session.scalars(stmt).first()
        if fault is None:
            raise NotFoundError("Fault report not found.")
        return fault

    @staticmethod
    def next_reference(when: date = None) -> str:
        """Allocate the next ``FR-YYYY-NNNN`` reference for the given year."""
        when = when or date.today()
        prefix = f"FR-{when.year}-"
        existing = db.session.scalars(
            select(FaultReport.reference_number).where(
                FaultReport.reference_number.like(f"{prefix}%")
            )
        ).all()
        used_numbers = set()
        for ref in existing:
            try:
                used_numbers.add(int(ref.rsplit("-", 1)[1]))
            except (ValueError, IndexError):
                continue
        sequence = 1
        while sequence in used_numbers:
            sequence += 1
        return f"{prefix}{sequence:04d}"

    # -------------------------------------------------------------- create
    @classmethod
    def create(cls, data: dict, actor: User) -> FaultReport:
        equipment = db.session.get(Equipment, data.get("equipment_id"))
        if equipment is None:
            raise ValidationError(
                "Please select the affected equipment.",
                {"equipment_id": "Unknown equipment."},
            )

        title = (data.get("fault_title") or "").strip()
        description = (data.get("fault_description") or "").strip()
        if not title:
            raise ValidationError("Fault title is required.",
                                  {"fault_title": "Fault title is required."})
        if not description:
            raise ValidationError("Fault description is required.",
                                  {"fault_description": "Description is required."})

        discovered = coerce_date(
            data.get("date_discovered"), "Discovery date"
        ) or date.today()
        if discovered > date.today():
            raise ValidationError(
                "Discovery date cannot be in the future.",
                {"date_discovered": "Discovery date cannot be in the future."},
            )

        fault = FaultReport(
            reference_number=cls.next_reference(discovered),
            equipment=equipment,
            reported_by=actor.id,
            assigned_to=data.get("assigned_to") or None,
            fault_title=title,
            fault_description=description,
            fault_category=data["fault_category"],
            priority=data.get("priority") or "Medium",
            status="Reported",
            date_discovered=discovered,
        )
        db.session.add(fault)
        db.session.flush()

        # First entry of the status history: the initial Report event.
        db.session.add(
            FaultStatusHistory(
                fault=fault,
                previous_status=None,
                new_status="Reported",
                changed_by=actor.id,
                change_notes="Fault reported.",
            )
        )
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_CREATE,
            "fault_report",
            fault.id,
            f"{actor.role_label} reported fault {fault.reference_number} "
            f"for equipment {equipment.asset_tag}.",
        )

        if fault.assigned_to:
            officer = db.session.get(User, fault.assigned_to)
            if officer:
                audit_service.AuditService.log(
                    actor,
                    audit_service.ACTION_ASSIGN,
                    "fault_report",
                    fault.id,
                    f"Fault {fault.reference_number} assigned to "
                    f"{officer.full_name} at creation.",
                )
        return fault

    # ------------------------------------------------------- status changes
    @classmethod
    def change_status(cls, fault: FaultReport, new_status: str, actor: User,
                      notes: str = "") -> FaultReport:
        """Move a fault through the lifecycle, recording the transition."""
        if new_status == fault.status:
            raise TransitionError(f"Fault is already '{new_status}'.")

        if not fault.can_transition_to(new_status):
            allowed = ", ".join(fault.available_transitions()) or "none"
            raise TransitionError(
                f"A fault cannot move from '{fault.status}' to '{new_status}'. "
                f"Allowed next statuses: {allowed}."
            )

        if new_status == FAULT_RESOLVED:
            cls._assert_resolvable(fault, notes)

        previous = fault.status
        fault.status = new_status
        if new_status == FAULT_RESOLVED:
            fault.resolved_at = _utcnow()
        elif fault.resolved_at and new_status != "Closed":
            fault.resolved_at = None
        if new_status == FAULT_RESOLVED and notes:
            fault.resolution_notes = notes

        db.session.add(
            FaultStatusHistory(
                fault=fault,
                previous_status=previous,
                new_status=new_status,
                changed_by=actor.id,
                change_notes=notes or f"Status changed to {new_status}.",
            )
        )
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_STATUS_CHANGE,
            "fault_report",
            fault.id,
            f"{actor.role_label} changed fault {fault.reference_number} "
            f"from {previous} to {new_status}.",
        )
        return fault

    @classmethod
    def _assert_resolvable(cls, fault: FaultReport, notes: str) -> None:
        """A fault is only 'Resolved' once a repair record actually exists."""
        has_repair = (
            db.session.query(MaintenanceRecord.id)
            .filter(MaintenanceRecord.fault_report_id == fault.id)
            .count()
            > 0
        )
        if not has_repair:
            raise ValidationError(
                f"Cannot resolve {fault.reference_number}: no maintenance/repair "
                "record is linked to it yet. Record the repair first, then "
                "resolve the fault."
            )
        if not (notes or fault.resolution_notes or "").strip():
            raise ValidationError(
                "Resolution notes are required before a fault can be resolved.",
                {"resolution_notes": "Provide a resolution summary."},
            )

    @classmethod
    def assign(cls, fault: FaultReport, officer_id, actor: User,
               notes: str = "") -> FaultReport:
        """Assign (or unassign) the fault to an ICT officer."""
        officer = None
        if officer_id:
            officer = db.session.get(User, int(officer_id))
            if officer is None:
                raise ValidationError("Selected officer does not exist.")
            if not officer.is_officer and not officer.is_admin:
                raise ValidationError("Faults may only be assigned to ICT staff.")
        previous_assignee = fault.assignee_name
        fault.assigned_to = officer.id if officer else None
        new_name = officer.full_name if officer else "Unassigned"
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_ASSIGN,
            "fault_report",
            fault.id,
            f"{actor.role_label} changed fault {fault.reference_number} "
            f"assignment from {previous_assignee} to {new_name}.",
        )
        if notes:
            cls.add_note(fault, actor, notes)
        return fault

    @classmethod
    def change_priority(cls, fault: FaultReport, new_priority: str, actor: User,
                        notes: str = "") -> FaultReport:
        from models.constants import FAULT_PRIORITIES

        if new_priority not in FAULT_PRIORITIES:
            raise ValidationError(f"Invalid priority: {new_priority!r}")
        previous = fault.priority
        if previous == new_priority:
            return fault
        fault.priority = new_priority
        db.session.add(
            FaultStatusHistory(
                fault=fault,
                previous_status=fault.status,
                new_status=fault.status,
                changed_by=actor.id,
                change_notes=notes or f"Priority changed from {previous} to {new_priority}.",
            )
        )
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_UPDATE,
            "fault_report",
            fault.id,
            f"{actor.role_label} changed priority of {fault.reference_number} "
            f"from {previous} to {new_priority}.",
        )
        return fault

    @classmethod
    def add_note(cls, fault: FaultReport, author: User, body: str) -> FaultNote:
        body = (body or "").strip()
        if not body:
            raise ValidationError("Note text cannot be empty.",
                                  {"body": "Enter a note."})
        note = FaultNote(fault=fault, author_id=author.id, body=body)
        db.session.add(note)
        audit_service.AuditService.log(
            author,
            audit_service.ACTION_UPDATE,
            "fault_report",
            fault.id,
            f"{author.role_label} added an investigation note to "
            f"{fault.reference_number}.",
        )
        return note

    @classmethod
    def record_resolution_notes(cls, fault: FaultReport, actor: User,
                                resolution_notes: str) -> FaultReport:
        """Store resolution/investigation text without changing status."""
        text = (resolution_notes or "").strip()
        if not text:
            raise ValidationError("Resolution notes cannot be empty.")
        fault.resolution_notes = text
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_UPDATE,
            "fault_report",
            fault.id,
            f"{actor.role_label} updated resolution notes on "
            f"{fault.reference_number}.",
        )
        return fault

    # ------------------------------------------------------------ queries
    @classmethod
    def search_statement(cls, **filters):
        """Parameterised fault list query (search + filters)."""
        stmt = (
            select(FaultReport)
            .join(
                Equipment,
                FaultReport.equipment_id == Equipment.id,
                isouter=True,
            )
            .join(
                Department,
                Equipment.department_id == Department.id,
                isouter=True,
            )
        )

        search = (filters.get("search") or "").strip()
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                FaultReport.reference_number.ilike(pattern)
                | FaultReport.fault_title.ilike(pattern)
                | Equipment.asset_tag.ilike(pattern)
                | Equipment.equipment_name.ilike(pattern)
            )

        # Simple equality filters (validated upstream by the form/view).
        for column, key in (
            (FaultReport.status, "status"),
            (FaultReport.priority, "priority"),
            (FaultReport.fault_category, "fault_category"),
            (Equipment.department_id, "department_id"),
            (FaultReport.assigned_to, "assigned_to"),
        ):
            value = filters.get(key)
            if value not in (None, ""):
                if key in {"department_id", "assigned_to"}:
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        continue  # ignore junk instead of building bad SQL
                stmt = stmt.where(column == value)

        date_from = filters.get("date_from")
        if date_from:
            stmt = stmt.where(FaultReport.date_discovered >= date_from)
        date_to = filters.get("date_to")
        if date_to:
            stmt = stmt.where(FaultReport.date_discovered <= date_to)

        return stmt.order_by(
            FaultReport.created_at.desc(), FaultReport.id.desc()
        )

    @classmethod
    def paginate(cls, page: int, per_page: int, **filters):
        stmt = cls.search_statement(**filters)
        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)

    @staticmethod
    def count_open():
        stmt = select(func.count(FaultReport.id)).where(
            FaultReport.status.in_(OPEN_FAULT_STATUSES)
        )
        return db.session.scalar(stmt) or 0
