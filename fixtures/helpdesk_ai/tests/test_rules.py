"""
Tests for rule engine and routing.

These tests expose bugs in routing priority handling.
"""

import pytest
from helpdesk_ai.domain.models import Ticket, Category, Priority, TicketStatus
from helpdesk_ai.domain.rules import RuleEngine, Rule


def test_rule_matching():
    """Test basic rule matching."""
    rule_engine = RuleEngine()
    
    rule = Rule(
        rule_id="test_rule",
        name="Test Rule",
        priority=Priority.HIGH,
        condition=lambda t: "test" in t.title.lower(),
    )
    
    rule_engine.add_rule(rule)
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test ticket",
        description="Test description",
        requester_email="test@example.com",
        category=Category.GENERAL,
    )
    
    matches = rule_engine.evaluate(ticket)
    assert len(matches) == 1
    assert matches[0].matched is True


def test_highest_priority_match_bug():
    """
    Test that exposes routing priority bug.
    
    BUG: get_highest_priority_match returns the LAST match after sorting,
    which means LOW priority wins instead of CRITICAL.
    """
    rule_engine = RuleEngine()
    
    # Add rules with different priorities
    rule_engine.add_rule(Rule(
        rule_id="low_priority",
        name="Low Priority Rule",
        priority=Priority.LOW,
        condition=lambda t: True,  # Always matches
    ))
    
    rule_engine.add_rule(Rule(
        rule_id="critical_priority",
        name="Critical Priority Rule",
        priority=Priority.CRITICAL,
        condition=lambda t: True,  # Always matches
    ))
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test ticket",
        description="Test description",
        requester_email="test@example.com",
        category=Category.GENERAL,
    )
    
    # This should return CRITICAL priority rule, but bug returns LOW
    matched_rule = rule_engine.get_highest_priority_match(ticket)
    
    # BUG: This assertion will fail because LOW priority is returned instead of CRITICAL
    assert matched_rule is not None
    assert matched_rule.priority == Priority.CRITICAL, \
        f"Expected CRITICAL priority, got {matched_rule.priority}"


def test_priority_ordering():
    """Test that priority ordering works correctly."""
    rule_engine = RuleEngine()
    
    priorities = [Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.CRITICAL]
    
    for priority in priorities:
        rule_engine.add_rule(Rule(
            rule_id=f"rule_{priority.value}",
            name=f"{priority.value} Rule",
            priority=priority,
            condition=lambda t: True,
        ))
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test ticket",
        description="Test description",
        requester_email="test@example.com",
        category=Category.GENERAL,
    )
    
    matched_rule = rule_engine.get_highest_priority_match(ticket)
    
    # Should get CRITICAL, not LOW
    assert matched_rule.priority == Priority.CRITICAL


def test_multiple_matching_rules():
    """Test behavior with multiple matching rules."""
    rule_engine = RuleEngine()
    
    rule_engine.add_rule(Rule(
        rule_id="billing_rule",
        name="Billing Rule",
        priority=Priority.HIGH,
        condition=lambda t: t.category == Category.BILLING,
    ))
    
    rule_engine.add_rule(Rule(
        rule_id="payment_rule",
        name="Payment Rule",
        priority=Priority.CRITICAL,
        condition=lambda t: "payment" in t.description.lower(),
    ))
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Payment issue",
        description="Unable to process payment",
        requester_email="test@example.com",
        category=Category.BILLING,
    )
    
    # Both rules should match
    matches = rule_engine.get_matching_rules(ticket)
    assert len(matches) == 2
    
    # Highest priority should be CRITICAL
    highest = rule_engine.get_highest_priority_match(ticket)
    assert highest.priority == Priority.CRITICAL

