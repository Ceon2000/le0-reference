"""
Domain models for helpdesk tickets and related entities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class TicketStatus(Enum):
    """Ticket status enumeration."""
    NEW = "new"
    TRIAGED = "triaged"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class Priority(Enum):
    """Priority levels for tickets."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(Enum):
    """Ticket category enumeration."""
    TECHNICAL = "technical"
    BILLING = "billing"
    ACCOUNT = "account"
    FEATURE = "feature"
    BUG = "bug"
    GENERAL = "general"


@dataclass
class Ticket:
    """Represents a helpdesk ticket."""
    
    ticket_id: str
    title: str
    description: str
    requester_email: str
    category: Category
    priority: Priority = Priority.MEDIUM
    status: TicketStatus = TicketStatus.NEW
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    assigned_to: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: Optional[float] = None
    
    def update(self, **kwargs) -> None:
        """Update ticket fields and set updated_at timestamp."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ticket to dictionary representation."""
        return {
            "ticket_id": self.ticket_id,
            "title": self.title,
            "description": self.description,
            "requester_email": self.requester_email,
            "category": self.category.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "assigned_to": self.assigned_to,
            "tags": self.tags,
            "metadata": self.metadata,
            "score": self.score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ticket":
        """Create ticket from dictionary representation."""
        data = data.copy()
        data["category"] = Category(data["category"])
        data["priority"] = Priority(data["priority"])
        data["status"] = TicketStatus(data["status"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class TicketUpdate:
    """Represents an update to a ticket."""
    
    ticket_id: str
    field: str
    old_value: Any
    new_value: Any
    updated_by: str
    timestamp: datetime = field(default_factory=datetime.now)
    reason: Optional[str] = None

