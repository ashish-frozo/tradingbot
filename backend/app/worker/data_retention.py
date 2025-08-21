"""
Data Retention Worker

Handles automatic cleanup of expired market data based on retention policies:
- Raw WebSocket data: 7 days
- Derived metrics: 2 years  
- Minute bars: 90 days
- Market summaries: Indefinite
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from app.core.logging import get_logger
from app.data.storage import get_market_data_storage
from app.core.config import settings

logger = get_logger(__name__)

class DataRetentionWorker:
    """
    Background worker for data retention and cleanup
    """
    
    def __init__(self):
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._storage = None
        
    async def start(self):
        """Start the data retention worker"""
        if self.is_running:
            logger.warning("Data retention worker is already running")
            return
            
        self.is_running = True
        self._storage = await get_market_data_storage()
        
        # Start the background cleanup task
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("Data retention worker started")
        
    async def stop(self):
        """Stop the data retention worker"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            
        logger.info("Data retention worker stopped")
        
    async def _cleanup_loop(self):
        """Main cleanup loop - runs every 6 hours"""
        cleanup_interval = 6 * 3600  # 6 hours in seconds
        
        while self.is_running:
            try:
                await self._perform_cleanup()
                await asyncio.sleep(cleanup_interval)
                
            except asyncio.CancelledError:
                logger.info("Data retention cleanup loop cancelled")
                break
                
            except Exception as e:
                logger.error(f"Error in data retention cleanup loop: {e}")
                # Sleep for shorter interval on error before retrying
                await asyncio.sleep(300)  # 5 minutes
                
    async def _perform_cleanup(self):
        """Perform the actual data cleanup"""
        logger.info("Starting data retention cleanup...")
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Run the cleanup
            cleanup_stats = await self._storage.cleanup_expired_data()
            
            # Calculate duration
            duration = datetime.now(timezone.utc) - start_time
            
            # Log results
            total_deleted = sum(cleanup_stats.values())
            if total_deleted > 0:
                logger.info(
                    f"Data cleanup completed in {duration.total_seconds():.2f}s: "
                    f"Raw ticks: {cleanup_stats.get('raw_ticks_deleted', 0)}, "
                    f"Derived metrics: {cleanup_stats.get('derived_metrics_deleted', 0)}, "
                    f"Minute bars: {cleanup_stats.get('minute_bars_deleted', 0)}"
                )
            else:
                logger.info(f"Data cleanup completed in {duration.total_seconds():.2f}s: No expired data found")
                
        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
            
    async def perform_manual_cleanup(self) -> Dict[str, Any]:
        """
        Perform manual cleanup (can be triggered via API)
        
        Returns:
            Dict with cleanup statistics
        """
        logger.info("Starting manual data retention cleanup...")
        
        if not self._storage:
            self._storage = await get_market_data_storage()
            
        try:
            start_time = datetime.now(timezone.utc)
            cleanup_stats = await self._storage.cleanup_expired_data()
            duration = datetime.now(timezone.utc) - start_time
            
            result = {
                "success": True,
                "duration_seconds": duration.total_seconds(),
                "cleanup_stats": cleanup_stats,
                "timestamp": start_time.isoformat()
            }
            
            logger.info(f"Manual cleanup completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Manual cleanup failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

# Global worker instance
_worker_instance: Optional[DataRetentionWorker] = None

async def get_data_retention_worker() -> DataRetentionWorker:
    """Get the global data retention worker instance"""
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = DataRetentionWorker()
    return _worker_instance

async def start_data_retention_worker():
    """Start the data retention worker"""
    worker = await get_data_retention_worker()
    await worker.start()

async def stop_data_retention_worker():
    """Stop the data retention worker"""
    global _worker_instance
    if _worker_instance:
        await _worker_instance.stop()
        _worker_instance = None

async def manual_data_cleanup() -> Dict[str, Any]:
    """Trigger manual data cleanup"""
    worker = await get_data_retention_worker()
    return await worker.perform_manual_cleanup() 