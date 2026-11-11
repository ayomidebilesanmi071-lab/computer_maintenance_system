"""CMIMS - Computer Maintenance and Inventory Management System.

This module only *wires the application together*: it creates the Flask app,
loads configuration, initialises the extensions, registers the blueprints and
adds the shared template helpers / error handlers.  All domain logic lives in
``services/``, the data model in ``models/``, the HTTP endpoints in ``routes/``
and the markup in ``templates/``.

Run it with::

    python app.py                 # development server (debug off by default)
    flask --app app init-db       # create the database + tables
    flask --app app seed-db       # load idempotent sample data
"""

import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import current_user, logout_user
from flask_wtf.csrf import CSRFError
from markupsafe import Markup, escape

# Load environment variables from a local .env file if present.
load_dotenv()

from config import Config  # noqa: E402
from extensions import csrf, db, login_manager  # noqa: E402
from models import User  # noqa: E402,F401  (importing models registers every table)
from models.constants import (  # noqa: E402
    BADGE_CLASSES,
    CONDITIONS,
    EQUIPMENT_TYPES,
    FAULT_CATEGORIES,
    FAULT_PRIORITIES,
    FAULT_STATUSES,
    MAINTENANCE_OUTCOMES,
    MAINTENANCE_TYPES,
    OPERATIONAL_STATUSES,
    ROLE_LABELS,
    SCHEDULE_STATUSES,
)
from models.roles import (  # noqa: E402
    PERM_AUDIT_VIEW,
    PERM_CATEGORY_MANAGE,
    PERM_DEPARTMENT_MANAGE,
    PERM_EQUIPMENT_CREATE,
    PERM_EQUIPMENT_EDIT,
    PERM_EQUIPMENT_RETIRE,
    PERM_EQUIPMENT_STATUS,
    PERM_EQUIPMENT_VIEW,
    PERM_FAULT_CREATE,
    PERM_FAULT_MANAGE,
    PERM_FAULT_VIEW,
    PERM_MAINTENANCE_CREATE,
    PERM_MAINTENANCE_EDIT,
    PERM_MAINTENANCE_VIEW,
    PERM_REPORT_EXPORT,
    PERM_REPORT_VIEW,
    PERM_SCHEDULE_MANAGE,
    PERM_SCHEDULE_VIEW,
    PERM_USER_MANAGE,
)

#: Permission strings exposed to Jinja so templates can hide controls the
#: current user may not use (a convenience - the server re-checks everything).
PERMS = {
    "equipment_view": PERM_EQUIPMENT_VIEW,
    "equipment_create": PERM_EQUIPMENT_CREATE,
    "equipment_edit": PERM_EQUIPMENT_EDIT,
    "equipment_status": PERM_EQUIPMENT_STATUS,
    "equipment_retire": PERM_EQUIPMENT_RETIRE,
    "fault_view": PERM_FAULT_VIEW,
    "fault_create": PERM_FAULT_CREATE,
    "fault_manage": PERM_FAULT_MANAGE,
    "maintenance_view": PERM_MAINTENANCE_VIEW,
    "maintenance_create": PERM_MAINTENANCE_CREATE,
    "maintenance_edit": PERM_MAINTENANCE_EDIT,
    "schedule_view": PERM_SCHEDULE_VIEW,
    "schedule_manage": PERM_SCHEDULE_MANAGE,
    "report_view": PERM_REPORT_VIEW,
    "report_export": PERM_REPORT_EXPORT,
    "department_manage": PERM_DEPARTMENT_MANAGE,
    "category_manage": PERM_CATEGORY_MANAGE,
    "user_manage": PERM_USER_MANAGE,
    "audit_view": PERM_AUDIT_VIEW,
}


def create_app(config_class=Config, database_uri=None, upload_folder=None):
    """Application factory.

    ``database_uri`` and ``upload_folder`` override the configuration *before*
    the extensions are initialised (the test-suite uses this to point at a
    throwaway SQLite file), because Flask-SQLAlchemy builds its engine during
    ``init_app``.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # --- Database ---------------------------------------------------------
    if database_uri:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    elif not app.config.get("SQLALCHEMY_DATABASE_URI"):
        db_path = Path(app.instance_path) / "computer_maintenance.db"
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path.as_posix()

    # --- Uploads (optional attachments) -----------------------------------
    if upload_folder:
        app.config["UPLOAD_FOLDER"] = upload_folder
    upload_path = Path(app.config["UPLOAD_FOLDER"])
    upload_path.mkdir(parents=True, exist_ok=True)

    # --- Extensions -------------------------------------------------------
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from routes import register_blueprints

    register_blueprints(app)

    # --- Flask-Login ------------------------------------------------------
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    _register_template_helpers(app)
    _register_security_hooks(app)
    _register_error_handlers(app)
    _register_cli(app)
    return app


def _register_template_helpers(app):
    """Custom Jinja filters + globally available constants."""

    @app.template_filter("badge")
    def badge(value):
        """Map a status/condition/priority onto its CSS badge class."""
        return BADGE_CLASSES.get(value, "badge-secondary")

    @app.template_filter("nl2br")
    def nl2br(value):
        """Render multi-line text safely (escape first, then add <br>)."""
        if value is None:
            return ""
        return Markup(escape(value).replace("\n", "<br>"))

    @app.template_filter("date_display")
    def date_display(value, fallback="—"):
        if not value:
            return fallback
        if isinstance(value, datetime):
            return value.strftime("%d %b %Y, %H:%M")
        if isinstance(value, date):
            return value.strftime("%d %b %Y")
        return str(value)

    @app.template_filter("money")
    def money(value):
        if value is None or value == "":
            return "—"
        return f"₦{float(value):,.2f}"

    @app.template_filter("yesno")
    def yesno(value):
        return "Yes" if value else "No"

    app.jinja_env.globals.update(
        CONDITIONS=CONDITIONS,
        EQUIPMENT_TYPES=EQUIPMENT_TYPES,
        FAULT_CATEGORIES=FAULT_CATEGORIES,
        FAULT_PRIORITIES=FAULT_PRIORITIES,
        FAULT_STATUSES=FAULT_STATUSES,
        MAINTENANCE_OUTCOMES=MAINTENANCE_OUTCOMES,
        MAINTENANCE_TYPES=MAINTENANCE_TYPES,
        OPERATIONAL_STATUSES=OPERATIONAL_STATUSES,
        ROLE_LABELS=ROLE_LABELS,
        SCHEDULE_STATUSES=SCHEDULE_STATUSES,
        PERMS=PERMS,
        current_year=date.today().year,
    )


def _register_security_hooks(app):
    """Request-level guards that apply to every blueprint."""

    @app.before_request
    def enforce_active_account():
        """Sign out an account that was deactivated while logged in."""
        if current_user.is_authenticated and not current_user.is_active:
            logout_user()
            flash(
                "Your account has been deactivated. Please contact an administrator.",
                "error",
            )
            return redirect(url_for("auth.login"))
        return None


def _register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(_error):
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(CSRFError)
    def csrf_error(_error):
        """Expired/missing CSRF token - explain, never leak internals."""
        flash("Your session expired or the form was not valid. Please try again.", "error")
        return redirect(request.referrer or url_for("auth.login"))

    @app.errorhandler(413)
    def too_large(_error):
        flash("That upload is larger than the 2 MB limit.", "error")
        return redirect(request.referrer or url_for("dashboard.index"))


def _register_cli(app):
    """``flask --app app <command>`` helpers."""

    @app.cli.command("init-db")
    def init_db_command():
        """Create the database file and every table."""
        db.create_all()
        print("Database initialised:", app.config["SQLALCHEMY_DATABASE_URI"])

    @app.cli.command("seed-db")
    def seed_db_command():
        """Load the documented sample data (safe to run repeatedly)."""
        from scripts.seed_db import seed

        summary = seed()
        for line in summary:
            print(line)

    @app.shell_context_processor
    def shell_context():  # pragma: no cover - developer convenience
        return {"db": db, "User": User}


def _dev_port(default: int = 5000) -> int:
    """Port for the development server.

    Falls back to ``default`` when ``PORT`` is unset, blank, non-numeric or
    ``0`` (some hosts export ``PORT=0`` to mean "assign me any free port",
    which would otherwise make the documented URL misleading).
    """
    try:
        return int(os.environ.get("PORT") or 0) or default
    except (TypeError, ValueError):
        return default


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    # Debug mode is opt-in through FLASK_DEBUG / config, so a plain
    # ``python app.py`` never exposes the Werkzeug debugger.
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=_dev_port(),
        debug=bool(app.config.get("DEBUG")),
    )
