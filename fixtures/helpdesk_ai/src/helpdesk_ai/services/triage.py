"""
Triage service for processing and scoring tickets.
"""

from typing import List, Optional
from ..domain.models import Ticket
from ..domain.scoring import Scorer, Score
from ..domain.rules import RuleEngine
from .routing import Router, RoutingResult


class TriageService:
    """Service for triaging tickets."""
    
    def __init__(
        self,
        scorer: Scorer,
        router: Router,
        rule_engine: Optional[RuleEngine] = None,
    ):
        """Initialize triage service."""
        self.scorer = scorer
        self.router = router
        self.rule_engine = rule_engine or Router.rule_engine if hasattr(Router, 'rule_engine') else None
    
    def triage(self, ticket: Ticket) -> RoutingResult:
        """Triage a single ticket."""
        # Score the ticket
        score = self.scorer.score(ticket)
        ticket.score = score.normalized if score.normalized is not None else score.total
        
        # Route the ticket
        routing_result = self.router.route(ticket)
        
        return routing_result
    
    def batch_triage(self, tickets: List[Ticket]) -> List[RoutingResult]:
        """Triage multiple tickets."""
        results = []
        for ticket in tickets:
            result = self.triage(ticket)
            results.append(result)
        return results
    
    def get_score(self, ticket: Ticket) -> Score:
        """Get score for a ticket without routing."""
        return self.scorer.score(ticket)

