"""
In-memory storage implementation for tickets.
"""

from typing import Dict, Optional, List
from ..domain.models import Ticket


class MemoryStore:
    """In-memory ticket storage."""
    
    def __init__(self):
        """Initialize memory store."""
        self._tickets: Dict[str, Ticket] = {}
    
    def save(self, ticket: Ticket) -> None:
        """Save a ticket."""
        self._tickets[ticket.ticket_id] = ticket
    
    def get(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
        return self._tickets.get(ticket_id)
    
    def delete(self, ticket_id: str) -> bool:
        """Delete a ticket by ID. Returns True if deleted."""
        if ticket_id in self._tickets:
            del self._tickets[ticket_id]
            return True
        return False
    
    def list_all(self) -> List[Ticket]:
        """List all tickets."""
        return list(self._tickets.values())
    
    def search(self, **criteria) -> List[Ticket]:
        """Search tickets by criteria."""
        results = []
        for ticket in self._tickets.values():
            match = True
            for key, value in criteria.items():
                if not hasattr(ticket, key):
                    match = False
                    break
                if getattr(ticket, key) != value:
                    match = False
                    break
            if match:
                results.append(ticket)
        return results
    
    def count(self) -> int:
        """Get total number of tickets."""
        return len(self._tickets)
    
    def clear(self) -> None:
        """Clear all tickets."""
        self._tickets.clear()

