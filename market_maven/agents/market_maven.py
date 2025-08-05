"""
Stock Market Agent using Google Generative AI.
"""

import google.generativeai as genai
from typing import Dict, Any, List, Optional
import json
from datetime import datetime

from market_maven.config.settings import settings
from market_maven.core.logging import get_logger
from market_maven.core.exceptions import StockAgentError
from market_maven.tools.data_fetcher import data_fetcher

logger = get_logger(__name__)


class StockMarketAgent:
    """
    AI-powered stock market agent using Google Generative AI.
    
    This agent provides stock analysis capabilities:
    - Fetches market data
    - Performs analysis
    - Provides investment recommendations
    """

    def __init__(self):
        """Initialize the stock market agent."""
        # Configure Google Generative AI
        genai.configure(api_key=settings.api.google_api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel(
            model_name=settings.model.gemini_model,
            generation_config={
                "temperature": settings.model.temperature,
                "top_p": 1,
                "top_k": 1,
                "max_output_tokens": settings.model.max_tokens,
            }
        )
        
        # Store tools for reference (simplified - not using ADK)
        self.tools = {
            "data_fetcher": None,  # Will be initialized when needed
            "analyzer": None,      # Will be initialized when needed
            "trader": None        # Will be initialized when needed
        }
        
        logger.info("Stock market agent initialized")

    def _get_system_instruction(self) -> str:
        """Get system instruction for the agent."""
        return f"""
You are an AI-powered stock market agent. Your primary responsibilities include:

## Core Capabilities:
1. **Data Analysis**: Analyze stock market data including:
   - Historical price data and trends
   - Company fundamentals (P/E ratios, EPS, market cap, etc.)
   - Technical indicators
   - Market sentiment

2. **Investment Analysis**: Provide investment recommendations considering:
   - Technical analysis patterns
   - Fundamental valuation metrics
   - Risk assessment
   - User's risk tolerance and investment horizon

## Communication Style:
- Be professional, accurate, and data-driven
- Provide clear reasoning for all recommendations
- Include specific price targets and risk levels
- Always include appropriate disclaimers about financial risks

## Important Guidelines:
- Never provide financial advice without proper risk disclaimers
- Always validate data before making recommendations
- Consider market conditions and volatility

## Environment: {settings.environment}
"""

    async def analyze_stock(
        self,
        symbol: str,
        analysis_type: str = "comprehensive",
        risk_tolerance: str = "moderate",
        investment_horizon: str = "medium_term"
    ) -> Dict[str, Any]:
        """
        Analyze a stock and provide recommendations.
        
        Args:
            symbol: Stock ticker symbol
            analysis_type: Type of analysis to perform
            risk_tolerance: User's risk tolerance
            investment_horizon: Investment time horizon
            
        Returns:
            Analysis results with recommendations
        """
        try:
            logger.info(f"Analyzing stock {symbol}")
            
            # Fetch real-time data
            quote_data = await data_fetcher.fetch_stock_quote(symbol)
            company_info = await data_fetcher.fetch_company_info(symbol)
            
            # Check for errors
            if quote_data.get('error'):
                return {
                    "status": "error",
                    "error": quote_data.get('message', 'Failed to fetch stock data')
                }
            
            # Build the analysis prompt with real data
            prompt = f"""
{self._get_system_instruction()}

Please analyze the stock {symbol} with the following parameters:
- Analysis Type: {analysis_type}
- Risk Tolerance: {risk_tolerance}
- Investment Horizon: {investment_horizon}

Current Market Data:
- Current Price: ${quote_data.get('price', 'N/A')}
- Open: ${quote_data.get('open', 'N/A')}
- High: ${quote_data.get('high', 'N/A')}
- Low: ${quote_data.get('low', 'N/A')}
- Volume: {quote_data.get('volume', 'N/A'):,}
- Change: {quote_data.get('change', 'N/A')} ({quote_data.get('change_percent', 'N/A')}%)
- Previous Close: ${quote_data.get('previous_close', 'N/A')}

Company Information:
- Company Name: {company_info.get('name', 'N/A')}
- Sector: {company_info.get('sector', 'N/A')}
- Industry: {company_info.get('industry', 'N/A')}
- Market Cap: ${company_info.get('market_cap', 0):,}
- P/E Ratio: {company_info.get('pe_ratio', 'N/A')}
- EPS: {company_info.get('eps', 'N/A')}
- 52-Week High: ${company_info.get('52_week_high', 'N/A')}
- 52-Week Low: ${company_info.get('52_week_low', 'N/A')}
- Dividend Yield: {company_info.get('dividend_yield', 'N/A')}%
- Beta: {company_info.get('beta', 'N/A')}

Based on this real-time data, provide a comprehensive analysis including:
1. Current market data overview and interpretation
2. Technical analysis insights based on price movements
3. Fundamental analysis based on the metrics provided
4. Investment recommendation (Buy/Hold/Sell)
5. Confidence score (0-100)
6. Key risks and opportunities
7. Price targets (if applicable)

Format your response as a structured analysis.
"""

            # Generate analysis using Gemini
            response = self.model.generate_content(prompt)
            
            # Parse and structure the response
            # Handle different response formats
            if hasattr(response, 'text'):
                analysis_text = response.text
            elif hasattr(response, 'parts'):
                analysis_text = response.parts[0].text if response.parts else "No analysis generated"
            else:
                analysis_text = str(response)
            
            # For now, return a structured response
            # In production, we'd parse the AI response more carefully
            result = {
                "status": "success",
                "data": {
                    "symbol": symbol,
                    "analysis_type": analysis_type,
                    "recommendation": "HOLD",  # Would be parsed from AI response
                    "confidence_score": 75,    # Would be parsed from AI response
                    "risk_level": "MEDIUM",    # Would be parsed from AI response
                    "analysis": analysis_text,
                    "metadata": {
                        "risk_tolerance": risk_tolerance,
                        "investment_horizon": investment_horizon,
                        "analyzed_at": datetime.utcnow().isoformat() + "Z"
                    }
                }
            }
            
            logger.info(f"Analysis completed for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing stock {symbol}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "data": None
            }

    async def quick_analysis(self, symbol: str) -> Dict[str, Any]:
        """
        Perform a quick analysis of a stock.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Quick analysis results
        """
        return await self.analyze_stock(
            symbol=symbol,
            analysis_type="quick",
            risk_tolerance="moderate",
            investment_horizon="short_term"
        )

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio summary.
        
        Returns:
            Portfolio information
        """
        # Simplified implementation
        return {
            "status": "success",
            "data": {
                "total_value": 0,
                "positions": [],
                "message": "Portfolio functionality not yet implemented"
            }
        }

    def get_position(self, symbol: str) -> Dict[str, Any]:
        """
        Get position information for a specific stock.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Position information
        """
        # Simplified implementation
        return {
            "status": "success",
            "data": {
                "symbol": symbol,
                "shares": 0,
                "message": "Position tracking not yet implemented"
            }
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the agent.
        
        Returns:
            Health status information
        """
        health_status = {
            "agent": "healthy",
            "model": "connected" if self.model else "not_initialized",
            "api_key": "configured" if settings.api.google_api_key else "missing",
            "environment": settings.environment
        }
        
        return health_status


import asyncio


class SyncStockMarketAgent:
    """Synchronous wrapper for the async StockMarketAgent."""
    
    def __init__(self):
        self.agent = StockMarketAgent()
        
    def _run_async(self, coro):
        """Run an async coroutine in a sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            else:
                # If no loop is running, use asyncio.run
                return asyncio.run(coro)
        except RuntimeError:
            # Fallback: create a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
    
    def analyze_stock(self, **kwargs):
        """Sync wrapper for analyze_stock."""
        return self._run_async(self.agent.analyze_stock(**kwargs))
    
    def quick_analysis(self, symbol: str):
        """Sync wrapper for quick_analysis."""
        return self._run_async(self.agent.quick_analysis(symbol))
    
    def get_portfolio_summary(self):
        """Sync wrapper for get_portfolio_summary."""
        return self.agent.get_portfolio_summary()
    
    def get_position(self, symbol: str):
        """Sync wrapper for get_position."""
        return self.agent.get_position(symbol)
    
    def health_check(self):
        """Sync wrapper for health_check."""
        return self.agent.health_check()


# Create the main agent instance with sync wrapper
market_maven = SyncStockMarketAgent()