"""
File-based storage implementation for tickets.
"""

import json
import os
from pathlib import Path
from typing import Optional, List
from ..domain.models import Ticket


class FileStore:
    """File-based ticket storage."""
    
    def __init__(self, base_path: str):
        """Initialize file store with base path."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.tickets_dir = self.base_path / "tickets"
        self.tickets_dir.mkdir(exist_ok=True)
    
    def _ticket_path(self, ticket_id: str) -> Path:
        """Get file path for a ticket."""
        return self.tickets_dir / f"{ticket_id}.json"
    
    def save(self, ticket: Ticket) -> None:
        """Save a ticket to file."""
        path = self._ticket_path(ticket.ticket_id)
        with open(path, "w") as f:
            json.dump(ticket.to_dict(), f, indent=2)
    
    def get(self, ticket_id: str) -> Optional[Ticket]:
        """Get a ticket by ID."""
        path = self._ticket_path(ticket_id)
        if not path.exists():
            return None
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return Ticket.from_dict(data)
        except Exception:
            return None
    
    def delete(self, ticket_id: str) -> bool:
        """Delete a ticket by ID. Returns True if deleted."""
        path = self._ticket_path(ticket_id)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def list_all(self) -> List[Ticket]:
        """List all tickets."""
        tickets = []
        for path in self.tickets_dir.glob("*.json"):
            try:
                ticket_id = path.stem
                ticket = self.get(ticket_id)
                if ticket:
                    tickets.append(ticket)
            except Exception:
                continue
        return tickets
    
    def count(self) -> int:
        """Get total number of tickets."""
        return len(list(self.tickets_dir.glob("*.json")))

