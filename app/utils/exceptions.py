class UserVisibleError(Exception):
    """An exception whose message is safe to show to the user."""


class AuthorizationError(UserVisibleError):
    """Raised when a user is not authorized for an action."""


class ConflictError(UserVisibleError):
    """Raised when an entity is already in the target state."""


class NotFoundError(UserVisibleError):
    """Raised when a required entity is missing."""


class RateLimitExceeded(UserVisibleError):
    """Raised when a user exceeds the configured limit."""
