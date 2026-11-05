"""FreightGuard In-Memory Rate Limiter
Prevents automated spam, brute-force requests, and settlement endpoint abuse.
"""
from typing import Dict, List
import time
from fastapi import Request, HTTPException, status

class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter based on client IP or user identity."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.history: Dict[str, List[float]] = {}

    def check(self, request: Request, identifier: str = None) -> None:
        """Checks if request is within allowed rate limit. Raises HTTP 429 if exceeded."""
        key = identifier or (request.client.host if request.client else "127.0.0.1")
        now = time.time()
        window_start = now - self.window_seconds

        timestamps = self.history.get(key, [])
        # Filter timestamps outside window
        timestamps = [t for t in timestamps if t > window_start]

        if len(timestamps) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - timestamps[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.window_seconds}s. Try again in {max(retry_after, 1)}s.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        timestamps.append(now)
        self.history[key] = timestamps

# Global limiters
settlement_limiter = SlidingWindowRateLimiter(max_requests=25, window_seconds=60)
api_general_limiter = SlidingWindowRateLimiter(max_requests=120, window_seconds=60)

