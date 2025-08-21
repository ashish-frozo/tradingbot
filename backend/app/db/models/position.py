"""
Position Model
Tracks current portfolio positions and aggregated P&L
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum
from sqlmodel import SQLModel, Field, Column, DateTime, Numeric
from sqlalchemy import Index


class PositionStatus(str, Enum):
    """Position status enumeration"""
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL = "partial"


class Position(SQLModel, table=True):
    """
    Position model for tracking portfolio state
    Aggregates trades into net positions with real-time P&L
    """
    
    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Position identification
    symbol: str = Field(max_length=100, index=True)
    exchange: str = Field(max_length=20)
    strategy_name: str = Field(max_length=100, index=True)
    
    # Position details
    status: PositionStatus = Field(default=PositionStatus.OPEN)
    net_quantity: int = Field(default=0)  # Positive = Long, Negative = Short
    average_price: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    
    # P&L tracking
    realized_pnl: Decimal = Field(
        sa_column=Column(Numeric(12, 2)), default=0
    )
    unrealized_pnl: Decimal = Field(
        sa_column=Column(Numeric(12, 2)), default=0
    )
    total_pnl: Decimal = Field(
        sa_column=Column(Numeric(12, 2)), default=0
    )
    
    # Cost tracking
    total_cost: Decimal = Field(
        sa_column=Column(Numeric(12, 2)), default=0
    )
    total_commission: Decimal = Field(
        sa_column=Column(Numeric(8, 2)), default=0
    )
    total_brokerage: Decimal = Field(
        sa_column=Column(Numeric(8, 2)), default=0
    )
    
    # Market values
    current_price: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    market_value: Optional[Decimal] = Field(
        sa_column=Column(Numeric(12, 2)), default=None
    )
    
    # Greeks and risk metrics (for options)
    delta: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 6)), default=None
    )
    gamma: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 6)), default=None
    )
    theta: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 6)), default=None
    )
    vega: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 6)), default=None
    )
    implied_volatility: Optional[Decimal] = Field(
        sa_column=Column(Numeric(6, 4)), default=None
    )
    
    # Risk and margin
    margin_required: Optional[Decimal] = Field(
        sa_column=Column(Numeric(12, 2)), default=None
    )
    margin_used: Optional[Decimal] = Field(
        sa_column=Column(Numeric(12, 2)), default=None
    )
    
    # Position limits and controls
    max_position_size: Optional[int] = Field(default=None)
    stop_loss_price: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    take_profit_price: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    
    # Trading statistics
    total_trades: int = Field(default=0)
    winning_trades: int = Field(default=0)
    losing_trades: int = Field(default=0)
    largest_win: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    largest_loss: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    
    # Time tracking
    first_trade_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    last_trade_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    closed_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    
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
    
    def is_long(self) -> bool:
        """Check if position is long"""
        return self.net_quantity > 0
    
    def is_short(self) -> bool:
        """Check if position is short"""
        return self.net_quantity < 0
    
    def is_flat(self) -> bool:
        """Check if position is flat (no quantity)"""
        return self.net_quantity == 0
    
    def calculate_total_pnl(self) -> Decimal:
        """Calculate total P&L"""
        self.total_pnl = self.realized_pnl + self.unrealized_pnl
        return self.total_pnl
    
    def calculate_market_value(self) -> Optional[Decimal]:
        """Calculate current market value"""
        if self.current_price is not None and self.net_quantity != 0:
            self.market_value = abs(self.net_quantity) * self.current_price
            return self.market_value
        return None
    
    def calculate_unrealized_pnl(self) -> Optional[Decimal]:
        """Calculate unrealized P&L based on current price"""
        if (self.current_price is not None and 
            self.average_price is not None and 
            self.net_quantity != 0):
            
            if self.is_long():
                unrealized = (self.current_price - self.average_price) * self.net_quantity
            else:
                unrealized = (self.average_price - self.current_price) * abs(self.net_quantity)
            
            self.unrealized_pnl = unrealized
            self.calculate_total_pnl()  # Update total P&L
            return self.unrealized_pnl
        return None
    
    def win_rate(self) -> float:
        """Calculate win rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100.0
    
    def profit_factor(self) -> Optional[float]:
        """Calculate profit factor (gross profit / gross loss)"""
        if self.largest_loss is None or self.largest_loss == 0:
            return None
        if self.largest_win is None:
            return 0.0
        return float(abs(self.largest_win) / abs(self.largest_loss))
    
    def update_from_trade(self, trade_quantity: int, trade_price: Decimal, 
                         commission: Decimal = Decimal('0')) -> None:
        """Update position from a new trade"""
        # Update trade statistics
        self.total_trades += 1
        self.total_commission += commission
        self.last_trade_at = datetime.utcnow()
        
        if self.first_trade_at is None:
            self.first_trade_at = datetime.utcnow()
        
        # Calculate new average price and net quantity
        if self.net_quantity == 0:
            # New position
            self.net_quantity = trade_quantity
            self.average_price = trade_price
            self.total_cost = abs(trade_quantity) * trade_price
        else:
            # Update existing position
            current_value = self.net_quantity * self.average_price
            trade_value = trade_quantity * trade_price
            
            new_quantity = self.net_quantity + trade_quantity
            
            if new_quantity == 0:
                # Position closed
                self.realized_pnl += -current_value - trade_value
                self.net_quantity = 0
                self.average_price = None
                self.status = PositionStatus.CLOSED
                self.closed_at = datetime.utcnow()
            else:
                # Position modified
                new_total_value = current_value + trade_value
                self.net_quantity = new_quantity
                self.average_price = new_total_value / new_quantity
                self.total_cost += abs(trade_quantity) * trade_price
        
        self.updated_at = datetime.utcnow()


# Create indexes for performance
Position.__table_args__ = (
    Index('idx_position_symbol_strategy', 'symbol', 'strategy_name'),
    Index('idx_position_status_updated', 'status', 'updated_at'),
    Index('idx_position_pnl', 'total_pnl'),
    Index('idx_position_active', 'status', 'net_quantity'),
) 