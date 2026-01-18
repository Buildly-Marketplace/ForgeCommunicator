"""
Simple in-memory rate limiter for auth endpoints.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock

from app.settings import settings


@dataclass
class RateLimitEntry:
    """Rate limit entry for tracking requests."""
    
    requests: list[float] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = 60
        self._entries: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
    
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed for the given key."""
        entry = self._entries[key]
        now = time.time()
        window_start = now - self.window_seconds
        
        with entry.lock:
            # Remove old requests outside the window
            entry.requests = [t for t in entry.requests if t > window_start]
            
            # Check if under limit
            if len(entry.requests) < self.requests_per_minute:
                entry.requests.append(now)
                return True
            
            return False
    
    def remaining(self, key: str) -> int:
        """Get remaining requests for the key."""
        entry = self._entries[key]
        now = time.time()
        window_start = now - self.window_seconds
        
        with entry.lock:
            entry.requests = [t for t in entry.requests if t > window_start]
            return max(0, self.requests_per_minute - len(entry.requests))
    
    def reset_time(self, key: str) -> float:
        """Get time until rate limit resets."""
        entry = self._entries[key]
        
        with entry.lock:
            if not entry.requests:
                return 0
            oldest = min(entry.requests)
            return max(0, oldest + self.window_seconds - time.time())


# Global rate limiters
auth_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_auth_per_minute)
api_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limit_api_per_minute)
