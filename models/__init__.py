"""Domain models for CMIMS.

Importing this package registers every table with SQLAlchemy, which is what
``db.create_all()`` relies on.  Keep the imports here rather than in each
module to avoid circular-import problems.
"""

from models.audit import AuditLog
from models.department import Department
from models.equipment import Equipment, EquipmentCategory, EquipmentStatusHistory
from models.fault import FaultNote, FaultReport, FaultStatusHistory
from models.maintenance import MaintenanceRecord, MaintenanceSchedule
from models.roles import (
    Administrator,
    ICTOfficer,
    Role,
    Viewer,
    get_role,
)
from models.user import User

__all__ = [
    "Administrator",
    "AuditLog",
    "Department",
    "Equipment",
    "EquipmentCategory",
    "EquipmentStatusHistory",
    "FaultNote",
    "FaultReport",
    "FaultStatusHistory",
    "ICTOfficer",
    "MaintenanceRecord",
    "MaintenanceSchedule",
    "Role",
    "User",
    "Viewer",
    "get_role",
]
