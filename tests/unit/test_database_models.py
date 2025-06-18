"""
Unit tests for database models.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from market_maven.core.database import Base
from market_maven.models.db_models import (
    StockSymbol, StockPriceHistory, CompanyInfoDB, AnalysisResultDB,
    TradeOrderDB, TradeExecutionDB, PortfolioSnapshot, AlertConfiguration,
    AuditLog, User, APIKey, OrderStatus, OrderType, OrderAction,
    Recommendation, RiskLevel, AnalysisType
)


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()


class TestStockSymbol:
    """Test StockSymbol model."""
    
    def test_create_stock_symbol(self, db_session):
        """Test creating a stock symbol."""
        stock = StockSymbol(
            symbol="AAPL",
            name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            country="US",
            currency="USD",
            exchange="NASDAQ"
        )
        
        db_session.add(stock)
        db_session.commit()
        
        assert stock.id is not None
        assert stock.symbol == "AAPL"
        assert stock.name == "Apple Inc."
        assert stock.sector == "Technology"
        assert stock.is_active is True
        assert stock.created_at is not None
    
    def test_unique_symbol_constraint(self, db_session):
        """Test that symbols must be unique."""
        stock1 = StockSymbol(symbol="AAPL", name="Apple Inc.")
        stock2 = StockSymbol(symbol="AAPL", name="Apple Inc. Duplicate")
        
        db_session.add(stock1)
        db_session.commit()
        
        db_session.add(stock2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()


class TestStockPriceHistory:
    """Test StockPriceHistory model."""
    
    def test_create_price_history(self, db_session):
        """Test creating stock price history."""
        # Create stock symbol first
        stock = StockSymbol(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()
        
        price_history = StockPriceHistory(
            stock_id=stock.id,
            timestamp=datetime.now(),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("152.00"),
            volume=1000000
        )
        
        db_session.add(price_history)
        db_session.commit()
        
        assert price_history.id is not None
        assert price_history.stock_id == stock.id
        assert price_history.open == Decimal("150.00")
        assert price_history.high == Decimal("155.00")
        assert price_history.low == Decimal("149.00")
        assert price_history.close == Decimal("152.00")
        assert price_history.volume == 1000000
    
    def test_price_history_relationship(self, db_session):
        """Test relationship between stock and price history."""
        stock = StockSymbol(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()
        
        price_history = StockPriceHistory(
            stock_id=stock.id,
            timestamp=datetime.now(),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("152.00"),
            volume=1000000
        )
        
        db_session.add(price_history)
        db_session.commit()
        
        # Test relationship
        assert price_history.stock == stock
        assert price_history in stock.price_history


class TestCompanyInfoDB:
    """Test CompanyInfoDB model."""
    
    def test_create_company_info(self, db_session):
        """Test creating company information."""
        stock = StockSymbol(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()
        
        company_info = CompanyInfoDB(
            stock_id=stock.id,
            market_cap=Decimal("2500000000000"),  # 2.5T
            pe_ratio=Decimal("25.5"),
            eps=Decimal("6.15"),
            dividend_yield=Decimal("0.0045"),
            description="Apple Inc. designs, manufactures, and markets smartphones.",
            employees=150000
        )
        
        db_session.add(company_info)
        db_session.commit()
        
        assert company_info.id is not None
        assert company_info.stock_id == stock.id
        assert company_info.market_cap == Decimal("2500000000000")
        assert company_info.pe_ratio == Decimal("25.5")
        assert company_info.eps == Decimal("6.15")
        assert company_info.dividend_yield == Decimal("0.0045")
        assert "Apple Inc." in company_info.description
        assert company_info.employees == 150000


class TestAnalysisResultDB:
    """Test AnalysisResultDB model."""
    
    def test_create_analysis_result(self, db_session):
        """Test creating analysis result."""
        stock = StockSymbol(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()
        
        analysis = AnalysisResultDB(
            stock_id=stock.id,
            analysis_type=AnalysisType.COMPREHENSIVE,
            recommendation=Recommendation.BUY,
            confidence_score=0.85,
            risk_level=RiskLevel.MEDIUM,
            risk_tolerance="moderate",
            investment_horizon="medium_term",
            overall_score=0.82,
            technical_score=0.78,
            fundamental_score=0.86,
            current_price=Decimal("152.50"),
            target_price=Decimal("165.00"),
            reasoning="Strong fundamentals with positive technical indicators."
        )
        
        db_session.add(analysis)
        db_session.commit()
        
        assert analysis.id is not None
        assert analysis.stock_id == stock.id
        assert analysis.analysis_type == AnalysisType.COMPREHENSIVE
        assert analysis.recommendation == Recommendation.BUY
        assert analysis.confidence_score == 0.85
        assert analysis.risk_level == RiskLevel.MEDIUM
        assert analysis.overall_score == 0.82
        assert analysis.current_price == Decimal("152.50")
        assert "Strong fundamentals" in analysis.reasoning
    
    def test_analysis_expiration(self, db_session):
        """Test analysis expiration property."""
        stock = StockSymbol(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()
        
        # Create expired analysis
        expired_analysis = AnalysisResultDB(
            stock_id=stock.id,
            analysis_type=AnalysisType.QUICK,
            recommendation=Recommendation.HOLD,
            confidence_score=0.6,
            risk_level=RiskLevel.LOW,
            risk_tolerance="conservative",
            investment_horizon="short_term",
            overall_score=0.6,
            current_price=Decimal("150.00"),
            reasoning="Neutral outlook.",
            expires_at=datetime.now() - timedelta(hours=1)  # Expired 1 hour ago
        )
        
        db_session.add(expired_analysis)
        db_session.commit()
        
        assert expired_analysis.is_expired is True
        
        # Create non-expired analysis
        fresh_analysis = AnalysisResultDB(
            stock_id=stock.id,
            analysis_type=AnalysisType.QUICK,
            recommendation=Recommendation.HOLD,
            confidence_score=0.6,
            risk_level=RiskLevel.LOW,
            risk_tolerance="conservative",
            investment_horizon="short_term",
            overall_score=0.6,
            current_price=Decimal("150.00"),
            reasoning="Neutral outlook.",
            expires_at=datetime.now() + timedelta(hours=1)  # Expires in 1 hour
        )
        
        db_session.add(fresh_analysis)
        db_session.commit()
        
        assert fresh_analysis.is_expired is False


class TestTradeOrderDB:
    """Test TradeOrderDB model."""
    
    def test_create_trade_order(self, db_session):
        """Test creating a trade order."""
        stock = StockSymbol(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()
        
        order = TradeOrderDB(
            stock_id=stock.id,
            action=OrderAction.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            stop_loss=Decimal("145.00"),
            take_profit=Decimal("160.00"),
            broker_order_id="12345",
            strategy="momentum_breakout",
            dry_run=False
        )
        
        db_session.add(order)
        db_session.commit()
        
        assert order.id is not None
        assert order.stock_id == stock.id
        assert order.action == OrderAction.BUY
        assert order.quantity == 100
        assert order.order_type == OrderType.MARKET
        assert order.status == OrderStatus.PENDING
        assert order.stop_loss == Decimal("145.00")
        assert order.take_profit == Decimal("160.00")
        assert order.broker_order_id == "12345"
        assert order.strategy == "momentum_breakout"
        assert order.dry_run is False
    
    def test_order_execution_relationship(self, db_session):
        """Test relationship between orders and executions."""
        stock = StockSymbol(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()
        
        order = TradeOrderDB(
            stock_id=stock.id,
            action=OrderAction.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED
        )
        
        db_session.add(order)
        db_session.commit()
        
        execution = TradeExecutionDB(
            order_id=order.id,
            execution_id="EXEC123",
            timestamp=datetime.now(),
            price=Decimal("152.50"),
            quantity=100,
            commission=Decimal("1.00")
        )
        
        db_session.add(execution)
        db_session.commit()
        
        # Test relationship
        assert execution.order == order
        assert execution in order.executions


class TestUser:
    """Test User model."""
    
    def test_create_user(self, db_session):
        """Test creating a user."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_here",
            full_name="Test User",
            is_active=True,
            is_superuser=False
        )
        
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.is_active is True
        assert user.is_superuser is False
        assert user.created_at is not None
    
    def test_unique_username_email(self, db_session):
        """Test that username and email must be unique."""
        user1 = User(
            username="testuser",
            email="test@example.com",
            hashed_password="password1"
        )
        
        user2 = User(
            username="testuser",  # Same username
            email="different@example.com",
            hashed_password="password2"
        )
        
        db_session.add(user1)
        db_session.commit()
        
        db_session.add(user2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()


class TestAPIKey:
    """Test APIKey model."""
    
    def test_create_api_key(self, db_session):
        """Test creating an API key."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password"
        )
        
        db_session.add(user)
        db_session.commit()
        
        api_key = APIKey(
            user_id=user.id,
            key_hash="hashed_api_key",
            name="Test API Key",
            scopes=["read:analysis", "write:trades"],
            rate_limit_per_hour=100,
            is_active=True
        )
        
        db_session.add(api_key)
        db_session.commit()
        
        assert api_key.id is not None
        assert api_key.user_id == user.id
        assert api_key.key_hash == "hashed_api_key"
        assert api_key.name == "Test API Key"
        assert api_key.scopes == ["read:analysis", "write:trades"]
        assert api_key.rate_limit_per_hour == 100
        assert api_key.is_active is True
    
    def test_api_key_user_relationship(self, db_session):
        """Test relationship between API key and user."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password"
        )
        
        db_session.add(user)
        db_session.commit()
        
        api_key = APIKey(
            user_id=user.id,
            key_hash="hashed_api_key",
            name="Test API Key"
        )
        
        db_session.add(api_key)
        db_session.commit()
        
        # Test relationship
        assert api_key.user == user
        assert api_key in user.api_keys


class TestAuditLog:
    """Test AuditLog model."""
    
    def test_create_audit_log(self, db_session):
        """Test creating an audit log entry."""
        audit_log = AuditLog(
            action_type="stock_analysis",
            action_details={
                "symbol": "AAPL",
                "analysis_type": "comprehensive",
                "user_id": "user123"
            },
            user_id="user123",
            session_id="session456",
            ip_address="192.168.1.1",
            status="success",
            duration_ms=1500
        )
        
        db_session.add(audit_log)
        db_session.commit()
        
        assert audit_log.id is not None
        assert audit_log.action_type == "stock_analysis"
        assert audit_log.action_details["symbol"] == "AAPL"
        assert audit_log.user_id == "user123"
        assert audit_log.session_id == "session456"
        assert audit_log.ip_address == "192.168.1.1"
        assert audit_log.status == "success"
        assert audit_log.duration_ms == 1500
        assert audit_log.created_at is not None 