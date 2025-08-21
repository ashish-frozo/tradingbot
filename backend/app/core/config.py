"""
Application Configuration Management
Centralized settings and environment variables
"""

import os
from typing import Any, Dict, Optional, List
from pydantic import Field, validator, AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application
    APP_NAME: str = "QuantHub Trading Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # Server
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    RELOAD: bool = Field(default=True, env="RELOAD")
    
    # Security
    SECRET_KEY: str = Field(default="super-secret-dev-key-change-in-production", env="SECRET_KEY")
    CORS_ORIGINS: List[str] = Field(default=["*"], env="CORS_ORIGINS")
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/quanthub_db",
        env="DATABASE_URL"
    )
    DB_POOL_SIZE: int = Field(default=20, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=30, env="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")
    DB_POOL_RECYCLE: int = Field(default=3600, env="DB_POOL_RECYCLE")  # 1 hour
    
    # Redis Cache
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    REDIS_MAX_CONNECTIONS: int = Field(default=20, env="REDIS_MAX_CONNECTIONS")
    REDIS_SOCKET_TIMEOUT: int = Field(default=5, env="REDIS_SOCKET_TIMEOUT")
    REDIS_SOCKET_CONNECT_TIMEOUT: int = Field(default=5, env="REDIS_SOCKET_CONNECT_TIMEOUT")
    REDIS_HEALTH_CHECK_INTERVAL: int = Field(default=30, env="REDIS_HEALTH_CHECK_INTERVAL")
    
    # Trading Configuration
    DHAN_CLIENT_ID: Optional[str] = Field(default=None, env="DHAN_CLIENT_ID")
    DHAN_ACCESS_TOKEN: Optional[str] = Field(default=None, env="DHAN_ACCESS_TOKEN")
    DHAN_USERNAME: Optional[str] = Field(default=None, env="DHAN_USERNAME")
    DHAN_PASSWORD: Optional[str] = Field(default=None, env="DHAN_PASSWORD")
    DHAN_BASE_URL: str = Field(default="https://api.dhan.co", env="DHAN_BASE_URL")
    DHAN_TOKEN_REFRESH_HOUR: int = Field(default=8, env="DHAN_TOKEN_REFRESH_HOUR")
    DHAN_TOKEN_REFRESH_MINUTE: int = Field(default=50, env="DHAN_TOKEN_REFRESH_MINUTE")
    TRADING_ENABLED: bool = Field(default=False, env="TRADING_ENABLED")
    PAPER_TRADING: bool = Field(default=True, env="PAPER_TRADING")
    
    # Market Data Configuration
    NIFTY_UNDERLYING_SYMBOLS: List[Dict[str, Any]] = Field(default=[
        {
            "symbol": "NIFTY",
            "security_id": "26000",  # NIFTY 50 
            "exchange_segment": "NSE_FNO"
        },
        {
            "symbol": "BANKNIFTY", 
            "security_id": "26009",  # BANK NIFTY
            "exchange_segment": "NSE_FNO"
        }
    ])
    
    # Futures Configuration for LTP data
    NIFTY_FUTURES_SYMBOLS: List[Dict[str, Any]] = Field(default=[
        {
            "symbol": "NIFTY",
            "trading_symbol": "NIFTY25JAN",  # Current month contract (changes monthly)
            "security_id": "52175",  # Example security ID (changes monthly)
            "exchange_segment": "NSE_FNO",
            "lot_size": 25
        },
        {
            "symbol": "BANKNIFTY",
            "trading_symbol": "BANKNIFTY25JAN",  # Current month contract (changes monthly)
            "security_id": "52179",  # Example security ID (changes monthly)
            "exchange_segment": "NSE_FNO",
            "lot_size": 15
        }
    ])
    
    DATA_FEED_INTERVAL: float = Field(default=3.0, env="DATA_FEED_INTERVAL")  # seconds
    LTP_FEED_INTERVAL: float = Field(default=1.0, env="LTP_FEED_INTERVAL")  # seconds for LTP updates
    
    # Risk Management
    MAX_DAILY_LOSS: float = Field(default=25000.0, env="MAX_DAILY_LOSS")  # ₹25,000
    MAX_POSITION_SIZE: int = Field(default=10, env="MAX_POSITION_SIZE")  # lots
    MIN_ACCOUNT_BALANCE: float = Field(default=50000.0, env="MIN_ACCOUNT_BALANCE")  # ₹50,000
    
    # Performance Monitoring
    LATENCY_THRESHOLD_MS: int = Field(default=150, env="LATENCY_THRESHOLD_MS")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    
    # Celery (for background tasks)
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        env="CELERY_BROKER_URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1",
        env="CELERY_RESULT_BACKEND"
    )
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        """Parse CORS origins from string or list"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format"""
        if not v.startswith(("postgresql://", "postgresql+psycopg2://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must start with postgresql://")
        return v
    
    @validator("REDIS_URL", pre=True) 
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format"""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("Redis URL must start with redis:// or rediss://")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            """Prioritize environment variables over .env file"""
            return (
                init_settings,
                env_settings,
                file_secret_settings,
            )


# Global settings instance
settings = Settings()


# Export commonly used settings
DATABASE_URL = settings.DATABASE_URL
REDIS_URL = settings.REDIS_URL
SECRET_KEY = settings.SECRET_KEY
DEBUG = settings.DEBUG
ENVIRONMENT = settings.ENVIRONMENT


# Utility functions
def is_development() -> bool:
    """Check if running in development environment"""
    return settings.ENVIRONMENT.lower() in ("development", "dev")


def is_production() -> bool:
    """Check if running in production environment"""
    return settings.ENVIRONMENT.lower() in ("production", "prod")


def is_testing() -> bool:
    """Check if running in testing environment"""
    return settings.ENVIRONMENT.lower() in ("testing", "test")


def get_database_config() -> Dict[str, Any]:
    """Get database configuration dictionary"""
    return {
        "url": settings.DATABASE_URL,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    }


def get_redis_config() -> Dict[str, Any]:
    """Get Redis configuration dictionary"""
    return {
        "url": settings.REDIS_URL,
        "max_connections": settings.REDIS_MAX_CONNECTIONS,
        "socket_timeout": settings.REDIS_SOCKET_TIMEOUT,
        "socket_connect_timeout": settings.REDIS_SOCKET_CONNECT_TIMEOUT,
        "health_check_interval": settings.REDIS_HEALTH_CHECK_INTERVAL,
    }


def get_trading_config() -> Dict[str, Any]:
    """Get trading configuration dictionary"""
    return {
        "dhan_client_id": settings.DHAN_CLIENT_ID,
        "dhan_access_token": settings.DHAN_ACCESS_TOKEN,
        "dhan_username": settings.DHAN_USERNAME,
        "dhan_password": settings.DHAN_PASSWORD,
        "dhan_base_url": settings.DHAN_BASE_URL,
        "dhan_token_refresh_hour": settings.DHAN_TOKEN_REFRESH_HOUR,
        "dhan_token_refresh_minute": settings.DHAN_TOKEN_REFRESH_MINUTE,
        "trading_enabled": settings.TRADING_ENABLED,
        "paper_trading": settings.PAPER_TRADING,
        "max_daily_loss": settings.MAX_DAILY_LOSS,
        "max_position_size": settings.MAX_POSITION_SIZE,
        "min_account_balance": settings.MIN_ACCOUNT_BALANCE,
    }


# Export all
__all__ = [
    "Settings",
    "settings",
    "DATABASE_URL",
    "REDIS_URL", 
    "SECRET_KEY",
    "DEBUG",
    "ENVIRONMENT",
    "is_development",
    "is_production",
    "is_testing",
    "get_database_config",
    "get_redis_config",
    "get_trading_config"
] 