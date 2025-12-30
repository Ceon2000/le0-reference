"""
T02: Scoring Normalization
Tests for priority scoring normalization and zero-division safety.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fixtures" / "helpdesk_ai" / "src"))

try:
    from helpdesk_ai.domain.scoring import WeightedScorer, PriorityScorer, Score
    from helpdesk_ai.domain.models import Ticket, Priority, Category
except ImportError as e:
    pytest.skip(f"Cannot import helpdesk_ai: {e}", allow_module_level=True)


class TestT02Scoring:
    """T02: Scoring normalization tests."""
    
    def _create_test_ticket(self):
        return Ticket(
            ticket_id="TKT-SCORE-001",
            title="Test ticket",
            description="Test description",
            requester_email="test@example.com",
            category=Category.GENERAL,
            priority=Priority.MEDIUM,
        )
    
    def test_zero_weight_normalization(self):
        """Normalization should not divide by zero when weights sum to zero."""
        def always_one(ticket):
            return 1.0
        
        # This is the BUG case - weights that sum to zero
        scorer = WeightedScorer(
            scorers={"test": always_one},
            weights={"test": 0.0},  # Zero weight!
            normalize=True,
        )
        
        ticket = self._create_test_ticket()
        
        # Should not raise ZeroDivisionError
        try:
            score = scorer.score(ticket)
            # If it handles zero correctly, normalized should be 0.0
            assert score.normalized == 0.0, "Should handle zero weights gracefully"
        except ZeroDivisionError:
            pytest.fail("Scorer raised ZeroDivisionError on zero weights")
    
    def test_empty_weights_handling(self):
        """Scorer should handle empty scorers dict safely."""
        scorer = WeightedScorer(
            scorers={},  # Empty!
            weights={},
            normalize=True,
        )
        
        ticket = self._create_test_ticket()
        
        # Should not raise
        score = scorer.score(ticket)
        assert score.total == 0.0, "Empty scorers should produce zero score"
    
    def test_normalized_range(self):
        """Normalized scores should be in [0, 1] range."""
        priority_scorer = PriorityScorer()
        ticket = self._create_test_ticket()
        
        score = priority_scorer.score(ticket)
        
        assert score.normalized is not None, "Normalized should not be None"
        assert 0.0 <= score.normalized <= 1.0, f"Normalized {score.normalized} not in [0, 1]"
