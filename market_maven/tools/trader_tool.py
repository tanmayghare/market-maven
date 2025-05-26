"""
Trader tool for executing trades through Interactive Brokers using Google ADK framework.
"""

from google.adk.tools import Tool
from typing import Dict, Any, Optional
from datetime import datetime
from ib_insync import IB, Stock, MarketOrder, LimitOrder

from market_maven.config.settings import (
    IBKR_HOST,
    IBKR_PORT,
    IBKR_CLIENT_ID,
    MAX_POSITION_SIZE
)

class TraderTool(Tool):
    """ADK Tool for executing trades through Interactive Brokers."""

    def __init__(self):
        super().__init__(
            name="stock_trader",
            description="Execute stock trades through Interactive Brokers with proper risk management",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["BUY", "SELL", "GET_POSITION", "GET_ACCOUNT_SUMMARY"],
                        "description": "Trading action to perform"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (required for BUY/SELL/GET_POSITION)"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of shares to trade (required for BUY/SELL)",
                        "minimum": 1,
                        "maximum": MAX_POSITION_SIZE
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["MARKET", "LIMIT"],
                        "description": "Type of order to place",
                        "default": "MARKET"
                    },
                    "limit_price": {
                        "type": "number",
                        "description": "Limit price for LIMIT orders"
                    },
                    "stop_loss": {
                        "type": "number",
                        "description": "Stop loss price"
                    },
                    "take_profit": {
                        "type": "number",
                        "description": "Take profit price"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, simulate the trade without executing",
                        "default": False
                    }
                },
                "required": ["action"]
            }
        )
        
        self.ib = None
        self._connection_status = "disconnected"

    def execute(self, action: str, symbol: str = None, quantity: int = None, 
                order_type: str = "MARKET", limit_price: float = None, 
                stop_loss: float = None, take_profit: float = None, 
                dry_run: bool = False) -> Dict[str, Any]:
        """Execute the trading operation."""
        
        try:
            if action in ["BUY", "SELL"]:
                return self._execute_trade(action, symbol, quantity, order_type, 
                                         limit_price, stop_loss, take_profit, dry_run)
            elif action == "GET_POSITION":
                return self._get_position(symbol)
            elif action == "GET_ACCOUNT_SUMMARY":
                return self._get_account_summary()
            else:
                return {
                    "status": "error",
                    "error": f"Unknown action: {action}",
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _execute_trade(self, action: str, symbol: str, quantity: int, order_type: str,
                      limit_price: float, stop_loss: float, take_profit: float, 
                      dry_run: bool) -> Dict[str, Any]:
        """Execute a buy or sell trade."""
        
        # Validate inputs
        if not symbol:
            raise ValueError("Symbol is required for trading")
        if not quantity or quantity <= 0:
            raise ValueError("Valid quantity is required for trading")
        if quantity > MAX_POSITION_SIZE:
            raise ValueError(f"Quantity exceeds maximum position size of {MAX_POSITION_SIZE}")
        if order_type == "LIMIT" and not limit_price:
            raise ValueError("Limit price is required for LIMIT orders")

        # If dry run, simulate the trade
        if dry_run:
            return self._simulate_trade(action, symbol, quantity, order_type, limit_price)

        # Connect to IBKR if not connected
        if not self._ensure_connection():
            raise ConnectionError("Failed to connect to Interactive Brokers")

        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Create order
            if order_type == "MARKET":
                ib_order = MarketOrder(action, quantity)
            else:  # LIMIT
                ib_order = LimitOrder(action, quantity, limit_price)

            # Add stop loss and take profit if specified
            if stop_loss:
                ib_order.stopPrice = stop_loss
            if take_profit:
                ib_order.takeProfitPrice = take_profit

            # Place the order
            trade = self.ib.placeOrder(contract, ib_order)
            
            # Wait for order to be processed
            self.ib.sleep(2)
            
            # Get order status
            order_status = trade.orderStatus
            
            return {
                "status": "success",
                "order_id": str(trade.order.orderId),
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "order_type": order_type,
                "order_status": order_status.status,
                "filled_quantity": order_status.filled,
                "remaining_quantity": order_status.remaining,
                "average_fill_price": order_status.avgFillPrice,
                "commission": sum(fill.commission for fill in trade.fills) if trade.fills else 0,
                "timestamp": datetime.now().isoformat(),
                "limit_price": limit_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Trade execution failed: {str(e)}",
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "timestamp": datetime.now().isoformat()
            }

    def _simulate_trade(self, action: str, symbol: str, quantity: int, 
                       order_type: str, limit_price: float) -> Dict[str, Any]:
        """Simulate a trade without actually executing it."""
        
        # For simulation, we'll use a mock price (in real implementation, 
        # you might fetch current market price)
        simulated_price = limit_price if order_type == "LIMIT" else 100.0
        simulated_commission = quantity * 0.005  # $0.005 per share commission
        
        return {
            "status": "simulated",
            "order_id": f"SIM_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "order_type": order_type,
            "order_status": "Filled",
            "filled_quantity": quantity,
            "remaining_quantity": 0,
            "average_fill_price": simulated_price,
            "commission": simulated_commission,
            "total_cost": quantity * simulated_price + simulated_commission,
            "timestamp": datetime.now().isoformat(),
            "note": "This is a simulated trade - no actual execution occurred"
        }

    def _get_position(self, symbol: str) -> Dict[str, Any]:
        """Get current position for a symbol."""
        if not symbol:
            raise ValueError("Symbol is required to get position")

        if not self._ensure_connection():
            return {
                "status": "error",
                "error": "Failed to connect to Interactive Brokers",
                "symbol": symbol,
                "timestamp": datetime.now().isoformat()
            }

        try:
            positions = self.ib.positions()
            
            for position in positions:
                if position.contract.symbol == symbol:
                    return {
                        "status": "success",
                        "symbol": symbol,
                        "position": position.position,
                        "market_price": position.marketPrice,
                        "market_value": position.marketValue,
                        "average_cost": position.avgCost,
                        "unrealized_pnl": position.unrealizedPNL,
                        "realized_pnl": position.realizedPNL,
                        "timestamp": datetime.now().isoformat()
                    }
            
            # No position found
            return {
                "status": "success",
                "symbol": symbol,
                "position": 0,
                "message": f"No position found for {symbol}",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to get position: {str(e)}",
                "symbol": symbol,
                "timestamp": datetime.now().isoformat()
            }

    def _get_account_summary(self) -> Dict[str, Any]:
        """Get account summary information."""
        if not self._ensure_connection():
            return {
                "status": "error",
                "error": "Failed to connect to Interactive Brokers",
                "timestamp": datetime.now().isoformat()
            }

        try:
            account_summary = {}
            
            # Get account summary values
            for summary_item in self.ib.accountSummary():
                account_summary[summary_item.tag] = summary_item.value
            
            # Get portfolio information
            portfolio = []
            for position in self.ib.positions():
                if position.position != 0:  # Only include non-zero positions
                    portfolio.append({
                        "symbol": position.contract.symbol,
                        "position": position.position,
                        "market_price": position.marketPrice,
                        "market_value": position.marketValue,
                        "average_cost": position.avgCost,
                        "unrealized_pnl": position.unrealizedPNL
                    })
            
            return {
                "status": "success",
                "account_summary": account_summary,
                "portfolio": portfolio,
                "total_positions": len(portfolio),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to get account summary: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def _ensure_connection(self) -> bool:
        """Ensure connection to Interactive Brokers."""
        try:
            if self.ib is None:
                self.ib = IB()
            
            if not self.ib.isConnected():
                self.ib.connect(
                    host=IBKR_HOST,
                    port=IBKR_PORT,
                    clientId=IBKR_CLIENT_ID,
                    timeout=10
                )
                self._connection_status = "connected"
            
            return self.ib.isConnected()
            
        except Exception as e:
            self._connection_status = f"connection_failed: {str(e)}"
            return False

    def disconnect(self):
        """Disconnect from Interactive Brokers."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            self._connection_status = "disconnected"

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.disconnect() 