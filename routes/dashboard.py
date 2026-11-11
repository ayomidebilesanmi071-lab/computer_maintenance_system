"""Dashboard routes.

One endpoint serves all three roles: the figures are assembled once by
:class:`~services.dashboard_service.DashboardService` and the *template* is
chosen from the user's role policy object (``user.role_object``), so
administrators, ICT officers and viewers each land on a page that matches what
they are allowed to do.
"""

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from models.constants import ROLE_ADMIN, ROLE_OFFICER
from services.dashboard_service import DashboardService
from services.maintenance_service import ScheduleService

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    """Landing page - dispatches to the template for the signed-in role."""
    # Keep Due/Overdue flags truthful without needing a background job.
    if ScheduleService.refresh_statuses():
        from extensions import db

        db.session.commit()

    context = {
        "stats": DashboardService.statistics(),
        "equipment_by_status": DashboardService.equipment_by_status(),
        "equipment_by_condition": DashboardService.equipment_by_condition(),
        "equipment_by_type": DashboardService.equipment_by_type(),
        "equipment_by_department": DashboardService.equipment_by_department(),
        "faults_by_status": DashboardService.faults_by_status(),
        "faults_by_priority": DashboardService.faults_by_priority(),
        "faults_by_category": DashboardService.faults_by_category(),
        "maintenance_by_type": DashboardService.maintenance_by_type(),
        "trend": DashboardService.monthly_trend(6),
        "recent_activity": DashboardService.recent_activity(8),
        "upcoming_schedules": DashboardService.upcoming_schedules(5),
        "open_faults": DashboardService.open_fault_queue(6),
        "warranty_watchlist": DashboardService.warranty_watchlist(5),
        "role_counts": DashboardService.role_counts(),
        "category_count": DashboardService.category_count(),
        "my_role": current_user.role,
        "is_admin": current_user.role == ROLE_ADMIN,
        "is_officer": current_user.role == ROLE_OFFICER,
    }
    return render_template(current_user.role_object.dashboard_template(), **context)


@dashboard_bp.route("/home")
@login_required
def home():
    """Alias kept for bookmarked links."""
    return redirect(url_for("dashboard.index"))
