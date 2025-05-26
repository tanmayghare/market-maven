"""
API request and response models.
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from uuid import UUID


class AnalysisRequest(BaseModel):
    """Stock analysis request model."""
    
    symbol: str = Field(..., description="Stock ticker symbol", pattern="^[A-Z]{1,5}$")
    analysis_type: Literal["comprehensive", "technical", "fundamental", "quick"] = Field(
        default="comprehensive",
        description="Type of analysis to perform"
    )
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] = Field(
        default="moderate",
        description="Risk tolerance level"
    )
    investment_horizon: Literal["short_term", "medium_term", "long_term"] = Field(
        default="medium_term",
        description="Investment time horizon"
    )
    
    @validator('symbol')
    def uppercase_symbol(cls, v):
        return v.upper()


class AnalysisResponse(BaseModel):
    """Stock analysis response model."""
    
    status: str
    symbol: str
    analysis_type: str
    recommendation: str
    confidence_score: float = Field(..., ge=0, le=1)
    risk_level: str
    
    # Price information
    current_price: float
    target_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    
    # Analysis details
    reasoning: str
    key_factors: List[str]
    risks: List[str]
    opportunities: List[str]
    
    # Technical indicators
    technical_indicators: Optional[Dict[str, Any]]
    
    # Metadata
    timestamp: datetime
    analysis_duration: Optional[float]


class TradeRequest(BaseModel):
    """Trade execution request model."""
    
    symbol: str = Field(..., description="Stock ticker symbol", pattern="^[A-Z]{1,5}$")
    action: Literal["BUY", "SELL"] = Field(..., description="Trade action")
    quantity: int = Field(..., gt=0, description="Number of shares")
    order_type: Literal["MARKET", "LIMIT", "STOP", "STOP_LIMIT"] = Field(
        default="MARKET",
        description="Order type"
    )
    limit_price: Optional[float] = Field(None, gt=0, description="Limit price for LIMIT orders")
    stop_price: Optional[float] = Field(None, gt=0, description="Stop price for STOP orders")
    stop_loss: Optional[float] = Field(None, gt=0, description="Stop loss price")
    take_profit: Optional[float] = Field(None, gt=0, description="Take profit price")
    time_in_force: Literal["DAY", "GTC", "IOC", "FOK"] = Field(
        default="DAY",
        description="Time in force"
    )
    dry_run: bool = Field(default=True, description="Execute in dry-run mode")
    
    @validator('symbol')
    def uppercase_symbol(cls, v):
        return v.upper()
    
    @validator('limit_price')
    def limit_price_required_for_limit_orders(cls, v, values):
        if values.get('order_type') == 'LIMIT' and v is None:
            raise ValueError('Limit price required for LIMIT orders')
        return v


class TradeResponse(BaseModel):
    """Trade execution response model."""
    
    status: str
    order_id: str
    symbol: str
    action: str
    order_type: str
    
    # Quantities
    requested_quantity: int
    filled_quantity: int
    remaining_quantity: int
    
    # Pricing
    average_fill_price: Optional[float]
    total_cost: Optional[float]
    
    # Fees
    commission: float
    fees: float
    
    # Timestamps
    submitted_at: datetime
    filled_at: Optional[datetime]
    
    # Status details
    order_status: str
    dry_run: bool
    error_message: Optional[str]


class PortfolioResponse(BaseModel):
    """Portfolio information response."""
    
    account_id: str
    total_value: float
    cash_balance: float
    buying_power: float
    
    # Performance
    day_pnl: float
    total_pnl: float
    
    # Positions
    positions: List[Dict[str, Any]]
    
    # Risk metrics
    portfolio_beta: Optional[float]
    var_95: Optional[float]
    sharpe_ratio: Optional[float]
    
    # Metadata
    last_updated: datetime


class HealthResponse(BaseModel):
    """System health check response."""
    
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    environment: str
    
    # Component status
    components: Dict[str, Dict[str, Any]]
    
    # Metrics
    uptime_seconds: float
    total_requests: int
    error_rate: float
    
    # Timestamps
    timestamp: datetime


class ErrorResponse(BaseModel):
    """API error response."""
    
    error: str
    message: str
    details: Optional[Dict[str, Any]]
    request_id: str
    timestamp: datetime


class MarketDataRequest(BaseModel):
    """Market data request model."""
    
    symbols: List[str] = Field(..., description="List of stock symbols")
    data_types: List[Literal["quote", "historical", "news", "fundamentals"]] = Field(
        default=["quote"],
        description="Types of data to fetch"
    )
    period: Optional[str] = Field(None, description="Time period for historical data")
    
    @validator('symbols')
    def uppercase_symbols(cls, v):
        return [s.upper() for s in v]
    
    @validator('symbols')
    def validate_symbol_count(cls, v):
        if len(v) > 50:
            raise ValueError('Maximum 50 symbols allowed per request')
        return v


class MarketDataResponse(BaseModel):
    """Market data response model."""
    
    status: str
    data: Dict[str, Dict[str, Any]]
    metadata: Dict[str, Any]
    timestamp: datetime


class AlertRequest(BaseModel):
    """Alert configuration request."""
    
    symbol: str = Field(..., description="Stock ticker symbol", pattern="^[A-Z]{1,5}$")
    alert_type: Literal["price_above", "price_below", "volume_spike", "rsi_overbought", "rsi_oversold"]
    threshold_value: float
    notification_channels: List[Literal["email", "sms", "webhook"]]
    webhook_url: Optional[str] = None
    
    @validator('symbol')
    def uppercase_symbol(cls, v):
        return v.upper()
    
    @validator('webhook_url')
    def webhook_required_if_channel_selected(cls, v, values):
        if 'webhook' in values.get('notification_channels', []) and not v:
            raise ValueError('Webhook URL required when webhook notification is selected')
        return v


class AlertResponse(BaseModel):
    """Alert configuration response."""
    
    alert_id: UUID
    symbol: str
    alert_type: str
    threshold_value: float
    is_active: bool
    created_at: datetime
    last_triggered_at: Optional[datetime]
    trigger_count: int


class BatchAnalysisRequest(BaseModel):
    """Batch analysis request for multiple symbols."""
    
    symbols: List[str] = Field(..., description="List of stock symbols to analyze")
    analysis_type: Literal["comprehensive", "technical", "fundamental", "quick"] = Field(
        default="quick",
        description="Type of analysis to perform"
    )
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] = Field(
        default="moderate",
        description="Risk tolerance level"
    )
    investment_horizon: Literal["short_term", "medium_term", "long_term"] = Field(
        default="medium_term",
        description="Investment time horizon"
    )
    
    @validator('symbols')
    def uppercase_symbols(cls, v):
        return [s.upper() for s in v]
    
    @validator('symbols')
    def validate_symbol_count(cls, v):
        if len(v) > 20:
            raise ValueError('Maximum 20 symbols allowed for batch analysis')
        return v


class BatchAnalysisResponse(BaseModel):
    """Batch analysis response."""
    
    status: str
    results: List[AnalysisResponse]
    failed_symbols: List[Dict[str, str]]
    total_duration: float
    timestamp: datetime 