"""
Unit tests for the caching layer.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from market_maven.core.cache import (
    CacheKeyBuilder, 
    RedisCache, 
    CacheManager,
    cache_manager
)


class TestCacheKeyBuilder:
    """Test cache key building functionality."""
    
    def test_stock_data_key(self):
        """Test stock data key generation."""
        key = CacheKeyBuilder.stock_data("AAPL", "historical", "1y")
        assert key == "stock_data:AAPL:historical:1y"
        
        key_no_period = CacheKeyBuilder.stock_data("AAPL", "company_info")
        assert key_no_period == "stock_data:AAPL:company_info"
    
    def test_analysis_result_key(self):
        """Test analysis result key generation."""
        key = CacheKeyBuilder.analysis_result("AAPL", "comprehensive", "moderate", "long_term")
        assert key == "analysis:AAPL:comprehensive:moderate:long_term"
    
    def test_technical_indicator_key(self):
        """Test technical indicator key generation."""
        key = CacheKeyBuilder.technical_indicator("AAPL", "RSI", 14)
        assert key == "indicator:AAPL:RSI:14"
        
        key_no_period = CacheKeyBuilder.technical_indicator("AAPL", "MACD")
        assert key_no_period == "indicator:AAPL:MACD"
    
    def test_market_data_key(self):
        """Test market data key generation."""
        key = CacheKeyBuilder.market_data("AAPL")
        assert key == "market_data:AAPL"
    
    def test_symbol_normalization(self):
        """Test that symbols are normalized to uppercase."""
        key = CacheKeyBuilder.stock_data("aapl", "historical")
        assert "AAPL" in key
        assert "aapl" not in key


@pytest.mark.asyncio
class TestRedisCache:
    """Test Redis cache functionality."""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        with patch('redis.asyncio.from_url') as mock_from_url:
            mock_client = AsyncMock()
            mock_from_url.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def redis_cache(self, mock_redis_client):
        """Create Redis cache instance with mocked client."""
        cache = RedisCache()
        cache.redis_client = mock_redis_client
        cache.connected = True
        return cache
    
    async def test_connect_success(self, mock_redis_client):
        """Test successful Redis connection."""
        mock_redis_client.ping.return_value = True
        
        cache = RedisCache()
        await cache.connect()
        
        assert cache.connected is True
        mock_redis_client.ping.assert_called_once()
    
    async def test_connect_failure(self, mock_redis_client):
        """Test Redis connection failure."""
        from redis.exceptions import RedisError
        mock_redis_client.ping.side_effect = RedisError("Connection failed")
        
        cache = RedisCache()
        
        with pytest.raises(RedisError):
            await cache.connect()
        
        assert cache.connected is False
    
    async def test_get_hit(self, redis_cache, mock_redis_client):
        """Test cache hit scenario."""
        test_data = {"symbol": "AAPL", "price": 150.0}
        mock_redis_client.get.return_value = json.dumps(test_data).encode('utf-8')
        
        result = await redis_cache.get("test_key")
        
        assert result == test_data
        mock_redis_client.get.assert_called_once_with("test_key")
    
    async def test_get_miss(self, redis_cache, mock_redis_client):
        """Test cache miss scenario."""
        mock_redis_client.get.return_value = None
        
        result = await redis_cache.get("test_key", default="default_value")
        
        assert result == "default_value"
        mock_redis_client.get.assert_called_once_with("test_key")
    
    async def test_set_with_ttl(self, redis_cache, mock_redis_client):
        """Test setting value with TTL."""
        test_data = {"symbol": "AAPL", "price": 150.0}
        
        result = await redis_cache.set("test_key", test_data, ttl=300)
        
        assert result is True
        mock_redis_client.setex.assert_called_once()
        args = mock_redis_client.setex.call_args[0]
        assert args[0] == "test_key"
        assert args[1] == 300
    
    async def test_set_without_ttl(self, redis_cache, mock_redis_client):
        """Test setting value without TTL."""
        test_data = {"symbol": "AAPL", "price": 150.0}
        
        result = await redis_cache.set("test_key", test_data)
        
        assert result is True
        mock_redis_client.set.assert_called_once()
    
    async def test_delete(self, redis_cache, mock_redis_client):
        """Test deleting key."""
        mock_redis_client.delete.return_value = 1
        
        result = await redis_cache.delete("test_key")
        
        assert result is True
        mock_redis_client.delete.assert_called_once_with("test_key")
    
    async def test_exists(self, redis_cache, mock_redis_client):
        """Test checking key existence."""
        mock_redis_client.exists.return_value = 1
        
        result = await redis_cache.exists("test_key")
        
        assert result is True
        mock_redis_client.exists.assert_called_once_with("test_key")
    
    async def test_clear_pattern(self, redis_cache, mock_redis_client):
        """Test clearing keys by pattern."""
        mock_redis_client.keys.return_value = ["key1", "key2", "key3"]
        mock_redis_client.delete.return_value = 3
        
        result = await redis_cache.clear_pattern("test_*")
        
        assert result == 3
        mock_redis_client.keys.assert_called_once_with("test_*")
        mock_redis_client.delete.assert_called_once_with("key1", "key2", "key3")
    
    async def test_get_stats(self, redis_cache, mock_redis_client):
        """Test getting cache statistics."""
        mock_info = {
            "connected_clients": 5,
            "used_memory": 1024,
            "used_memory_human": "1K",
            "keyspace_hits": 100,
            "keyspace_misses": 10,
            "total_commands_processed": 1000
        }
        mock_redis_client.info.return_value = mock_info
        
        stats = await redis_cache.get_stats()
        
        assert stats == mock_info
        mock_redis_client.info.assert_called_once()


@pytest.mark.asyncio
class TestCacheManager:
    """Test cache manager functionality."""
    
    @pytest.fixture
    def cache_manager_instance(self):
        """Create cache manager instance."""
        return CacheManager()
    
    async def test_redis_cache_context(self, cache_manager_instance):
        """Test Redis cache context manager."""
        with patch.object(cache_manager_instance.redis_cache, 'connect') as mock_connect:
            with patch.object(cache_manager_instance.redis_cache, 'disconnect') as mock_disconnect:
                mock_connect.return_value = None
                mock_disconnect.return_value = None
                
                async with cache_manager_instance.get_cache() as cache:
                    assert cache == cache_manager_instance.redis_cache
                
                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()
    
    async def test_memory_cache_fallback(self, cache_manager_instance):
        """Test fallback to memory cache when Redis fails."""
        with patch.object(cache_manager_instance.redis_cache, 'connect') as mock_connect:
            mock_connect.side_effect = Exception("Redis connection failed")
            
            async with cache_manager_instance.get_cache() as cache:
                # Should be memory cache, not Redis cache
                assert cache != cache_manager_instance.redis_cache
                
                # Test memory cache operations
                await cache.set("test_key", "test_value")
                result = await cache.get("test_key")
                assert result == "test_value"
    
    async def test_memory_cache_ttl(self, cache_manager_instance):
        """Test memory cache TTL functionality."""
        import time
        
        with patch.object(cache_manager_instance.redis_cache, 'connect') as mock_connect:
            mock_connect.side_effect = Exception("Redis connection failed")
            
            async with cache_manager_instance.get_cache() as cache:
                # Set short TTL for testing
                cache.ttl = 0.1  # 100ms
                
                await cache.set("test_key", "test_value")
                
                # Should be available immediately
                result = await cache.get("test_key")
                assert result == "test_value"
                
                # Wait for TTL to expire
                time.sleep(0.2)
                
                # Should be expired now
                result = await cache.get("test_key", default="expired")
                assert result == "expired"


@pytest.mark.integration
class TestCacheIntegration:
    """Integration tests for caching functionality."""
    
    @pytest.mark.skipif(
        not pytest.config.getoption("--integration"),
        reason="Integration tests require --integration flag"
    )
    async def test_real_redis_operations(self):
        """Test with real Redis instance (requires Redis running)."""
        cache = RedisCache()
        
        try:
            await cache.connect()
            
            # Test basic operations
            test_data = {
                "symbol": "AAPL",
                "price": 150.0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Set and get
            await cache.set("integration_test", test_data, ttl=60)
            result = await cache.get("integration_test")
            
            assert result["symbol"] == test_data["symbol"]
            assert result["price"] == test_data["price"]
            
            # Test existence
            exists = await cache.exists("integration_test")
            assert exists is True
            
            # Test deletion
            deleted = await cache.delete("integration_test")
            assert deleted is True
            
            # Verify deletion
            result = await cache.get("integration_test")
            assert result is None
            
        finally:
            await cache.disconnect()


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


def pytest_addoption(parser):
    """Add command line options for pytest."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="run integration tests"
    ) 