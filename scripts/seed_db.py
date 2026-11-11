"""Seed CMIMS with documented, fictional sample data.

The script is **idempotent**: every record is looked up by its natural key
(email, asset tag, department name, fault title, ...) and skipped when it is
already present, so running it twice never duplicates rows and never touches
records that were entered by real users.

All data below is invented for demonstration purposes and contains no
confidential organisational information.

Usage::

    python scripts/seed_db.py
    flask --app app seed-db
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models.constants import EQUIPMENT_TYPES  # noqa: E402
from models.department import Department  # noqa: E402
from models.equipment import Equipment, EquipmentCategory  # noqa: E402
from models.fault import FaultReport  # noqa: E402
from models.maintenance import MaintenanceRecord, MaintenanceSchedule  # noqa: E402
from models.user import User  # noqa: E402
from services.equipment_service import EquipmentService  # noqa: E402
from services.fault_service import FaultService  # noqa: E402
from services.maintenance_service import (  # noqa: E402
    MaintenanceService,
    ScheduleService,
)

TODAY = date.today()

# --- Accounts (passwords are development-only; see README before deploying) --
ACCOUNTS = (
    ("System Administrator", "admin@cmims.local", "Admin@2026#ICT", "admin"),
    ("Ayomide Bello", "officer1@cmims.local", "Officer@2026#One", "ict_officer"),
    ("Chidera Nwosu", "officer2@cmims.local", "Officer@2026#Two", "ict_officer"),
    ("Akorede Bilesanmi", "viewer@cmims.local", "Viewer@2026#One", "viewer"),
)

DEPARTMENTS = (
    ("ICT Department", "Manages the organisation's computer systems.", "Ground floor, Block A"),
    ("Accounts Department", "Finance, payroll and procurement.", "First floor, Block B"),
    ("Administration Department", "General administration and records.", "Ground floor, Block A"),
    ("Human Resources Department", "Staff records and welfare.", "Second floor, Block C"),
    ("Registry Department", "Document registry and archives.", "Ground floor, Block C"),
)

# --- 18 fictional assets ------------------------------------------------------
EQUIPMENT = (
    # asset_tag, name, type, manufacturer, model, serial, dept, location,
    # purchase offset (days ago), warranty offset (days from now), condition, status
    ("ICT-001", "HP ProDesk 400 G7 Desktop Computer", "Desktop Computer", "HP",
     "ProDesk 400 G7", "HP4G7-1001", "ICT Department", "ICT Office, Room 12",
     900, 180, "Good", "In Use"),
    ("ICT-002", "Dell Latitude 5420 Laptop", "Laptop Computer", "Dell",
     "Latitude 5420", "DLL5420-1002", "Accounts Department", "Accounts Office, Room 4",
     700, 90, "Excellent", "In Use"),
    ("ICT-003", "Canon imageRUNNER 2630 Printer", "Printer", "Canon",
     "imageRUNNER 2630", "CN2630-1003", "Administration Department", "Admin Copy Room",
     1200, -60, "Fair", "Under Maintenance"),
    ("ICT-004", "HP LaserJet Pro M404dn Printer", "Printer", "HP",
     "LaserJet Pro M404dn", "HPLJ404-1004", "Accounts Department", "Accounts Copy Room",
     640, 300, "Good", "In Use"),
    ("ICT-005", "Cisco Catalyst 9200 Network Switch", "Network Switch", "Cisco",
     "Catalyst 9200", "CSC9200-1005", "ICT Department", "Server Room, Room 1",
     1500, 400, "Excellent", "In Use"),
    ("ICT-006", "TP-Link Archer C6 Wireless Router", "Router", "TP-Link",
     "Archer C6", "TPLAC6-1006", "ICT Department", "Server Room, Room 1",
     500, 45, "Good", "In Use"),
    ("ICT-007", "APC Smart-UPS 1500VA", "UPS", "APC",
     "Smart-UPS 1500VA", "APC15-1007", "ICT Department", "Server Room, Room 1",
     800, -30, "Fair", "In Use"),
    ("ICT-008", "Dell PowerEdge T340 Network Server", "Server", "Dell",
     "PowerEdge T340", "DLLT340-1008", "ICT Department", "Server Room, Room 1",
     1100, 250, "Good", "In Use"),
    ("ICT-009", "Samsung 24\" LED Monitor", "Monitor", "Samsung",
     "LS24R350", "SMS24-1009", "Human Resources Department", "HR Office, Room 7",
     430, 20, "Good", "In Use"),
    ("ICT-010", "Fujitsu fi-7160 Document Scanner", "Scanner", "Fujitsu",
     "fi-7160", "FJ7160-1010", "Registry Department", "Registry Room, Room 2",
     1400, -120, "Poor", "Faulty"),
    ("ICT-011", "Lenovo ThinkPad E14 Laptop", "Laptop Computer", "Lenovo",
     "ThinkPad E14", "LNV E14-1011", "ICT Department", "Field kit",
     380, 320, "Excellent", "Available"),
    ("ICT-012", "HP ProBook 450 G9 Laptop", "Laptop Computer", "HP",
     "ProBook 450 G9", "HP450G9-1012", "Administration Department", "Admin Office, Room 3",
     300, 400, "Excellent", "In Use"),
    ("ICT-013", "Epson EB-X06 Projector", "Projector", "Epson",
     "EB-X06", "EPSX06-1013", "Administration Department", "Conference Room",
     520, 150, "Good", "Available"),
    ("ICT-014", "Logitech K120 Keyboard Set", "Keyboard", "Logitech",
     "K120", "LGTK120-1014", "Accounts Department", "Accounts Office, Room 4",
     260, 10, "Good", "In Use"),
    ("ICT-015", "APC Back-UPS 650VA", "UPS", "APC",
     "Back-UPS 650VA", "APC650-1015", "Human Resources Department", "HR Office, Room 7",
     620, -10, "Fair", "In Use"),
    ("ICT-016", "Dell OptiPlex 3080 Desktop Computer", "Desktop Computer", "Dell",
     "OptiPlex 3080", "DLL3080-1016", "Registry Department", "Registry Room, Room 2",
     950, 365, "Good", "In Use"),
    ("ICT-017", "HP ProDesk 405 G6 Desktop Computer", "Desktop Computer", "HP",
     "ProDesk 405 G6", "HP405G6-1017", "Administration Department", "Admin Office, Room 3",
     700, 210, "Fair", "Under Maintenance"),
    ("ICT-018", "Cisco RV340 Router", "Router", "Cisco",
     "RV340", "CSRV340-1018", "ICT Department", "Server Room, Room 1",
     1300, -200, "Damaged", "Retired"),
)

# --- Faults: (equipment tag, title, description, category, priority, days ago,
#              officer index, final status)
FAULTS = (
    ("ICT-003", "Printer jams on every duplex job",
     "The Canon printer jams paper whenever a double-sided job is sent from the "
     "Accounts workstation. Single-sided jobs print normally.",
     "Printer Problem", "High", 18, 1, "Closed"),
    ("ICT-007", "UPS beeping and showing battery fault",
     "The UPS in the server room beeps continuously and the battery indicator is "
     "red. Load is currently running on mains only.",
     "Power Supply Problem", "Critical", 9, 1, "Resolved"),
    ("ICT-010", "Document scanner failing to feed pages",
     "The registry scanner pulls two or three sheets at once and frequently stops "
     "mid-batch with a paper feed error.",
     "Peripheral Device Problem", "Medium", 25, 2, "Under Repair"),
    ("ICT-017", "Desktop reboots during long reports",
     "The administration desktop restarts unexpectedly when a large report is "
     "generated. No blue-screen message is shown.",
     "Slow Computer Performance", "High", 6, 2, "Acknowledged"),
    ("ICT-002", "Laptop will not connect to the office Wi-Fi",
     "The Accounts laptop sees the wireless network but cannot obtain an IP "
     "address. Wired connections work fine.",
     "Network Connectivity Problem", "Medium", 3, 1, "Reported"),
    ("ICT-014", "Keyboard keys sticking",
     "Several keys on the Accounts keyboard require repeated presses before "
     "registering.",
     "Other", "Low", 40, 2, "Closed"),
    ("ICT-016", "Operating system updates failing to install",
     "Monthly operating system updates fail repeatedly on the registry desktop "
     "with an installation error.",
     "Operating System Problem", "Medium", 12, 1, "Resolved"),
    ("ICT-009", "Monitor flickering at 60 Hz",
     "The HR monitor flickers intermittently, especially when the office air "
     "conditioner switches on.",
     "Hardware Failure", "Low", 30, 2, "Awaiting Parts"),
)

# --- Maintenance performed: (equipment tag, fault title or None, type, days ago,
#                             technician index, diagnosis, work, parts, cost,
#                             outcome)
MAINTENANCE = (
    ("ICT-003", "Printer jams on every duplex job", "Hardware Repair", 15, 1,
     "Worn duplex feed roller and separation pad.",
     "Replaced the duplex feed roller assembly and separation pad, cleaned the "
     "paper path and re-ran a 30-page duplex test.", "Duplex roller kit", 18500.00,
     "Completed - Equipment Working"),
    ("ICT-007", "UPS beeping and showing battery fault", "Hardware Repair", 7, 1,
     "Battery pack below usable capacity.",
     "Replaced the battery pack, calibrated the runtime estimate and load-tested "
     "the unit for 20 minutes.", "Replacement battery pack", 42000.00,
     "Completed - Equipment Working"),
    ("ICT-010", "Document scanner failing to feed pages", "Hardware Repair", 20, 2,
     "Roller assembly worn, feed sensor dirty.",
     "Cleaned the feed sensor and replaced the pickup rollers. The scanner still "
     "double-feeds occasionally; a service kit has been ordered.", "Pickup rollers",
     9000.00, "Completed - Equipment Not Fully Working"),
    ("ICT-014", "Keyboard keys sticking", "Corrective Maintenance", 38, 2,
     "Debris under the key caps.",
     "Cleaned the keyboard internally and tested every key; advised the user to "
     "replace the unit if the problem returns.", None, 0.00,
     "Completed - Equipment Working"),
    ("ICT-016", "Operating system updates failing to install", "Software Maintenance", 10, 1,
     "Corrupted component store.",
     "Repaired the component store, cleared the update cache and installed all "
     "pending updates successfully.", None, 0.00, "Completed - Equipment Working"),
    ("ICT-001", None, "Preventive Maintenance", 45, 1,
     "Routine inspection.",
     "Blow-cleaned internal dust, checked fan speeds and temperatures, verified "
     "storage health and ran a memory test.", None, 2500.00,
     "Completed - Equipment Working"),
    ("ICT-005", None, "Network Maintenance", 21, 1,
     "Scheduled firmware and configuration review.",
     "Backed up the configuration, applied the recommended firmware update and "
     "verified all switch ports.", None, 0.00, "Completed - Equipment Working"),
    ("ICT-017", None, "Inspection", 4, 2,
     "Intermittent restart under load - suspected power supply.",
     "Inspected the power supply, replaced the mains cable and arranged for a "
     "replacement power supply unit.", None, 0.00, "Deferred - Awaiting Parts"),
)

# --- Preventive schedules: (equipment tag, type, day offset, officer index,
#                            instructions, status)
SCHEDULES = (
    ("ICT-001", "Preventive Maintenance", 5, 1,
     "Quarterly dust clean, fan check and storage health check.", "Scheduled"),
    ("ICT-005", "Network Maintenance", 12, 1,
     "Back up switch configuration and review firmware release notes.", "Scheduled"),
    ("ICT-008", "Preventive Maintenance", 20, 2,
     "Server room check: fan filters, disk health, backup verification.", "Scheduled"),
    ("ICT-004", "Preventive Maintenance", 0, 2,
     "Clean the printer paper path and inspect the toner cartridge.", "Due"),
    ("ICT-006", "Inspection", -6, 1,
     "Inspect the router antennae and confirm the latest firmware.", "Overdue"),
    ("ICT-013", "Preventive Maintenance", -12, 2,
     "Clean the projector air filter and check lamp hours.", "Overdue"),
    ("ICT-015", "Preventive Maintenance", 30, 1,
     "Battery runtime test for the HR backup UPS.", "Scheduled"),
    ("ICT-002", "System Update", -20, 1,
     "Apply operating system and driver updates.", "Completed"),
)


# --------------------------------------------------------------------- helpers
def _get_or_create_department(name, description, location):
    existing = db.session.scalars(
        select(Department).where(Department.name == name)
    ).first()
    if existing is not None:
        return existing, False
    department = Department(name=name, description=description, location=location)
    db.session.add(department)
    db.session.flush()
    return department, True


def _get_or_create_category(name):
    existing = db.session.scalars(
        select(EquipmentCategory).where(EquipmentCategory.name == name)
    ).first()
    if existing is not None:
        return existing, False
    category = EquipmentCategory(name=name, description=f"{name} assets")
    db.session.add(category)
    db.session.flush()
    return category, True


def _account(email):
    return db.session.scalars(select(User).where(User.email == email)).first()


# ------------------------------------------------------------------------ seed
def seed() -> list:
    """Insert the sample data and return a human-readable summary."""
    app = create_app()
    summary = []

    with app.app_context():
        # 1. Accounts -------------------------------------------------------
        created_users = 0
        for full_name, email, password, role in ACCOUNTS:
            if _account(email) is not None:
                continue
            user = User(full_name=full_name, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            created_users += 1
        db.session.flush()
        summary.append(f"Accounts created: {created_users}")

        admin = _account("admin@cmims.local")
        officer_one = _account("officer1@cmims.local")
        officer_two = _account("officer2@cmims.local")
        officers = [officer_one, officer_two]
        actor = admin or officer_one
        if actor is None:  # pragma: no cover - accounts always exist by now
            raise RuntimeError("Seed accounts could not be created.")
        if admin is None:
            admin = actor

        # 2. Departments ----------------------------------------------------
        created_departments = 0
        departments = {}
        for name, description, location in DEPARTMENTS:
            department, created = _get_or_create_department(name, description, location)
            departments[name] = department
            created_departments += int(created)
        summary.append(f"Departments created: {created_departments}")

        # 3. Equipment-type catalogue ---------------------------------------
        created_categories = 0
        for name in EQUIPMENT_TYPES:
            _, created = _get_or_create_category(name)
            created_categories += int(created)
        summary.append(f"Equipment types created: {created_categories}")
        db.session.commit()

        # 4. Equipment ------------------------------------------------------
        created_equipment = 0
        equipment_by_tag = {}
        for (tag, name, type_name, manufacturer, model, serial, dept_name, location,
             purchase_days_ago, warranty_days, condition, status) in EQUIPMENT:
            existing = EquipmentService.find_by_asset_tag(tag)
            if existing is not None:
                equipment_by_tag[tag] = existing
                continue
            record = EquipmentService.create(
                {
                    "asset_tag": tag,
                    "equipment_name": name,
                    "equipment_type": type_name,
                    "manufacturer": manufacturer,
                    "model": model,
                    "serial_number": serial,
                    "department_id": departments[dept_name].id,
                    "location": location,
                    "purchase_date": TODAY - timedelta(days=purchase_days_ago),
                    "warranty_expiry_date": TODAY + timedelta(days=warranty_days),
                    "assigned_user_id": None,
                    "condition": condition,
                    "operational_status": status,
                    "description": f"{type_name} issued to the {dept_name}.",
                },
                actor=admin,
            )
            equipment_by_tag[tag] = record
            created_equipment += 1
        db.session.commit()
        summary.append(f"Equipment registered: {created_equipment}")

        # 5. Fault reports --------------------------------------------------
        created_faults = 0
        faults_by_title = {}
        for (tag, title, description, category, priority, days_ago, officer_index,
             final_status) in FAULTS:
            existing = db.session.scalars(
                select(FaultReport).where(FaultReport.fault_title == title)
            ).first()
            if existing is not None:
                faults_by_title[title] = existing
                continue
            equipment = equipment_by_tag[tag]
            fault = FaultService.create(
                {
                    "equipment_id": equipment.id,
                    "fault_title": title,
                    "fault_description": description,
                    "fault_category": category,
                    "priority": priority,
                    "date_discovered": TODAY - timedelta(days=days_ago),
                    "assigned_to": officers[officer_index - 1].id,
                },
                actor=officers[officer_index - 1],
            )
            # Keep the reported date realistic relative to the record itself.
            fault.created_at = fault.created_at - timedelta(days=1) if fault.created_at else None
            faults_by_title[title] = fault
            created_faults += 1
        db.session.commit()
        summary.append(f"Fault reports recorded: {created_faults}")

        # 6. Maintenance records -------------------------------------------
        created_maintenance = 0
        for (tag, fault_title, maint_type, days_ago, technician_index, diagnosis,
             work, parts, cost, outcome) in MAINTENANCE:
            equipment = equipment_by_tag[tag]
            fault = faults_by_title.get(fault_title) if fault_title else None
            already = db.session.scalars(
                select(MaintenanceRecord).where(
                    MaintenanceRecord.equipment_id == equipment.id,
                    MaintenanceRecord.maintenance_date == TODAY - timedelta(days=days_ago),
                )
            ).first()
            if already is not None:
                continue
            MaintenanceService.record_maintenance(
                {
                    "equipment_id": equipment.id,
                    "fault_report_id": fault.id if fault else None,
                    "maintenance_type": maint_type,
                    "work_performed": work,
                    "technician_id": officers[technician_index - 1].id,
                    "maintenance_date": TODAY - timedelta(days=days_ago),
                    "outcome": outcome,
                    "diagnosis": diagnosis,
                    "parts_replaced": parts,
                    "cost": cost,
                    "condition_after": equipment.condition,
                },
                actor=officers[technician_index - 1],
            )
            created_maintenance += 1
        db.session.commit()
        summary.append(f"Maintenance records logged: {created_maintenance}")

        # 7. Walk the faults through their lifecycle ------------------------
        for (tag, title, _d, _c, _p, _days, officer_index, final_status) in FAULTS:
            fault = faults_by_title.get(title)
            if fault is None or fault.status == final_status:
                continue
            officer = officers[officer_index - 1]
            path = {
                "Acknowledged": ["Acknowledged"],
                "Under Repair": ["Acknowledged", "Under Repair"],
                "Awaiting Parts": ["Acknowledged", "Under Repair", "Awaiting Parts"],
                "Resolved": ["Acknowledged", "Under Repair", "Resolved"],
                "Closed": ["Acknowledged", "Under Repair", "Resolved", "Closed"],
                "Reported": [],
            }.get(final_status, [])
            for step in path:
                if step == "Resolved":
                    FaultService.change_status(
                        fault, "Resolved", actor=officer,
                        notes="Repair completed and the equipment tested "
                              "successfully by the ICT officer.",
                    )
                elif step == "Under Repair":
                    FaultService.change_status(
                        fault, "Under Repair", actor=officer,
                        notes="Equipment collected for repair in the ICT workshop.",
                    )
                else:
                    FaultService.change_status(
                        fault, step, actor=officer,
                        notes=f"Fault moved to {step} by the ICT officer.",
                    )
            if title == "Laptop will not connect to the office Wi-Fi":
                FaultService.add_note(
                    fault, officer,
                    "Checked the wireless adapter driver and authenticated the "
                    "device against the access point; requested a network "
                    "configuration review.",
                )
        db.session.commit()

        # 8. Preventive-maintenance schedules ------------------------------
        created_schedules = 0
        for (tag, maint_type, day_offset, officer_index, instructions,
             status) in SCHEDULES:
            equipment = equipment_by_tag[tag]
            scheduled_date = TODAY + timedelta(days=day_offset)
            already = db.session.scalars(
                select(MaintenanceSchedule).where(
                    MaintenanceSchedule.equipment_id == equipment.id,
                    MaintenanceSchedule.scheduled_date == scheduled_date,
                )
            ).first()
            if already is not None:
                continue
            schedule = ScheduleService.create(
                {
                    "equipment_id": equipment.id,
                    "maintenance_type": maint_type,
                    "scheduled_date": scheduled_date,
                    "assigned_to": officers[officer_index - 1].id,
                    "instructions": instructions,
                    "notes": None,
                },
                actor=officers[officer_index - 1],
            )
            if status == "Completed":
                for record in equipment.maintenance_records:
                    if record.maintenance_date <= TODAY:
                        ScheduleService.complete(
                            schedule, actor=officers[officer_index - 1],
                            record_maintenance=False,
                        )
                        break
            elif status == "In Progress":
                schedule.status = "In Progress"
            created_schedules += 1
        db.session.commit()
        summary.append(f"Preventive schedules created: {created_schedules}")

        summary.append("Seeding complete (existing records were left untouched).")
    return summary


if __name__ == "__main__":
    for line in seed():
        print(line)
