"""
Order Management Module

This module provides comprehensive order management functionality including:
- Order lifecycle management
- Slippage filtering (reject if >₹0.30/leg or spread >0.3%)
- Risk integration
- Fill tracking and latency monitoring
- Circuit breaker integration
- Order execution with latency auditing (<150ms target)
- Re-quote system (max 3 retries, ≤₹0.10 price chase)
- Emergency kill switch with 2-second flatten target
- Order status tracking and fill notifications
"""

from .models import (
    OrderStatus,
    OrderType,
    SlippageStatus,
    RejectReason,
    PriceData,
    SlippageMetrics,
    Fill,
    LatencyMetrics,
    OrderRequest,
    Order,
    OrderBook,
    ExecutionReport
)

from .manager import (
    OrderManager,
    SlippageConfig,
    OrderValidationResult,
    order_manager
)

from .executor import (
    OrderExecutor,
    ExecutionPriority,
    LatencyBreakdown,
    ExecutionContext
)

from .requote import (
    OrderRequoter,
    RequoteStrategy,
    RequoteReason,
    RequoteConfig,
    RequoteAttempt,
    RequoteContext
)

from .kill_switch import (
    EmergencyKillSwitch,
    KillSwitchTrigger,
    KillSwitchStatus,
    PositionSnapshot,
    FlattenOrder,
    KillSwitchExecution
)

from .tracking import (
    OrderTrackingManager,
    FillType,
    NotificationType,
    FillInfo,
    OrderTracker,
    NotificationEvent
)

__all__ = [
    # Models
    "OrderStatus",
    "OrderType",
    "SlippageStatus",
    "RejectReason",
    "PriceData",
    "SlippageMetrics",
    "Fill",
    "LatencyMetrics",
    "OrderRequest",
    "Order",
    "OrderBook",
    "ExecutionReport",
    
    # Manager
    "OrderManager",
    "SlippageConfig",
    "OrderValidationResult",
    "order_manager",
    
    # Executor (Task 4.5)
    "OrderExecutor",
    "ExecutionPriority",
    "LatencyBreakdown",
    "ExecutionContext",
    
    # Re-quote (Task 4.6)
    "OrderRequoter",
    "RequoteStrategy",
    "RequoteReason",
    "RequoteConfig",
    "RequoteAttempt",
    "RequoteContext",
    
    # Kill Switch (Task 4.9)
    "EmergencyKillSwitch",
    "KillSwitchTrigger",
    "KillSwitchStatus",
    "PositionSnapshot",
    "FlattenOrder",
    "KillSwitchExecution",
    
    # Tracking (Task 4.10)
    "OrderTrackingManager",
    "FillType",
    "NotificationType",
    "FillInfo",
    "OrderTracker",
    "NotificationEvent"
] 