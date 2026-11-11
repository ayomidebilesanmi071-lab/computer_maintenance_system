"""Exceptions raised by the service layer.

Routes catch these and turn them into flash messages / HTTP responses, so the
business rules live in one place instead of being copy-pasted across handlers.
"""


class ServiceError(Exception):
    """Base class for business-rule violations."""


class ValidationError(ServiceError):
    """Bad or inconsistent input supplied to a service call."""

    def __init__(self, message: str, field_errors=None):
        super().__init__(message)
        self.field_errors = field_errors or {}


class DuplicateError(ServiceError):
    """A uniqueness rule (asset tag / serial number) was violated."""


class TransitionError(ServiceError):
    """An illegal state transition (e.g. Closed -> Reported)."""


class NotFoundError(ServiceError):
    """The referenced record does not exist."""
