"""
Custom exception classes.
"""


class HelpdeskError(Exception):
    """Base exception for helpdesk operations."""
    pass


class ValidationError(HelpdeskError):
    """Raised when validation fails."""
    pass


class StorageError(HelpdeskError):
    """Raised when storage operations fail."""
    pass


class RoutingError(HelpdeskError):
    """Raised when routing fails."""
    pass


class ScoringError(HelpdeskError):
    """Raised when scoring fails."""
    pass


class ParsingError(HelpdeskError):
    """Raised when parsing fails."""
    pass

