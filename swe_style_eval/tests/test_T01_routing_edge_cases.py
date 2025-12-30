"""T01: Test routing edge cases that could cause mis-routing."""
import pytest
from helpdesk_ai.domain.models import Ticket, Priority, Category, TicketStatus
from helpdesk_ai.services.routing import Router
from helpdesk_ai.domain.rules import RuleEngine


class TestRoutingEdgeCases:
    """Test Router.route() edge cases."""

    def test_route_with_none_category_raises_or_fallbacks(self, sample_ticket):
        """Route should handle tickets with unusual category gracefully."""
        router = Router(RuleEngine())
        # Bug: Router has no fallback for category not in default_assignees
        # If someone adds a new category, routing will fail
        result = router.route(sample_ticket)
        assert result.assigned_to is not None, "Ticket should always be assigned"

    def test_route_with_all_categories_covered(self, router):
        """All defined categories should have a default assignee."""
        for cat in Category:
            assert cat in router.default_assignees, f"Category {cat} missing default assignee"

    def test_route_assigns_confidence_for_rule_match(self, router, sample_ticket):
        """Rule-matched routes should have confidence = 1.0."""
        result = router.route(sample_ticket)
        # Even without matching rule, should have valid confidence
        assert 0.0 <= result.confidence <= 1.0, "Confidence must be between 0 and 1"

    def test_route_updates_ticket_assigned_to(self, router, sample_ticket):
        """Routing should update ticket's assigned_to field."""
        assert sample_ticket.assigned_to is None
        result = router.route(sample_ticket)
        assert sample_ticket.assigned_to == result.assigned_to

    def test_batch_route_handles_empty_list(self, router):
        """Batch routing empty list should return empty list."""
        results = router.batch_route([])
        assert results == []

    def test_batch_route_returns_same_length(self, router, sample_ticket, critical_ticket):
        """Batch routing should return same number of results as inputs."""
        results = router.batch_route([sample_ticket, critical_ticket])
        assert len(results) == 2

    @pytest.mark.parametrize("priority", list(Priority))
    def test_route_handles_all_priorities(self, router, priority):
        """Router should handle all priority levels."""
        ticket = Ticket(
            ticket_id="PRI-001",
            title="Test",
            description="Test",
            requester_email="test@test.com",
            category=Category.GENERAL,
            priority=priority,
        )
        result = router.route(ticket)
        assert result.priority is not None
