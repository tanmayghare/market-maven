"""
Database initialization and management utilities.
"""

import asyncio
import sys
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from market_maven.core.database import (
    init_database, 
    create_tables, 
    drop_tables, 
    get_async_db,
    health_check,
    engine,
    async_engine
)
from market_maven.core.logging import get_logger
from market_maven.models.db_models import *  # Import all models
from market_maven.config.settings import settings

logger = get_logger(__name__)


class DatabaseManager:
    """Comprehensive database management utilities."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
    async def initialize_database(self, force: bool = False) -> bool:
        """Initialize the database with all tables and indexes."""
        try:
            self.logger.info("Initializing database...")
            
            # Initialize connections
            init_database()
            
            # Check if database is already initialized
            if not force and await self._is_database_initialized():
                self.logger.info("Database already initialized")
                return True
            
            # Create all tables
            await create_tables()
            
            # Create indexes and constraints
            await self._create_custom_indexes()
            
            # Seed initial data if needed
            await self._seed_initial_data()
            
            self.logger.info("Database initialization completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            return False
    
    async def reset_database(self) -> bool:
        """Reset the database by dropping and recreating all tables."""
        try:
            self.logger.warning("Resetting database - all data will be lost!")
            
            # Drop all tables
            await drop_tables()
            
            # Recreate tables
            await create_tables()
            
            # Create indexes
            await self._create_custom_indexes()
            
            # Seed initial data
            await self._seed_initial_data()
            
            self.logger.info("Database reset completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Database reset failed: {e}")
            return False
    
    async def _is_database_initialized(self) -> bool:
        """Check if database has been initialized."""
        try:
            async with get_async_db() as db:
                # Check if key tables exist
                result = await db.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('stock_symbols', 'analysis_results', 'trade_orders')
                """))
                tables = result.fetchall()
                return len(tables) >= 3
        except Exception:
            return False
    
    async def _create_custom_indexes(self) -> None:
        """Create custom database indexes for performance."""
        try:
            async with get_async_db() as db:
                # Performance indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_price_history_symbol_date ON stock_price_history(stock_id, timestamp DESC)",
                    "CREATE INDEX IF NOT EXISTS idx_analysis_results_symbol_date ON analysis_results(stock_id, created_at DESC)",
                    "CREATE INDEX IF NOT EXISTS idx_trade_orders_status_date ON trade_orders(status, created_at DESC)",
                    "CREATE INDEX IF NOT EXISTS idx_audit_logs_action_date ON audit_logs(action_type, created_at DESC)",
                    
                    # Composite indexes for common queries
                    "CREATE INDEX IF NOT EXISTS idx_stock_symbols_active_sector ON stock_symbols(is_active, sector) WHERE is_active = true",
                    "CREATE INDEX IF NOT EXISTS idx_price_history_volume_date ON stock_price_history(volume DESC, timestamp DESC)",
                    
                    # Partial indexes for active records
                    "CREATE INDEX IF NOT EXISTS idx_alerts_active ON alert_configurations(stock_id, alert_type) WHERE is_active = true",
                    "CREATE INDEX IF NOT EXISTS idx_orders_pending ON trade_orders(stock_id, created_at) WHERE status IN ('PENDING', 'SUBMITTED')",
                ]
                
                for index_sql in indexes:
                    await db.execute(text(index_sql))
                
                await db.commit()
                self.logger.info("Custom indexes created successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to create custom indexes: {e}")
    
    async def _seed_initial_data(self) -> None:
        """Seed database with initial data."""
        try:
            async with get_async_db() as db:
                # Check if data already exists
                result = await db.execute(text("SELECT COUNT(*) FROM stock_symbols"))
                count = result.scalar()
                
                if count > 0:
                    self.logger.info("Initial data already exists, skipping seeding")
                    return
                
                # Seed popular stock symbols
                popular_stocks = [
                    {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology", "country": "US"},
                    {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Technology", "country": "US"},
                    {"symbol": "MSFT", "name": "Microsoft Corporation", "sector": "Technology", "country": "US"},
                    {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Discretionary", "country": "US"},
                    {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Consumer Discretionary", "country": "US"},
                    {"symbol": "META", "name": "Meta Platforms Inc.", "sector": "Technology", "country": "US"},
                    {"symbol": "NVDA", "name": "NVIDIA Corporation", "sector": "Technology", "country": "US"},
                    {"symbol": "NFLX", "name": "Netflix Inc.", "sector": "Communication Services", "country": "US"},
                    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "sector": "Financials", "country": "US"},
                    {"symbol": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare", "country": "US"},
                ]
                
                for stock_data in popular_stocks:
                    stock = StockSymbol(**stock_data)
                    db.add(stock)
                
                await db.commit()
                self.logger.info(f"Seeded {len(popular_stocks)} initial stock symbols")
                
        except Exception as e:
            self.logger.error(f"Failed to seed initial data: {e}")
    
    async def validate_database_schema(self) -> bool:
        """Validate that the database schema is correct."""
        try:
            async with get_async_db() as db:
                # Check all required tables exist
                required_tables = [
                    'stock_symbols', 'stock_price_history', 'company_info',
                    'analysis_results', 'trade_orders', 'trade_executions',
                    'portfolio_snapshots', 'alert_configurations', 'audit_logs',
                    'users', 'api_keys'
                ]
                
                for table in required_tables:
                    result = await db.execute(text(f"""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = '{table}'
                        )
                    """))
                    exists = result.scalar()
                    if not exists:
                        self.logger.error(f"Required table '{table}' does not exist")
                        return False
                
                self.logger.info("Database schema validation successful")
                return True
                
        except Exception as e:
            self.logger.error(f"Database schema validation failed: {e}")
            return False
    
    def check_health(self) -> dict:
        """Comprehensive database health check."""
        try:
            # Basic connectivity check
            is_connected = health_check()
            
            result = {
                "status": "healthy" if is_connected else "unhealthy",
                "connected": is_connected,
                "details": {}
            }
            
            if is_connected:
                # Additional health metrics
                result["details"]["pool_size"] = engine.pool.size() if engine else 0
                result["details"]["pool_checked_in"] = engine.pool.checkedin() if engine else 0
                result["details"]["pool_checked_out"] = engine.pool.checkedout() if engine else 0
            
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "connected": False,
                "error": str(e)
            }
    
    async def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """Clean up old data to maintain database performance."""
        try:
            async with get_async_db() as db:
                # Clean up old audit logs
                await db.execute(text(f"""
                    DELETE FROM audit_logs 
                    WHERE created_at < NOW() - INTERVAL '{days_to_keep} days'
                """))
                
                # Clean up old analysis results
                await db.execute(text(f"""
                    DELETE FROM analysis_results 
                    WHERE created_at < NOW() - INTERVAL '{days_to_keep} days'
                    AND expires_at < NOW()
                """))
                
                # Clean up old portfolio snapshots (keep daily snapshots)
                await db.execute(text(f"""
                    DELETE FROM portfolio_snapshots 
                    WHERE created_at < NOW() - INTERVAL '{days_to_keep} days'
                    AND created_at NOT IN (
                        SELECT DISTINCT DATE_TRUNC('day', created_at)
                        FROM portfolio_snapshots
                    )
                """))
                
                await db.commit()
                self.logger.info(f"Cleaned up data older than {days_to_keep} days")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")


# Global database manager instance
db_manager = DatabaseManager()


async def init_db():
    """Initialize database - convenience function."""
    return await db_manager.initialize_database()


async def reset_db():
    """Reset database - convenience function."""
    return await db_manager.reset_database()


def main():
    """CLI interface for database management."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Database management utility")
    parser.add_argument("action", choices=["init", "reset", "health", "validate", "cleanup"],
                       help="Action to perform")
    parser.add_argument("--force", action="store_true",
                       help="Force action even if database exists")
    parser.add_argument("--days", type=int, default=30,
                       help="Days to keep for cleanup action")
    
    args = parser.parse_args()
    
    if args.action == "init":
        success = asyncio.run(db_manager.initialize_database(force=args.force))
        sys.exit(0 if success else 1)
    elif args.action == "reset":
        success = asyncio.run(db_manager.reset_database())
        sys.exit(0 if success else 1)
    elif args.action == "health":
        result = db_manager.check_health()
        print(f"Database health: {result}")
        sys.exit(0 if result["status"] == "healthy" else 1)
    elif args.action == "validate":
        success = asyncio.run(db_manager.validate_database_schema())
        sys.exit(0 if success else 1)
    elif args.action == "cleanup":
        asyncio.run(db_manager.cleanup_old_data(days_to_keep=args.days))
        sys.exit(0)


if __name__ == "__main__":
    main() 