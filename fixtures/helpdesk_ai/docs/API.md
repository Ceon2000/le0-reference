# API Documentation

## CLI API

### Command Line Interface

```bash
python -m helpdesk_ai.cli <input_file> [output_file]
```

Processes a ticket file and outputs routing results.

**Arguments:**
- `input_file`: Path to input ticket file (JSON, CSV, or text)
- `output_file`: Optional path for output JSON file

**Returns:**
- Exit code 0 on success
- Exit code 1 on error (with error message to stderr)

**Output Format:**
```json
{
  "ticket": {
    "ticket_id": "TKT-20240101-ABC12345",
    "title": "Ticket title",
    "description": "Ticket description",
    "requester_email": "user@example.com",
    "category": "billing",
    "priority": "high",
    "status": "triaged",
    "score": 0.85
  },
  "routing": {
    "assigned_to": "billing-team",
    "priority": "high",
    "category": "billing",
    "rule_matched": "critical_billing",
    "confidence": 1.0
  }
}
```

## Python API

### Domain Models

#### Ticket

```python
from helpdesk_ai.domain.models import Ticket, Category, Priority

ticket = Ticket(
    ticket_id="TKT-20240101-ABC12345",
    title="Payment issue",
    description="Unable to process payment",
    requester_email="user@example.com",
    category=Category.BILLING,
    priority=Priority.HIGH,
)
```

#### TicketStatus Enum

- `NEW`: Newly created ticket
- `TRIAGED`: Ticket has been triaged
- `ASSIGNED`: Ticket assigned to team
- `IN_PROGRESS`: Work in progress
- `RESOLVED`: Ticket resolved
- `CLOSED`: Ticket closed
- `ESCALATED`: Ticket escalated

#### Priority Enum

- `CRITICAL`: Highest priority
- `HIGH`: High priority
- `MEDIUM`: Medium priority
- `LOW`: Low priority

#### Category Enum

- `TECHNICAL`: Technical issues
- `BILLING`: Billing and payment
- `ACCOUNT`: Account management
- `FEATURE`: Feature requests
- `BUG`: Bug reports
- `GENERAL`: General inquiries

### Storage API

#### MemoryStore

```python
from helpdesk_ai.store.memory_store import MemoryStore

store = MemoryStore()
store.save(ticket)
ticket = store.get("TKT-20240101-ABC12345")
tickets = store.list_all()
store.delete("TKT-20240101-ABC12345")
```

#### FileStore

```python
from helpdesk_ai.store.file_store import FileStore

store = FileStore("./data")
store.save(ticket)
ticket = store.get("TKT-20240101-ABC12345")
```

### Triage Service API

```python
from helpdesk_ai.services.triage import TriageService
from helpdesk_ai.cli import create_default_triage_service

triage_service = create_default_triage_service()
result = triage_service.triage(ticket)
```

**Returns:** `RoutingResult` with:
- `ticket`: Updated ticket object
- `assigned_to`: Assigned team or individual
- `priority`: Assigned priority
- `category`: Assigned category
- `rule_matched`: ID of matched rule (if any)
- `confidence`: Confidence score (0.0-1.0)

### Scoring API

```python
from helpdesk_ai.domain.scoring import PriorityScorer, UrgencyScorer, WeightedScorer

priority_scorer = PriorityScorer()
score = priority_scorer.score(ticket)

urgency_scorer = UrgencyScorer()
score = urgency_scorer.score(ticket)

scorer = WeightedScorer(
    scorers={
        "priority": priority_scorer.score,
        "urgency": urgency_scorer.score,
    },
    weights={"priority": 0.6, "urgency": 0.4},
    normalize=True,
)
score = scorer.score(ticket)
```

**Score Object:**
- `total`: Total weighted score
- `components`: Dictionary of component scores
- `normalized`: Normalized score (0.0-1.0) if normalization enabled

### Rule Engine API

```python
from helpdesk_ai.domain.rules import RuleEngine, Rule
from helpdesk_ai.domain.models import Priority, Category

rule_engine = RuleEngine()

rule = Rule(
    rule_id="critical_billing",
    name="Critical Billing Issues",
    priority=Priority.CRITICAL,
    condition=lambda t: t.category == Category.BILLING and "payment" in t.description.lower(),
    target_category=Category.BILLING,
    target_assignee="billing-team",
)

rule_engine.add_rule(rule)
matches = rule_engine.evaluate(ticket)
matching_rule = rule_engine.get_highest_priority_match(ticket)
```

### Escalation Service API

```python
from helpdesk_ai.services.escalation import EscalationService

escalation_service = EscalationService(
    escalation_threshold_hours=24,
    auto_escalate_critical=True,
)

if escalation_service.should_escalate(ticket):
    escalated_ticket = escalation_service.escalate(ticket, reason="Age threshold exceeded")
```

### Audit Service API

```python
from helpdesk_ai.services.audit import AuditService

audit_service = AuditService()
audit_service.log(
    ticket_id="TKT-20240101-ABC12345",
    action="update",
    actor="system",
    changes={"priority": "high"},
)

logs = audit_service.get_logs_for_ticket("TKT-20240101-ABC12345")
```

### Configuration API

```python
from helpdesk_ai.config import Config

config = Config(config_file="./config.json")
store_type = config.get("store_type", "memory")
config.set("cache_enabled", True)
config.save_to_file()
```

### Parser API

```python
from helpdesk_ai.ingest.parsers import JSONParser, CSVParser, TextParser, MultiFormatParser

parser = JSONParser()
data = parser.parse(json_string)

parser = MultiFormatParser()
data = parser.parse(any_format_string)
```

### Validator API

```python
from helpdesk_ai.ingest.validators import TicketValidator

validator = TicketValidator()
errors = validator.validate(data_dict)
if errors:
    for error in errors:
        print(f"{error.field}: {error.message}")
```

### Normalizer API

```python
from helpdesk_ai.ingest.normalize import TicketNormalizer

normalizer = TicketNormalizer()
ticket = normalizer.normalize(parsed_data_dict)
```

## Error Handling

All APIs raise appropriate exceptions:

- `ValidationError`: Data validation failures
- `StorageError`: Storage operation failures
- `RoutingError`: Routing failures
- `ScoringError`: Scoring failures
- `ParsingError`: Parsing failures

Exceptions inherit from `HelpdeskError` base class.

