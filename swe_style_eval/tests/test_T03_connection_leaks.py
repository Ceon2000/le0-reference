"""T03: Test database connection handling for potential connection leaks."""
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from helpdesk_ai.store.memory_store import MemoryStore
from helpdesk_ai.domain.models import Ticket, Priority, Category


class TestConnectionLeaks:
    """Test storage for thread safety and resource leaks."""

    def test_memory_store_basic_operations(self, memory_store, sample_ticket):
        """Basic CRUD operations should work correctly."""
        memory_store.save(sample_ticket)
        retrieved = memory_store.get(sample_ticket.ticket_id)
        assert retrieved is not None
        assert retrieved.ticket_id == sample_ticket.ticket_id
        
        deleted = memory_store.delete(sample_ticket.ticket_id)
        assert deleted is True
        assert memory_store.get(sample_ticket.ticket_id) is None

    def test_memory_store_concurrent_writes(self, memory_store):
        """Concurrent writes should not cause data corruption."""
        # Bug: MemoryStore uses plain dict without locks
        results = []
        errors = []
        
        def write_ticket(i):
            try:
                ticket = Ticket(
                    ticket_id=f"CONC-{i:04d}",
                    title=f"Concurrent Test {i}",
                    description="Test",
                    requester_email="test@test.com",
                    category=Category.GENERAL,
                )
                memory_store.save(ticket)
                return True
            except Exception as e:
                errors.append(str(e))
                return False
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_ticket, i) for i in range(100)]
            for f in as_completed(futures):
                results.append(f.result())
        
        # All writes should succeed without error
        assert len(errors) == 0, f"Errors during concurrent writes: {errors[:5]}"
        # All tickets should be saved
        assert memory_store.count() == 100, f"Expected 100 tickets, got {memory_store.count()}"

    def test_memory_store_concurrent_read_write(self, memory_store):
        """Concurrent reads and writes should not cause issues."""
        # Pre-populate with some tickets
        for i in range(50):
            ticket = Ticket(
                ticket_id=f"INIT-{i:04d}",
                title=f"Initial {i}",
                description="Test",
                requester_email="test@test.com",
                category=Category.GENERAL,
            )
            memory_store.save(ticket)
        
        read_results = []
        write_results = []
        errors = []
        
        def read_op():
            try:
                return len(memory_store.list_all())
            except Exception as e:
                errors.append(f"read: {e}")
                return -1
        
        def write_op(i):
            try:
                ticket = Ticket(
                    ticket_id=f"NEW-{i:04d}",
                    title=f"New {i}",
                    description="Test",
                    requester_email="test@test.com",
                    category=Category.GENERAL,
                )
                memory_store.save(ticket)
                return True
            except Exception as e:
                errors.append(f"write: {e}")
                return False
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Mix reads and writes
            futures = []
            for i in range(50):
                futures.append(executor.submit(read_op))
                futures.append(executor.submit(write_op, i))
            for f in as_completed(futures):
                f.result()
        
        assert len(errors) == 0, f"Errors: {errors[:5]}"

    def test_memory_store_search_consistency(self, memory_store):
        """Search results should be consistent with store contents."""
        # Add tickets with different categories
        for cat in Category:
            ticket = Ticket(
                ticket_id=f"CAT-{cat.value}",
                title=f"Ticket for {cat.value}",
                description="Test",
                requester_email="test@test.com",
                category=cat,
            )
            memory_store.save(ticket)
        
        # Search should return correct results
        for cat in Category:
            results = memory_store.search(category=cat)
            assert len(results) == 1, f"Expected 1 result for {cat}, got {len(results)}"
            assert results[0].category == cat

    def test_memory_store_clear_releases_resources(self, memory_store, sample_ticket):
        """Clear should release all stored tickets."""
        memory_store.save(sample_ticket)
        assert memory_store.count() == 1
        
        memory_store.clear()
        assert memory_store.count() == 0
        assert memory_store.list_all() == []
