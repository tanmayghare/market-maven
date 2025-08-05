"""
Data fetcher for Alpha Vantage API.
"""

import requests
from typing import Dict, Any, Optional
from datetime import datetime
import time

from market_maven.config.settings import settings
from market_maven.core.logging import get_logger
from market_maven.core.cache import cache_manager, CacheKeyBuilder

logger = get_logger(__name__)


class DataFetcher:
    """Data fetcher for stock market data using Alpha Vantage."""
    
    def __init__(self):
        self.api_key = settings.api.alpha_vantage_api_key
        self.base_url = settings.api.alpha_vantage_base_url
        self.last_request_time = 0
        self.min_request_interval = 12  # 5 requests per minute = 12 seconds between requests
    
    def _rate_limit(self):
        """Enforce rate limiting for Alpha Vantage API."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def fetch_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch current stock quote data."""
        cache_key = CacheKeyBuilder.stock_quote(symbol)
        
        # Check cache first
        async with cache_manager.get_cache() as cache:
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.info(f"Retrieved quote for {symbol} from cache")
                return cached_data
        
        # Rate limit before making request
        self._rate_limit()
        
        try:
            # Make API request
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if 'Error Message' in data:
                logger.error(f"API error for {symbol}: {data['Error Message']}")
                return {
                    'error': True,
                    'message': data['Error Message'],
                    'symbol': symbol
                }
            
            if 'Note' in data:  # Rate limit message
                logger.warning(f"API rate limit reached: {data['Note']}")
                return {
                    'error': True,
                    'message': 'Rate limit reached. Please try again later.',
                    'symbol': symbol
                }
            
            if 'Global Quote' not in data or not data['Global Quote']:
                logger.warning(f"No data returned for {symbol}")
                return {
                    'error': True,
                    'message': f'No data available for symbol {symbol}',
                    'symbol': symbol
                }
            
            # Parse the response
            quote_data = data['Global Quote']
            parsed_data = {
                'symbol': quote_data.get('01. symbol', symbol),
                'price': float(quote_data.get('05. price', 0)),
                'open': float(quote_data.get('02. open', 0)),
                'high': float(quote_data.get('03. high', 0)),
                'low': float(quote_data.get('04. low', 0)),
                'volume': int(quote_data.get('06. volume', 0)),
                'change': float(quote_data.get('09. change', 0)),
                'change_percent': quote_data.get('10. change percent', '0%').rstrip('%'),
                'previous_close': float(quote_data.get('08. previous close', 0)),
                'timestamp': quote_data.get('07. latest trading day', datetime.now().isoformat()),
                'fetched_at': datetime.now().isoformat()
            }
            
            # Cache the data
            async with cache_manager.get_cache() as cache:
                await cache.set(cache_key, parsed_data, ttl=300)  # 5 minutes cache
            
            logger.info(f"Successfully fetched quote for {symbol}")
            return parsed_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return {
                'error': True,
                'message': f'Network error: {str(e)}',
                'symbol': symbol
            }
        except Exception as e:
            logger.error(f"Unexpected error fetching quote for {symbol}: {e}")
            return {
                'error': True,
                'message': f'Unexpected error: {str(e)}',
                'symbol': symbol
            }
    
    async def fetch_company_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch company overview information."""
        cache_key = f"company_info:{symbol.upper()}"
        
        # Check cache first
        async with cache_manager.get_cache() as cache:
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.info(f"Retrieved company info for {symbol} from cache")
                return cached_data
        
        # Rate limit before making request
        self._rate_limit()
        
        try:
            # Make API request
            params = {
                'function': 'OVERVIEW',
                'symbol': symbol,
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for errors
            if not data or 'Symbol' not in data:
                logger.warning(f"No company info returned for {symbol}")
                return {
                    'error': True,
                    'message': f'No company information available for {symbol}',
                    'symbol': symbol
                }
            
            # Parse relevant fields
            parsed_data = {
                'symbol': data.get('Symbol', symbol),
                'name': data.get('Name', 'Unknown'),
                'description': data.get('Description', ''),
                'exchange': data.get('Exchange', ''),
                'currency': data.get('Currency', 'USD'),
                'country': data.get('Country', ''),
                'sector': data.get('Sector', ''),
                'industry': data.get('Industry', ''),
                'market_cap': int(data.get('MarketCapitalization', 0)),
                'pe_ratio': float(data.get('PERatio', 0)) if data.get('PERatio') != 'None' else 0,
                'dividend_yield': float(data.get('DividendYield', 0)) if data.get('DividendYield') != 'None' else 0,
                '52_week_high': float(data.get('52WeekHigh', 0)),
                '52_week_low': float(data.get('52WeekLow', 0)),
                'eps': float(data.get('EPS', 0)) if data.get('EPS') != 'None' else 0,
                'beta': float(data.get('Beta', 0)) if data.get('Beta') != 'None' else 0,
                'fetched_at': datetime.now().isoformat()
            }
            
            # Cache the data (longer TTL for company info)
            async with cache_manager.get_cache() as cache:
                await cache.set(cache_key, parsed_data, ttl=3600)  # 1 hour cache
            
            logger.info(f"Successfully fetched company info for {symbol}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error fetching company info for {symbol}: {e}")
            return {
                'error': True,
                'message': f'Error fetching company info: {str(e)}',
                'symbol': symbol
            }


# Global instance
data_fetcher = DataFetcher()