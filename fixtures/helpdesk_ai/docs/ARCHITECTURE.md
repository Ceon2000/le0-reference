# Architecture Documentation

## System Overview

The Helpdesk AI Triage Service is designed as a modular system with clear separation of concerns. The architecture follows a layered approach with domain models at the core, surrounded by service layers, data access layers, and presentation layers.

## Component Layers

### Domain Layer

The domain layer contains core business logic and models:

- **Models**: Ticket, TicketStatus, Priority, Category enums and data classes
- **Rules**: Rule engine for matching tickets against routing rules
- **Scoring**: Scoring algorithms for ticket prioritization

This layer is independent of infrastructure and can be tested in isolation.

### Ingest Layer

The ingest layer handles data input and transformation:

- **Parsers**: Convert raw input (JSON, CSV, text) into structured data
- **Normalizers**: Transform parsed data into domain models
- **Validators**: Ensure data quality and completeness

This layer provides a clean interface for accepting tickets from various sources.

### Store Layer

The store layer abstracts data persistence:

- **MemoryStore**: In-memory storage for development and testing
- **FileStore**: File-based JSON storage for simple persistence
- **Cache**: Caching layer for performance optimization

Storage implementations are swappable, allowing different backends without changing business logic.

### Service Layer

The service layer orchestrates business operations:

- **TriageService**: Coordinates scoring and routing
- **Router**: Applies routing rules to assign tickets
- **EscalationService**: Handles automatic escalations
- **AuditService**: Tracks all operations

Services compose domain logic and storage to provide high-level operations.

### Presentation Layer

The presentation layer provides interfaces for users:

- **CLI**: Command-line interface for batch processing
- **Web**: Minimal web interface skeleton

These layers are thin wrappers around service methods.

## Data Flow

1. **Ingestion**: Raw ticket data enters through parsers
2. **Validation**: Validators ensure data quality
3. **Normalization**: Normalizers convert to domain models
4. **Scoring**: Scorers calculate priority scores
5. **Routing**: Router applies rules to assign tickets
6. **Storage**: Tickets are persisted to storage backend
7. **Audit**: Operations are logged for tracking

## Design Patterns

### Strategy Pattern

Scoring uses the strategy pattern - different scorers can be plugged in:
- PriorityScorer
- UrgencyScorer
- WeightedScorer (composite)

### Factory Pattern

Service creation uses factory functions:
- `create_default_triage_service()` creates configured service instances

### Repository Pattern

Storage backends implement repository pattern:
- Abstract interface (implicit)
- Multiple implementations (MemoryStore, FileStore)

## Extension Points

The system is designed for extension:

1. **New Parsers**: Implement Parser interface
2. **New Scorers**: Implement Scorer interface
3. **New Storage**: Implement storage interface
4. **New Rules**: Add Rule instances to RuleEngine
5. **New Services**: Compose existing components

## Performance Considerations

- Caching layer reduces repeated operations
- In-memory storage for high-throughput scenarios
- File storage for persistence without database overhead
- Batch operations for processing multiple tickets

## Error Handling

Errors are handled at appropriate layers:

- Parsing errors: Caught and reported during ingestion
- Validation errors: Collected and returned as list
- Storage errors: Wrapped in StorageError exceptions
- Business logic errors: Domain-specific exceptions

## Configuration Management

Configuration supports multiple sources:

1. Default values (hardcoded)
2. Config file (JSON)
3. Environment variables (highest precedence)

This allows flexible deployment across environments.

## Testing Strategy

- Unit tests for individual components
- Integration tests for service composition
- No external dependencies (no network, no database)
- Mock-friendly interfaces

## Future Enhancements

Potential areas for extension:

- Database storage backend
- Real-time web interface
- Advanced scoring algorithms
- Machine learning integration
- Multi-tenant support
- Advanced rule conditions

