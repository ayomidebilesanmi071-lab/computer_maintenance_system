"""Audit trail model.

Every important action (create / update / status change / retire / login) is
recorded here through :mod:`services.audit_service`, never by hand-writing log
rows inside route handlers.  Audit rows are append-only - the application
offers no route that edits or deletes them.
"""

from datetime import datetime, timezone

from extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class AuditLog(db.Model):
    """An immutable record of who did what, and when."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    entity_type = db.Column(db.String(50), nullable=False, index=True)
    entity_id = db.Column(db.Integer)
    description = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)

    user = db.relationship("User", back_populates="audit_logs", lazy="joined")

    # --- Read helpers -----------------------------------------------------
    @property
    def actor(self) -> str:
        return self.user.full_name if self.user else "System"

    @property
    def entity_label(self) -> str:
        return f"{self.entity_type} #{self.entity_id}" if self.entity_id else self.entity_type

    @classmethod
    def record(cls, user, action: str, entity_type: str, entity_id, description: str) -> "AuditLog":
        """Factory used by the audit service (keeps construction in one place)."""
        if len(description) > 500:  # defensive: never overflow the column
            description = description[:497] + "..."
        return cls(
            user_id=getattr(user, "id", None),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} {self.entity_type}>"
