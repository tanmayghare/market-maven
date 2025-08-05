"""
Simplified FastAPI application for Market Maven MVP.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from market_maven.config.settings import settings
from market_maven.core.logging import get_logger
from market_maven.agents.market_maven import market_maven

logger = get_logger(__name__)


# Simple response models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    environment: str
    model: str


class AnalysisResponse(BaseModel):
    status: str
    symbol: str
    analysis: str
    recommendation: str
    confidence_score: int
    timestamp: str


class QuoteResponse(BaseModel):
    symbol: str
    price: float
    change: float
    change_percent: str
    volume: int
    timestamp: str


# Create FastAPI app
app = FastAPI(
    title="Market Maven API",
    description="AI-powered stock market analysis API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Market Maven API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    health_status = market_maven.health_check()
    
    return HealthResponse(
        status="healthy" if health_status.get("agent") == "healthy" else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        environment=settings.environment,
        model=health_status.get("model", "unknown")
    )


@app.get("/api/v1/analyze/{symbol}", response_model=AnalysisResponse)
async def analyze_stock(
    symbol: str = Path(..., description="Stock ticker symbol (e.g., AAPL)"),
    analysis_type: str = Query("comprehensive", description="Type of analysis"),
    risk_tolerance: str = Query("moderate", description="Risk tolerance level"),
    investment_horizon: str = Query("medium_term", description="Investment horizon")
):
    """
    Perform AI-powered stock analysis.
    
    Args:
        symbol: Stock ticker symbol
        analysis_type: Type of analysis (comprehensive, quick, technical, fundamental)
        risk_tolerance: Risk tolerance (conservative, moderate, aggressive)
        investment_horizon: Investment horizon (short_term, medium_term, long_term)
    
    Returns:
        Analysis results with AI recommendations
    """
    try:
        result = market_maven.analyze_stock(
            symbol=symbol.upper(),
            analysis_type=analysis_type,
            risk_tolerance=risk_tolerance,
            investment_horizon=investment_horizon
        )
        
        if result["status"] == "success":
            data = result["data"]
            return AnalysisResponse(
                status="success",
                symbol=data["symbol"],
                analysis=data["analysis"],
                recommendation=data["recommendation"],
                confidence_score=data["confidence_score"],
                timestamp=data["metadata"]["analyzed_at"]
            )
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
            
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(
    symbol: str = Path(..., description="Stock ticker symbol (e.g., AAPL)")
):
    """
    Get current stock quote.
    
    Args:
        symbol: Stock ticker symbol
    
    Returns:
        Current stock quote data
    """
    try:
        # For MVP, we'll use the agent's analysis to get quote data
        # In production, this could be a separate optimized endpoint
        result = market_maven.analyze_stock(
            symbol=symbol.upper(),
            analysis_type="quick"
        )
        
        if result["status"] == "success":
            # Extract quote data from analysis
            # This is simplified for MVP
            return QuoteResponse(
                symbol=symbol.upper(),
                price=0.0,  # Would be extracted from real data
                change=0.0,
                change_percent="0%",
                volume=0,
                timestamp=datetime.utcnow().isoformat()
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to fetch quote")
            
    except Exception as e:
        logger.error(f"Error fetching quote for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio")
async def get_portfolio():
    """
    Get portfolio summary.
    
    Returns:
        Portfolio information (placeholder for MVP)
    """
    portfolio = market_maven.get_portfolio_summary()
    return portfolio


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return {
        "status": "error",
        "error_code": exc.status_code,
        "detail": exc.detail,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return {
        "status": "error",
        "error_code": 500,
        "detail": "Internal server error",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)