# Helpdesk AI Triage Service

A helpdesk ticket triage and routing service that uses rule-based scoring and priority assignment to automatically route tickets to appropriate teams.

## Overview

The Helpdesk AI service processes incoming tickets, scores them based on priority and urgency indicators, matches them against routing rules, and assigns them to appropriate teams. The system includes components for data ingestion, validation, normalization, storage, caching, routing, triage, and escalation.

## Architecture

The service is organized into several key modules:

- **Domain**: Core business logic including ticket models, rule engine, and scoring system
- **Ingest**: Data parsing, normalization, and validation
- **Store**: Storage backends (memory and file-based) with caching
- **Services**: Triage, routing, escalation, and audit services
- **Utils**: Utility functions for text processing, time handling, and ID generation
- **Web**: Minimal web interface skeleton
- **CLI**: Command-line interface for processing tickets

## Key Features

- Multi-format ticket parsing (JSON, CSV, plain text)
- Rule-based routing with priority matching
- Weighted scoring system for ticket prioritization
- Automatic escalation based on age and priority
- Audit logging for all ticket operations
- Configurable storage backends
- Caching layer for performance optimization

## Usage

### CLI Usage

Process a ticket file:

```bash
python -m helpdesk_ai.cli input.json output.json
```

### Programmatic Usage

```python
from helpdesk_ai.domain.models import Ticket, Category, Priority
from helpdesk_ai.services.triage import TriageService
from helpdesk_ai.cli import create_default_triage_service

# Create triage service
triage_service = create_default_triage_service()

# Create a ticket
ticket = Ticket(
    ticket_id="TKT-20240101-ABC12345",
    title="Payment issue",
    description="Unable to process payment",
    requester_email="user@example.com",
    category=Category.BILLING,
    priority=Priority.HIGH,
)

# Triage the ticket
result = triage_service.triage(ticket)
print(f"Assigned to: {result.assigned_to}")
print(f"Priority: {result.priority}")
```

## Configuration

Configuration can be provided via environment variables or a config file:

- `HELPDESK_STORE_TYPE`: Storage backend type (memory or file)
- `HELPDESK_STORE_PATH`: Path for file-based storage
- `HELPDESK_CACHE_ENABLED`: Enable/disable caching
- `HELPDESK_CACHE_TTL`: Cache TTL in seconds
- `HELPDESK_ESCALATION_THRESHOLD`: Hours before auto-escalation
- `HELPDESK_LOG_LEVEL`: Logging level

## Testing

Run tests with pytest:

```bash
pytest tests/
```

## Data Model

Tickets contain the following key fields:

- `ticket_id`: Unique identifier
- `title`: Ticket title/subject
- `description`: Detailed description
- `requester_email`: Requester's email address
- `category`: Ticket category (technical, billing, account, etc.)
- `priority`: Priority level (critical, high, medium, low)
- `status`: Current status (new, triaged, assigned, etc.)
- `assigned_to`: Assigned team or individual
- `tags`: List of tags
- `metadata`: Additional metadata dictionary
- `score`: Calculated priority score

## Routing Rules

Routing rules match tickets based on conditions and assign them to appropriate teams. Rules have:

- `rule_id`: Unique rule identifier
- `name`: Human-readable rule name
- `priority`: Priority level for matching tickets
- `condition`: Function that determines if rule matches
- `target_category`: Category to assign
- `target_assignee`: Team or individual to assign to

## Scoring

The scoring system combines multiple factors:

- Priority-based scoring (critical=10, high=7, medium=4, low=1)
- Urgency keyword matching in title/description
- Custom weighted combinations

Scores are normalized to 0-1 range for consistent comparison.

## Storage

Two storage backends are available:

- **MemoryStore**: In-memory storage for testing and development
- **FileStore**: File-based JSON storage for persistence

Both support CRUD operations, search, and listing.

## Caching

The caching layer provides:

- TTL-based expiration
- Key-based lookups
- Automatic cleanup of expired entries

Cache keys are generated from ticket attributes for efficient lookups.

## Escalation

Automatic escalation occurs when:

- Critical priority tickets remain unresolved
- Tickets exceed age threshold (default 24 hours)

Escalated tickets have priority increased and status set to ESCALATED.

## Audit Logging

All ticket operations are logged with:

- Action type
- Actor (who performed the action)
- Timestamp
- Changes made
- Additional metadata

Audit logs can be queried by ticket ID, actor, or time range.

