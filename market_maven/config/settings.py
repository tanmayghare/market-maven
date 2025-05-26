"""
Production-grade configuration settings for the stock agent.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseSettings, Field, validator
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class APISettings(BaseSettings):
    """API configuration settings."""
    
    alpha_vantage_api_key: str = Field(..., env='ALPHA_VANTAGE_API_KEY')
    google_api_key: str = Field(..., env='GOOGLE_API_KEY')
    
    # API endpoints
    alpha_vantage_base_url: str = "https://www.alphavantage.co/query"
    sec_edgar_base_url: str = "https://data.sec.gov/api"
    
    # Rate limiting
    alpha_vantage_requests_per_minute: int = 5
    alpha_vantage_requests_per_day: int = 500
    
    class Config:
        env_prefix = "API_"


class IBKRSettings(BaseSettings):
    """Interactive Brokers configuration settings."""
    
    host: str = Field(default="127.0.0.1", env='IBKR_HOST')
    port: int = Field(default=7496, env='IBKR_PORT')
    client_id: int = Field(default=1, env='IBKR_CLIENT_ID')
    
    # Connection settings
    connection_timeout: int = 10
    reconnect_attempts: int = 3
    reconnect_delay: int = 5
    
    class Config:
        env_prefix = "IBKR_"


class ModelSettings(BaseSettings):
    """AI model configuration settings."""
    
    gemini_model: str = Field(default="gemini-2.0-flash", env='GEMINI_MODEL')
    temperature: float = Field(default=0.1, env='MODEL_TEMPERATURE')
    max_tokens: int = Field(default=4096, env='MODEL_MAX_TOKENS')
    
    # Model behavior
    enable_streaming: bool = True
    enable_function_calling: bool = True
    
    class Config:
        env_prefix = "MODEL_"


class AnalysisSettings(BaseSettings):
    """Analysis configuration settings."""
    
    default_period: str = "1y"
    technical_indicators: List[str] = ["SMA", "EMA", "RSI", "MACD"]
    
    # Analysis thresholds
    confidence_threshold: float = 0.6
    risk_tolerance_levels: List[str] = ["conservative", "moderate", "aggressive"]
    investment_horizons: List[str] = ["short_term", "medium_term", "long_term"]
    
    # Cache settings
    enable_caching: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes
    
    class Config:
        env_prefix = "ANALYSIS_"


class TradingSettings(BaseSettings):
    """Trading configuration settings."""
    
    max_position_size: int = Field(default=100, env='MAX_POSITION_SIZE')
    stop_loss_percentage: float = Field(default=0.05, env='STOP_LOSS_PERCENTAGE')
    take_profit_percentage: float = Field(default=0.10, env='TAKE_PROFIT_PERCENTAGE')
    
    # Risk management
    max_daily_trades: int = 10
    max_portfolio_risk: float = 0.02  # 2% of portfolio
    enable_dry_run: bool = Field(default=True, env='ENABLE_DRY_RUN')
    
    # Order settings
    default_order_type: str = "MARKET"
    order_timeout_seconds: int = 30
    
    @validator('stop_loss_percentage', 'take_profit_percentage')
    def validate_percentages(cls, v):
        if not 0 < v < 1:
            raise ValueError('Percentage must be between 0 and 1')
        return v
    
    class Config:
        env_prefix = "TRADING_"


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""
    
    level: str = Field(default="INFO", env='LOG_LEVEL')
    json_logs: bool = Field(default=True, env='JSON_LOGS')
    log_file: Optional[str] = Field(default=None, env='LOG_FILE')
    
    # Structured logging
    enable_correlation_ids: bool = True
    log_sensitive_data: bool = False
    
    class Config:
        env_prefix = "LOG_"


class MetricsSettings(BaseSettings):
    """Metrics and monitoring configuration settings."""
    
    enable_metrics: bool = Field(default=True, env='ENABLE_METRICS')
    metrics_port: int = Field(default=8000, env='METRICS_PORT')
    
    # Health checks
    health_check_interval: int = 30
    enable_health_endpoint: bool = True
    
    class Config:
        env_prefix = "METRICS_"


class PostgresSettings(BaseSettings):
    """PostgreSQL database configuration settings."""
    
    host: str = Field(default="localhost", env='POSTGRES_HOST')
    port: int = Field(default=5432, env='POSTGRES_PORT')
    database: str = Field(default="marketmaven", env='POSTGRES_DB')
    user: str = Field(default="marketmaven", env='POSTGRES_USER')
    password: str = Field(..., env='POSTGRES_PASSWORD')
    
    # Connection pool settings
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    
    class Config:
        env_prefix = "POSTGRES_"


class RedisSettings(BaseSettings):
    """Redis configuration settings."""
    
    url: str = Field(default="redis://localhost:6379", env='REDIS_URL')
    password: Optional[str] = Field(default=None, env='REDIS_PASSWORD')
    db: int = Field(default=0, env='REDIS_DB')
    
    # Connection settings
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    
    class Config:
        env_prefix = "REDIS_"


class SecuritySettings(BaseSettings):
    """Security configuration settings."""
    
    enable_api_key_rotation: bool = False
    api_key_rotation_days: int = 30
    
    # Data encryption
    encrypt_sensitive_data: bool = True
    encryption_key: Optional[str] = Field(default=None, env='ENCRYPTION_KEY')
    
    # Rate limiting
    enable_rate_limiting: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1 hour
    
    class Config:
        env_prefix = "SECURITY_"


class Settings(BaseSettings):
    """Main application settings."""
    
    # Environment
    environment: str = Field(default="development", env='ENVIRONMENT')
    debug: bool = Field(default=False, env='DEBUG')
    
    # Component settings
    api: APISettings = APISettings()
    ibkr: IBKRSettings = IBKRSettings()
    model: ModelSettings = ModelSettings()
    analysis: AnalysisSettings = AnalysisSettings()
    trading: TradingSettings = TradingSettings()
    logging: LoggingSettings = LoggingSettings()
    metrics: MetricsSettings = MetricsSettings()
    postgres: PostgresSettings = PostgresSettings()
    redis: RedisSettings = RedisSettings()
    security: SecuritySettings = SecuritySettings()
    
    @validator('environment')
    def validate_environment(cls, v):
        allowed = ['development', 'staging', 'production']
        if v not in allowed:
            raise ValueError(f'Environment must be one of {allowed}')
        return v
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


# Convenience functions for backward compatibility
def get_alpha_vantage_api_key() -> str:
    """Get Alpha Vantage API key."""
    return settings.api.alpha_vantage_api_key


def get_google_api_key() -> str:
    """Get Google API key."""
    return settings.api.google_api_key


def get_ibkr_config() -> Dict[str, Any]:
    """Get IBKR configuration."""
    return {
        "host": settings.ibkr.host,
        "port": settings.ibkr.port,
        "client_id": settings.ibkr.client_id,
        "timeout": settings.ibkr.connection_timeout,
    }


# Legacy constants for backward compatibility
ALPHA_VANTAGE_API_KEY = settings.api.alpha_vantage_api_key
GOOGLE_API_KEY = settings.api.google_api_key
ALPHA_VANTAGE_BASE_URL = settings.api.alpha_vantage_base_url
IBKR_HOST = settings.ibkr.host
IBKR_PORT = settings.ibkr.port
IBKR_CLIENT_ID = settings.ibkr.client_id
MAX_POSITION_SIZE = settings.trading.max_position_size
DEFAULT_ANALYSIS_PERIOD = settings.analysis.default_period 