"""
Time utility functions.
"""

from datetime import datetime, timedelta
from typing import Optional


def format_timestamp(dt: datetime, format_str: Optional[str] = None) -> str:
    """Format datetime to string."""
    if format_str is None:
        format_str = "%Y-%m-%d %H:%M:%S"
    return dt.strftime(format_str)


def parse_timestamp(timestamp_str: str, format_str: Optional[str] = None) -> datetime:
    """Parse string to datetime."""
    if format_str is None:
        # Try ISO format first
        try:
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            format_str = "%Y-%m-%d %H:%M:%S"
    
    return datetime.strptime(timestamp_str, format_str)


def time_ago(dt: datetime) -> str:
    """Get human-readable time ago string."""
    delta = datetime.now() - dt
    
    if delta.days > 365:
        years = delta.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif delta.days > 30:
        months = delta.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif delta.days > 0:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    elif delta.seconds > 3600:
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif delta.seconds > 60:
        minutes = delta.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "just now"


def is_business_hours(dt: datetime) -> bool:
    """Check if datetime is within business hours (9 AM - 5 PM, Mon-Fri)."""
    if dt.weekday() >= 5:  # Saturday or Sunday
        return False
    return 9 <= dt.hour < 17


def add_business_days(dt: datetime, days: int) -> datetime:
    """Add business days to a datetime."""
    current = dt
    added = 0
    while added < days:
        current += timedelta(days=1)
        if is_business_hours(current):
            added += 1
    return current

