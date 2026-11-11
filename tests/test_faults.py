"""Fault reporting tests: creation, reference numbers, status history, authorization."""

from datetime import date, timedelta

from extensions import db
from models.audit import AuditLog
from models.fault import FaultNote, FaultReport, FaultStatusHistory
from services.errors import TransitionError, ValidationError
from services.fault_service import FaultService
from tests.conftest import login_as


def _fault_payload(equipment_id, **overrides):
    payload = {
        "equipment_id": equipment_id,
        "fault_title": "Printer jams on duplex jobs",
        "fault_description": "The printer jams whenever a double-sided job is sent.",
        "fault_category": "Printer Problem",
        "priority": "High",
        "date_discovered": date.today().isoformat(),
        "assigned_to": 0,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- creation
def test_fault_can_be_recorded_for_existing_equipment(client, officer_user, equipment):
    login_as(client, "officer")
    response = client.post(
        "/faults/new", data=_fault_payload(equipment.id), follow_redirects=True
    )
    assert response.status_code == 200
    assert b"recorded successfully" in response.data

    stored = db.session.query(FaultReport).one()
    assert stored.equipment_id == equipment.id
    assert stored.reported_by == officer_user.id
    assert stored.status == "Reported"


def test_fault_reference_numbers_are_generated_correctly(app, officer_user, equipment):
    first = FaultService.create(
        {
            "equipment_id": equipment.id,
            "fault_title": "First fault",
            "fault_description": "Description of the first fault.",
            "fault_category": "Other",
            "priority": "Low",
            "date_discovered": date(2026, 3, 1),
        },
        actor=officer_user,
    )
    second = FaultService.create(
        {
            "equipment_id": equipment.id,
            "fault_title": "Second fault",
            "fault_description": "Description of the second fault.",
            "fault_category": "Other",
            "priority": "Low",
            "date_discovered": date(2026, 3, 2),
        },
        actor=officer_user,
    )
    db.session.commit()

    assert first.reference_number == "FR-2026-0001"
    assert second.reference_number == "FR-2026-0002"


def test_fault_records_are_stored_in_the_database(app, officer_user, equipment):
    fault = FaultService.create(
        {
            "equipment_id": equipment.id,
            "fault_title": "Stored fault",
            "fault_description": "A fault that must be persisted.",
            "fault_category": "Hardware Failure",
            "priority": "Critical",
            "date_discovered": date.today(),
        },
        actor=officer_user,
    )
    db.session.commit()

    stored = db.session.get(FaultReport, fault.id)
    assert stored is not None
    assert stored.fault_title == "Stored fault"
    assert stored.equipment.asset_tag == "ICT-001"


def test_invalid_fault_data_is_rejected(client, officer_user, equipment):
    login_as(client, "officer")
    response = client.post(
        "/faults/new",
        data=_fault_payload(equipment.id, fault_title="", fault_description="short"),
        follow_redirects=True,
    )
    assert b"Fault title is required" in response.data or b"Describe the fault" in response.data
    assert db.session.query(FaultReport).count() == 0


def test_fault_for_unknown_equipment_is_rejected(app, officer_user):
    try:
        FaultService.create(
            {
                "equipment_id": 99999,
                "fault_title": "Ghost fault",
                "fault_description": "Reported against equipment that does not exist.",
                "fault_category": "Other",
                "priority": "Low",
                "date_discovered": date.today(),
            },
            actor=officer_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()


def test_future_discovery_date_is_rejected(app, officer_user, equipment):
    try:
        FaultService.create(
            {
                "equipment_id": equipment.id,
                "fault_title": "Time traveller fault",
                "fault_description": "Discovered in the future, which is impossible.",
                "fault_category": "Other",
                "priority": "Low",
                "date_discovered": date.today() + timedelta(days=5),
            },
            actor=officer_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()


# ---------------------------------------------------------------- status changes
def test_authorised_user_can_update_fault_status(client, officer_user, fault):
    login_as(client, "officer")
    response = client.post(
        f"/faults/{fault.id}/status",
        data={"status": "Acknowledged", "resolution_notes": "Seen by the ICT officer."},
        follow_redirects=True,
    )
    assert response.status_code == 200

    stored = db.session.get(FaultReport, fault.id)
    assert stored.status == "Acknowledged"


def test_fault_status_history_is_recorded(app, officer_user, fault):
    FaultService.change_status(fault, "Acknowledged", actor=officer_user, notes="Seen.")
    db.session.commit()

    history = (
        db.session.query(FaultStatusHistory)
        .filter_by(fault_report_id=fault.id)
        .order_by(FaultStatusHistory.id)
        .all()
    )
    # The initial "Reported" entry plus the acknowledgement.
    assert [row.new_status for row in history] == ["Reported", "Acknowledged"]
    assert history[-1].previous_status == "Reported"
    assert history[-1].changed_by == officer_user.id
    assert history[-1].changed_at is not None


def test_illegal_status_transition_is_refused(app, officer_user, fault):
    try:
        # Reported -> Resolved is not a legal transition.
        FaultService.change_status(fault, "Resolved", actor=officer_user, notes="Done")
        raise AssertionError("TransitionError was not raised")
    except (TransitionError, ValidationError):
        db.session.rollback()


def test_fault_cannot_be_resolved_without_a_repair_record(app, officer_user, fault):
    FaultService.change_status(fault, "Acknowledged", actor=officer_user)
    FaultService.change_status(fault, "Under Repair", actor=officer_user)
    db.session.commit()

    try:
        FaultService.change_status(
            fault, "Resolved", actor=officer_user, notes="Resolved without a repair."
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError as error:
        assert "no maintenance/repair record" in str(error)
        db.session.rollback()


def test_fault_can_be_resolved_once_a_repair_exists(app, officer_user, fault, maintenance):
    FaultService.change_status(fault, "Acknowledged", actor=officer_user)
    FaultService.change_status(fault, "Under Repair", actor=officer_user)
    FaultService.change_status(
        fault, "Resolved", actor=officer_user, notes="Repair completed and tested."
    )
    db.session.commit()

    stored = db.session.get(FaultReport, fault.id)
    assert stored.status == "Resolved"
    assert stored.resolved_at is not None
    assert stored.resolution_notes == "Repair completed and tested."


def test_fault_can_be_closed_after_resolution(app, officer_user, fault, maintenance):
    for status, notes in (
        ("Acknowledged", ""),
        ("Under Repair", ""),
        ("Resolved", "Repair completed."),
        ("Closed", "User confirmed the fix."),
    ):
        FaultService.change_status(fault, status, actor=officer_user, notes=notes)
    db.session.commit()

    stored = db.session.get(FaultReport, fault.id)
    assert stored.status == "Closed"
    assert stored.available_transitions() == ()


def test_priority_can_be_changed(app, officer_user, fault):
    FaultService.change_priority(fault, "Critical", actor=officer_user, notes="Escalated")
    db.session.commit()
    assert db.session.get(FaultReport, fault.id).priority == "Critical"


def test_fault_can_be_assigned_and_unassigned(app, officer_user, officer_two, fault):
    FaultService.assign(fault, officer_two.id, actor=officer_user)
    db.session.commit()
    assert db.session.get(FaultReport, fault.id).assigned_to == officer_two.id
    assert fault.assignee_name == officer_two.full_name

    FaultService.assign(fault, None, actor=officer_user)
    db.session.commit()
    assert db.session.get(FaultReport, fault.id).assigned_to is None
    assert fault.assignee_name == "Unassigned"


def test_faults_cannot_be_assigned_to_a_viewer(app, officer_user, viewer_user, fault):
    try:
        FaultService.assign(fault, viewer_user.id, actor=officer_user)
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()


def test_troubleshooting_notes_are_stored(client, officer_user, fault):
    login_as(client, "officer")
    client.post(
        f"/faults/{fault.id}/notes",
        data={"body": "Reseated the memory modules and re-tested."},
        follow_redirects=True,
    )
    notes = db.session.query(FaultNote).filter_by(fault_report_id=fault.id).all()
    assert len(notes) == 1
    assert notes[0].author_id == officer_user.id


def test_empty_note_is_rejected(app, officer_user, fault):
    try:
        FaultService.add_note(fault, officer_user, "   ")
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()


# -------------------------------------------------------------- search & filter
def test_fault_search_and_filters(client, admin_user, fault):
    login_as(client, "admin")
    reference = fault.reference_number.encode()
    assert reference in client.get(f"/faults/?search={fault.reference_number}").data
    assert reference in client.get(f"/faults/?search=ICT-001").data
    assert reference in client.get("/faults/?status=Reported").data
    assert reference in client.get("/faults/?priority=High").data
    assert reference not in client.get("/faults/?status=Closed").data


def test_fault_list_paginates(client, admin_user, officer_user, equipment):
    login_as(client, "admin")
    for index in range(20):
        FaultService.create(
            {
                "equipment_id": equipment.id,
                "fault_title": f"Fault number {index}",
                "fault_description": f"Description for fault number {index}.",
                "fault_category": "Other",
                "priority": "Low",
                "date_discovered": date.today(),
            },
            actor=officer_user,
        )
    db.session.commit()

    assert b"page 1 of 2" in client.get("/faults/").data
    assert client.get("/faults/?page=2").status_code == 200
