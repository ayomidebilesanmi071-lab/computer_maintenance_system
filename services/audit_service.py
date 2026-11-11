"""Centralised audit logging.

Every important action in CMIMS funnels through :class:`AuditService`.  The
service only *adds* a row to the current transaction - the caller commits - so
a business change and its audit entry either both persist or both roll back.

The log is append-only: no route in this application lets a user edit or delete
audit rows, and descriptions are built from human labels only (never passwords,
tokens or session data).
"""

from sqlalchemy import select

from extensions import db
from models.audit import AuditLog

# Action vocabulary (mirrors models.constants but kept readable for logs).
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_STATUS_CHANGE = "status_change"
ACTION_ASSIGN = "assign"
ACTION_RETIRE = "retire"
ACTION_LOGIN = "login"
ACTION_LOGOUT = "logout"
ACTION_DEACTIVATE = "deactivate"
ACTION_ACTIVATE = "activate"


class AuditService:
    """Stateless service that writes the organisation's audit trail."""

    @staticmethod
    def log(user, action: str, entity_type: str, entity_id, description: str) -> AuditLog:
        """Append one audit entry to the *current* transaction.

        Does **not** commit - call it inside the same unit of work as the
        change it describes so both succeed or fail together.

        Parameters
        ----------
        user:
            The :class:`~models.user.User` responsible (or ``None`` for
            system/anonymous events such as a failed login).
        action:
            Short verb, e.g. ``create``, ``status_change``.
        entity_type:
            Table-ish label, e.g. ``equipment``, ``fault_report``.
        entity_id:
            Primary key of the affected row (may be ``None``).
        description:
            Human readable sentence, e.g. ``"Administrator retired equipment ICT-010."``
        """
        entry = AuditLog.record(user, action, entity_type, entity_id, description)
        db.session.add(entry)
        return entry

    @classmethod
    def log_login(cls, user) -> AuditLog:
        return cls.log(user, ACTION_LOGIN, "user", user.id, f"{user.role_label} {user.full_name} logged in.")

    @classmethod
    def log_logout(cls, user) -> AuditLog:
        return cls.log(user, ACTION_LOGOUT, "user", user.id, f"{user.full_name} logged out.")

    @staticmethod
    def history(entity_type: str = None, entity_id: int = None, limit: int = 100):
        """Audit rows, optionally scoped to one entity, newest first."""
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        return db.session.scalars(stmt.limit(limit)).all()

    @staticmethod
    def recent(limit: int = 25):
        """Latest ``limit`` entries for a dashboard/feed widget."""
        stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        return db.session.scalars(stmt).all()

    @staticmethod
    def search_statement(**filters):
        """Filtered audit query (action / entity type / user).

        Rows are only ever read - the application exposes no route that edits
        or deletes an audit entry.
        """
        stmt = select(AuditLog).join(AuditLog.user, isouter=True)
        if filters.get("action"):
            stmt = stmt.where(AuditLog.action == filters["action"])
        if filters.get("entity_type"):
            stmt = stmt.where(AuditLog.entity_type == filters["entity_type"])
        if filters.get("user_id"):
            stmt = stmt.where(AuditLog.user_id == int(filters["user_id"]))
        if filters.get("entity_id"):
            stmt = stmt.where(AuditLog.entity_id == int(filters["entity_id"]))
        search = (filters.get("search") or "").strip()
        if search:
            stmt = stmt.where(AuditLog.description.ilike(f"%{search}%"))
        if filters.get("date_from"):
            stmt = stmt.where(AuditLog.timestamp >= filters["date_from"])
        if filters.get("date_to"):
            from datetime import date, datetime, time

            end = filters["date_to"]
            if isinstance(end, date) and not isinstance(end, datetime):
                end = datetime.combine(end, time.max)
            stmt = stmt.where(AuditLog.timestamp <= end)
        return stmt.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())

    @classmethod
    def paginate(cls, page: int, per_page: int, **filters):
        return db.paginate(
            cls.search_statement(**filters), page=page, per_page=per_page,
            error_out=False,
        )
