"""T02: Test priority scoring algorithm normalization calculations."""
import pytest
from helpdesk_ai.domain.models import Ticket, Priority, Category
from helpdesk_ai.domain.scoring import WeightedScorer, PriorityScorer, UrgencyScorer, CompositeScorer, Score


class TestScoringNormalization:
    """Test scoring normalization for mathematical correctness."""

    def test_weighted_scorer_empty_weights_no_crash(self, sample_ticket):
        """WeightedScorer with empty weights should not crash (ZeroDivisionError bug)."""
        # Bug: If scorers dict is empty, score() will fail
        scorer = WeightedScorer(scorers={}, weights={}, normalize=True)
        # This should not raise ZeroDivisionError
        score = scorer.score(sample_ticket)
        assert isinstance(score, Score)

    def test_weighted_scorer_zero_weight_sum(self, sample_ticket):
        """WeightedScorer with zero-sum weights should handle gracefully."""
        # Bug: Documented - divides by zero when sum of weights is zero
        scorer = WeightedScorer(
            scorers={"test": lambda t: 5.0},
            weights={"test": 0.0},
            normalize=True,
        )
        # Should not raise ZeroDivisionError
        score = scorer.score(sample_ticket)
        assert score.normalized == 0.0 or score.normalized is None

    def test_normalized_score_in_range(self, sample_ticket):
        """Normalized scores should always be in [0, 1]."""
        scorer = WeightedScorer(
            scorers={"a": lambda t: 10.0, "b": lambda t: 5.0},
            weights={"a": 1.0, "b": 1.0},
            normalize=True,
        )
        score = scorer.score(sample_ticket)
        assert 0.0 <= score.normalized <= 1.0, f"Normalized score {score.normalized} out of range"

    def test_priority_scorer_all_priorities(self):
        """PriorityScorer should score all priority levels correctly."""
        scorer = PriorityScorer()
        for priority in Priority:
            ticket = Ticket(
                ticket_id="T1",
                title="Test",
                description="Test",
                requester_email="t@t.com",
                category=Category.GENERAL,
                priority=priority,
            )
            score = scorer.score(ticket)
            assert score.total >= 0
            assert score.normalized is not None

    def test_priority_scorer_monotonicity(self):
        """Higher priority should have higher score."""
        scorer = PriorityScorer()
        priorities = [Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.CRITICAL]
        scores = []
        for priority in priorities:
            ticket = Ticket(
                ticket_id="T1",
                title="Test",
                description="Test",
                requester_email="t@t.com",
                category=Category.GENERAL,
                priority=priority,
            )
            scores.append(scorer.score(ticket).total)
        
        # Each score should be >= previous (monotonic)
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i-1], f"Priority monotonicity violated at {priorities[i]}"

    def test_urgency_scorer_keyword_detection(self):
        """UrgencyScorer should detect urgency keywords."""
        scorer = UrgencyScorer()
        urgent_ticket = Ticket(
            ticket_id="U1",
            title="URGENT: System down emergency",
            description="Critical outage, cannot access system",
            requester_email="u@u.com",
            category=Category.BUG,
        )
        normal_ticket = Ticket(
            ticket_id="N1",
            title="Feature request",
            description="Would like to have dark mode",
            requester_email="n@n.com",
            category=Category.FEATURE,
        )
        urgent_score = scorer.score(urgent_ticket).total
        normal_score = scorer.score(normal_ticket).total
        assert urgent_score > normal_score, "Urgent ticket should score higher"

    def test_composite_scorer_combines_scores(self, sample_ticket):
        """CompositeScorer should combine multiple scorers."""
        priority_scorer = PriorityScorer()
        urgency_scorer = UrgencyScorer()
        composite = CompositeScorer([priority_scorer, urgency_scorer])
        score = composite.score(sample_ticket)
        assert len(score.components) >= 2, "Should have components from both scorers"
