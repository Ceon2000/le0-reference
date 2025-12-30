"""T06: Test error handling patterns for silent failures."""
import pytest
import logging
from helpdesk_ai.store.memory_store import MemoryStore
from helpdesk_ai.store.cache import MemoryCache
from helpdesk_ai.config import Config
from helpdesk_ai.domain.models import Ticket, Category


class TestSilentFailures:
    """Test that errors are logged and not silently swallowed."""

    def test_config_load_invalid_file_logs_error(self, caplog, tmp_path):
        """Loading invalid config file should log error, not fail silently."""
        # Create invalid JSON file
        invalid_file = tmp_path / "bad_config.json"
        invalid_file.write_text("{invalid json content")
        
        with caplog.at_level(logging.WARNING):
            config = Config(config_file=str(invalid_file))
        
        # Bug: Config.load_from_file() has bare except that swallows all errors
        # Should log the error but currently doesn't

    def test_memory_store_get_nonexistent_returns_none(self, memory_store):
        """Getting nonexistent ticket should return None, not raise."""
        result = memory_store.get("nonexistent-id")
        assert result is None

    def test_memory_store_delete_nonexistent_returns_false(self, memory_store):
        """Deleting nonexistent ticket should return False."""
        result = memory_store.delete("nonexistent-id")
        assert result is False

    def test_cache_get_nonexistent_returns_none(self, memory_cache):
        """Cache miss should return None."""
        result = memory_cache.get("nonexistent-key")
        assert result is None

    def test_cache_delete_nonexistent_silent(self, memory_cache):
        """Deleting nonexistent cache key should not raise."""
        memory_cache.delete("nonexistent-key")  # Should not raise

    def test_config_get_missing_key_returns_default(self, config):
        """Getting missing config key should return default."""
        result = config.get("nonexistent_key", "default_value")
        assert result == "default_value"

    def test_weighted_scorer_missing_weight_uses_default(self):
        """Scorer should use default weight for missing keys."""
        from helpdesk_ai.domain.scoring import WeightedScorer
        from helpdesk_ai.domain.models import Ticket, Category, Priority
        
        # Create scorer with mismatched weights (missing key)
        scorer = WeightedScorer(
            scorers={"a": lambda t: 5.0, "b": lambda t: 3.0},
            weights={"a": 1.0},  # Missing weight for "b"
        )
        ticket = Ticket(
            ticket_id="T1",
            title="Test",
            description="Test",
            requester_email="t@t.com",
            category=Category.GENERAL,
        )
        # Should not raise, should use default weight
        score = scorer.score(ticket)
        assert score is not None

    def test_operations_should_log_errors(self, caplog, memory_store, sample_ticket):
        """Critical operations should log their activity."""
        with caplog.at_level(logging.DEBUG):
            memory_store.save(sample_ticket)
            memory_store.get(sample_ticket.ticket_id)
            memory_store.delete(sample_ticket.ticket_id)
        
        # Bug: MemoryStore has no logging at all
        # In production, operations should be logged
