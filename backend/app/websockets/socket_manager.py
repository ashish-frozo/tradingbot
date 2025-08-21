"""
Socket.IO Manager
Real-time WebSocket communication for trading updates
"""

import asyncio
import socketio
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class EventType(str, Enum):
    """WebSocket event types"""
    # Connection events
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    
    # Market data events
    MARKET_DATA = "market_data"
    TICK_DATA = "tick_data"
    ORDER_BOOK = "order_book"
    
    # Trading events
    ORDER_UPDATE = "order_update"
    TRADE_EXECUTION = "trade_execution"
    POSITION_UPDATE = "position_update"
    
    # Strategy events
    STRATEGY_SIGNAL = "strategy_signal"
    STRATEGY_STATUS = "strategy_status"
    
    # Risk events
    RISK_ALERT = "risk_alert"
    POSITION_LIMIT = "position_limit"
    LOSS_LIMIT = "loss_limit"
    
    # System events
    SYSTEM_STATUS = "system_status"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class SubscriptionType(str, Enum):
    """Subscription types for filtering events"""
    ALL = "all"
    MARKET_DATA = "market_data"
    TRADING = "trading"
    STRATEGY = "strategy"
    RISK = "risk"
    SYSTEM = "system"


class WebSocketMessage(BaseModel):
    """Standard WebSocket message format"""
    event: EventType
    data: Dict[str, Any]
    timestamp: datetime
    subscription: SubscriptionType
    session_id: Optional[str] = None


class SocketManager:
    """Manages Socket.IO connections and real-time updates"""
    
    def __init__(self):
        # Create Socket.IO server
        self.sio = socketio.AsyncServer(
            cors_allowed_origins=settings.CORS_ORIGINS,
            async_mode="asgi",
            logger=False,  # Use our custom logging
            engineio_logger=False
        )
        
        # Track connections and subscriptions
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.subscriptions: Dict[str, Set[SubscriptionType]] = {}
        
        # Event handlers
        self.event_handlers: Dict[EventType, List[callable]] = {}
        
        # Statistics
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0
        }
        
        # Setup event handlers
        self._setup_connection_handlers()
    
    def _setup_connection_handlers(self):
        """Setup basic connection event handlers"""
        
        @self.sio.event
        async def connect(sid, environ, auth):
            """Handle client connection"""
            try:
                # Extract client info
                client_ip = environ.get("REMOTE_ADDR", "unknown")
                user_agent = environ.get("HTTP_USER_AGENT", "unknown")
                
                # Store connection info
                self.connections[sid] = {
                    "connected_at": datetime.utcnow(),
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "auth": auth
                }
                
                # Default subscription to system events
                self.subscriptions[sid] = {SubscriptionType.SYSTEM}
                
                # Update stats
                self.stats["total_connections"] += 1
                self.stats["active_connections"] += 1
                
                logger.info(f"WebSocket client connected", extra={
                    "session_id": sid,
                    "client_ip": client_ip,
                    "total_connections": self.stats["active_connections"]
                })
                
                # Send welcome message
                await self.emit_to_client(
                    sid,
                    EventType.SYSTEM_STATUS,
                    {
                        "status": "connected",
                        "session_id": sid,
                        "server_time": datetime.utcnow().isoformat(),
                        "subscriptions": list(self.subscriptions[sid])
                    },
                    SubscriptionType.SYSTEM
                )
                
            except Exception as e:
                logger.error(f"Error handling WebSocket connection: {e}")
                self.stats["errors"] += 1
        
        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnection"""
            try:
                # Get connection info
                connection_info = self.connections.get(sid, {})
                
                # Clean up
                self.connections.pop(sid, None)
                self.subscriptions.pop(sid, None)
                
                # Update stats
                self.stats["active_connections"] -= 1
                
                logger.info(f"WebSocket client disconnected", extra={
                    "session_id": sid,
                    "client_ip": connection_info.get("client_ip", "unknown"),
                    "active_connections": self.stats["active_connections"]
                })
                
            except Exception as e:
                logger.error(f"Error handling WebSocket disconnection: {e}")
                self.stats["errors"] += 1
        
        @self.sio.event
        async def subscribe(sid, data):
            """Handle subscription requests"""
            try:
                subscription_types = data.get("subscriptions", [])
                
                # Validate subscription types
                valid_subscriptions = set()
                for sub_type in subscription_types:
                    try:
                        valid_subscriptions.add(SubscriptionType(sub_type))
                    except ValueError:
                        logger.warning(f"Invalid subscription type: {sub_type}")
                
                # Update subscriptions
                if valid_subscriptions:
                    self.subscriptions[sid] = valid_subscriptions
                    
                    logger.info(f"Client subscription updated", extra={
                        "session_id": sid,
                        "subscriptions": list(valid_subscriptions)
                    })
                    
                    # Confirm subscription
                    await self.emit_to_client(
                        sid,
                        EventType.SYSTEM_STATUS,
                        {
                            "status": "subscriptions_updated",
                            "subscriptions": list(valid_subscriptions)
                        },
                        SubscriptionType.SYSTEM
                    )
                
            except Exception as e:
                logger.error(f"Error handling subscription: {e}")
                await self.emit_error(sid, f"Subscription error: {str(e)}")
        
        @self.sio.event
        async def heartbeat(sid, data):
            """Handle heartbeat pings"""
            await self.emit_to_client(
                sid,
                EventType.HEARTBEAT,
                {"timestamp": datetime.utcnow().isoformat()},
                SubscriptionType.SYSTEM
            )
    
    async def emit_to_client(
        self,
        sid: str,
        event: EventType,
        data: Dict[str, Any],
        subscription: SubscriptionType
    ) -> bool:
        """Emit event to specific client"""
        try:
            # Check if client is subscribed to this event type
            client_subscriptions = self.subscriptions.get(sid, set())
            if subscription not in client_subscriptions and SubscriptionType.ALL not in client_subscriptions:
                return False
            
            # Create message
            message = WebSocketMessage(
                event=event,
                data=data,
                timestamp=datetime.utcnow(),
                subscription=subscription,
                session_id=sid
            )
            
            # Send message
            await self.sio.emit(event.value, message.dict(), room=sid)
            self.stats["messages_sent"] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error emitting to client {sid}: {e}")
            self.stats["errors"] += 1
            return False
    
    async def broadcast(
        self,
        event: EventType,
        data: Dict[str, Any],
        subscription: SubscriptionType,
        exclude_sids: Optional[List[str]] = None
    ) -> int:
        """Broadcast event to all subscribed clients"""
        sent_count = 0
        exclude_sids = exclude_sids or []
        
        for sid in list(self.connections.keys()):
            if sid not in exclude_sids:
                if await self.emit_to_client(sid, event, data, subscription):
                    sent_count += 1
        
        logger.debug(f"Broadcasted {event.value} to {sent_count} clients")
        return sent_count
    
    async def emit_error(self, sid: str, error_message: str):
        """Emit error message to client"""
        await self.emit_to_client(
            sid,
            EventType.ERROR,
            {
                "error": error_message,
                "timestamp": datetime.utcnow().isoformat()
            },
            SubscriptionType.SYSTEM
        )
    
    # Trading-specific event methods
    async def broadcast_market_data(self, symbol: str, data: Dict[str, Any]):
        """Broadcast market data update"""
        await self.broadcast(
            EventType.MARKET_DATA,
            {
                "symbol": symbol,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            },
            SubscriptionType.MARKET_DATA
        )
    
    async def broadcast_order_update(self, order_data: Dict[str, Any]):
        """Broadcast order status update"""
        await self.broadcast(
            EventType.ORDER_UPDATE,
            order_data,
            SubscriptionType.TRADING
        )
    
    async def broadcast_trade_execution(self, trade_data: Dict[str, Any]):
        """Broadcast trade execution"""
        await self.broadcast(
            EventType.TRADE_EXECUTION,
            trade_data,
            SubscriptionType.TRADING
        )
    
    async def broadcast_position_update(self, position_data: Dict[str, Any]):
        """Broadcast position update"""
        await self.broadcast(
            EventType.POSITION_UPDATE,
            position_data,
            SubscriptionType.TRADING
        )
    
    async def broadcast_strategy_signal(self, signal_data: Dict[str, Any]):
        """Broadcast strategy signal"""
        await self.broadcast(
            EventType.STRATEGY_SIGNAL,
            signal_data,
            SubscriptionType.STRATEGY
        )
    
    async def broadcast_risk_alert(self, alert_data: Dict[str, Any]):
        """Broadcast risk management alert"""
        await self.broadcast(
            EventType.RISK_ALERT,
            alert_data,
            SubscriptionType.RISK
        )
    
    async def broadcast_system_status(self, status_data: Dict[str, Any]):
        """Broadcast system status update"""
        await self.broadcast(
            EventType.SYSTEM_STATUS,
            status_data,
            SubscriptionType.SYSTEM
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection and usage statistics"""
        return {
            **self.stats,
            "active_connections": len(self.connections),
            "connection_details": [
                {
                    "session_id": sid,
                    "client_ip": info.get("client_ip"),
                    "connected_at": info.get("connected_at").isoformat() if info.get("connected_at") else None,
                    "subscriptions": list(self.subscriptions.get(sid, []))
                }
                for sid, info in self.connections.items()
            ]
        }
    
    def get_asgi_app(self):
        """Get ASGI app for integration with FastAPI"""
        return socketio.ASGIApp(self.sio, static_files={})


# Global socket manager instance
_socket_manager: Optional[SocketManager] = None


def get_socket_manager() -> SocketManager:
    """Get global socket manager instance"""
    global _socket_manager
    if _socket_manager is None:
        _socket_manager = SocketManager()
    return _socket_manager


# Export classes and functions
__all__ = [
    "EventType",
    "SubscriptionType", 
    "WebSocketMessage",
    "SocketManager",
    "get_socket_manager"
] 