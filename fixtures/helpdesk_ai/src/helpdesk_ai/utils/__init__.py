"""Utility modules."""

from .time import format_timestamp, parse_timestamp, time_ago
from .text import normalize_text, extract_email, truncate_text
from .ids import generate_ticket_id, generate_audit_id
from .errors import HelpdeskError, ValidationError, StorageError

__all__ = [
    "format_timestamp",
    "parse_timestamp",
    "time_ago",
    "normalize_text",
    "extract_email",
    "truncate_text",
    "generate_ticket_id",
    "generate_audit_id",
    "HelpdeskError",
    "ValidationError",
    "StorageError",
]

