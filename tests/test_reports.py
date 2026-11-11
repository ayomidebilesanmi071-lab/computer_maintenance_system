"""Dashboard and reporting tests: figures from the database, filters, CSV export."""

from datetime import date, timedelta

from extensions import db
from models.equipment import Equipment
from services.equipment_service import EquipmentService
from services.report_service import ReportService
from tests.conftest import login_as


def _register(actor, department_id, tag, **overrides):
    payload = {
        "asset_tag": tag,
        "equipment_name": f"Asset {tag}",
        "equipment_type": "Desktop Computer",
        "department_id": department_id,
        "manufacturer": "HP",
        "model": "ProDesk",
        "serial_number": f"SN-{tag}",
        "location": "Store room",
        "purchase_date": date(2024, 6, 1),
        "warranty_expiry_date": date(2027, 6, 1),
        "condition": "Good",
        "operational_status": "In Use",
    }
    payload.update(overrides)
    return EquipmentService.create(payload, actor=actor)


# ------------------------------------------------------------------ dashboards
def test_dashboard_figures_are_calculated_from_database_records(
    client, admin_user, equipment, fault
):
    login_as(client, "admin")
    page = client.get("/")
    assert page.status_code == 200
    # One equipment record and one fault exist, so both must be reflected.
    assert b"1" in page.data
    assert b"Equipment by department" in page.data

    from services.dashboard_service import DashboardService

    stats = DashboardService.statistics()
    assert stats["total_equipment"] == db.session.query(Equipment).count() == 1
    assert stats["total_faults"] == 1
    assert stats["open_faults"] == 1
    assert stats["resolution_rate"] == 0.0
    assert sum(DashboardService.equipment_by_status().values()) == 1
    assert sum(DashboardService.equipment_by_condition().values()) == 1
    assert DashboardService.role_counts()["admin"] == 1


def test_dashboard_counts_react_to_new_records(client, admin_user, department, equipment):
    login_as(client, "admin")
    _register(admin_user, department.id, "ICT-601")
    _register(
        admin_user,
        department.id,
        "ICT-602",
        condition="Poor",
        operational_status="Faulty",
    )
    db.session.commit()

    from services.dashboard_service import DashboardService

    assert DashboardService.statistics()["total_equipment"] == 3
    assert DashboardService.statistics()["faulty_equipment"] == 1
    assert DashboardService.equipment_by_condition()["Poor"] == 1


def test_trend_series_covers_the_requested_months(app, admin_user, equipment, fault):
    from services.dashboard_service import DashboardService

    trend = DashboardService.monthly_trend(6)
    assert len(trend["labels"]) == 6
    assert len(trend["faults"]) == 6
    assert sum(trend["faults"]) == 1  # one fault was reported today


# ------------------------------------------------------------------ search/filter
def test_equipment_filters_return_the_correct_results(client, admin_user, department, equipment):
    login_as(client, "admin")
    _register(admin_user, department.id, "ICT-610", equipment_type="Laptop Computer")
    db.session.commit()

    assert b"ICT-001" in client.get("/equipment/?equipment_type=Desktop%20Computer").data
    assert b"ICT-610" not in client.get("/equipment/?equipment_type=Desktop%20Computer").data
    assert b"ICT-610" in client.get("/equipment/?equipment_type=Laptop%20Computer").data
    assert b"ICT-001" in client.get("/equipment/?search=ProDesk").data
    assert b"ICT-001" in client.get(f"/equipment/?department_id={department.id}").data
    assert b"ICT-001" in client.get("/equipment/?warranty=active").data
    assert b"ICT-001" not in client.get("/equipment/?warranty=missing").data


def test_invalid_filter_values_do_not_break_the_page(client, admin_user, equipment):
    login_as(client, "admin")
    response = client.get("/equipment/?date_from=not-a-date&department_id=abc&condition=Bogus")
    assert response.status_code == 200
    assert b"invalid" in response.data.lower() or b"ICT-001" in response.data


# ---------------------------------------------------------------- report pages
def test_report_pages_render_live_database_records(client, admin_user, equipment, fault, maintenance, schedule):
    login_as(client, "admin")

    inventory = client.get("/reports/equipment")
    assert inventory.status_code == 200
    assert b"ICT-001" in inventory.data

    faults = client.get("/reports/faults")
    assert faults.status_code == 200
    assert fault.reference_number.encode() in faults.data

    history = client.get("/reports/maintenance")
    assert history.status_code == 200
    assert b"Hardware Repair" in history.data

    preventive = client.get("/reports/preventive")
    assert preventive.status_code == 200
    assert b"Preventive Maintenance" in preventive.data

    conditions = client.get("/reports/conditions")
    assert conditions.status_code == 200
    assert b"Excellent" in conditions.data and b"Good" in conditions.data

    hub = client.get("/reports/")
    assert hub.status_code == 200
    assert b"Equipment Inventory Report" in hub.data


def test_condition_report_groups_equipment_by_condition(app, admin_user, department):
    _register(admin_user, department.id, "ICT-701", condition="Excellent")
    _register(admin_user, department.id, "ICT-702", condition="Poor")
    _register(admin_user, department.id, "ICT-703", condition="Damaged")
    db.session.commit()

    grouped = ReportService.equipment_condition_report()
    assert [item.asset_tag for item in grouped["Excellent"]] == ["ICT-701"]
    assert [item.asset_tag for item in grouped["Poor"]] == ["ICT-702"]
    assert [item.asset_tag for item in grouped["Damaged"]] == ["ICT-703"]
    assert grouped["Fair"] == []


def test_report_filters_narrow_the_result_set(client, admin_user, department, equipment):
    login_as(client, "admin")
    _register(admin_user, department.id, "ICT-801", equipment_type="Printer")
    db.session.commit()

    response = client.get("/reports/equipment?equipment_type=Printer")
    assert b"ICT-801" in response.data
    assert b"ICT-001" not in response.data


# --------------------------------------------------------------------- CSV
def test_equipment_csv_export_contains_the_expected_information(client, admin_user, equipment):
    login_as(client, "admin")
    response = client.get("/reports/equipment?export=csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    assert ".csv" in response.headers["Content-Disposition"]

    text = response.get_data(as_text=True)
    lines = text.strip().splitlines()
    assert lines[0].startswith("Asset Tag,Equipment Name,Equipment Type,Department")
    assert "ICT-001" in text
    assert "HP ProDesk Desktop Computer" in text
    assert "ICT Department" in text


def test_fault_csv_export_contains_the_expected_information(client, admin_user, fault):
    login_as(client, "admin")
    response = client.get("/reports/faults?export=csv")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert text.splitlines()[0].startswith("Fault Reference,Equipment,Fault Category")
    assert fault.reference_number in text
    assert "ICT-001" in text


def test_maintenance_and_schedule_csv_exports(client, admin_user, maintenance, schedule):
    login_as(client, "admin")

    maintenance_csv = client.get("/reports/maintenance?export=csv").get_data(as_text=True)
    assert maintenance_csv.splitlines()[0].startswith("Equipment,Maintenance Type,Date of Maintenance")
    assert "Hardware Repair" in maintenance_csv

    preventive_csv = client.get("/reports/preventive?export=csv").get_data(as_text=True)
    assert preventive_csv.splitlines()[0].startswith("Equipment,Maintenance Type,Scheduled Date")
    assert "Preventive Maintenance" in preventive_csv

    condition_csv = client.get("/reports/conditions?export=csv").get_data(as_text=True)
    assert condition_csv.splitlines()[0].startswith("Condition,Asset Tag")
    assert "Good,ICT-001" in condition_csv


def test_csv_export_respects_the_active_filters(client, admin_user, department, equipment):
    login_as(client, "admin")
    _register(admin_user, department.id, "ICT-901", equipment_type="Printer")
    db.session.commit()

    text = client.get("/reports/equipment?equipment_type=Printer&export=csv").get_data(as_text=True)
    assert "ICT-901" in text
    assert "ICT-001" not in text


def test_viewer_cannot_export_csv(client, viewer_user, equipment):
    login_as(client, "viewer")
    # The page itself is readable...
    assert client.get("/reports/equipment").status_code == 200
    # ...but the export requires the report.export permission.
    assert client.get("/reports/equipment?export=csv").status_code == 403


def test_reports_are_not_available_to_anonymous_users(client):
    assert client.get("/reports/equipment").status_code == 302
    assert client.get("/reports/equipment?export=csv").status_code == 302


def test_summary_totals_come_from_the_database(app, admin_user, department, maintenance):
    totals = ReportService.summary_totals()
    assert totals["total_equipment"] == 1
    assert totals["total_maintenance"] == 1
    assert totals["total_schedules"] == 0
    assert totals["maintenance_cost"] == float(maintenance.cost or 0)


def test_csv_writer_escapes_commas_and_quotes(app):
    text = ReportService.to_csv(["A", "B"], [["hello, world", 'say "hi"']])
    lines = text.strip().splitlines()
    assert lines[0] == "A,B"
    assert '"hello, world","say ""hi"""' in lines[1]
