"""T07: Test caching strategy for cache invalidation issues."""
import pytest
from datetime import datetime, timedelta
from helpdesk_ai.store.cache import MemoryCache, CacheEntry, Cache
from helpdesk_ai.domain.models import Ticket, Category


class TestCacheInvalidation:
    """Test cache TTL and invalidation behavior."""

    def test_cache_entry_expires_after_ttl(self, fake_clock, monkeypatch):
        """Cache entry should expire after TTL."""
        # Monkeypatch datetime.now to use fake clock
        monkeypatch.setattr("helpdesk_ai.store.cache.datetime", type("FakeDatetime", (), {
            "now": fake_clock.now
        }))
        
        entry = CacheEntry("test_value", ttl=60)
        assert not entry.is_expired()
        
        # Advance time past TTL
        fake_clock.advance(seconds=61)
        assert entry.is_expired()

    def test_cache_returns_none_for_expired(self, memory_cache, monkeypatch, fake_clock):
        """Expired entries should return None on get."""
        monkeypatch.setattr("helpdesk_ai.store.cache.datetime", type("FakeDatetime", (), {
            "now": fake_clock.now
        }))
        
        memory_cache.set("key1", "value1", ttl=30)
        
        # Before TTL
        assert memory_cache.get("key1") == "value1"
        
        # After TTL
        fake_clock.advance(seconds=31)
        assert memory_cache.get("key1") is None

    def test_cache_no_ttl_never_expires(self, memory_cache, monkeypatch, fake_clock):
        """Entries without TTL should never expire."""
        monkeypatch.setattr("helpdesk_ai.store.cache.datetime", type("FakeDatetime", (), {
            "now": fake_clock.now
        }))
        
        memory_cache.set("permanent", "value", ttl=None)
        
        fake_clock.advance(days=365)
        assert memory_cache.get("permanent") == "value"

    def test_cache_clear_removes_all(self, memory_cache):
        """Clear should remove all entries."""
        memory_cache.set("a", 1)
        memory_cache.set("b", 2)
        memory_cache.set("c", 3)
        
        memory_cache.clear()
        
        assert memory_cache.get("a") is None
        assert memory_cache.get("b") is None
        assert memory_cache.get("c") is None

    def test_cache_key_collision_bug(self, memory_cache):
        """Document the key collision bug in _generate_key."""
        # Bug: Different tickets with same email/category get same key
        ticket1 = Ticket(
            ticket_id="T1",
            title="First ticket",
            description="Description 1",
            requester_email="user@example.com",
            category=Category.TECHNICAL,
        )
        ticket2 = Ticket(
            ticket_id="T2",
            title="Second ticket",
            description="Description 2",
            requester_email="user@example.com",
            category=Category.TECHNICAL,
        )
        
        key1 = memory_cache.cache_ticket(ticket1)
        key2 = memory_cache.cache_ticket(ticket2)
        
        # Bug: keys are the same, ticket2 overwrites ticket1
        # This test documents the bug
        assert key1 != key2, "Different tickets should have different cache keys"

    def test_cache_key_order_sensitivity(self, memory_cache):
        """Key generation should be order-insensitive."""
        # Bug: _generate_key uses sorted() but only at top level
        key1 = memory_cache._generate_key("test", a=1, b=2)
        key2 = memory_cache._generate_key("test", b=2, a=1)
        
        # Should be the same (sorted handles this case)
        assert key1 == key2

    def test_cache_delete_removes_entry(self, memory_cache):
        """Delete should remove specific entry."""
        memory_cache.set("to_delete", "value")
        memory_cache.set("to_keep", "value")
        
        memory_cache.delete("to_delete")
        
        assert memory_cache.get("to_delete") is None
        assert memory_cache.get("to_keep") == "value"

    def test_base_cache_interface_raises(self):
        """Base Cache class methods should raise NotImplementedError."""
        cache = Cache()
        with pytest.raises(NotImplementedError):
            cache.get("key")
        with pytest.raises(NotImplementedError):
            cache.set("key", "value")
        with pytest.raises(NotImplementedError):
            cache.delete("key")
        with pytest.raises(NotImplementedError):
            cache.clear()
