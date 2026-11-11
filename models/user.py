"""User model - the single shared account table for every role.

Design notes
------------
* **One table, three roles.**  ``ICTOfficer`` and ``Administrator`` are *not*
  duplicated models; they are role policy objects from :mod:`models.roles`
  attached to this shared table.
* **Encapsulation** - passwords only ever pass through :meth:`User.set_password`
  and are stored as Werkzeug scrypt hashes; the plain password is never kept.
* **Relationships** - registered equipment, reported faults, assigned faults,
  maintenance records and audit entries all point back to a user.
"""

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models.constants import ROLES, ROLE_LABELS
from models.roles import ROLE_REGISTRY, Role, get_role


def _utcnow():
    """Timezone-aware UTC timestamp (keeps tests deterministic)."""
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    """A CMIMS account."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="viewer", index=True)
    # Deactivated accounts cannot log in and lose every permission.
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # --- Relationships ---------------------------------------------------
    registered_equipment = db.relationship(
        "Equipment",
        foreign_keys="Equipment.registered_by",
        back_populates="registrar",
        lazy="select",
    )
    assigned_equipment = db.relationship(
        "Equipment",
        foreign_keys="Equipment.assigned_user_id",
        back_populates="assigned_user",
        lazy="select",
    )
    reported_faults = db.relationship(
        "FaultReport",
        foreign_keys="FaultReport.reported_by",
        back_populates="reporter",
        lazy="select",
    )
    assigned_faults = db.relationship(
        "FaultReport",
        foreign_keys="FaultReport.assigned_to",
        back_populates="assignee",
        lazy="select",
    )
    maintenance_performed = db.relationship(
        "MaintenanceRecord",
        foreign_keys="MaintenanceRecord.technician_id",
        back_populates="technician",
        lazy="select",
    )
    maintenance_recorded = db.relationship(
        "MaintenanceRecord",
        foreign_keys="MaintenanceRecord.recorded_by",
        back_populates="recorder",
        lazy="select",
    )
    assigned_schedules = db.relationship(
        "MaintenanceSchedule",
        foreign_keys="MaintenanceSchedule.assigned_to",
        back_populates="assignee",
        lazy="select",
    )
    audit_logs = db.relationship(
        "AuditLog",
        back_populates="user",
        lazy="dynamic",
        order_by="AuditLog.timestamp.desc()",
    )

    # ------------------------------------------------------------- helpers
    def set_password(self, raw_password: str) -> None:
        """Hash and store a password (plain text is never persisted)."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Verify a candidate password against the stored hash."""
        return check_password_hash(self.password_hash, raw_password)

    # --- Role / permission API -------------------------------------------
    @property
    def role_object(self) -> Role:
        """Polymorphic access to this user's permission policy."""
        return get_role(self.role)

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_officer(self) -> bool:
        return self.role == "ict_officer"

    @property
    def is_viewer(self) -> bool:
        return self.role == "viewer"

    def can(self, permission: str) -> bool:
        """Does this user's role grant ``permission``?

        Flask-Login consults :attr:`is_active` on every request, and this
        method re-checks it so even a guarded helper call can never succeed
        for a deactivated account.
        """
        if not self.is_active:
            # A deactivated account keeps no effective permissions.
            return False
        return self.role_object.can(permission)

    def cannot(self, permission: str) -> bool:
        return not self.can(permission)

    def activate(self) -> None:
        """Re-enable a deactivated account."""
        self.is_active = True

    def deactivate(self) -> None:
        """Disable an account without deleting its historical records."""
        self.is_active = False

    def rename(self, full_name: str) -> None:
        """Simple encapsulated mutator used by the admin user form."""
        self.full_name = full_name.strip()

    # --- Convenience factories (used by seeding + admin screens) ---------
    @classmethod
    def create_admin(cls, full_name: str, email: str, password: str) -> "User":
        return cls._build(full_name, email, password, "admin")

    @classmethod
    def create_officer(cls, full_name: str, email: str, password: str) -> "User":
        return cls._build(full_name, email, password, "ict_officer")

    @classmethod
    def create_viewer(cls, full_name: str, email: str, password: str) -> "User":
        return cls._build(full_name, email, password, "viewer")

    @classmethod
    def _build(cls, full_name, email, password, role) -> "User":
        if role not in ROLES:  # pragma: no cover - guarded by forms/CLI
            raise ValueError(f"Invalid role: {role}")
        user = cls(full_name=full_name.strip(), email=email.strip().lower(), role=role)
        user.set_password(password)
        return user

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<User {self.email} ({self.role})>"


# Import-time sanity check: every role in the registry must be usable by User.
for _role_name in ROLES:  # pragma: no cover - protects against typos
    ROLE_REGISTRY[_role_name]
