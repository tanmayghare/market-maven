"""
Unit tests for the validators module.
"""

import pytest
from decimal import Decimal
from datetime import datetime

from market_maven.core.validators import (
    StockSymbolValidator,
    PriceValidator,
    VolumeValidator,
    DateValidator,
    OrderValidator,
    AnalysisValidator,
    DataIntegrityValidator
)
from market_maven.core.exceptions import ValidationError


class TestStockSymbolValidator:
    """Test stock symbol validation."""
    
    def test_valid_us_symbols(self):
        """Test valid US stock symbols."""
        valid_symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "A"]
        
        for symbol in valid_symbols:
            result = StockSymbolValidator.validate_symbol(symbol)
            assert result == symbol.upper()
    
    def test_invalid_us_symbols(self):
        """Test invalid US stock symbols."""
        invalid_symbols = ["", "TOOLONG", "123", "AA.L", "AAPL.TO"]
        
        for symbol in invalid_symbols:
            with pytest.raises(ValidationError):
                StockSymbolValidator.validate_symbol(symbol)
    
    def test_international_symbols(self):
        """Test international stock symbols."""
        valid_international = ["AAPL.L", "SAP.DE", "NESN.SW"]
        
        for symbol in valid_international:
            result = StockSymbolValidator.validate_symbol(symbol, allow_international=True)
            assert result == symbol.upper()
    
    def test_case_normalization(self):
        """Test case normalization."""
        result = StockSymbolValidator.validate_symbol("aapl")
        assert result == "AAPL"
    
    def test_whitespace_handling(self):
        """Test whitespace handling."""
        result = StockSymbolValidator.validate_symbol("  AAPL  ")
        assert result == "AAPL"


class TestPriceValidator:
    """Test price validation."""
    
    def test_valid_prices(self):
        """Test valid price values."""
        valid_prices = [100.50, "150.75", Decimal("200.25"), 0]
        
        for price in valid_prices:
            result = PriceValidator.validate_price(price)
            assert isinstance(result, Decimal)
            assert result >= 0
    
    def test_invalid_prices(self):
        """Test invalid price values."""
        invalid_prices = [None, -10.50, "invalid", "", "abc"]
        
        for price in invalid_prices:
            with pytest.raises(ValidationError):
                PriceValidator.validate_price(price)
    
    def test_price_range_validation(self):
        """Test price range validation."""
        low, high = PriceValidator.validate_price_range(100, 200)
        assert low == Decimal("100")
        assert high == Decimal("200")
        
        # Test invalid range
        with pytest.raises(ValidationError):
            PriceValidator.validate_price_range(200, 100)
    
    def test_extreme_prices(self):
        """Test extremely high prices."""
        with pytest.raises(ValidationError):
            PriceValidator.validate_price(2000000)  # Too high


class TestVolumeValidator:
    """Test volume validation."""
    
    def test_valid_volumes(self):
        """Test valid volume values."""
        valid_volumes = [1000, "5000", 0]
        
        for volume in valid_volumes:
            result = VolumeValidator.validate_volume(volume)
            assert isinstance(result, int)
            assert result >= 0
    
    def test_invalid_volumes(self):
        """Test invalid volume values."""
        invalid_volumes = [None, -1000, "invalid", "", 15_000_000_000]  # Too high
        
        for volume in invalid_volumes:
            with pytest.raises(ValidationError):
                VolumeValidator.validate_volume(volume)


class TestDateValidator:
    """Test date validation."""
    
    def test_valid_dates(self):
        """Test valid date formats."""
        valid_dates = [
            "2024-01-15",
            "2024-01-15 10:30:00",
            "2024-01-15T10:30:00",
            "2024-01-15T10:30:00.123456",
            "2024-01-15T10:30:00Z",
            datetime(2024, 1, 15)
        ]
        
        for date_value in valid_dates:
            result = DateValidator.validate_date(date_value)
            assert isinstance(result, datetime)
    
    def test_invalid_dates(self):
        """Test invalid date values."""
        invalid_dates = [None, "invalid", "2024-13-01", "2024-01-32", 123]
        
        for date_value in invalid_dates:
            with pytest.raises(ValidationError):
                DateValidator.validate_date(date_value)
    
    def test_date_range_validation(self):
        """Test date range validation."""
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        
        start_dt, end_dt = DateValidator.validate_date_range(start_date, end_date)
        assert isinstance(start_dt, datetime)
        assert isinstance(end_dt, datetime)
        assert start_dt < end_dt
        
        # Test invalid range
        with pytest.raises(ValidationError):
            DateValidator.validate_date_range(end_date, start_date)


class TestOrderValidator:
    """Test order validation."""
    
    def test_valid_market_order(self):
        """Test valid market order."""
        order_data = {
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 100,
            "order_type": "MARKET"
        }
        
        result = OrderValidator.validate_order_data(order_data)
        assert result["symbol"] == "AAPL"
        assert result["action"] == "BUY"
        assert result["quantity"] == 100
        assert result["order_type"] == "MARKET"
    
    def test_valid_limit_order(self):
        """Test valid limit order."""
        order_data = {
            "symbol": "AAPL",
            "action": "SELL",
            "quantity": 50,
            "order_type": "LIMIT",
            "limit_price": 150.00
        }
        
        result = OrderValidator.validate_order_data(order_data)
        assert result["limit_price"] == Decimal("150.00")
    
    def test_missing_required_fields(self):
        """Test missing required fields."""
        incomplete_order = {
            "symbol": "AAPL",
            "action": "BUY"
            # Missing quantity and order_type
        }
        
        with pytest.raises(ValidationError, match="Missing required field"):
            OrderValidator.validate_order_data(incomplete_order)
    
    def test_invalid_action(self):
        """Test invalid order action."""
        order_data = {
            "symbol": "AAPL",
            "action": "INVALID",
            "quantity": 100,
            "order_type": "MARKET"
        }
        
        with pytest.raises(ValidationError, match="Invalid action"):
            OrderValidator.validate_order_data(order_data)
    
    def test_limit_order_without_price(self):
        """Test limit order without limit price."""
        order_data = {
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 100,
            "order_type": "LIMIT"
            # Missing limit_price
        }
        
        with pytest.raises(ValidationError, match="require limit_price"):
            OrderValidator.validate_order_data(order_data)


class TestAnalysisValidator:
    """Test analysis parameter validation."""
    
    def test_valid_analysis_params(self):
        """Test valid analysis parameters."""
        params = {
            "symbol": "AAPL",
            "analysis_type": "comprehensive",
            "risk_tolerance": "moderate",
            "investment_horizon": "medium_term"
        }
        
        result = AnalysisValidator.validate_analysis_params(params)
        assert result["symbol"] == "AAPL"
        assert result["analysis_type"] == "comprehensive"
        assert result["risk_tolerance"] == "moderate"
        assert result["investment_horizon"] == "medium_term"
    
    def test_missing_symbol(self):
        """Test missing symbol."""
        params = {
            "analysis_type": "comprehensive"
        }
        
        with pytest.raises(ValidationError, match="Missing required field: symbol"):
            AnalysisValidator.validate_analysis_params(params)
    
    def test_invalid_analysis_type(self):
        """Test invalid analysis type."""
        params = {
            "symbol": "AAPL",
            "analysis_type": "invalid"
        }
        
        with pytest.raises(ValidationError, match="Invalid analysis_type"):
            AnalysisValidator.validate_analysis_params(params)
    
    def test_default_values(self):
        """Test default parameter values."""
        params = {
            "symbol": "AAPL"
        }
        
        result = AnalysisValidator.validate_analysis_params(params)
        assert result["analysis_type"] == "comprehensive"
        assert result["risk_tolerance"] == "moderate"
        assert result["investment_horizon"] == "medium_term"


class TestDataIntegrityValidator:
    """Test data integrity validation."""
    
    def test_valid_stock_price_data(self):
        """Test valid stock price data."""
        price_data = {
            "open": 150.00,
            "high": 155.00,
            "low": 148.00,
            "close": 152.50,
            "volume": 1000000
        }
        
        result = DataIntegrityValidator.validate_stock_price_data(price_data)
        assert result is True
    
    def test_invalid_price_relationships(self):
        """Test invalid price relationships."""
        # High lower than low
        invalid_data = {
            "open": 150.00,
            "high": 145.00,  # Invalid: high < low
            "low": 148.00,
            "close": 152.50,
            "volume": 1000000
        }
        
        with pytest.raises(ValidationError, match="High price should be the highest"):
            DataIntegrityValidator.validate_stock_price_data(invalid_data)
    
    def test_open_outside_range(self):
        """Test open price outside high-low range."""
        invalid_data = {
            "open": 160.00,  # Invalid: open > high
            "high": 155.00,
            "low": 148.00,
            "close": 152.50,
            "volume": 1000000
        }
        
        with pytest.raises(ValidationError, match="Open price should be within high-low range"):
            DataIntegrityValidator.validate_stock_price_data(invalid_data)
    
    def test_missing_required_fields(self):
        """Test missing required price fields."""
        incomplete_data = {
            "open": 150.00,
            "high": 155.00
            # Missing low, close, volume
        }
        
        with pytest.raises(ValidationError, match="Missing required price field"):
            DataIntegrityValidator.validate_stock_price_data(incomplete_data)
    
    def test_valid_technical_indicator(self):
        """Test valid technical indicator data."""
        rsi_data = {
            "latest_value": 65.5,
            "latest_date": "2024-01-15",
            "interpretation": "Bullish momentum"
        }
        
        result = DataIntegrityValidator.validate_technical_indicator(rsi_data, "RSI")
        assert result is True
    
    def test_invalid_rsi_value(self):
        """Test invalid RSI value."""
        invalid_rsi = {
            "latest_value": 150.0  # Invalid: RSI should be 0-100
        }
        
        with pytest.raises(ValidationError, match="RSI value must be between 0 and 100"):
            DataIntegrityValidator.validate_technical_indicator(invalid_rsi, "RSI")
    
    def test_invalid_sma_value(self):
        """Test invalid SMA value."""
        invalid_sma = {
            "latest_value": -10.0  # Invalid: SMA should be positive
        }
        
        with pytest.raises(ValidationError, match="SMA value must be positive"):
            DataIntegrityValidator.validate_technical_indicator(invalid_sma, "SMA") 