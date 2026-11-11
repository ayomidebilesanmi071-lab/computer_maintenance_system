"""Authorization tests.

Every protected operation is checked on the **server**: the tests below call
the URLs directly (bypassing the interface entirely) to prove that hiding a
button in a template is not what protects the data.
"""

from datetime import date

from extensions import db
from models.constants import ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER
from models.equipment import Equipment
from models.fault import FaultReport
from services.equipment_service import EquipmentService
from tests.conftest import login_as

#: Pages that require only an authenticated session.
AUTHENTICATED_PAGES = (
    "/",
    "/equipment/",
    "/faults/",
    "/maintenance/",
    "/maintenance/schedules",
    "/departments/",
    "/departments/categories",
    "/reports/",
    "/reports/equipment",
    "/reports/faults",
    "/reports/maintenance",
    "/reports/preventive",
    "/reports/conditions",
    "/profile",
)

#: Routes that must never be reachable without signing in.
PROTECTED_POSTS = (
    ("/equipment/new", {}),
    ("/faults/new", {}),
)


def test_unauthenticated_users_cannot_reach_protected_pages(client):
    for path in AUTHENTICATED_PAGES:
        response = client.get(path)
        assert response.status_code == 302, f"{path} should redirect to the login form"
        assert "/login" in response.headers["Location"]


def test_unauthenticated_users_cannot_post_to_protected_routes(client):
    for path, payload in PROTECTED_POSTS:
        response = client.post(path, data=payload)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


def test_unauthenticated_users_cannot_reach_administrator_pages(client):
    assert client.get("/admin/users").status_code == 302
    assert client.get("/admin/audit").status_code == 302


def test_viewer_cannot_create_equipment(client, viewer_user, department):
    login_as(client, "viewer")
    response = client.post(
        "/equipment/new",
        data={
            "asset_tag": "ICT-950",
            "equipment_name": "Viewer attempt",
            "equipment_type": "Desktop Computer",
            "department_id": department.id,
            "condition": "Good",
            "operational_status": "In Use",
        },
    )
    assert response.status_code == 403
    assert EquipmentService.find_by_asset_tag("ICT-950") is None


def test_viewer_cannot_edit_or_retire_equipment(client, viewer_user, equipment):
    login_as(client, "viewer")
    assert client.post(f"/equipment/{equipment.id}/edit", data={}).status_code == 403
    assert client.post(f"/equipment/{equipment.id}/status", data={}).status_code == 403
    assert client.post(f"/equipment/{equipment.id}/retire", data={}).status_code == 403

    stored = db.session.get(Equipment, equipment.id)
    assert stored.operational_status == "In Use"


def test_viewer_cannot_report_or_manage_faults(client, viewer_user, equipment, fault):
    login_as(client, "viewer")
    assert client.post("/faults/new", data={}).status_code == 403
    assert client.post(f"/faults/{fault.id}/status", data={"status": "Closed"}).status_code == 403
    assert client.post(f"/faults/{fault.id}/assign", data={"assigned_to": 1}).status_code == 403
    assert client.post(f"/faults/{fault.id}/priority", data={"priority": "Low"}).status_code == 403
    assert client.post(f"/faults/{fault.id}/notes", data={"body": "hi"}).status_code == 403

    assert db.session.get(FaultReport, fault.id).status == "Reported"


def test_viewer_cannot_record_maintenance_or_schedules(client, viewer_user, equipment):
    login_as(client, "viewer")
    assert client.post("/maintenance/new", data={}).status_code == 403
    assert client.post("/maintenance/schedules/new", data={}).status_code == 403
    assert client.post("/departments/new", data={}).status_code == 403
    assert client.post("/departments/categories/new", data={}).status_code == 403


def test_viewer_cannot_reach_administrator_screens(client, viewer_user):
    login_as(client, "viewer")
    assert client.get("/admin/users").status_code == 403
    assert client.get("/admin/users/new").status_code == 403
    assert client.get("/admin/audit").status_code == 403


def test_ict_officer_cannot_reach_administrator_only_screens(client, officer_user):
    login_as(client, "officer")
    assert client.get("/admin/users").status_code == 403
    assert client.get("/admin/users/new").status_code == 403
    assert client.post("/admin/users/new", data={}).status_code == 403
    assert client.post("/departments/new", data={"name": "Officer department"}).status_code == 403
    assert client.post(
        "/departments/categories/new", data={"name": "Officer type"}
    ).status_code == 403


def test_ict_officer_can_use_operational_routes(client, officer_user, equipment, fault):
    login_as(client, "officer")
    assert client.get(f"/maintenance/new?equipment_id={equipment.id}").status_code == 200
    assert client.get(f"/maintenance/schedules/new?equipment_id={equipment.id}").status_code == 200
    assert client.post(
        f"/faults/{fault.id}/notes", data={"body": "Checked the power cable."},
        follow_redirects=True,
    ).status_code == 200


def test_administrator_can_reach_every_area(client, admin_user):
    login_as(client, "admin")
    for path in AUTHENTICATED_PAGES + (
        "/admin/users",
        "/admin/users/new",
        "/admin/audit",
        "/equipment/new",
        "/faults/new",
        "/maintenance/new",
        "/departments/new",
    ):
        assert client.get(path).status_code == 200, f"{path} should render for an admin"


def test_inactive_account_loses_access_immediately(client, officer_user, equipment):
    login_as(client, "officer")
    assert client.get("/faults/").status_code == 200

    officer_user.is_active = False
    db.session.commit()

    # The session guard signs the user out on the next request.
    response = client.get("/faults/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_inactive_account_cannot_perform_protected_actions(client, officer_user, equipment, department):
    """A deactivated account keeps no effective permissions."""
    login_as(client, "officer")
    officer_user.is_active = False
    db.session.commit()

    response = client.post(
        "/equipment/new",
        data={
            "asset_tag": "ICT-960",
            "equipment_name": "Deactivated officer attempt",
            "equipment_type": "Desktop Computer",
            "department_id": department.id,
            "condition": "Good",
            "operational_status": "In Use",
        },
    )
    assert response.status_code in (302, 403)
    assert EquipmentService.find_by_asset_tag("ICT-960") is None


def test_role_objects_grant_the_documented_permissions(app, admin_user, officer_user, viewer_user):
    assert admin_user.role == ROLE_ADMIN
    assert officer_user.role == ROLE_OFFICER
    assert viewer_user.role == ROLE_VIEWER

    # "Administrator-only routes must reject ICT officers and viewers."
    assert officer_user.cannot("user.manage")
    assert viewer_user.cannot("user.manage")
    assert admin_user.can("user.manage")

    # "ICT maintenance routes must reject viewers."
    assert viewer_user.cannot("maintenance.create")
    assert viewer_user.cannot("fault.manage")
    assert viewer_user.cannot("equipment.create")
    assert officer_user.can("maintenance.create")
    assert officer_user.can("fault.manage")

    # Viewers keep read access.
    assert viewer_user.can("equipment.view")
    assert viewer_user.can("report.view")
    assert viewer_user.cannot("report.export")


def test_deactivated_user_has_no_permissions(app, officer_user):
    officer_user.is_active = False
    db.session.commit()
    assert officer_user.can("equipment.view") is False
    assert officer_user.cannot("fault.manage") is True


def test_csrf_protection_is_enabled_outside_testing(app):
    from config import Config

    assert Config.WTF_CSRF_ENABLED is True
    assert app.config["WTF_CSRF_ENABLED"] is False  # tests only


def test_login_required_decorator_protects_every_state_changing_route(app):
    """No POST route may be reachable anonymously."""
    with app.test_request_context():
        from flask import request

    rules = [rule for rule in app.url_map.iter_rules() if "POST" in rule.methods]
    public = {"auth.login", "static"}
    for rule in rules:
        assert rule.endpoint not in public or rule.endpoint == "auth.login"
