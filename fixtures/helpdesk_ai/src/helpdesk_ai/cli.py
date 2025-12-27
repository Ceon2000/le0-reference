"""
Command-line interface for helpdesk service.
"""

import sys
import json
from pathlib import Path
from typing import Optional

from .domain.models import Ticket, Category, Priority
from .ingest.parsers import JSONParser, TextParser, MultiFormatParser
from .ingest.normalize import TicketNormalizer
from .ingest.validators import TicketValidator
from .store.memory_store import MemoryStore
from .store.file_store import FileStore
from .services.triage import TriageService
from .services.routing import Router
from .services.escalation import EscalationService
from .domain.rules import RuleEngine, Rule
from .domain.scoring import WeightedScorer, PriorityScorer, UrgencyScorer
from .config import Config


def create_default_triage_service() -> TriageService:
    """Create a default triage service with standard configuration."""
    # Create scorers
    priority_scorer = PriorityScorer()
    urgency_scorer = UrgencyScorer()
    
    # Create weighted scorer
    scorer = WeightedScorer(
        scorers={
            "priority": priority_scorer.score,
            "urgency": urgency_scorer.score,
        },
        weights={
            "priority": 0.6,
            "urgency": 0.4,
        },
        normalize=True,
    )
    
    # Create rule engine
    rule_engine = RuleEngine()
    
    # Add some default rules
    rule_engine.add_rule(Rule(
        rule_id="critical_billing",
        name="Critical Billing Issues",
        priority=Priority.CRITICAL,
        condition=lambda t: t.category == Category.BILLING and "payment" in t.description.lower(),
        target_category=Category.BILLING,
        target_assignee="billing-team",
    ))
    
    rule_engine.add_rule(Rule(
        rule_id="account_lockout",
        name="Account Lockout",
        priority=Priority.HIGH,
        condition=lambda t: "lock" in t.title.lower() or "lockout" in t.description.lower(),
        target_category=Category.ACCOUNT,
        target_assignee="account-team",
    ))
    
    # Create router
    router = Router(rule_engine)
    
    # Create triage service
    return TriageService(scorer=scorer, router=router)


def process_ticket_file(input_file: str, output_file: Optional[str] = None) -> None:
    """Process a ticket file and output results."""
    # Read input
    with open(input_file, "r") as f:
        content = f.read()
    
    # Parse
    parser = MultiFormatParser()
    try:
        data = parser.parse(content)
    except Exception as e:
        print(f"Error parsing input: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Validate
    validator = TicketValidator()
    errors = validator.validate(data)
    if errors:
        print("Validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error.field}: {error.message}", file=sys.stderr)
        sys.exit(1)
    
    # Normalize
    normalizer = TicketNormalizer()
    try:
        ticket = normalizer.normalize(data)
    except Exception as e:
        print(f"Error normalizing ticket: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Triage
    triage_service = create_default_triage_service()
    result = triage_service.triage(ticket)
    
    # Output
    output_data = {
        "ticket": ticket.to_dict(),
        "routing": {
            "assigned_to": result.assigned_to,
            "priority": result.priority.value,
            "category": result.category.value,
            "rule_matched": result.rule_matched,
            "confidence": result.confidence,
        },
    }
    
    if output_file:
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)
    else:
        print(json.dumps(output_data, indent=2))


def main() -> None:
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: helpdesk-ai <input_file> [output_file]", file=sys.stderr)
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(input_file).exists():
        print(f"Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)
    
    process_ticket_file(input_file, output_file)


if __name__ == "__main__":
    main()

