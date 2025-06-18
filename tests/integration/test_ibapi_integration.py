#!/usr/bin/env python3
"""
Test script for IBAPI integration with TraderTool.
This script tests the connection and basic functionality without executing real trades.
"""

import sys
import os
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from market_maven.tools.trader_tool import TraderTool
from market_maven.config.settings import settings

def test_trader_tool():
    """Test the TraderTool with IBAPI integration."""
    
    print("🚀 Testing Market Maven TraderTool with IBAPI")
    print("=" * 50)
    
    # Initialize the trader tool
    print("📊 Initializing TraderTool...")
    trader = TraderTool()
    
    # Test 1: Dry run trade (should work without connection)
    print("\n🧪 Test 1: Dry Run Trade")
    print("-" * 30)
    
    result = trader.execute(
        action="BUY",
        symbol="AAPL",
        quantity=10,
        order_type="MARKET",
        dry_run=True
    )
    
    print(f"Dry run result: {result['status']}")
    if result['status'] == 'simulated':
        print(f"✅ Dry run successful - Order ID: {result['order_id']}")
        print(f"   Symbol: {result['symbol']}")
        print(f"   Action: {result['action']}")
        print(f"   Quantity: {result['quantity']}")
        print(f"   Simulated Price: ${result['average_fill_price']}")
    else:
        print(f"❌ Dry run failed: {result.get('error', 'Unknown error')}")
    
    # Test 2: Connection test (will only work if TWS/Gateway is running)
    print("\n🔌 Test 2: Connection Test")
    print("-" * 30)
    
    print(f"IBKR Settings:")
    print(f"  Host: {settings.ibkr.host}")
    print(f"  Port: {settings.ibkr.port}")
    print(f"  Client ID: {settings.ibkr.client_id}")
    
    # Try to connect (this will fail gracefully if TWS is not running)
    try:
        connected = trader._ensure_connection()
        if connected:
            print("✅ Successfully connected to Interactive Brokers")
            
            # Test getting account summary
            print("\n📈 Test 3: Account Summary")
            print("-" * 30)
            
            account_result = trader.execute(action="GET_ACCOUNT_SUMMARY")
            if account_result['status'] == 'success':
                print("✅ Account summary retrieved successfully")
                print(f"   Total positions: {account_result['total_positions']}")
            else:
                print(f"❌ Account summary failed: {account_result.get('error', 'Unknown error')}")
            
            # Test getting position
            print("\n📊 Test 4: Position Check")
            print("-" * 30)
            
            position_result = trader.execute(action="GET_POSITION", symbol="AAPL")
            if position_result['status'] == 'success':
                print("✅ Position check successful")
                print(f"   AAPL Position: {position_result['position']}")
            else:
                print(f"❌ Position check failed: {position_result.get('error', 'Unknown error')}")
            
        else:
            print("❌ Failed to connect to Interactive Brokers")
            print("   This is expected if TWS/Gateway is not running")
            print("   Make sure TWS or IB Gateway is running and API is enabled")
            
    except Exception as e:
        print(f"❌ Connection test failed: {str(e)}")
        print("   This is expected if TWS/Gateway is not running")
    
    finally:
        # Clean up
        print("\n🧹 Cleanup")
        print("-" * 30)
        trader.disconnect()
        print("✅ Disconnected from Interactive Brokers")
    
    print("\n" + "=" * 50)
    print("🎉 TraderTool IBAPI integration test completed!")
    print("\nNext steps:")
    print("1. Start TWS or IB Gateway")
    print("2. Enable API connections in TWS settings")
    print("3. Run this test again to verify full functionality")
    print("4. Use dry_run=False for live trading (be careful!)")

if __name__ == "__main__":
    test_trader_tool() 