"""
Escalation service for handling ticket escalations.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from ..domain.models import Ticket, TicketStatus, Priority


class EscalationService:
    """Service for managing ticket escalations."""
    
    def __init__(
        self,
        escalation_threshold_hours: int = 24,
        auto_escalate_critical: bool = True,
    ):
        """Initialize escalation service."""
        self.escalation_threshold_hours = escalation_threshold_hours
        self.auto_escalate_critical = auto_escalate_critical
    
    def should_escalate(self, ticket: Ticket) -> bool:
        """Check if a ticket should be escalated."""
        # Auto-escalate critical tickets
        if self.auto_escalate_critical and ticket.priority == Priority.CRITICAL:
            if ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                return True
        
        # Escalate based on age
        age = datetime.now() - ticket.created_at
        if age > timedelta(hours=self.escalation_threshold_hours):
            if ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                return True
        
        return False
    
    def escalate(self, ticket: Ticket, reason: Optional[str] = None) -> Ticket:
        """Escalate a ticket."""
        if ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            return ticket
        
        # Increase priority if not already critical
        if ticket.priority != Priority.CRITICAL:
            if ticket.priority == Priority.LOW:
                ticket.priority = Priority.MEDIUM
            elif ticket.priority == Priority.MEDIUM:
                ticket.priority = Priority.HIGH
            elif ticket.priority == Priority.HIGH:
                ticket.priority = Priority.CRITICAL
        
        ticket.status = TicketStatus.ESCALATED
        ticket.metadata["escalated_at"] = datetime.now().isoformat()
        if reason:
            ticket.metadata["escalation_reason"] = reason
        
        return ticket
    
    def check_and_escalate(self, ticket: Ticket) -> Optional[Ticket]:
        """Check if ticket should be escalated and escalate if needed."""
        if self.should_escalate(ticket):
            return self.escalate(ticket, "Automatic escalation due to age or priority")
        return None
    
    def batch_check(self, tickets: List[Ticket]) -> List[Ticket]:
        """Check multiple tickets for escalation."""
        escalated = []
        for ticket in tickets:
            escalated_ticket = self.check_and_escalate(ticket)
            if escalated_ticket:
                escalated.append(escalated_ticket)
        return escalated

