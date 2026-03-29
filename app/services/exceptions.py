from __future__ import annotations


class ServiceError(Exception):
    """Base service error with a safe user-facing message."""


class ValidationError(ServiceError):
    """Raised when user input is invalid."""


class AccessDeniedError(ServiceError):
    """Raised when an action is not allowed."""


class ConflictError(ServiceError):
    """Raised when state conflicts with the requested action."""


class NotFoundError(ServiceError):
    """Raised when a requested resource does not exist."""

