"""Maintenance and preventive-scheduling business logic.

Two related flows live here:

* :class:`MaintenanceService` - recording repairs/inspections and completing
  schedules, including the side effects on the linked equipment and fault;
* schedule status refresh (``Scheduled`` / ``Due`` / ``Overdue``), which is
  derived from the stored ``scheduled_date`` on every dashboard load, so no
  background job or email service is required.
"""

from datetime import date, datetime, timezone

from sqlalchemy import select

from extensions import db
from models.constants import (
    MAINTENANCE_OUTCOMES,
    MAINTENANCE_TYPES,
    OPEN_FAULT_STATUSES,
    SCHEDULE_CANCELLED,
    SCHEDULE_COMPLETED,
    SCHEDULE_DUE,
    SCHEDULE_IN_PROGRESS,
    SCHEDULE_OVERDUE,
    SCHEDULE_SCHEDULED,
    STATUS_AVAILABLE,
    STATUS_FAULTY,
    STATUS_IN_USE,
    STATUS_UNDER_MAINTENANCE,
)
from models.equipment import Equipment
from models.fault import FaultReport, FaultStatusHistory
from models.maintenance import MaintenanceRecord, MaintenanceSchedule
from models.user import User
from services import audit_service
from services.errors import NotFoundError, TransitionError, ValidationError
from services.validation import coerce_date, coerce_decimal


def _utcnow():
    return datetime.now(timezone.utc)


class MaintenanceService:
    """Domain service for maintenance records."""

    # ------------------------------------------------------------ retrieval
    @staticmethod
    def get(record_id: int) -> MaintenanceRecord:
        record = db.session.get(MaintenanceRecord, record_id)
        if record is None:
            raise NotFoundError("Maintenance record not found.")
        return record

    @classmethod
    def history_for(cls, equipment: Equipment):
        return list(equipment.maintenance_records)

    # -------------------------------------------------------------- create
    @classmethod
    def record_maintenance(cls, data: dict, actor: User) -> MaintenanceRecord:
        """Persist a maintenance/repair activity and sync the asset."""
        equipment = db.session.get(Equipment, data.get("equipment_id"))
        if equipment is None:
            raise ValidationError(
                "Please select the affected equipment.",
                {"equipment_id": "Unknown equipment."},
            )

        work_performed = (data.get("work_performed") or "").strip()
        if not work_performed:
            raise ValidationError(
                "Description of the work performed is required.",
                {"work_performed": "Describe the work performed."},
            )

        maintenance_date = coerce_date(
            data.get("maintenance_date"), "Maintenance date"
        ) or date.today()
        if maintenance_date > date.today():
            raise ValidationError(
                "Maintenance date cannot be in the future.",
                {"maintenance_date": "Maintenance date cannot be in the future."},
            )

        fault = None
        if data.get("fault_report_id"):
            fault = db.session.get(FaultReport, int(data["fault_report_id"]))
            if fault is None:
                raise ValidationError(
                    "The selected fault report no longer exists.",
                    {"fault_report_id": "Unknown fault report."},
                )
            if fault.equipment_id != equipment.id:
                raise ValidationError(
                    "The selected fault report belongs to a different piece "
                    "of equipment.",
                    {"fault_report_id": "Mismatched fault report."},
                )

        outcome = data.get("outcome")
        if outcome not in MAINTENANCE_OUTCOMES:
            raise ValidationError(f"Invalid maintenance outcome: {outcome!r}")

        technician_id = data.get("technician_id") or actor.id
        technician = db.session.get(User, int(technician_id))
        if technician is None:
            raise ValidationError("Selected technician does not exist.",
                                  {"technician_id": "Unknown technician."})

        cost = coerce_decimal(data.get("cost"), "Maintenance cost", minimum=0)

        condition_after = data.get("condition_after") or equipment.condition
        record = MaintenanceRecord(
            equipment=equipment,
            fault_report=fault,
            maintenance_type=data["maintenance_type"],
            diagnosis=(data.get("diagnosis") or "").strip() or None,
            work_performed=work_performed,
            parts_replaced=(data.get("parts_replaced") or "").strip() or None,
            technician_id=technician.id,
            maintenance_date=maintenance_date,
            start_time=data.get("start_time"),
            completion_time=data.get("completion_time"),
            cost=cost,
            condition_after=condition_after,
            outcome=outcome,
            notes=(data.get("notes") or "").strip() or None,
            recorded_by=actor.id,
            schedule_id=data.get("schedule_id") or None,
        )
        db.session.add(record)
        db.session.flush()

        # --- side effects on the asset ------------------------------------
        before_status = equipment.operational_status
        if condition_after != equipment.condition:
            cls._history(
                equipment, equipment.condition, condition_after, None, None,
                actor, f"Condition updated after maintenance #{record.id}.",
            )
            equipment.condition = condition_after

        new_status = cls._status_after_outcome(outcome, equipment)
        if new_status and new_status != before_status:
            cls._history(
                equipment, None, None, before_status, new_status, actor,
                f"Operational status updated after maintenance #{record.id}.",
            )
            equipment.operational_status = new_status

        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_CREATE,
            "maintenance_record",
            record.id,
            f"{actor.role_label} recorded {record.maintenance_type} for "
            f"equipment {equipment.asset_tag} ({outcome}).",
        )
        return record

    @staticmethod
    def _status_after_outcome(outcome: str, equipment: Equipment):
        """Choose the operational status implied by a maintenance outcome."""
        if equipment.is_retired:
            return None
        if outcome == "Completed - Equipment Working":
            return STATUS_IN_USE
        if outcome in {"Completed - Equipment Not Fully Working",
                       "Unsuccessful - Fault Persists"}:
            return STATUS_FAULTY
        if outcome == "Deferred - Awaiting Parts":
            return STATUS_UNDER_MAINTENANCE
        return None

    @staticmethod
    def _history(equipment, prev_cond, new_cond, prev_status, new_status, actor, notes):
        from models.equipment import EquipmentStatusHistory

        entry = EquipmentStatusHistory(
            equipment=equipment,
            previous_condition=prev_cond,
            new_condition=new_cond or prev_cond,
            previous_status=prev_status,
            new_status=new_status or prev_status,
            changed_by=actor.id if actor else None,
            change_notes=notes,
        )
        db.session.add(entry)
        return entry

    # -------------------------------------------------------------- update
    @classmethod
    def update_record(cls, record: MaintenanceRecord, data: dict, actor: User) -> MaintenanceRecord:
        """Edit an existing maintenance record (fields only, keeps history)."""
        if data.get("work_performed") is not None:
            text = data["work_performed"].strip()
            if not text:
                raise ValidationError(
                    "Description of the work performed is required.",
                    {"work_performed": "Describe the work performed."},
                )
            record.work_performed = text
        if "maintenance_type" in data and data["maintenance_type"]:
            if data["maintenance_type"] not in MAINTENANCE_TYPES:
                raise ValidationError("Invalid maintenance type.")
            record.maintenance_type = data["maintenance_type"]
        if "outcome" in data and data["outcome"]:
            if data["outcome"] not in MAINTENANCE_OUTCOMES:
                raise ValidationError("Invalid maintenance outcome.")
            record.outcome = data["outcome"]
        for field in ("diagnosis", "parts_replaced", "notes"):
            if field in data:
                setattr(record, field, (data.get(field) or "").strip() or None)
        if data.get("cost") is not None:
            record.cost = coerce_decimal(data["cost"], "Maintenance cost", minimum=0)
        new_date = coerce_date(data.get("maintenance_date"), "Maintenance date")
        if new_date:
            record.maintenance_date = new_date
        if data.get("technician_id"):
            technician = db.session.get(User, int(data["technician_id"]))
            if technician is None:
                raise ValidationError("Selected technician does not exist.")
            record.technician_id = technician.id

        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_UPDATE,
            "maintenance_record",
            record.id,
            f"{actor.role_label} updated maintenance record #{record.id} "
            f"for {record.equipment.asset_tag}.",
        )
        return record

    # ------------------------------------------------------------ queries
    @classmethod
    def search_statement(cls, **filters):
        from models.department import Department

        stmt = (
            select(MaintenanceRecord)
            .join(Equipment, MaintenanceRecord.equipment_id == Equipment.id, isouter=True)
            .join(Department, Equipment.department_id == Department.id, isouter=True)
        )
        search = (filters.get("search") or "").strip()
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                Equipment.asset_tag.ilike(pattern)
                | Equipment.equipment_name.ilike(pattern)
                | MaintenanceRecord.maintenance_type.ilike(pattern)
                | MaintenanceRecord.work_performed.ilike(pattern)
            )
        for column, key in (
            (MaintenanceRecord.maintenance_type, "maintenance_type"),
            (MaintenanceRecord.outcome, "outcome"),
            (Equipment.department_id, "department_id"),
            (MaintenanceRecord.technician_id, "technician_id"),
        ):
            value = filters.get(key)
            if value not in (None, ""):
                if key == "department_id":
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        continue
                stmt = stmt.where(column == value)
        if filters.get("date_from"):
            stmt = stmt.where(MaintenanceRecord.maintenance_date >= filters["date_from"])
        if filters.get("date_to"):
            stmt = stmt.where(MaintenanceRecord.maintenance_date <= filters["date_to"])
        return stmt.order_by(
            MaintenanceRecord.maintenance_date.desc(), MaintenanceRecord.id.desc()
        )

    @classmethod
    def paginate(cls, page: int, per_page: int, **filters):
        stmt = cls.search_statement(**filters)
        return db.paginate(stmt, page=page, per_page=per_page, error_out=False)


class ScheduleService:
    """Domain service for preventive-maintenance schedules."""

    @staticmethod
    def get(schedule_id: int) -> MaintenanceSchedule:
        schedule = db.session.get(MaintenanceSchedule, schedule_id)
        if schedule is None:
            raise NotFoundError("Maintenance schedule not found.")
        return schedule

    @classmethod
    def create(cls, data: dict, actor: User) -> MaintenanceSchedule:
        equipment = db.session.get(Equipment, data.get("equipment_id"))
        if equipment is None:
            raise ValidationError(
                "Please select the equipment to schedule.",
                {"equipment_id": "Unknown equipment."},
            )
        scheduled_date = coerce_date(data.get("scheduled_date"), "Scheduled date")
        if scheduled_date is None:
            raise ValidationError(
                "Scheduled date is required.", {"scheduled_date": "Required."}
            )
        officer = db.session.get(User, int(data.get("assigned_to") or 0))
        if officer is None or not (officer.is_officer or officer.is_admin):
            raise ValidationError(
                "Schedules must be assigned to an ICT officer or administrator.",
                {"assigned_to": "Select a valid ICT officer."},
            )

        schedule = MaintenanceSchedule(
            equipment=equipment,
            maintenance_type=data["maintenance_type"],
            scheduled_date=scheduled_date,
            assigned_to=officer.id,
            instructions=(data.get("instructions") or "").strip() or None,
            status=SCHEDULE_DUE if scheduled_date <= date.today() else SCHEDULE_SCHEDULED,
            notes=(data.get("notes") or "").strip() or None,
            created_by=actor.id,
        )
        db.session.add(schedule)
        db.session.flush()
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_CREATE,
            "maintenance_schedule",
            schedule.id,
            f"{actor.role_label} scheduled {schedule.maintenance_type} for "
            f"{equipment.asset_tag} on {scheduled_date:%Y-%m-%d}.",
        )
        return schedule

    @classmethod
    def update(cls, schedule: MaintenanceSchedule, data: dict, actor: User) -> MaintenanceSchedule:
        new_date = coerce_date(data.get("scheduled_date"), "Scheduled date")
        if new_date:
            schedule.scheduled_date = new_date
        if data.get("maintenance_type"):
            schedule.maintenance_type = data["maintenance_type"]
        if data.get("assigned_to"):
            officer = db.session.get(User, int(data["assigned_to"]))
            if officer is None or not (officer.is_officer or officer.is_admin):
                raise ValidationError("Select a valid ICT officer.")
            schedule.assigned_to = officer.id
        if "instructions" in data:
            schedule.instructions = (data.get("instructions") or "").strip() or None
        if "notes" in data:
            schedule.notes = (data.get("notes") or "").strip() or None
        if data.get("status"):
            cls._validate_status_change(schedule, data["status"])
            schedule.status = data["status"]
            if schedule.status == SCHEDULE_COMPLETED and not schedule.completed_at:
                schedule.completed_at = _utcnow()
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_UPDATE,
            "maintenance_schedule",
            schedule.id,
            f"{actor.role_label} updated schedule #{schedule.id} for "
            f"{schedule.equipment.asset_tag}.",
        )
        return schedule

    @staticmethod
    def _validate_status_change(schedule, new_status):
        allowed = {
            SCHEDULE_SCHEDULED: {SCHEDULE_DUE, SCHEDULE_IN_PROGRESS, SCHEDULE_COMPLETED, SCHEDULE_CANCELLED},
            SCHEDULE_DUE: {SCHEDULE_IN_PROGRESS, SCHEDULE_COMPLETED, SCHEDULE_CANCELLED, SCHEDULE_OVERDUE},
            SCHEDULE_OVERDUE: {SCHEDULE_IN_PROGRESS, SCHEDULE_COMPLETED, SCHEDULE_CANCELLED},
            SCHEDULE_IN_PROGRESS: {SCHEDULE_COMPLETED, SCHEDULE_CANCELLED},
            SCHEDULE_COMPLETED: set(),
            SCHEDULE_CANCELLED: set(),
        }
        if new_status not in allowed.get(schedule.status, set()):
            raise TransitionError(
                f"A schedule cannot move from '{schedule.status}' to '{new_status}'."
            )

    @classmethod
    def complete(cls, schedule: MaintenanceSchedule, actor: User,
                 record_maintenance: bool = True,
                 extra: dict = None) -> MaintenanceSchedule:
        """Finish a schedule, optionally creating the maintenance record."""
        if schedule.is_completed:
            raise TransitionError("This schedule is already completed.")
        if record_maintenance:
            payload = {
                "equipment_id": schedule.equipment_id,
                "fault_report_id": None,
                # Link the new record back to the schedule it fulfils.
                "schedule_id": schedule.id,
                "maintenance_type": schedule.maintenance_type,
                "work_performed": schedule.instructions
                or f"Preventive maintenance performed as scheduled ({schedule.maintenance_type}).",
                "technician_id": schedule.assigned_to,
                "maintenance_date": date.today(),
                "outcome": "Completed - Equipment Working",
                "condition_after": schedule.equipment.condition,
            }
            payload.update(extra or {})
            MaintenanceService.record_maintenance(payload, actor)
        schedule.status = SCHEDULE_COMPLETED
        schedule.completed_at = _utcnow()
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_STATUS_CHANGE,
            "maintenance_schedule",
            schedule.id,
            f"{actor.role_label} completed schedule #{schedule.id} for "
            f"{schedule.equipment.asset_tag}.",
        )
        return schedule

    @classmethod
    def cancel(cls, schedule: MaintenanceSchedule, actor: User, reason: str = ""):
        if schedule.is_completed:
            raise TransitionError("A completed schedule cannot be cancelled.")
        schedule.status = SCHEDULE_CANCELLED
        schedule.notes = reason or schedule.notes
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_STATUS_CHANGE,
            "maintenance_schedule",
            schedule.id,
            f"{actor.role_label} cancelled schedule #{schedule.id} for "
            f"{schedule.equipment.asset_tag}.",
        )
        return schedule

    @classmethod
    def refresh_statuses(cls) -> int:
        """Recompute Due/Overdue flags from the stored scheduled dates.

        Called at the start of every dashboard/list render so reminders stay
        correct without a cron job.
        """
        today = date.today()
        updated = 0

        overdue = db.session.scalars(
            select(MaintenanceSchedule).where(
                MaintenanceSchedule.scheduled_date < today,
                MaintenanceSchedule.status.in_((SCHEDULE_SCHEDULED, SCHEDULE_DUE)),
            )
        ).all()
        for schedule in overdue:
            schedule.status = SCHEDULE_OVERDUE
            updated += 1

        due = db.session.scalars(
            select(MaintenanceSchedule).where(
                MaintenanceSchedule.scheduled_date == today,
                MaintenanceSchedule.status == SCHEDULE_SCHEDULED,
            )
        ).all()
        for schedule in due:
            schedule.status = SCHEDULE_DUE
            updated += 1
        return updated

    @classmethod
    def upcoming(cls, days: int = 7):
        """Schedules due within ``days`` days (including overdue ones)."""
        today = date.today()
        horizon = date.fromordinal(today.toordinal() + days)
        stmt = (
            select(MaintenanceSchedule)
            .where(
                MaintenanceSchedule.scheduled_date <= horizon,
                MaintenanceSchedule.status.notin_((SCHEDULE_COMPLETED, SCHEDULE_CANCELLED)),
            )
            .order_by(MaintenanceSchedule.scheduled_date.asc())
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def open_fault_count(equipment: Equipment) -> int:
        return sum(1 for f in equipment.fault_reports if f.status in OPEN_FAULT_STATUSES)
