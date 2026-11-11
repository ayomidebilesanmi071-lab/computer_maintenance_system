"""Business-logic (service) layer of CMIMS.

Routes are kept thin: they parse the request, call a service, and render a
template.  Everything that must stay consistent - validation, state machines,
audit logging, reporting queries - lives in this package so it can be reused,
unit-tested and audited in one place.
"""

from services import audit_service
from services.dashboard_service import DashboardService
from services.equipment_service import EquipmentService
from services.errors import (
    DuplicateError,
    NotFoundError,
    ServiceError,
    TransitionError,
    ValidationError,
)
from services.fault_service import FaultService
from services.maintenance_service import MaintenanceService, ScheduleService
from services.report_service import ReportService
from services.upload_service import AttachmentService
from services.user_service import UserService

__all__ = [
    "AttachmentService",
    "DashboardService",
    "DuplicateError",
    "EquipmentService",
    "FaultService",
    "MaintenanceService",
    "NotFoundError",
    "ReportService",
    "ScheduleService",
    "ServiceError",
    "TransitionError",
    "UserService",
    "ValidationError",
    "audit_service",
]
