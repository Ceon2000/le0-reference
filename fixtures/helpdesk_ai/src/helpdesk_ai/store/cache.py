"""
Caching layer for ticket operations.
"""

from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from ..domain.models import Ticket


class Cache:
    """Base cache interface."""
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        raise NotImplementedError
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        raise NotImplementedError
    
    def delete(self, key: str) -> None:
        """Delete value from cache."""
        raise NotImplementedError
    
    def clear(self) -> None:
        """Clear all cache entries."""
        raise NotImplementedError


class CacheEntry:
    """Represents a cache entry with expiration."""
    
    def __init__(self, value: Any, ttl: Optional[int] = None):
        """Initialize cache entry."""
        self.value = value
        self.created_at = datetime.now()
        self.ttl = ttl
        if ttl:
            self.expires_at = self.created_at + timedelta(seconds=ttl)
        else:
            self.expires_at = None
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


class MemoryCache(Cache):
    """In-memory cache implementation."""
    
    def __init__(self, default_ttl: Optional[int] = None):
        """Initialize memory cache."""
        self._entries: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        
        if entry.is_expired():
            del self._entries[key]
            return None
        
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        ttl = ttl or self.default_ttl
        self._entries[key] = CacheEntry(value, ttl)
    
    def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self._entries:
            del self._entries[key]
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._entries.clear()
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """
        Generate cache key from prefix and kwargs.
        
        BUG: Key collision - two different requests can map to the same key.
        When kwargs contain nested dicts or lists, they're converted to string
        which can cause collisions. Also, order of kwargs matters but isn't
        normalized, so same data in different order creates different keys.
        """
        # Convert kwargs to string representation
        # BUG: This doesn't handle nested structures properly
        # BUG: Order of kwargs affects key generation
        parts = [prefix]
        for k, v in sorted(kwargs.items()):
            # BUG: str(dict) or str(list) can create same string for different objects
            parts.append(f"{k}={str(v)}")
        return ":".join(parts)
    
    def cache_ticket(self, ticket: Ticket) -> str:
        """Cache a ticket and return its key."""
        # BUG: This key generation can collide
        # Two tickets with same email and category but different IDs get same key
        key = self._generate_key(
            "ticket",
            email=ticket.requester_email,
            category=ticket.category.value,
            # BUG: ticket_id not included, causing potential collisions
        )
        self.set(key, ticket)
        return key
    
    def get_cached_ticket(self, email: str, category: str) -> Optional[Ticket]:
        """Get cached ticket by email and category."""
        key = self._generate_key("ticket", email=email, category=category)
        return self.get(key)

