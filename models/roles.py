"""Role-based authorization policy objects.

The ``User`` model stays a *single* shared table (no duplicated user logic).
Behaviour that differs between administrators, ICT officers and viewers lives
in these role objects instead, which is a classic **Strategy** pattern:

* ``Role``                - abstract base class (abstraction / encapsulation).
* ``Administrator``       - full administrative policy.
* ``ICTOfficer``          - day-to-day equipment and maintenance policy.
* ``Viewer``              - read-only policy.

Every ``User`` instance holds a :meth:`User.role_object`; calling
``user.can("equipment.create")`` dispatches to the concrete role class, so the
rest of the application never needs ``if role == ...`` chains (polymorphism).
"""

from abc import ABC, abstractmethod

from models.constants import ROLE_ADMIN, ROLE_OFFICER, ROLE_VIEWER

# --- Permission vocabulary ---------------------------------------------------
# Keeping permissions as small capability strings makes the policy readable
# and lets routes declare exactly what they need.
PERM_EQUIPMENT_VIEW = "equipment.view"
PERM_EQUIPMENT_CREATE = "equipment.create"
PERM_EQUIPMENT_EDIT = "equipment.edit"
PERM_EQUIPMENT_STATUS = "equipment.status"
PERM_EQUIPMENT_RETIRE = "equipment.retire"

PERM_FAULT_VIEW = "fault.view"
PERM_FAULT_CREATE = "fault.create"
PERM_FAULT_MANAGE = "fault.manage"  # assign / change status / resolve / notes

PERM_MAINTENANCE_VIEW = "maintenance.view"
PERM_MAINTENANCE_CREATE = "maintenance.create"
PERM_MAINTENANCE_EDIT = "maintenance.edit"

PERM_SCHEDULE_VIEW = "schedule.view"
PERM_SCHEDULE_MANAGE = "schedule.manage"

PERM_REPORT_VIEW = "report.view"
PERM_REPORT_EXPORT = "report.export"

PERM_DEPARTMENT_MANAGE = "department.manage"
PERM_CATEGORY_MANAGE = "category.manage"
PERM_USER_MANAGE = "user.manage"
PERM_AUDIT_VIEW = "audit.view"
PERM_SETTINGS_MANAGE = "settings.manage"

ALL_PERMISSIONS = frozenset(
    {
        PERM_EQUIPMENT_VIEW,
        PERM_EQUIPMENT_CREATE,
        PERM_EQUIPMENT_EDIT,
        PERM_EQUIPMENT_STATUS,
        PERM_EQUIPMENT_RETIRE,
        PERM_FAULT_VIEW,
        PERM_FAULT_CREATE,
        PERM_FAULT_MANAGE,
        PERM_MAINTENANCE_VIEW,
        PERM_MAINTENANCE_CREATE,
        PERM_MAINTENANCE_EDIT,
        PERM_SCHEDULE_VIEW,
        PERM_SCHEDULE_MANAGE,
        PERM_REPORT_VIEW,
        PERM_REPORT_EXPORT,
        PERM_DEPARTMENT_MANAGE,
        PERM_CATEGORY_MANAGE,
        PERM_USER_MANAGE,
        PERM_AUDIT_VIEW,
        PERM_SETTINGS_MANAGE,
    }
)


class Role(ABC):
    """Abstract base class describing a security role.

    Sub-classes only declare *which* permissions they grant and *which*
    dashboard they use - the ``can``/``cannot`` logic is inherited so the rules
    are never re-implemented inconsistently.
    """

    #: Machine name stored in ``users.role``.
    name: str = ""
    #: Human readable label shown in the UI.
    label: str = ""
    #: Frozen set of granted permission strings.
    permissions: frozenset = frozenset()

    def can(self, permission: str) -> bool:
        """Return ``True`` when this role grants ``permission``."""
        return permission in self.permissions

    def cannot(self, permission: str) -> bool:
        """Inverse of :meth:`can` - reads naturally in route guards."""
        return not self.can(permission)

    @property
    def permission_list(self) -> list:
        """Sorted permission list (used by the admin UI and tests)."""
        return sorted(self.permissions)

    @abstractmethod
    def dashboard_template(self) -> str:
        """Template rendered for this role's landing page."""

    @abstractmethod
    def home_endpoint(self) -> str:
        """Endpoint name this role is redirected to after login."""

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Role {self.name}>"


class Administrator(Role):
    """System-wide management access.

    Administrators manage users, departments, categories, audit logs and all
    records - but they still pass through the same authentication, CSRF and
    validation controls as everybody else (no security bypass).
    """

    name = ROLE_ADMIN
    label = "Administrator"
    permissions = ALL_PERMISSIONS

    def dashboard_template(self) -> str:
        return "dashboards/admin.html"

    def home_endpoint(self) -> str:
        return "dashboard.index"


class ICTOfficer(Role):
    """Operational access for the ICT maintenance team."""

    name = ROLE_OFFICER
    label = "ICT Officer"
    permissions = frozenset(
        {
            PERM_EQUIPMENT_VIEW,
            PERM_EQUIPMENT_CREATE,
            PERM_EQUIPMENT_EDIT,
            PERM_EQUIPMENT_STATUS,
            PERM_EQUIPMENT_RETIRE,
            PERM_FAULT_VIEW,
            PERM_FAULT_CREATE,
            PERM_FAULT_MANAGE,
            PERM_MAINTENANCE_VIEW,
            PERM_MAINTENANCE_CREATE,
            PERM_MAINTENANCE_EDIT,
            PERM_SCHEDULE_VIEW,
            PERM_SCHEDULE_MANAGE,
            PERM_REPORT_VIEW,
            PERM_REPORT_EXPORT,
            # Officers may view audit history relevant to their work.
            PERM_AUDIT_VIEW,
        }
    )

    def dashboard_template(self) -> str:
        return "dashboards/ict_officer.html"

    def home_endpoint(self) -> str:
        return "dashboard.index"


class Viewer(Role):
    """Read-only access to approved inventory information."""

    name = ROLE_VIEWER
    label = "Viewer"
    permissions = frozenset(
        {
            PERM_EQUIPMENT_VIEW,
            PERM_FAULT_VIEW,
            PERM_MAINTENANCE_VIEW,
            PERM_SCHEDULE_VIEW,
            PERM_REPORT_VIEW,
        }
    )

    def dashboard_template(self) -> str:
        return "dashboards/viewer.html"

    def home_endpoint(self) -> str:
        return "dashboard.index"


#: Registry consulted by :func:`get_role`.  Unknown names raise so a corrupt
#: database row can never silently grant access.
ROLE_REGISTRY = {
    ROLE_ADMIN: Administrator(),
    ROLE_OFFICER: ICTOfficer(),
    ROLE_VIEWER: Viewer(),
}


def get_role(role_name: str) -> Role:
    """Return the policy object for ``role_name``.

    Raises ``ValueError`` for unknown roles so that invalid data fails loudly
    instead of defaulting to a permissive policy.
    """
    try:
        return ROLE_REGISTRY[role_name]
    except KeyError as exc:
        raise ValueError(f"Unknown role: {role_name!r}") from exc
