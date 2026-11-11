"""Route (blueprint) registration.

``app.create_app`` calls :func:`register_blueprints` once; every module keeps
its own ``Blueprint`` so features stay in separate files instead of growing a
single monolithic ``app.py``.
"""


def register_blueprints(app) -> None:
    """Attach every blueprint to ``app``."""
    from routes.admin import admin_bp
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.departments import departments_bp
    from routes.equipment import equipment_bp
    from routes.faults import faults_bp
    from routes.maintenance import maintenance_bp
    from routes.reports import reports_bp

    for blueprint in (
        auth_bp,
        dashboard_bp,
        equipment_bp,
        faults_bp,
        maintenance_bp,
        departments_bp,
        reports_bp,
        admin_bp,
    ):
        app.register_blueprint(blueprint)


__all__ = ["register_blueprints"]
