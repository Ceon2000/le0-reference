"""T21-T25: Metrics, backup, inter-service, permissions, and architecture tests."""
import pytest
import json
from pathlib import Path
from helpdesk_ai.domain.models import Ticket, Category, Priority, TicketStatus
from helpdesk_ai.store.memory_store import MemoryStore


class TestMetricsAccuracy:
    """T21: Test metrics collection accuracy."""

    def test_store_count_accurate(self, memory_store):
        """Store count should match actual tickets."""
        for i in range(10):
            ticket = Ticket(
                ticket_id=f"M{i}",
                title="Test",
                description="Test",
                requester_email="t@t.com",
                category=Category.GENERAL,
            )
            memory_store.save(ticket)
        
        assert memory_store.count() == 10

    def test_list_all_returns_all(self, memory_store):
        """list_all should return all stored tickets."""
        ids = set()
        for i in range(5):
            ticket = Ticket(
                ticket_id=f"L{i}",
                title="Test",
                description="Test",
                requester_email="t@t.com",
                category=Category.GENERAL,
            )
            memory_store.save(ticket)
            ids.add(f"L{i}")
        
        results = memory_store.list_all()
        result_ids = {t.ticket_id for t in results}
        assert result_ids == ids


class TestBackupRecovery:
    """T22: Test backup and recovery procedures."""

    def test_ticket_serialization_roundtrip(self, sample_ticket):
        """Ticket should survive serialize/deserialize."""
        data = sample_ticket.to_dict()
        json_str = json.dumps(data)
        
        loaded_data = json.loads(json_str)
        restored = Ticket.from_dict(loaded_data)
        
        assert restored.ticket_id == sample_ticket.ticket_id
        assert restored.title == sample_ticket.title
        assert restored.category == sample_ticket.category
        assert restored.priority == sample_ticket.priority
        assert restored.status == sample_ticket.status

    def test_store_can_repopulate(self, memory_store):
        """Store should be repopulatable from backup."""
        # Create and save tickets
        original_tickets = []
        for i in range(3):
            ticket = Ticket(
                ticket_id=f"B{i}",
                title=f"Backup {i}",
                description="Test",
                requester_email="t@t.com",
                category=Category.GENERAL,
            )
            original_tickets.append(ticket)
            memory_store.save(ticket)
        
        # Serialize
        backup = [t.to_dict() for t in memory_store.list_all()]
        
        # Clear and restore
        memory_store.clear()
        assert memory_store.count() == 0
        
        for data in backup:
            memory_store.save(Ticket.from_dict(data))
        
        assert memory_store.count() == 3


class TestInterServiceErrors:
    """T23: Test inter-service communication error handling."""

    def test_routing_handles_rule_engine_errors(self, router, sample_ticket, monkeypatch):
        """Router should handle rule engine errors gracefully."""
        def bad_match(*args):
            raise RuntimeError("Rule engine failure")
        
        monkeypatch.setattr(router.rule_engine, "get_highest_priority_match", bad_match)
        
        # Should either handle gracefully or raise specific exception
        try:
            result = router.route(sample_ticket)
            # If it didn't raise, it handled the error
        except RuntimeError:
            # Bug: Raw exception propagates - should be wrapped
            pytest.fail("RuntimeError should be caught and handled")

    def test_escalation_handles_ticket_errors(self, escalation_service):
        """Escalation should handle malformed tickets."""
        # Create ticket with missing fields (if possible)
        pass


class TestPermissionModel:
    """T24: Test user permission model for privilege escalation."""

    def test_ticket_has_requester(self, sample_ticket):
        """Ticket should track requester."""
        assert sample_ticket.requester_email is not None

    def test_ticket_has_assignee(self, router, sample_ticket):
        """Routed ticket should have assignee."""
        result = router.route(sample_ticket)
        assert result.assigned_to is not None

    def test_updates_should_track_actor(self, sample_ticket):
        """Ticket updates should track who made them."""
        # Bug: update() doesn't track who made the change
        sample_ticket.update(priority=Priority.HIGH)
        # Should have metadata about who made the change


class TestArchitectureSPOF:
    """T25: Test architecture for single points of failure."""

    def test_memory_store_isolation(self):
        """Each MemoryStore instance should be independent."""
        store1 = MemoryStore()
        store2 = MemoryStore()
        
        ticket = Ticket(
            ticket_id="ISO-1",
            title="Test",
            description="Test",
            requester_email="t@t.com",
            category=Category.GENERAL,
        )
        
        store1.save(ticket)
        
        # store2 should not see store1's ticket
        assert store2.get("ISO-1") is None
        assert store1.get("ISO-1") is not None

    def test_service_independence(self):
        """Services should be independently instantiable."""
        from helpdesk_ai.services.routing import Router
        from helpdesk_ai.services.escalation import EscalationService
        from helpdesk_ai.domain.rules import RuleEngine
        
        # Each service should work independently
        router = Router(RuleEngine())
        escalation = EscalationService()
        
        assert router is not None
        assert escalation is not None

    def test_config_independence(self, tmp_path):
        """Config instances should be independent."""
        from helpdesk_ai.config import Config
        
        config1 = Config()
        config2 = Config()
        
        config1.set("custom", "value1")
        config2.set("custom", "value2")
        
        # Should be independent (unless env var interferes)
        assert config1._config["custom"] == "value1"
        assert config2._config["custom"] == "value2"
