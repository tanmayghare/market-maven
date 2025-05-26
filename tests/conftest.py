"""
Pytest configuration and shared fixtures for the stock agent tests.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from typing import Dict, Any, Generator
from datetime import datetime, timedelta
from decimal import Decimal

from market_maven.config.settings import settings
from market_maven.core.logging import setup_logging
from market_maven.models.schemas import StockPrice, CompanyInfo


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """Set up logging for tests."""
    setup_logging(level="DEBUG", json_logs=False)


@pytest.fixture
def mock_alpha_vantage_response() -> Dict[str, Any]:
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


@pytest.fixture
def mock_company_info() -> Dict[str, Any]:
    """Mock company information response."""
    return {
        "Symbol": "AAPL",
        "Name": "Apple Inc.",
        "Sector": "Technology",
        "Industry": "Consumer Electronics",
        "Country": "USA",
        "MarketCapitalization": "3000000000000",
        "PERatio": "25.5",
        "EPS": "6.00",
        "DividendPerShare": "0.96",
        "DividendYield": "0.0063",
        "52WeekHigh": "200.00",
        "52WeekLow": "120.00",
        "Description": "Apple Inc. designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories worldwide."
    }


@pytest.fixture
def mock_technical_indicators() -> Dict[str, Any]:
    """Mock technical indicators response."""
    return {
        "RSI": {
            "latest_value": 65.5,
            "latest_date": "2024-01-15",
            "interpretation": "Bullish momentum",
            "signal": "NEUTRAL",
            "period": 14
        },
        "SMA": {
            "latest_value": 148.75,
            "latest_date": "2024-01-15",
            "period": 20
        },
        "MACD": {
            "macd": 2.5,
            "signal": 2.0,
            "histogram": 0.5,
            "latest_date": "2024-01-15",
            "interpretation": "Bullish - MACD above signal line",
            "signal": "BUY"
        }
    }


@pytest.fixture
def sample_stock_price() -> StockPrice:
    """Create a sample stock price object."""
    return StockPrice(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 15),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("148.00"),
        close=Decimal("152.50"),
        volume=1000000,
        adjusted_close=Decimal("152.50")
    )


@pytest.fixture
def sample_company_info() -> CompanyInfo:
    """Create a sample company info object."""
    return CompanyInfo(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        country="USA",
        market_cap=Decimal("3000000000000"),
        pe_ratio=Decimal("25.5"),
        eps=Decimal("6.00"),
        dividend_per_share=Decimal("0.96"),
        dividend_yield=Decimal("0.0063"),
        week_52_high=Decimal("200.00"),
        week_52_low=Decimal("120.00")
    )


@pytest.fixture
def mock_requests_session():
    """Mock requests session for API calls."""
    with patch('requests.Session') as mock_session:
        mock_instance = Mock()
        mock_session.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_data_fetcher_tool():
    """Mock data fetcher tool."""
    with patch('market_maven.tools.data_fetcher_tool.DataFetcherTool') as mock_tool:
        mock_instance = Mock()
        mock_tool.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_analyzer_tool():
    """Mock analyzer tool."""
    with patch('market_maven.tools.analyzer_tool.AnalyzerTool') as mock_tool:
        mock_instance = Mock()
        mock_tool.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_trader_tool():
    """Mock trader tool."""
    with patch('market_maven.tools.trader_tool.TraderTool') as mock_tool:
        mock_instance = Mock()
        mock_tool.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_llm_agent():
    """Mock LLM agent for testing."""
    with patch('google.adk.agents.LlmAgent') as mock_agent:
        mock_instance = Mock()
        mock_agent.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def test_market_data() -> Dict[str, Any]:
    """Comprehensive test market data."""
    return {
        "symbol": "AAPL",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "historical": {
                "period": "1y",
                "data_points": 2,
                "data": [
                    {
                        "symbol": "AAPL",
                        "timestamp": "2024-01-14T00:00:00",
                        "open": 148.00,
                        "high": 151.00,
                        "low": 147.00,
                        "close": 150.00,
                        "volume": 950000,
                        "adjusted_close": 150.00
                    },
                    {
                        "symbol": "AAPL",
                        "timestamp": "2024-01-15T00:00:00",
                        "open": 150.00,
                        "high": 155.00,
                        "low": 148.00,
                        "close": 152.50,
                        "volume": 1000000,
                        "adjusted_close": 152.50
                    }
                ],
                "latest_price": 152.50
            },
            "company_info": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "country": "USA",
                "market_cap": 3000000000000,
                "pe_ratio": 25.5,
                "eps": 6.00,
                "dividend_per_share": 0.96,
                "dividend_yield": 0.0063,
                "week_52_high": 200.00,
                "week_52_low": 120.00
            },
            "technical_indicators": {
                "RSI": {
                    "latest_value": 65.5,
                    "latest_date": "2024-01-15",
                    "interpretation": "Bullish momentum",
                    "signal": "NEUTRAL",
                    "period": 14
                },
                "SMA": {
                    "latest_value": 148.75,
                    "latest_date": "2024-01-15",
                    "period": 20
                },
                "MACD": {
                    "macd": 2.5,
                    "signal": 2.0,
                    "histogram": 0.5,
                    "latest_date": "2024-01-15",
                    "interpretation": "Bullish - MACD above signal line",
                    "signal": "BUY"
                }
            }
        },
        "metadata": {
            "cached": False,
            "rate_limited": False,
            "data_sources": ["alpha_vantage_historical", "alpha_vantage_overview", "alpha_vantage_technical"]
        },
        "status": "success"
    }


@pytest.fixture
def cleanup_test_files():
    """Clean up test files after tests."""
    yield
    # Cleanup logic here if needed
    pass 