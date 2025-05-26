"""
AI Stock Market Agent - Production-grade stock analysis and trading using Google ADK.

This package provides comprehensive stock market analysis and trading capabilities:
- Real-time and historical market data fetching
- Advanced technical and fundamental analysis
- AI-powered investment recommendations
- Automated trading with risk management
- Production-grade monitoring and logging
"""

__version__ = "1.0.0"
__author__ = "AI Stock Agent Team"
__email__ = "team@example.com"

from market_maven.agents.market_maven import StockMarketAgent, market_maven
from market_maven.config.settings import settings
from market_maven.core.logging import setup_logging, get_logger
from market_maven.core.metrics import metrics

# Main exports
__all__ = [
    "StockMarketAgent",
    "market_maven", 
    "settings",
    "setup_logging",
    "get_logger",
    "metrics",
]

# Package metadata
__package_info__ = {
    "name": "ai-stock-agent",
    "version": __version__,
    "description": "Production-grade AI stock market agent using Google ADK",
    "author": __author__,
    "email": __email__,
    "framework": "Google ADK",
    "model": "Gemini 2.0 Flash",
    "license": "MIT",
} 