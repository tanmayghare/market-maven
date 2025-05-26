"""
Unit tests for the data fetcher tool.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import time
import json

from market_maven.tools.data_fetcher_tool import DataFetcherTool, DataCache, RateLimiter
from market_maven.core.exceptions import DataFetchError, RateLimitError


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    def test_rate_limit_allows_initial_requests(self):
        """Test that rate limiter allows initial requests."""
        limiter = RateLimiter(requests_per_minute=5)
        
        for _ in range(5):
            assert limiter.can_make_request() is True
            limiter.record_request()
    
    def test_rate_limit_blocks_excess_requests(self):
        """Test that rate limiter blocks requests over limit."""
        limiter = RateLimiter(requests_per_minute=5)
        
        # Make 5 requests
        for _ in range(5):
            limiter.record_request()
        
        # 6th request should be blocked
        assert limiter.can_make_request() is False
    
    def test_rate_limit_resets_after_time_window(self):
        """Test that rate limiter resets after time window."""
        limiter = RateLimiter(requests_per_minute=5)
        
        # Record a request with old timestamp
        limiter.requests = [time.time() - 61]  # 61 seconds ago
        
        # Should allow new request
        assert limiter.can_make_request() is True
    
    def test_wait_time_calculation(self):
        """Test wait time calculation."""
        limiter = RateLimiter(requests_per_minute=5)
        
        # No requests yet
        assert limiter.wait_time() == 0
        
        # Add a request
        limiter.record_request()
        
        # Wait time should be close to 60 seconds
        wait = limiter.wait_time()
        assert 59 <= wait <= 60


class TestDataCache:
    """Test data caching functionality."""
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = DataCache(ttl_seconds=300)
        assert cache.get("nonexistent") is None
    
    def test_cache_hit(self):
        """Test cache hit returns data."""
        cache = DataCache(ttl_seconds=300)
        test_data = {"symbol": "AAPL", "price": 150.0}
        
        cache.set("test_key", test_data)
        result = cache.get("test_key")
        
        assert result == test_data
    
    def test_cache_expiration(self):
        """Test cache expiration."""
        cache = DataCache(ttl_seconds=0.1)  # 100ms TTL
        test_data = {"symbol": "AAPL", "price": 150.0}
        
        cache.set("test_key", test_data)
        
        # Should be available immediately
        assert cache.get("test_key") == test_data
        
        # Wait for expiration
        time.sleep(0.2)
        
        # Should be expired
        assert cache.get("test_key") is None
    
    @patch('market_maven.core.metrics.metrics.record_cache_event')
    def test_cache_metrics(self, mock_metrics):
        """Test cache metrics recording."""
        cache = DataCache(ttl_seconds=300)
        
        # Cache miss
        cache.get("test_key")
        mock_metrics.assert_called_with("data_fetch", hit=False)
        
        # Cache hit
        cache.set("test_key", {"data": "test"})
        cache.get("test_key")
        mock_metrics.assert_called_with("data_fetch", hit=True)


@pytest.mark.asyncio
class TestDataFetcherTool:
    """Test data fetcher tool functionality."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('market_maven.config.settings.settings') as mock:
            mock.api.alpha_vantage_api_key = "test_key"
            mock.api.alpha_vantage_base_url = "https://test.api.com"
            mock.api.alpha_vantage_requests_per_minute = 5
            mock.analysis.cache_ttl_seconds = 300
            mock.analysis.enable_caching = True
            mock.analysis.technical_indicators = ["RSI", "SMA", "EMA", "MACD"]
            yield mock
    
    @pytest.fixture
    def data_fetcher(self, mock_settings):
        """Create data fetcher instance."""
        return DataFetcherTool()
    
    @pytest.fixture
    def mock_api_response(self):
        """Mock Alpha Vantage API response."""
        return {
            "Time Series (Daily)": {
                "2024-01-15": {
                    "1. open": "150.00",
                    "2. high": "155.00",
                    "3. low": "148.00",
                    "4. close": "152.50",
                    "5. adjusted close": "152.50",
                    "6. volume": "1000000"
                },
                "2024-01-14": {
                    "1. open": "148.00",
                    "2. high": "151.00",
                    "3. low": "147.00",
                    "4. close": "150.00",
                    "5. adjusted close": "150.00",
                    "6. volume": "950000"
                }
            }
        }
    
    def test_execute_with_cache_hit(self, data_fetcher):
        """Test execute method with cache hit."""
        # Pre-populate cache
        cache_data = {
            "symbol": "AAPL",
            "data": {"historical": {"test": "data"}},
            "metadata": {"cached": True}
        }
        cache_key = "AAPL_historical_1y_EMA,MACD,RSI,SMA"
        data_fetcher.cache.set(cache_key, cache_data)
        
        result = data_fetcher.execute("AAPL", "historical", use_cache=True)
        
        assert result["symbol"] == "AAPL"
        assert result["metadata"]["cached"] is True
        assert result["data"]["historical"]["test"] == "data"
    
    @patch('requests.Session.get')
    def test_execute_with_cache_miss(self, mock_get, data_fetcher, mock_api_response):
        """Test execute method with cache miss."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = mock_api_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = data_fetcher.execute("AAPL", "historical", use_cache=False)
        
        assert result["symbol"] == "AAPL"
        assert result["metadata"]["cached"] is False
        assert "historical" in result["data"]
        assert mock_get.called
    
    def test_execute_with_invalid_symbol(self, data_fetcher):
        """Test execute with invalid symbol."""
        with pytest.raises(ValueError):
            data_fetcher.execute("INVALID_SYMBOL_TOO_LONG", "historical")
    
    @patch('requests.Session.get')
    def test_rate_limiting(self, mock_get, data_fetcher):
        """Test rate limiting behavior."""
        # Fill up rate limit
        for _ in range(5):
            data_fetcher.rate_limiter.record_request()
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {"Error Message": "Rate limit exceeded"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Should raise RateLimitError
        with pytest.raises(RateLimitError):
            data_fetcher._make_api_request({"function": "TIME_SERIES_DAILY"})
    
    @patch('requests.Session.get')
    def test_api_error_handling(self, mock_get, data_fetcher):
        """Test API error handling."""
        # Mock API error
        mock_get.side_effect = Exception("API Error")
        
        with pytest.raises(DataFetchError):
            data_fetcher._make_api_request({"function": "TIME_SERIES_DAILY"})
    
    def test_get_cutoff_date(self, data_fetcher):
        """Test cutoff date calculation."""
        now = datetime.utcnow()
        
        # Test different periods
        cutoff_1y = data_fetcher._get_cutoff_date("1y")
        assert (now - cutoff_1y).days >= 364
        
        cutoff_6m = data_fetcher._get_cutoff_date("6m")
        assert (now - cutoff_6m).days >= 179
        
        cutoff_3m = data_fetcher._get_cutoff_date("3m")
        assert (now - cutoff_3m).days >= 89
        
        cutoff_1m = data_fetcher._get_cutoff_date("1m")
        assert (now - cutoff_1m).days >= 29
        
        cutoff_1w = data_fetcher._get_cutoff_date("1w")
        assert (now - cutoff_1w).days >= 6
    
    def test_safe_decimal_conversion(self, data_fetcher):
        """Test safe decimal conversion."""
        assert data_fetcher._safe_decimal("123.45") == 123.45
        assert data_fetcher._safe_decimal(123.45) == 123.45
        assert data_fetcher._safe_decimal("invalid") is None
        assert data_fetcher._safe_decimal(None) is None
    
    def test_safe_int_conversion(self, data_fetcher):
        """Test safe integer conversion."""
        assert data_fetcher._safe_int("123") == 123
        assert data_fetcher._safe_int(123) == 123
        assert data_fetcher._safe_int("123.45") == 123
        assert data_fetcher._safe_int("invalid") is None
        assert data_fetcher._safe_int(None) is None
    
    def test_rsi_interpretation(self, data_fetcher):
        """Test RSI interpretation."""
        assert data_fetcher._interpret_rsi(75) == "Overbought - potential sell signal"
        assert data_fetcher._interpret_rsi(25) == "Oversold - potential buy signal"
        assert data_fetcher._interpret_rsi(50) == "Neutral"
    
    def test_rsi_signal(self, data_fetcher):
        """Test RSI signal generation."""
        assert data_fetcher._rsi_signal(75) == "SELL"
        assert data_fetcher._rsi_signal(25) == "BUY"
        assert data_fetcher._rsi_signal(50) == "NEUTRAL"
    
    def test_macd_interpretation(self, data_fetcher):
        """Test MACD interpretation."""
        assert data_fetcher._interpret_macd(2.5, 2.0) == "Bullish - MACD above signal line"
        assert data_fetcher._interpret_macd(2.0, 2.5) == "Bearish - MACD below signal line"
        assert data_fetcher._interpret_macd(2.0, 2.0) == "Neutral - MACD equals signal line"
    
    def test_stoch_signal(self, data_fetcher):
        """Test Stochastic signal generation."""
        assert data_fetcher._stoch_signal(85, 80) == "SELL"
        assert data_fetcher._stoch_signal(15, 20) == "BUY"
        assert data_fetcher._stoch_signal(50, 50) == "NEUTRAL"


@pytest.mark.integration
class TestDataFetcherIntegration:
    """Integration tests for data fetcher."""
    
    @pytest.mark.skipif(
        not pytest.config.getoption("--integration"),
        reason="Integration tests require --integration flag"
    )
    async def test_real_api_call(self):
        """Test with real Alpha Vantage API (requires valid API key)."""
        data_fetcher = DataFetcherTool()
        
        # Test fetching historical data
        result = data_fetcher.execute("AAPL", "historical", period="1m")
        
        assert result["symbol"] == "AAPL"
        assert "historical" in result["data"]
        assert result["data"]["historical"]["data_points"] > 0
    
    @pytest.mark.skipif(
        not pytest.config.getoption("--integration"),
        reason="Integration tests require --integration flag"
    )
    async def test_all_data_types(self):
        """Test fetching all data types."""
        data_fetcher = DataFetcherTool()
        
        result = data_fetcher.execute("AAPL", "all", period="1m")
        
        assert result["symbol"] == "AAPL"
        assert "historical" in result["data"]
        assert "company_info" in result["data"]
        assert "technical_indicators" in result["data"] 