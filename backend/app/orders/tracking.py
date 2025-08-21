"""
Order status tracking and fill notifications system.

This module provides comprehensive order lifecycle tracking, real-time
status updates, fill notifications, and execution analytics.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set
from uuid import uuid4

from loguru import logger
from app.broker.tradehull_client import TradehullClient
from app.orders.models import OrderStatus, OrderRequest, OrderResponse
from app.cache.redis import RedisManager
from app.websockets.events import WebSocketEventManager


class FillType(Enum):
    """Types of order fills."""
    COMPLETE = "complete"
    PARTIAL = "partial"
    NONE = "none"


class NotificationType(Enum):
    """Types of notifications."""
    ORDER_SUBMITTED = "order_submitted"
    ORDER_CONFIRMED = "order_confirmed"
    ORDER_PARTIAL_FILL = "order_partial_fill"
    ORDER_COMPLETE_FILL = "order_complete_fill"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    ORDER_EXPIRED = "order_expired"


@dataclass
class FillInfo:
    """Information about an order fill."""
    fill_id: str
    order_id: str
    broker_order_id: str
    symbol: str
    filled_quantity: int
    fill_price: float
    fill_time: datetime
    remaining_quantity: int
    cumulative_quantity: int
    average_fill_price: float
    fill_type: FillType
    exchange_timestamp: Optional[datetime] = None
    commission: float = 0.0
    taxes: float = 0.0
    

@dataclass
class OrderTracker:
    """Tracks a single order through its lifecycle."""
    order_id: str
    broker_order_id: Optional[str]
    strategy_id: str
    symbol: str
    original_request: OrderRequest
    current_status: OrderStatus
    fills: List[FillInfo] = field(default_factory=list)
    total_filled_quantity: int = 0
    remaining_quantity: int = 0
    average_fill_price: float = 0.0
    total_commission: float = 0.0
    total_taxes: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    completion_time: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    

@dataclass
class NotificationEvent:
    """Notification event for order updates."""
    event_id: str
    notification_type: NotificationType
    order_id: str
    strategy_id: str
    symbol: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    

class OrderTrackingManager:
    """
    Comprehensive order tracking and notification system.
    
    Features:
    - Real-time order status tracking
    - Fill notifications with detailed execution info
    - Order lifecycle management
    - WebSocket notifications for real-time updates
    - Fill analytics and execution quality metrics
    - Automated status polling and updates
    """
    
    def __init__(
        self,
        broker_client: TradehullClient,
        redis_manager: RedisManager,
        websocket_manager: Optional[WebSocketEventManager] = None,
        status_poll_interval_seconds: int = 1,
        enable_notifications: bool = True
    ):
        self.broker_client = broker_client
        self.redis = redis_manager
        self.websocket_manager = websocket_manager
        self.status_poll_interval_seconds = status_poll_interval_seconds
        self.enable_notifications = enable_notifications
        
        # Order tracking
        self.active_orders: Dict[str, OrderTracker] = {}
        self.completed_orders: Dict[str, OrderTracker] = {}
        
        # Notification system
        self.notification_callbacks: List[Callable[[NotificationEvent], None]] = []
        self.pending_notifications: List[NotificationEvent] = []
        
        # Status polling
        self.is_polling = False
        self.poll_task: Optional[asyncio.Task] = None
        
        # Metrics
        self.tracking_stats = {
            "total_orders_tracked": 0,
            "active_orders": 0,
            "completed_orders": 0,
            "total_fills": 0,
            "notifications_sent": 0,
            "average_fill_time_ms": 0.0
        }
        
        logger.info(
            "Order tracking manager initialized (poll_interval: {}s, notifications: {})",
            status_poll_interval_seconds,
            enable_notifications
        )
    
    async def start(self) -> None:
        """Start the order tracking system."""
        if self.is_polling:
            return
        
        self.is_polling = True
        
        # Load existing orders from Redis
        await self._load_orders_from_redis()
        
        # Start status polling task
        self.poll_task = asyncio.create_task(
            self._status_polling_loop(),
            name="order_status_polling"
        )
        
        logger.info("Order tracking system started")
    
    async def stop(self) -> None:
        """Stop the order tracking system."""
        self.is_polling = False
        
        if self.poll_task:
            self.poll_task.cancel()
            try:
                await self.poll_task
            except asyncio.CancelledError:
                pass
        
        # Save current state to Redis
        await self._save_orders_to_redis()
        
        logger.info("Order tracking system stopped")
    
    async def track_order(
        self,
        order_id: str,
        broker_order_id: Optional[str],
        strategy_id: str,
        original_request: OrderRequest
    ) -> None:
        """
        Start tracking an order.
        
        Args:
            order_id: Internal order ID
            broker_order_id: Broker's order ID
            strategy_id: Strategy that placed the order
            original_request: Original order request
        """
        tracker = OrderTracker(
            order_id=order_id,
            broker_order_id=broker_order_id,
            strategy_id=strategy_id,
            symbol=original_request.symbol,
            original_request=original_request,
            current_status=OrderStatus.SUBMITTED,
            remaining_quantity=original_request.quantity
        )
        
        self.active_orders[order_id] = tracker
        self.tracking_stats["total_orders_tracked"] += 1
        self.tracking_stats["active_orders"] += 1
        
        logger.info(
            "Started tracking order: {} (broker: {}, symbol: {}, qty: {})",
            order_id,
            broker_order_id,
            original_request.symbol,
            original_request.quantity,
            extra={
                "order_id": order_id,
                "broker_order_id": broker_order_id,
                "strategy_id": strategy_id,
                "symbol": original_request.symbol,
                "quantity": original_request.quantity
            }
        )
        
        # Send notification
        await self._send_notification(
            NotificationType.ORDER_SUBMITTED,
            tracker,
            {
                "order_request": {
                    "symbol": original_request.symbol,
                    "quantity": original_request.quantity,
                    "price": original_request.price,
                    "order_type": original_request.order_type.value,
                    "transaction_type": original_request.transaction_type.value
                }
            }
        )
        
        # Save to Redis
        await self._save_order_to_redis(tracker)
    
    async def update_order_status(
        self,
        order_id: str,
        new_status: OrderStatus,
        fill_info: Optional[FillInfo] = None,
        rejection_reason: Optional[str] = None
    ) -> None:
        """
        Update order status and process any fills.
        
        Args:
            order_id: Order ID to update
            new_status: New order status
            fill_info: Fill information if applicable
            rejection_reason: Rejection reason if order was rejected
        """
        tracker = self.active_orders.get(order_id)
        if not tracker:
            logger.warning("Cannot update status for unknown order: {}", order_id)
            return
        
        old_status = tracker.current_status
        tracker.current_status = new_status
        tracker.last_updated = datetime.utcnow()
        
        if rejection_reason:
            tracker.rejection_reason = rejection_reason
        
        # Process fill if provided
        if fill_info:
            await self._process_fill(tracker, fill_info)
        
        # Handle status transitions
        if new_status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]:
            await self._complete_order(tracker)
        
        logger.info(
            "Order status updated: {} {} -> {} {}",
            order_id,
            old_status.value,
            new_status.value,
            f"(fill: {fill_info.filled_quantity} @ ₹{fill_info.fill_price})" if fill_info else "",
            extra={
                "order_id": order_id,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "fill_quantity": fill_info.filled_quantity if fill_info else 0,
                "fill_price": fill_info.fill_price if fill_info else 0
            }
        )
        
        # Send appropriate notification
        notification_type = self._get_notification_type(new_status, fill_info)
        if notification_type:
            notification_data = {
                "old_status": old_status.value,
                "new_status": new_status.value
            }
            
            if fill_info:
                notification_data["fill_info"] = {
                    "filled_quantity": fill_info.filled_quantity,
                    "fill_price": fill_info.fill_price,
                    "remaining_quantity": fill_info.remaining_quantity,
                    "cumulative_quantity": fill_info.cumulative_quantity,
                    "average_fill_price": fill_info.average_fill_price,
                    "fill_type": fill_info.fill_type.value
                }
            
            if rejection_reason:
                notification_data["rejection_reason"] = rejection_reason
            
            await self._send_notification(notification_type, tracker, notification_data)
        
        # Save updated tracker
        await self._save_order_to_redis(tracker)
    
    async def _process_fill(self, tracker: OrderTracker, fill_info: FillInfo) -> None:
        """Process an order fill and update tracker state."""
        # Add fill to tracker
        tracker.fills.append(fill_info)
        tracker.total_filled_quantity += fill_info.filled_quantity
        tracker.remaining_quantity = max(0, tracker.original_request.quantity - tracker.total_filled_quantity)
        tracker.total_commission += fill_info.commission
        tracker.total_taxes += fill_info.taxes
        
        # Calculate average fill price
        if tracker.total_filled_quantity > 0:
            total_value = sum(fill.filled_quantity * fill.fill_price for fill in tracker.fills)
            tracker.average_fill_price = total_value / tracker.total_filled_quantity
        
        # Update global stats
        self.tracking_stats["total_fills"] += 1
        
        logger.info(
            "Fill processed: {} filled {} @ ₹{:.2f} (total: {}/{}, avg: ₹{:.2f})",
            tracker.order_id,
            fill_info.filled_quantity,
            fill_info.fill_price,
            tracker.total_filled_quantity,
            tracker.original_request.quantity,
            tracker.average_fill_price,
            extra={
                "order_id": tracker.order_id,
                "fill_quantity": fill_info.filled_quantity,
                "fill_price": fill_info.fill_price,
                "total_filled": tracker.total_filled_quantity,
                "remaining": tracker.remaining_quantity,
                "average_price": tracker.average_fill_price
            }
        )
    
    async def _complete_order(self, tracker: OrderTracker) -> None:
        """Move order from active to completed tracking."""
        tracker.completion_time = datetime.utcnow()
        
        # Move to completed orders
        self.completed_orders[tracker.order_id] = tracker
        self.active_orders.pop(tracker.order_id, None)
        
        # Update stats
        self.tracking_stats["active_orders"] -= 1
        self.tracking_stats["completed_orders"] += 1
        
        logger.info(
            "Order completed: {} - {} (filled: {}/{}, avg_price: ₹{:.2f})",
            tracker.order_id,
            tracker.current_status.value,
            tracker.total_filled_quantity,
            tracker.original_request.quantity,
            tracker.average_fill_price,
            extra={
                "order_id": tracker.order_id,
                "final_status": tracker.current_status.value,
                "fill_rate": tracker.total_filled_quantity / tracker.original_request.quantity if tracker.original_request.quantity > 0 else 0,
                "total_commission": tracker.total_commission,
                "total_taxes": tracker.total_taxes
            }
        )
    
    def _get_notification_type(
        self,
        status: OrderStatus,
        fill_info: Optional[FillInfo]
    ) -> Optional[NotificationType]:
        """Determine notification type based on status and fill info."""
        if status == OrderStatus.CONFIRMED:
            return NotificationType.ORDER_CONFIRMED
        elif status == OrderStatus.PARTIALLY_FILLED:
            return NotificationType.ORDER_PARTIAL_FILL
        elif status == OrderStatus.FILLED:
            return NotificationType.ORDER_COMPLETE_FILL
        elif status == OrderStatus.CANCELLED:
            return NotificationType.ORDER_CANCELLED
        elif status == OrderStatus.REJECTED:
            return NotificationType.ORDER_REJECTED
        elif status == OrderStatus.EXPIRED:
            return NotificationType.ORDER_EXPIRED
        
        return None
    
    async def _send_notification(
        self,
        notification_type: NotificationType,
        tracker: OrderTracker,
        data: Dict[str, Any]
    ) -> None:
        """Send notification for order update."""
        if not self.enable_notifications:
            return
        
        event = NotificationEvent(
            event_id=str(uuid4()),
            notification_type=notification_type,
            order_id=tracker.order_id,
            strategy_id=tracker.strategy_id,
            symbol=tracker.symbol,
            data={
                **data,
                "order_summary": {
                    "order_id": tracker.order_id,
                    "broker_order_id": tracker.broker_order_id,
                    "symbol": tracker.symbol,
                    "strategy_id": tracker.strategy_id,
                    "current_status": tracker.current_status.value,
                    "total_filled": tracker.total_filled_quantity,
                    "remaining": tracker.remaining_quantity,
                    "average_fill_price": tracker.average_fill_price
                }
            }
        )
        
        # Add to pending notifications
        self.pending_notifications.append(event)
        
        # Send via callbacks
        for callback in self.notification_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error("Notification callback error: {}", str(e))
        
        # Send via WebSocket if available
        if self.websocket_manager:
            try:
                await self.websocket_manager.broadcast_event(
                    "order_update",
                    {
                        "notification_type": notification_type.value,
                        "order_id": tracker.order_id,
                        "strategy_id": tracker.strategy_id,
                        "symbol": tracker.symbol,
                        "data": event.data
                    }
                )
            except Exception as e:
                logger.error("WebSocket notification error: {}", str(e))
        
        self.tracking_stats["notifications_sent"] += 1
        
        logger.debug(
            "Notification sent: {} for order {}",
            notification_type.value,
            tracker.order_id
        )
    
    async def _status_polling_loop(self) -> None:
        """Main loop for polling order status from broker."""
        logger.info("Order status polling started")
        
        while self.is_polling:
            try:
                if not self.active_orders:
                    await asyncio.sleep(self.status_poll_interval_seconds)
                    continue
                
                # Poll status for all active orders
                poll_tasks = []
                for order_id in list(self.active_orders.keys()):
                    task = asyncio.create_task(
                        self._poll_single_order_status(order_id),
                        name=f"poll_order_{order_id}"
                    )
                    poll_tasks.append(task)
                
                if poll_tasks:
                    # Wait for all polls to complete
                    await asyncio.gather(*poll_tasks, return_exceptions=True)
                
                await asyncio.sleep(self.status_poll_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in status polling loop: {}", str(e))
                await asyncio.sleep(self.status_poll_interval_seconds)
        
        logger.info("Order status polling stopped")
    
    async def _poll_single_order_status(self, order_id: str) -> None:
        """Poll status for a single order."""
        tracker = self.active_orders.get(order_id)
        if not tracker or not tracker.broker_order_id:
            return
        
        try:
            # Get order status from broker
            status_response = await self.broker_client.get_order_status(tracker.broker_order_id)
            
            # Parse broker response (this would depend on actual broker API)
            # For now, simulate response processing
            broker_status = status_response.get("status", "UNKNOWN")
            filled_qty = status_response.get("filled_quantity", 0)
            avg_price = status_response.get("average_price", 0.0)
            
            # Map broker status to internal status
            internal_status = self._map_broker_status(broker_status)
            
            # Check if status changed
            if internal_status != tracker.current_status:
                fill_info = None
                if filled_qty > tracker.total_filled_quantity:
                    # New fill detected
                    new_fill_qty = filled_qty - tracker.total_filled_quantity
                    fill_info = FillInfo(
                        fill_id=str(uuid4()),
                        order_id=order_id,
                        broker_order_id=tracker.broker_order_id,
                        symbol=tracker.symbol,
                        filled_quantity=new_fill_qty,
                        fill_price=avg_price,  # Simplified - would need actual fill price
                        fill_time=datetime.utcnow(),
                        remaining_quantity=tracker.original_request.quantity - filled_qty,
                        cumulative_quantity=filled_qty,
                        average_fill_price=avg_price,
                        fill_type=FillType.COMPLETE if filled_qty == tracker.original_request.quantity else FillType.PARTIAL
                    )
                
                await self.update_order_status(order_id, internal_status, fill_info)
                
        except Exception as e:
            logger.error("Error polling status for order {}: {}", order_id, str(e))
    
    def _map_broker_status(self, broker_status: str) -> OrderStatus:
        """Map broker status to internal order status."""
        # This mapping would depend on the actual broker API
        status_mapping = {
            "PENDING": OrderStatus.SUBMITTED,
            "CONFIRMED": OrderStatus.CONFIRMED,
            "PARTIAL": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED
        }
        
        return status_mapping.get(broker_status, OrderStatus.UNKNOWN)
    
    async def _load_orders_from_redis(self) -> None:
        """Load existing orders from Redis."""
        try:
            # TODO: Implement Redis loading
            pass
        except Exception as e:
            logger.warning("Failed to load orders from Redis: {}", str(e))
    
    async def _save_orders_to_redis(self) -> None:
        """Save all orders to Redis."""
        try:
            # Save active orders
            active_data = {
                order_id: {
                    "order_id": tracker.order_id,
                    "broker_order_id": tracker.broker_order_id,
                    "strategy_id": tracker.strategy_id,
                    "symbol": tracker.symbol,
                    "current_status": tracker.current_status.value,
                    "total_filled_quantity": tracker.total_filled_quantity,
                    "remaining_quantity": tracker.remaining_quantity,
                    "average_fill_price": tracker.average_fill_price,
                    "created_at": tracker.created_at.isoformat(),
                    "last_updated": tracker.last_updated.isoformat()
                }
                for order_id, tracker in self.active_orders.items()
            }
            
            await self.redis.set("active_orders", active_data, ttl=timedelta(hours=24))
            
        except Exception as e:
            logger.error("Failed to save orders to Redis: {}", str(e))
    
    async def _save_order_to_redis(self, tracker: OrderTracker) -> None:
        """Save a single order to Redis."""
        try:
            order_data = {
                "order_id": tracker.order_id,
                "broker_order_id": tracker.broker_order_id,
                "strategy_id": tracker.strategy_id,
                "symbol": tracker.symbol,
                "current_status": tracker.current_status.value,
                "total_filled_quantity": tracker.total_filled_quantity,
                "remaining_quantity": tracker.remaining_quantity,
                "average_fill_price": tracker.average_fill_price,
                "fills": [
                    {
                        "fill_id": fill.fill_id,
                        "filled_quantity": fill.filled_quantity,
                        "fill_price": fill.fill_price,
                        "fill_time": fill.fill_time.isoformat(),
                        "fill_type": fill.fill_type.value
                    }
                    for fill in tracker.fills
                ],
                "last_updated": tracker.last_updated.isoformat()
            }
            
            key = f"order_tracker:{tracker.order_id}"
            await self.redis.set(key, order_data, ttl=timedelta(days=7))
            
        except Exception as e:
            logger.error("Failed to save order tracker to Redis: {}", str(e))
    
    def add_notification_callback(self, callback: Callable[[NotificationEvent], None]) -> None:
        """Add a callback for order notifications."""
        self.notification_callbacks.append(callback)
    
    def get_order_details(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an order."""
        tracker = self.active_orders.get(order_id) or self.completed_orders.get(order_id)
        if not tracker:
            return None
        
        return {
            "order_id": tracker.order_id,
            "broker_order_id": tracker.broker_order_id,
            "strategy_id": tracker.strategy_id,
            "symbol": tracker.symbol,
            "current_status": tracker.current_status.value,
            "original_quantity": tracker.original_request.quantity,
            "total_filled_quantity": tracker.total_filled_quantity,
            "remaining_quantity": tracker.remaining_quantity,
            "average_fill_price": tracker.average_fill_price,
            "total_commission": tracker.total_commission,
            "total_taxes": tracker.total_taxes,
            "created_at": tracker.created_at.isoformat(),
            "last_updated": tracker.last_updated.isoformat(),
            "completion_time": tracker.completion_time.isoformat() if tracker.completion_time else None,
            "fills": [
                {
                    "fill_id": fill.fill_id,
                    "filled_quantity": fill.filled_quantity,
                    "fill_price": fill.fill_price,
                    "fill_time": fill.fill_time.isoformat(),
                    "fill_type": fill.fill_type.value,
                    "commission": fill.commission,
                    "taxes": fill.taxes
                }
                for fill in tracker.fills
            ],
            "rejection_reason": tracker.rejection_reason
        }
    
    def get_tracking_stats(self) -> Dict[str, Any]:
        """Get current tracking statistics."""
        return {
            **self.tracking_stats,
            "pending_notifications": len(self.pending_notifications),
            "poll_interval_seconds": self.status_poll_interval_seconds,
            "is_polling": self.is_polling
        } 