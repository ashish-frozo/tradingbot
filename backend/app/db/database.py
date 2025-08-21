"""
Database Connection Management
SQLModel with PostgreSQL backend
"""

from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from sqlmodel import SQLModel, Session, select
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Database engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Validate connections before use
    pool_recycle=3600,   # Recycle connections after 1 hour
    echo=settings.DEBUG  # Log SQL queries in debug mode
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session
)


def create_db_and_tables() -> bool:
    """Create database tables"""
    try:
        SQLModel.metadata.create_all(engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False


def get_session() -> Generator[Session, None, None]:
    """
    Dependency to get database session
    Used with FastAPI's Depends()
    """
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"Database session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


async def get_async_session() -> Generator[Session, None, None]:
    """
    Async dependency to get database session
    """
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"Async database session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def test_connection() -> bool:
    """Test database connection"""
    try:
        with engine.connect() as conn:
            # Test with a simple query
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()
            if test_value and test_value.test == 1:
                logger.info("Database connection test successful")
                return True
            else:
                logger.error("Database connection test failed: unexpected result")
                return False
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def get_db_health() -> dict:
    """Get database health status"""
    try:
        with engine.connect() as conn:
            # Get connection info
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            
            # Get current timestamp
            result = conn.execute(text("SELECT NOW()"))
            current_time = result.fetchone()[0]
            
            return {
                "status": "healthy",
                "version": version,
                "current_time": current_time.isoformat(),
                "pool_size": engine.pool.size(),
                "pool_checked_out": engine.pool.checkedout(),
                "pool_overflow": engine.pool.overflow(),
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Database initialization function
def init_db() -> bool:
    """Initialize database connection and create tables"""
    logger.info("Initializing database...")
    
    # Test connection first
    if not test_connection():
        logger.warning("Database connection failed - skipping initialization")
        return False
    
    # Create tables
    try:
        create_db_and_tables()
        logger.info("Database initialization completed")
        return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False


# Cleanup function
def close_db() -> None:
    """Close database connections"""
    try:
        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


# Export commonly used items
__all__ = [
    "engine",
    "SessionLocal", 
    "get_session",
    "get_async_session",
    "create_db_and_tables",
    "test_connection",
    "get_db_health",
    "init_db",
    "close_db"
] 