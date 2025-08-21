"""
Health Check API Endpoints
Comprehensive system health monitoring
"""

import time
import psutil
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import get_db_health
from app.cache import get_redis_health
from app.websockets import get_socket_manager
from app.data import get_option_chain_feed, get_ltp_feed, get_market_data_storage, get_validation_health
from app.worker.data_retention import get_data_retention_worker, manual_data_cleanup

logger = get_logger(__name__)

# Create health router
health_router = APIRouter(prefix="/health", tags=["Health"])


@health_router.get("/")
async def main_health_check():
    """Comprehensive health check with all system components"""
    try:
        # Get component health
        db_health = get_db_health()
        redis_health = await get_redis_health()
        system_health = get_system_health()
        ws_health = await get_websocket_health()
        feed_health = await get_data_feed_health()
        ltp_health = await get_ltp_feed_health()
        validation_health = await get_validation_health_status()
        
        # Determine overall status
        components_healthy = (
            db_health["status"] == "healthy" and 
            redis_health["status"] == "healthy" and
            system_health["status"] == "healthy" and
            ws_health["status"] == "healthy" and
            feed_health["status"] in ["healthy", "degraded"] and  # Feed can be degraded during non-market hours
            ltp_health["status"] in ["healthy", "degraded"]  # LTP feed can be degraded during non-market hours
        )
        
        overall_status = "healthy" if components_healthy else "degraded"
        
        # Check for critical failures
        critical_failure = (
            db_health["status"] == "critical" or 
            redis_health["status"] == "critical" or
            system_health["status"] == "critical"
        )
        
        if critical_failure:
            overall_status = "critical"
        
        return {
            "status": overall_status,
            "service": "QuantHub Trading Bot",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.ENVIRONMENT,
            "uptime": get_uptime(),
            "components": {
                "database": db_health,
                "redis": redis_health,
                "system": system_health,
                "websocket": ws_health,
                "data_feed": feed_health,
                "ltp_feed": ltp_health,
                "validation": validation_health
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "critical",
            "service": "QuantHub Trading Bot",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@health_router.get("/database")
async def database_health():
    """Database-specific health check with detailed metrics"""
    return get_db_health()


@health_router.get("/redis")
async def redis_health():
    """Redis cache health check with metrics"""
    return await get_redis_health()


@health_router.get("/websocket")
async def websocket_health():
    """WebSocket connections health check"""
    try:
        socket_manager = get_socket_manager()
        stats = socket_manager.get_stats()
        
        return {
            "status": "healthy",
            "connections": stats["active_connections"],
            "total_connections": stats["total_connections"],
            "messages_sent": stats["messages_sent"],
            "messages_received": stats["messages_received"],
            "errors": stats["errors"],
            "connection_details": stats["connection_details"]
        }
        
    except Exception as e:
        logger.error(f"WebSocket health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@health_router.get("/system")
async def system_health():
    """System resources health check"""
    return get_system_health()


@health_router.get("/datafeed")
async def data_feed_health():
    """Option chain data feed health check"""
    return await get_data_feed_health()


@health_router.get("/ltpfeed")
async def ltp_feed_health():
    """LTP (Last Traded Price) data feed health check"""
    return await get_ltp_feed_health()


@health_router.get("/storage")
async def storage_health():
    """Market data storage system health check"""
    return await get_storage_health()


@health_router.post("/storage/cleanup")
async def trigger_storage_cleanup():
    """Manually trigger data retention cleanup"""
    return await manual_data_cleanup()


@health_router.get("/validation")
async def validation_health():
    """Data validation system health check"""
    return await get_validation_health_status()


@health_router.get("/detailed")
async def detailed_health_check():
    """Detailed health check with all metrics and diagnostics"""
    try:
        # Get all component health
        db_health = get_db_health()
        redis_health = await get_redis_health()
        system_health = get_system_health()
        ws_health = await get_websocket_health()
        feed_health = await get_data_feed_health()
        ltp_health = await get_ltp_feed_health()
        storage_health = await get_storage_health()
        validation_health = await get_validation_health_status()
        
        # Additional diagnostics
        diagnostics = get_system_diagnostics()
        
        return {
            "status": "healthy",
            "service": "QuantHub Trading Bot",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.ENVIRONMENT,
            "debug_mode": settings.DEBUG,
            "uptime": get_uptime(),
            "components": {
                "database": db_health,
                "redis": redis_health,
                "system": system_health,
                "websocket": ws_health,
                "data_feed": feed_health,
                "ltp_feed": ltp_health,
                "storage": storage_health,
                "validation": validation_health
            },
            "diagnostics": diagnostics,
            "configuration": {
                "cors_origins": settings.CORS_ORIGINS,
                "log_level": settings.LOG_LEVEL,
                "trading_enabled": getattr(settings, 'TRADING_ENABLED', False),
                "paper_trading": getattr(settings, 'PAPER_TRADING', True)
            }
        }
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )


@health_router.get("/ready")
async def readiness_check():
    """Kubernetes/Docker readiness probe - minimal response"""
    try:
        # Quick checks for essential services
        db_health = get_db_health()
        redis_health = await get_redis_health()
        
        # Service is ready if at least one data store is available
        ready = (
            db_health["status"] in ["healthy", "degraded"] or 
            redis_health["status"] in ["healthy", "degraded"]
        )
        
        if ready:
            return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not ready"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )


@health_router.get("/live")
async def liveness_check():
    """Kubernetes/Docker liveness probe - minimal response"""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": get_uptime()
    }


# Health check helper functions
async def get_data_feed_health() -> Dict[str, Any]:
    """Get option chain data feed health"""
    try:
        feed = await get_option_chain_feed()
        return await feed.get_health_status()
        
    except Exception as e:
        logger.error(f"Data feed health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


async def get_ltp_feed_health() -> Dict[str, Any]:
    """Get LTP data feed health"""
    try:
        feed = await get_ltp_feed()
        return await feed.get_health_status()
        
    except Exception as e:
        logger.error(f"LTP feed health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


async def get_websocket_health() -> Dict[str, Any]:
    """Get WebSocket system health"""
    try:
        socket_manager = get_socket_manager()
        stats = socket_manager.get_stats()
        
        return {
            "status": "healthy",
            "connections": stats["active_connections"],
            "total_connections": stats["total_connections"],
            "messages_sent": stats["messages_sent"],
            "messages_received": stats["messages_received"],
            "errors": stats["errors"]
        }
        
    except Exception as e:
        logger.error(f"WebSocket health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def get_system_health() -> Dict[str, Any]:
    """Get system resource health metrics"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage (root partition)
        disk = psutil.disk_usage('/')
        
        # Determine status based on thresholds
        status = "healthy"
        
        if cpu_percent > 90 or memory.percent > 95 or disk.percent > 95:
            status = "critical"
        elif cpu_percent > 80 or memory.percent > 85 or disk.percent > 85:
            status = "degraded"
        
        return {
            "status": status,
            "cpu": {
                "usage_percent": round(cpu_percent, 2),
                "count": psutil.cpu_count()
            },
            "memory": {
                "usage_percent": round(memory.percent, 2),
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2)
            },
            "disk": {
                "usage_percent": round(disk.percent, 2),
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2)
            }
        }
        
    except Exception as e:
        logger.error(f"System health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def get_storage_health() -> Dict[str, Any]:
    """Get market data storage system health"""
    try:
        storage = await get_market_data_storage()
        
        # Get storage statistics
        stats = await storage.get_storage_stats()
        
        # Get data retention worker status
        worker = await get_data_retention_worker()
        
        # Determine overall storage health status
        status = "healthy"
        record_counts = stats.get("record_counts", {})
        latest_timestamps = stats.get("latest_timestamps", {})
        
        # Check if storage is receiving data (recent timestamps)
        now = datetime.utcnow()
        
        # Check LTP data freshness (should be recent if market is open)
        latest_raw = latest_timestamps.get("raw_ticks")
        if latest_raw:
            time_diff = now - latest_raw
            if time_diff > timedelta(minutes=5):
                status = "degraded"  # No recent raw data
                
        return {
            "status": status,
            "storage_stats": stats,
            "data_retention": {
                "worker_running": worker.is_running if worker else False,
                "last_cleanup": stats.get("buffer_status", {}).get("last_cleanup")
            },
            "record_counts": record_counts,
            "buffer_status": stats.get("buffer_status", {}),
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


def get_system_diagnostics() -> Dict[str, Any]:
    """Get detailed system diagnostics"""
    try:
        # Network interfaces
        network_info = {}
        for interface, addresses in psutil.net_if_addrs().items():
            network_info[interface] = [addr.address for addr in addresses]
        
        # Process info
        process = psutil.Process()
        
        return {
            "python_version": f"{psutil.version_info}",
            "platform": psutil.PLATFORM,
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
            "network_interfaces": network_info,
            "process": {
                "pid": process.pid,
                "memory_mb": round(process.memory_info().rss / (1024**2), 2),
                "cpu_percent": round(process.cpu_percent(), 2),
                "create_time": datetime.fromtimestamp(process.create_time()).isoformat(),
                "num_threads": process.num_threads()
            }
        }
        
    except Exception as e:
        logger.error(f"System diagnostics failed: {e}")
        return {"error": str(e)}


# Global start time for uptime calculation
start_time = time.time()

def get_uptime() -> Dict[str, Any]:
    """Calculate service uptime"""
    uptime_seconds = time.time() - start_time
    uptime_delta = timedelta(seconds=uptime_seconds)
    
    return {
        "seconds": round(uptime_seconds, 2),
        "human_readable": str(uptime_delta).split('.')[0],  # Remove microseconds
        "started_at": datetime.fromtimestamp(start_time).isoformat()
    }


async def get_validation_health_status() -> Dict[str, Any]:
    """Get data validation system health status"""
    try:
        validation_health = await get_validation_health()
        
        # Convert to health check format
        if validation_health["status"] == "healthy":
            status = "healthy"
        elif validation_health["status"] == "degraded":
            status = "degraded"
        else:
            status = "unhealthy"
        
        return {
            "status": status,
            "total_symbols_tracked": validation_health.get("total_symbols_tracked", 0),
            "circuit_breakers_open": sum(
                1 for cb in validation_health.get("circuit_breakers", {}).values() 
                if cb.get("is_open", False)
            ),
            "average_quality_scores": validation_health.get("average_quality_scores", {}),
            "timestamp": validation_health.get("timestamp"),
            "details": validation_health
        }
        
    except Exception as e:
        logger.error(f"Validation health check failed: {e}")
        return {
            "status": "critical",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Export router
__all__ = ["health_router"] 