"""QoS rate limiting module"""

import asyncio
import time
import logging
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class QoSLimiter:
    """
    Rate limiter using token bucket algorithm with concurrency control.
    
    Features:
    - QPS (queries per second) limiting
    - Maximum concurrent requests limiting
    - Minimum interval between requests
    """
    
    def __init__(
        self,
        qps: float = 5.0,
        max_concurrent: int = 3,
        interval_ms: int = 200,
    ):
        """
        Initialize QoS limiter.
        
        Args:
            qps: Maximum queries per second
            max_concurrent: Maximum concurrent requests
            interval_ms: Minimum interval between requests in milliseconds
        """
        self.qps = qps
        self.max_concurrent = max_concurrent
        self.interval = interval_ms / 1000.0  # Convert to seconds
        
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()
        
        # Statistics
        self._total_requests = 0
        self._waiting_requests = 0
        
        logger.info(
            f"QoS initialized: qps={qps}, max_concurrent={max_concurrent}, "
            f"interval={interval_ms}ms"
        )
    
    async def _wait_for_rate_limit(self) -> None:
        """Wait to respect rate limiting"""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            
            # Calculate minimum wait time based on QPS
            min_interval = max(1.0 / self.qps, self.interval)
            
            if elapsed < min_interval:
                wait_time = min_interval - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.3f}s")
                await asyncio.sleep(wait_time)
            
            self._last_request_time = time.time()
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a request slot with rate limiting.
        
        Usage:
            async with limiter.acquire():
                await make_request()
        """
        self._waiting_requests += 1
        try:
            async with self._semaphore:
                await self._wait_for_rate_limit()
                self._total_requests += 1
                yield
        finally:
            self._waiting_requests -= 1
    
    async def execute(self, coro):
        """
        Execute a coroutine with rate limiting.
        
        Args:
            coro: Coroutine to execute
            
        Returns:
            Result of the coroutine
        """
        async with self.acquire():
            return await coro
    
    @property
    def stats(self) -> dict:
        """Get current statistics"""
        return {
            "total_requests": self._total_requests,
            "waiting_requests": self._waiting_requests,
            "qps": self.qps,
            "max_concurrent": self.max_concurrent,
            "interval_ms": int(self.interval * 1000),
        }
    
    def update_limits(
        self,
        qps: Optional[float] = None,
        max_concurrent: Optional[int] = None,
        interval_ms: Optional[int] = None,
    ) -> None:
        """
        Update rate limits dynamically.
        
        Args:
            qps: New QPS limit
            max_concurrent: New max concurrent limit  
            interval_ms: New interval in milliseconds
        """
        if qps is not None:
            self.qps = qps
        if max_concurrent is not None:
            self.max_concurrent = max_concurrent
            self._semaphore = asyncio.Semaphore(max_concurrent)
        if interval_ms is not None:
            self.interval = interval_ms / 1000.0
        
        logger.info(
            f"QoS updated: qps={self.qps}, max_concurrent={self.max_concurrent}, "
            f"interval={int(self.interval * 1000)}ms"
        )


# Global QoS limiter instance
_qos_limiter: Optional[QoSLimiter] = None


def get_qos_limiter() -> QoSLimiter:
    """Get the global QoS limiter instance"""
    global _qos_limiter
    if _qos_limiter is None:
        from app.config import get_config
        config = get_config()
        _qos_limiter = QoSLimiter(
            qps=config.qos.qps,
            max_concurrent=config.qos.max_concurrent,
            interval_ms=config.qos.interval,
        )
    return _qos_limiter


def reset_qos_limiter() -> None:
    """Reset the global QoS limiter instance"""
    global _qos_limiter
    _qos_limiter = None
