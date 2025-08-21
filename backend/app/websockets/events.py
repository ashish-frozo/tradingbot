"""
WebSocket Events
Trading-specific event handlers and integrations
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.logging import get_logger, log_performance_metric
from app.websockets.socket_manager import get_socket_manager, EventType, SubscriptionType

logger = get_logger(__name__)


class TradingEventEmitter:
    """Emit trading events to WebSocket clients"""
    
    def __init__(self):
        self.socket_manager = get_socket_manager()
    
    async def emit_market_data_update(
        self,
        symbol: str,
        price: float,
        volume: int,
        change: float,
        change_percent: float,
        timestamp: Optional[datetime] = None
    ):
        """Emit market data update"""
        data = {
            "symbol": symbol,
            "price": price,
            "volume": volume,
            "change": change,
            "change_percent": change_percent,
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }
        
        await self.socket_manager.broadcast_market_data(symbol, data)
        
        # Log performance metric for market data latency
        log_performance_metric(
            metric_name="market_data_broadcast",
            value=1,
            unit="count",
            symbol=symbol
        )
    
    async def emit_tick_data(
        self,
        symbol: str,
        ltp: float,
        bid_price: float,
        ask_price: float,
        bid_size: int,
        ask_size: int,
        volume: int,
        open_interest: Optional[int] = None
    ):
        """Emit real-time tick data"""
        data = {
            "symbol": symbol,
            "ltp": ltp,
            "bid_price": bid_price,
            "ask_price": ask_price,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "volume": volume,
            "open_interest": open_interest,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.socket_manager.broadcast(
            EventType.TICK_DATA,
            data,
            SubscriptionType.MARKET_DATA
        )
    
    async def emit_order_update(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        status: str,
        filled_quantity: int = 0,
        average_price: Optional[float] = None,
        timestamp: Optional[datetime] = None
    ):
        """Emit order status update"""
        data = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "status": status,
            "filled_quantity": filled_quantity,
            "average_price": average_price,
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }
        
        await self.socket_manager.broadcast_order_update(data)
        
        logger.info(f"Order update broadcasted: {order_id} - {status}")
    
    async def emit_trade_execution(
        self,
        trade_id: str,
        order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        commission: float,
        timestamp: Optional[datetime] = None
    ):
        """Emit trade execution event"""
        data = {
            "trade_id": trade_id,
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "commission": commission,
            "value": quantity * price,
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }
        
        await self.socket_manager.broadcast_trade_execution(data)
        
        logger.info(f"Trade execution broadcasted: {trade_id} - {symbol} {quantity}@{price}")
    
    async def emit_position_update(
        self,
        symbol: str,
        quantity: int,
        average_price: float,
        current_price: float,
        unrealized_pnl: float,
        realized_pnl: float,
        timestamp: Optional[datetime] = None
    ):
        """Emit position update"""
        data = {
            "symbol": symbol,
            "quantity": quantity,
            "average_price": average_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_pnl": unrealized_pnl + realized_pnl,
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }
        
        await self.socket_manager.broadcast_position_update(data)
    
    async def emit_strategy_signal(
        self,
        strategy_name: str,
        signal_type: str,
        symbol: str,
        action: str,
        confidence: float,
        price: float,
        quantity: int,
        reason: str,
        timestamp: Optional[datetime] = None
    ):
        """Emit strategy signal"""
        data = {
            "strategy_name": strategy_name,
            "signal_type": signal_type,
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "price": price,
            "quantity": quantity,
            "reason": reason,
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }
        
        await self.socket_manager.broadcast_strategy_signal(data)
        
        logger.info(f"Strategy signal broadcasted: {strategy_name} - {action} {symbol}")
    
    async def emit_risk_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        symbol: Optional[str] = None,
        current_value: Optional[float] = None,
        limit_value: Optional[float] = None,
        action_required: bool = False,
        timestamp: Optional[datetime] = None
    ):
        """Emit risk management alert"""
        data = {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "symbol": symbol,
            "current_value": current_value,
            "limit_value": limit_value,
            "action_required": action_required,
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }
        
        await self.socket_manager.broadcast_risk_alert(data)
        
        logger.warning(f"Risk alert broadcasted: {alert_type} - {severity}")
    
    async def emit_system_status(
        self,
        component: str,
        status: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """Emit system status update"""
        data = {
            "component": component,
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": (timestamp or datetime.utcnow()).isoformat()
        }
        
        await self.socket_manager.broadcast_system_status(data)


class TradingEventListener:
    """Listen to trading events and emit WebSocket updates"""
    
    def __init__(self):
        self.emitter = TradingEventEmitter()
        self.is_running = False
    
    async def start(self):
        """Start event listener"""
        self.is_running = True
        logger.info("Trading event listener started")
        
        # Start background tasks
        asyncio.create_task(self._system_health_broadcaster())
    
    async def stop(self):
        """Stop event listener"""
        self.is_running = False
        logger.info("Trading event listener stopped")
    
    async def _system_health_broadcaster(self):
        """Broadcast system health status periodically"""
        while self.is_running:
            try:
                # Get system health
                from app.api.health import get_system_health
                health_data = get_system_health()
                
                await self.emitter.emit_system_status(
                    component="system",
                    status=health_data["status"],
                    message="System health update",
                    details=health_data
                )
                
                # Wait 30 seconds before next broadcast
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in system health broadcaster: {e}")
                await asyncio.sleep(30)


# Global instances
_event_emitter: Optional[TradingEventEmitter] = None
_event_listener: Optional[TradingEventListener] = None


def get_event_emitter() -> TradingEventEmitter:
    """Get global event emitter instance"""
    global _event_emitter
    if _event_emitter is None:
        _event_emitter = TradingEventEmitter()
    return _event_emitter


def get_event_listener() -> TradingEventListener:
    """Get global event listener instance"""
    global _event_listener
    if _event_listener is None:
        _event_listener = TradingEventListener()
    return _event_listener


async def setup_socket_events():
    """Setup and start WebSocket event system"""
    logger.info("Setting up WebSocket events...")
    
    # Start event listener
    listener = get_event_listener()
    await listener.start()
    
    logger.info("WebSocket events setup completed")


async def cleanup_socket_events():
    """Cleanup WebSocket event system"""
    logger.info("Cleaning up WebSocket events...")
    
    # Stop event listener
    listener = get_event_listener()
    await listener.stop()
    
    logger.info("WebSocket events cleanup completed")


# Export main classes and functions
__all__ = [
    "TradingEventEmitter",
    "TradingEventListener",
    "get_event_emitter",
    "get_event_listener",
    "setup_socket_events",
    "cleanup_socket_events"
] 