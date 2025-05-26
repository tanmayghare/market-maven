"""
Database connection and ORM setup for the stock agent.
"""

import os
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from market_maven.config.settings import settings
from market_maven.core.logging import get_logger

logger = get_logger(__name__)

# Database metadata and base
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# Database engines
engine = None
async_engine = None
SessionLocal = None
AsyncSessionLocal = None


def get_database_url() -> str:
    """Get database URL from environment or settings."""
    return os.getenv(
        "DATABASE_URL",
        f"postgresql://{settings.postgres.user}:{settings.postgres.password}@{settings.postgres.host}:{settings.postgres.port}/{settings.postgres.database}"
    )


def get_async_database_url() -> str:
    """Get async database URL."""
    url = get_database_url()
    return url.replace("postgresql://", "postgresql+asyncpg://")


def init_database() -> None:
    """Initialize database connections."""
    global engine, async_engine, SessionLocal, AsyncSessionLocal
    
    database_url = get_database_url()
    async_database_url = get_async_database_url()
    
    # Synchronous engine
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.debug
    )
    
    # Asynchronous engine
    async_engine = create_async_engine(
        async_database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.debug
    )
    
    # Session factories
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    logger.info("Database connections initialized")


def get_db():
    """Get synchronous database session."""
    if SessionLocal is None:
        init_database()
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Get asynchronous database session."""
    if AsyncSessionLocal is None:
        init_database()
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all database tables."""
    if async_engine is None:
        init_database()
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created")


async def drop_tables() -> None:
    """Drop all database tables."""
    if async_engine is None:
        init_database()
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.info("Database tables dropped")


def health_check() -> bool:
    """Check database connectivity."""
    try:
        if engine is None:
            init_database()
        
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False 