"""Flask-WTF forms for CMIMS.

Every state-changing form is CSRF protected by default; the read-only filter
forms opt out through :class:`forms.base.FilterFormMixin` because they only
issue GET requests.
"""

from forms.audit_forms import AuditFilterForm
from forms.auth_forms import ChangePasswordForm, LoginForm, ProfileForm
from forms.department_forms import (
    DepartmentFilterForm,
    DepartmentForm,
    EquipmentCategoryForm,
)
from forms.equipment_forms import (
    EquipmentFilterForm,
    EquipmentForm,
    EquipmentStatusForm,
    RetireEquipmentForm,
)
from forms.fault_forms import (
    AssignFaultForm,
    FaultFilterForm,
    FaultForm,
    FaultNoteForm,
    FaultPriorityForm,
    FaultResolutionForm,
    FaultStatusForm,
)
from forms.maintenance_forms import (
    CompleteScheduleForm,
    MaintenanceFilterForm,
    MaintenanceForm,
    ScheduleFilterForm,
    ScheduleForm,
    ScheduleStatusForm,
)
from forms.report_forms import ReportFilterForm
from forms.user_forms import UserFilterForm, UserForm

__all__ = [
    "AssignFaultForm",
    "AuditFilterForm",
    "ChangePasswordForm",
    "CompleteScheduleForm",
    "DepartmentFilterForm",
    "DepartmentForm",
    "EquipmentCategoryForm",
    "EquipmentFilterForm",
    "EquipmentForm",
    "EquipmentStatusForm",
    "FaultFilterForm",
    "FaultForm",
    "FaultNoteForm",
    "FaultPriorityForm",
    "FaultResolutionForm",
    "FaultStatusForm",
    "LoginForm",
    "MaintenanceFilterForm",
    "MaintenanceForm",
    "ProfileForm",
    "ReportFilterForm",
    "RetireEquipmentForm",
    "ScheduleFilterForm",
    "ScheduleForm",
    "ScheduleStatusForm",
    "UserFilterForm",
    "UserForm",
]
