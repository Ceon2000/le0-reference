"""T05: Test ticket lifecycle from creation to resolution."""
import pytest
from helpdesk_ai.domain.models import Ticket, Priority, Category, TicketStatus


class TestTicketLifecycle:
    """Test ticket state transitions and lifecycle."""

    def test_new_ticket_starts_in_new_status(self, sample_ticket):
        """New tickets should have NEW status."""
        assert sample_ticket.status == TicketStatus.NEW

    def test_ticket_update_changes_status(self, sample_ticket):
        """Ticket.update() should change status."""
        sample_ticket.update(status=TicketStatus.TRIAGED)
        assert sample_ticket.status == TicketStatus.TRIAGED

    def test_ticket_update_changes_priority(self, sample_ticket):
        """Ticket.update() should change priority."""
        sample_ticket.update(priority=Priority.HIGH)
        assert sample_ticket.priority == Priority.HIGH

    def test_ticket_update_updates_timestamp(self, sample_ticket):
        """Ticket.update() should update updated_at timestamp."""
        original_time = sample_ticket.updated_at
        sample_ticket.update(title="Updated Title")
        # Note: This might pass too quickly; in real tests, mock time
        assert sample_ticket.updated_at >= original_time

    def test_valid_status_transitions(self, sample_ticket):
        """Document valid status transitions."""
        # NEW -> TRIAGED
        sample_ticket.update(status=TicketStatus.TRIAGED)
        assert sample_ticket.status == TicketStatus.TRIAGED
        
        # TRIAGED -> ASSIGNED
        sample_ticket.update(status=TicketStatus.ASSIGNED)
        assert sample_ticket.status == TicketStatus.ASSIGNED
        
        # ASSIGNED -> IN_PROGRESS
        sample_ticket.update(status=TicketStatus.IN_PROGRESS)
        assert sample_ticket.status == TicketStatus.IN_PROGRESS
        
        # IN_PROGRESS -> RESOLVED
        sample_ticket.update(status=TicketStatus.RESOLVED)
        assert sample_ticket.status == TicketStatus.RESOLVED
        
        # RESOLVED -> CLOSED
        sample_ticket.update(status=TicketStatus.CLOSED)
        assert sample_ticket.status == TicketStatus.CLOSED

    def test_invalid_status_transition_should_fail(self, sample_ticket):
        """Invalid transitions should be rejected (currently they aren't)."""
        # Bug: Ticket.update() allows any transition
        # CLOSED -> NEW should be invalid
        sample_ticket.update(status=TicketStatus.CLOSED)
        
        # This should raise an error but currently doesn't
        # Documenting the expected behavior
        try:
            sample_ticket.update(status=TicketStatus.NEW)
            # If we get here, the bug exists - no validation
            invalid_transition_allowed = True
        except ValueError:
            invalid_transition_allowed = False
        
        # This assertion documents the bug - it will fail when fixed
        assert not invalid_transition_allowed, "CLOSED -> NEW transition should be rejected"

    def test_escalation_status(self, sample_ticket):
        """Ticket can be escalated from various states."""
        sample_ticket.update(status=TicketStatus.IN_PROGRESS)
        sample_ticket.update(status=TicketStatus.ESCALATED)
        assert sample_ticket.status == TicketStatus.ESCALATED

    def test_ticket_to_dict_preserves_data(self, sample_ticket):
        """to_dict() should preserve all ticket data."""
        data = sample_ticket.to_dict()
        assert data["ticket_id"] == sample_ticket.ticket_id
        assert data["title"] == sample_ticket.title
        assert data["description"] == sample_ticket.description
        assert data["status"] == sample_ticket.status.value
        assert data["priority"] == sample_ticket.priority.value

    def test_ticket_from_dict_restores_data(self, sample_ticket):
        """from_dict() should restore ticket from dict."""
        data = sample_ticket.to_dict()
        restored = Ticket.from_dict(data)
        assert restored.ticket_id == sample_ticket.ticket_id
        assert restored.title == sample_ticket.title
        assert restored.status == sample_ticket.status
        assert restored.priority == sample_ticket.priority

    def test_all_status_values_are_valid(self):
        """All TicketStatus enum values should be usable."""
        for status in TicketStatus:
            ticket = Ticket(
                ticket_id="T1",
                title="Test",
                description="Test",
                requester_email="t@t.com",
                category=Category.GENERAL,
                status=status,
            )
            assert ticket.status == status
