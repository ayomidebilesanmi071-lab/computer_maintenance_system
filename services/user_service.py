"""Account management business logic (administrator screens).

Keeping this out of the route handler means the same rules apply whether an
account is created from the web form or from the seeding script: unique email,
valid role, strong-enough password, and an audit entry written in the same
transaction.  Deactivated users keep their historical records - accounts are
never deleted.
"""

from sqlalchemy import func, or_, select

from extensions import db
from models.constants import ROLES, ROLE_ADMIN, ROLE_LABELS
from models.user import User
from services import audit_service
from services.errors import DuplicateError, NotFoundError, ValidationError

MIN_PASSWORD_LENGTH = 8


def check_password_strength(password: str) -> None:
    """Reject weak passwords with a message the user can act on."""
    password = password or ""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.",
            {"password": f"Use at least {MIN_PASSWORD_LENGTH} characters."},
        )
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValidationError(
            "Password must contain both letters and numbers.",
            {"password": "Mix letters and numbers."},
        )


class UserService:
    """Domain service for CMIMS accounts."""

    # ------------------------------------------------------------ retrieval
    @staticmethod
    def get(user_id: int) -> User:
        user = db.session.get(User, user_id)
        if user is None:
            raise NotFoundError("User account not found.")
        return user

    @staticmethod
    def find_by_email(email: str):
        if not email:
            return None
        stmt = select(User).where(func.lower(User.email) == email.strip().lower())
        return db.session.scalars(stmt).first()

    @staticmethod
    def staff(include_viewers: bool = False):
        """Active ICT officers/administrators, for assignment dropdowns."""
        stmt = select(User).where(User.is_active.is_(True))
        if not include_viewers:
            stmt = stmt.where(User.role.in_((ROLE_ADMIN, "ict_officer")))
        return db.session.scalars(stmt.order_by(User.full_name)).all()

    @staticmethod
    def count_by_role():
        rows = db.session.execute(
            select(User.role, func.count(User.id)).group_by(User.role)
        ).all()
        return {role: total for role, total in rows}

    # -------------------------------------------------------------- create
    @classmethod
    def create_user(cls, data: dict, actor: User) -> User:
        full_name = (data.get("full_name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        role = data.get("role")
        password = data.get("password") or ""

        if not full_name:
            raise ValidationError("Full name is required.",
                                  {"full_name": "Full name is required."})
        if not email or "@" not in email:
            raise ValidationError("A valid email address is required.",
                                  {"email": "Enter a valid email address."})
        if role not in ROLES:
            raise ValidationError("Select a valid role.", {"role": "Invalid role."})

        if cls.find_by_email(email) is not None:
            raise DuplicateError(f"An account with the email '{email}' already exists.")

        if not password:
            raise ValidationError("Password is required.", {"password": "Required."})
        check_password_strength(password)

        user = User(full_name=full_name, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_CREATE,
            "user",
            user.id,
            f"{actor.role_label} created an {user.role_label} account for "
            f"{user.full_name} ({user.email}).",
        )
        return user

    # -------------------------------------------------------------- update
    @classmethod
    def update_user(cls, user: User, data: dict, actor: User) -> User:
        full_name = (data.get("full_name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        role = data.get("role") or user.role

        if not full_name:
            raise ValidationError("Full name is required.")
        if not email or "@" not in email:
            raise ValidationError("A valid email address is required.")
        if role not in ROLES:
            raise ValidationError("Select a valid role.")

        clash = cls.find_by_email(email)
        if clash is not None and clash.id != user.id:
            raise DuplicateError(f"Another account already uses '{email}'.")

        # Never allow the last active administrator to be demoted.
        if user.is_admin and role != ROLE_ADMIN:
            cls._assert_not_last_admin(user.id, "change the role of")
        if user.id == actor.id and role != user.role:
            raise ValidationError("You cannot change your own role.")

        changes = []
        if user.full_name != full_name:
            changes.append(f"name {user.full_name} → {full_name}")
        if user.email != email:
            changes.append(f"email {user.email} → {email}")
        if user.role != role:
            changes.append(
                f"role {user.role_label} → {ROLE_LABELS.get(role, role)}"
            )

        user.full_name = full_name
        user.email = email
        user.role = role

        if data.get("password"):
            check_password_strength(data["password"])
            user.set_password(data["password"])
            changes.append("password reset")

        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_UPDATE,
            "user",
            user.id,
            f"{actor.role_label} updated the account of {user.full_name}"
            + (f" ({'; '.join(changes)})." if changes else "."),
        )
        return user

    @classmethod
    def set_password(cls, user: User, new_password: str, actor: User) -> User:
        """Reset another account's password (administrator action)."""
        check_password_strength(new_password)
        user.set_password(new_password)
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_UPDATE,
            "user",
            user.id,
            f"{actor.role_label} reset the password of {user.full_name}.",
        )
        return user

    @staticmethod
    def change_own_password(user: User, current_password: str, new_password: str):
        """Self-service password change (always requires the current one)."""
        if not user.check_password(current_password or ""):
            raise ValidationError(
                "Your current password is not correct.",
                {"current_password": "Incorrect password."},
            )
        if current_password == new_password:
            raise ValidationError(
                "Please choose a password you have not used before.",
                {"password": "Choose a different password."},
            )
        check_password_strength(new_password)
        user.set_password(new_password)
        audit_service.AuditService.log(
            user,
            audit_service.ACTION_UPDATE,
            "user",
            user.id,
            f"{user.full_name} changed their own password.",
        )
        return user

    # ------------------------------------------------- activate/deactivate
    @classmethod
    def deactivate(cls, user: User, actor: User) -> User:
        if user.id == actor.id:
            raise ValidationError("You cannot deactivate your own account.")
        if not user.is_active:
            raise ValidationError("That account is already deactivated.")
        if user.is_admin:
            cls._assert_not_last_admin(user.id, "deactivate")
        user.deactivate()
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_DEACTIVATE,
            "user",
            user.id,
            f"{actor.role_label} deactivated the account of {user.full_name}.",
        )
        return user

    @classmethod
    def activate(cls, user: User, actor: User) -> User:
        if user.is_active:
            raise ValidationError("That account is already active.")
        user.activate()
        audit_service.AuditService.log(
            actor,
            audit_service.ACTION_ACTIVATE,
            "user",
            user.id,
            f"{actor.role_label} reactivated the account of {user.full_name}.",
        )
        return user

    # ------------------------------------------------------------ internals
    @staticmethod
    def _assert_not_last_admin(excluded_id: int, verb: str) -> None:
        remaining = db.session.scalar(
            select(func.count(User.id)).where(
                User.role == ROLE_ADMIN,
                User.is_active.is_(True),
                User.id != excluded_id,
            )
        )
        if not remaining:
            raise ValidationError(
                f"You cannot {verb} the only active administrator account."
            )

    # -------------------------------------------------------------- queries
    @classmethod
    def search_statement(cls, **filters):
        stmt = select(User)
        search = (filters.get("search") or "").strip()
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(User.full_name.ilike(pattern), User.email.ilike(pattern))
            )
        if filters.get("role"):
            stmt = stmt.where(User.role == filters["role"])
        status = filters.get("status")
        if status == "active":
            stmt = stmt.where(User.is_active.is_(True))
        elif status == "inactive":
            stmt = stmt.where(User.is_active.is_(False))
        return stmt.order_by(User.full_name.asc())

    @classmethod
    def paginate(cls, page: int, per_page: int, **filters):
        return db.paginate(
            cls.search_statement(**filters), page=page, per_page=per_page,
            error_out=False,
        )
