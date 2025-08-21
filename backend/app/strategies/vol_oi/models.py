"""
Volume-OI Strategy Data Models
Defines the data structures for tracking volume spikes, OI changes, and strategy signals.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any


class SignalStrength(str, Enum):
    """Signal strength levels for volume and OI detection"""
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"
    CRITICAL = "critical"


class TradePhase(str, Enum):
    """Trading phases in the Volume-OI strategy"""
    WAITING = "waiting"
    PROBE_TRIGGERED = "probe_triggered"
    PROBE_EXECUTED = "probe_executed"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    SCALED = "scaled"
    EXITING = "exiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class VolumeSignal:
    """Volume spike detection signal"""
    symbol: str
    timestamp: datetime
    current_volume: int
    volume_1min_avg: int
    volume_stddev: Decimal
    volume_zscore: Decimal
    volume_multiplier: Decimal  # Current / 1-min average
    strength: SignalStrength
    is_spike: bool
    
    def __post_init__(self):
        # Determine if this is a volume spike (>3σ AND >5× 1-min average)
        self.is_spike = (
            self.volume_zscore >= 3.0 and 
            self.volume_multiplier >= 5.0
        )
        
        # Set strength based on magnitude
        if self.volume_zscore >= 5.0 and self.volume_multiplier >= 10.0:
            self.strength = SignalStrength.CRITICAL
        elif self.volume_zscore >= 4.0 and self.volume_multiplier >= 7.5:
            self.strength = SignalStrength.STRONG
        elif self.volume_zscore >= 3.5 and self.volume_multiplier >= 6.0:
            self.strength = SignalStrength.MEDIUM
        else:
            self.strength = SignalStrength.WEAK


@dataclass
class PriceJumpSignal:
    """Price jump detection signal"""
    symbol: str
    timestamp: datetime
    previous_price: Decimal
    current_price: Decimal
    price_change_pct: Decimal
    time_window_seconds: int
    is_jump: bool
    direction: str  # "up" or "down"
    
    def __post_init__(self):
        self.price_change_pct = abs(
            (self.current_price - self.previous_price) / self.previous_price * 100
        )
        self.is_jump = (
            self.price_change_pct >= 0.15 and 
            self.time_window_seconds <= 2
        )
        self.direction = "up" if self.current_price > self.previous_price else "down"


@dataclass
class OISignal:
    """Open Interest change detection signal"""
    symbol: str
    timestamp: datetime
    previous_oi: int
    current_oi: int
    oi_change: int
    oi_change_pct: Decimal
    oi_stddev: Decimal
    oi_zscore: Decimal
    time_since_trigger_seconds: int
    is_confirmation: bool
    strength: SignalStrength
    
    def __post_init__(self):
        self.oi_change = self.current_oi - self.previous_oi
        if self.previous_oi > 0:
            self.oi_change_pct = (self.oi_change / self.previous_oi) * 100
        else:
            self.oi_change_pct = Decimal('0')
        
        # OI confirmation is >1.5σ within 240 seconds
        self.is_confirmation = (
            abs(self.oi_zscore) >= 1.5 and 
            self.time_since_trigger_seconds <= 240
        )
        
        # Set strength
        if abs(self.oi_zscore) >= 3.0:
            self.strength = SignalStrength.CRITICAL
        elif abs(self.oi_zscore) >= 2.5:
            self.strength = SignalStrength.STRONG
        elif abs(self.oi_zscore) >= 2.0:
            self.strength = SignalStrength.MEDIUM
        else:
            self.strength = SignalStrength.WEAK


@dataclass
class StrategySignal:
    """Complete strategy signal combining volume, price, and OI signals"""
    signal_id: str
    symbol: str
    timestamp: datetime
    phase: TradePhase
    
    # Component signals
    volume_signal: Optional[VolumeSignal] = None
    price_signal: Optional[PriceJumpSignal] = None
    oi_signal: Optional[OISignal] = None
    
    # Trade details
    entry_price: Optional[Decimal] = None
    hedge_symbol: Optional[str] = None
    hedge_price: Optional[Decimal] = None
    probe_quantity: int = 2
    scale_quantity: int = 8
    
    # Timing
    trigger_time: Optional[datetime] = None
    probe_time: Optional[datetime] = None
    confirmation_time: Optional[datetime] = None
    scale_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    
    # P&L tracking
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    
    # Exit conditions
    profit_target_pct: Decimal = Decimal('40')  # 40% profit target
    stop_loss_pct: Decimal = Decimal('-25')    # -25% stop loss
    timeout_minutes: int = 10
    
    # Risk metrics
    max_drawdown: Decimal = Decimal('0')
    peak_profit: Decimal = Decimal('0')
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = None
    
    def is_triggered(self) -> bool:
        """Check if the strategy signal is triggered (volume spike + price jump)"""
        return (
            self.volume_signal and self.volume_signal.is_spike and
            self.price_signal and self.price_signal.is_jump
        )
    
    def is_confirmed(self) -> bool:
        """Check if the strategy signal is confirmed (OI change)"""
        return (
            self.is_triggered() and 
            self.oi_signal and self.oi_signal.is_confirmation
        )
    
    def should_exit(self) -> tuple[bool, str]:
        """Check if position should be exited and reason"""
        if self.phase in [TradePhase.COMPLETED, TradePhase.CANCELLED]:
            return False, ""
        
        # Profit target hit
        if self.unrealized_pnl >= (self.entry_price * self.profit_target_pct / 100):
            return True, "profit_target"
        
        # Stop loss hit
        if self.unrealized_pnl <= (self.entry_price * self.stop_loss_pct / 100):
            return True, "stop_loss"
        
        # Timeout
        if (self.trigger_time and 
            (datetime.utcnow() - self.trigger_time).total_seconds() > self.timeout_minutes * 60):
            return True, "timeout"
        
        return False, ""
    
    def update_pnl(self, current_price: Decimal, quantity: int) -> None:
        """Update P&L calculations"""
        if not self.entry_price:
            return
        
        # Calculate unrealized P&L
        price_diff = current_price - self.entry_price
        self.unrealized_pnl = price_diff * quantity
        
        # Track peak profit and max drawdown
        if self.unrealized_pnl > self.peak_profit:
            self.peak_profit = self.unrealized_pnl
        
        drawdown = self.peak_profit - self.unrealized_pnl
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
    
    def get_summary(self) -> Dict[str, Any]:
        """Get signal summary for logging and monitoring"""
        return {
            'signal_id': self.signal_id,
            'symbol': self.symbol,
            'phase': self.phase,
            'is_triggered': self.is_triggered(),
            'is_confirmed': self.is_confirmed(),
            'volume_spike': self.volume_signal.is_spike if self.volume_signal else False,
            'price_jump': self.price_signal.is_jump if self.price_signal else False,
            'oi_confirmation': self.oi_signal.is_confirmation if self.oi_signal else False,
            'unrealized_pnl': float(self.unrealized_pnl),
            'realized_pnl': float(self.realized_pnl),
            'max_drawdown': float(self.max_drawdown),
            'peak_profit': float(self.peak_profit),
            'entry_price': float(self.entry_price) if self.entry_price else None,
            'trigger_time': self.trigger_time.isoformat() if self.trigger_time else None,
            'probe_time': self.probe_time.isoformat() if self.probe_time else None,
            'confirmation_time': self.confirmation_time.isoformat() if self.confirmation_time else None,
            'exit_conditions': self.should_exit()
        }


@dataclass
class EventFilter:
    """Event filter for market conditions"""
    date: datetime
    event_type: str  # "RBI", "Budget", "US-CPI", "Exchange-Halt"
    description: str
    is_active: bool
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def is_blocking_trade(self, current_time: datetime) -> bool:
        """Check if this event should block trading"""
        if not self.is_active:
            return False
        
        # If no specific time range, block the entire day
        if not self.start_time or not self.end_time:
            return current_time.date() == self.date.date()
        
        # Block during specific time range
        return self.start_time <= current_time <= self.end_time


@dataclass
class PerformanceMetrics:
    """Strategy performance tracking"""
    total_signals: int = 0
    triggered_signals: int = 0
    confirmed_signals: int = 0
    completed_trades: int = 0
    profitable_trades: int = 0
    
    total_pnl: Decimal = Decimal('0')
    gross_profit: Decimal = Decimal('0')
    gross_loss: Decimal = Decimal('0')
    
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    current_streak: int = 0
    
    avg_hold_time_minutes: Decimal = Decimal('0')
    avg_profit_per_trade: Decimal = Decimal('0')
    avg_loss_per_trade: Decimal = Decimal('0')
    
    profit_factor: Optional[Decimal] = None
    win_rate: Optional[Decimal] = None
    sharpe_ratio: Optional[Decimal] = None
    
    def update_from_trade(self, signal: StrategySignal) -> None:
        """Update metrics from completed trade"""
        if signal.phase != TradePhase.COMPLETED:
            return
        
        self.completed_trades += 1
        self.total_pnl += signal.realized_pnl
        
        if signal.realized_pnl > 0:
            self.profitable_trades += 1
            self.gross_profit += signal.realized_pnl
            self.current_streak = max(0, self.current_streak) + 1
            self.max_consecutive_wins = max(self.max_consecutive_wins, self.current_streak)
        else:
            self.gross_loss += abs(signal.realized_pnl)
            self.current_streak = min(0, self.current_streak) - 1
            self.max_consecutive_losses = max(self.max_consecutive_losses, abs(self.current_streak))
        
        # Calculate derived metrics
        if self.completed_trades > 0:
            self.win_rate = (self.profitable_trades / self.completed_trades) * 100
            self.avg_profit_per_trade = self.total_pnl / self.completed_trades
        
        if self.profitable_trades > 0:
            self.avg_profit_per_trade = self.gross_profit / self.profitable_trades
        
        losing_trades = self.completed_trades - self.profitable_trades
        if losing_trades > 0:
            self.avg_loss_per_trade = self.gross_loss / losing_trades
        
        if self.gross_loss > 0:
            self.profit_factor = self.gross_profit / self.gross_loss
        
        # Calculate hold time
        if signal.trigger_time and signal.exit_time:
            hold_time = (signal.exit_time - signal.trigger_time).total_seconds() / 60
            # Simple moving average for now
            if self.avg_hold_time_minutes == 0:
                self.avg_hold_time_minutes = Decimal(str(hold_time))
            else:
                self.avg_hold_time_minutes = (
                    (self.avg_hold_time_minutes * (self.completed_trades - 1) + 
                     Decimal(str(hold_time))) / self.completed_trades
                ) 