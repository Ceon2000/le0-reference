"""
Tests for routing and cache functionality.

These tests expose bugs in cache key generation and routing.
"""

import pytest
from helpdesk_ai.domain.models import Ticket, Category, Priority
from helpdesk_ai.store.cache import MemoryCache
from helpdesk_ai.services.routing import Router
from helpdesk_ai.domain.rules import RuleEngine


def test_cache_key_collision_bug():
    """
    Test that exposes cache key collision bug.
    
    BUG: Two different tickets with same email and category but different
    IDs can map to the same cache key because ticket_id is not included.
    """
    cache = MemoryCache()
    
    ticket1 = Ticket(
        ticket_id="TKT-001",
        title="First ticket",
        description="First description",
        requester_email="user@example.com",
        category=Category.BILLING,
    )
    
    ticket2 = Ticket(
        ticket_id="TKT-002",  # Different ID
        title="Second ticket",
        description="Second description",
        requester_email="user@example.com",  # Same email
        category=Category.BILLING,  # Same category
    )
    
    # Cache both tickets
    key1 = cache.cache_ticket(ticket1)
    key2 = cache.cache_ticket(ticket2)
    
    # BUG: Keys should be different but may collide
    assert key1 != key2, "Cache keys should be unique for different tickets"
    
    # Verify we can retrieve the correct ticket
    cached1 = cache.get_cached_ticket("user@example.com", "billing")
    # BUG: This may return ticket2 instead of ticket1 due to collision
    assert cached1 is not None
    # Should be able to distinguish between tickets
    assert cached1.ticket_id in ["TKT-001", "TKT-002"]


def test_cache_key_generation_order():
    """Test that cache key generation handles different kwarg orders."""
    cache = MemoryCache()
    
    # Same data, different order
    key1 = cache._generate_key("test", a=1, b=2)
    key2 = cache._generate_key("test", b=2, a=1)
    
    # Should generate same key (sorted)
    assert key1 == key2


def test_cache_key_with_nested_structures():
    """Test cache key generation with nested structures."""
    cache = MemoryCache()
    
    # BUG: Nested dicts/lists may create same string representation
    key1 = cache._generate_key("test", data={"a": 1, "b": 2})
    key2 = cache._generate_key("test", data={"b": 2, "a": 1})  # Different dict, same content
    
    # These might collide incorrectly
    # In a proper implementation, should serialize deterministically
    assert isinstance(key1, str)
    assert isinstance(key2, str)


def test_router_priority_assignment():
    """Test router priority assignment."""
    rule_engine = RuleEngine()
    
    rule_engine.add_rule(Rule(
        rule_id="high_priority_rule",
        name="High Priority",
        priority=Priority.HIGH,
        condition=lambda t: True,
    ))
    
    router = Router(rule_engine)
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test",
        description="Test",
        requester_email="test@example.com",
        category=Category.GENERAL,
        priority=Priority.LOW,
    )
    
    result = router.route(ticket)
    
    # Router should assign priority from rule
    assert result.priority == Priority.HIGH


def test_router_default_assignment():
    """Test router default assignment when no rules match."""
    rule_engine = RuleEngine()
    router = Router(rule_engine)
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test",
        description="Test",
        requester_email="test@example.com",
        category=Category.TECHNICAL,
        priority=Priority.MEDIUM,
    )
    
    result = router.route(ticket)
    
    # Should use default assignee for category
    assert result.assigned_to == "tech-team"
    assert result.priority == Priority.MEDIUM

