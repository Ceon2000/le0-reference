"""
Rule engine for matching tickets against routing rules.
"""

from dataclasses import dataclass
from typing import List, Optional, Callable, Dict, Any
from .models import Ticket, Priority, Category


@dataclass
class RuleMatch:
    """Represents a match between a ticket and a rule."""
    
    rule_id: str
    rule_name: str
    matched: bool
    confidence: float
    metadata: Dict[str, Any] = None


@dataclass
class Rule:
    """A routing rule that can match tickets."""
    
    rule_id: str
    name: str
    priority: Priority
    condition: Callable[[Ticket], bool]
    target_category: Optional[Category] = None
    target_assignee: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def matches(self, ticket: Ticket) -> RuleMatch:
        """Check if this rule matches the given ticket."""
        try:
            matched = self.condition(ticket)
            confidence = 1.0 if matched else 0.0
            return RuleMatch(
                rule_id=self.rule_id,
                rule_name=self.name,
                matched=matched,
                confidence=confidence,
                metadata=self.metadata or {},
            )
        except Exception as e:
            return RuleMatch(
                rule_id=self.rule_id,
                rule_name=self.name,
                matched=False,
                confidence=0.0,
                metadata={"error": str(e)},
            )


class RuleEngine:
    """Engine for evaluating rules against tickets."""
    
    def __init__(self, rules: Optional[List[Rule]] = None):
        """Initialize rule engine with optional initial rules."""
        self.rules: List[Rule] = rules or []
    
    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self.rules.append(rule)
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID. Returns True if removed."""
        initial_len = len(self.rules)
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        return len(self.rules) < initial_len
    
    def evaluate(self, ticket: Ticket) -> List[RuleMatch]:
        """Evaluate all rules against a ticket."""
        matches = []
        for rule in self.rules:
            match = rule.matches(ticket)
            matches.append(match)
        return matches
    
    def get_matching_rules(self, ticket: Ticket) -> List[Rule]:
        """Get all rules that match the ticket."""
        matches = self.evaluate(ticket)
        matching_rules = []
        for match in matches:
            if match.matched:
                rule = next(r for r in self.rules if r.rule_id == match.rule_id)
                matching_rules.append(rule)
        return matching_rules
    
    def get_highest_priority_match(self, ticket: Ticket) -> Optional[Rule]:
        """
        Get the highest priority rule that matches the ticket.
        
        BUG: Priority ordering is inverted - CRITICAL is treated as lowest priority.
        Should use priority.value ordering or explicit priority enum comparison.
        """
        matches = self.get_matching_rules(ticket)
        if not matches:
            return None
        
        # BUG: This comparison is inverted
        # CRITICAL should be highest, but this treats it as lowest
        priority_order = {
            Priority.CRITICAL: 1,
            Priority.HIGH: 2,
            Priority.MEDIUM: 3,
            Priority.LOW: 4,
        }
        
        # Sort by priority value (lower number = higher priority)
        # But the mapping above is correct, so the bug is in the comparison
        matches.sort(key=lambda r: priority_order.get(r.priority, 99))
        
        # Actually, wait - the bug is that we're returning the LAST one after sorting
        # ascending, which means LOW priority wins. Should return FIRST.
        return matches[-1] if matches else None

