"""Interface smoke tests.

Walks every page a signed-in user can reach and asserts it renders without an
error, which also proves the templates, filters and macros are wired up.
"""

import pytest
from markupsafe import escape

from models.user import User  # noqa: F401  (ensures the model is registered)
from tests.conftest import login_as


def _pages_for(equipment_id, fault_id, record_id, schedule_id, user_id):
    return (
        "/",
        "/equipment/",
        f"/equipment/{equipment_id}",
        f"/equipment/{equipment_id}/history",
        "/equipment/new",
        f"/equipment/{equipment_id}/edit",
        "/faults/",
        f"/faults/{fault_id}",
        "/faults/new",
        "/maintenance/",
        f"/maintenance/{record_id}",
        f"/maintenance/{record_id}/edit",
        "/maintenance/new",
        "/maintenance/schedules",
        f"/maintenance/schedules/{schedule_id}",
        f"/maintenance/schedules/{schedule_id}/edit",
        "/maintenance/schedules/new",
        "/departments/",
        "/departments/categories",
        "/departments/new",
        "/reports/",
        "/reports/equipment",
        "/reports/faults",
        "/reports/maintenance",
        "/reports/preventive",
        "/reports/conditions",
        "/admin/users",
        "/admin/users/new",
        f"/admin/users/{user_id}/edit",
        "/admin/audit",
        "/profile",
    )


@pytest.fixture()
def ids(equipment, fault, maintenance, schedule, admin_user):
    return {
        "equipment_id": equipment.id,
        "fault_id": fault.id,
        "record_id": maintenance.id,
        "schedule_id": schedule.id,
        "user_id": admin_user.id,
    }


def test_every_page_renders_for_an_administrator(client, admin_user, ids):
    login_as(client, "admin")
    for path in _pages_for(**ids):
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"
        assert b"Traceback" not in response.data


def test_unfiltered_list_pages_do_not_report_bogus_filter_warnings(client, admin_user, ids):
    """A plain GET supplies no filter values, so every dropdown is blank.

    That has to be a *valid* state: only genuinely malformed values (for
    example a non-numeric department id) may produce a warning.
    """
    login_as(client, "admin")
    for path in (
        "/equipment/",
        "/faults/",
        "/maintenance/",
        "/maintenance/schedules",
        "/admin/users",
        "/admin/audit",
        "/reports/",
        "/reports/equipment",
        "/reports/faults",
        "/reports/maintenance",
        "/reports/preventive",
        "/reports/conditions",
    ):
        body = client.get(path).get_data(as_text=True)
        assert response_ok(body), f"{path} did not render"
        assert "invalid and have been ignored" not in body, f"{path} flashed a bogus warning"

    # A real bad value must still be reported rather than silently swallowed.
    bad = client.get("/equipment/?department_id=not-a-number").get_data(as_text=True)
    assert "invalid and have been ignored" in bad


def response_ok(body: str) -> bool:
    return "Traceback" not in body


def test_viewer_pages_render_and_reject_management_controls(client, viewer_user, ids):
    login_as(client, "viewer")
    for path in (
        "/",
        "/equipment/",
        f"/equipment/{ids['equipment_id']}",
        "/faults/",
        f"/faults/{ids['fault_id']}",
        "/maintenance/",
        "/maintenance/schedules",
        "/departments/",
        "/reports/",
        "/reports/equipment",
        "/profile",
    ):
        assert client.get(path).status_code == 200, path

    # The viewer dashboard is used, not the administrator one.
    dashboard = client.get("/")
    assert b"Inventory overview" in dashboard.data
    assert b"Administrator dashboard" not in dashboard.data
    # Read-only hint is shown, and no create buttons leak into the page.
    assert b"read-only access" in dashboard.data


def test_ict_officer_dashboard_and_pages_render(client, officer_user, ids):
    login_as(client, "officer")
    assert b"ICT Officer dashboard" in client.get("/").data
    for path in ("/equipment/", "/faults/", "/maintenance/", "/maintenance/schedules",
                 "/reports/", "/equipment/new", "/faults/new"):
        assert client.get(path).status_code == 200, path


def test_detail_pages_show_the_required_information(client, admin_user, equipment, fault):
    login_as(client, "admin")

    fault_page = client.get(f"/faults/{fault.id}").get_data(as_text=True)
    for value in (
        fault.reference_number,
        equipment.asset_tag,
        equipment.equipment_name,
        fault.fault_title,
        fault.fault_category,
        fault.priority,
        fault.status,
    ):
        # Templates escape text, so compare against the escaped form.
        assert escape(value) in fault_page, f"fault detail page is missing {value!r}"

    for expected in (
        equipment.asset_tag,
        "Fault description",
        "Resolution notes",
        "Previous status changes",
        "Investigation and troubleshooting notes",
        "Related maintenance records",
        "Relevant audit entries",
    ):
        assert expected in fault_page, f"fault detail page is missing {expected!r}"
    # Workflow controls offered for a newly reported fault: the legal next
    # step plus the acknowledge / assign / prioritise / note / repair controls.
    for control in ("Move to Acknowledged", "Assign fault", "Change priority",
                    "Add troubleshooting note", "Record resolution notes",
                    "Record a repair"):
        assert control in fault_page, f"fault detail page is missing the {control!r} control"

    equipment_page = client.get(f"/equipment/{equipment.id}").get_data(as_text=True)
    for expected in (
        equipment.asset_tag,
        equipment.equipment_name,
        equipment.equipment_type,
        equipment.serial_number,
        "Status &amp; condition history",
        "Fault reports",
        "Maintenance history",
        "Preventive schedules",
    ):
        assert expected in equipment_page, f"equipment detail page is missing {expected!r}"


def test_fault_workflow_controls_appear_as_the_fault_progresses(
    client, admin_user, fault, maintenance
):
    """Acknowledge / resolve / close controls appear exactly when they are legal."""
    login_as(client, "admin")

    reported = client.get(f"/faults/{fault.id}").get_data(as_text=True)
    assert "Move to Acknowledged" in reported
    assert "Resolve the fault" not in reported

    client.post(
        f"/faults/{fault.id}/status", data={"status": "Acknowledged"},
        follow_redirects=True,
    )
    client.post(
        f"/faults/{fault.id}/status", data={"status": "Under Repair"},
        follow_redirects=True,
    )

    repairing = client.get(f"/faults/{fault.id}").get_data(as_text=True)
    assert "Resolve the fault" in repairing

    client.post(
        f"/faults/{fault.id}/status",
        data={"status": "Resolved", "resolution_notes": "Repaired and tested."},
        follow_redirects=True,
    )

    resolved = client.get(f"/faults/{fault.id}").get_data(as_text=True)
    assert "Close the fault" in resolved
    assert "Repaired and tested." in resolved

    client.post(
        f"/faults/{fault.id}/status", data={"status": "Closed"},
        follow_redirects=True,
    )
    closed = client.get(f"/faults/{fault.id}").get_data(as_text=True)
    assert "no further status changes are possible" in closed


def test_missing_record_renders_the_404_page(client, admin_user):
    login_as(client, "admin")
    response = client.get("/equipment/999999")
    assert response.status_code == 404
    assert b"404" in response.data
    assert b"Traceback" not in response.data


def test_forbidden_page_renders_the_403_page(client, officer_user):
    login_as(client, "officer")
    response = client.get("/admin/users")
    assert response.status_code == 403
    assert b"403" in response.data
    assert b"Access denied" in response.data


def test_unknown_url_renders_the_404_page(client, admin_user):
    login_as(client, "admin")
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert b"404" in response.data


def test_invalid_int_converter_returns_404(client, admin_user):
    login_as(client, "admin")
    assert client.get("/equipment/not-a-number").status_code == 404


def test_templates_escape_user_submitted_content(client, admin_user, department):
    """Jinja2 autoescaping must neutralise injected markup."""
    from services.equipment_service import EquipmentService

    EquipmentService.create(
        {
            "asset_tag": "ICT-950",
            "equipment_name": "<script>alert('xss')</script>",
            "equipment_type": "Desktop Computer",
            "department_id": department.id,
            "description": "<img src=x onerror=alert(1)>",
            "condition": "Good",
            "operational_status": "In Use",
        },
        actor=admin_user,
    )
    from extensions import db

    db.session.commit()

    login_as(client, "admin")
    page = client.get("/equipment/").get_data(as_text=True)
    assert "<script>alert('xss')</script>" not in page
    assert "&lt;script&gt;" in page
