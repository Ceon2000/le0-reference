"""
Minimal web application skeleton for helpdesk service.
"""

from typing import Dict, Any, Optional
from .handlers import TicketHandler, HealthHandler


class WebApp:
    """Minimal WSGI-like web application."""
    
    def __init__(self):
        """Initialize web application."""
        self.handlers = {
            "/health": HealthHandler(),
            "/tickets": TicketHandler(),
        }
    
    def handle_request(self, path: str, method: str = "GET", body: Optional[str] = None) -> Dict[str, Any]:
        """Handle a web request."""
        handler = self.handlers.get(path)
        if not handler:
            return {
                "status": 404,
                "headers": {"Content-Type": "application/json"},
                "body": '{"error": "Not found"}',
            }
        
        if method == "GET":
            return handler.get()
        elif method == "POST":
            return handler.post(body)
        elif method == "PUT":
            return handler.put(body)
        elif method == "DELETE":
            return handler.delete()
        else:
            return {
                "status": 405,
                "headers": {"Content-Type": "application/json"},
                "body": '{"error": "Method not allowed"}',
            }


def create_app() -> WebApp:
    """Create and configure web application."""
    return WebApp()

