# Runbook

## Operations Guide

This runbook provides procedures for common operational tasks.

## Starting the Service

### CLI Mode

```bash
python -m helpdesk_ai.cli input.json output.json
```

### Programmatic Usage

```python
from helpdesk_ai.cli import create_default_triage_service

triage_service = create_default_triage_service()
```

## Configuration

### Environment Variables

Set these environment variables before starting:

```bash
export HELPDESK_STORE_TYPE=file
export HELPDESK_STORE_PATH=/var/lib/helpdesk
export HELPDESK_CACHE_ENABLED=true
export HELPDESK_CACHE_TTL=3600
export HELPDESK_ESCALATION_THRESHOLD=24
export HELPDESK_LOG_LEVEL=INFO
```

### Config File

Create `config.json`:

```json
{
  "store_type": "file",
  "store_path": "/var/lib/helpdesk",
  "cache_enabled": true,
  "cache_ttl": 3600,
  "escalation_threshold_hours": 24,
  "auto_escalate_critical": true,
  "max_ticket_title_length": 200,
  "max_ticket_description_length": 10000,
  "default_priority": "medium",
  "log_level": "INFO"
}
```

## Ticket Processing

### Single Ticket

```python
from helpdesk_ai.domain.models import Ticket, Category, Priority
from helpdesk_ai.services.triage import TriageService
from helpdesk_ai.cli import create_default_triage_service

triage_service = create_default_triage_service()

ticket = Ticket(
    ticket_id="TKT-20240101-ABC12345",
    title="Payment issue",
    description="Unable to process payment",
    requester_email="user@example.com",
    category=Category.BILLING,
    priority=Priority.HIGH,
)

result = triage_service.triage(ticket)
```

### Batch Processing

```python
tickets = [ticket1, ticket2, ticket3]
results = triage_service.batch_triage(tickets)
```

## Storage Management

### Memory Store

```python
from helpdesk_ai.store.memory_store import MemoryStore

store = MemoryStore()
store.save(ticket)
```

### File Store

```python
from helpdesk_ai.store.file_store import FileStore

store = FileStore("./data")
store.save(ticket)
```

### Backup

File store backups:

```bash
tar -czf backup-$(date +%Y%m%d).tar.gz ./data/tickets/
```

### Restore

```bash
tar -xzf backup-20240101.tar.gz
```

## Monitoring

### Check Service Health

```python
from helpdesk_ai.web.handlers import HealthHandler

handler = HealthHandler()
response = handler.get()
```

### View Audit Logs

```python
from helpdesk_ai.services.audit import AuditService

audit_service = AuditService()
logs = audit_service.get_recent_logs(limit=100)
for log in logs:
    print(f"{log.timestamp}: {log.action} on {log.ticket_id}")
```

### Ticket Statistics

```python
from helpdesk_ai.store.memory_store import MemoryStore

store = MemoryStore()
tickets = store.list_all()

by_status = {}
for ticket in tickets:
    status = ticket.status.value
    by_status[status] = by_status.get(status, 0) + 1

print(by_status)
```

## Troubleshooting

### Common Issues

#### Parsing Errors

**Symptom**: "Error parsing input"

**Solution**: Check input format matches expected format (JSON, CSV, or text)

#### Validation Errors

**Symptom**: "Validation errors" with field names

**Solution**: Ensure all required fields are present and valid:
- ticket_id: Must match pattern
- title: Required, max 200 chars
- description: Required, non-empty
- requester_email: Valid email format

#### Storage Errors

**Symptom**: "StorageError" exceptions

**Solution**: 
- Check file permissions for file store
- Ensure directory exists
- Verify disk space

#### Routing Issues

**Symptom**: Tickets not routing correctly

**Solution**:
- Check rule conditions
- Verify rule priority ordering
- Review rule matching logic

#### Scoring Issues

**Symptom**: Unexpected scores

**Solution**:
- Check scorer weights
- Verify normalization logic
- Review component scores

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Tuning

### Caching

Enable caching for repeated operations:

```python
from helpdesk_ai.store.cache import MemoryCache

cache = MemoryCache(default_ttl=3600)
```

### Batch Operations

Use batch methods for multiple tickets:

```python
results = triage_service.batch_triage(tickets)
```

### Storage Selection

- Memory store: Fastest, no persistence
- File store: Slower, persistent

Choose based on requirements.

## Maintenance

### Cleanup Old Tickets

```python
from datetime import datetime, timedelta

cutoff = datetime.now() - timedelta(days=90)
old_tickets = [t for t in store.list_all() if t.created_at < cutoff]
for ticket in old_tickets:
    store.delete(ticket.ticket_id)
```

### Clear Cache

```python
cache.clear()
```

### Archive Audit Logs

```python
old_logs = [l for l in audit_service._logs if l.timestamp < cutoff]
# Export to external system
audit_service.clear()
```

## Scaling Considerations

### Horizontal Scaling

- Stateless design allows multiple instances
- Shared storage backend required
- Consider distributed cache (Redis)

### Vertical Scaling

- Increase cache size
- Optimize scoring algorithms
- Use faster storage backend

### Load Balancing

- Route requests to multiple instances
- Session affinity not required (stateless)
- Health check endpoints available

## Security

### Input Validation

Always validate input:

```python
validator = TicketValidator()
errors = validator.validate(data)
if errors:
    raise ValidationError("Invalid input")
```

### Access Control

Implement authentication/authorization in web layer.

### Data Protection

- Encrypt sensitive data in metadata
- Secure storage backend
- Audit all operations

## Disaster Recovery

### Backup Strategy

1. Regular file store backups
2. Export audit logs
3. Configuration backups

### Recovery Procedures

1. Restore from backup
2. Verify data integrity
3. Resume operations

### Testing

Regularly test backup/restore procedures.

