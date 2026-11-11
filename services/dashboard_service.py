"""Dashboard aggregate queries.

Everything on the dashboards is derived from live database records - no
hard-coded sample figures anywhere.  Aggregates are computed with SQL
``GROUP BY`` where possible and in Python only for the small monthly trend
series, which keeps the queries portable across database engines.
"""

from datetime import date, timedelta

from sqlalchemy import func, select

from extensions import db
from models.audit import AuditLog
from models.constants import (
    CONDITIONS,
    OPEN_FAULT_STATUSES,
    OPERATIONAL_STATUSES,
    ROLE_ADMIN,
    ROLE_OFFICER,
    ROLE_VIEWER,
)
from models.department import Department
from models.equipment import Equipment, EquipmentCategory
from models.fault import FaultReport
from models.maintenance import MaintenanceRecord, MaintenanceSchedule
from models.user import User


def _month_starts(months: int):
    """Start date of each of the last ``months`` months (oldest first)."""
    today = date.today()
    starts = []
    year, month = today.year, today.month
    for _ in range(months):
        starts.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(starts))


class DashboardService:
    """Read-only aggregates used by the role dashboards and reports."""

    # ================================================================ totals
    @classmethod
    def statistics(cls) -> dict:
        today = date.today()
        soon = today + timedelta(days=30)

        total_equipment = db.session.scalar(select(func.count(Equipment.id))) or 0
        total_departments = db.session.scalar(select(func.count(Department.id))) or 0
        total_users = db.session.scalar(select(func.count(User.id))) or 0
        active_users = db.session.scalar(
            select(func.count(User.id)).where(User.is_active.is_(True))
        ) or 0

        open_faults = db.session.scalar(
            select(func.count(FaultReport.id)).where(
                FaultReport.status.in_(OPEN_FAULT_STATUSES)
            )
        ) or 0
        total_faults = db.session.scalar(select(func.count(FaultReport.id))) or 0
        resolved_faults = db.session.scalar(
            select(func.count(FaultReport.id)).where(
                FaultReport.status.in_(("Resolved", "Closed"))
            )
        ) or 0
        unassigned_faults = db.session.scalar(
            select(func.count(FaultReport.id)).where(
                FaultReport.assigned_to.is_(None),
                FaultReport.status.in_(OPEN_FAULT_STATUSES),
            )
        ) or 0

        faulty_equipment = db.session.scalar(
            select(func.count(Equipment.id)).where(Equipment.operational_status == "Faulty")
        ) or 0
        under_maintenance = db.session.scalar(
            select(func.count(Equipment.id)).where(
                Equipment.operational_status == "Under Maintenance"
            )
        ) or 0
        retired_equipment = db.session.scalar(
            select(func.count(Equipment.id)).where(Equipment.operational_status == "Retired")
        ) or 0

        maintenance_count = db.session.scalar(
            select(func.count(MaintenanceRecord.id))
        ) or 0
        maintenance_cost = db.session.scalar(
            select(func.coalesce(func.sum(MaintenanceRecord.cost), 0))
        ) or 0
        maintenance_this_month = db.session.scalar(
            select(func.count(MaintenanceRecord.id)).where(
                MaintenanceRecord.maintenance_date >= date(today.year, today.month, 1)
            )
        ) or 0

        overdue_schedules = db.session.scalar(
            select(func.count(MaintenanceSchedule.id)).where(
                MaintenanceSchedule.scheduled_date < today,
                MaintenanceSchedule.status.notin_(("Completed", "Cancelled")),
            )
        ) or 0
        due_schedules = db.session.scalar(
            select(func.count(MaintenanceSchedule.id)).where(
                MaintenanceSchedule.scheduled_date <= soon,
                MaintenanceSchedule.status.notin_(("Completed", "Cancelled")),
            )
        ) or 0

        warranty_expiring = db.session.scalar(
            select(func.count(Equipment.id)).where(
                Equipment.warranty_expiry_date.isnot(None),
                Equipment.warranty_expiry_date >= today,
                Equipment.warranty_expiry_date <= soon,
            )
        ) or 0
        warranty_expired = db.session.scalar(
            select(func.count(Equipment.id)).where(
                Equipment.warranty_expiry_date.isnot(None),
                Equipment.warranty_expiry_date < today,
            )
        ) or 0

        resolution_rate = (
            round(resolved_faults / total_faults * 100, 1) if total_faults else 0.0
        )

        return {
            "total_equipment": total_equipment,
            "total_departments": total_departments,
            "total_users": total_users,
            "active_users": active_users,
            "total_faults": total_faults,
            "open_faults": open_faults,
            "resolved_faults": resolved_faults,
            "unassigned_faults": unassigned_faults,
            "resolution_rate": resolution_rate,
            "faulty_equipment": faulty_equipment,
            "under_maintenance": under_maintenance,
            "retired_equipment": retired_equipment,
            "maintenance_count": maintenance_count,
            "maintenance_cost": float(maintenance_cost or 0),
            "maintenance_this_month": maintenance_this_month,
            "overdue_schedules": overdue_schedules,
            "due_schedules": due_schedules,
            "warranty_expiring": warranty_expiring,
            "warranty_expired": warranty_expired,
        }

    # =========================================================== breakdowns
    @staticmethod
    def _count_by(model, column):
        rows = db.session.execute(
            select(column, func.count(model.id)).group_by(column)
        ).all()
        return {value: total for value, total in rows}

    @classmethod
    def equipment_by_status(cls) -> dict:
        counts = cls._count_by(Equipment, Equipment.operational_status)
        return {status: counts.get(status, 0) for status in OPERATIONAL_STATUSES}

    @classmethod
    def equipment_by_condition(cls) -> dict:
        counts = cls._count_by(Equipment, Equipment.condition)
        return {condition: counts.get(condition, 0) for condition in CONDITIONS}

    @classmethod
    def equipment_by_type(cls) -> dict:
        rows = db.session.execute(
            select(Equipment.equipment_type, func.count(Equipment.id))
            .group_by(Equipment.equipment_type)
            .order_by(func.count(Equipment.id).desc())
        ).all()
        return {name: total for name, total in rows}

    @classmethod
    def equipment_by_department(cls) -> list:
        """``[(department_name, total), ...]`` - includes empty departments."""
        rows = db.session.execute(
            select(Department.name, func.count(Equipment.id))
            .join(Equipment, Equipment.department_id == Department.id, isouter=True)
            .group_by(Department.name)
            .order_by(Department.name)
        ).all()
        return [(name, total) for name, total in rows]

    @classmethod
    def faults_by_status(cls) -> dict:
        return cls._count_by(FaultReport, FaultReport.status)

    @classmethod
    def faults_by_priority(cls) -> dict:
        return cls._count_by(FaultReport, FaultReport.priority)

    @classmethod
    def faults_by_category(cls) -> dict:
        rows = db.session.execute(
            select(FaultReport.fault_category, func.count(FaultReport.id))
            .group_by(FaultReport.fault_category)
            .order_by(func.count(FaultReport.id).desc())
        ).all()
        return {name: total for name, total in rows}

    @classmethod
    def maintenance_by_type(cls) -> dict:
        return cls._count_by(MaintenanceRecord, MaintenanceRecord.maintenance_type)

    # ================================================================= trend
    @classmethod
    def monthly_trend(cls, months: int = 6) -> dict:
        """Faults reported and maintenance performed per month.

        Returns ``{"labels": [...], "faults": [...], "maintenance": [...]}``
        where the series are aligned with ``labels`` (oldest month first).
        """
        starts = _month_starts(months)
        labels = [start.strftime("%b %Y") for start in starts]

        fault_rows = db.session.scalars(
            select(FaultReport.created_at).where(
                FaultReport.created_at >= starts[0]
            )
        ).all()
        maintenance_rows = db.session.scalars(
            select(MaintenanceRecord.maintenance_date).where(
                MaintenanceRecord.maintenance_date >= starts[0]
            )
        ).all()

        def bucket(values, key):
            counts = [0] * len(starts)
            for value in values:
                if value is None:
                    continue
                stamp = key(value)
                for index, start in enumerate(starts):
                    next_start = (
                        starts[index + 1]
                        if index + 1 < len(starts)
                        else None
                    )
                    if stamp >= start and (next_start is None or stamp < next_start):
                        counts[index] += 1
                        break
                else:
                    continue
            return counts

        return {
            "labels": labels,
            "faults": bucket(fault_rows, lambda v: v.date()),
            "maintenance": bucket(maintenance_rows, lambda v: v),
        }

    # ============================================================== lookups
    @staticmethod
    def recent_activity(limit: int = 10):
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        return db.session.scalars(stmt).all()

    @staticmethod
    def upcoming_schedules(limit: int = 5):
        stmt = (
            select(MaintenanceSchedule)
            .where(
                MaintenanceSchedule.scheduled_date <= date.today() + timedelta(days=30),
                MaintenanceSchedule.status.notin_(("Completed", "Cancelled")),
            )
            .order_by(MaintenanceSchedule.scheduled_date.asc())
            .limit(limit)
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def open_fault_queue(limit: int = 8):
        stmt = (
            select(FaultReport)
            .where(FaultReport.status.in_(OPEN_FAULT_STATUSES))
            .order_by(FaultReport.created_at.asc())
            .limit(limit)
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def warranty_watchlist(limit: int = 5):
        today = date.today()
        stmt = (
            select(Equipment)
            .where(
                Equipment.warranty_expiry_date.isnot(None),
                Equipment.warranty_expiry_date <= today + timedelta(days=60),
            )
            .order_by(Equipment.warranty_expiry_date.asc())
            .limit(limit)
        )
        return db.session.scalars(stmt).all()

    @staticmethod
    def role_counts() -> dict:
        rows = db.session.execute(
            select(User.role, func.count(User.id)).group_by(User.role)
        ).all()
        counts = {ROLE_ADMIN: 0, ROLE_OFFICER: 0, ROLE_VIEWER: 0}
        counts.update({role: total for role, total in rows})
        return counts

    @staticmethod
    def category_count() -> int:
        return db.session.scalar(select(func.count(EquipmentCategory.id))) or 0
