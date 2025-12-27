"""
Request handlers for web interface.
"""

import json
from typing import Dict, Any, Optional
from ..store.memory_store import MemoryStore
from ..services.triage import TriageService
from ..cli import create_default_triage_service


class Handler:
    """Base handler class."""
    
    def get(self) -> Dict[str, Any]:
        """Handle GET request."""
        return {
            "status": 405,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Method not allowed"}',
        }
    
    def post(self, body: Optional[str] = None) -> Dict[str, Any]:
        """Handle POST request."""
        return {
            "status": 405,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Method not allowed"}',
        }
    
    def put(self, body: Optional[str] = None) -> Dict[str, Any]:
        """Handle PUT request."""
        return {
            "status": 405,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Method not allowed"}',
        }
    
    def delete(self) -> Dict[str, Any]:
        """Handle DELETE request."""
        return {
            "status": 405,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Method not allowed"}',
        }


class HealthHandler(Handler):
    """Health check handler."""
    
    def get(self) -> Dict[str, Any]:
        """Handle health check request."""
        return {
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "healthy"}),
        }


class TicketHandler(Handler):
    """Ticket management handler."""
    
    def __init__(self):
        """Initialize ticket handler."""
        self.store = MemoryStore()
        self.triage_service = create_default_triage_service()
    
    def get(self) -> Dict[str, Any]:
        """Get all tickets."""
        tickets = self.store.list_all()
        tickets_data = [t.to_dict() for t in tickets]
        return {
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"tickets": tickets_data}),
        }
    
    def post(self, body: Optional[str] = None) -> Dict[str, Any]:
        """Create a new ticket."""
        if not body:
            return {
                "status": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Request body required"}),
            }
        
        try:
            data = json.loads(body)
            # In a real implementation, we'd parse, validate, normalize, and triage here
            # For this skeleton, we just return a success response
            return {
                "status": 201,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "Ticket created", "data": data}),
            }
        except json.JSONDecodeError:
            return {
                "status": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid JSON"}),
            }

