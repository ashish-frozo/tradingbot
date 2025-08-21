#!/usr/bin/env python3
"""
Quant Hub Trading Bot - Main Application
FastAPI application factory with Socket.IO integration
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
import socketio
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.middleware import setup_middleware
from app.core.exception_handlers import setup_exception_handlers
from app.db.database import init_db, close_db, get_db_health, test_connection
from app.db.models import *  # Import all models to register them
from app.api import sentiment_api
from app.cache import init_redis, close_redis, get_redis_health
from app.api.health import health_router
from app.api.test import test_router
from app.websockets import get_socket_manager, setup_socket_events
from app.websockets.events import cleanup_socket_events
from app.data import start_option_chain_feed, stop_option_chain_feed, start_ltp_feed, stop_ltp_feed
from app.data import get_statistical_processor, cleanup_statistical_processor
from app.worker.data_retention import start_data_retention_worker, stop_data_retention_worker


# Initialize Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True
)

# Create Socket.IO ASGI app
socket_app = socketio.ASGIApp(sio)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    setup_logging()
    logger = get_logger(__name__)
    
    logger.info("🚀 Quant Hub Trading Bot starting up...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Database URL: {settings.DATABASE_URL[:50]}...")
    
    try:
        # Initialize database
        logger.info("Initializing database connection...")
        db_initialized = init_db()
        if db_initialized:
            logger.info("Database initialized successfully")
        else:
            logger.warning("Database initialization failed - continuing without database")
        
        # Initialize Redis connection
        logger.info("Initializing Redis cache...")
        await init_redis()
        redis_health = await get_redis_health()
        if redis_health["status"] == "healthy":
            logger.info("Redis cache initialized successfully")
        else:
            logger.warning(f"Redis cache initialization failed: {redis_health.get('error', 'Unknown error')}")
        
        # Initialize WebSocket system
        logger.info("Setting up WebSocket events...")
        await setup_socket_events()
        logger.info("WebSocket system initialized successfully")
        
        # Start option chain data feed
        logger.info("Starting option chain data feed...")
        try:
            await start_option_chain_feed()
            logger.info("Option chain data feed started successfully")
        except Exception as e:
            logger.warning(f"Failed to start option chain data feed: {e}")
            # Continue without data feed for now
        
        # Start LTP data feed
        logger.info("Starting LTP data feed...")
        try:
            await start_ltp_feed()
            logger.info("LTP data feed started successfully")
        except Exception as e:
            logger.warning(f"Failed to start LTP data feed: {e}")
            # Continue without LTP feed for now
        
        # Start data retention worker
        logger.info("Starting data retention worker...")
        try:
            await start_data_retention_worker()
            logger.info("Data retention worker started successfully")
        except Exception as e:
            logger.warning(f"Failed to start data retention worker: {e}")
            # Continue without retention worker for now
        
        # Initialize statistical processor
        logger.info("Starting statistical processor...")
        try:
            await get_statistical_processor()
            logger.info("Statistical processor started successfully")
        except Exception as e:
            logger.warning(f"Failed to start statistical processor: {e}")
            # Continue without statistical processor for now
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("⏹️  Quant Hub Trading Bot shutting down...")
    try:
        # Stop option chain data feed
        logger.info("Stopping option chain data feed...")
        await stop_option_chain_feed()
        logger.info("Option chain data feed stopped")
        
        # Stop LTP data feed
        logger.info("Stopping LTP data feed...")
        await stop_ltp_feed()
        logger.info("LTP data feed stopped")
        
        # Stop data retention worker
        logger.info("Stopping data retention worker...")
        await stop_data_retention_worker()
        logger.info("Data retention worker stopped")
        
        # Stop statistical processor
        logger.info("Stopping statistical processor...")
        await cleanup_statistical_processor()
        logger.info("Statistical processor stopped")
        
        # Cleanup WebSocket system
        await cleanup_socket_events()
        logger.info("WebSocket system cleaned up")
        
        # Close Redis connections
        await close_redis()
        logger.info("Redis connections closed")
        
        # Close database connections
        close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def create_app() -> FastAPI:
    """Create FastAPI application with all configurations"""
    
    app = FastAPI(
        title="Quant Hub Trading Bot",
        description="Low-latency options trading bot with Volume + OI confirmation strategy",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None
    )
    
    # Setup exception handlers (must be before middleware)
    setup_exception_handlers(app)
    
    # Setup all middleware (CORS, logging, security, etc.)
    setup_middleware(app)
    
    # Include routers
    app.include_router(health_router)
    app.include_router(test_router)
    
    # Mount Socket.IO app
    socket_manager = get_socket_manager()
    socket_app = socket_manager.get_asgi_app()
    app.mount("/socket.io", socket_app)
    
    # Legacy health check endpoint (redirect to new comprehensive health)
    @app.get("/healthz")
    async def health_check():
        """Legacy health check endpoint - redirects to /health/"""
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/health/", status_code=307)
    
    # Additional legacy endpoint
    @app.get("/ping")
    async def ping():
        """Simple ping endpoint for basic connectivity checks"""
        return {"status": "pong", "timestamp": db_health.get("current_time") if (db_health := get_db_health()) else None}
    
    # Include API routers
    app.include_router(sentiment_api.router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(test_router, prefix="/api/v1")
    
    # Mount Socket.IO app
    app.mount("/socket.io", socket_app)
    
    return app


# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    print(f"Client {sid} connected")
    await sio.emit('connection_ack', {'status': 'connected'}, room=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    print(f"Client {sid} disconnected")


# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 