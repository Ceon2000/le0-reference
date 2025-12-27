"""
Routing service for assigning tickets to appropriate handlers.
"""

from dataclasses import dataclass
from typing import Optional, List
from ..domain.models import Ticket, Priority, Category
from ..domain.rules import RuleEngine, Rule


@dataclass
class RoutingResult:
    """Result of routing a ticket."""
    
    ticket: Ticket
    assigned_to: Optional[str]
    priority: Priority
    category: Category
    rule_matched: Optional[str]
    confidence: float


class Router:
    """Router for assigning tickets to handlers."""
    
    def __init__(self, rule_engine: RuleEngine):
        """Initialize router with rule engine."""
        self.rule_engine = rule_engine
        self.default_assignees = {
            Category.TECHNICAL: "tech-team",
            Category.BILLING: "billing-team",
            Category.ACCOUNT: "account-team",
            Category.FEATURE: "product-team",
            Category.BUG: "engineering-team",
            Category.GENERAL: "support-team",
        }
    
    def route(self, ticket: Ticket) -> RoutingResult:
        """Route a ticket to appropriate handler."""
        # Find matching rule
        matching_rule = self.rule_engine.get_highest_priority_match(ticket)
        
        if matching_rule:
            # Use rule's assignment if available
            assigned_to = matching_rule.target_assignee or self.default_assignees.get(ticket.category)
            priority = matching_rule.priority
            category = matching_rule.target_category or ticket.category
            rule_matched = matching_rule.rule_id
            confidence = 1.0
        else:
            # Default routing
            assigned_to = self.default_assignees.get(ticket.category)
            priority = ticket.priority
            category = ticket.category
            rule_matched = None
            confidence = 0.5
        
        # Update ticket with routing results
        ticket.update(
            assigned_to=assigned_to,
            priority=priority,
            category=category,
        )
        
        return RoutingResult(
            ticket=ticket,
            assigned_to=assigned_to,
            priority=priority,
            category=category,
            rule_matched=rule_matched,
            confidence=confidence,
        )
    
    def batch_route(self, tickets: List[Ticket]) -> List[RoutingResult]:
        """Route multiple tickets."""
        return [self.route(ticket) for ticket in tickets]

