"""Shared pytest fixtures for SWE-bench-style tests."""
import sys
from pathlib import Path
from datetime import datetime
import pytest

# Add fixtures/helpdesk_ai to path for imports
HELPDESK_SRC = Path(__file__).parent.parent.parent / "fixtures" / "helpdesk_ai" / "src"
if str(HELPDESK_SRC) not in sys.path:
    sys.path.insert(0, str(HELPDESK_SRC))


@pytest.fixture
def sample_ticket():
    """Create a sample ticket for testing."""
    from helpdesk_ai.domain.models import Ticket, Priority, Category, TicketStatus
    return Ticket(
        ticket_id="TEST-001",
        title="Test Ticket",
        description="Test description",
        requester_email="test@example.com",
        category=Category.TECHNICAL,
        priority=Priority.MEDIUM,
        status=TicketStatus.NEW,
    )


@pytest.fixture
def critical_ticket():
    """Create a critical priority ticket."""
    from helpdesk_ai.domain.models import Ticket, Priority, Category, TicketStatus
    return Ticket(
        ticket_id="CRIT-001",
        title="Critical Issue",
        description="System down emergency",
        requester_email="urgent@example.com",
        category=Category.BUG,
        priority=Priority.CRITICAL,
        status=TicketStatus.NEW,
    )


@pytest.fixture
def memory_store():
    """Create a clean memory store."""
    from helpdesk_ai.store.memory_store import MemoryStore
    return MemoryStore()


@pytest.fixture
def memory_cache():
    """Create a clean memory cache."""
    from helpdesk_ai.store.cache import MemoryCache
    return MemoryCache(default_ttl=60)


@pytest.fixture
def config(tmp_path):
    """Create a config instance with temp file."""
    from helpdesk_ai.config import Config
    config_file = tmp_path / "config.json"
    return Config(config_file=str(config_file))


@pytest.fixture
def escalation_service():
    """Create an escalation service instance."""
    from helpdesk_ai.services.escalation import EscalationService
    return EscalationService(escalation_threshold_hours=24)


@pytest.fixture
def router():
    """Create a router with default rule engine."""
    from helpdesk_ai.services.routing import Router
    from helpdesk_ai.domain.rules import RuleEngine
    return Router(RuleEngine())


class FakeClock:
    """Fake clock for deterministic time-based tests."""
    def __init__(self, start_time: datetime = None):
        self._now = start_time or datetime(2024, 1, 1, 12, 0, 0)

    def now(self):
        return self._now

    def advance(self, **kwargs):
        from datetime import timedelta
        self._now += timedelta(**kwargs)
        return self._now


@pytest.fixture
def fake_clock():
    """Create a fake clock for time-based tests."""
    return FakeClock()
