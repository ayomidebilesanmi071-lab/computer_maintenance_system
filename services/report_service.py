"""CSV generation for the reporting module.

Reports are rendered from live database queries (never from hard-coded sample
figures) and the same row iterators feed both the HTML tables and the CSV
download, so what the user sees on screen is exactly what they export.
"""

import csv
import io

from sqlalchemy import func, select

from extensions import db
from models.constants import CONDITIONS, OPEN_FAULT_STATUSES
from models.department import Department
from models.equipment import Equipment
from models.fault import FaultReport
from models.maintenance import MaintenanceRecord, MaintenanceSchedule


class ReportService:
    """Read-only reporting queries grouped by report type."""

    # =================================================== equipment inventory
    @staticmethod
    def equipment_inventory(**filters):
        """Full inventory listing with the fields required by the report."""
        stmt = select(Equipment).join(Equipment.department, isouter=True)
        if filters.get("department_id"):
            stmt = stmt.where(Equipment.department_id == int(filters["department_id"]))
        if filters.get("equipment_type"):
            stmt = stmt.where(Equipment.equipment_type == filters["equipment_type"])
        if filters.get("condition"):
            stmt = stmt.where(Equipment.condition == filters["condition"])
        if filters.get("operational_status"):
            stmt = stmt.where(Equipment.operational_status == filters["operational_status"])
        if filters.get("date_from"):
            stmt = stmt.where(Equipment.purchase_date >= filters["date_from"])
        if filters.get("date_to"):
            stmt = stmt.where(Equipment.purchase_date <= filters["date_to"])
        stmt = stmt.order_by(Equipment.asset_tag.asc())
        return db.session.scalars(stmt).all()

    @staticmethod
    def inventory_rows(items):
        """Yield CSV-ready rows for the equipment inventory report."""
        for item in items:
            yield [
                item.asset_tag,
                item.equipment_name,
                item.equipment_type,
                item.department.name if item.department else "",
                item.location or "",
                item.condition,
                item.operational_status,
                item.manufacturer or "",
                item.model or "",
                item.serial_number or "",
                item.purchase_date.isoformat() if item.purchase_date else "",
                item.warranty_expiry_date.isoformat() if item.warranty_expiry_date else "",
            ]

    INVENTORY_HEADERS = [
        "Asset Tag", "Equipment Name", "Equipment Type", "Department", "Location",
        "Condition", "Operational Status", "Manufacturer", "Model", "Serial Number",
        "Purchase Date", "Warranty Expiry",
    ]

    # ======================================================== fault summary
    @staticmethod
    def fault_summary(**filters):
        stmt = (
            select(FaultReport)
            .join(Equipment, FaultReport.equipment_id == Equipment.id, isouter=True)
            .join(Department, Equipment.department_id == Department.id, isouter=True)
        )
        if filters.get("status"):
            stmt = stmt.where(FaultReport.status == filters["status"])
        if filters.get("priority"):
            stmt = stmt.where(FaultReport.priority == filters["priority"])
        if filters.get("fault_category"):
            stmt = stmt.where(FaultReport.fault_category == filters["fault_category"])
        if filters.get("department_id"):
            stmt = stmt.where(Equipment.department_id == int(filters["department_id"]))
        if filters.get("assigned_to"):
            stmt = stmt.where(FaultReport.assigned_to == int(filters["assigned_to"]))
        if filters.get("date_from"):
            stmt = stmt.where(FaultReport.date_discovered >= filters["date_from"])
        if filters.get("date_to"):
            stmt = stmt.where(FaultReport.date_discovered <= filters["date_to"])
        stmt = stmt.order_by(FaultReport.created_at.desc())
        return db.session.scalars(stmt).all()

    @staticmethod
    def fault_rows(items):
        for fault in items:
            equipment = fault.equipment
            yield [
                fault.reference_number,
                f"{equipment.asset_tag} - {equipment.equipment_name}" if equipment else "",
                fault.fault_category,
                fault.priority,
                fault.status,
                fault.date_discovered.isoformat() if fault.date_discovered else "",
                fault.assignee_name,
            ]

    FAULT_HEADERS = [
        "Fault Reference", "Equipment", "Fault Category", "Priority", "Status",
        "Date Reported", "Assigned Officer",
    ]

    # ==================================================== maintenance history
    @staticmethod
    def maintenance_history(**filters):
        stmt = (
            select(MaintenanceRecord)
            .join(Equipment, MaintenanceRecord.equipment_id == Equipment.id, isouter=True)
            .join(Department, Equipment.department_id == Department.id, isouter=True)
        )
        if filters.get("maintenance_type"):
            stmt = stmt.where(MaintenanceRecord.maintenance_type == filters["maintenance_type"])
        if filters.get("outcome"):
            stmt = stmt.where(MaintenanceRecord.outcome == filters["outcome"])
        if filters.get("department_id"):
            stmt = stmt.where(Equipment.department_id == int(filters["department_id"]))
        if filters.get("technician_id"):
            stmt = stmt.where(MaintenanceRecord.technician_id == int(filters["technician_id"]))
        if filters.get("date_from"):
            stmt = stmt.where(MaintenanceRecord.maintenance_date >= filters["date_from"])
        if filters.get("date_to"):
            stmt = stmt.where(MaintenanceRecord.maintenance_date <= filters["date_to"])
        stmt = stmt.order_by(MaintenanceRecord.maintenance_date.desc())
        return db.session.scalars(stmt).all()

    @staticmethod
    def maintenance_rows(items):
        for record in items:
            equipment = record.equipment
            yield [
                f"{equipment.asset_tag} - {equipment.equipment_name}" if equipment else "",
                record.maintenance_type,
                record.maintenance_date.isoformat() if record.maintenance_date else "",
                record.technician_name,
                (record.work_performed or "").replace("\n", " "),
                record.outcome,
                f"{float(record.cost):.2f}" if record.cost is not None else "",
            ]

    MAINTENANCE_HEADERS = [
        "Equipment", "Maintenance Type", "Date of Maintenance", "Technician",
        "Work Performed", "Maintenance Outcome", "Cost",
    ]

    # ================================================== preventive maintenance
    @staticmethod
    def preventive_schedule(**filters):
        stmt = (
            select(MaintenanceSchedule)
            .join(Equipment, MaintenanceSchedule.equipment_id == Equipment.id, isouter=True)
            .join(Department, Equipment.department_id == Department.id, isouter=True)
        )
        if filters.get("status"):
            stmt = stmt.where(MaintenanceSchedule.status == filters["status"])
        if filters.get("department_id"):
            stmt = stmt.where(Equipment.department_id == int(filters["department_id"]))
        if filters.get("assigned_to"):
            stmt = stmt.where(MaintenanceSchedule.assigned_to == int(filters["assigned_to"]))
        if filters.get("date_from"):
            stmt = stmt.where(MaintenanceSchedule.scheduled_date >= filters["date_from"])
        if filters.get("date_to"):
            stmt = stmt.where(MaintenanceSchedule.scheduled_date <= filters["date_to"])
        stmt = stmt.order_by(MaintenanceSchedule.scheduled_date.asc())
        return db.session.scalars(stmt).all()

    @staticmethod
    def schedule_rows(items):
        for schedule in items:
            equipment = schedule.equipment
            yield [
                f"{equipment.asset_tag} - {equipment.equipment_name}" if equipment else "",
                schedule.maintenance_type,
                schedule.scheduled_date.isoformat() if schedule.scheduled_date else "",
                schedule.assignee_name,
                schedule.status,
                schedule.completed_at.strftime("%Y-%m-%d") if schedule.completed_at else "",
            ]

    SCHEDULE_HEADERS = [
        "Equipment", "Maintenance Type", "Scheduled Date", "Assigned Officer",
        "Schedule Status", "Completion Date",
    ]

    # ====================================================== condition report
    @classmethod
    def equipment_condition_report(cls, **filters):
        """Equipment grouped by condition, in the order of ``CONDITIONS``."""
        items = cls.equipment_inventory(**filters)
        grouped = {condition: [] for condition in CONDITIONS}
        for item in items:
            grouped.setdefault(item.condition, []).append(item)
        return grouped

    @staticmethod
    def condition_rows(grouped):
        for condition, items in grouped.items():
            for item in items:
                yield [
                    condition,
                    item.asset_tag,
                    item.equipment_name,
                    item.equipment_type,
                    item.department.name if item.department else "",
                    item.location or "",
                    item.operational_status,
                ]

    CONDITION_HEADERS = [
        "Condition", "Asset Tag", "Equipment Name", "Equipment Type", "Department",
        "Location", "Operational Status",
    ]

    # ============================================================== summaries
    @staticmethod
    def summary_totals() -> dict:
        """Headline figures shown above each report."""
        total_equipment = db.session.scalar(select(func.count(Equipment.id))) or 0
        total_faults = db.session.scalar(select(func.count(FaultReport.id))) or 0
        open_faults = db.session.scalar(
            select(func.count(FaultReport.id)).where(
                FaultReport.status.in_(OPEN_FAULT_STATUSES)
            )
        ) or 0
        total_maintenance = db.session.scalar(
            select(func.count(MaintenanceRecord.id))
        ) or 0
        maintenance_cost = db.session.scalar(
            select(func.coalesce(func.sum(MaintenanceRecord.cost), 0))
        ) or 0
        total_schedules = db.session.scalar(
            select(func.count(MaintenanceSchedule.id))
        ) or 0
        return {
            "total_equipment": total_equipment,
            "total_faults": total_faults,
            "open_faults": open_faults,
            "total_maintenance": total_maintenance,
            "maintenance_cost": float(maintenance_cost or 0),
            "total_schedules": total_schedules,
        }

    # ================================================================== CSV
    @staticmethod
    def to_csv(headers, rows) -> str:
        """Serialise report rows into CSV text (RFC 4180, Excel friendly)."""
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        return buffer.getvalue()
