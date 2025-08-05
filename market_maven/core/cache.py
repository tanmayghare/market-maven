"""
In-memory caching implementation.
"""

import time
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager

from market_maven.core.logging import get_logger

logger = get_logger(__name__)


class CacheKeyBuilder:
    """Build standardized cache keys."""
    
    @staticmethod
    def stock_quote(symbol: str) -> str:
        """Build cache key for stock quote."""
        return f"quote:{symbol.upper()}"
    
    @staticmethod
    def stock_analysis(symbol: str, period: str = "daily") -> str:
        """Build cache key for stock analysis."""
        return f"analysis:{symbol.upper()}:{period}"
    
    @staticmethod
    def market_data(symbol: str) -> str:
        """Build cache key for market data."""
        return f"market_data:{symbol.upper()}"


class InMemoryCache:
    """In-memory cache implementation."""
    
    def __init__(self, default_ttl: int = 300):  # 5 minutes default
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        if key in self.cache:
            data = self.cache[key]['data']
            timestamp = self.cache[key]['timestamp']
            ttl = self.cache[key].get('ttl', self.default_ttl)
            
            if time.time() - timestamp < ttl:
                # Cache hit
                logger.debug(f"Cache hit for key: {key}")
                return data
            else:
                # Expired
                del self.cache[key]
                logger.debug(f"Cache expired for key: {key}")
        
        # Cache miss
        return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        self.cache[key] = {
            'data': value,
            'timestamp': time.time(),
            'ttl': ttl or self.default_ttl
        }
        logger.debug(f"Cache set for key: {key}, ttl: {ttl or self.default_ttl}s")
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"Cache deleted for key: {key}")
            return True
        return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        if key in self.cache:
            timestamp = self.cache[key]['timestamp']
            ttl = self.cache[key].get('ttl', self.default_ttl)
            if time.time() - timestamp < ttl:
                return True
            else:
                del self.cache[key]
        return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_keys = len(self.cache)
        total_size = sum(len(str(v['data'])) for v in self.cache.values())
        
        return {
            "type": "memory",
            "total_keys": total_keys,
            "total_size_bytes": total_size,
            "oldest_key": min(
                self.cache.items(), 
                key=lambda x: x[1]['timestamp']
            )[0] if self.cache else None,
            "newest_key": max(
                self.cache.items(), 
                key=lambda x: x[1]['timestamp']
            )[0] if self.cache else None
        }


class CacheManager:
    """Cache manager for application caching."""
    
    def __init__(self):
        self.cache = InMemoryCache()
    
    @asynccontextmanager
    async def get_cache(self):
        """Context manager for cache operations."""
        yield self.cache
    
    async def clear_expired(self) -> int:
        """Clear expired entries."""
        expired_count = 0
        keys_to_delete = []
        
        for key, data in list(self.cache.cache.items()):
            timestamp = data['timestamp']
            ttl = data.get('ttl', self.cache.default_ttl)
            if time.time() - timestamp >= ttl:
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            await self.cache.delete(key)
            expired_count += 1
        
        if expired_count > 0:
            logger.info(f"Cleared {expired_count} expired cache entries")
        
        return expired_count


# Global cache instance
cache_manager = CacheManager()