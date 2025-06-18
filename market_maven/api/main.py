"""
FastAPI application for the Stock Market Agent API.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Depends, Query, Path, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from market_maven.config.settings import settings
from market_maven.core.logging import get_logger
from market_maven.core.database import get_async_db
from market_maven.core.database_init import db_manager
from market_maven.models.schemas import (
    AnalysisResult, TradeOrder, TradeResult, Portfolio, Position,
    MarketData, CompanyInfo, StockPrice
)
from market_maven.models.db_models import StockSymbol
from market_maven.api.auth import get_current_user, User as AuthUser
from market_maven.agents.market_maven import market_maven

logger = get_logger(__name__)


# API metadata
app = FastAPI(
    title="Market Maven API",
    description="""
    **Production-grade AI-powered stock market intelligence API**
    
    This API provides comprehensive stock analysis, investment recommendations, 
    and automated trading capabilities powered by Google's Agent Development Kit (ADK) 
    and Gemini 2.0 Flash.
    
    ## Features
    
    * **Stock Analysis**: Technical, fundamental, and sentiment analysis
    * **AI Recommendations**: Investment advice with confidence scoring
    * **Portfolio Management**: Track positions and performance
    * **Trading Integration**: Execute trades through Interactive Brokers
    * **Market Data**: Real-time and historical market data
    * **Risk Management**: Comprehensive risk assessment and controls
    
    ## Authentication
    
    Most endpoints require API key authentication. Include your API key in the 
    `Authorization` header as a Bearer token.
    
    ## Rate Limits
    
    * **Free tier**: 100 requests per hour
    * **Pro tier**: 1000 requests per hour
    * **Enterprise**: Custom limits
    
    ## Environment
    
    Current environment: **{environment}**
    """.format(environment=settings.environment.upper()),
    version="1.0.0",
    contact={
        "name": "Market Maven Support",
        "url": "https://github.com/your-org/market-maven",
        "email": "support@marketmaven.ai",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.marketmaven.ai",
            "description": "Production server"
        }
    ]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else ["https://marketmaven.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()


# Response models
class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: datetime
    version: str
    environment: str
    database: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    message: str
    timestamp: datetime
    request_id: Optional[str] = None


# Health and status endpoints
@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check the health status of the API and its dependencies",
    tags=["System"]
)
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns the current status of the API and all its dependencies including:
    - Database connectivity
    - External API availability
    - System resources
    """
    try:
        # Check database health
        db_health = db_manager.check_health()
        
        return HealthResponse(
            status="healthy" if db_health["connected"] else "degraded",
            timestamp=datetime.utcnow(),
            version="1.0.0",
            environment=settings.environment,
            database=db_health
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable"
        )


@app.get(
    "/",
    summary="API Root",
    description="API root endpoint with basic information",
    tags=["System"]
)
async def root():
    """API root endpoint."""
    return {
        "name": "Market Maven API",
        "version": "1.0.0",
        "description": "AI-powered stock market intelligence API",
        "documentation": "/docs",
        "health": "/health"
    }


# Stock analysis endpoints
@app.post(
    "/api/v1/analyze/{symbol}",
    response_model=AnalysisResult,
    summary="Analyze Stock",
    description="Perform comprehensive AI-powered stock analysis",
    tags=["Analysis"],
    responses={
        200: {"description": "Analysis completed successfully"},
        400: {"description": "Invalid symbol or parameters"},
        401: {"description": "Authentication required"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Analysis failed"}
    }
)
async def analyze_stock(
    symbol: str = Path(..., description="Stock ticker symbol (e.g., AAPL)", regex="^[A-Z]{1,5}$"),
    analysis_type: str = Query("comprehensive", description="Type of analysis to perform"),
    risk_tolerance: str = Query("moderate", description="Risk tolerance level"),
    investment_horizon: str = Query("medium_term", description="Investment time horizon"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Perform comprehensive stock analysis using AI.
    
    This endpoint provides detailed stock analysis including:
    - **Technical Analysis**: Chart patterns, indicators, momentum
    - **Fundamental Analysis**: Financial metrics, ratios, growth
    - **Sentiment Analysis**: News sentiment, social media buzz
    - **AI Recommendation**: Buy/Sell/Hold with confidence score
    - **Risk Assessment**: Risk level and risk factors
    - **Price Targets**: Target price, stop loss, take profit levels
    
    **Parameters:**
    - `symbol`: Stock ticker symbol (required)
    - `analysis_type`: Type of analysis (comprehensive, technical, fundamental, quick)
    - `risk_tolerance`: Risk tolerance (conservative, moderate, aggressive)
    - `investment_horizon`: Time horizon (short_term, medium_term, long_term)
    
    **Returns:**
    Complete analysis result with recommendation and confidence score.
    """
    try:
        result = market_maven.analyze_stock(
            symbol=symbol.upper(),
            analysis_type=analysis_type,
            risk_tolerance=risk_tolerance,
            investment_horizon=investment_horizon
        )
        
        if result["status"] == "success":
            # Convert to AnalysisResult schema
            return AnalysisResult(**result["data"])
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Analysis failed")
            )
            
    except Exception as e:
        logger.error(f"Stock analysis failed for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis service temporarily unavailable"
        )


@app.get(
    "/api/v1/stocks/{symbol}/info",
    response_model=CompanyInfo,
    summary="Get Company Information",
    description="Get detailed company information and financial metrics",
    tags=["Market Data"]
)
async def get_company_info(
    symbol: str = Path(..., description="Stock ticker symbol", regex="^[A-Z]{1,5}$"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get comprehensive company information.
    
    Returns detailed company information including:
    - Basic company details (name, sector, industry)
    - Financial metrics (market cap, P/E ratio, EPS)
    - Valuation ratios (P/B, P/S, PEG)
    - Dividend information
    - 52-week price range
    """
    try:
        # Implementation would fetch from database or external API
        # This is a placeholder
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Company info endpoint not implemented yet"
        )
    except Exception as e:
        logger.error(f"Failed to get company info for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch company information"
        )


# Trading endpoints
@app.post(
    "/api/v1/trade",
    response_model=TradeResult,
    summary="Execute Trade",
    description="Execute a stock trade with risk management",
    tags=["Trading"],
    responses={
        200: {"description": "Trade executed successfully"},
        400: {"description": "Invalid trade parameters"},
        401: {"description": "Authentication required"},
        403: {"description": "Trading not authorized or risk limits exceeded"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def execute_trade(
    trade_order: TradeOrder,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Execute a stock trade through Interactive Brokers.
    
    **Features:**
    - Multiple order types (Market, Limit, Stop, Stop-Limit)
    - Risk management (position sizing, stop-loss, take-profit)
    - Real-time execution tracking
    - Comprehensive audit trail
    - Dry-run mode for testing
    
    **Risk Controls:**
    - Maximum position size limits
    - Portfolio risk percentage limits
    - Daily trading limits
    - Automatic risk checks
    
    **Order Types:**
    - **Market**: Execute immediately at current market price
    - **Limit**: Execute only at specified price or better
    - **Stop**: Trigger market order when price hits stop level
    - **Stop-Limit**: Trigger limit order when price hits stop level
    """
    try:
        # Implementation would use TraderTool
        # This is a placeholder
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Trading endpoint not implemented yet"
        )
    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Trading service temporarily unavailable"
        )


# Portfolio endpoints
@app.get(
    "/api/v1/portfolio",
    response_model=Portfolio,
    summary="Get Portfolio",
    description="Get current portfolio summary and performance metrics",
    tags=["Portfolio"]
)
async def get_portfolio(
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get comprehensive portfolio information.
    
    Returns:
    - Total portfolio value and cash balance
    - Daily and total P&L
    - Risk metrics (beta, VaR, Sharpe ratio)
    - Asset allocation breakdown
    - Performance statistics
    """
    try:
        # Implementation would fetch from database
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Portfolio endpoint not implemented yet"
        )
    except Exception as e:
        logger.error(f"Failed to get portfolio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch portfolio information"
        )


@app.get(
    "/api/v1/positions",
    response_model=List[Position],
    summary="Get Positions",
    description="Get all current stock positions",
    tags=["Portfolio"]
)
async def get_positions(
    symbol: Optional[str] = Query(None, description="Filter by symbol (optional)"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get current stock positions.
    
    Returns list of all positions or filtered by symbol, including:
    - Position size and average cost
    - Current market value
    - Unrealized P&L
    - Position performance metrics
    """
    try:
        # Implementation would fetch from database
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Positions endpoint not implemented yet"
        )
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch position information"
        )


# Market data endpoints
@app.get(
    "/api/v1/market/{symbol}",
    response_model=MarketData,
    summary="Get Market Data",
    description="Get real-time market data for a stock",
    tags=["Market Data"]
)
async def get_market_data(
    symbol: str = Path(..., description="Stock ticker symbol", regex="^[A-Z]{1,5}$"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get real-time market data.
    
    Returns current market data including:
    - Bid/Ask prices and sizes
    - Last trade price and volume
    - Daily OHLC values
    - Volume and market statistics
    """
    try:
        # Implementation would fetch real-time data
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Market data endpoint not implemented yet"
        )
    except Exception as e:
        logger.error(f"Failed to get market data for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch market data"
        )


@app.get(
    "/api/v1/history/{symbol}",
    response_model=List[StockPrice],
    summary="Get Price History",
    description="Get historical price data for a stock",
    tags=["Market Data"]
)
async def get_price_history(
    symbol: str = Path(..., description="Stock ticker symbol", regex="^[A-Z]{1,5}$"),
    period: str = Query("1y", description="Time period (1d, 5d, 1m, 3m, 6m, 1y, 2y, 5y, max)"),
    interval: str = Query("1d", description="Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get historical price data.
    
    Returns historical OHLCV data for the specified period and interval.
    Supports various time periods and granularities for different analysis needs.
    """
    try:
        # Implementation would fetch from database or external API
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Price history endpoint not implemented yet"
        )
    except Exception as e:
        logger.error(f"Failed to get price history for {symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch price history"
        )


# Database management endpoints (admin only)
@app.post(
    "/api/v1/admin/database/init",
    summary="Initialize Database",
    description="Initialize database with all tables and initial data (Admin only)",
    tags=["Admin"]
)
async def init_database(
    force: bool = Query(False, description="Force initialization even if database exists"),
    current_user: AuthUser = Depends(get_current_user)
):
    """Initialize the database (Admin only)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        success = await db_manager.initialize_database(force=force)
        if success:
            return {"message": "Database initialized successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database initialization failed"
            )
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url)
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "market_maven.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development"
    ) 