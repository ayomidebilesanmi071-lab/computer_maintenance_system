"""Equipment tests: registration, duplicate rejection, retrieval, editing, validation."""

from datetime import date, timedelta

from extensions import db
from models.equipment import Equipment, EquipmentStatusHistory
from services.equipment_service import EquipmentService
from services.errors import DuplicateError, ValidationError
from tests.conftest import login_as


def _new_equipment_payload(department_id, **overrides):
    payload = {
        "asset_tag": "ICT-900",
        "equipment_name": "Dell OptiPlex 3080 Desktop Computer",
        "equipment_type": "Desktop Computer",
        "manufacturer": "Dell",
        "model": "OptiPlex 3080",
        "serial_number": "SN-9001",
        "department_id": department_id,
        "location": "Registry Room",
        "purchase_date": "2025-02-01",
        "warranty_expiry_date": "2028-02-01",
        "condition": "Good",
        "operational_status": "In Use",
        "description": "Registered by the test suite.",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------- creation
def test_authorised_user_can_register_equipment(client, officer_user, department):
    login_as(client, "officer")
    response = client.post(
        "/equipment/new",
        data=_new_equipment_payload(department.id),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"registered successfully" in response.data

    stored = EquipmentService.find_by_asset_tag("ICT-900")
    assert stored is not None
    assert stored.department_id == department.id
    assert stored.registered_by == officer_user.id


def test_duplicate_asset_tag_is_rejected(client, officer_user, department, equipment):
    login_as(client, "officer")
    response = client.post(
        "/equipment/new",
        data=_new_equipment_payload(department.id, asset_tag=equipment.asset_tag, serial_number="SN-9999"),
        follow_redirects=True,
    )
    assert b"already registered" in response.data
    assert db.session.query(Equipment).filter_by(asset_tag=equipment.asset_tag).count() == 1


def test_duplicate_serial_number_is_rejected(client, officer_user, department, equipment):
    login_as(client, "officer")
    response = client.post(
        "/equipment/new",
        data=_new_equipment_payload(department.id, asset_tag="ICT-901", serial_number="SN-1001"),
        follow_redirects=True,
    )
    assert b"already belongs to" in response.data


def test_service_rejects_duplicate_asset_tag(app, admin_user, department, equipment):
    """The service, not just the form, is the security boundary."""
    try:
        EquipmentService.create(
            {
                "asset_tag": equipment.asset_tag,
                "equipment_name": "Another desktop",
                "equipment_type": "Desktop Computer",
                "department_id": department.id,
                "condition": "Good",
                "operational_status": "In Use",
            },
            actor=admin_user,
        )
        raise AssertionError("DuplicateError was not raised")
    except DuplicateError:
        db.session.rollback()


def test_invalid_equipment_data_is_rejected(client, admin_user, department):
    login_as(client, "admin")
    # Warranty expiry before the purchase date must fail validation.
    response = client.post(
        "/equipment/new",
        data=_new_equipment_payload(department.id, warranty_expiry_date="2020-01-01"),
        follow_redirects=True,
    )
    assert b"Warranty expiry date cannot be earlier" in response.data
    assert EquipmentService.find_by_asset_tag("ICT-900") is None


def test_future_purchase_date_is_rejected(app, admin_user, department):
    future = date.today() + timedelta(days=30)
    try:
        EquipmentService.create(
            {
                "asset_tag": "ICT-902",
                "equipment_name": "Future desktop",
                "equipment_type": "Desktop Computer",
                "department_id": department.id,
                "purchase_date": future,
                "condition": "Good",
                "operational_status": "In Use",
            },
            actor=admin_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError as error:
        assert "future" in str(error).lower()
        db.session.rollback()


def test_unknown_department_is_rejected(app, admin_user):
    try:
        EquipmentService.create(
            {
                "asset_tag": "ICT-903",
                "equipment_name": "Orphan desktop",
                "equipment_type": "Desktop Computer",
                "department_id": 99999,
                "condition": "Good",
                "operational_status": "In Use",
            },
            actor=admin_user,
        )
        raise AssertionError("ValidationError was not raised")
    except ValidationError:
        db.session.rollback()


def test_empty_asset_tag_is_rejected(client, admin_user, department):
    login_as(client, "admin")
    response = client.post(
        "/equipment/new",
        data=_new_equipment_payload(department.id, asset_tag=""),
        follow_redirects=True,
    )
    assert b"Asset tag is required" in response.data or b"Asset tag" in response.data


# -------------------------------------------------------------------- retrieval
def test_equipment_details_can_be_retrieved(client, admin_user, equipment):
    login_as(client, "admin")
    response = client.get(f"/equipment/{equipment.id}")
    assert response.status_code == 200
    assert b"ICT-001" in response.data
    assert b"HP ProDesk Desktop Computer" in response.data


def test_unknown_equipment_returns_404(client, admin_user):
    login_as(client, "admin")
    assert client.get("/equipment/4242").status_code == 404


# ----------------------------------------------------------------------- editing
def test_authorised_user_can_edit_equipment(client, admin_user, equipment):
    login_as(client, "admin")
    response = client.post(
        f"/equipment/{equipment.id}/edit",
        data=_new_equipment_payload(
            equipment.department_id,
            asset_tag=equipment.asset_tag,
            equipment_name="Renamed desktop computer",
            serial_number="SN-1001",
        ),
        follow_redirects=True,
    )
    assert b"updated" in response.data

    stored = db.session.get(Equipment, equipment.id)
    assert stored.equipment_name == "Renamed desktop computer"


def test_status_change_is_recorded_in_history(client, admin_user, equipment):
    login_as(client, "admin")
    response = client.post(
        f"/equipment/{equipment.id}/status",
        data={
            "condition": "Fair",
            "operational_status": "Under Maintenance",
            "notes": "Reported by the department.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    stored = db.session.get(Equipment, equipment.id)
    assert stored.condition == "Fair"
    assert stored.operational_status == "Under Maintenance"

    history = (
        db.session.query(EquipmentStatusHistory)
        .filter_by(equipment_id=equipment.id)
        .all()
    )
    assert history, "A status change must create a history row"
    latest = history[-1]
    assert latest.previous_status == "In Use"
    assert latest.new_status == "Under Maintenance"
    assert latest.changed_by == admin_user.id


def test_retiring_equipment_keeps_the_record(client, admin_user, equipment):
    login_as(client, "admin")
    response = client.post(
        f"/equipment/{equipment.id}/retire",
        data={"reason": "Beyond economical repair", "confirm": "yes"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    stored = db.session.get(Equipment, equipment.id)
    assert stored is not None, "Retirement must never delete the asset"
    assert stored.operational_status == "Retired"


def test_search_and_filter_return_matching_records(client, admin_user, equipment):
    login_as(client, "admin")
    assert b"ICT-001" in client.get("/equipment/?search=ICT-001").data
    assert b"ICT-001" in client.get("/equipment/?condition=Good").data
    assert b"ICT-001" not in client.get("/equipment/?condition=Damaged").data
    assert b"ICT-001" not in client.get("/equipment/?search=ICT-999").data


def test_equipment_list_paginates(client, admin_user, department):
    login_as(client, "admin")
    for index in range(20):
        EquipmentService.create(
            {
                "asset_tag": f"ICT-{500 + index}",
                "equipment_name": f"Asset {index}",
                "equipment_type": "Desktop Computer",
                "department_id": department.id,
                "condition": "Good",
                "operational_status": "In Use",
            },
            actor=admin_user,
        )
    db.session.commit()

    page_one = client.get("/equipment/")
    assert b"page 1 of 2" in page_one.data
    page_two = client.get("/equipment/?page=2")
    assert page_two.status_code == 200
    assert page_one.data != page_two.data


def test_equipment_relationships_work(app, equipment, fault, maintenance):
    """Equipment -> department, faults, maintenance and history."""
    stored = db.session.get(Equipment, equipment.id)
    assert stored.department.name == "ICT Department"
    assert stored.department.equipment_count >= 1
    assert stored.fault_reports[0].reference_number == fault.reference_number
    assert stored.maintenance_records[0].id == maintenance.id
    assert stored.maintenance_count == 1
    assert stored.open_fault_count == 1
    assert stored.has_open_faults is True


def test_equipment_model_validates_condition(app, equipment):
    try:
        equipment.update_condition("Not A Condition")
        raise AssertionError("ValueError was not raised")
    except ValueError:
        pass
