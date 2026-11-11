"""Create the CMIMS database and every table.

Safe to run repeatedly: ``db.create_all`` only creates what is missing and
**never** drops or overwrites an existing database, so a deployment that
already holds real records cannot be wiped by re-running this script.

Usage::

    python scripts/init_db.py
    flask --app app init-db
"""

import sys
from pathlib import Path

# Allow ``python scripts/init_db.py`` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models import (  # noqa: E402
    AuditLog,
    Department,
    Equipment,
    EquipmentCategory,
    FaultReport,
    MaintenanceRecord,
    MaintenanceSchedule,
    User,
)


def initialise() -> None:
    """Create the instance folder, the database file and all tables."""
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database initialised.")
        print("  URI:", app.config["SQLALCHEMY_DATABASE_URI"])
        for label, model in (
            ("users", User),
            ("departments", Department),
            ("equipment types", EquipmentCategory),
            ("equipment", Equipment),
            ("fault reports", FaultReport),
            ("maintenance records", MaintenanceRecord),
            ("maintenance schedules", MaintenanceSchedule),
            ("audit entries", AuditLog),
        ):
            print(f"  {label:<20} {db.session.query(model).count()}")
        print("\nNext step: python scripts/seed_db.py")


if __name__ == "__main__":
    initialise()
