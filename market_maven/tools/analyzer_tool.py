"""
Production-grade stock analyzer tool using Google ADK framework.
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal

from google.adk.tools import Tool

from market_maven.config.settings import settings
from market_maven.core.exceptions import AnalysisError
from market_maven.core.logging import LoggerMixin
from market_maven.core.metrics import metrics
from market_maven.models.schemas import (
    AnalysisResult, AnalysisType, Recommendation, RiskLevel,
    RiskTolerance, InvestmentHorizon, AnalysisScores, PriceTargets
)


class AnalyzerTool(Tool, LoggerMixin):
    """Production-grade ADK Tool for comprehensive stock analysis."""

    def __init__(self):
        super().__init__(
            name="stock_analyzer",
            description="Perform comprehensive stock analysis with AI-powered insights, technical indicators, and fundamental analysis",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., AAPL, GOOGL, MSFT)",
                        "pattern": "^[A-Z]{1,5}$"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["comprehensive", "technical", "fundamental", "quick"],
                        "description": "Type of analysis to perform",
                        "default": "comprehensive"
                    },
                    "risk_tolerance": {
                        "type": "string",
                        "enum": ["conservative", "moderate", "aggressive"],
                        "description": "Investor's risk tolerance level",
                        "default": "moderate"
                    },
                    "investment_horizon": {
                        "type": "string",
                        "enum": ["short_term", "medium_term", "long_term"],
                        "description": "Investment time horizon",
                        "default": "medium_term"
                    },
                    "market_data": {
                        "type": "object",
                        "description": "Market data from data fetcher tool",
                        "properties": {
                            "historical": {"type": "object"},
                            "company_info": {"type": "object"},
                            "technical_indicators": {"type": "object"}
                        }
                    },
                    "current_price": {
                        "type": "number",
                        "description": "Current stock price",
                        "minimum": 0
                    }
                },
                "required": ["symbol", "market_data"]
            }
        )

    def execute(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        analysis_type: str = "comprehensive",
        risk_tolerance: str = "moderate",
        investment_horizon: str = "medium_term",
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Execute comprehensive stock analysis with AI insights."""
        
        start_time = time.time()
        symbol = symbol.upper().strip()
        
        # Log operation start
        operation_logger = self.log_operation(
            "stock_analysis",
            symbol=symbol,
            analysis_type=analysis_type,
            risk_tolerance=risk_tolerance,
            investment_horizon=investment_horizon
        )
        
        result = {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_type": analysis_type,
            "status": "processing"
        }

        try:
            # Validate inputs
            self._validate_inputs(symbol, market_data, analysis_type, risk_tolerance, investment_horizon)
            
            # Extract current price
            if current_price is None:
                current_price = self._extract_current_price(market_data)
            
            # Perform analysis based on type
            if analysis_type == "comprehensive":
                analysis_result = self._comprehensive_analysis(
                    symbol, market_data, risk_tolerance, investment_horizon, current_price
                )
            elif analysis_type == "technical":
                analysis_result = self._technical_analysis(
                    symbol, market_data, risk_tolerance, investment_horizon, current_price
                )
            elif analysis_type == "fundamental":
                analysis_result = self._fundamental_analysis(
                    symbol, market_data, risk_tolerance, investment_horizon, current_price
                )
            elif analysis_type == "quick":
                analysis_result = self._quick_analysis(
                    symbol, market_data, risk_tolerance, investment_horizon, current_price
                )
            else:
                raise AnalysisError(f"Unknown analysis type: {analysis_type}")
            
            result.update(analysis_result)
            result["status"] = "success"
            
            # Record metrics
            duration = time.time() - start_time
            metrics.record_analysis(
                analysis_type=analysis_type,
                symbol=symbol,
                status="success",
                confidence=result.get("confidence_score"),
                recommendation=result.get("recommendation"),
                duration=duration
            )
            
            operation_logger.info(
                "Analysis completed successfully",
                duration=duration,
                recommendation=result.get("recommendation"),
                confidence=result.get("confidence_score")
            )
            
            return result
            
        except AnalysisError as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["error_code"] = e.error_code
            
            metrics.record_analysis(analysis_type, symbol, "error")
            operation_logger.error("Analysis failed", error=str(e), error_code=e.error_code)
            
            return result
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = f"Unexpected error: {str(e)}"
            
            metrics.record_analysis(analysis_type, symbol, "error")
            operation_logger.error("Unexpected error during analysis", error=str(e))
            
            return result

    def _validate_inputs(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        analysis_type: str,
        risk_tolerance: str,
        investment_horizon: str
    ) -> None:
        """Validate input parameters."""
        
        if not symbol or len(symbol) > 5:
            raise AnalysisError("Invalid symbol format", symbol=symbol)
        
        if not market_data:
            raise AnalysisError("Market data is required", symbol=symbol)
        
        valid_analysis_types = ["comprehensive", "technical", "fundamental", "quick"]
        if analysis_type not in valid_analysis_types:
            raise AnalysisError(f"Invalid analysis type: {analysis_type}")
        
        valid_risk_levels = ["conservative", "moderate", "aggressive"]
        if risk_tolerance not in valid_risk_levels:
            raise AnalysisError(f"Invalid risk tolerance: {risk_tolerance}")
        
        valid_horizons = ["short_term", "medium_term", "long_term"]
        if investment_horizon not in valid_horizons:
            raise AnalysisError(f"Invalid investment horizon: {investment_horizon}")

    def _extract_current_price(self, market_data: Dict[str, Any]) -> float:
        """Extract current price from market data."""
        
        # Try to get from historical data (latest close)
        if "historical" in market_data and "data" in market_data["historical"]:
            historical_data = market_data["historical"]["data"]
            if historical_data:
                latest = historical_data[-1]
                return float(latest.get("close", 0))
        
        # Try to get from company info
        if "company_info" in market_data:
            # This would typically come from real-time data
            pass
        
        raise AnalysisError("Unable to determine current price from market data")

    def _comprehensive_analysis(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        risk_tolerance: str,
        investment_horizon: str,
        current_price: float
    ) -> Dict[str, Any]:
        """Perform comprehensive analysis combining technical and fundamental factors."""
        
        # Technical analysis
        technical_scores = self._analyze_technical_indicators(market_data.get("technical_indicators", {}))
        
        # Fundamental analysis
        fundamental_scores = self._analyze_fundamentals(market_data.get("company_info", {}))
        
        # Price trend analysis
        trend_scores = self._analyze_price_trends(market_data.get("historical", {}))
        
        # Combine scores
        overall_score = (
            technical_scores["overall"] * 0.4 +
            fundamental_scores["overall"] * 0.4 +
            trend_scores["overall"] * 0.2
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(overall_score, risk_tolerance)
        
        # Calculate confidence based on data quality and consistency
        confidence = self._calculate_confidence(technical_scores, fundamental_scores, trend_scores)
        
        # Determine risk level
        risk_level = self._assess_risk_level(
            technical_scores, fundamental_scores, market_data.get("company_info", {})
        )
        
        # Generate price targets
        price_targets = self._generate_price_targets(
            current_price, technical_scores, fundamental_scores, recommendation
        )
        
        # Generate insights
        reasoning = self._generate_comprehensive_reasoning(
            symbol, technical_scores, fundamental_scores, trend_scores, 
            recommendation, risk_tolerance, investment_horizon
        )
        
        key_factors = self._extract_key_factors(technical_scores, fundamental_scores, trend_scores)
        risks = self._identify_risks(market_data, technical_scores, fundamental_scores)
        opportunities = self._identify_opportunities(market_data, technical_scores, fundamental_scores)
        
        return {
            "recommendation": recommendation.value,
            "confidence_score": confidence,
            "risk_level": risk_level.value,
            "current_price": current_price,
            "scores": {
                "overall": overall_score,
                "technical": technical_scores["overall"],
                "fundamental": fundamental_scores["overall"],
                "momentum": trend_scores["overall"]
            },
            "price_targets": price_targets,
            "reasoning": reasoning,
            "key_factors": key_factors,
            "risks": risks,
            "opportunities": opportunities,
            "analysis_details": {
                "technical_analysis": technical_scores,
                "fundamental_analysis": fundamental_scores,
                "trend_analysis": trend_scores
            }
        }

    def _technical_analysis(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        risk_tolerance: str,
        investment_horizon: str,
        current_price: float
    ) -> Dict[str, Any]:
        """Perform technical analysis focusing on price patterns and indicators."""
        
        technical_scores = self._analyze_technical_indicators(market_data.get("technical_indicators", {}))
        trend_scores = self._analyze_price_trends(market_data.get("historical", {}))
        
        # Weight technical factors more heavily
        overall_score = (
            technical_scores["overall"] * 0.7 +
            trend_scores["overall"] * 0.3
        )
        
        recommendation = self._generate_recommendation(overall_score, risk_tolerance)
        confidence = min(technical_scores.get("confidence", 0.5), trend_scores.get("confidence", 0.5))
        risk_level = self._assess_technical_risk(technical_scores, trend_scores)
        
        price_targets = self._generate_technical_price_targets(current_price, technical_scores)
        
        reasoning = self._generate_technical_reasoning(
            symbol, technical_scores, trend_scores, recommendation, investment_horizon
        )
        
        return {
            "recommendation": recommendation.value,
            "confidence_score": confidence,
            "risk_level": risk_level.value,
            "current_price": current_price,
            "scores": {
                "overall": overall_score,
                "technical": technical_scores["overall"],
                "momentum": trend_scores["overall"]
            },
            "price_targets": price_targets,
            "reasoning": reasoning,
            "key_factors": self._extract_technical_factors(technical_scores, trend_scores),
            "risks": self._identify_technical_risks(technical_scores, trend_scores),
            "opportunities": self._identify_technical_opportunities(technical_scores, trend_scores)
        }

    def _fundamental_analysis(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        risk_tolerance: str,
        investment_horizon: str,
        current_price: float
    ) -> Dict[str, Any]:
        """Perform fundamental analysis focusing on company financials and valuation."""
        
        fundamental_scores = self._analyze_fundamentals(market_data.get("company_info", {}))
        
        overall_score = fundamental_scores["overall"]
        recommendation = self._generate_recommendation(overall_score, risk_tolerance)
        confidence = fundamental_scores.get("confidence", 0.5)
        risk_level = self._assess_fundamental_risk(fundamental_scores, market_data.get("company_info", {}))
        
        price_targets = self._generate_fundamental_price_targets(
            current_price, fundamental_scores, market_data.get("company_info", {})
        )
        
        reasoning = self._generate_fundamental_reasoning(
            symbol, fundamental_scores, recommendation, investment_horizon
        )
        
        return {
            "recommendation": recommendation.value,
            "confidence_score": confidence,
            "risk_level": risk_level.value,
            "current_price": current_price,
            "scores": {
                "overall": overall_score,
                "fundamental": fundamental_scores["overall"]
            },
            "price_targets": price_targets,
            "reasoning": reasoning,
            "key_factors": self._extract_fundamental_factors(fundamental_scores),
            "risks": self._identify_fundamental_risks(fundamental_scores),
            "opportunities": self._identify_fundamental_opportunities(fundamental_scores)
        }

    def _quick_analysis(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        risk_tolerance: str,
        investment_horizon: str,
        current_price: float
    ) -> Dict[str, Any]:
        """Perform quick analysis for rapid decision making."""
        
        # Simplified scoring based on key indicators
        quick_score = 0.5  # Default neutral
        
        # Check key technical indicators
        technical_indicators = market_data.get("technical_indicators", {})
        if "RSI" in technical_indicators:
            rsi_data = technical_indicators["RSI"]
            rsi_value = rsi_data.get("latest_value", 50)
            if rsi_value < 30:
                quick_score += 0.2  # Oversold - bullish
            elif rsi_value > 70:
                quick_score -= 0.2  # Overbought - bearish
        
        # Check MACD
        if "MACD" in technical_indicators:
            macd_data = technical_indicators["MACD"]
            if macd_data.get("macd", 0) > macd_data.get("signal", 0):
                quick_score += 0.1  # Bullish signal
            else:
                quick_score -= 0.1  # Bearish signal
        
        # Check basic fundamentals
        company_info = market_data.get("company_info", {})
        if "pe_ratio" in company_info:
            pe_ratio = company_info.get("pe_ratio")
            if pe_ratio and 10 <= pe_ratio <= 25:
                quick_score += 0.1  # Reasonable valuation
            elif pe_ratio and pe_ratio > 40:
                quick_score -= 0.1  # Potentially overvalued
        
        # Clamp score
        quick_score = max(0, min(1, quick_score))
        
        recommendation = self._generate_recommendation(quick_score, risk_tolerance)
        confidence = 0.6  # Lower confidence for quick analysis
        risk_level = RiskLevel.MEDIUM  # Default to medium risk
        
        reasoning = f"""Quick analysis for {symbol}:
        
Current Price: ${current_price:.2f}

Key Signals:
- RSI: {technical_indicators.get('RSI', {}).get('latest_value', 'N/A')} ({technical_indicators.get('RSI', {}).get('interpretation', 'N/A')})
- MACD: {technical_indicators.get('MACD', {}).get('interpretation', 'N/A')}
- P/E Ratio: {company_info.get('pe_ratio', 'N/A')}

Overall Score: {quick_score:.2f}/1.0
Recommendation: {recommendation.value}

Note: This is a rapid assessment. Consider a comprehensive analysis for important investment decisions."""
        
        return {
            "recommendation": recommendation.value,
            "confidence_score": confidence,
            "risk_level": risk_level.value,
            "current_price": current_price,
            "scores": {
                "overall": quick_score
            },
            "price_targets": {
                "target_price": current_price * (1.05 if quick_score > 0.6 else 0.95)
            },
            "reasoning": reasoning,
            "key_factors": ["Quick technical signals", "Basic valuation metrics"],
            "risks": ["Limited analysis depth", "Market volatility"],
            "opportunities": ["Rapid decision making", "Quick entry/exit signals"]
        }

    def _analyze_technical_indicators(self, technical_indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze technical indicators and generate scores."""
        
        scores = {"overall": 0.5, "confidence": 0.5}
        signals = []
        
        # RSI Analysis
        if "RSI" in technical_indicators:
            rsi_data = technical_indicators["RSI"]
            rsi_value = rsi_data.get("latest_value", 50)
            
            if rsi_value < 30:
                scores["rsi"] = 0.8  # Oversold - bullish
                signals.append("RSI oversold - potential buy signal")
            elif rsi_value > 70:
                scores["rsi"] = 0.2  # Overbought - bearish
                signals.append("RSI overbought - potential sell signal")
            else:
                scores["rsi"] = 0.5  # Neutral
                signals.append("RSI in neutral range")
        
        # MACD Analysis
        if "MACD" in technical_indicators:
            macd_data = technical_indicators["MACD"]
            macd_value = macd_data.get("macd", 0)
            signal_value = macd_data.get("signal", 0)
            
            if macd_value > signal_value:
                scores["macd"] = 0.7  # Bullish
                signals.append("MACD above signal line - bullish")
            else:
                scores["macd"] = 0.3  # Bearish
                signals.append("MACD below signal line - bearish")
        
        # Moving Averages
        sma_score = 0.5
        if "SMA" in technical_indicators:
            sma_data = technical_indicators["SMA"]
            # Compare current price to SMA (would need current price)
            scores["sma"] = sma_score
        
        # Calculate overall technical score
        indicator_scores = [scores.get(key, 0.5) for key in ["rsi", "macd", "sma"]]
        scores["overall"] = sum(indicator_scores) / len(indicator_scores) if indicator_scores else 0.5
        scores["signals"] = signals
        scores["confidence"] = 0.7 if len(indicator_scores) >= 2 else 0.5
        
        return scores

    def _analyze_fundamentals(self, company_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze fundamental metrics and generate scores."""
        
        scores = {"overall": 0.5, "confidence": 0.5}
        factors = []
        
        # P/E Ratio Analysis
        pe_ratio = company_info.get("pe_ratio")
        if pe_ratio:
            if 10 <= pe_ratio <= 25:
                scores["pe"] = 0.7  # Good valuation
                factors.append(f"P/E ratio {pe_ratio:.1f} - reasonable valuation")
            elif pe_ratio < 10:
                scores["pe"] = 0.8  # Potentially undervalued
                factors.append(f"P/E ratio {pe_ratio:.1f} - potentially undervalued")
            elif pe_ratio > 40:
                scores["pe"] = 0.3  # Potentially overvalued
                factors.append(f"P/E ratio {pe_ratio:.1f} - potentially overvalued")
            else:
                scores["pe"] = 0.5  # Neutral
                factors.append(f"P/E ratio {pe_ratio:.1f} - moderate valuation")
        
        # Market Cap Analysis
        market_cap = company_info.get("market_cap")
        if market_cap:
            market_cap_val = float(market_cap) if isinstance(market_cap, str) else market_cap
            if market_cap_val > 10_000_000_000:  # Large cap
                scores["market_cap"] = 0.6  # Stable
                factors.append("Large cap stock - stable")
            elif market_cap_val > 2_000_000_000:  # Mid cap
                scores["market_cap"] = 0.7  # Growth potential
                factors.append("Mid cap stock - growth potential")
            else:  # Small cap
                scores["market_cap"] = 0.5  # Higher risk/reward
                factors.append("Small cap stock - higher risk/reward")
        
        # Dividend Yield
        dividend_yield = company_info.get("dividend_yield")
        if dividend_yield:
            div_yield = float(dividend_yield)
            if div_yield > 0.03:  # > 3%
                scores["dividend"] = 0.6  # Income generating
                factors.append(f"Dividend yield {div_yield:.1%} - income generating")
            else:
                scores["dividend"] = 0.5  # Growth focused
                factors.append("Low/no dividend - growth focused")
        
        # Calculate overall fundamental score
        fundamental_scores = [scores.get(key, 0.5) for key in ["pe", "market_cap", "dividend"]]
        scores["overall"] = sum(fundamental_scores) / len(fundamental_scores) if fundamental_scores else 0.5
        scores["factors"] = factors
        scores["confidence"] = 0.7 if len(fundamental_scores) >= 2 else 0.5
        
        return scores

    def _analyze_price_trends(self, historical_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze price trends and momentum."""
        
        scores = {"overall": 0.5, "confidence": 0.5}
        
        if not historical_data or "data" not in historical_data:
            return scores
        
        data_points = historical_data["data"]
        if len(data_points) < 10:
            return scores
        
        # Calculate recent trend (last 10 days vs previous 10 days)
        recent_prices = [float(point["close"]) for point in data_points[-10:]]
        previous_prices = [float(point["close"]) for point in data_points[-20:-10]]
        
        if recent_prices and previous_prices:
            recent_avg = sum(recent_prices) / len(recent_prices)
            previous_avg = sum(previous_prices) / len(previous_prices)
            
            trend_change = (recent_avg - previous_avg) / previous_avg
            
            if trend_change > 0.05:  # > 5% increase
                scores["trend"] = 0.8  # Strong uptrend
                scores["overall"] = 0.7
            elif trend_change > 0.02:  # > 2% increase
                scores["trend"] = 0.6  # Moderate uptrend
                scores["overall"] = 0.6
            elif trend_change < -0.05:  # > 5% decrease
                scores["trend"] = 0.2  # Strong downtrend
                scores["overall"] = 0.3
            elif trend_change < -0.02:  # > 2% decrease
                scores["trend"] = 0.4  # Moderate downtrend
                scores["overall"] = 0.4
            else:
                scores["trend"] = 0.5  # Sideways
                scores["overall"] = 0.5
            
            scores["trend_change"] = trend_change
            scores["confidence"] = 0.6
        
        return scores

    def _generate_recommendation(self, score: float, risk_tolerance: str) -> Recommendation:
        """Generate investment recommendation based on score and risk tolerance."""
        
        # Adjust thresholds based on risk tolerance
        if risk_tolerance == "conservative":
            if score >= 0.8:
                return Recommendation.BUY
            elif score >= 0.6:
                return Recommendation.HOLD
            elif score <= 0.3:
                return Recommendation.SELL
            else:
                return Recommendation.HOLD
        elif risk_tolerance == "aggressive":
            if score >= 0.7:
                return Recommendation.STRONG_BUY
            elif score >= 0.6:
                return Recommendation.BUY
            elif score <= 0.4:
                return Recommendation.SELL
            elif score <= 0.2:
                return Recommendation.STRONG_SELL
            else:
                return Recommendation.HOLD
        else:  # moderate
            if score >= 0.75:
                return Recommendation.BUY
            elif score >= 0.6:
                return Recommendation.HOLD
            elif score <= 0.4:
                return Recommendation.SELL
            elif score <= 0.25:
                return Recommendation.STRONG_SELL
            else:
                return Recommendation.HOLD

    def _calculate_confidence(self, *score_dicts) -> float:
        """Calculate overall confidence based on data quality and consistency."""
        
        confidences = []
        for score_dict in score_dicts:
            if isinstance(score_dict, dict) and "confidence" in score_dict:
                confidences.append(score_dict["confidence"])
        
        if not confidences:
            return 0.5
        
        # Average confidence, but penalize if we have very few data sources
        base_confidence = sum(confidences) / len(confidences)
        data_penalty = max(0, (3 - len(confidences)) * 0.1)
        
        return max(0.1, min(1.0, base_confidence - data_penalty))

    def _assess_risk_level(self, technical_scores: Dict, fundamental_scores: Dict, company_info: Dict) -> RiskLevel:
        """Assess overall risk level based on various factors."""
        
        risk_factors = 0
        
        # Technical risk factors
        if technical_scores.get("overall", 0.5) < 0.3:
            risk_factors += 1
        
        # Fundamental risk factors
        pe_ratio = company_info.get("pe_ratio")
        if pe_ratio and pe_ratio > 50:
            risk_factors += 1
        
        market_cap = company_info.get("market_cap")
        if market_cap:
            market_cap_val = float(market_cap) if isinstance(market_cap, str) else market_cap
            if market_cap_val < 1_000_000_000:  # Small cap
                risk_factors += 1
        
        # Determine risk level
        if risk_factors >= 2:
            return RiskLevel.HIGH
        elif risk_factors == 1:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _assess_technical_risk(self, technical_scores: Dict, trend_scores: Dict) -> RiskLevel:
        """Assess risk level based on technical factors."""
        
        if technical_scores.get("overall", 0.5) < 0.3 or trend_scores.get("overall", 0.5) < 0.3:
            return RiskLevel.HIGH
        elif technical_scores.get("overall", 0.5) < 0.4 or trend_scores.get("overall", 0.5) < 0.4:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _assess_fundamental_risk(self, fundamental_scores: Dict, company_info: Dict) -> RiskLevel:
        """Assess risk level based on fundamental factors."""
        
        risk_factors = 0
        
        if fundamental_scores.get("overall", 0.5) < 0.4:
            risk_factors += 1
        
        pe_ratio = company_info.get("pe_ratio")
        if pe_ratio and (pe_ratio > 40 or pe_ratio < 5):
            risk_factors += 1
        
        if risk_factors >= 2:
            return RiskLevel.HIGH
        elif risk_factors == 1:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _generate_price_targets(
        self, current_price: float, technical_scores: Dict, 
        fundamental_scores: Dict, recommendation: Recommendation
    ) -> Dict[str, float]:
        """Generate price targets based on analysis."""
        
        # Base targets on recommendation strength
        if recommendation in [Recommendation.STRONG_BUY, Recommendation.BUY]:
            target_multiplier = 1.15 if recommendation == Recommendation.STRONG_BUY else 1.10
            stop_loss_multiplier = 0.95
        elif recommendation == Recommendation.SELL:
            target_multiplier = 0.90
            stop_loss_multiplier = 1.05
        elif recommendation == Recommendation.STRONG_SELL:
            target_multiplier = 0.85
            stop_loss_multiplier = 1.10
        else:  # HOLD
            target_multiplier = 1.05
            stop_loss_multiplier = 0.95
        
        return {
            "target_price": current_price * target_multiplier,
            "stop_loss": current_price * stop_loss_multiplier,
            "take_profit": current_price * (target_multiplier + 0.05),
            "support_level": current_price * 0.95,
            "resistance_level": current_price * 1.05
        }

    def _generate_technical_price_targets(self, current_price: float, technical_scores: Dict) -> Dict[str, float]:
        """Generate price targets based on technical analysis."""
        
        score = technical_scores.get("overall", 0.5)
        
        if score > 0.7:
            target_multiplier = 1.12
        elif score > 0.6:
            target_multiplier = 1.08
        elif score < 0.3:
            target_multiplier = 0.88
        elif score < 0.4:
            target_multiplier = 0.92
        else:
            target_multiplier = 1.02
        
        return {
            "target_price": current_price * target_multiplier,
            "stop_loss": current_price * (0.95 if score > 0.5 else 1.05),
            "support_level": current_price * 0.95,
            "resistance_level": current_price * 1.05
        }

    def _generate_fundamental_price_targets(
        self, current_price: float, fundamental_scores: Dict, company_info: Dict
    ) -> Dict[str, float]:
        """Generate price targets based on fundamental analysis."""
        
        score = fundamental_scores.get("overall", 0.5)
        
        # Adjust based on P/E ratio if available
        pe_ratio = company_info.get("pe_ratio")
        if pe_ratio:
            if pe_ratio < 15:  # Potentially undervalued
                target_multiplier = 1.15
            elif pe_ratio > 30:  # Potentially overvalued
                target_multiplier = 0.90
            else:
                target_multiplier = 1.05 if score > 0.6 else 0.95
        else:
            target_multiplier = 1.10 if score > 0.6 else 0.95
        
        return {
            "target_price": current_price * target_multiplier,
            "stop_loss": current_price * (0.92 if score > 0.5 else 1.08)
        }

    def _generate_comprehensive_reasoning(
        self, symbol: str, technical_scores: Dict, fundamental_scores: Dict, 
        trend_scores: Dict, recommendation: Recommendation, risk_tolerance: str, 
        investment_horizon: str
    ) -> str:
        """Generate comprehensive reasoning for the analysis."""
        
        reasoning = f"""Comprehensive Analysis for {symbol}

RECOMMENDATION: {recommendation.value}

TECHNICAL ANALYSIS (Score: {technical_scores.get('overall', 0.5):.2f}/1.0):
"""
        
        # Add technical signals
        if "signals" in technical_scores:
            for signal in technical_scores["signals"]:
                reasoning += f"• {signal}\n"
        
        reasoning += f"""
FUNDAMENTAL ANALYSIS (Score: {fundamental_scores.get('overall', 0.5):.2f}/1.0):
"""
        
        # Add fundamental factors
        if "factors" in fundamental_scores:
            for factor in fundamental_scores["factors"]:
                reasoning += f"• {factor}\n"
        
        reasoning += f"""
TREND ANALYSIS (Score: {trend_scores.get('overall', 0.5):.2f}/1.0):
• Recent price momentum: {trend_scores.get('trend_change', 0):.1%}

INVESTMENT CONSIDERATIONS:
• Risk Tolerance: {risk_tolerance.title()}
• Investment Horizon: {investment_horizon.replace('_', ' ').title()}
• Overall confidence in analysis: {self._calculate_confidence(technical_scores, fundamental_scores, trend_scores):.1%}

This analysis combines technical indicators, fundamental metrics, and price trends to provide a comprehensive investment recommendation. Consider your personal financial situation and risk tolerance before making investment decisions."""
        
        return reasoning

    def _generate_technical_reasoning(
        self, symbol: str, technical_scores: Dict, trend_scores: Dict, 
        recommendation: Recommendation, investment_horizon: str
    ) -> str:
        """Generate reasoning focused on technical analysis."""
        
        reasoning = f"""Technical Analysis for {symbol}

RECOMMENDATION: {recommendation.value}

TECHNICAL INDICATORS:
"""
        
        if "signals" in technical_scores:
            for signal in technical_scores["signals"]:
                reasoning += f"• {signal}\n"
        
        reasoning += f"""
PRICE TREND:
• Recent momentum: {trend_scores.get('trend_change', 0):.1%}
• Trend score: {trend_scores.get('overall', 0.5):.2f}/1.0

TECHNICAL OUTLOOK:
This analysis focuses on price action and technical indicators. The recommendation is based on current market signals and momentum patterns suitable for {investment_horizon.replace('_', ' ')} trading strategies."""
        
        return reasoning

    def _generate_fundamental_reasoning(
        self, symbol: str, fundamental_scores: Dict, recommendation: Recommendation, 
        investment_horizon: str
    ) -> str:
        """Generate reasoning focused on fundamental analysis."""
        
        reasoning = f"""Fundamental Analysis for {symbol}

RECOMMENDATION: {recommendation.value}

FUNDAMENTAL FACTORS:
"""
        
        if "factors" in fundamental_scores:
            for factor in fundamental_scores["factors"]:
                reasoning += f"• {factor}\n"
        
        reasoning += f"""
VALUATION ASSESSMENT:
• Overall fundamental score: {fundamental_scores.get('overall', 0.5):.2f}/1.0

INVESTMENT OUTLOOK:
This analysis focuses on company fundamentals and valuation metrics. The recommendation considers long-term value and financial health, suitable for {investment_horizon.replace('_', ' ')} investment strategies."""
        
        return reasoning

    def _extract_key_factors(self, technical_scores: Dict, fundamental_scores: Dict, trend_scores: Dict) -> List[str]:
        """Extract key factors influencing the analysis."""
        
        factors = []
        
        # Technical factors
        if technical_scores.get("overall", 0.5) > 0.6:
            factors.append("Positive technical indicators")
        elif technical_scores.get("overall", 0.5) < 0.4:
            factors.append("Negative technical indicators")
        
        # Fundamental factors
        if fundamental_scores.get("overall", 0.5) > 0.6:
            factors.append("Strong fundamental metrics")
        elif fundamental_scores.get("overall", 0.5) < 0.4:
            factors.append("Weak fundamental metrics")
        
        # Trend factors
        trend_change = trend_scores.get("trend_change", 0)
        if trend_change > 0.05:
            factors.append("Strong upward price momentum")
        elif trend_change < -0.05:
            factors.append("Strong downward price momentum")
        
        return factors if factors else ["Mixed signals across indicators"]

    def _extract_technical_factors(self, technical_scores: Dict, trend_scores: Dict) -> List[str]:
        """Extract technical factors."""
        
        factors = []
        
        if "signals" in technical_scores:
            factors.extend(technical_scores["signals"][:3])  # Top 3 signals
        
        trend_change = trend_scores.get("trend_change", 0)
        if abs(trend_change) > 0.02:
            direction = "upward" if trend_change > 0 else "downward"
            factors.append(f"Recent {direction} price momentum ({trend_change:.1%})")
        
        return factors if factors else ["Limited technical signals available"]

    def _extract_fundamental_factors(self, fundamental_scores: Dict) -> List[str]:
        """Extract fundamental factors."""
        
        if "factors" in fundamental_scores:
            return fundamental_scores["factors"][:3]  # Top 3 factors
        
        return ["Limited fundamental data available"]

    def _identify_risks(self, market_data: Dict, technical_scores: Dict, fundamental_scores: Dict) -> List[str]:
        """Identify potential risks."""
        
        risks = []
        
        # Technical risks
        if technical_scores.get("overall", 0.5) < 0.4:
            risks.append("Negative technical momentum")
        
        # Fundamental risks
        company_info = market_data.get("company_info", {})
        pe_ratio = company_info.get("pe_ratio")
        if pe_ratio and pe_ratio > 40:
            risks.append("High valuation multiples")
        
        # Market risks
        risks.append("General market volatility")
        risks.append("Economic uncertainty")
        
        return risks

    def _identify_technical_risks(self, technical_scores: Dict, trend_scores: Dict) -> List[str]:
        """Identify technical risks."""
        
        risks = ["Market volatility", "Technical indicator divergence"]
        
        if technical_scores.get("overall", 0.5) < 0.4:
            risks.append("Weak technical signals")
        
        if trend_scores.get("trend_change", 0) < -0.05:
            risks.append("Negative price momentum")
        
        return risks

    def _identify_fundamental_risks(self, fundamental_scores: Dict) -> List[str]:
        """Identify fundamental risks."""
        
        risks = ["Economic downturn", "Industry competition"]
        
        if fundamental_scores.get("overall", 0.5) < 0.4:
            risks.append("Weak fundamental metrics")
        
        return risks

    def _identify_opportunities(self, market_data: Dict, technical_scores: Dict, fundamental_scores: Dict) -> List[str]:
        """Identify potential opportunities."""
        
        opportunities = []
        
        # Technical opportunities
        if technical_scores.get("overall", 0.5) > 0.6:
            opportunities.append("Positive technical momentum")
        
        # Fundamental opportunities
        company_info = market_data.get("company_info", {})
        pe_ratio = company_info.get("pe_ratio")
        if pe_ratio and pe_ratio < 15:
            opportunities.append("Attractive valuation")
        
        # General opportunities
        opportunities.append("Market recovery potential")
        
        return opportunities

    def _identify_technical_opportunities(self, technical_scores: Dict, trend_scores: Dict) -> List[str]:
        """Identify technical opportunities."""
        
        opportunities = []
        
        if technical_scores.get("overall", 0.5) > 0.6:
            opportunities.append("Strong technical signals")
        
        if trend_scores.get("trend_change", 0) > 0.05:
            opportunities.append("Positive price momentum")
        
        opportunities.append("Technical breakout potential")
        
        return opportunities

    def _identify_fundamental_opportunities(self, fundamental_scores: Dict) -> List[str]:
        """Identify fundamental opportunities."""
        
        opportunities = []
        
        if fundamental_scores.get("overall", 0.5) > 0.6:
            opportunities.append("Strong fundamental position")
        
        opportunities.extend(["Long-term growth potential", "Market expansion opportunities"])
        
        return opportunities 