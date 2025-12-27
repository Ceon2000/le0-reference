"""
Scoring system for ticket prioritization and routing.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from .models import Ticket, Priority


@dataclass
class Score:
    """Represents a score with components."""
    
    total: float
    components: Dict[str, float]
    normalized: Optional[float] = None
    
    def __repr__(self) -> str:
        return f"Score(total={self.total:.2f}, normalized={self.normalized:.2f if self.normalized else None})"


class Scorer:
    """Base scorer interface."""
    
    def score(self, ticket: Ticket) -> Score:
        """Calculate score for a ticket."""
        raise NotImplementedError


class WeightedScorer(Scorer):
    """
    Scorer that combines multiple scoring functions with weights.
    
    BUG: Normalization can divide by zero when sum of weights is zero.
    Also, if weights dict is empty, normalization fails silently.
    """
    
    def __init__(
        self,
        scorers: Dict[str, Callable[[Ticket], float]],
        weights: Optional[Dict[str, float]] = None,
        normalize: bool = True,
    ):
        """
        Initialize weighted scorer.
        
        Args:
            scorers: Dictionary mapping scorer names to scoring functions
            weights: Optional weights for each scorer (defaults to equal weights)
            normalize: Whether to normalize the final score to [0, 1]
        """
        self.scorers = scorers
        self.weights = weights or {name: 1.0 for name in scorers.keys()}
        self.normalize = normalize
    
    def score(self, ticket: Ticket) -> Score:
        """Calculate weighted score for a ticket."""
        components = {}
        weighted_sum = 0.0
        
        for name, scorer_func in self.scorers.items():
            component_score = scorer_func(ticket)
            weight = self.weights.get(name, 1.0)
            components[name] = component_score
            weighted_sum += component_score * weight
        
        # BUG: If sum of weights is zero, normalization divides by zero
        # Also, if weights dict is empty, this will fail
        if self.normalize:
            weight_sum = sum(self.weights.values())
            # BUG: No check for weight_sum == 0
            normalized = weighted_sum / weight_sum if weight_sum > 0 else 0.0
        else:
            normalized = None
        
        return Score(
            total=weighted_sum,
            components=components,
            normalized=normalized,
        )


class PriorityScorer(Scorer):
    """Scorer based on ticket priority."""
    
    PRIORITY_WEIGHTS = {
        Priority.CRITICAL: 10.0,
        Priority.HIGH: 7.0,
        Priority.MEDIUM: 4.0,
        Priority.LOW: 1.0,
    }
    
    def score(self, ticket: Ticket) -> Score:
        """Score ticket based on priority."""
        priority_score = self.PRIORITY_WEIGHTS.get(ticket.priority, 0.0)
        return Score(
            total=priority_score,
            components={"priority": priority_score},
            normalized=priority_score / 10.0,
        )


class UrgencyScorer(Scorer):
    """Scorer based on ticket urgency indicators."""
    
    def __init__(self, urgency_keywords: Optional[List[str]] = None):
        """Initialize with optional urgency keywords."""
        self.urgency_keywords = urgency_keywords or [
            "urgent", "critical", "down", "broken", "emergency",
            "outage", "cannot", "unable", "failed", "error",
        ]
    
    def score(self, ticket: Ticket) -> Score:
        """Score ticket based on urgency keywords in title/description."""
        text = (ticket.title + " " + ticket.description).lower()
        matches = sum(1 for keyword in self.urgency_keywords if keyword in text)
        urgency_score = min(matches * 2.0, 10.0)  # Cap at 10.0
        
        return Score(
            total=urgency_score,
            components={"urgency": urgency_score},
            normalized=urgency_score / 10.0,
        )


class CompositeScorer(Scorer):
    """Composite scorer combining multiple scorers."""
    
    def __init__(self, scorers: List[Scorer], weights: Optional[List[float]] = None):
        """Initialize composite scorer."""
        self.scorers = scorers
        self.weights = weights or [1.0] * len(scorers)
        if len(self.weights) != len(self.scorers):
            self.weights = [1.0] * len(self.scorers)
    
    def score(self, ticket: Ticket) -> Score:
        """Calculate composite score."""
        all_components = {}
        weighted_sum = 0.0
        
        for i, scorer in enumerate(self.scorers):
            score_result = scorer.score(ticket)
            weight = self.weights[i] if i < len(self.weights) else 1.0
            
            for comp_name, comp_value in score_result.components.items():
                all_components[f"{scorer.__class__.__name__}.{comp_name}"] = comp_value
            
            weighted_sum += score_result.total * weight
        
        total_weight = sum(self.weights)
        normalized = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        return Score(
            total=weighted_sum,
            components=all_components,
            normalized=normalized,
        )

