"""Audit tests: entries are written, complete, and cannot be altered."""

from datetime import date

from extensions import db
from models.audit import AuditLog
from services.equipment_service import EquipmentService
from services.fault_service import FaultService
from services.maintenance_service import MaintenanceService
from services.user_service import UserService
from tests.conftest import login_as


def _entries(**filters):
    query = db.session.query(AuditLog)
    for key, value in filters.items():
        query = query.filter(getattr(AuditLog, key) == value)
    return query.order_by(AuditLog.id).all()


def test_registering_equipment_creates_an_audit_entry(app, admin_user, department):
    equipment = EquipmentService.create(
        {
            "asset_tag": "ICT-300",
            "equipment_name": "Audited desktop",
            "equipment_type": "Desktop Computer",
            "department_id": department.id,
            "condition": "Good",
            "operational_status": "In Use",
        },
        actor=admin_user,
    )
    db.session.commit()

    entries = _entries(entity_type="equipment", entity_id=equipment.id)
    assert entries, "Registering equipment must create an audit entry"
    entry = entries[0]
    assert entry.user_id == admin_user.id
    assert entry.action == "create"
    assert entry.timestamp is not None
    assert "registered equipment ICT-300" in entry.description
    assert entry.actor == admin_user.full_name


def test_reporting_a_fault_creates_an_audit_entry(app, officer_user, equipment):
    fault = FaultService.create(
        {
            "equipment_id": equipment.id,
            "fault_title": "Audited fault",
            "fault_description": "A fault reported to check the audit trail.",
            "fault_category": "Other",
            "priority": "Low",
            "date_discovered": date.today(),
        },
        actor=officer_user,
    )
    db.session.commit()

    entries = _entries(entity_type="fault_report", entity_id=fault.id)
    assert entries
    assert "reported fault" in entries[0].description
    assert fault.reference_number in entries[0].description


def test_status_change_creates_an_audit_entry_with_previous_and_new_status(
    app, officer_user, fault
):
    FaultService.change_status(fault, "Acknowledged", actor=officer_user, notes="Seen.")
    db.session.commit()

    entries = _entries(entity_type="fault_report", entity_id=fault.id, action="status_change")
    assert entries
    assert "from Reported to Acknowledged" in entries[-1].description
    assert entries[-1].user_id == officer_user.id


def test_recording_maintenance_creates_an_audit_entry(app, officer_user, equipment):
    record = MaintenanceService.record_maintenance(
        {
            "equipment_id": equipment.id,
            "fault_report_id": None,
            "maintenance_type": "Inspection",
            "work_performed": "Inspected the device and cleaned it.",
            "technician_id": officer_user.id,
            "maintenance_date": date.today(),
            "outcome": "Completed - Equipment Working",
            "condition_after": equipment.condition,
        },
        actor=officer_user,
    )
    db.session.commit()

    entries = _entries(entity_type="maintenance_record", entity_id=record.id)
    assert entries
    assert "recorded Inspection for equipment ICT-001" in entries[0].description


def test_creating_an_account_creates_an_audit_entry(app, admin_user):
    user = UserService.create_user(
        {
            "full_name": "New Officer",
            "email": "new.officer@test.local",
            "role": "ict_officer",
            "password": "Officer@2026",
        },
        actor=admin_user,
    )
    db.session.commit()

    entries = _entries(entity_type="user", entity_id=user.id)
    assert entries
    assert "created an ICT Officer account" in entries[0].description


def test_retiring_equipment_creates_an_audit_entry(app, admin_user, equipment):
    EquipmentService.retire(equipment, actor=admin_user)
    db.session.commit()

    entries = _entries(entity_type="equipment", entity_id=equipment.id, action="retire")
    assert entries
    assert "retired equipment ICT-001" in entries[0].description


def test_audit_entries_never_contain_passwords(app, admin_user):
    UserService.create_user(
        {
            "full_name": "Password Check",
            "email": "pw.check@test.local",
            "role": "viewer",
            "password": "SuperSecret@123",
        },
        actor=admin_user,
    )
    db.session.commit()

    for entry in db.session.query(AuditLog).all():
        assert "SuperSecret@123" not in entry.description
        assert "password_hash" not in entry.description


def test_audit_service_reuses_one_helper_rather_than_duplicated_logging(app):
    """The audit trail is written through the single shared service."""
    import inspect

    from services import audit_service as module

    source = inspect.getsource(module)
    assert "class AuditService" in source
    assert "def log(" in source
    # Only the service constructs audit rows.
    import services.equipment_service as equipment_module

    equipment_source = inspect.getsource(equipment_module)
    assert "AuditLog(" not in equipment_source
    assert "audit_service.AuditService.log(" in equipment_source


def test_administrator_can_view_the_audit_trail(client, admin_user, equipment):
    login_as(client, "admin")
    response = client.get("/admin/audit")
    assert response.status_code == 200
    assert b"registered equipment ICT-001" in response.data


def test_audit_trail_can_be_filtered(client, admin_user, equipment):
    login_as(client, "admin")
    assert b"registered equipment ICT-001" in client.get("/admin/audit?action=create").data
    assert b"registered equipment ICT-001" in client.get("/admin/audit?entity_type=equipment").data
    assert b"registered equipment ICT-001" not in client.get(
        "/admin/audit?entity_type=user"
    ).data


def test_application_exposes_no_route_that_modifies_audit_logs(app):
    """Audit rows are append-only through the application."""
    for rule in app.url_map.iter_rules():
        endpoint = rule.endpoint or ""
        assert "audit" not in endpoint or "log" in endpoint
        assert not endpoint.endswith(("audit_edit", "audit_delete", "audit_update"))

    from routes import register_blueprints  # noqa: F401  (import must not fail)

    assert all(
        method in {"GET", "HEAD", "OPTIONS"}
        for rule in app.url_map.iter_rules()
        if "audit" in (rule.endpoint or "")
        for method in rule.methods
    )


def test_officers_may_read_audit_history_but_not_manage_accounts(client, officer_user):
    login_as(client, "officer")
    assert client.get("/admin/audit").status_code == 200
    assert client.get("/admin/users").status_code == 403
