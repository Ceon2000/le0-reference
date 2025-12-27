"""
Tests for scoring system.

These tests expose bugs in scoring normalization.
"""

import pytest
from helpdesk_ai.domain.models import Ticket, Category, Priority
from helpdesk_ai.domain.scoring import WeightedScorer, PriorityScorer, UrgencyScorer, Score


def test_priority_scorer():
    """Test priority-based scoring."""
    scorer = PriorityScorer()
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test ticket",
        description="Test description",
        requester_email="test@example.com",
        category=Category.GENERAL,
        priority=Priority.CRITICAL,
    )
    
    score = scorer.score(ticket)
    assert score.total == 10.0
    assert score.normalized == 1.0


def test_weighted_scorer_normalization():
    """Test weighted scorer with normalization."""
    def scorer1(ticket):
        return 5.0
    
    def scorer2(ticket):
        return 10.0
    
    scorer = WeightedScorer(
        scorers={"s1": scorer1, "s2": scorer2},
        weights={"s1": 0.6, "s2": 0.4},
        normalize=True,
    )
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test ticket",
        description="Test description",
        requester_email="test@example.com",
        category=Category.GENERAL,
    )
    
    score = scorer.score(ticket)
    # Weighted sum: 5.0 * 0.6 + 10.0 * 0.4 = 3.0 + 4.0 = 7.0
    # Normalized: 7.0 / (0.6 + 0.4) = 7.0 / 1.0 = 7.0
    assert score.total == 7.0
    assert score.normalized == 7.0


def test_weighted_scorer_zero_weights_bug():
    """
    Test that exposes divide-by-zero bug in normalization.
    
    BUG: When sum of weights is zero, normalization divides by zero.
    """
    def scorer1(ticket):
        return 5.0
    
    scorer = WeightedScorer(
        scorers={"s1": scorer1},
        weights={"s1": 0.0},  # Zero weight
        normalize=True,
    )
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test ticket",
        description="Test description",
        requester_email="test@example.com",
        category=Category.GENERAL,
    )
    
    # BUG: This will cause divide-by-zero or return incorrect normalized value
    score = scorer.score(ticket)
    
    # Should handle zero weights gracefully
    assert score.normalized is not None
    assert not (isinstance(score.normalized, float) and (score.normalized != score.normalized))  # Not NaN


def test_weighted_scorer_empty_weights_bug():
    """
    Test that exposes bug with empty weights dictionary.
    
    BUG: If weights dict is empty but scorers exist, normalization fails.
    """
    def scorer1(ticket):
        return 5.0
    
    scorer = WeightedScorer(
        scorers={"s1": scorer1},
        weights={},  # Empty weights
        normalize=True,
    )
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test ticket",
        description="Test description",
        requester_email="test@example.com",
        category=Category.GENERAL,
    )
    
    # BUG: This may fail or return incorrect values
    score = scorer.score(ticket)
    
    # Should handle empty weights - either use default weights or skip normalization
    assert score.total is not None
    # Normalized should be handled gracefully
    if score.normalized is not None:
        assert isinstance(score.normalized, float)


def test_weighted_scorer_mismatched_weights():
    """Test scorer with mismatched weights."""
    def scorer1(ticket):
        return 5.0
    
    def scorer2(ticket):
        return 10.0
    
    # Weights only for scorer1
    scorer = WeightedScorer(
        scorers={"s1": scorer1, "s2": scorer2},
        weights={"s1": 0.6},  # Missing weight for s2
        normalize=True,
    )
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Test ticket",
        description="Test description",
        requester_email="test@example.com",
        category=Category.GENERAL,
    )
    
    score = scorer.score(ticket)
    # s1: 5.0 * 0.6 = 3.0
    # s2: 10.0 * 1.0 (default) = 10.0
    # Total: 13.0
    # Normalized: 13.0 / (0.6 + 1.0) = 13.0 / 1.6 = 8.125
    assert score.total == 13.0
    assert abs(score.normalized - 8.125) < 0.01


def test_urgency_scorer():
    """Test urgency keyword scoring."""
    scorer = UrgencyScorer()
    
    ticket = Ticket(
        ticket_id="TKT-001",
        title="Urgent: System down",
        description="Critical error occurred",
        requester_email="test@example.com",
        category=Category.GENERAL,
    )
    
    score = scorer.score(ticket)
    # Should find "urgent" and "critical" keywords
    assert score.total > 0
    assert score.normalized is not None

