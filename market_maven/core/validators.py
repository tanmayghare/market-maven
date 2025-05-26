"""
Comprehensive validation utilities for the stock agent.
"""

import re
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal, InvalidOperation
from datetime import datetime

from pydantic import ValidationError

from .exceptions import ValidationError as StockValidationError


class StockSymbolValidator:
    """Validator for stock symbols."""
    
    # Common stock symbol patterns
    US_PATTERN = re.compile(r'^[A-Z]{1,5}$')
    INTERNATIONAL_PATTERN = re.compile(r'^[A-Z]{1,10}(\.[A-Z]{1,3})?$')
    
    @classmethod
    def validate_symbol(cls, symbol: str, allow_international: bool = False) -> str:
        """
        Validate and normalize a stock symbol.
        
        Args:
            symbol: Stock symbol to validate
            allow_international: Whether to allow international symbols
            
        Returns:
            Normalized symbol
            
        Raises:
            StockValidationError: If symbol is invalid
        """
        if not symbol or not isinstance(symbol, str):
            raise StockValidationError("Symbol must be a non-empty string")
        
        symbol = symbol.upper().strip()
        
        if not symbol:
            raise StockValidationError("Symbol cannot be empty")
        
        pattern = cls.INTERNATIONAL_PATTERN if allow_international else cls.US_PATTERN
        
        if not pattern.match(symbol):
            raise StockValidationError(
                f"Invalid symbol format: {symbol}. "
                f"Expected {'international' if allow_international else 'US'} format."
            )
        
        return symbol


class PriceValidator:
    """Validator for price data."""
    
    @classmethod
    def validate_price(cls, price: Union[str, float, Decimal], field_name: str = "price") -> Decimal:
        """
        Validate and convert price to Decimal.
        
        Args:
            price: Price value to validate
            field_name: Name of the field for error messages
            
        Returns:
            Validated price as Decimal
            
        Raises:
            StockValidationError: If price is invalid
        """
        if price is None:
            raise StockValidationError(f"{field_name} cannot be None")
        
        try:
            decimal_price = Decimal(str(price))
        except (InvalidOperation, ValueError, TypeError):
            raise StockValidationError(f"Invalid {field_name}: {price}")
        
        if decimal_price < 0:
            raise StockValidationError(f"{field_name} cannot be negative: {decimal_price}")
        
        if decimal_price > Decimal('1000000'):  # Reasonable upper limit
            raise StockValidationError(f"{field_name} too high: {decimal_price}")
        
        return decimal_price
    
    @classmethod
    def validate_price_range(
        cls, 
        low: Union[str, float, Decimal], 
        high: Union[str, float, Decimal]
    ) -> tuple[Decimal, Decimal]:
        """
        Validate a price range (low, high).
        
        Args:
            low: Low price
            high: High price
            
        Returns:
            Tuple of (low, high) as Decimals
            
        Raises:
            StockValidationError: If range is invalid
        """
        low_decimal = cls.validate_price(low, "low price")
        high_decimal = cls.validate_price(high, "high price")
        
        if low_decimal > high_decimal:
            raise StockValidationError(f"Low price ({low_decimal}) cannot be higher than high price ({high_decimal})")
        
        return low_decimal, high_decimal


class VolumeValidator:
    """Validator for volume data."""
    
    @classmethod
    def validate_volume(cls, volume: Union[str, int], field_name: str = "volume") -> int:
        """
        Validate volume data.
        
        Args:
            volume: Volume to validate
            field_name: Name of the field for error messages
            
        Returns:
            Validated volume as int
            
        Raises:
            StockValidationError: If volume is invalid
        """
        if volume is None:
            raise StockValidationError(f"{field_name} cannot be None")
        
        try:
            int_volume = int(volume)
        except (ValueError, TypeError):
            raise StockValidationError(f"Invalid {field_name}: {volume}")
        
        if int_volume < 0:
            raise StockValidationError(f"{field_name} cannot be negative: {int_volume}")
        
        if int_volume > 10_000_000_000:  # 10 billion shares reasonable limit
            raise StockValidationError(f"{field_name} too high: {int_volume}")
        
        return int_volume


class DateValidator:
    """Validator for date data."""
    
    @classmethod
    def validate_date(cls, date_value: Union[str, datetime], field_name: str = "date") -> datetime:
        """
        Validate and convert date.
        
        Args:
            date_value: Date to validate
            field_name: Name of the field for error messages
            
        Returns:
            Validated datetime
            
        Raises:
            StockValidationError: If date is invalid
        """
        if date_value is None:
            raise StockValidationError(f"{field_name} cannot be None")
        
        if isinstance(date_value, datetime):
            return date_value
        
        if isinstance(date_value, str):
            # Try common date formats
            formats = [
                "%Y-%m-%d",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue
            
            raise StockValidationError(f"Invalid {field_name} format: {date_value}")
        
        raise StockValidationError(f"Invalid {field_name} type: {type(date_value)}")
    
    @classmethod
    def validate_date_range(
        cls, 
        start_date: Union[str, datetime], 
        end_date: Union[str, datetime]
    ) -> tuple[datetime, datetime]:
        """
        Validate a date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Tuple of (start_date, end_date) as datetime objects
            
        Raises:
            StockValidationError: If date range is invalid
        """
        start_dt = cls.validate_date(start_date, "start date")
        end_dt = cls.validate_date(end_date, "end date")
        
        if start_dt > end_dt:
            raise StockValidationError(f"Start date ({start_dt}) cannot be after end date ({end_dt})")
        
        return start_dt, end_dt


class OrderValidator:
    """Validator for trading orders."""
    
    VALID_ACTIONS = {"BUY", "SELL"}
    VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP", "STOP_LIMIT"}
    VALID_TIME_IN_FORCE = {"DAY", "GTC", "IOC", "FOK"}
    
    @classmethod
    def validate_order_data(cls, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate complete order data.
        
        Args:
            order_data: Order data to validate
            
        Returns:
            Validated order data
            
        Raises:
            StockValidationError: If order data is invalid
        """
        validated = {}
        
        # Required fields
        required_fields = ["symbol", "action", "quantity", "order_type"]
        for field in required_fields:
            if field not in order_data:
                raise StockValidationError(f"Missing required field: {field}")
        
        # Validate symbol
        validated["symbol"] = StockSymbolValidator.validate_symbol(order_data["symbol"])
        
        # Validate action
        action = str(order_data["action"]).upper()
        if action not in cls.VALID_ACTIONS:
            raise StockValidationError(f"Invalid action: {action}. Must be one of {cls.VALID_ACTIONS}")
        validated["action"] = action
        
        # Validate quantity
        validated["quantity"] = VolumeValidator.validate_volume(order_data["quantity"], "quantity")
        if validated["quantity"] <= 0:
            raise StockValidationError("Quantity must be positive")
        
        # Validate order type
        order_type = str(order_data["order_type"]).upper()
        if order_type not in cls.VALID_ORDER_TYPES:
            raise StockValidationError(f"Invalid order type: {order_type}. Must be one of {cls.VALID_ORDER_TYPES}")
        validated["order_type"] = order_type
        
        # Validate prices based on order type
        if order_type in ["LIMIT", "STOP_LIMIT"] and "limit_price" not in order_data:
            raise StockValidationError(f"{order_type} orders require limit_price")
        
        if order_type in ["STOP", "STOP_LIMIT"] and "stop_price" not in order_data:
            raise StockValidationError(f"{order_type} orders require stop_price")
        
        # Validate optional price fields
        for price_field in ["limit_price", "stop_price", "stop_loss", "take_profit"]:
            if price_field in order_data and order_data[price_field] is not None:
                validated[price_field] = PriceValidator.validate_price(
                    order_data[price_field], 
                    price_field
                )
        
        # Validate time in force
        if "time_in_force" in order_data:
            tif = str(order_data["time_in_force"]).upper()
            if tif not in cls.VALID_TIME_IN_FORCE:
                raise StockValidationError(f"Invalid time_in_force: {tif}. Must be one of {cls.VALID_TIME_IN_FORCE}")
            validated["time_in_force"] = tif
        
        # Copy other fields
        for field in ["all_or_none", "dry_run", "strategy", "notes"]:
            if field in order_data:
                validated[field] = order_data[field]
        
        return validated


class AnalysisValidator:
    """Validator for analysis parameters."""
    
    VALID_ANALYSIS_TYPES = {"comprehensive", "technical", "fundamental", "quick"}
    VALID_RISK_TOLERANCES = {"conservative", "moderate", "aggressive"}
    VALID_INVESTMENT_HORIZONS = {"short_term", "medium_term", "long_term"}
    
    @classmethod
    def validate_analysis_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate analysis parameters.
        
        Args:
            params: Analysis parameters to validate
            
        Returns:
            Validated parameters
            
        Raises:
            StockValidationError: If parameters are invalid
        """
        validated = {}
        
        # Validate symbol
        if "symbol" not in params:
            raise StockValidationError("Missing required field: symbol")
        validated["symbol"] = StockSymbolValidator.validate_symbol(params["symbol"])
        
        # Validate analysis type
        analysis_type = params.get("analysis_type", "comprehensive")
        if analysis_type not in cls.VALID_ANALYSIS_TYPES:
            raise StockValidationError(f"Invalid analysis_type: {analysis_type}. Must be one of {cls.VALID_ANALYSIS_TYPES}")
        validated["analysis_type"] = analysis_type
        
        # Validate risk tolerance
        risk_tolerance = params.get("risk_tolerance", "moderate")
        if risk_tolerance not in cls.VALID_RISK_TOLERANCES:
            raise StockValidationError(f"Invalid risk_tolerance: {risk_tolerance}. Must be one of {cls.VALID_RISK_TOLERANCES}")
        validated["risk_tolerance"] = risk_tolerance
        
        # Validate investment horizon
        investment_horizon = params.get("investment_horizon", "medium_term")
        if investment_horizon not in cls.VALID_INVESTMENT_HORIZONS:
            raise StockValidationError(f"Invalid investment_horizon: {investment_horizon}. Must be one of {cls.VALID_INVESTMENT_HORIZONS}")
        validated["investment_horizon"] = investment_horizon
        
        return validated


class DataIntegrityValidator:
    """Validator for data integrity checks."""
    
    @classmethod
    def validate_stock_price_data(cls, price_data: Dict[str, Any]) -> bool:
        """
        Validate stock price data integrity.
        
        Args:
            price_data: Price data to validate
            
        Returns:
            True if data is valid
            
        Raises:
            StockValidationError: If data integrity is compromised
        """
        required_fields = ["open", "high", "low", "close", "volume"]
        
        for field in required_fields:
            if field not in price_data:
                raise StockValidationError(f"Missing required price field: {field}")
        
        # Validate price relationships
        open_price = PriceValidator.validate_price(price_data["open"], "open")
        high_price = PriceValidator.validate_price(price_data["high"], "high")
        low_price = PriceValidator.validate_price(price_data["low"], "low")
        close_price = PriceValidator.validate_price(price_data["close"], "close")
        
        # High should be the highest
        if high_price < max(open_price, close_price, low_price):
            raise StockValidationError("High price should be the highest value")
        
        # Low should be the lowest
        if low_price > min(open_price, close_price, high_price):
            raise StockValidationError("Low price should be the lowest value")
        
        # Open and close should be within high-low range
        if not (low_price <= open_price <= high_price):
            raise StockValidationError("Open price should be within high-low range")
        
        if not (low_price <= close_price <= high_price):
            raise StockValidationError("Close price should be within high-low range")
        
        # Validate volume
        VolumeValidator.validate_volume(price_data["volume"])
        
        return True
    
    @classmethod
    def validate_technical_indicator(cls, indicator_data: Dict[str, Any], indicator_name: str) -> bool:
        """
        Validate technical indicator data.
        
        Args:
            indicator_data: Indicator data to validate
            indicator_name: Name of the indicator
            
        Returns:
            True if data is valid
            
        Raises:
            StockValidationError: If indicator data is invalid
        """
        if not isinstance(indicator_data, dict):
            raise StockValidationError(f"Invalid {indicator_name} data format")
        
        # Common validations for all indicators
        if "latest_value" in indicator_data:
            try:
                value = float(indicator_data["latest_value"])
                
                # Indicator-specific validations
                if indicator_name == "RSI":
                    if not (0 <= value <= 100):
                        raise StockValidationError(f"RSI value must be between 0 and 100: {value}")
                
                elif indicator_name in ["SMA", "EMA"]:
                    if value <= 0:
                        raise StockValidationError(f"{indicator_name} value must be positive: {value}")
                
            except (ValueError, TypeError):
                raise StockValidationError(f"Invalid {indicator_name} value: {indicator_data['latest_value']}")
        
        return True 