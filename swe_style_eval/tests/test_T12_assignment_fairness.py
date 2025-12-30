"""T12: Test ticket assignment algorithm for fairness across agents."""
import pytest
from collections import Counter
from helpdesk_ai.services.routing import Router
from helpdesk_ai.domain.rules import RuleEngine
from helpdesk_ai.domain.models import Ticket, Category, Priority


class TestAssignmentFairness:
    """Test fair distribution of tickets across agents."""

    @pytest.fixture
    def router(self):
        return Router(RuleEngine())

    def test_same_category_same_assignee(self, router):
        """Same category should route to same team."""
        tickets = [
            Ticket(
                ticket_id=f"T{i}",
                title=f"Test {i}",
                description="Test",
                requester_email="t@t.com",
                category=Category.TECHNICAL,
            )
            for i in range(10)
        ]
        
        results = router.batch_route(tickets)
        assignees = {r.assigned_to for r in results}
        
        # All should go to same team
        assert len(assignees) == 1
        assert "tech-team" in assignees

    def test_distribution_across_categories(self, router):
        """Different categories should route to different teams."""
        tickets = []
        for cat in Category:
            tickets.append(Ticket(
                ticket_id=f"T-{cat.value}",
                title=f"Test for {cat.value}",
                description="Test",
                requester_email="t@t.com",
                category=cat,
            ))
        
        results = router.batch_route(tickets)
        assignees = {r.assigned_to for r in results}
        
        # Should have multiple different assignees
        assert len(assignees) > 1

    def test_no_overload_single_agent(self, router):
        """Work should be distributed, not all to one agent."""
        # Create diverse tickets
        tickets = []
        for i, cat in enumerate([Category.TECHNICAL, Category.BILLING, Category.BUG] * 10):
            tickets.append(Ticket(
                ticket_id=f"T{i}",
                title=f"Test {i}",
                description="Test",
                requester_email="t@t.com",
                category=cat,
            ))
        
        results = router.batch_route(tickets)
        assignee_counts = Counter(r.assigned_to for r in results)
        
        # No single assignee should have all tickets
        max_tickets = max(assignee_counts.values())
        assert max_tickets < len(tickets), "Single assignee has all tickets"

    def test_priority_does_not_affect_assignment(self, router):
        """Priority should not change which team gets assigned."""
        for priority in Priority:
            ticket = Ticket(
                ticket_id=f"P-{priority.value}",
                title="Test",
                description="Test",
                requester_email="t@t.com",
                category=Category.TECHNICAL,
                priority=priority,
            )
            result = router.route(ticket)
            assert result.assigned_to == "tech-team"
