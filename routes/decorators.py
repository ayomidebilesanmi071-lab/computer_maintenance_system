"""Reusable authorization decorators and request helpers.

Access control is enforced **on the server** for every protected view.  Hiding
a button in a template is a usability nicety, never a security measure, so every
blueprint decorates its routes with :func:`permission_required` (or
:func:`roles_required` for the few administrator-only areas).

Deactivated accounts are handled twice over: Flask-Login refuses to create the
session in the first place, and :meth:`models.user.User.can` returns ``False``
for an inactive account, so a session that is deactivated mid-flight loses
every permission immediately.
"""

from functools import wraps

from flask import abort, flash, request
from flask_login import current_user, login_required

DENIED_MESSAGE = "You do not have permission to perform that action."


def _deny(message: str = DENIED_MESSAGE):
    """Flash a friendly message and answer with a proper 403."""
    flash(message, "error")
    abort(403)


def permission_required(permission: str):
    """Require an authenticated user whose role grants ``permission``."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:  # pragma: no cover - login_required
                return login_required(view)(*args, **kwargs)
            if current_user.cannot(permission):
                _deny()
            return view(*args, **kwargs)

        return wrapper

    return decorator


def roles_required(*roles: str):
    """Require one of ``roles`` (used for administrator-only screens)."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            if not current_user.is_active or current_user.role not in roles:
                _deny()
            return view(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(view):
    """Shortcut for administrator-only routes that have no finer permission."""
    return roles_required("admin")(view)


def validated_filters(form, label: str = "filter"):
    """Validate a GET filter form and return the cleaned filter dictionary.

    Invalid values (a junk date, an unknown status, a non-numeric id) are
    reported to the user and then ignored, so a malformed query string can never
    reach the database layer or raise a 500.
    """
    if form.validate():
        return form.to_filters()

    problems = []
    for field_name, errors in form.errors.items():
        field = form._fields.get(field_name)
        label_text = getattr(field, "label", None)
        label_text = label_text.text if label_text else field_name
        problems.append(f"{label_text}: {errors[0]}")
    flash(
        f"Some {label} values were invalid and have been ignored — "
        + "; ".join(problems),
        "warning",
    )
    return form.to_filters()


def export_requested() -> bool:
    """True when the current request asks for a CSV download."""
    return request.args.get("export") == "csv"
