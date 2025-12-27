# Data Model Documentation

## Ticket Model

The Ticket model is the central entity in the system.

### Fields

- **ticket_id** (str): Unique identifier for the ticket
- **title** (str): Short title or subject of the ticket
- **description** (str): Detailed description of the issue
- **requester_email** (str): Email address of the person requesting help
- **category** (Category): Category classification
- **priority** (Priority): Priority level
- **status** (TicketStatus): Current status
- **created_at** (datetime): Creation timestamp
- **updated_at** (datetime): Last update timestamp
- **assigned_to** (str, optional): Team or individual assigned
- **tags** (List[str]): List of tags for categorization
- **metadata** (Dict[str, Any]): Additional metadata
- **score** (float, optional): Calculated priority score

### Constraints

- `ticket_id`: Required, must match pattern `^[A-Z0-9-]+$`
- `title`: Required, max 200 characters, cannot be empty
- `description`: Required, cannot be empty
- `requester_email`: Required, must be valid email format
- `category`: Required, must be valid Category enum value
- `priority`: Defaults to MEDIUM if not specified
- `status`: Defaults to NEW if not specified

### Methods

- `update(**kwargs)`: Update fields and set updated_at timestamp
- `to_dict()`: Convert to dictionary representation
- `from_dict(data)`: Create from dictionary representation

## Category Enum

Categories classify tickets by type:

- **TECHNICAL**: Technical support issues
- **BILLING**: Billing and payment issues
- **ACCOUNT**: Account management issues
- **FEATURE**: Feature requests
- **BUG**: Bug reports
- **GENERAL**: General inquiries

## Priority Enum

Priorities indicate urgency:

- **CRITICAL**: Highest priority, immediate attention required
- **HIGH**: High priority, urgent attention needed
- **MEDIUM**: Medium priority, normal processing
- **LOW**: Low priority, can be deferred

Priority weights used in scoring:
- CRITICAL: 10.0
- HIGH: 7.0
- MEDIUM: 4.0
- LOW: 1.0

## TicketStatus Enum

Statuses track ticket lifecycle:

- **NEW**: Newly created, not yet processed
- **TRIAGED**: Processed and categorized
- **ASSIGNED**: Assigned to a team or individual
- **IN_PROGRESS**: Work is actively being done
- **RESOLVED**: Issue resolved, awaiting closure
- **CLOSED**: Ticket closed
- **ESCALATED**: Ticket escalated for higher attention

## Score Model

Scores represent ticket priority calculations:

- **total** (float): Total weighted score
- **components** (Dict[str, float]): Individual component scores
- **normalized** (float, optional): Normalized score (0.0-1.0)

Normalized scores allow comparison across different scoring algorithms.

## RuleMatch Model

Represents a match between a ticket and a rule:

- **rule_id** (str): ID of the matched rule
- **rule_name** (str): Name of the rule
- **matched** (bool): Whether rule matched
- **confidence** (float): Confidence score (0.0-1.0)
- **metadata** (Dict[str, Any]): Additional match metadata

## RoutingResult Model

Result of routing a ticket:

- **ticket** (Ticket): Updated ticket object
- **assigned_to** (str, optional): Assigned team or individual
- **priority** (Priority): Assigned priority
- **category** (Category): Assigned category
- **rule_matched** (str, optional): ID of matched rule
- **confidence** (float): Confidence in routing decision

## AuditLog Model

Audit log entry:

- **log_id** (str): Unique log identifier
- **ticket_id** (str): Related ticket ID
- **action** (str): Action performed
- **actor** (str): Who performed the action
- **timestamp** (datetime): When action occurred
- **changes** (Dict[str, Any]): Changes made
- **metadata** (Dict[str, Any]): Additional metadata

## Storage Formats

### Memory Storage

Tickets stored in memory as Ticket objects in a dictionary keyed by ticket_id.

### File Storage

Tickets stored as JSON files:
- Filename: `{ticket_id}.json`
- Format: JSON with ISO timestamp strings
- Location: `{base_path}/tickets/`

### Cache Storage

Cache entries stored with:
- Key: Generated from attributes
- Value: Cached object
- TTL: Time-to-live in seconds
- Expiration: Calculated from creation time + TTL

## Data Flow

1. **Input**: Raw data (JSON, CSV, text)
2. **Parse**: Convert to dictionary
3. **Validate**: Check constraints
4. **Normalize**: Convert to Ticket model
5. **Score**: Calculate priority score
6. **Route**: Apply routing rules
7. **Store**: Persist to storage backend
8. **Audit**: Log operation

## Validation Rules

### Ticket ID
- Pattern: `^[A-Z0-9-]+$`
- Required: Yes
- Type: String

### Title
- Required: Yes
- Type: String
- Min length: 1
- Max length: 200
- Cannot be empty after trimming

### Description
- Required: Yes
- Type: String
- Min length: 1
- Cannot be empty after trimming

### Email
- Required: Yes
- Type: String
- Pattern: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`

### Category
- Required: Yes
- Type: Category enum
- Valid values: TECHNICAL, BILLING, ACCOUNT, FEATURE, BUG, GENERAL

### Priority
- Required: No (defaults to MEDIUM)
- Type: Priority enum
- Valid values: CRITICAL, HIGH, MEDIUM, LOW

## Serialization

Tickets can be serialized to/from dictionaries:

- `to_dict()`: Convert Ticket to dictionary
- `from_dict(data)`: Create Ticket from dictionary

Dictionary format uses string values for enums and ISO format for timestamps.

## Extensibility

The metadata field allows storing additional data without schema changes:

```python
ticket.metadata["custom_field"] = "value"
ticket.metadata["nested"] = {"key": "value"}
```

This enables integration with external systems and custom workflows.

