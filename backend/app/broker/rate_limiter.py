"""
Rate limiter for Dhan-Tradehull API operations.

This module implements rate limiting to comply with Dhan API limits:
- 20 orders per second
- 20 modifications per order
- Sliding window algorithm for smooth rate limiting
"""

import asyncio
import time
from collections import deque
from typing import Optional, Dict, List
from dataclasses import dataclass

from loguru import logger


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_requests: int
    time_window: float
    burst_allowance: int = 0


class RateLimiter:
    """
    Sliding window rate limiter with burst support.
    
    Uses a sliding window algorithm to ensure smooth rate limiting
    while allowing for temporary bursts within limits.
    """

    def __init__(
        self,
        max_requests: int,
        time_window: float = 1.0,
        burst_allowance: int = 0
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
            burst_allowance: Additional requests allowed for bursts
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst_allowance = burst_allowance
        self.effective_limit = max_requests + burst_allowance
        
        # Request timestamps for sliding window
        self._requests: deque = deque()
        self._lock = asyncio.Lock()
        
        logger.info(
            f"Rate limiter initialized: {max_requests} req/{time_window}s "
            f"(burst: +{burst_allowance})"
        )

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make a request.
        
        Args:
            timeout: Maximum time to wait for permission (None = no timeout)
            
        Returns:
            True if permission granted, False if timeout exceeded
            
        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        start_time = time.time()
        
        async with self._lock:
            while True:
                current_time = time.time()
                
                # Remove old requests from sliding window
                self._cleanup_old_requests(current_time)
                
                # Check if we can make a request
                if len(self._requests) < self.effective_limit:
                    self._requests.append(current_time)
                    logger.debug(
                        f"Rate limit acquired: {len(self._requests)}/{self.effective_limit}"
                    )
                    return True
                
                # Check timeout
                if timeout and (current_time - start_time) >= timeout:
                    logger.warning("Rate limit acquisition timeout")
                    return False
                
                # Calculate wait time until next slot available
                wait_time = self._calculate_wait_time(current_time)
                
                logger.debug(
                    f"Rate limit hit, waiting {wait_time:.3f}s "
                    f"({len(self._requests)}/{self.effective_limit})"
                )
                
                # Wait for next slot
                await asyncio.sleep(wait_time)

    def _cleanup_old_requests(self, current_time: float):
        """Remove requests outside the sliding window."""
        cutoff_time = current_time - self.time_window
        
        while self._requests and self._requests[0] <= cutoff_time:
            self._requests.popleft()

    def _calculate_wait_time(self, current_time: float) -> float:
        """Calculate minimum wait time for next available slot."""
        if not self._requests:
            return 0.0
        
        # Find the oldest request that needs to age out
        oldest_request = self._requests[0]
        time_to_age_out = (oldest_request + self.time_window) - current_time
        
        # Add small buffer to avoid race conditions
        return max(0.001, time_to_age_out + 0.001)

    def get_current_usage(self) -> Dict[str, float]:
        """
        Get current rate limiter usage statistics.
        
        Returns:
            Dictionary with usage statistics
        """
        current_time = time.time()
        self._cleanup_old_requests(current_time)
        
        usage_percentage = (len(self._requests) / self.effective_limit) * 100
        
        return {
            "current_requests": len(self._requests),
            "max_requests": self.max_requests,
            "effective_limit": self.effective_limit,
            "usage_percentage": usage_percentage,
            "time_window": self.time_window
        }

    def reset(self):
        """Reset the rate limiter, clearing all tracked requests."""
        self._requests.clear()
        logger.info("Rate limiter reset")


class OrderRateLimiter:
    """
    Specialized rate limiter for order operations with modification tracking.
    
    Implements the Dhan API specific limits:
    - 20 orders per second
    - 20 modifications per order
    """

    def __init__(self):
        """Initialize order rate limiter."""
        # Main order rate limiter (20/sec)
        self.order_limiter = RateLimiter(max_requests=20, time_window=1.0)
        
        # Modification rate limiter (20/sec globally)
        self.modification_limiter = RateLimiter(max_requests=20, time_window=1.0)
        
        # Per-order modification tracking
        self._order_modifications: Dict[str, int] = {}
        self._modification_lock = asyncio.Lock()
        
        logger.info("Order rate limiter initialized")

    async def acquire_order_permission(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to place a new order.
        
        Args:
            timeout: Maximum time to wait for permission
            
        Returns:
            True if permission granted
        """
        return await self.order_limiter.acquire(timeout=timeout)

    async def acquire_modification_permission(
        self,
        order_id: str,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Acquire permission to modify an order.
        
        Args:
            order_id: Order ID to modify
            timeout: Maximum time to wait for permission
            
        Returns:
            True if permission granted
            
        Raises:
            ValueError: If order has reached modification limit
        """
        async with self._modification_lock:
            # Check per-order modification limit
            current_modifications = self._order_modifications.get(order_id, 0)
            if current_modifications >= 20:
                raise ValueError(
                    f"Order {order_id} has reached maximum modifications (20)"
                )
            
            # Acquire global modification rate limit
            permission = await self.modification_limiter.acquire(timeout=timeout)
            
            if permission:
                # Increment modification count for this order
                self._order_modifications[order_id] = current_modifications + 1
                logger.debug(
                    f"Modification permission granted for order {order_id} "
                    f"({current_modifications + 1}/20)"
                )
            
            return permission

    def register_new_order(self, order_id: str):
        """Register a new order for modification tracking."""
        self._order_modifications[order_id] = 0
        logger.debug(f"Order {order_id} registered for modification tracking")

    def unregister_order(self, order_id: str):
        """Unregister an order (when cancelled/filled)."""
        self._order_modifications.pop(order_id, None)
        logger.debug(f"Order {order_id} unregistered from modification tracking")

    def get_order_modification_count(self, order_id: str) -> int:
        """Get current modification count for an order."""
        return self._order_modifications.get(order_id, 0)

    def get_statistics(self) -> Dict[str, any]:
        """
        Get comprehensive rate limiter statistics.
        
        Returns:
            Dictionary with statistics for all rate limiters
        """
        return {
            "order_limiter": self.order_limiter.get_current_usage(),
            "modification_limiter": self.modification_limiter.get_current_usage(),
            "tracked_orders": len(self._order_modifications),
            "order_modifications": dict(self._order_modifications)
        }

    def reset_all(self):
        """Reset all rate limiters and tracking."""
        self.order_limiter.reset()
        self.modification_limiter.reset()
        self._order_modifications.clear()
        logger.info("All order rate limiters reset")


class MarketDataRateLimiter:
    """
    Rate limiter for market data operations.
    
    Implements reasonable limits for market data requests to avoid
    overwhelming the API while maintaining real-time capabilities.
    """

    def __init__(self):
        """Initialize market data rate limiter."""
        # Quote requests (for individual quotes)
        self.quote_limiter = RateLimiter(max_requests=10, time_window=1.0)
        
        # Depth requests (more intensive)
        self.depth_limiter = RateLimiter(max_requests=5, time_window=1.0)
        
        # Option chain requests (most intensive)
        self.option_chain_limiter = RateLimiter(max_requests=2, time_window=1.0)
        
        logger.info("Market data rate limiter initialized")

    async def acquire_quote_permission(self, timeout: Optional[float] = None) -> bool:
        """Acquire permission for quote request."""
        return await self.quote_limiter.acquire(timeout=timeout)

    async def acquire_depth_permission(self, timeout: Optional[float] = None) -> bool:
        """Acquire permission for depth request."""
        return await self.depth_limiter.acquire(timeout=timeout)

    async def acquire_option_chain_permission(self, timeout: Optional[float] = None) -> bool:
        """Acquire permission for option chain request."""
        return await self.option_chain_limiter.acquire(timeout=timeout)

    def get_statistics(self) -> Dict[str, any]:
        """Get market data rate limiter statistics."""
        return {
            "quote_limiter": self.quote_limiter.get_current_usage(),
            "depth_limiter": self.depth_limiter.get_current_usage(),
            "option_chain_limiter": self.option_chain_limiter.get_current_usage()
        }


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts limits based on API response times.
    
    Automatically reduces request rate if API latency increases,
    helping to maintain stable performance during high load periods.
    """

    def __init__(
        self,
        base_max_requests: int,
        time_window: float = 1.0,
        latency_threshold_ms: float = 500.0,
        adaptation_factor: float = 0.8
    ):
        """
        Initialize adaptive rate limiter.
        
        Args:
            base_max_requests: Base maximum requests per time window
            time_window: Time window in seconds
            latency_threshold_ms: Latency threshold for adaptation
            adaptation_factor: Factor to reduce rate when adapting (0.0-1.0)
        """
        self.base_max_requests = base_max_requests
        self.time_window = time_window
        self.latency_threshold_ms = latency_threshold_ms
        self.adaptation_factor = adaptation_factor
        
        self.current_max_requests = base_max_requests
        self._recent_latencies: deque = deque(maxlen=10)
        
        self.rate_limiter = RateLimiter(base_max_requests, time_window)
        
        logger.info(
            f"Adaptive rate limiter initialized: {base_max_requests} req/{time_window}s "
            f"(threshold: {latency_threshold_ms}ms)"
        )

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire permission with adaptive rate limiting."""
        return await self.rate_limiter.acquire(timeout=timeout)

    def record_latency(self, latency_ms: float):
        """
        Record API latency and adapt rate limits if necessary.
        
        Args:
            latency_ms: API response latency in milliseconds
        """
        self._recent_latencies.append(latency_ms)
        
        if len(self._recent_latencies) >= 5:  # Need enough samples
            avg_latency = sum(self._recent_latencies) / len(self._recent_latencies)
            
            if avg_latency > self.latency_threshold_ms:
                # Reduce rate limit
                new_max = max(1, int(self.current_max_requests * self.adaptation_factor))
                if new_max != self.current_max_requests:
                    self.current_max_requests = new_max
                    self._update_rate_limiter()
                    
                    logger.warning(
                        f"Rate limit adapted down due to high latency: "
                        f"{avg_latency:.1f}ms > {self.latency_threshold_ms}ms, "
                        f"new limit: {new_max}"
                    )
            else:
                # Gradually increase rate limit back to base
                if self.current_max_requests < self.base_max_requests:
                    self.current_max_requests = min(
                        self.base_max_requests,
                        self.current_max_requests + 1
                    )
                    self._update_rate_limiter()
                    
                    logger.info(
                        f"Rate limit increased back to: {self.current_max_requests}"
                    )

    def _update_rate_limiter(self):
        """Update the internal rate limiter with new limits."""
        self.rate_limiter = RateLimiter(self.current_max_requests, self.time_window)

    def get_statistics(self) -> Dict[str, any]:
        """Get adaptive rate limiter statistics."""
        avg_latency = (
            sum(self._recent_latencies) / len(self._recent_latencies)
            if self._recent_latencies else 0.0
        )
        
        stats = self.rate_limiter.get_current_usage()
        stats.update({
            "base_max_requests": self.base_max_requests,
            "current_max_requests": self.current_max_requests,
            "average_latency_ms": avg_latency,
            "latency_threshold_ms": self.latency_threshold_ms,
            "adaptation_active": self.current_max_requests < self.base_max_requests
        })
        
        return stats 