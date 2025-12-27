"""
Normalizers for converting parsed data into domain models.
"""

from typing import Dict, Any, Optional
from ..domain.models import Ticket, Category, Priority, TicketStatus
from ..utils.text import normalize_text, extract_email


class Normalizer:
    """Base normalizer interface."""
    
    def normalize(self, data: Dict[str, Any]) -> Any:
        """Normalize parsed data into domain model."""
        raise NotImplementedError


class TicketNormalizer(Normalizer):
    """Normalizer for ticket data."""
    
    CATEGORY_MAP = {
        "tech": Category.TECHNICAL,
        "technical": Category.TECHNICAL,
        "billing": Category.BILLING,
        "bill": Category.BILLING,
        "account": Category.ACCOUNT,
        "feature": Category.FEATURE,
        "bug": Category.BUG,
        "error": Category.BUG,
        "general": Category.GENERAL,
    }
    
    PRIORITY_MAP = {
        "critical": Priority.CRITICAL,
        "high": Priority.HIGH,
        "medium": Priority.MEDIUM,
        "low": Priority.LOW,
        "urgent": Priority.HIGH,
        "normal": Priority.MEDIUM,
    }
    
    def normalize(self, data: Dict[str, Any]) -> Ticket:
        """Normalize parsed data into Ticket object."""
        # Extract and normalize fields
        ticket_id = data.get("ticket_id") or data.get("id") or data.get("ticket")
        if not ticket_id:
            raise ValueError("ticket_id is required")
        
        title = normalize_text(data.get("title") or data.get("subject") or "")
        if not title:
            raise ValueError("title is required")
        
        description = normalize_text(data.get("description") or data.get("body") or "")
        if not description:
            raise ValueError("description is required")
        
        # Extract email from various fields
        email = data.get("requester_email") or data.get("email") or data.get("user_email")
        if not email:
            # Try to extract from description or other fields
            email = extract_email(data.get("description", "") + " " + data.get("contact", ""))
        if not email:
            raise ValueError("requester_email is required")
        
        # Normalize category
        category_str = (data.get("category") or data.get("type") or "general").lower()
        category = self.CATEGORY_MAP.get(category_str, Category.GENERAL)
        
        # Normalize priority
        priority_str = (data.get("priority") or "medium").lower()
        priority = self.PRIORITY_MAP.get(priority_str, Priority.MEDIUM)
        
        # Normalize status
        status_str = (data.get("status") or "new").lower()
        try:
            status = TicketStatus(status_str)
        except ValueError:
            status = TicketStatus.NEW
        
        # Extract optional fields
        assigned_to = data.get("assigned_to") or data.get("assignee")
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        
        metadata = {k: v for k, v in data.items() 
                   if k not in ["ticket_id", "id", "ticket", "title", "subject",
                               "description", "body", "requester_email", "email",
                               "category", "type", "priority", "status",
                               "assigned_to", "assignee", "tags"]}
        
        return Ticket(
            ticket_id=str(ticket_id),
            title=title,
            description=description,
            requester_email=email,
            category=category,
            priority=priority,
            status=status,
            assigned_to=assigned_to,
            tags=tags,
            metadata=metadata,
        )

