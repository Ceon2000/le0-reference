"""
Audit service for tracking ticket changes and operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from ..domain.models import Ticket


@dataclass
class AuditLog:
    """Represents an audit log entry."""
    
    log_id: str
    ticket_id: str
    action: str
    actor: str
    timestamp: datetime = field(default_factory=datetime.now)
    changes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuditService:
    """Service for managing audit logs."""
    
    def __init__(self):
        """Initialize audit service."""
        self._logs: List[AuditLog] = []
    
    def log(
        self,
        ticket_id: str,
        action: str,
        actor: str,
        changes: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        log_id = f"audit_{len(self._logs) + 1}_{datetime.now().timestamp()}"
        log = AuditLog(
            log_id=log_id,
            ticket_id=ticket_id,
            action=action,
            actor=actor,
            changes=changes or {},
            metadata=metadata or {},
        )
        self._logs.append(log)
        return log
    
    def get_logs_for_ticket(self, ticket_id: str) -> List[AuditLog]:
        """Get all audit logs for a ticket."""
        return [log for log in self._logs if log.ticket_id == ticket_id]
    
    def get_logs_for_actor(self, actor: str) -> List[AuditLog]:
        """Get all audit logs for an actor."""
        return [log for log in self._logs if log.actor == actor]
    
    def get_recent_logs(self, limit: int = 100) -> List[AuditLog]:
        """Get recent audit logs."""
        return sorted(self._logs, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    def clear(self) -> None:
        """Clear all audit logs."""
        self._logs.clear()

