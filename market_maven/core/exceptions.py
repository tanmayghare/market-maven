"""
Custom exceptions for the stock agent.
"""

from typing import Optional, Dict, Any


class StockAgentError(Exception):
    """Base exception for all stock agent errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class DataFetchError(StockAgentError):
    """Exception raised when data fetching fails."""
    
    def __init__(
        self, 
        message: str, 
        symbol: Optional[str] = None,
        source: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.symbol = symbol
        self.source = source


class AnalysisError(StockAgentError):
    """Exception raised when stock analysis fails."""
    
    def __init__(
        self, 
        message: str, 
        symbol: Optional[str] = None,
        analysis_type: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.symbol = symbol
        self.analysis_type = analysis_type


class TradingError(StockAgentError):
    """Exception raised when trading operations fail."""
    
    def __init__(
        self, 
        message: str, 
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.symbol = symbol
        self.order_id = order_id


class ConfigurationError(StockAgentError):
    """Exception raised when configuration is invalid."""
    pass


class ValidationError(StockAgentError):
    """Exception raised when input validation fails."""
    pass


class RateLimitError(StockAgentError):
    """Exception raised when API rate limits are exceeded."""
    
    def __init__(
        self, 
        message: str, 
        retry_after: Optional[int] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class SecurityError(StockAgentError):
    """Exception raised when security-related operations fail."""
    pass 