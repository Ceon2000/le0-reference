"""
ID generation utilities.
"""

import uuid
from datetime import datetime


def generate_ticket_id(prefix: str = "TKT") -> str:
    """Generate a unique ticket ID."""
    timestamp = datetime.now().strftime("%Y%m%d")
    unique_part = str(uuid.uuid4())[:8].upper()
    return f"{prefix}-{timestamp}-{unique_part}"


def generate_audit_id(prefix: str = "AUD") -> str:
    """Generate a unique audit log ID."""
    timestamp = datetime.now().strftime("%Y%m%d")
    unique_part = str(uuid.uuid4())[:8].upper()
    return f"{prefix}-{timestamp}-{unique_part}"


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())


def is_valid_ticket_id(ticket_id: str) -> bool:
    """Validate ticket ID format."""
    parts = ticket_id.split("-")
    if len(parts) != 3:
        return False
    prefix, date_part, unique_part = parts
    if len(date_part) != 8 or not date_part.isdigit():
        return False
    if len(unique_part) != 8:
        return False
    return True

