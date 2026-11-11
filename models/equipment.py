"""Equipment inventory models.

``Equipment`` is the central asset record of CMIMS.  It carries encapsulated
behaviour (warranty checks, status updates, retirement) rather than being a
plain data bag, and every meaningful change is mirrored into
``EquipmentStatusHistory`` so the asset's history can be replayed in order.
"""

from datetime import date, datetime, timezone

from extensions import db
from models.constants import (
    CONDITION_GOOD,
    OPERATIONAL_STATUSES,
    CONDITIONS,
    STATUS_FAULTY,
    STATUS_RETIRED,
    STATUS_UNDER_MAINTENANCE,
)


def _utcnow():
    return datetime.now(timezone.utc)


class EquipmentCategory(db.Model):
    """Master-data catalogue of equipment types.

    Administrators can add or rename categories (e.g. "Tablet"); the seeding
    script pre-loads the twelve standard IT asset types.  Equipment rows store
    the category name in ``equipment_type`` so a typo'd free-text value can
    never be submitted - forms validate against this table.
    """

    __tablename__ = "equipment_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    def rename(self, name: str) -> None:
        self.name = name.strip()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EquipmentCategory {self.name}>"


class Equipment(db.Model):
    """A registered IT asset (desktop, laptop, printer, switch, ...)."""

    __tablename__ = "equipment"

    id = db.Column(db.Integer, primary_key=True)
    asset_tag = db.Column(db.String(64), nullable=False, unique=True, index=True)
    equipment_name = db.Column(db.String(150), nullable=False)
    equipment_type = db.Column(db.String(64), nullable=False, index=True)
    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100), index=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True
    )
    location = db.Column(db.String(120))
    purchase_date = db.Column(db.Date)
    warranty_expiry_date = db.Column(db.Date)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    condition = db.Column(db.String(20), nullable=False, default=CONDITION_GOOD)
    operational_status = db.Column(db.String(30), nullable=False, default="In Use")
    description = db.Column(db.Text)
    registered_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Composite index to speed up dashboard aggregates.
    __table_args__ = (
        db.Index("ix_equipment_status_condition", "operational_status", "condition"),
    )

    # --- Relationships -----------------------------------------------------
    department = db.relationship(
        "Department", back_populates="equipment", lazy="joined"
    )
    assigned_user = db.relationship(
        "User",
        foreign_keys=[assigned_user_id],
        back_populates="assigned_equipment",
        lazy="select",
    )
    registrar = db.relationship(
        "User",
        foreign_keys=[registered_by],
        back_populates="registered_equipment",
        lazy="select",
    )
    fault_reports = db.relationship(
        "FaultReport",
        back_populates="equipment",
        lazy="select",
        order_by="FaultReport.created_at.desc()",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    maintenance_records = db.relationship(
        "MaintenanceRecord",
        back_populates="equipment",
        lazy="select",
        order_by="MaintenanceRecord.maintenance_date.desc()",
    )
    maintenance_schedules = db.relationship(
        "MaintenanceSchedule",
        back_populates="equipment",
        lazy="select",
        order_by="MaintenanceSchedule.scheduled_date.desc()",
    )
    status_history = db.relationship(
        "EquipmentStatusHistory",
        back_populates="equipment",
        lazy="select",
        order_by="EquipmentStatusHistory.changed_at.desc()",
    )

    # --- Encapsulated behaviour -------------------------------------------
    @property
    def display_name(self) -> str:
        """Human friendly label used across the UI."""
        return self.equipment_name or self.asset_tag

    @property
    def is_retired(self) -> bool:
        return self.operational_status == STATUS_RETIRED

    @property
    def is_faulty(self) -> bool:
        return self.operational_status == STATUS_FAULTY

    @property
    def is_under_maintenance(self) -> bool:
        return self.operational_status == STATUS_UNDER_MAINTENANCE

    @property
    def warranty_status(self) -> str:
        """``Expired`` / ``Expiring`` / ``Active`` / ``Not recorded``."""
        if not self.warranty_expiry_date:
            return "Not recorded"
        today = date.today()
        if self.warranty_expiry_date < today:
            return "Expired"
        if (self.warranty_expiry_date - today).days <= 30:
            return "Expiring Soon"
        return "Active"

    @property
    def is_under_warranty(self) -> bool:
        return self.warranty_status in {"Active", "Expiring Soon"}

    @property
    def has_open_faults(self) -> bool:
        from models.constants import OPEN_FAULT_STATUSES

        return any(f.status in OPEN_FAULT_STATUSES for f in self.fault_reports)

    @property
    def open_fault_count(self) -> int:
        from models.constants import OPEN_FAULT_STATUSES

        return sum(1 for f in self.fault_reports if f.status in OPEN_FAULT_STATUSES)

    @property
    def maintenance_count(self) -> int:
        return len(self.maintenance_records)

    @property
    def last_maintenance_date(self):
        if not self.maintenance_records:
            return None
        return self.maintenance_records[0].maintenance_date

    def update_condition(self, new_condition: str) -> bool:
        """Set the physical condition; ``False`` when nothing changed."""
        if new_condition not in CONDITIONS:
            raise ValueError(f"Invalid condition: {new_condition!r}")
        if new_condition == self.condition:
            return False
        self.condition = new_condition
        return True

    def update_status(self, new_status: str) -> bool:
        """Set the operational status; ``False`` when nothing changed."""
        if new_status not in OPERATIONAL_STATUSES:
            raise ValueError(f"Invalid operational status: {new_status!r}")
        if new_status == self.operational_status:
            return False
        self.operational_status = new_status
        return True

    def retire(self, changed_by, notes: str = "Equipment retired from service.") -> "EquipmentStatusHistory":
        """Retire the asset (never a hard delete) and record the change."""
        return self._change_status(
            new_condition=None,
            new_status=STATUS_RETIRED,
            changed_by=changed_by,
            notes=notes,
        )

    def _change_status(self, new_condition, new_status, changed_by, notes=""):
        """Create the history row for a condition/status transition."""
        history = EquipmentStatusHistory(
            equipment=self,
            previous_condition=self.condition,
            new_condition=new_condition or self.condition,
            previous_status=self.operational_status,
            new_status=new_status or self.operational_status,
            changed_by=changed_by.id if changed_by is not None else None,
            change_notes=notes,
        )
        if new_condition:
            self.condition = new_condition
        if new_status:
            self.operational_status = new_status
        return history

    def change_condition(self, new_condition, changed_by, notes=""):
        """Update condition *and* persist an auditable history entry."""
        return self._change_status(
            new_condition=new_condition,
            new_status=None,
            changed_by=changed_by,
            notes=notes,
        )

    def change_status(self, new_status, changed_by, notes=""):
        """Update operational status *and* persist a history entry."""
        return self._change_status(
            new_condition=None,
            new_status=new_status,
            changed_by=changed_by,
            notes=notes,
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Equipment {self.asset_tag} ({self.operational_status})>"


class EquipmentStatusHistory(db.Model):
    """Immutable trail of condition / operational-status changes."""

    __tablename__ = "equipment_status_history"

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(
        db.Integer,
        db.ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_condition = db.Column(db.String(20))
    new_condition = db.Column(db.String(20))
    previous_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30))
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    change_notes = db.Column(db.String(255))
    changed_at = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)

    equipment = db.relationship("Equipment", back_populates="status_history")
    changer = db.relationship("User", foreign_keys=[changed_by], lazy="select")

    @property
    def change_summary(self) -> str:
        bits = []
        if self.previous_status and self.previous_status != self.new_status:
            bits.append(f"{self.previous_status} → {self.new_status}")
        if self.previous_condition and self.previous_condition != self.new_condition:
            bits.append(f"condition {self.previous_condition} → {self.new_condition}")
        return ", ".join(bits) or "No effective change"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EquipmentStatusHistory #{self.id} eq={self.equipment_id}>"
