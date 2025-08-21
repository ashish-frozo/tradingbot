"""
Strategy Model
Manages trading strategies and their runtime configurations
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum
from sqlmodel import SQLModel, Field, Column, DateTime, Numeric, JSON
from sqlalchemy import Index


class StrategyStatus(str, Enum):
    """Strategy status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    TESTING = "testing"
    ERROR = "error"


class StrategyConfig(SQLModel, table=True):
    """
    Strategy configuration model
    Stores strategy parameters and settings
    """
    
    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Configuration identification
    strategy_name: str = Field(max_length=100, index=True)
    config_version: str = Field(max_length=20)
    is_active: bool = Field(default=True)
    
    # Volume-OI strategy specific parameters
    volume_spike_threshold: Decimal = Field(
        sa_column=Column(Numeric(6, 2)), default=Decimal('3.0')
    )  # Standard deviations above mean
    
    volume_multiplier_threshold: Decimal = Field(
        sa_column=Column(Numeric(6, 2)), default=Decimal('5.0')
    )  # Multiple of 1-minute average
    
    price_jump_threshold: Decimal = Field(
        sa_column=Column(Numeric(6, 4)), default=Decimal('0.0015')
    )  # 0.15% price jump
    
    oi_change_threshold: Decimal = Field(
        sa_column=Column(Numeric(6, 2)), default=Decimal('1.5')
    )  # Standard deviations for OI change
    
    oi_confirm_window_seconds: int = Field(default=180)  # 3 minutes
    
    # Position sizing
    probe_quantity: int = Field(default=2)  # Initial probe size
    scale_quantity: int = Field(default=10)  # Scale up size
    max_position_size: int = Field(default=50)  # Maximum position
    
    # Risk management
    profit_target_pct: Decimal = Field(
        sa_column=Column(Numeric(6, 4)), default=Decimal('0.40')
    )  # 40% profit target
    
    stop_loss_pct: Decimal = Field(
        sa_column=Column(Numeric(6, 4)), default=Decimal('0.25')
    )  # 25% stop loss
    
    timeout_minutes: int = Field(default=10)  # Exit timeout
    
    daily_loss_limit: Decimal = Field(
        sa_column=Column(Numeric(10, 2)), default=Decimal('25000')
    )  # ₹25k daily loss limit
    
    max_slippage_bps: int = Field(default=10)  # 10 bps max slippage
    
    # Market filters
    min_market_hour: int = Field(default=9)  # 9 AM
    max_market_hour: int = Field(default=15)  # 3 PM
    
    exclude_expiry_day: bool = Field(default=True)
    exclude_first_hour: bool = Field(default=True)
    exclude_last_hour: bool = Field(default=True)
    
    # Latency and performance
    max_order_latency_ms: int = Field(default=150)
    
    # Additional parameters as JSON
    additional_params: Optional[Dict[str, Any]] = Field(
        sa_column=Column(JSON), default=None
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
    
    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class Strategy(SQLModel, table=True):
    """
    Main strategy model
    Tracks strategy runtime state and performance
    """
    
    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Strategy identification
    name: str = Field(max_length=100, unique=True, index=True)
    description: str = Field(max_length=500)
    strategy_type: str = Field(max_length=50)  # e.g., "volume_oi_confirm"
    
    # Status and control
    status: StrategyStatus = Field(default=StrategyStatus.TESTING)
    is_enabled: bool = Field(default=False)
    auto_trade: bool = Field(default=False)
    
    # Current configuration
    active_config_id: Optional[int] = Field(default=None, foreign_key="strategyconfig.id")
    
    # Performance metrics
    total_trades: int = Field(default=0)
    winning_trades: int = Field(default=0)
    losing_trades: int = Field(default=0)
    
    total_pnl: Decimal = Field(
        sa_column=Column(Numeric(12, 2)), default=0
    )
    daily_pnl: Decimal = Field(
        sa_column=Column(Numeric(10, 2)), default=0
    )
    max_drawdown: Decimal = Field(
        sa_column=Column(Numeric(10, 2)), default=0
    )
    
    # Risk metrics
    sharpe_ratio: Optional[Decimal] = Field(
        sa_column=Column(Numeric(6, 4)), default=None
    )
    win_rate: Optional[Decimal] = Field(
        sa_column=Column(Numeric(6, 4)), default=None
    )
    profit_factor: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 4)), default=None
    )
    
    # Operational metrics
    avg_latency_ms: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 2)), default=None
    )
    uptime_pct: Optional[Decimal] = Field(
        sa_column=Column(Numeric(6, 4)), default=None
    )
    
    # Capital allocation
    allocated_capital: Decimal = Field(
        sa_column=Column(Numeric(12, 2)), default=0
    )
    used_capital: Decimal = Field(
        sa_column=Column(Numeric(12, 2)), default=0
    )
    
    # Last runtime information
    last_signal_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    last_trade_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    last_error_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    last_error_msg: Optional[str] = Field(default=None, max_length=500)
    
    # Health and monitoring
    consecutive_losses: int = Field(default=0)
    circuit_breaker_triggered: bool = Field(default=False)
    circuit_breaker_reason: Optional[str] = Field(default=None, max_length=200)
    
    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)), 
        default_factory=datetime.utcnow
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)), 
        default_factory=datetime.utcnow
    )
    started_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    stopped_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    
    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
    
    def calculate_win_rate(self) -> Decimal:
        """Calculate win rate percentage"""
        if self.total_trades == 0:
            return Decimal('0')
        rate = (self.winning_trades / self.total_trades) * 100
        self.win_rate = Decimal(str(rate))
        return self.win_rate
    
    def calculate_profit_factor(self) -> Optional[Decimal]:
        """Calculate profit factor (gross profit / gross loss)"""
        # This would need trade details to calculate properly
        # Placeholder implementation
        if self.losing_trades == 0:
            return None
        return self.profit_factor
    
    def is_operational(self) -> bool:
        """Check if strategy is operational (active and enabled)"""
        return (self.status == StrategyStatus.ACTIVE and 
                self.is_enabled and 
                not self.circuit_breaker_triggered)
    
    def trigger_circuit_breaker(self, reason: str) -> None:
        """Trigger circuit breaker and pause strategy"""
        self.circuit_breaker_triggered = True
        self.circuit_breaker_reason = reason
        self.status = StrategyStatus.PAUSED
        self.is_enabled = False
        self.updated_at = datetime.utcnow()
    
    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker"""
        self.circuit_breaker_triggered = False
        self.circuit_breaker_reason = None
        self.consecutive_losses = 0
        self.updated_at = datetime.utcnow()
    
    def start_strategy(self) -> None:
        """Start the strategy"""
        self.status = StrategyStatus.ACTIVE
        self.is_enabled = True
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def stop_strategy(self) -> None:
        """Stop the strategy"""
        self.status = StrategyStatus.INACTIVE
        self.is_enabled = False
        self.stopped_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


# Create indexes for performance
Strategy.__table_args__ = (
    Index('idx_strategy_status_enabled', 'status', 'is_enabled'),
    Index('idx_strategy_performance', 'total_pnl', 'win_rate'),
    Index('idx_strategy_updated', 'updated_at'),
)

StrategyConfig.__table_args__ = (
    Index('idx_config_strategy_active', 'strategy_name', 'is_active'),
    Index('idx_config_version', 'strategy_name', 'config_version'),
) 