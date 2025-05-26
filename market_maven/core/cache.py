"""
Advanced caching layer for the stock agent using Redis.
"""

import json
import pickle
import time
from typing import Any, Optional, Dict, Union, List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.exceptions import RedisError

from market_maven.config.settings import settings
from market_maven.core.logging import LoggerMixin, get_logger
from market_maven.core.metrics import metrics

logger = get_logger(__name__)


class CacheKeyBuilder:
    """Build standardized cache keys."""
    
    @staticmethod
    def stock_data(symbol: str, data_type: str, period: str = None) -> str:
        """Build cache key for stock data."""
        key_parts = ["stock_data", symbol.upper(), data_type]
        if period:
            key_parts.append(period)
        return ":".join(key_parts)
    
    @staticmethod
    def analysis_result(symbol: str, analysis_type: str, risk_tolerance: str, horizon: str) -> str:
        """Build cache key for analysis results."""
        return f"analysis:{symbol.upper()}:{analysis_type}:{risk_tolerance}:{horizon}"
    
    @staticmethod
    def technical_indicator(symbol: str, indicator: str, period: int = None) -> str:
        """Build cache key for technical indicators."""
        key_parts = ["indicator", symbol.upper(), indicator]
        if period:
            key_parts.append(str(period))
        return ":".join(key_parts)
    
    @staticmethod
    def market_data(symbol: str) -> str:
        """Build cache key for real-time market data."""
        return f"market_data:{symbol.upper()}"


class RedisCache(LoggerMixin):
    """Redis-based caching implementation."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.connected = False
        
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(
                settings.redis.url,
                password=settings.redis.password,
                db=settings.redis.db,
                socket_timeout=settings.redis.socket_timeout,
                socket_connect_timeout=settings.redis.socket_connect_timeout,
                retry_on_timeout=settings.redis.retry_on_timeout,
                decode_responses=False  # We'll handle encoding ourselves
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connected = True
            logger.info("Redis cache connected successfully")
            
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False
            logger.info("Redis cache disconnected")
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        if not self.connected:
            await self.connect()
        
        try:
            start_time = time.time()
            
            # Get raw data from Redis
            raw_data = await self.redis_client.get(key)
            
            if raw_data is None:
                metrics.record_cache_event("redis", hit=False)
                return default
            
            # Deserialize data
            try:
                # Try JSON first (for simple data)
                data = json.loads(raw_data.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fall back to pickle for complex objects
                data = pickle.loads(raw_data)
            
            # Record metrics
            duration = time.time() - start_time
            metrics.record_cache_event("redis", hit=True, duration=duration)
            
            self.log_operation("cache_get", key=key, hit=True).debug("Cache hit")
            return data
            
        except RedisError as e:
            logger.error(f"Redis get error for key {key}: {e}")
            metrics.record_cache_event("redis", hit=False, error=True)
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        serialize_method: str = "auto"
    ) -> bool:
        """Set value in cache."""
        if not self.connected:
            await self.connect()
        
        try:
            start_time = time.time()
            
            # Serialize data
            if serialize_method == "auto":
                # Try JSON first for better performance and readability
                try:
                    serialized_data = json.dumps(value, default=str).encode('utf-8')
                except (TypeError, ValueError):
                    # Fall back to pickle for complex objects
                    serialized_data = pickle.dumps(value)
            elif serialize_method == "json":
                serialized_data = json.dumps(value, default=str).encode('utf-8')
            elif serialize_method == "pickle":
                serialized_data = pickle.dumps(value)
            else:
                raise ValueError(f"Unknown serialization method: {serialize_method}")
            
            # Set in Redis with optional TTL
            if ttl:
                await self.redis_client.setex(key, ttl, serialized_data)
            else:
                await self.redis_client.set(key, serialized_data)
            
            # Record metrics
            duration = time.time() - start_time
            metrics.record_cache_event("redis", hit=False, duration=duration, operation="set")
            
            self.log_operation("cache_set", key=key, ttl=ttl).debug("Cache set")
            return True
            
        except RedisError as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.connected:
            await self.connect()
        
        try:
            result = await self.redis_client.delete(key)
            self.log_operation("cache_delete", key=key).debug("Cache delete")
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.connected:
            await self.connect()
        
        try:
            result = await self.redis_client.exists(key)
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if not self.connected:
            await self.connect()
        
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"Cleared {deleted} cache keys matching pattern: {pattern}")
                return deleted
            return 0
            
        except RedisError as e:
            logger.error(f"Redis clear pattern error for {pattern}: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.connected:
            await self.connect()
        
        try:
            info = await self.redis_client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
            }
            
        except RedisError as e:
            logger.error(f"Redis stats error: {e}")
            return {}


class CacheManager:
    """High-level cache manager with fallback strategies."""
    
    def __init__(self):
        self.redis_cache = RedisCache()
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.memory_cache_ttl = 300  # 5 minutes for memory cache
    
    @asynccontextmanager
    async def get_cache(self):
        """Context manager for cache operations."""
        try:
            await self.redis_cache.connect()
            yield self.redis_cache
        except Exception as e:
            logger.warning(f"Redis unavailable, using memory cache: {e}")
            yield self._get_memory_cache()
        finally:
            await self.redis_cache.disconnect()
    
    def _get_memory_cache(self):
        """Get memory-based cache fallback."""
        class MemoryCache:
            def __init__(self, cache_dict: Dict[str, Dict[str, Any]], ttl: int):
                self.cache = cache_dict
                self.ttl = ttl
            
            async def get(self, key: str, default: Any = None) -> Any:
                if key in self.cache:
                    data, timestamp = self.cache[key]['data'], self.cache[key]['timestamp']
                    if time.time() - timestamp < self.ttl:
                        metrics.record_cache_event("memory", hit=True)
                        return data
                    else:
                        del self.cache[key]
                
                metrics.record_cache_event("memory", hit=False)
                return default
            
            async def set(self, key: str, value: Any, ttl: Optional[int] = None, **kwargs) -> bool:
                self.cache[key] = {
                    'data': value,
                    'timestamp': time.time()
                }
                return True
            
            async def delete(self, key: str) -> bool:
                return bool(self.cache.pop(key, None))
            
            async def exists(self, key: str) -> bool:
                return key in self.cache
            
            async def clear_pattern(self, pattern: str) -> int:
                # Simple pattern matching for memory cache
                keys_to_delete = [k for k in self.cache.keys() if pattern.replace('*', '') in k]
                for key in keys_to_delete:
                    del self.cache[key]
                return len(keys_to_delete)
        
        return MemoryCache(self.memory_cache, self.memory_cache_ttl)


# Global cache manager instance
cache_manager = CacheManager() 