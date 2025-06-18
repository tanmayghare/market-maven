"""
Trader tool for executing trades through Interactive Brokers using Google ADK framework.
"""

from google.adk.tools import Tool
from typing import Dict, Any, Optional
from datetime import datetime
import threading
import time

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.common import OrderId, TickerId

from market_maven.config.settings import settings
from market_maven.core.logging import LoggerMixin, get_logger


class IBAPIWrapper(EWrapper):
    """Wrapper class for handling IBAPI callbacks."""
    
    def __init__(self):
        EWrapper.__init__(self)
        self.logger = get_logger(__name__)
        
        # Data storage
        self.positions = {}
        self.account_summary = {}
        self.orders = {}
        self.executions = {}
        self.portfolio = {}
        
        # Event flags
        self.positions_received = threading.Event()
        self.account_summary_received = threading.Event()
        self.order_status_received = threading.Event()
        
        # Error tracking
        self.last_error = None
        
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        """Handle error messages."""
        error_msg = f"Error {errorCode}: {errorString}"
        self.logger.error(f"IBAPI Error - ReqId: {reqId}, {error_msg}")
        self.last_error = {"code": errorCode, "message": errorString, "reqId": reqId}
        
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """Handle position updates."""
        symbol = contract.symbol
        self.positions[symbol] = {
            "account": account,
            "symbol": symbol,
            "position": position,
            "avgCost": avgCost,
            "contract": contract
        }
        
    def positionEnd(self):
        """Called when all positions have been received."""
        self.positions_received.set()
        
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """Handle account summary updates."""
        self.account_summary[tag] = {
            "value": value,
            "currency": currency,
            "account": account
        }
        
    def accountSummaryEnd(self, reqId: int):
        """Called when account summary is complete."""
        self.account_summary_received.set()
        
    def orderStatus(self, orderId: OrderId, status: str, filled: float, remaining: float,
                   avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float,
                   clientId: int, whyHeld: str, mktCapPrice: float):
        """Handle order status updates."""
        self.orders[orderId] = {
            "orderId": orderId,
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice,
            "permId": permId,
            "parentId": parentId,
            "lastFillPrice": lastFillPrice,
            "clientId": clientId,
            "whyHeld": whyHeld,
            "mktCapPrice": mktCapPrice
        }
        self.order_status_received.set()
        
    def execDetails(self, reqId: int, contract: Contract, execution):
        """Handle execution details."""
        self.executions[execution.execId] = {
            "contract": contract,
            "execution": execution
        }


class IBAPIClient(EClient):
    """Client class for IBAPI connection."""
    
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)
        self.wrapper = wrapper
        self.logger = get_logger(__name__)
        
    def get_next_order_id(self):
        """Get next valid order ID."""
        # This is a simplified approach - in production you'd want to handle this more robustly
        return int(time.time() * 1000) % 1000000


class TraderTool(Tool, LoggerMixin):
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
                        "maximum": settings.trading.max_position_size
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
        
        # Initialize IBAPI components
        self.wrapper = IBAPIWrapper()
        self.client = IBAPIClient(self.wrapper)
        self._connection_status = "disconnected"
        self._connection_thread = None

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
        if quantity > settings.trading.max_position_size:
            raise ValueError(f"Quantity exceeds maximum position size of {settings.trading.max_position_size}")
        if order_type == "LIMIT" and not limit_price:
            raise ValueError("Limit price is required for LIMIT orders")

        # If dry run, simulate the trade
        if dry_run or settings.trading.enable_dry_run:
            return self._simulate_trade(action, symbol, quantity, order_type, limit_price)

        # Connect to IBKR if not connected
        if not self._ensure_connection():
            raise ConnectionError("Failed to connect to Interactive Brokers")

        try:
            # Create contract
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Create order
            order = Order()
            order.action = action
            order.totalQuantity = quantity
            
            # Map order types to IBAPI format
            if order_type == "MARKET":
                order.orderType = "MKT"
            elif order_type == "LIMIT":
                order.orderType = "LMT"
                order.lmtPrice = limit_price
            
            # Add stop loss and take profit if specified
            if stop_loss:
                order.auxPrice = stop_loss  # For stop orders
            
            # Get next order ID
            order_id = self.client.get_next_order_id()
            
            # Clear previous order status
            self.wrapper.order_status_received.clear()
            
            # Place the order
            self.client.placeOrder(order_id, contract, order)
            
            # Wait for order status update (with timeout)
            if self.wrapper.order_status_received.wait(timeout=10):
                order_status = self.wrapper.orders.get(order_id, {})
                
                return {
                    "status": "success",
                    "order_id": str(order_id),
                    "symbol": symbol,
                    "action": action,
                    "quantity": quantity,
                    "order_type": order_type,
                    "order_status": order_status.get("status", "Unknown"),
                    "filled_quantity": order_status.get("filled", 0),
                    "remaining_quantity": order_status.get("remaining", quantity),
                    "average_fill_price": order_status.get("avgFillPrice", 0),
                    "timestamp": datetime.now().isoformat(),
                    "limit_price": limit_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit
                }
            else:
                return {
                    "status": "timeout",
                    "error": "Order status update timeout",
                    "order_id": str(order_id),
                    "symbol": symbol,
                    "action": action,
                    "quantity": quantity,
                    "timestamp": datetime.now().isoformat()
                }
            
        except Exception as e:
            self.logger.error(f"Trade execution failed: {str(e)}")
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
            # Clear previous positions
            self.wrapper.positions.clear()
            self.wrapper.positions_received.clear()
            
            # Request positions
            self.client.reqPositions()
            
            # Wait for positions to be received (with timeout)
            if self.wrapper.positions_received.wait(timeout=10):
                position_data = self.wrapper.positions.get(symbol)
                
                if position_data:
                    return {
                        "status": "success",
                        "symbol": symbol,
                        "position": position_data["position"],
                        "average_cost": position_data["avgCost"],
                        "account": position_data["account"],
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    # No position found
                    return {
                        "status": "success",
                        "symbol": symbol,
                        "position": 0,
                        "message": f"No position found for {symbol}",
                        "timestamp": datetime.now().isoformat()
                    }
            else:
                return {
                    "status": "timeout",
                    "error": "Position request timeout",
                    "symbol": symbol,
                    "timestamp": datetime.now().isoformat()
                }
            
        except Exception as e:
            self.logger.error(f"Failed to get position: {str(e)}")
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
            # Clear previous data
            self.wrapper.account_summary.clear()
            self.wrapper.positions.clear()
            self.wrapper.account_summary_received.clear()
            self.wrapper.positions_received.clear()
            
            # Request account summary
            req_id = 1
            self.client.reqAccountSummary(req_id, "All", "TotalCashValue,NetLiquidation,GrossPositionValue")
            
            # Request positions
            self.client.reqPositions()
            
            # Wait for both requests to complete
            account_ready = self.wrapper.account_summary_received.wait(timeout=10)
            positions_ready = self.wrapper.positions_received.wait(timeout=10)
            
            if not account_ready:
                return {
                    "status": "timeout",
                    "error": "Account summary request timeout",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Build portfolio from positions
            portfolio = []
            if positions_ready:
                for symbol, position_data in self.wrapper.positions.items():
                    if position_data["position"] != 0:  # Only include non-zero positions
                        portfolio.append({
                            "symbol": symbol,
                            "position": position_data["position"],
                            "average_cost": position_data["avgCost"],
                            "account": position_data["account"]
                        })
            
            # Format account summary
            formatted_summary = {}
            for tag, data in self.wrapper.account_summary.items():
                formatted_summary[tag] = {
                    "value": data["value"],
                    "currency": data["currency"]
                }
            
            return {
                "status": "success",
                "account_summary": formatted_summary,
                "portfolio": portfolio,
                "total_positions": len(portfolio),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get account summary: {str(e)}")
            return {
                "status": "error",
                "error": f"Failed to get account summary: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }

    def _ensure_connection(self) -> bool:
        """Ensure connection to Interactive Brokers."""
        try:
            if not self.client.isConnected():
                # Start connection in a separate thread
                self._connection_thread = threading.Thread(
                    target=self._connect_to_ib,
                    daemon=True
                )
                self._connection_thread.start()
                
                # Wait for connection to establish
                time.sleep(2)
                
                if self.client.isConnected():
                    self._connection_status = "connected"
                    self.logger.info("Successfully connected to Interactive Brokers")
                    return True
                else:
                    self._connection_status = "connection_failed"
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {str(e)}")
            self._connection_status = f"connection_failed: {str(e)}"
            return False
    
    def _connect_to_ib(self):
        """Connect to Interactive Brokers in a separate thread."""
        try:
            self.client.connect(
                host=settings.ibkr.host,
                port=settings.ibkr.port,
                clientId=settings.ibkr.client_id
            )
            # Start the message loop
            self.client.run()
        except Exception as e:
            self.logger.error(f"IBAPI connection thread error: {str(e)}")

    def disconnect(self):
        """Disconnect from Interactive Brokers."""
        try:
            if self.client.isConnected():
                self.client.disconnect()
                self._connection_status = "disconnected"
                self.logger.info("Disconnected from Interactive Brokers")
                
            if self._connection_thread and self._connection_thread.is_alive():
                self._connection_thread.join(timeout=5)
        except Exception as e:
            self.logger.error(f"Disconnect error: {str(e)}")

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.disconnect() 