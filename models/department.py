"""Department model - organisational units that own equipment."""

from extensions import db


class Department(db.Model):
    """A department / unit inside the organisation (e.g. Accounts)."""

    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255))
    location = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())

    # --- Relationships ---------------------------------------------------
    equipment = db.relationship(
        "Equipment",
        back_populates="department",
        lazy="select",
        order_by="Equipment.asset_tag",
    )

    # --- Instance methods --------------------------------------------------
    @property
    def equipment_count(self) -> int:
        """Number of equipment items registered to this department."""
        return len(self.equipment)

    @property
    def display_location(self) -> str:
        return self.location or "Not specified"

    def rename(self, name: str) -> None:
        self.name = name.strip()

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Department {self.name}>"
