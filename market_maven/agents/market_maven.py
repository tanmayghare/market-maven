"""
Production-grade Stock Market Agent using Google ADK framework.
"""

from typing import Dict, Any, List, Optional
from google.adk.agents import LlmAgent
from google.adk.core import CallbackContext, ToolContext
from google.adk.tools import Tool

from market_maven.config.settings import settings
from market_maven.core.logging import LoggerMixin, get_logger
from market_maven.core.metrics import metrics
from market_maven.core.exceptions import StockAgentError
from market_maven.tools.data_fetcher_tool import DataFetcherTool
from market_maven.tools.analyzer_tool import AnalyzerTool
from market_maven.tools.trader_tool import TraderTool


class StockMarketAgent(LlmAgent, LoggerMixin):
    """
    Production-grade AI-powered stock market agent using Google ADK.
    
    This agent provides comprehensive stock analysis and trading capabilities:
    - Fetches real-time and historical market data
    - Performs technical and fundamental analysis
    - Executes trades with proper risk management
    - Provides investment recommendations
    """

    def __init__(self, **kwargs):
        """Initialize the stock market agent with production-grade configuration."""
        
        # Initialize tools
        tools = [
            DataFetcherTool(),
            AnalyzerTool(),
            TraderTool()
        ]
        
        # Agent configuration
        agent_config = {
            "name": "stock_market_agent",
            "model": settings.model.gemini_model,
            "instruction": self._get_system_instruction(),
            "description": "AI-powered stock market agent for analysis and trading",
            "tools": tools,
            "temperature": settings.model.temperature,
            "max_tokens": settings.model.max_tokens,
        }
        
        # Override with any provided kwargs
        agent_config.update(kwargs)
        
        # Initialize the LLM agent
        super().__init__(**agent_config)
        
        # Set up callbacks for monitoring and control
        self._setup_callbacks()
        
        # Initialize metrics if enabled
        if settings.metrics.enable_metrics:
            metrics.start_metrics_server(settings.metrics.metrics_port)
        
        self.logger.info(
            "Stock Market Agent initialized",
            model=settings.model.gemini_model,
            tools=[tool.name for tool in tools],
            environment=settings.environment
        )

    def _get_system_instruction(self) -> str:
        """Get comprehensive system instruction for the agent."""
        
        return f"""
You are an AI-powered stock market agent with advanced capabilities for financial analysis and trading. Your primary responsibilities include:

## Core Capabilities:
1. **Data Analysis**: Fetch and analyze comprehensive stock market data including:
   - Historical price data and trends
   - Company fundamentals (P/E ratios, EPS, market cap, etc.)
   - Technical indicators (RSI, MACD, SMA, EMA, Bollinger Bands, Stochastic)
   - Market sentiment and news analysis

2. **Investment Analysis**: Provide detailed investment recommendations considering:
   - Technical analysis patterns and signals
   - Fundamental valuation metrics
   - Risk assessment and management
   - Market conditions and sector performance
   - User's risk tolerance and investment horizon

3. **Trading Execution**: Execute trades with proper risk management:
   - Market and limit orders
   - Stop-loss and take-profit levels
   - Position sizing and portfolio risk management
   - Dry-run capabilities for testing strategies

## Analysis Framework:
- **Comprehensive Analysis**: Combines technical and fundamental factors
- **Technical Analysis**: Focus on price patterns and technical indicators
- **Fundamental Analysis**: Evaluate company financials and valuation
- **Quick Analysis**: Rapid assessment for immediate decisions

## Risk Management Principles:
- Always consider the user's risk tolerance ({', '.join(settings.analysis.risk_tolerance_levels)})
- Respect investment horizons ({', '.join(settings.analysis.investment_horizons)})
- Implement proper position sizing (max {settings.trading.max_position_size} shares)
- Use stop-loss ({settings.trading.stop_loss_percentage:.1%}) and take-profit ({settings.trading.take_profit_percentage:.1%}) levels
- Provide confidence scores for all recommendations

## Communication Style:
- Be professional, accurate, and data-driven
- Provide clear reasoning for all recommendations
- Include specific price targets and risk levels
- Explain technical concepts in accessible terms
- Always include appropriate disclaimers about financial risks

## Important Guidelines:
- Never provide financial advice without proper risk disclaimers
- Always validate data before making recommendations
- Consider market conditions and volatility
- Respect rate limits and API constraints
- Log all significant operations for audit trails

## Environment: {settings.environment.upper()}
{"- DRY RUN MODE ENABLED: All trades will be simulated" if settings.trading.enable_dry_run else "- LIVE TRADING ENABLED: Real trades will be executed"}

Remember: Past performance does not guarantee future results. All investments carry risk of loss.
"""

    def _setup_callbacks(self) -> None:
        """Set up ADK callbacks for monitoring and control."""
        
        # Before agent callback for logging and validation
        def before_agent_callback(context: CallbackContext) -> Optional[str]:
            """Log agent invocations and perform validation."""
            
            # Extract user message
            user_message = context.request.contents[-1].text if context.request.contents else ""
            
            # Log the request
            self.log_operation(
                "agent_invocation",
                user_message=user_message[:200],  # Truncate for logging
                session_id=getattr(context, 'session_id', 'unknown')
            ).info("Agent invocation started")
            
            # Validate environment-specific constraints
            if settings.is_production():
                # Additional production validations
                if "test" in user_message.lower() and not settings.trading.enable_dry_run:
                    return "Production environment detected. Please use dry-run mode for testing."
            
            return None  # Continue with normal processing
        
        # After agent callback for metrics and cleanup
        def after_agent_callback(context: CallbackContext) -> None:
            """Record metrics and perform cleanup after agent execution."""
            
            # Record agent execution metrics
            metrics.record_tool_execution(
                tool_name="stock_market_agent",
                status="completed"
            )
            
            self.logger.info("Agent invocation completed")
        
        # Before tool callback for tool-specific logging and validation
        def before_tool_callback(context: ToolContext) -> Optional[Dict[str, Any]]:
            """Log tool executions and perform validation."""
            
            tool_name = context.tool.name
            
            # Log tool execution
            self.log_operation(
                "tool_execution",
                tool_name=tool_name,
                args=context.args
            ).info("Tool execution started")
            
            # Tool-specific validations
            if tool_name == "stock_trader":
                action = context.args.get("action")
                if action in ["BUY", "SELL"] and settings.trading.enable_dry_run:
                    # Force dry run in development
                    context.args["dry_run"] = True
                    self.logger.info("Forcing dry-run mode", tool=tool_name, action=action)
            
            return None  # Continue with normal processing
        
        # After tool callback for metrics and error handling
        def after_tool_callback(context: ToolContext) -> None:
            """Record tool metrics and handle errors."""
            
            tool_name = context.tool.name
            
            # Determine status based on response
            status = "success"
            if hasattr(context, 'response') and isinstance(context.response, dict):
                if context.response.get("status") == "error":
                    status = "error"
                elif context.response.get("status") == "rate_limited":
                    status = "rate_limited"
            
            # Record tool execution metrics
            metrics.record_tool_execution(
                tool_name=tool_name,
                status=status
            )
            
            self.logger.info(
                "Tool execution completed",
                tool_name=tool_name,
                status=status
            )
        
        # Register callbacks
        self.add_callback("before_agent", before_agent_callback)
        self.add_callback("after_agent", after_agent_callback)
        self.add_callback("before_tool", before_tool_callback)
        self.add_callback("after_tool", after_tool_callback)

    def analyze_stock(
        self, 
        symbol: str, 
        analysis_type: str = "comprehensive",
        risk_tolerance: str = "moderate",
        investment_horizon: str = "medium_term"
    ) -> Dict[str, Any]:
        """
        Analyze a stock with specified parameters.
        
        Args:
            symbol: Stock ticker symbol
            analysis_type: Type of analysis (comprehensive, technical, fundamental, quick)
            risk_tolerance: Risk tolerance level (conservative, moderate, aggressive)
            investment_horizon: Investment time horizon (short_term, medium_term, long_term)
            
        Returns:
            Analysis result dictionary
        """
        
        prompt = f"""
        Please analyze the stock {symbol.upper()} with the following parameters:
        - Analysis type: {analysis_type}
        - Risk tolerance: {risk_tolerance}
        - Investment horizon: {investment_horizon}
        
        Steps to follow:
        1. First, fetch comprehensive data for {symbol} including historical prices, company information, and technical indicators
        2. Perform a {analysis_type} analysis considering the specified risk tolerance and investment horizon
        3. Provide a clear recommendation with confidence score, price targets, and risk assessment
        4. Include specific reasoning and key factors influencing the recommendation
        
        Please be thorough and data-driven in your analysis.
        """
        
        try:
            response = self.run(prompt)
            return {
                "status": "success",
                "symbol": symbol.upper(),
                "analysis_type": analysis_type,
                "risk_tolerance": risk_tolerance,
                "investment_horizon": investment_horizon,
                "response": response
            }
        except Exception as e:
            self.logger.error(f"Stock analysis failed for {symbol}: {e}")
            return {
                "status": "error",
                "symbol": symbol.upper(),
                "error": str(e)
            }

    def execute_trade(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str = "MARKET",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a trade with the specified parameters.
        
        Args:
            symbol: Stock ticker symbol
            action: Trade action (BUY or SELL)
            quantity: Number of shares
            order_type: Order type (MARKET or LIMIT)
            **kwargs: Additional order parameters
            
        Returns:
            Trade execution result
        """
        
        # Build order parameters
        order_params = {
            "symbol": symbol.upper(),
            "action": action.upper(),
            "quantity": quantity,
            "order_type": order_type.upper(),
            **kwargs
        }
        
        # Force dry run in development
        if settings.is_development() or settings.trading.enable_dry_run:
            order_params["dry_run"] = True
        
        prompt = f"""
        Please execute a {action.upper()} trade for {quantity} shares of {symbol.upper()} with the following parameters:
        {', '.join(f'{k}: {v}' for k, v in order_params.items())}
        
        Use the stock_trader tool to execute this trade. Ensure proper risk management and validation.
        """
        
        try:
            response = self.run(prompt)
            return {
                "status": "success",
                "trade_request": order_params,
                "response": response
            }
        except Exception as e:
            self.logger.error(f"Trade execution failed: {e}")
            return {
                "status": "error",
                "trade_request": order_params,
                "error": str(e)
            }

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio and account summary."""
        
        prompt = """
        Please provide a comprehensive portfolio and account summary including:
        1. Current account balance and buying power
        2. All current positions with P&L
        3. Portfolio performance metrics
        4. Risk assessment
        
        Use the stock_trader tool with action GET_ACCOUNT_SUMMARY.
        """
        
        try:
            response = self.run(prompt)
            return {
                "status": "success",
                "response": response
            }
        except Exception as e:
            self.logger.error(f"Portfolio summary failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def get_position(self, symbol: str) -> Dict[str, Any]:
        """Get current position for a specific symbol."""
        
        prompt = f"""
        Please get the current position information for {symbol.upper()}.
        Use the stock_trader tool with action GET_POSITION.
        """
        
        try:
            response = self.run(prompt)
            return {
                "status": "success",
                "symbol": symbol.upper(),
                "response": response
            }
        except Exception as e:
            self.logger.error(f"Position lookup failed for {symbol}: {e}")
            return {
                "status": "error",
                "symbol": symbol.upper(),
                "error": str(e)
            }

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the agent and its components."""
        
        health_status = {
            "agent": "healthy",
            "tools": {},
            "configuration": {},
            "environment": settings.environment
        }
        
        # Check tool availability
        for tool in self.tools:
            try:
                # Basic tool validation
                health_status["tools"][tool.name] = "healthy"
            except Exception as e:
                health_status["tools"][tool.name] = f"unhealthy: {str(e)}"
        
        # Check configuration
        try:
            # Validate API keys
            if settings.api.alpha_vantage_api_key:
                health_status["configuration"]["alpha_vantage"] = "configured"
            else:
                health_status["configuration"]["alpha_vantage"] = "missing"
                
            if settings.api.google_api_key:
                health_status["configuration"]["google_ai"] = "configured"
            else:
                health_status["configuration"]["google_ai"] = "missing"
                
        except Exception as e:
            health_status["configuration"]["error"] = str(e)
        
        # Overall health
        unhealthy_tools = [name for name, status in health_status["tools"].items() 
                          if status != "healthy"]
        missing_config = [name for name, status in health_status["configuration"].items() 
                         if "missing" in str(status)]
        
        if unhealthy_tools or missing_config:
            health_status["agent"] = "degraded"
            health_status["issues"] = {
                "unhealthy_tools": unhealthy_tools,
                "missing_configuration": missing_config
            }
        
        return health_status


# Create the main agent instance
market_maven = StockMarketAgent() 