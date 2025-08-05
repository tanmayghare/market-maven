"""
SQLAlchemy database models for persistent storage.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Numeric, Boolean, 
    DateTime, Text, JSON, ForeignKey, Index, UniqueConstraint, TypeDecorator, CHAR
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.hybrid import hybrid_property
import uuid

from market_maven.core.database import Base
from sqlalchemy import Enum as SQLEnum


# Custom UUID type that works with both PostgreSQL and SQLite
class UUID(TypeDecorator):
    """Platform-independent UUID type.
    
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36) for other databases.
    """
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            else:
                return str(uuid.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            else:
                return value

# Define enums directly to avoid circular imports
import enum

class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"

class OrderAction(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class Recommendation(str, enum.Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"

class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"

class AnalysisType(str, enum.Enum):
    COMPREHENSIVE = "comprehensive"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    QUICK = "quick"


class StockSymbol(Base):
    """Stock symbol master data."""
    __tablename__ = "stock_symbols"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100))
    industry = Column(String(100))
    country = Column(String(50))
    currency = Column(String(10), default="USD")
    exchange = Column(String(50))
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    price_history = relationship("StockPriceHistory", back_populates="stock", cascade="all, delete-orphan")
    company_info = relationship("CompanyInfoDB", back_populates="stock", uselist=False, cascade="all, delete-orphan")
    analyses = relationship("AnalysisResultDB", back_populates="stock", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_stock_symbol_active', 'symbol', 'is_active'),
    )


class StockPriceHistory(Base):
    """Historical stock price data."""
    __tablename__ = "stock_price_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stock_symbols.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    # Price data
    open = Column(Numeric(12, 4), nullable=False)
    high = Column(Numeric(12, 4), nullable=False)
    low = Column(Numeric(12, 4), nullable=False)
    close = Column(Numeric(12, 4), nullable=False)
    adjusted_close = Column(Numeric(12, 4))
    volume = Column(Integer, nullable=False)
    
    # Technical indicators (cached)
    sma_20 = Column(Numeric(12, 4))
    sma_50 = Column(Numeric(12, 4))
    sma_200 = Column(Numeric(12, 4))
    rsi_14 = Column(Float)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    stock = relationship("StockSymbol", back_populates="price_history")
    
    __table_args__ = (
        UniqueConstraint('stock_id', 'timestamp', name='uq_stock_price_timestamp'),
        Index('idx_price_history_lookup', 'stock_id', 'timestamp'),
        Index('idx_price_history_timestamp', 'timestamp'),
    )


class CompanyInfoDB(Base):
    """Company fundamental information."""
    __tablename__ = "company_info"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stock_symbols.id"), unique=True, nullable=False)
    
    # Financial metrics
    market_cap = Column(Numeric(20, 2))
    enterprise_value = Column(Numeric(20, 2))
    pe_ratio = Column(Numeric(10, 2))
    peg_ratio = Column(Numeric(10, 2))
    price_to_book = Column(Numeric(10, 2))
    price_to_sales = Column(Numeric(10, 2))
    
    # Per-share metrics
    eps = Column(Numeric(10, 2))
    book_value_per_share = Column(Numeric(10, 2))
    dividend_per_share = Column(Numeric(10, 2))
    dividend_yield = Column(Numeric(6, 4))
    
    # Growth metrics
    revenue_growth = Column(Numeric(6, 4))
    earnings_growth = Column(Numeric(6, 4))
    
    # Price ranges
    week_52_high = Column(Numeric(12, 4))
    week_52_low = Column(Numeric(12, 4))
    
    # Additional info
    description = Column(Text)
    employees = Column(Integer)
    founded = Column(Integer)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    stock = relationship("StockSymbol", back_populates="company_info")


class AnalysisResultDB(Base):
    """Stored analysis results."""
    __tablename__ = "analysis_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stock_symbols.id"), nullable=False)
    
    # Analysis details
    analysis_type = Column(SQLEnum(AnalysisType), nullable=False)
    recommendation = Column(SQLEnum(Recommendation), nullable=False)
    confidence_score = Column(Float, nullable=False)
    risk_level = Column(SQLEnum(RiskLevel), nullable=False)
    
    # Context
    risk_tolerance = Column(String(50), nullable=False)
    investment_horizon = Column(String(50), nullable=False)
    
    # Scores
    overall_score = Column(Float, nullable=False)
    technical_score = Column(Float)
    fundamental_score = Column(Float)
    sentiment_score = Column(Float)
    momentum_score = Column(Float)
    
    # Price targets
    current_price = Column(Numeric(12, 4), nullable=False)
    target_price = Column(Numeric(12, 4))
    stop_loss = Column(Numeric(12, 4))
    take_profit = Column(Numeric(12, 4))
    support_level = Column(Numeric(12, 4))
    resistance_level = Column(Numeric(12, 4))
    
    # Analysis details (JSON)
    technical_indicators = Column(JSON)
    reasoning = Column(Text, nullable=False)
    key_factors = Column(JSON)
    risks = Column(JSON)
    opportunities = Column(JSON)
    
    # Metadata
    analysis_duration = Column(Float)  # seconds
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # When this analysis becomes stale
    
    # Relationships
    stock = relationship("StockSymbol", back_populates="analyses")
    
    __table_args__ = (
        Index('idx_analysis_lookup', 'stock_id', 'analysis_type', 'created_at'),
        Index('idx_analysis_expiry', 'expires_at'),
    )
    
    @hybrid_property
    def is_expired(self):
        """Check if analysis has expired."""
        return self.expires_at is not None and datetime.utcnow() > self.expires_at


class TradeOrderDB(Base):
    """Trade order records."""
    __tablename__ = "trade_orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stock_symbols.id"), nullable=False)
    
    # Order details
    action = Column(SQLEnum(OrderAction), nullable=False)
    quantity = Column(Integer, nullable=False)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    
    # Prices
    limit_price = Column(Numeric(12, 4))
    stop_price = Column(Numeric(12, 4))
    stop_loss = Column(Numeric(12, 4))
    take_profit = Column(Numeric(12, 4))
    
    # Execution details
    average_fill_price = Column(Numeric(12, 4))
    filled_quantity = Column(Integer, default=0)
    commission = Column(Numeric(10, 2), default=0)
    fees = Column(Numeric(10, 2), default=0)
    
    # Order settings
    time_in_force = Column(String(10), default="DAY")
    all_or_none = Column(Boolean, default=False)
    
    # External references
    broker_order_id = Column(String(100), unique=True)
    parent_order_id = Column(UUID(as_uuid=True))
    
    # Metadata
    strategy = Column(String(100))
    notes = Column(Text)
    dry_run = Column(Boolean, default=False)
    
    # Risk management
    risk_checks_passed = Column(Boolean, default=True)
    risk_warnings = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime)
    filled_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    
    # Error handling
    error_message = Column(Text)
    error_code = Column(String(50))
    
    # Relationships
    stock = relationship("StockSymbol")
    executions = relationship("TradeExecutionDB", back_populates="order", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_order_status', 'status', 'created_at'),
        Index('idx_order_stock', 'stock_id', 'status'),
        Index('idx_order_broker', 'broker_order_id'),
    )


class TradeExecutionDB(Base):
    """Individual trade executions."""
    __tablename__ = "trade_executions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("trade_orders.id"), nullable=False)
    
    # Execution details
    execution_id = Column(String(100), unique=True, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    price = Column(Numeric(12, 4), nullable=False)
    quantity = Column(Integer, nullable=False)
    commission = Column(Numeric(10, 2), default=0)
    fees = Column(Numeric(10, 2), default=0)
    
    # Venue information
    exchange = Column(String(50))
    liquidity_flag = Column(String(10))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    order = relationship("TradeOrderDB", back_populates="executions")
    
    __table_args__ = (
        Index('idx_execution_order', 'order_id'),
        Index('idx_execution_timestamp', 'timestamp'),
    )


class PortfolioSnapshot(Base):
    """Portfolio state snapshots."""
    __tablename__ = "portfolio_snapshots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id = Column(String(100), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Portfolio values
    total_value = Column(Numeric(20, 2), nullable=False)
    cash_balance = Column(Numeric(20, 2), nullable=False)
    buying_power = Column(Numeric(20, 2), nullable=False)
    
    # Performance metrics
    day_pnl = Column(Numeric(12, 2), default=0)
    total_pnl = Column(Numeric(12, 2), default=0)
    
    # Risk metrics
    portfolio_beta = Column(Float)
    var_95 = Column(Numeric(12, 2))  # Value at Risk (95%)
    sharpe_ratio = Column(Float)
    
    # Position summary
    positions_count = Column(Integer, default=0)
    positions_data = Column(JSON)  # Detailed position information
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_portfolio_account_time', 'account_id', 'timestamp'),
    )


class AlertConfiguration(Base):
    """User alert configurations."""
    __tablename__ = "alert_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stock_symbols.id"), nullable=False)
    
    # Alert conditions
    alert_type = Column(String(50), nullable=False)  # price_above, price_below, volume_spike, etc.
    threshold_value = Column(Numeric(12, 4))
    comparison_operator = Column(String(10))  # >, <, >=, <=, ==
    
    # Alert settings
    is_active = Column(Boolean, default=True)
    notification_channels = Column(JSON)  # email, sms, webhook, etc.
    
    # Trigger tracking
    last_triggered_at = Column(DateTime)
    trigger_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    stock = relationship("StockSymbol")
    
    __table_args__ = (
        Index('idx_alert_active', 'is_active', 'alert_type'),
        Index('idx_alert_stock', 'stock_id', 'is_active'),
    )


class AuditLog(Base):
    """Audit trail for all system actions."""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Action details
    action_type = Column(String(100), nullable=False)  # analysis, trade, data_fetch, etc.
    action_details = Column(JSON, nullable=False)
    
    # Context
    user_id = Column(String(100))
    session_id = Column(String(100))
    ip_address = Column(String(45))
    
    # Results
    status = Column(String(50), nullable=False)  # success, failure, error
    error_message = Column(Text)
    
    # Performance
    duration_ms = Column(Integer)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index('idx_audit_action_time', 'action_type', 'created_at'),
        Index('idx_audit_user', 'user_id', 'created_at'),
        Index('idx_audit_status', 'status', 'created_at'),
    )


class User(Base):
    """User accounts for authentication."""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # API access
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)


class APIKey(Base):
    """API keys for authentication."""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Key details
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    
    # Permissions
    scopes = Column(JSON)  # ["read:analysis", "write:trades", etc.]
    
    # Rate limiting
    rate_limit_per_hour = Column(Integer, default=1000)
    
    # Validity
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime)
    
    # Usage tracking
    last_used_at = Column(DateTime)
    usage_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    __table_args__ = (
        Index('idx_api_key_active', 'key_hash', 'is_active'),
    ) 