"""
Trade Model
Tracks individual trades with fills, P&L, and audit information
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum
from sqlmodel import SQLModel, Field, Column, String, DateTime, Numeric
from sqlalchemy import Index


class TradeStatus(str, Enum):
    """Trade status enumeration"""
    PENDING = "pending"
    FILLED = "filled" 
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TradeType(str, Enum):
    """Trade type enumeration"""
    BUY = "buy"
    SELL = "sell"


class Trade(SQLModel, table=True):
    """
    Trade model with comprehensive tracking
    Stores individual trade executions with audit information
    """
    
    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Order identification
    order_id: str = Field(max_length=100, index=True)
    broker_order_id: Optional[str] = Field(default=None, max_length=100, index=True)
    
    # Trade details
    symbol: str = Field(max_length=100, index=True)
    exchange: str = Field(max_length=20)
    trade_type: TradeType = Field()
    status: TradeStatus = Field(default=TradeStatus.PENDING)
    
    # Quantities and pricing
    quantity: int = Field()
    filled_quantity: int = Field(default=0)
    price: Decimal = Field(sa_column=Column(Numeric(10, 2)))
    average_fill_price: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    
    # P&L tracking
    realized_pnl: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    unrealized_pnl: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    commission: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 2)), default=None
    )
    brokerage: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 2)), default=None
    )
    
    # Strategy tracking
    strategy_name: str = Field(max_length=100, index=True)
    signal_id: Optional[str] = Field(default=None, max_length=100)
    
    # Latency and performance tracking
    order_timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True))
    )
    ack_timestamp: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    fill_timestamp: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    latency_ms: Optional[int] = Field(default=None)
    
    # Slippage tracking
    expected_price: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    slippage: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 4)), default=None
    )
    
    # Risk and margin
    margin_required: Optional[Decimal] = Field(
        sa_column=Column(Numeric(12, 2)), default=None
    )
    margin_used: Optional[Decimal] = Field(
        sa_column=Column(Numeric(12, 2)), default=None
    )
    
    # Market context
    underlying_price: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    implied_volatility: Optional[Decimal] = Field(
        sa_column=Column(Numeric(6, 4)), default=None
    )
    
    # Audit and compliance
    decision_hash: Optional[str] = Field(default=None, max_length=64)
    feature_snapshot: Optional[str] = Field(default=None)  # JSON string
    
    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)), 
        default_factory=datetime.utcnow
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)), 
        default_factory=datetime.utcnow
    )
    
    # Additional metadata
    notes: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
    
    def calculate_slippage(self) -> Optional[Decimal]:
        """Calculate slippage if both expected and fill prices are available"""
        if self.expected_price and self.average_fill_price:
            if self.trade_type == TradeType.BUY:
                slippage = self.average_fill_price - self.expected_price
            else:
                slippage = self.expected_price - self.average_fill_price
            self.slippage = slippage
            return slippage
        return None
    
    def calculate_latency(self) -> Optional[int]:
        """Calculate order acknowledgment latency in milliseconds"""
        if self.order_timestamp and self.ack_timestamp:
            delta = self.ack_timestamp - self.order_timestamp
            latency = int(delta.total_seconds() * 1000)
            self.latency_ms = latency
            return latency
        return None
    
    def is_filled(self) -> bool:
        """Check if trade is fully filled"""
        return self.status == TradeStatus.FILLED and self.filled_quantity == self.quantity
    
    def fill_percentage(self) -> float:
        """Calculate fill percentage"""
        if self.quantity == 0:
            return 0.0
        return (self.filled_quantity / self.quantity) * 100.0


# Create indexes for performance
Trade.__table_args__ = (
    Index('idx_trade_symbol_created', 'symbol', 'created_at'),
    Index('idx_trade_strategy_status', 'strategy_name', 'status'),
    Index('idx_trade_order_timestamp', 'order_timestamp'),
    Index('idx_trade_fill_timestamp', 'fill_timestamp'),
) 