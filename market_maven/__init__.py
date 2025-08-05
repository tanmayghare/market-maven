"""
AI Stock Market Agent - Stock analysis using Google Generative AI.

This package provides stock market analysis capabilities:
- Real-time and historical market data fetching
- Technical and fundamental analysis
- AI-powered investment recommendations
"""

__version__ = "1.0.0"
__author__ = "AI Stock Agent Team"
__email__ = "team@example.com"

from market_maven.agents.market_maven import StockMarketAgent, market_maven
from market_maven.config.settings import settings
from market_maven.core.logging import setup_logging, get_logger

# Main exports
__all__ = [
    "StockMarketAgent",
    "market_maven", 
    "settings",
    "setup_logging",
    "get_logger",
]

# Package metadata
__package_info__ = {
    "name": "ai-stock-agent",
    "version": __version__,
    "description": "AI stock market agent using Google Generative AI",
    "author": __author__,
    "email": __email__,
    "framework": "Google ADK",
    "model": "Gemini 2.0 Flash",
    "license": "MIT",
} 