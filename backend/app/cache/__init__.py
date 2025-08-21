"""
Cache Package
High-performance caching layer for market data and system state
"""

from .redis import (
    RedisCache,
    cache,
    init_redis,
    close_redis,
    get_redis_health,
    cache_key,
    cache_market_data,
    get_cached_market_data,
    cache_strategy_state,
    get_cached_strategy_state,
    cache_position_summary,
    get_cached_position_summary
)

__all__ = [
    "RedisCache",
    "cache",
    "init_redis",
    "close_redis",
    "get_redis_health",
    "cache_key",
    "cache_market_data",
    "get_cached_market_data",
    "cache_strategy_state",
    "get_cached_strategy_state",
    "cache_position_summary",
    "get_cached_position_summary"
] 