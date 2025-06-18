"""
Comprehensive data models for the stock agent.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union, Literal
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator
from uuid import uuid4, UUID


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderAction(str, Enum):
    """Order action enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class Recommendation(str, Enum):
    """Investment recommendation enumeration."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class RiskLevel(str, Enum):
    """Risk level enumeration."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class AnalysisType(str, Enum):
    """Analysis type enumeration."""
    COMPREHENSIVE = "comprehensive"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    QUICK = "quick"


class RiskTolerance(str, Enum):
    """Risk tolerance enumeration."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class InvestmentHorizon(str, Enum):
    """Investment horizon enumeration."""
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class BaseStockModel(BaseModel):
    """Base model for all stock-related data."""
    
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v),
        }


class TechnicalIndicator(BaseModel):
    """Technical indicator data model."""
    
    name: str
    value: float
    timestamp: datetime
    period: Optional[int] = None
    interpretation: Optional[str] = None
    signal: Optional[str] = None  # "BUY", "SELL", "NEUTRAL"


class StockPrice(BaseModel):
    """Stock price data model."""
    
    symbol: str
    timestamp: datetime
    open: Decimal = Field(..., decimal_places=4)
    high: Decimal = Field(..., decimal_places=4)
    low: Decimal = Field(..., decimal_places=4)
    close: Decimal = Field(..., decimal_places=4)
    volume: int = Field(..., ge=0)
    adjusted_close: Optional[Decimal] = Field(None, decimal_places=4)
    
    @validator('high')
    def high_must_be_highest(cls, v, values):
        if 'low' in values and v < values['low']:
            raise ValueError('High must be greater than or equal to low')
        return v
    
    @validator('open', 'close')
    def prices_within_range(cls, v, values):
        if 'high' in values and 'low' in values:
            if not (values['low'] <= v <= values['high']):
                raise ValueError('Open and close must be within high-low range')
        return v


class CompanyInfo(BaseModel):
    """Enhanced company information model."""
    
    symbol: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    currency: str = "USD"
    
    # Financial metrics
    market_cap: Optional[Decimal] = Field(None, ge=0)
    enterprise_value: Optional[Decimal] = None
    pe_ratio: Optional[Decimal] = Field(None, ge=0)
    peg_ratio: Optional[Decimal] = None
    price_to_book: Optional[Decimal] = Field(None, ge=0)
    price_to_sales: Optional[Decimal] = Field(None, ge=0)
    
    # Per-share metrics
    eps: Optional[Decimal] = None
    book_value_per_share: Optional[Decimal] = None
    dividend_per_share: Optional[Decimal] = Field(None, ge=0)
    dividend_yield: Optional[Decimal] = Field(None, ge=0, le=1)
    
    # Growth metrics
    revenue_growth: Optional[Decimal] = None
    earnings_growth: Optional[Decimal] = None
    
    # Price ranges
    week_52_high: Optional[Decimal] = Field(None, ge=0)
    week_52_low: Optional[Decimal] = Field(None, ge=0)
    
    # Additional info
    description: Optional[str] = None
    employees: Optional[int] = Field(None, ge=0)
    founded: Optional[int] = None
    
    @validator('week_52_high')
    def high_greater_than_low(cls, v, values):
        if v is not None and 'week_52_low' in values and values['week_52_low'] is not None:
            if v < values['week_52_low']:
                raise ValueError('52-week high must be greater than 52-week low')
        return v


class AnalysisScores(BaseModel):
    """Analysis scores breakdown."""
    
    overall: float = Field(..., ge=0, le=1)
    technical: Optional[float] = Field(None, ge=0, le=1)
    fundamental: Optional[float] = Field(None, ge=0, le=1)
    sentiment: Optional[float] = Field(None, ge=0, le=1)
    momentum: Optional[float] = Field(None, ge=0, le=1)


class PriceTargets(BaseModel):
    """Price target information."""
    
    target_price: Optional[Decimal] = Field(None, ge=0)
    stop_loss: Optional[Decimal] = Field(None, ge=0)
    take_profit: Optional[Decimal] = Field(None, ge=0)
    support_level: Optional[Decimal] = Field(None, ge=0)
    resistance_level: Optional[Decimal] = Field(None, ge=0)
    
    # Analyst targets
    analyst_high: Optional[Decimal] = Field(None, ge=0)
    analyst_low: Optional[Decimal] = Field(None, ge=0)
    analyst_mean: Optional[Decimal] = Field(None, ge=0)
    analyst_count: Optional[int] = Field(None, ge=0)


class AnalysisResult(BaseStockModel):
    """Comprehensive stock analysis result model."""
    
    symbol: str
    analysis_type: AnalysisType
    recommendation: Recommendation
    confidence_score: float = Field(..., ge=0, le=1)
    risk_level: RiskLevel
    
    # Analysis context
    risk_tolerance: RiskTolerance
    investment_horizon: InvestmentHorizon
    
    # Detailed scores
    scores: AnalysisScores
    
    # Price information
    current_price: Decimal = Field(..., ge=0)
    price_targets: PriceTargets
    
    # Technical indicators
    technical_indicators: Dict[str, TechnicalIndicator] = Field(default_factory=dict)
    
    # Analysis details
    reasoning: str
    key_factors: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    
    # Market context
    market_conditions: Optional[str] = None
    sector_performance: Optional[str] = None
    
    # Metadata
    data_sources: List[str] = Field(default_factory=list)
    analysis_duration: Optional[float] = None  # seconds
    
    @validator('confidence_score')
    def confidence_matches_recommendation(cls, v, values):
        if 'recommendation' in values:
            rec = values['recommendation']
            if rec in [Recommendation.STRONG_BUY, Recommendation.STRONG_SELL] and v < 0.8:
                raise ValueError('Strong recommendations require high confidence (>0.8)')
        return v


class TradeOrder(BaseStockModel):
    """Enhanced trading order model."""
    
    symbol: str
    action: OrderAction
    quantity: int = Field(..., gt=0)
    order_type: OrderType
    
    # Price information
    limit_price: Optional[Decimal] = Field(None, ge=0)
    stop_price: Optional[Decimal] = Field(None, ge=0)
    
    # Risk management
    stop_loss: Optional[Decimal] = Field(None, ge=0)
    take_profit: Optional[Decimal] = Field(None, ge=0)
    
    # Order settings
    time_in_force: str = "DAY"  # DAY, GTC, IOC, FOK
    all_or_none: bool = False
    
    # Execution details
    order_id: Optional[str] = None
    parent_order_id: Optional[str] = None
    
    # Metadata
    strategy: Optional[str] = None
    notes: Optional[str] = None
    dry_run: bool = False
    
    @root_validator
    def validate_order_prices(cls, values):
        order_type = values.get('order_type')
        limit_price = values.get('limit_price')
        stop_price = values.get('stop_price')
        
        if order_type == OrderType.LIMIT and limit_price is None:
            raise ValueError('Limit price required for LIMIT orders')
        
        if order_type == OrderType.STOP and stop_price is None:
            raise ValueError('Stop price required for STOP orders')
        
        if order_type == OrderType.STOP_LIMIT:
            if limit_price is None or stop_price is None:
                raise ValueError('Both limit and stop prices required for STOP_LIMIT orders')
        
        return values


class TradeExecution(BaseModel):
    """Trade execution details."""
    
    execution_id: str
    timestamp: datetime
    price: Decimal = Field(..., ge=0)
    quantity: int = Field(..., gt=0)
    commission: Decimal = Field(default=Decimal('0'), ge=0)
    fees: Decimal = Field(default=Decimal('0'), ge=0)
    
    # Execution venue
    exchange: Optional[str] = None
    liquidity_flag: Optional[str] = None  # "A" (Added), "R" (Removed)


class TradeResult(BaseStockModel):
    """Comprehensive trade execution result model."""
    
    order_id: str
    symbol: str
    action: OrderAction
    order_type: OrderType
    status: OrderStatus
    
    # Quantities
    requested_quantity: int = Field(..., gt=0)
    filled_quantity: int = Field(default=0, ge=0)
    remaining_quantity: int = Field(default=0, ge=0)
    
    # Pricing
    average_fill_price: Optional[Decimal] = Field(None, ge=0)
    total_cost: Optional[Decimal] = Field(None, ge=0)
    
    # Fees and costs
    commission: Decimal = Field(default=Decimal('0'), ge=0)
    fees: Decimal = Field(default=Decimal('0'), ge=0)
    
    # Execution details
    executions: List[TradeExecution] = Field(default_factory=list)
    
    # Timestamps
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    # Error handling
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # Risk management
    risk_checks_passed: bool = True
    risk_warnings: List[str] = Field(default_factory=list)
    
    @validator('remaining_quantity')
    def remaining_quantity_valid(cls, v, values):
        if 'requested_quantity' in values and 'filled_quantity' in values:
            expected = values['requested_quantity'] - values['filled_quantity']
            if v != expected:
                raise ValueError('Remaining quantity must equal requested minus filled')
        return v


class Portfolio(BaseModel):
    """Portfolio information model."""
    
    account_id: str
    total_value: Decimal = Field(..., ge=0)
    cash_balance: Decimal = Field(..., ge=0)
    buying_power: Decimal = Field(..., ge=0)
    
    # Performance metrics
    day_pnl: Decimal = Field(default=Decimal('0'))
    total_pnl: Decimal = Field(default=Decimal('0'))
    
    # Risk metrics
    portfolio_beta: Optional[float] = None
    var_95: Optional[Decimal] = None  # Value at Risk (95%)
    
    # Timestamps
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class Position(BaseModel):
    """Stock position model."""
    
    symbol: str
    quantity: int
    average_cost: Decimal = Field(..., ge=0)
    current_price: Decimal = Field(..., ge=0)
    market_value: Decimal = Field(..., ge=0)
    
    # P&L
    unrealized_pnl: Decimal = Field(default=Decimal('0'))
    realized_pnl: Decimal = Field(default=Decimal('0'))
    
    # Position details
    side: Literal["LONG", "SHORT"] = "LONG"
    
    # Timestamps
    opened_at: datetime
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class MarketData(BaseModel):
    """Real-time market data model."""
    
    symbol: str
    timestamp: datetime
    
    # Price data
    bid: Optional[Decimal] = Field(None, ge=0)
    ask: Optional[Decimal] = Field(None, ge=0)
    last: Optional[Decimal] = Field(None, ge=0)
    
    # Size data
    bid_size: Optional[int] = Field(None, ge=0)
    ask_size: Optional[int] = Field(None, ge=0)
    last_size: Optional[int] = Field(None, ge=0)
    
    # Daily statistics
    open: Optional[Decimal] = Field(None, ge=0)
    high: Optional[Decimal] = Field(None, ge=0)
    low: Optional[Decimal] = Field(None, ge=0)
    close: Optional[Decimal] = Field(None, ge=0)
    volume: Optional[int] = Field(None, ge=0)
    
    # Calculated fields
    spread: Optional[Decimal] = Field(None, ge=0)
    mid_price: Optional[Decimal] = Field(None, ge=0)
    
    @root_validator
    def calculate_derived_fields(cls, values):
        bid = values.get('bid')
        ask = values.get('ask')
        
        if bid is not None and ask is not None:
            values['spread'] = ask - bid
            values['mid_price'] = (bid + ask) / 2
        
        return values


class NewsItem(BaseModel):
    """News item model for sentiment analysis."""
    
    title: str
    summary: Optional[str] = None
    url: Optional[str] = None
    source: str
    published_at: datetime
    
    # Sentiment analysis
    sentiment_score: Optional[float] = Field(None, ge=-1, le=1)
    sentiment_label: Optional[Literal["positive", "negative", "neutral"]] = None
    
    # Relevance
    relevance_score: Optional[float] = Field(None, ge=0, le=1)
    symbols_mentioned: List[str] = Field(default_factory=list)
    
    # Categories
    categories: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list) 