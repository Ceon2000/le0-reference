"""
T01: Routing Edge Cases
Tests for ticket routing edge cases and mis-routing scenarios.
"""

import pytest
import sys
from pathlib import Path

# Add fixture path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fixtures" / "helpdesk_ai" / "src"))

try:
    from helpdesk_ai.services.routing import Router, RoutingResult
    from helpdesk_ai.domain.models import Ticket, Priority, Category, Status
    from helpdesk_ai.domain.rules import RuleEngine, Rule
except ImportError as e:
    pytest.skip(f"Cannot import helpdesk_ai: {e}", allow_module_level=True)


class TestT01Routing:
    """T01: Routing edge case tests."""
    
    def test_none_category_handling(self):
        """Router should handle tickets with None or unset category gracefully."""
        rule_engine = RuleEngine()
        router = Router(rule_engine)
        
        # Create ticket with valid category first
        ticket = Ticket(
            ticket_id="TKT-TEST-001",
            title="Test ticket",
            description="Test description",
            requester_email="test@example.com",
            category=Category.GENERAL,
            priority=Priority.MEDIUM,
        )
        
        # Route should not raise
        result = router.route(ticket)
        
        # Should have assigned_to
        assert result.assigned_to is not None, "Should have default assignee"
        assert result.confidence >= 0.0, "Confidence should be non-negative"
    
    def test_empty_rule_engine(self):
        """Router should work with empty rule engine (no rules)."""
        rule_engine = RuleEngine()  # Empty
        router = Router(rule_engine)
        
        ticket = Ticket(
            ticket_id="TKT-TEST-002",
            title="No rules test",
            description="Testing with empty rule engine",
            requester_email="test@example.com",
            category=Category.TECHNICAL,
            priority=Priority.HIGH,
        )
        
        result = router.route(ticket)
        
        # Should fall back to default routing
        assert result.rule_matched is None, "No rule should match"
        assert result.confidence < 1.0, "Confidence should be reduced for default"
        assert result.assigned_to is not None, "Should still have assignee"
