"""Database/model tests: relationships, encapsulated behaviour and constraints."""

from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.audit import AuditLog
from models.constants import (
    CONDITIONS,
    FAULT_REPORTED,
    FAULT_STATUS_TRANSITIONS,
    ROLE_ADMIN,
    ROLE_OFFICER,
    ROLE_VIEWER,
    STATUS_FAULTY,
)
from models.department import Department
from models.equipment import Equipment
from models.fault import FaultReport
from models.roles import get_role
from models.user import User


# ------------------------------------------------------------------- accounts
def test_user_role_objects_are_polymorphic(app, admin_user, officer_user, viewer_user):
    assert admin_user.role_object.name == ROLE_ADMIN
    assert officer_user.role_object.name == ROLE_OFFICER
    assert viewer_user.role_object.name == ROLE_VIEWER
    assert admin_user.role_label == "Administrator"
    assert officer_user.role_label == "ICT Officer"


def test_unknown_role_raises_instead_of_defaulting_to_access(app):
    with pytest.raises(ValueError):
        get_role("superuser")


def test_user_can_activate_and_deactivate(app, officer_user):
    assert officer_user.is_active is True
    officer_user.deactivate()
    assert officer_user.is_active is False
    officer_user.activate()
    assert officer_user.is_active is True


def test_email_must_be_unique(app, admin_user):
    duplicate = User(full_name="Impostor", email=admin_user.email, role=ROLE_VIEWER)
    duplicate.set_password("Password@123")
    db.session.add(duplicate)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_user_and_audit_log_relationship(app, admin_user, department):
    from services.equipment_service import EquipmentService

    equipment = EquipmentService.create(
        {
            "asset_tag": "ICT-400",
            "equipment_name": "Relationship desktop",
            "equipment_type": "Desktop Computer",
            "department_id": department.id,
            "condition": "Good",
            "operational_status": "In Use",
        },
        actor=admin_user,
    )
    db.session.commit()

    assert equipment.registrar.id == admin_user.id
    assert equipment in list(admin_user.registered_equipment)
    assert admin_user.audit_logs.count() >= 1
    assert all(isinstance(row, AuditLog) for row in admin_user.audit_logs.all())


# --------------------------------------------------------------- departments
def test_department_equipment_relationship(app, department, equipment):
    assert equipment in department.equipment
    assert department.equipment_count == len(department.equipment)
    assert department.display_location == "Block A"


# ------------------------------------------------------------------ equipment
def test_equipment_encapsulated_properties(app, equipment):
    assert equipment.display_name == equipment.equipment_name
    assert equipment.is_retired is False
    assert equipment.is_faulty is False
    assert equipment.warranty_status in {"Active", "Expiring Soon", "Expired", "Not recorded"}
    assert equipment.warranty_status == "Active"


def test_equipment_warranty_status_transitions(app, equipment):
    equipment.warranty_expiry_date = date.today() - timedelta(days=1)
    assert equipment.warranty_status == "Expired"
    equipment.warranty_expiry_date = date.today() + timedelta(days=10)
    assert equipment.warranty_status == "Expiring Soon"
    equipment.warranty_expiry_date = None
    assert equipment.warranty_status == "Not recorded"


def test_equipment_asset_tag_must_be_unique(app, admin_user, department, equipment):
    duplicate = Equipment(
        asset_tag=equipment.asset_tag,
        equipment_name="Duplicate tag",
        equipment_type="Desktop Computer",
        department_id=department.id,
        condition="Good",
        operational_status="In Use",
        registered_by=admin_user.id,
    )
    db.session.add(duplicate)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_equipment_condition_must_be_a_known_value(app, equipment):
    with pytest.raises(ValueError):
        equipment.update_condition("Broken")
    assert equipment.condition in CONDITIONS


def test_equipment_status_history_relationship(app, equipment, admin_user):
    from services.equipment_service import EquipmentService

    EquipmentService.change_status(equipment, STATUS_FAULTY, actor=admin_user, notes="Failed")
    db.session.commit()

    assert equipment.status_history
    assert equipment.status_history[0].change_summary == "In Use → Faulty"
    assert equipment.is_faulty is True


def test_fault_and_maintenance_relationships(app, equipment, fault, maintenance):
    stored = db.session.get(FaultReport, fault.id)
    assert stored.equipment.id == equipment.id
    assert stored.reporter is not None
    assert stored.maintenance_records[0].id == maintenance.id
    assert maintenance.fault_report.id == fault.id
    assert maintenance.technician_id == fault.reported_by


def test_fault_reference_number_is_unique(app, officer_user, equipment, fault):
    duplicate = FaultReport(
        reference_number=fault.reference_number,
        equipment_id=equipment.id,
        reported_by=officer_user.id,
        fault_title="Duplicate reference",
        fault_description="Should not be allowed to save.",
        fault_category="Other",
        priority="Low",
        date_discovered=date.today(),
        status=FAULT_REPORTED,
    )
    db.session.add(duplicate)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_fault_status_machine_is_declared_in_one_place(app, fault):
    assert fault.available_transitions() == FAULT_STATUS_TRANSITIONS[FAULT_REPORTED]
    assert fault.can_transition_to("Acknowledged") is True
    assert fault.can_transition_to("Closed") is False


def test_audit_log_record_truncates_over_long_descriptions(app, admin_user):
    entry = AuditLog.record(admin_user, "create", "equipment", 1, "x" * 800)
    assert len(entry.description) <= 500
    assert entry.description.endswith("...")


def test_audit_log_actor_defaults_to_system(app):
    entry = AuditLog.record(None, "login_failed", "user", None, "Failed sign-in attempt.")
    db.session.add(entry)
    db.session.commit()
    assert entry.actor == "System"
    assert entry.user_id is None
    assert entry.entity_label == "user"
