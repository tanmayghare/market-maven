"""
FastAPI REST API for the stock agent.
"""

import time
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from market_maven.api.models import (
    AnalysisRequest, AnalysisResponse,
    TradeRequest, TradeResponse,
    PortfolioResponse, HealthResponse,
    ErrorResponse, MarketDataRequest, MarketDataResponse,
    AlertRequest, AlertResponse,
    BatchAnalysisRequest, BatchAnalysisResponse
)
from market_maven.api.auth import (
    get_current_active_user, require_read_analysis,
    require_write_trades, require_read_portfolio,
    AuthService, create_user_tokens
)
from market_maven.agents.market_maven import market_maven
from market_maven.core.database import get_async_db, create_tables
from market_maven.core.cache import cache_manager
from market_maven.core.logging import get_logger
from market_maven.core.metrics import metrics
from market_maven.core.error_handler import error_handler
from market_maven.models.db_models import User
from market_maven.config.settings import settings

logger = get_logger(__name__)

# Application startup time
APP_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Stock Agent API...")
    
    # Initialize database
    await create_tables()
    
    # Initialize cache
    await cache_manager.redis_cache.connect()
    
    # Start metrics server
    if settings.metrics.enable_metrics:
        metrics.start_metrics_server(settings.metrics.metrics_port)
    
    logger.info("Stock Agent API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Stock Agent API...")
    
    # Disconnect cache
    await cache_manager.redis_cache.disconnect()
    
    logger.info("Stock Agent API shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Stock Agent API",
    description="AI-powered stock market intelligence and trading API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins if hasattr(settings.api, 'cors_origins') else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.api.allowed_hosts if hasattr(settings.api, 'allowed_hosts') else ["*"]
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add request ID to all requests."""
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    
    # Add to logging context
    logger.bind(request_id=request_id)
    
    # Process request
    start_time = time.time()
    response = await call_next(request)
    
    # Add response headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(time.time() - start_time)
    
    return response


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message=exc.detail,
            details={"status_code": exc.status_code},
            request_id=getattr(request.state, "request_id", "unknown"),
            timestamp=datetime.utcnow()
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=exc.__class__.__name__,
            message="Internal server error",
            details={"error": str(exc)},
            request_id=getattr(request.state, "request_id", "unknown"),
            timestamp=datetime.utcnow()
        ).dict()
    )


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Check system health status."""
    try:
        health_status = await market_maven.health_check()
        
        # Add system metrics
        uptime = time.time() - APP_START_TIME
        error_stats = error_handler.get_error_stats()
        
        return HealthResponse(
            status="healthy" if health_status["status"] == "healthy" else "degraded",
            version=settings.__version__ if hasattr(settings, '__version__') else "1.0.0",
            environment=settings.environment,
            components=health_status.get("components", {}),
            uptime_seconds=uptime,
            total_requests=error_stats.get("total_errors", 0),
            error_rate=error_stats.get("recent_errors_1h", 0) / max(uptime / 3600, 1),
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="System unhealthy")


# Authentication endpoints
@app.post("/api/v1/auth/login", tags=["Authentication"])
async def login(
    username: str,
    password: str,
    db = Depends(get_async_db)
):
    """Login with username and password."""
    user = await AuthService.authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.commit()
    
    return create_user_tokens(user)


@app.post("/api/v1/auth/refresh", tags=["Authentication"])
async def refresh_token(
    refresh_token: str,
    db = Depends(get_async_db)
):
    """Refresh access token using refresh token."""
    try:
        payload = AuthService.decode_token(refresh_token)
        token_type = payload.get("type")
        
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        user = await AuthService.get_user_by_id(db, user_id)
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user"
            )
        
        return create_user_tokens(user)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


# Analysis endpoints
@app.post("/api/v1/analyze", response_model=AnalysisResponse, tags=["Analysis"])
async def analyze_stock(
    request: AnalysisRequest,
    user: User = Depends(require_read_analysis)
):
    """
    Analyze a stock and get investment recommendations.
    
    - **symbol**: Stock ticker symbol (e.g., AAPL, GOOGL)
    - **analysis_type**: Type of analysis (comprehensive, technical, fundamental, quick)
    - **risk_tolerance**: Your risk tolerance level
    - **investment_horizon**: Your investment time horizon
    """
    try:
        # Record request
        metrics.record_analysis(
            analysis_type=request.analysis_type,
            symbol=request.symbol,
            status="started",
            duration=None
        )
        
        start_time = time.time()
        
        # Perform analysis
        result = await market_maven.analyze_stock(
            symbol=request.symbol,
            analysis_type=request.analysis_type,
            risk_tolerance=request.risk_tolerance,
            investment_horizon=request.investment_horizon
        )
        
        duration = time.time() - start_time
        
        # Record metrics
        metrics.record_analysis(
            analysis_type=request.analysis_type,
            symbol=request.symbol,
            status="success" if result["status"] == "success" else "error",
            confidence=result.get("confidence_score"),
            recommendation=result.get("recommendation"),
            duration=duration
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return AnalysisResponse(
            status=result["status"],
            symbol=result["symbol"],
            analysis_type=result["analysis_type"],
            recommendation=result["recommendation"],
            confidence_score=result["confidence_score"],
            risk_level=result["risk_level"],
            current_price=result["current_price"],
            target_price=result.get("price_targets", {}).get("target_price"),
            stop_loss=result.get("price_targets", {}).get("stop_loss"),
            take_profit=result.get("price_targets", {}).get("take_profit"),
            reasoning=result["reasoning"],
            key_factors=result["key_factors"],
            risks=result["risks"],
            opportunities=result["opportunities"],
            technical_indicators=result.get("technical_indicators"),
            timestamp=datetime.utcnow(),
            analysis_duration=duration
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze/batch", response_model=BatchAnalysisResponse, tags=["Analysis"])
async def batch_analyze(
    request: BatchAnalysisRequest,
    user: User = Depends(require_read_analysis)
):
    """Analyze multiple stocks in a single request."""
    start_time = time.time()
    results = []
    failed_symbols = []
    
    # Process symbols concurrently
    tasks = []
    for symbol in request.symbols:
        task = market_maven.analyze_stock(
            symbol=symbol,
            analysis_type=request.analysis_type,
            risk_tolerance=request.risk_tolerance,
            investment_horizon=request.investment_horizon
        )
        tasks.append((symbol, task))
    
    # Gather results
    for symbol, task in tasks:
        try:
            result = await task
            if result["status"] == "success":
                results.append(AnalysisResponse(
                    status=result["status"],
                    symbol=result["symbol"],
                    analysis_type=result["analysis_type"],
                    recommendation=result["recommendation"],
                    confidence_score=result["confidence_score"],
                    risk_level=result["risk_level"],
                    current_price=result["current_price"],
                    target_price=result.get("price_targets", {}).get("target_price"),
                    stop_loss=result.get("price_targets", {}).get("stop_loss"),
                    take_profit=result.get("price_targets", {}).get("take_profit"),
                    reasoning=result["reasoning"],
                    key_factors=result["key_factors"],
                    risks=result["risks"],
                    opportunities=result["opportunities"],
                    technical_indicators=result.get("technical_indicators"),
                    timestamp=datetime.utcnow(),
                    analysis_duration=None
                ))
            else:
                failed_symbols.append({
                    "symbol": symbol,
                    "error": result.get("error", "Unknown error")
                })
        except Exception as e:
            failed_symbols.append({
                "symbol": symbol,
                "error": str(e)
            })
    
    return BatchAnalysisResponse(
        status="success" if results else "error",
        results=results,
        failed_symbols=failed_symbols,
        total_duration=time.time() - start_time,
        timestamp=datetime.utcnow()
    )


# Trading endpoints
@app.post("/api/v1/trade", response_model=TradeResponse, tags=["Trading"])
async def execute_trade(
    request: TradeRequest,
    user: User = Depends(require_write_trades)
):
    """
    Execute a trade order.
    
    Requires proper authentication and trading permissions.
    """
    try:
        # Record request
        metrics.record_trade(
            symbol=request.symbol,
            action=request.action,
            status="submitted",
            volume=request.quantity
        )
        
        # Execute trade
        result = await market_maven.execute_trade(
            symbol=request.symbol,
            action=request.action,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            time_in_force=request.time_in_force,
            dry_run=request.dry_run or settings.trading.enable_dry_run
        )
        
        # Record metrics
        metrics.record_trade(
            symbol=request.symbol,
            action=request.action,
            status=result.get("status", "error"),
            volume=result.get("filled_quantity", 0),
            value=result.get("total_cost")
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return TradeResponse(
            status=result["status"],
            order_id=result["order_id"],
            symbol=result["symbol"],
            action=result["action"],
            order_type=result["order_type"],
            requested_quantity=result["requested_quantity"],
            filled_quantity=result.get("filled_quantity", 0),
            remaining_quantity=result.get("remaining_quantity", request.quantity),
            average_fill_price=result.get("average_fill_price"),
            total_cost=result.get("total_cost"),
            commission=result.get("commission", 0),
            fees=result.get("fees", 0),
            submitted_at=datetime.utcnow(),
            filled_at=datetime.utcnow() if result.get("filled_quantity", 0) > 0 else None,
            order_status=result.get("order_status", "PENDING"),
            dry_run=result.get("dry_run", True),
            error_message=result.get("error_message")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trade execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Portfolio endpoints
@app.get("/api/v1/portfolio", response_model=PortfolioResponse, tags=["Portfolio"])
async def get_portfolio(
    user: User = Depends(require_read_portfolio)
):
    """Get current portfolio status."""
    try:
        portfolio = await market_maven.get_portfolio_summary()
        
        if portfolio["status"] == "error":
            raise HTTPException(status_code=400, detail=portfolio.get("error"))
        
        return PortfolioResponse(
            account_id=portfolio.get("account_id", "default"),
            total_value=portfolio["total_value"],
            cash_balance=portfolio["cash_balance"],
            buying_power=portfolio["buying_power"],
            day_pnl=portfolio.get("day_pnl", 0),
            total_pnl=portfolio.get("total_pnl", 0),
            positions=portfolio.get("positions", []),
            portfolio_beta=portfolio.get("portfolio_beta"),
            var_95=portfolio.get("var_95"),
            sharpe_ratio=portfolio.get("sharpe_ratio"),
            last_updated=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Portfolio fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Market data endpoints
@app.post("/api/v1/market-data", response_model=MarketDataResponse, tags=["Market Data"])
async def get_market_data(
    request: MarketDataRequest,
    user: User = Depends(get_current_active_user)
):
    """Get market data for multiple symbols."""
    try:
        data = {}
        
        for symbol in request.symbols:
            symbol_data = {}
            
            if "quote" in request.data_types:
                # Get real-time quote
                quote = await market_maven.get_quote(symbol)
                symbol_data["quote"] = quote
            
            if "historical" in request.data_types:
                # Get historical data
                historical = await market_maven.get_historical_data(
                    symbol, 
                    period=request.period or "1m"
                )
                symbol_data["historical"] = historical
            
            if "fundamentals" in request.data_types:
                # Get fundamental data
                fundamentals = await market_maven.get_fundamentals(symbol)
                symbol_data["fundamentals"] = fundamentals
            
            if "news" in request.data_types:
                # Get news data
                news = await market_maven.get_news(symbol)
                symbol_data["news"] = news
            
            data[symbol] = symbol_data
        
        return MarketDataResponse(
            status="success",
            data=data,
            metadata={
                "symbols_count": len(request.symbols),
                "data_types": request.data_types
            },
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Market data fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Alert endpoints
@app.post("/api/v1/alerts", response_model=AlertResponse, tags=["Alerts"])
async def create_alert(
    request: AlertRequest,
    user: User = Depends(get_current_active_user),
    db = Depends(get_async_db)
):
    """Create a new price alert."""
    # Implementation would save to database
    # This is a placeholder response
    return AlertResponse(
        alert_id=uuid4(),
        symbol=request.symbol,
        alert_type=request.alert_type,
        threshold_value=request.threshold_value,
        is_active=True,
        created_at=datetime.utcnow(),
        last_triggered_at=None,
        trigger_count=0
    )


# WebSocket endpoint for real-time data
@app.websocket("/ws/market-data")
async def websocket_market_data(websocket):
    """WebSocket endpoint for real-time market data."""
    await websocket.accept()
    
    try:
        while True:
            # Receive symbol from client
            data = await websocket.receive_json()
            symbol = data.get("symbol")
            
            if symbol:
                # Get real-time data
                quote = await market_maven.get_quote(symbol)
                await websocket.send_json({
                    "type": "quote",
                    "symbol": symbol,
                    "data": quote,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Send data every second
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


if __name__ == "__main__":
    uvicorn.run(
        "market_maven.api.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.is_development(),
        log_level=settings.logging.level.lower()
    ) 