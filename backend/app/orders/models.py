"""
Order Models Module

Comprehensive order models for the trading system including:
- Order state management
- Execution tracking
- Slippage monitoring
- Fill details
- Latency auditing
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP

from app.broker.enums import TransactionType, ProductType


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    MODIFIED = "modified"


class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LOSS_MARKET = "stop_loss_market"
    BRACKET = "bracket"
    COVER = "cover"


class SlippageStatus(Enum):
    """Slippage validation status"""
    ACCEPTABLE = "acceptable"
    HIGH_WARNING = "high_warning"
    REJECTED = "rejected"
    SPREAD_TOO_WIDE = "spread_too_wide"


class RejectReason(Enum):
    """Order rejection reasons"""
    SLIPPAGE_EXCEEDED = "slippage_exceeded"
    SPREAD_TOO_WIDE = "spread_too_wide"
    RISK_LIMITS = "risk_limits"
    CIRCUIT_BREAKER = "circuit_breaker"
    INSUFFICIENT_MARGIN = "insufficient_margin"
    INVALID_PRICE = "invalid_price"
    EXCHANGE_ERROR = "exchange_error"
    SYSTEM_ERROR = "system_error"


@dataclass
class PriceData:
    """Market price data for slippage calculation"""
    bid: float
    ask: float
    ltp: float  # Last traded price
    spread_points: float
    spread_percentage: float
    timestamp: datetime
    
    def __post_init__(self):
        """Calculate spread metrics"""
        if self.bid > 0 and self.ask > 0:
            self.spread_points = self.ask - self.bid
            mid_price = (self.bid + self.ask) / 2
            self.spread_percentage = (self.spread_points / mid_price) * 100 if mid_price > 0 else 0
        else:
            self.spread_points = 0
            self.spread_percentage = 0


@dataclass
class SlippageMetrics:
    """Slippage calculation metrics"""
    expected_price: float
    actual_price: float
    slippage_points: float
    slippage_percentage: float
    slippage_amount: float  # In INR
    lot_size: int
    lots: int
    status: SlippageStatus
    warning_threshold: float = 0.20  # ₹0.20 warning
    rejection_threshold: float = 0.30  # ₹0.30 rejection per PRD
    
    def __post_init__(self):
        """Calculate slippage metrics"""
        self.slippage_points = abs(self.actual_price - self.expected_price)
        self.slippage_percentage = (self.slippage_points / self.expected_price) * 100 if self.expected_price > 0 else 0
        self.slippage_amount = self.slippage_points * self.lot_size * self.lots
        
        # Determine status
        if self.slippage_points >= self.rejection_threshold:
            self.status = SlippageStatus.REJECTED
        elif self.slippage_points >= self.warning_threshold:
            self.status = SlippageStatus.HIGH_WARNING
        else:
            self.status = SlippageStatus.ACCEPTABLE


@dataclass
class Fill:
    """Individual fill details"""
    fill_id: str
    timestamp: datetime
    quantity: int
    price: float
    value: float
    exchange_timestamp: Optional[datetime] = None
    trade_id: Optional[str] = None
    
    def __post_init__(self):
        """Calculate fill value"""
        self.value = self.quantity * self.price


@dataclass
class LatencyMetrics:
    """Order latency tracking"""
    order_created: datetime
    order_submitted: datetime
    order_acknowledged: Optional[datetime] = None
    first_fill: Optional[datetime] = None
    order_completed: Optional[datetime] = None
    
    # Calculated metrics
    submission_latency_ms: Optional[float] = None
    acknowledgment_latency_ms: Optional[float] = None
    fill_latency_ms: Optional[float] = None
    total_latency_ms: Optional[float] = None
    
    def calculate_latencies(self):
        """Calculate all latency metrics"""
        # Submission latency
        self.submission_latency_ms = (
            (self.order_submitted - self.order_created).total_seconds() * 1000
        )
        
        # Acknowledgment latency
        if self.order_acknowledged:
            self.acknowledgment_latency_ms = (
                (self.order_acknowledged - self.order_submitted).total_seconds() * 1000
            )
        
        # Fill latency (from submission to first fill)
        if self.first_fill:
            self.fill_latency_ms = (
                (self.first_fill - self.order_submitted).total_seconds() * 1000
            )
        
        # Total latency (from creation to completion)
        if self.order_completed:
            self.total_latency_ms = (
                (self.order_completed - self.order_created).total_seconds() * 1000
            )


@dataclass
class OrderRequest:
    """Order request data"""
    symbol: str
    strike: float
    option_type: str  # "CE" or "PE"
    expiry: str
    transaction_type: TransactionType
    order_type: OrderType
    product_type: ProductType
    quantity: int
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    disclosed_quantity: int = 0
    validity: str = "DAY"
    amo: bool = False
    strategy_name: str = "default"
    signal_id: Optional[str] = None
    parent_order_id: Optional[str] = None
    tag: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Order:
    """Complete order representation"""
    # Core order details
    order_id: str
    external_order_id: Optional[str] = None
    request: Optional[OrderRequest] = None
    
    # Status and state
    status: OrderStatus = OrderStatus.PENDING
    status_message: str = ""
    
    # Pricing and execution
    submitted_price: Optional[float] = None
    average_price: Optional[float] = None
    filled_quantity: int = 0
    remaining_quantity: int = 0
    
    # Fills and execution details
    fills: List[Fill] = field(default_factory=list)
    
    # Risk and slippage tracking
    slippage_metrics: Optional[SlippageMetrics] = None
    market_data_at_submission: Optional[PriceData] = None
    rejection_reason: Optional[RejectReason] = None
    
    # Timing and latency
    latency_metrics: Optional[LatencyMetrics] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Retry and modification tracking
    retry_count: int = 0
    modification_count: int = 0
    original_order_id: Optional[str] = None
    
    # Additional metadata
    broker_response: Dict[str, Any] = field(default_factory=dict)
    error_details: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize calculated fields"""
        if self.request:
            self.remaining_quantity = self.request.quantity - self.filled_quantity
    
    def add_fill(self, fill: Fill):
        """Add a fill to the order"""
        self.fills.append(fill)
        self.filled_quantity += fill.quantity
        self.remaining_quantity = self.request.quantity - self.filled_quantity if self.request else 0
        
        # Update average price
        total_value = sum(f.value for f in self.fills)
        if self.filled_quantity > 0:
            self.average_price = total_value / self.filled_quantity
        
        # Update status
        if self.remaining_quantity == 0:
            self.status = OrderStatus.FILLED
            self.completed_at = datetime.now(timezone.utc)
        elif self.filled_quantity > 0:
            self.status = OrderStatus.PARTIALLY_FILLED
        
        # Update latency metrics
        if not self.latency_metrics:
            self.latency_metrics = LatencyMetrics(
                order_created=self.created_at,
                order_submitted=self.submitted_at or self.created_at
            )
        
        if not self.latency_metrics.first_fill:
            self.latency_metrics.first_fill = fill.timestamp
        
        if self.status == OrderStatus.FILLED:
            self.latency_metrics.order_completed = self.completed_at
        
        self.latency_metrics.calculate_latencies()
        self.last_updated = datetime.now(timezone.utc)
    
    def calculate_slippage(self, expected_price: float, lot_size: int):
        """Calculate slippage metrics for the order"""
        if self.average_price is not None:
            lots = self.request.quantity // lot_size if self.request else 1
            self.slippage_metrics = SlippageMetrics(
                expected_price=expected_price,
                actual_price=self.average_price,
                slippage_points=0,  # Will be calculated in __post_init__
                slippage_percentage=0,  # Will be calculated in __post_init__
                slippage_amount=0,  # Will be calculated in __post_init__
                lot_size=lot_size,
                lots=lots,
                status=SlippageStatus.ACCEPTABLE  # Will be calculated in __post_init__
            )
    
    def update_status(self, new_status: OrderStatus, message: str = ""):
        """Update order status with timestamp"""
        self.status = new_status
        self.status_message = message
        self.last_updated = datetime.now(timezone.utc)
        
        # Update specific timestamps
        if new_status == OrderStatus.ACKNOWLEDGED:
            self.acknowledged_at = self.last_updated
        elif new_status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            self.completed_at = self.last_updated
    
    def is_active(self) -> bool:
        """Check if order is still active (can be filled or modified)"""
        return self.status in [
            OrderStatus.SUBMITTED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED
        ]
    
    def is_terminal(self) -> bool:
        """Check if order is in terminal state"""
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        ]
    
    def get_fill_percentage(self) -> float:
        """Get percentage of order filled"""
        if not self.request or self.request.quantity == 0:
            return 0.0
        return (self.filled_quantity / self.request.quantity) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary for serialization"""
        return {
            "order_id": self.order_id,
            "external_order_id": self.external_order_id,
            "status": self.status.value,
            "status_message": self.status_message,
            "symbol": self.request.symbol if self.request else None,
            "transaction_type": self.request.transaction_type.value if self.request else None,
            "quantity": self.request.quantity if self.request else 0,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "submitted_price": self.submitted_price,
            "average_price": self.average_price,
            "fills_count": len(self.fills),
            "slippage_points": self.slippage_metrics.slippage_points if self.slippage_metrics else None,
            "slippage_amount": self.slippage_metrics.slippage_amount if self.slippage_metrics else None,
            "total_latency_ms": self.latency_metrics.total_latency_ms if self.latency_metrics else None,
            "created_at": self.created_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
            "modification_count": self.modification_count
        }


@dataclass
class OrderBook:
    """Order book representation"""
    symbol: str
    timestamp: datetime
    bids: List[Tuple[float, int]] = field(default_factory=list)  # (price, quantity)
    asks: List[Tuple[float, int]] = field(default_factory=list)  # (price, quantity)
    
    def get_best_bid(self) -> Optional[float]:
        """Get best bid price"""
        return self.bids[0][0] if self.bids else None
    
    def get_best_ask(self) -> Optional[float]:
        """Get best ask price"""
        return self.asks[0][0] if self.asks else None
    
    def get_spread(self) -> Optional[float]:
        """Get bid-ask spread"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        return best_ask - best_bid if best_bid and best_ask else None
    
    def get_mid_price(self) -> Optional[float]:
        """Get mid price"""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        return (best_bid + best_ask) / 2 if best_bid and best_ask else None


@dataclass
class ExecutionReport:
    """Execution report from broker"""
    order_id: str
    external_order_id: str
    status: OrderStatus
    filled_quantity: int
    average_price: Optional[float]
    timestamp: datetime
    exchange_timestamp: Optional[datetime] = None
    message: str = ""
    fill_details: Optional[Fill] = None
    broker_data: Dict[str, Any] = field(default_factory=dict) 