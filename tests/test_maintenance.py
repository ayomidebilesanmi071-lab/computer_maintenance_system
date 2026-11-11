"""Maintenance tests: records, equipment/fault links, schedules, completion."""

from datetime import date, timedelta

from extensions import db
from models.constants import (
    SCHEDULE_COMPLETED,
    SCHEDULE_DUE,
    SCHEDULE_OVERDUE,
    STATUS_FAULTY,
    STATUS_IN_USE,
    STATUS_UNDER_MAINTENANCE,
)
from models.equipment import Equipment
from models.maintenance import MaintenanceRecord, MaintenanceSchedule
from services.errors import TransitionError, ValidationError
from services.maintenance_service import MaintenanceService, ScheduleService
from tests.conftest import login_as


def _maintenance_payload(equipment_id, technician_id, **overrides):
    payload = {
        "equipment_id": equipment_id,
        "fault_report_id": None,
        "maintenance_type": "Preventive Maintenance",
        "diagnosis": "Routine inspection.",
        "work_performed": "Cleaned the fans and tested the machine.",
        "parts_replaced": None,
        "technician_id": technician_id,
        "maintenance_date": date.today().isoformat(),
        "cost": 0,
        "condition_after": "Good",
        "outcome": "Completed - Equipment Working",
        "notes": None,
    }
    payload.update(overrides)
    return payload


# ----------------------------------------------------------------------- records
def test_maintenance_record_can_be_created(app, officer_user, equipment):
    record = MaintenanceService.record_maintenance(
        _maintenance_payload(equipment.id, officer_user.id), actor=officer_user
    )
    db.session.commit()

    stored = db.session.get(MaintenanceRecord, record.id)
    assert stored is not None
    assert stored.equipment_id == equipment.id
    assert stored.technician_id == officer_user.id
    assert stored.recorded_by == officer_user.id


def test_maintenance_record_is_linked_to_equipment_and_fault(app, officer_user, equipment, fault):
    record = MaintenanceService.record_maintenance(
        _maintenance_payload(equipment.id, officer_user.id, fault_report_id=fault.id),
        actor=officer_user,
    )
    db.session.commit()

    assert record.equipment.asset_tag == "ICT-001"
    assert record.fault_report.reference_number == fault.reference_number
    assert record in list(equipment.maintenance_records)


def test_maintenance_linked_to_a_foreign_fault_is_rejected(app, officer_user, equipment, fault, department):
    """A repair must belong to the equipment the fault was reported against."""
    from services.equipment_service import EquipmentService

    other = EquipmentService.create(
        {
            "asset_tag": "ICT-777",
            "equipment_name": "Second desktop",
            "equipment_type": "Desktop Computer",
            "department_id": department.id,
            "condition": "Good",
            "operational_status": "In Use",
        },
        actor=officer_user,
    )
    db.session.commit()

    try:
        MaintenanceService.record_maintenance(
            _maintenance_payload(other.id, officer_user.id, fault_report_id=fault.id),
            actor=officer_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError as error:
        assert "different piece of equipment" in str(error)
        db.session.rollback()


def test_equipment_maintenance_history_can_be_retrieved(app, officer_user, equipment):
    for offset in (0, 5, 10):
        MaintenanceService.record_maintenance(
            _maintenance_payload(
                equipment.id,
                officer_user.id,
                maintenance_date=(date.today() - timedelta(days=offset)).isoformat(),
            ),
            actor=officer_user,
        )
    db.session.commit()

    history = MaintenanceService.history_for(equipment)
    assert len(history) == 3
    assert equipment.maintenance_count == 3
    assert equipment.last_maintenance_date == date.today()


def test_invalid_maintenance_data_is_rejected(app, officer_user, equipment):
    # Missing work performed.
    try:
        MaintenanceService.record_maintenance(
            _maintenance_payload(equipment.id, officer_user.id, work_performed="  "),
            actor=officer_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()

    # Unknown outcome.
    try:
        MaintenanceService.record_maintenance(
            _maintenance_payload(equipment.id, officer_user.id, outcome="Something else"),
            actor=officer_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()

    # Future maintenance date.
    try:
        MaintenanceService.record_maintenance(
            _maintenance_payload(
                equipment.id,
                officer_user.id,
                maintenance_date=(date.today() + timedelta(days=1)).isoformat(),
            ),
            actor=officer_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()

    # Negative cost.
    try:
        MaintenanceService.record_maintenance(
            _maintenance_payload(equipment.id, officer_user.id, cost=-100),
            actor=officer_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()


def test_successful_repair_returns_equipment_to_service(app, officer_user, equipment):
    equipment.operational_status = STATUS_FAULTY
    db.session.commit()

    MaintenanceService.record_maintenance(
        _maintenance_payload(equipment.id, officer_user.id), actor=officer_user
    )
    db.session.commit()

    assert db.session.get(Equipment, equipment.id).operational_status == STATUS_IN_USE


def test_deferred_repair_marks_equipment_under_maintenance(app, officer_user, equipment):
    MaintenanceService.record_maintenance(
        _maintenance_payload(
            equipment.id,
            officer_user.id,
            outcome="Deferred - Awaiting Parts",
            cost=0,
        ),
        actor=officer_user,
    )
    db.session.commit()

    assert (
        db.session.get(Equipment, equipment.id).operational_status
        == STATUS_UNDER_MAINTENANCE
    )


def test_unsuccessful_repair_marks_equipment_faulty(app, officer_user, equipment):
    MaintenanceService.record_maintenance(
        _maintenance_payload(
            equipment.id,
            officer_user.id,
            outcome="Unsuccessful - Fault Persists",
        ),
        actor=officer_user,
    )
    db.session.commit()

    assert db.session.get(Equipment, equipment.id).operational_status == STATUS_FAULTY


def test_maintenance_record_can_be_edited(client, admin_user, officer_user, equipment, maintenance):
    login_as(client, "admin")
    response = client.post(
        f"/maintenance/{maintenance.id}/edit",
        data=_maintenance_payload(
            equipment.id,
            officer_user.id,
            work_performed="Replaced the power supply and cleaned the heat sink.",
        ),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "cleaned the heat sink" in db.session.get(MaintenanceRecord, maintenance.id).work_performed


# --------------------------------------------------------------------- schedules
def test_schedule_can_be_created(app, officer_user, equipment):
    schedule = ScheduleService.create(
        {
            "equipment_id": equipment.id,
            "maintenance_type": "Preventive Maintenance",
            "scheduled_date": date.today() + timedelta(days=10),
            "assigned_to": officer_user.id,
            "instructions": "Service the cooling system.",
            "notes": None,
        },
        actor=officer_user,
    )
    db.session.commit()

    stored = db.session.get(MaintenanceSchedule, schedule.id)
    assert stored.equipment_id == equipment.id
    assert stored.assigned_to == officer_user.id


def test_schedule_requires_an_ict_officer(app, admin_user, viewer_user, equipment):
    try:
        ScheduleService.create(
            {
                "equipment_id": equipment.id,
                "maintenance_type": "Inspection",
                "scheduled_date": date.today(),
                "assigned_to": viewer_user.id,
                "instructions": None,
                "notes": None,
            },
            actor=admin_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()


def test_completed_schedule_can_be_updated_and_records_maintenance(app, officer_user, equipment, schedule):
    ScheduleService.complete(schedule, actor=officer_user)
    db.session.commit()

    stored = db.session.get(MaintenanceSchedule, schedule.id)
    assert stored.status == SCHEDULE_COMPLETED
    assert stored.completed_at is not None
    assert stored.maintenance_record is not None
    assert stored.maintenance_record.equipment_id == equipment.id


def test_completing_a_schedule_twice_is_refused(app, officer_user, schedule):
    ScheduleService.complete(schedule, actor=officer_user, record_maintenance=False)
    db.session.commit()

    try:
        ScheduleService.complete(schedule, actor=officer_user)
        raise AssertionError("TransitionError was not raised")
    except TransitionError:
        db.session.rollback()


def test_overdue_and_due_statuses_are_recalculated(app, officer_user, equipment):
    overdue = ScheduleService.create(
        {
            "equipment_id": equipment.id,
            "maintenance_type": "Inspection",
            "scheduled_date": date.today() - timedelta(days=3),
            "assigned_to": officer_user.id,
            "instructions": None,
            "notes": None,
        },
        actor=officer_user,
    )
    due = ScheduleService.create(
        {
            "equipment_id": equipment.id,
            "maintenance_type": "Inspection",
            "scheduled_date": date.today(),
            "assigned_to": officer_user.id,
            "instructions": None,
            "notes": None,
        },
        actor=officer_user,
    )
    db.session.commit()

    ScheduleService.refresh_statuses()
    db.session.commit()

    assert db.session.get(MaintenanceSchedule, overdue.id).status == SCHEDULE_OVERDUE
    assert db.session.get(MaintenanceSchedule, due.id).status == SCHEDULE_DUE
    assert overdue in ScheduleService.upcoming(7)


def test_schedule_can_be_cancelled(app, officer_user, schedule):
    ScheduleService.cancel(schedule, actor=officer_user, reason="Equipment withdrawn.")
    db.session.commit()
    assert db.session.get(MaintenanceSchedule, schedule.id).status == "Cancelled"


def test_maintenance_history_and_schedule_pages_render(client, admin_user, maintenance, schedule):
    login_as(client, "admin")
    assert client.get("/maintenance/").status_code == 200
    assert client.get(f"/maintenance/{maintenance.id}").status_code == 200
    assert client.get("/maintenance/schedules").status_code == 200
    assert client.get(f"/maintenance/schedules/{schedule.id}").status_code == 200


def test_maintenance_filters_return_matching_records(client, admin_user, maintenance):
    login_as(client, "admin")
    assert b"ICT-001" in client.get("/maintenance/?maintenance_type=Hardware%20Repair").data
    assert b"ICT-001" not in client.get("/maintenance/?maintenance_type=Inspection").data
    assert b"ICT-001" in client.get("/maintenance/?search=ICT-001").data
