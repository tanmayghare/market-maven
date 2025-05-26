"""
Production-grade data fetcher tool using Google ADK framework.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

import aiohttp
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from google.adk.tools import Tool

from market_maven.config.settings import settings
from market_maven.core.exceptions import DataFetchError, RateLimitError
from market_maven.core.logging import LoggerMixin
from market_maven.core.metrics import metrics
from market_maven.models.schemas import StockPrice, CompanyInfo, TechnicalIndicator


class DataCache:
    """Simple in-memory cache for data fetching."""
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if not expired."""
        if key in self.cache:
            data, timestamp = self.cache[key]['data'], self.cache[key]['timestamp']
            if time.time() - timestamp < self.ttl_seconds:
                metrics.record_cache_event("data_fetch", hit=True)
                return data
            else:
                del self.cache[key]
        
        metrics.record_cache_event("data_fetch", hit=False)
        return None
    
    def set(self, key: str, data: Dict[str, Any]) -> None:
        """Cache data with timestamp."""
        self.cache[key] = {
            'data': data,
            'timestamp': time.time()
        }


class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, requests_per_minute: int = 5):
        self.requests_per_minute = requests_per_minute
        self.requests = []
    
    def can_make_request(self) -> bool:
        """Check if we can make a request without exceeding rate limits."""
        now = time.time()
        # Remove requests older than 1 minute
        self.requests = [req_time for req_time in self.requests if now - req_time < 60]
        
        return len(self.requests) < self.requests_per_minute
    
    def record_request(self) -> None:
        """Record a request timestamp."""
        self.requests.append(time.time())
    
    def wait_time(self) -> float:
        """Get time to wait before next request."""
        if not self.requests:
            return 0
        
        oldest_request = min(self.requests)
        return max(0, 60 - (time.time() - oldest_request))


class DataFetcherTool(Tool, LoggerMixin):
    """Production-grade ADK Tool for fetching stock market data."""

    def __init__(self):
        super().__init__(
            name="data_fetcher",
            description="Fetch comprehensive stock market data including historical prices, company fundamentals, and technical indicators with caching and rate limiting",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., AAPL, GOOGL, MSFT)",
                        "pattern": "^[A-Z]{1,5}$"
                    },
                    "data_type": {
                        "type": "string",
                        "enum": ["historical", "company_info", "technical_indicators", "all"],
                        "description": "Type of data to fetch"
                    },
                    "period": {
                        "type": "string",
                        "enum": ["1y", "6m", "3m", "1m", "1w"],
                        "description": "Time period for historical data",
                        "default": "1y"
                    },
                    "indicators": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["RSI", "SMA", "EMA", "MACD", "BBANDS", "STOCH"]
                        },
                        "description": "Technical indicators to fetch",
                        "default": ["RSI", "SMA", "EMA", "MACD"]
                    },
                    "use_cache": {
                        "type": "boolean",
                        "description": "Whether to use cached data if available",
                        "default": True
                    }
                },
                "required": ["symbol", "data_type"]
            }
        )
        
        # Validate API key
        if not settings.api.alpha_vantage_api_key:
            raise DataFetchError("Alpha Vantage API key not configured")
        
        # Initialize components
        self.cache = DataCache(ttl_seconds=settings.analysis.cache_ttl_seconds)
        self.rate_limiter = RateLimiter(settings.api.alpha_vantage_requests_per_minute)
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-Stock-Agent/1.0',
            'Accept': 'application/json'
        })

    def execute(
        self, 
        symbol: str, 
        data_type: str, 
        period: str = "1y", 
        indicators: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Execute the data fetching operation with comprehensive error handling."""
        
        start_time = time.time()
        symbol = symbol.upper().strip()
        
        if indicators is None:
            indicators = settings.analysis.technical_indicators
        
        # Log operation start
        operation_logger = self.log_operation(
            "data_fetch",
            symbol=symbol,
            data_type=data_type,
            period=period,
            indicators=indicators
        )
        
        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "data": {},
            "metadata": {
                "cached": False,
                "rate_limited": False,
                "data_sources": []
            }
        }

        try:
            # Check cache first
            cache_key = f"{symbol}_{data_type}_{period}_{','.join(sorted(indicators))}"
            
            if use_cache and settings.analysis.enable_caching:
                cached_data = self.cache.get(cache_key)
                if cached_data:
                    operation_logger.info("Using cached data")
                    result.update(cached_data)
                    result["metadata"]["cached"] = True
                    return result
            
            # Fetch data based on type
            if data_type == "historical" or data_type == "all":
                result["data"]["historical"] = self._get_historical_data(symbol, period)
                result["metadata"]["data_sources"].append("alpha_vantage_historical")
            
            if data_type == "company_info" or data_type == "all":
                result["data"]["company_info"] = self._get_company_info(symbol)
                result["metadata"]["data_sources"].append("alpha_vantage_overview")
            
            if data_type == "technical_indicators" or data_type == "all":
                result["data"]["technical_indicators"] = self._get_technical_indicators(symbol, indicators)
                result["metadata"]["data_sources"].append("alpha_vantage_technical")
            
            # Cache the result
            if settings.analysis.enable_caching:
                self.cache.set(cache_key, result)
            
            result["status"] = "success"
            
            # Record metrics
            duration = time.time() - start_time
            metrics.record_data_fetch(
                source="alpha_vantage",
                symbol=symbol,
                status="success",
                duration=duration
            )
            
            operation_logger.info(
                "Data fetch completed successfully",
                duration=duration,
                data_sources=result["metadata"]["data_sources"]
            )
            
            return result
            
        except RateLimitError as e:
            result["status"] = "rate_limited"
            result["error"] = str(e)
            result["metadata"]["rate_limited"] = True
            result["retry_after"] = e.retry_after
            
            metrics.record_data_fetch("alpha_vantage", symbol, "rate_limited")
            operation_logger.warning("Rate limit exceeded", retry_after=e.retry_after)
            
            return result
            
        except DataFetchError as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["error_code"] = e.error_code
            
            metrics.record_data_fetch("alpha_vantage", symbol, "error")
            operation_logger.error("Data fetch failed", error=str(e), error_code=e.error_code)
            
            return result
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Unexpected error: {str(e)}"
            
            metrics.record_data_fetch("alpha_vantage", symbol, "error")
            operation_logger.error("Unexpected error during data fetch", error=str(e))
            
            return result

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def _make_api_request(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Make API request with rate limiting and retry logic."""
        
        # Check rate limits
        if not self.rate_limiter.can_make_request():
            wait_time = self.rate_limiter.wait_time()
            raise RateLimitError(
                f"Rate limit exceeded. Wait {wait_time:.1f} seconds.",
                retry_after=int(wait_time) + 1
            )
        
        # Add API key to parameters
        params["apikey"] = settings.api.alpha_vantage_api_key
        
        # Make request
        response = self.session.get(
            settings.api.alpha_vantage_base_url,
            params=params,
            timeout=30
        )
        
        # Record request
        self.rate_limiter.record_request()
        
        # Check response
        response.raise_for_status()
        data = response.json()
        
        # Check for API errors
        if "Error Message" in data:
            raise DataFetchError(
                f"API Error: {data['Error Message']}",
                error_code="API_ERROR"
            )
        
        if "Note" in data and "rate limit" in data["Note"].lower():
            raise RateLimitError(
                "API rate limit exceeded",
                retry_after=60
            )
        
        return data

    def _get_historical_data(self, symbol: str, period: str) -> Dict[str, Any]:
        """Fetch historical stock data with validation."""
        
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full"
        }

        data = self._make_api_request(params)
        
        if "Time Series (Daily)" not in data:
            raise DataFetchError(
                f"No historical data available for {symbol}",
                symbol=symbol,
                source="alpha_vantage"
            )

        time_series = data["Time Series (Daily)"]
        
        # Convert to structured format and filter by period
        historical_data = []
        cutoff_date = self._get_cutoff_date(period)
        
        for date_str, values in time_series.items():
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if date_obj >= cutoff_date:
                    price_data = StockPrice(
                        symbol=symbol,
                        timestamp=date_obj,
                        open=Decimal(values["1. open"]),
                        high=Decimal(values["2. high"]),
                        low=Decimal(values["3. low"]),
                        close=Decimal(values["4. close"]),
                        volume=int(values["6. volume"]),
                        adjusted_close=Decimal(values["5. adjusted close"])
                    )
                    historical_data.append(price_data.dict())
            except (ValueError, KeyError) as e:
                self.logger.warning(f"Skipping invalid data point for {date_str}: {e}")
                continue

        # Sort by date
        historical_data.sort(key=lambda x: x["timestamp"])
        
        return {
            "period": period,
            "data_points": len(historical_data),
            "data": historical_data,
            "latest_price": historical_data[-1]["close"] if historical_data else None
        }

    def _get_company_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch company information with validation."""
        
        params = {
            "function": "OVERVIEW",
            "symbol": symbol
        }

        data = self._make_api_request(params)
        
        if not data or "Symbol" not in data:
            raise DataFetchError(
                f"No company information available for {symbol}",
                symbol=symbol,
                source="alpha_vantage"
            )

        try:
            company_info = CompanyInfo(
                symbol=symbol,
                name=data.get("Name", ""),
                sector=data.get("Sector"),
                industry=data.get("Industry"),
                country=data.get("Country"),
                market_cap=self._safe_decimal(data.get("MarketCapitalization")),
                pe_ratio=self._safe_decimal(data.get("PERatio")),
                peg_ratio=self._safe_decimal(data.get("PEGRatio")),
                price_to_book=self._safe_decimal(data.get("PriceToBookRatio")),
                price_to_sales=self._safe_decimal(data.get("PriceToSalesRatioTTM")),
                eps=self._safe_decimal(data.get("EPS")),
                dividend_per_share=self._safe_decimal(data.get("DividendPerShare")),
                dividend_yield=self._safe_decimal(data.get("DividendYield")),
                week_52_high=self._safe_decimal(data.get("52WeekHigh")),
                week_52_low=self._safe_decimal(data.get("52WeekLow")),
                description=data.get("Description", "")[:1000],  # Truncate long descriptions
                employees=self._safe_int(data.get("FullTimeEmployees"))
            )
            
            return company_info.dict()
            
        except Exception as e:
            raise DataFetchError(
                f"Failed to parse company info for {symbol}: {str(e)}",
                symbol=symbol,
                source="alpha_vantage"
            )

    def _get_technical_indicators(self, symbol: str, indicators: List[str]) -> Dict[str, Any]:
        """Fetch technical indicators with error handling."""
        
        results = {}
        
        for indicator in indicators:
            try:
                if indicator == "RSI":
                    results[indicator] = self._fetch_rsi(symbol)
                elif indicator == "SMA":
                    results[indicator] = self._fetch_sma(symbol)
                elif indicator == "EMA":
                    results[indicator] = self._fetch_ema(symbol)
                elif indicator == "MACD":
                    results[indicator] = self._fetch_macd(symbol)
                elif indicator == "BBANDS":
                    results[indicator] = self._fetch_bbands(symbol)
                elif indicator == "STOCH":
                    results[indicator] = self._fetch_stoch(symbol)
                else:
                    self.logger.warning(f"Unknown indicator: {indicator}")
                    results[indicator] = {"error": f"Unknown indicator: {indicator}"}
                    
            except Exception as e:
                self.logger.error(f"Failed to fetch {indicator} for {symbol}: {e}")
                results[indicator] = {"error": str(e)}
        
        return results

    def _fetch_rsi(self, symbol: str) -> Dict[str, Any]:
        """Fetch RSI indicator."""
        params = {
            "function": "RSI",
            "symbol": symbol,
            "interval": "daily",
            "time_period": "14",
            "series_type": "close"
        }
        
        data = self._make_api_request(params)
        
        if "Technical Analysis: RSI" not in data:
            raise DataFetchError(f"No RSI data available for {symbol}")
        
        rsi_data = data["Technical Analysis: RSI"]
        latest_date = max(rsi_data.keys())
        latest_value = float(rsi_data[latest_date]["RSI"])
        
        return {
            "latest_value": latest_value,
            "latest_date": latest_date,
            "interpretation": self._interpret_rsi(latest_value),
            "signal": self._rsi_signal(latest_value),
            "period": 14
        }

    def _fetch_sma(self, symbol: str, period: int = 20) -> Dict[str, Any]:
        """Fetch SMA indicator."""
        params = {
            "function": "SMA",
            "symbol": symbol,
            "interval": "daily",
            "time_period": str(period),
            "series_type": "close"
        }
        
        data = self._make_api_request(params)
        
        if "Technical Analysis: SMA" not in data:
            raise DataFetchError(f"No SMA data available for {symbol}")
        
        sma_data = data["Technical Analysis: SMA"]
        latest_date = max(sma_data.keys())
        latest_value = float(sma_data[latest_date]["SMA"])
        
        return {
            "latest_value": latest_value,
            "latest_date": latest_date,
            "period": period
        }

    def _fetch_ema(self, symbol: str, period: int = 20) -> Dict[str, Any]:
        """Fetch EMA indicator."""
        params = {
            "function": "EMA",
            "symbol": symbol,
            "interval": "daily",
            "time_period": str(period),
            "series_type": "close"
        }
        
        data = self._make_api_request(params)
        
        if "Technical Analysis: EMA" not in data:
            raise DataFetchError(f"No EMA data available for {symbol}")
        
        ema_data = data["Technical Analysis: EMA"]
        latest_date = max(ema_data.keys())
        latest_value = float(ema_data[latest_date]["EMA"])
        
        return {
            "latest_value": latest_value,
            "latest_date": latest_date,
            "period": period
        }

    def _fetch_macd(self, symbol: str) -> Dict[str, Any]:
        """Fetch MACD indicator."""
        params = {
            "function": "MACD",
            "symbol": symbol,
            "interval": "daily",
            "series_type": "close"
        }
        
        data = self._make_api_request(params)
        
        if "Technical Analysis: MACD" not in data:
            raise DataFetchError(f"No MACD data available for {symbol}")
        
        macd_data = data["Technical Analysis: MACD"]
        latest_date = max(macd_data.keys())
        latest = macd_data[latest_date]
        
        macd_value = float(latest["MACD"])
        signal_value = float(latest["MACD_Signal"])
        histogram_value = float(latest["MACD_Hist"])
        
        return {
            "macd": macd_value,
            "signal": signal_value,
            "histogram": histogram_value,
            "latest_date": latest_date,
            "interpretation": self._interpret_macd(macd_value, signal_value),
            "signal": "BUY" if macd_value > signal_value else "SELL"
        }

    def _fetch_bbands(self, symbol: str) -> Dict[str, Any]:
        """Fetch Bollinger Bands indicator."""
        params = {
            "function": "BBANDS",
            "symbol": symbol,
            "interval": "daily",
            "time_period": "20",
            "series_type": "close"
        }
        
        data = self._make_api_request(params)
        
        if "Technical Analysis: BBANDS" not in data:
            raise DataFetchError(f"No BBANDS data available for {symbol}")
        
        bbands_data = data["Technical Analysis: BBANDS"]
        latest_date = max(bbands_data.keys())
        latest = bbands_data[latest_date]
        
        return {
            "upper_band": float(latest["Real Upper Band"]),
            "middle_band": float(latest["Real Middle Band"]),
            "lower_band": float(latest["Real Lower Band"]),
            "latest_date": latest_date,
            "period": 20
        }

    def _fetch_stoch(self, symbol: str) -> Dict[str, Any]:
        """Fetch Stochastic oscillator."""
        params = {
            "function": "STOCH",
            "symbol": symbol,
            "interval": "daily"
        }
        
        data = self._make_api_request(params)
        
        if "Technical Analysis: STOCH" not in data:
            raise DataFetchError(f"No STOCH data available for {symbol}")
        
        stoch_data = data["Technical Analysis: STOCH"]
        latest_date = max(stoch_data.keys())
        latest = stoch_data[latest_date]
        
        slowk = float(latest["SlowK"])
        slowd = float(latest["SlowD"])
        
        return {
            "slowk": slowk,
            "slowd": slowd,
            "latest_date": latest_date,
            "signal": self._stoch_signal(slowk, slowd)
        }

    def _get_cutoff_date(self, period: str) -> datetime:
        """Get cutoff date based on period."""
        now = datetime.now()
        period_map = {
            "1y": 365,
            "6m": 180,
            "3m": 90,
            "1m": 30,
            "1w": 7
        }
        days = period_map.get(period, 365)
        return now - timedelta(days=days)

    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Safely convert value to Decimal."""
        if value is None or value == "None" or value == "":
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to int."""
        if value is None or value == "None" or value == "":
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _interpret_rsi(self, rsi_value: float) -> str:
        """Interpret RSI value."""
        if rsi_value > 70:
            return "Overbought - potential sell signal"
        elif rsi_value < 30:
            return "Oversold - potential buy signal"
        elif rsi_value > 60:
            return "Bullish momentum"
        elif rsi_value < 40:
            return "Bearish momentum"
        else:
            return "Neutral"

    def _rsi_signal(self, rsi_value: float) -> str:
        """Generate RSI trading signal."""
        if rsi_value < 30:
            return "BUY"
        elif rsi_value > 70:
            return "SELL"
        else:
            return "NEUTRAL"

    def _interpret_macd(self, macd: float, signal: float) -> str:
        """Interpret MACD values."""
        if macd > signal:
            return "Bullish - MACD above signal line"
        else:
            return "Bearish - MACD below signal line"

    def _stoch_signal(self, slowk: float, slowd: float) -> str:
        """Generate Stochastic trading signal."""
        if slowk < 20 and slowd < 20:
            return "BUY"  # Oversold
        elif slowk > 80 and slowd > 80:
            return "SELL"  # Overbought
        else:
            return "NEUTRAL"

    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'session'):
            self.session.close() 