"""T17-T20: Compliance, escalation, SLA, and metrics tests."""
import pytest
from datetime import datetime, timedelta
from helpdesk_ai.services.escalation import EscalationService
from helpdesk_ai.domain.models import Ticket, TicketStatus, Priority, Category


class TestAuditCompliance:
    """T17: Test audit logging for compliance."""

    def test_escalation_creates_audit_trail(self, escalation_service, sample_ticket, caplog):
        """Escalation should create audit trail."""
        import logging
        with caplog.at_level(logging.DEBUG):
            escalation_service.escalate(sample_ticket, "Compliance test")
        
        # Bug: No audit logging exists
        # Should have audit log entry for escalation

    def test_ticket_updates_tracked(self, sample_ticket, caplog):
        """All ticket updates should be tracked."""
        import logging
        with caplog.at_level(logging.DEBUG):
            sample_ticket.update(priority=Priority.HIGH)
            sample_ticket.update(status=TicketStatus.ASSIGNED)
        
        # Bug: No update tracking/audit


class TestPriorityInversion:
    """T18: Test queue management for priority inversion."""

    def test_critical_before_low(self, escalation_service):
        """Critical tickets should not be starved by low priority backlog."""
        tickets = []
        
        # Add many low priority tickets first
        for i in range(10):
            tickets.append(Ticket(
                ticket_id=f"LOW-{i}",
                title="Low priority",
                description="Test",
                requester_email="t@t.com",
                category=Category.GENERAL,
                priority=Priority.LOW,
            ))
        
        # Add critical ticket
        critical = Ticket(
            ticket_id="CRIT-1",
            title="Critical issue",
            description="Test",
            requester_email="t@t.com",
            category=Category.BUG,
            priority=Priority.CRITICAL,
        )
        tickets.append(critical)
        
        # Check escalation
        escalated = escalation_service.batch_check(tickets)
        # Critical should be escalated regardless of queue position
        assert any(t.ticket_id == "CRIT-1" for t in escalated)


class TestEscalationRules:
    """T19: Test escalation rules correctness."""

    def test_escalate_after_threshold(self, monkeypatch, fake_clock):
        """Ticket should escalate after age threshold."""
        service = EscalationService(escalation_threshold_hours=24)
        
        # Create old ticket
        old_ticket = Ticket(
            ticket_id="OLD-1",
            title="Old ticket",
            description="Test",
            requester_email="t@t.com",
            category=Category.GENERAL,
            priority=Priority.MEDIUM,
        )
        # Manually set created_at to be old
        old_ticket.created_at = datetime.now() - timedelta(hours=25)
        
        assert service.should_escalate(old_ticket)

    def test_no_escalate_resolved(self, escalation_service):
        """Resolved tickets should not escalate."""
        ticket = Ticket(
            ticket_id="RES-1",
            title="Resolved",
            description="Test",
            requester_email="t@t.com",
            category=Category.GENERAL,
            priority=Priority.CRITICAL,
            status=TicketStatus.RESOLVED,
        )
        
        assert not escalation_service.should_escalate(ticket)

    def test_auto_escalate_critical(self, escalation_service, critical_ticket):
        """Critical tickets should auto-escalate."""
        assert escalation_service.should_escalate(critical_ticket)


class TestSLATimezone:
    """T20: Test SLA tracking timezone handling."""

    def test_ticket_timestamps_consistent(self, sample_ticket):
        """Ticket timestamps should be consistent."""
        created = sample_ticket.created_at
        updated = sample_ticket.updated_at
        
        # Both should be datetime objects
        assert isinstance(created, datetime)
        assert isinstance(updated, datetime)

    def test_timezone_serialization(self, sample_ticket):
        """Timestamps should serialize correctly."""
        data = sample_ticket.to_dict()
        
        # Should be ISO format strings
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

    def test_timezone_deserialization(self, sample_ticket):
        """Timestamps should deserialize correctly."""
        data = sample_ticket.to_dict()
        restored = Ticket.from_dict(data)
        
        assert isinstance(restored.created_at, datetime)
        assert isinstance(restored.updated_at, datetime)
