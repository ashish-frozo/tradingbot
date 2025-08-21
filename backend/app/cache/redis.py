"""
Redis Connection and Caching Management
High-performance caching layer for market data and system state
"""

import json
import pickle
from typing import Any, Optional, Union, Dict, List
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis import ConnectionPool
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Redis connection pools
_redis_pool: Optional[ConnectionPool] = None
_async_redis: Optional[redis.Redis] = None


class RedisCache:
    """Redis caching utility with async support"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.connected = False
    
    async def connect(self) -> None:
        """Establish Redis connection"""
        global _async_redis
        
        try:
            # Parse Redis URL
            redis_url = settings.REDIS_URL
            logger.info(f"Connecting to Redis: {redis_url}")
            
            # Create async Redis connection
            _async_redis = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            await _async_redis.ping()
            self.redis = _async_redis
            self.connected = True
            
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection"""
        if self.redis:
            try:
                await self.redis.close()
                self.connected = False
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
    
    async def ping(self) -> bool:
        """Test Redis connection"""
        if not self.redis:
            return False
        
        try:
            result = await self.redis.ping()
            return result
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    async def get_health(self) -> Dict[str, Any]:
        """Get Redis health status"""
        if not self.connected or not self.redis:
            return {"status": "disconnected", "error": "No connection"}
        
        try:
            # Test connection
            ping_result = await self.ping()
            
            # Get Redis info
            info = await self.redis.info()
            
            return {
                "status": "healthy" if ping_result else "unhealthy",
                "ping": ping_result,
                "version": info.get("redis_version"),
                "memory_used": info.get("used_memory_human"),
                "memory_peak": info.get("used_memory_peak_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
                "uptime_seconds": info.get("uptime_in_seconds")
            }
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    # Basic Cache Operations
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[Union[int, timedelta]] = None,
        serialize: bool = True
    ) -> bool:
        """Set a key-value pair with optional TTL"""
        if not self.redis:
            logger.warning("Redis not connected, cannot set key")
            return False
        
        try:
            # Serialize value if needed
            if serialize:
                if isinstance(value, (dict, list, tuple)):
                    serialized_value = json.dumps(value, default=str)
                else:
                    serialized_value = str(value)
            else:
                serialized_value = value
            
            # Set with TTL if provided
            if ttl:
                if isinstance(ttl, timedelta):
                    ttl = int(ttl.total_seconds())
                await self.redis.setex(key, ttl, serialized_value)
            else:
                await self.redis.set(key, serialized_value)
            
            return True
            
        except Exception as e:
            logger.error(f"Redis set failed for key {key}: {e}")
            return False
    
    async def get(
        self, 
        key: str, 
        deserialize: bool = True,
        default: Any = None
    ) -> Any:
        """Get value by key"""
        if not self.redis:
            logger.warning("Redis not connected, cannot get key")
            return default
        
        try:
            value = await self.redis.get(key)
            
            if value is None:
                return default
            
            # Deserialize if needed
            if deserialize:
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            
            return value
            
        except Exception as e:
            logger.error(f"Redis get failed for key {key}: {e}")
            return default
    
    async def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        if not self.redis:
            return 0
        
        try:
            return await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Redis delete failed for keys {keys}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.redis:
            return False
        
        try:
            return bool(await self.redis.exists(key))
        except Exception as e:
            logger.error(f"Redis exists check failed for key {key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: Union[int, timedelta]) -> bool:
        """Set TTL for existing key"""
        if not self.redis:
            return False
        
        try:
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            return bool(await self.redis.expire(key, ttl))
        except Exception as e:
            logger.error(f"Redis expire failed for key {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get TTL for key (-1 = no expiry, -2 = doesn't exist)"""
        if not self.redis:
            return -2
        
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL check failed for key {key}: {e}")
            return -2
    
    # List Operations
    async def lpush(self, key: str, *values: Any) -> int:
        """Push values to left of list"""
        if not self.redis:
            return 0
        
        try:
            serialized_values = [json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v) for v in values]
            return await self.redis.lpush(key, *serialized_values)
        except Exception as e:
            logger.error(f"Redis lpush failed for key {key}: {e}")
            return 0
    
    async def rpush(self, key: str, *values: Any) -> int:
        """Push values to right of list"""
        if not self.redis:
            return 0
        
        try:
            serialized_values = [json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v) for v in values]
            return await self.redis.rpush(key, *serialized_values)
        except Exception as e:
            logger.error(f"Redis rpush failed for key {key}: {e}")
            return 0
    
    async def lpop(self, key: str, count: int = 1) -> Union[str, List[str], None]:
        """Pop from left of list"""
        if not self.redis:
            return None
        
        try:
            if count == 1:
                return await self.redis.lpop(key)
            else:
                return await self.redis.lpop(key, count)
        except Exception as e:
            logger.error(f"Redis lpop failed for key {key}: {e}")
            return None
    
    async def lrange(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """Get range of list elements"""
        if not self.redis:
            return []
        
        try:
            return await self.redis.lrange(key, start, end)
        except Exception as e:
            logger.error(f"Redis lrange failed for key {key}: {e}")
            return []
    
    async def llen(self, key: str) -> int:
        """Get list length"""
        if not self.redis:
            return 0
        
        try:
            return await self.redis.llen(key)
        except Exception as e:
            logger.error(f"Redis llen failed for key {key}: {e}")
            return 0
    
    # Hash Operations
    async def hset(self, key: str, mapping: Dict[str, Any]) -> int:
        """Set hash fields"""
        if not self.redis:
            return 0
        
        try:
            # Serialize values
            serialized_mapping = {}
            for field, value in mapping.items():
                if isinstance(value, (dict, list)):
                    serialized_mapping[field] = json.dumps(value, default=str)
                else:
                    serialized_mapping[field] = str(value)
            
            return await self.redis.hset(key, mapping=serialized_mapping)
        except Exception as e:
            logger.error(f"Redis hset failed for key {key}: {e}")
            return 0
    
    async def hget(self, key: str, field: str) -> Optional[str]:
        """Get hash field value"""
        if not self.redis:
            return None
        
        try:
            return await self.redis.hget(key, field)
        except Exception as e:
            logger.error(f"Redis hget failed for key {key}, field {field}: {e}")
            return None
    
    async def hgetall(self, key: str) -> Dict[str, str]:
        """Get all hash fields and values"""
        if not self.redis:
            return {}
        
        try:
            return await self.redis.hgetall(key)
        except Exception as e:
            logger.error(f"Redis hgetall failed for key {key}: {e}")
            return {}
    
    async def hdel(self, key: str, *fields: str) -> int:
        """Delete hash fields"""
        if not self.redis:
            return 0
        
        try:
            return await self.redis.hdel(key, *fields)
        except Exception as e:
            logger.error(f"Redis hdel failed for key {key}: {e}")
            return 0
    
    # Set Operations
    async def sadd(self, key: str, *values: Any) -> int:
        """Add to set"""
        if not self.redis:
            return 0
        
        try:
            serialized_values = [json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v) for v in values]
            return await self.redis.sadd(key, *serialized_values)
        except Exception as e:
            logger.error(f"Redis sadd failed for key {key}: {e}")
            return 0
    
    async def srem(self, key: str, *values: Any) -> int:
        """Remove from set"""
        if not self.redis:
            return 0
        
        try:
            serialized_values = [json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v) for v in values]
            return await self.redis.srem(key, *serialized_values)
        except Exception as e:
            logger.error(f"Redis srem failed for key {key}: {e}")
            return 0
    
    async def smembers(self, key: str) -> set:
        """Get all set members"""
        if not self.redis:
            return set()
        
        try:
            return await self.redis.smembers(key)
        except Exception as e:
            logger.error(f"Redis smembers failed for key {key}: {e}")
            return set()
    
    async def sismember(self, key: str, value: Any) -> bool:
        """Check if value is in set"""
        if not self.redis:
            return False
        
        try:
            serialized_value = json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)
            return bool(await self.redis.sismember(key, serialized_value))
        except Exception as e:
            logger.error(f"Redis sismember failed for key {key}: {e}")
            return False


# Global cache instance
cache = RedisCache()


# Convenience functions
async def init_redis() -> None:
    """Initialize Redis connection"""
    try:
        await cache.connect()
        logger.info("Redis cache initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis cache: {e}")
        # Don't raise - allow app to continue without cache


async def close_redis() -> None:
    """Close Redis connection"""
    await cache.disconnect()


async def get_redis_health() -> Dict[str, Any]:
    """Get Redis health status"""
    return await cache.get_health()


# Cache decorators and utilities
def cache_key(*parts: str) -> str:
    """Generate cache key from parts"""
    return ":".join(str(part) for part in parts)


# Trading-specific cache functions
async def cache_market_data(symbol: str, data: Dict[str, Any], ttl: int = 60) -> bool:
    """Cache market data with symbol-based key"""
    key = cache_key("market_data", symbol)
    return await cache.set(key, data, ttl=ttl)


async def get_cached_market_data(symbol: str) -> Optional[Dict[str, Any]]:
    """Get cached market data for symbol"""
    key = cache_key("market_data", symbol)
    return await cache.get(key)


async def cache_strategy_state(strategy_name: str, state: Dict[str, Any], ttl: int = 300) -> bool:
    """Cache strategy state"""
    key = cache_key("strategy_state", strategy_name)
    return await cache.set(key, state, ttl=ttl)


async def get_cached_strategy_state(strategy_name: str) -> Optional[Dict[str, Any]]:
    """Get cached strategy state"""
    key = cache_key("strategy_state", strategy_name)
    return await cache.get(key)


async def cache_position_summary(summary: Dict[str, Any], ttl: int = 30) -> bool:
    """Cache position summary"""
    key = cache_key("position_summary")
    return await cache.set(key, summary, ttl=ttl)


async def get_cached_position_summary() -> Optional[Dict[str, Any]]:
    """Get cached position summary"""
    key = cache_key("position_summary")
    return await cache.get(key)


# Export main components
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