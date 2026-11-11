"""Shared pytest fixtures.

Every test runs against a **throwaway SQLite database inside a temporary
directory**, so the development database (``instance/computer_maintenance.db``)
is never touched.  CSRF validation is switched off by ``TestingConfig`` so the
test client can post forms directly; every other security control -
authentication, role authorization, validation, audit logging - stays on.
"""

import sys
from datetime import date
from pathlib import Path

import pytest

# Make the project importable when pytest is run from any directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app  # noqa: E402
from config import TestingConfig  # noqa: E402
from extensions import db as _db  # noqa: E402
from models import Department, EquipmentCategory, User  # noqa: E402

PASSWORDS = {
    "admin": "Admin@12345",
    "officer": "Officer@12345",
    "officer2": "Officer@23456",
    "viewer": "Viewer@12345",
}


# --------------------------------------------------------------------- application
@pytest.fixture()
def app(tmp_path):
    """A fresh application + database for one test."""
    db_path = tmp_path / "test_cmims.db"
    application = create_app(
        TestingConfig,
        database_uri="sqlite:///" + db_path.as_posix(),
        upload_folder=str(tmp_path / "uploads"),
    )
    with application.app_context():
        _db.create_all()
        _seed_reference_data()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    """Flask test client (no CSRF, session cookies handled for us)."""
    return app.test_client()


def _seed_reference_data():
    """Departments + equipment types that the seeded tests rely on."""
    departments = {
        "ICT Department": "Manages computer systems.",
        "Accounts Department": "Finance and payroll.",
        "Registry Department": "Registry and archives.",
    }
    for name, description in departments.items():
        _db.session.add(Department(name=name, description=description, location="Block A"))
    for name in (
        "Desktop Computer",
        "Laptop Computer",
        "Printer",
        "Network Switch",
        "Router",
        "UPS",
        "Server",
        "Monitor",
        "Scanner",
        "Keyboard",
        "Projector",
        "Other ICT Equipment",
    ):
        _db.session.add(EquipmentCategory(name=name))
    _db.session.commit()


# --------------------------------------------------------------------------- users
def make_user(full_name, email, password, role):
    """Create and persist an account."""
    user = User(full_name=full_name, email=email, role=role)
    user.set_password(password)
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture()
def admin_user(app):
    return make_user("Admin User", "admin@test.local", PASSWORDS["admin"], "admin")


@pytest.fixture()
def officer_user(app):
    return make_user("Officer One", "officer1@test.local", PASSWORDS["officer"], "ict_officer")


@pytest.fixture()
def officer_two(app):
    return make_user("Officer Two", "officer2@test.local", PASSWORDS["officer2"], "ict_officer")


@pytest.fixture()
def viewer_user(app):
    return make_user("Viewer User", "viewer@test.local", PASSWORDS["viewer"], "viewer")


@pytest.fixture()
def all_users(admin_user, officer_user, officer_two, viewer_user):
    return {
        "admin": admin_user,
        "officer": officer_user,
        "officer2": officer_two,
        "viewer": viewer_user,
    }


# ---------------------------------------------------------------------- login aid
def login(client, email, password):
    """Sign in through the real login form."""
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def login_as(client, role):
    """Sign in as one of the standard test accounts."""
    emails = {
        "admin": "admin@test.local",
        "officer": "officer1@test.local",
        "officer2": "officer2@test.local",
        "viewer": "viewer@test.local",
    }
    return login(client, emails[role], PASSWORDS[role])


@pytest.fixture()
def logout(client):
    def _logout():
        return client.post("/logout", follow_redirects=True)

    return _logout


# ------------------------------------------------------------------ domain data
@pytest.fixture()
def department(app):
    return _db.session.query(Department).filter_by(name="ICT Department").one()


@pytest.fixture()
def equipment(app, admin_user, department):
    """One registered asset, created through the service layer."""
    from services.equipment_service import EquipmentService

    record = EquipmentService.create(
        {
            "asset_tag": "ICT-001",
            "equipment_name": "HP ProDesk Desktop Computer",
            "equipment_type": "Desktop Computer",
            "manufacturer": "HP",
            "model": "ProDesk 400 G7",
            "serial_number": "SN-1001",
            "department_id": department.id,
            "location": "ICT Office",
            "purchase_date": date(2024, 1, 15),
            "warranty_expiry_date": date(2027, 1, 15),
            "condition": "Good",
            "operational_status": "In Use",
            "description": "Test asset",
        },
        actor=admin_user,
    )
    _db.session.commit()
    return record


@pytest.fixture()
def fault(app, officer_user, equipment):
    """One fault report created through the service layer."""
    from services.fault_service import FaultService

    record = FaultService.create(
        {
            "equipment_id": equipment.id,
            "fault_title": "Desktop will not power on",
            "fault_description": "The desktop shows no sign of power when the button is pressed.",
            "fault_category": "Computer Won't Start",
            "priority": "High",
            "date_discovered": date.today(),
            "assigned_to": None,
        },
        actor=officer_user,
    )
    _db.session.commit()
    return record


@pytest.fixture()
def maintenance(app, officer_user, equipment, fault):
    """One maintenance record linked to the fault fixture."""
    from services.maintenance_service import MaintenanceService

    record = MaintenanceService.record_maintenance(
        {
            "equipment_id": equipment.id,
            "fault_report_id": fault.id,
            "maintenance_type": "Hardware Repair",
            "work_performed": "Replaced the power supply unit and tested the machine.",
            "technician_id": officer_user.id,
            "maintenance_date": date.today(),
            "outcome": "Completed - Equipment Working",
            "condition_after": equipment.condition,
        },
        actor=officer_user,
    )
    _db.session.commit()
    return record


@pytest.fixture()
def schedule(app, officer_user, equipment):
    """One preventive schedule."""
    from datetime import timedelta

    from services.maintenance_service import ScheduleService

    record = ScheduleService.create(
        {
            "equipment_id": equipment.id,
            "maintenance_type": "Preventive Maintenance",
            "scheduled_date": date.today() + timedelta(days=7),
            "assigned_to": officer_user.id,
            "instructions": "Clean the fans and check the storage health.",
            "notes": None,
        },
        actor=officer_user,
    )
    _db.session.commit()
    return record
