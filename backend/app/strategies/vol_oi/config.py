"""
Volume-OI Strategy Configuration
Defines configurable parameters for the Volume + Delayed-OI Confirm strategy.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Any
from datetime import time


@dataclass
class VolumeOIConfig:
    """Configuration for Volume-OI Confirm Strategy"""
    
    # Strategy identification
    strategy_name: str = "volume_oi_confirm"
    version: str = "1.0"
    description: str = "Volume + Delayed-OI Confirm Strategy"
    
    # Volume spike detection parameters
    volume_spike_threshold_sigma: Decimal = Decimal('3.0')  # >3σ above mean
    volume_multiplier_threshold: Decimal = Decimal('5.0')   # >5× 1-minute average
    volume_lookback_periods: int = 60  # periods for rolling statistics
    
    # Price jump detection parameters
    price_jump_threshold_pct: Decimal = Decimal('0.15')  # 0.15% minimum jump
    price_jump_window_seconds: int = 2  # within 2 seconds
    
    # OI confirmation parameters
    oi_change_threshold_sigma: Decimal = Decimal('1.5')  # >1.5σ for confirmation
    oi_confirmation_window_seconds: int = 240  # 4 minutes max wait
    oi_lookback_periods: int = 30  # periods for rolling OI statistics
    
    # Position sizing
    probe_quantity: int = 2  # Initial probe size (lots)
    scale_quantity: int = 8  # Scale-in size (lots) - total becomes 10
    max_position_size: int = 10  # Maximum position per signal
    
    # Risk management
    profit_target_pct: Decimal = Decimal('40.0')  # 40% profit target
    stop_loss_pct: Decimal = Decimal('25.0')      # 25% stop loss
    timeout_minutes: int = 10  # Exit after 10 minutes
    
    # Daily limits
    daily_loss_limit: Decimal = Decimal('25000')  # ₹25k daily loss cap
    max_positions_per_day: int = 20  # Maximum positions per day
    max_consecutive_losses: int = 5   # Circuit breaker threshold
    
    # Slippage and execution
    max_slippage_bps: int = 30  # 30 bps = ₹0.30 per ₹100
    max_spread_pct: Decimal = Decimal('0.3')  # 0.3% max spread
    partial_fill_threshold: Decimal = Decimal('80.0')  # 80% fill threshold
    partial_fill_timeout_seconds: int = 1  # Cancel remainder after 1s
    requote_max_attempts: int = 3  # Max requote attempts
    requote_price_chase_bps: int = 10  # ₹0.10 max price chase
    
    # Market timing filters
    market_open_time: time = time(9, 15)   # 09:15 IST
    market_close_time: time = time(15, 30) # 15:30 IST
    warmup_time: time = time(9, 30)        # Start trading after 09:30
    
    exclude_first_hour: bool = True    # Skip 09:15-10:15
    exclude_last_hour: bool = True     # Skip 14:30-15:30
    exclude_expiry_day: bool = True    # Skip weekly expiry days
    
    # Margin and leverage
    margin_utilization_pct: Decimal = Decimal('40.0')  # Max 40% margin usage
    hedge_delta_threshold: Decimal = Decimal('0.3')    # Hedge if delta > 30%
    
    # Event filters (trading holidays/events)
    event_blackout_days: List[str] = field(default_factory=lambda: [
        "RBI_POLICY",
        "BUDGET",
        "US_CPI",
        "EXCHANGE_HALT"
    ])
    
    # Performance tracking
    min_win_rate_pct: Decimal = Decimal('65.0')  # Target win rate
    min_profit_factor: Decimal = Decimal('1.5')  # Target profit factor
    max_drawdown_pct: Decimal = Decimal('6.0')   # Max drawdown threshold
    
    # Data validation
    max_data_age_seconds: int = 10     # Max stale data age
    min_volume_threshold: int = 100    # Minimum volume for consideration
    min_oi_threshold: int = 1000       # Minimum OI for consideration
    
    # Monitoring and alerts
    latency_alert_threshold_ms: int = 200      # Alert if latency > 200ms
    slippage_alert_threshold: int = 3          # Alert if 3+ blocked by slippage in 5min
    consecutive_loss_alert: int = 3            # Alert after 3 consecutive losses
    
    # Debug and testing
    dry_run_mode: bool = False         # Paper trading mode
    verbose_logging: bool = True       # Detailed logging
    save_debug_data: bool = True       # Save market data snapshots
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization"""
        return {
            'strategy_name': self.strategy_name,
            'version': self.version,
            'description': self.description,
            
            # Detection thresholds
            'volume_spike_threshold_sigma': float(self.volume_spike_threshold_sigma),
            'volume_multiplier_threshold': float(self.volume_multiplier_threshold),
            'price_jump_threshold_pct': float(self.price_jump_threshold_pct),
            'oi_change_threshold_sigma': float(self.oi_change_threshold_sigma),
            
            # Position sizing
            'probe_quantity': self.probe_quantity,
            'scale_quantity': self.scale_quantity,
            'max_position_size': self.max_position_size,
            
            # Risk management
            'profit_target_pct': float(self.profit_target_pct),
            'stop_loss_pct': float(self.stop_loss_pct),
            'timeout_minutes': self.timeout_minutes,
            'daily_loss_limit': float(self.daily_loss_limit),
            
            # Execution parameters
            'max_slippage_bps': self.max_slippage_bps,
            'max_spread_pct': float(self.max_spread_pct),
            'partial_fill_threshold': float(self.partial_fill_threshold),
            
            # Market timing
            'market_open_time': self.market_open_time.strftime('%H:%M'),
            'market_close_time': self.market_close_time.strftime('%H:%M'),
            'warmup_time': self.warmup_time.strftime('%H:%M'),
            'exclude_first_hour': self.exclude_first_hour,
            'exclude_last_hour': self.exclude_last_hour,
            'exclude_expiry_day': self.exclude_expiry_day,
            
            # Other parameters
            'margin_utilization_pct': float(self.margin_utilization_pct),
            'event_blackout_days': self.event_blackout_days,
            'dry_run_mode': self.dry_run_mode,
            'verbose_logging': self.verbose_logging
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'VolumeOIConfig':
        """Create config from dictionary"""
        config = cls()
        
        for key, value in config_dict.items():
            if hasattr(config, key):
                # Convert string times back to time objects
                if key in ['market_open_time', 'market_close_time', 'warmup_time']:
                    if isinstance(value, str):
                        hour, minute = map(int, value.split(':'))
                        value = time(hour, minute)
                
                # Convert numeric strings to Decimal where appropriate
                elif key in ['volume_spike_threshold_sigma', 'volume_multiplier_threshold',
                           'price_jump_threshold_pct', 'oi_change_threshold_sigma',
                           'profit_target_pct', 'stop_loss_pct', 'daily_loss_limit',
                           'max_spread_pct', 'partial_fill_threshold', 'margin_utilization_pct']:
                    value = Decimal(str(value))
                
                setattr(config, key, value)
        
        return config
    
    def validate(self) -> List[str]:
        """Validate configuration parameters"""
        errors = []
        
        # Validate thresholds
        if self.volume_spike_threshold_sigma < 1.0:
            errors.append("volume_spike_threshold_sigma must be >= 1.0")
        
        if self.volume_multiplier_threshold < 1.0:
            errors.append("volume_multiplier_threshold must be >= 1.0")
        
        if self.price_jump_threshold_pct <= 0:
            errors.append("price_jump_threshold_pct must be > 0")
        
        if self.oi_change_threshold_sigma < 1.0:
            errors.append("oi_change_threshold_sigma must be >= 1.0")
        
        # Validate position sizing
        if self.probe_quantity <= 0:
            errors.append("probe_quantity must be > 0")
        
        if self.scale_quantity <= 0:
            errors.append("scale_quantity must be > 0")
        
        if self.max_position_size < (self.probe_quantity + self.scale_quantity):
            errors.append("max_position_size must be >= probe_quantity + scale_quantity")
        
        # Validate risk parameters
        if self.profit_target_pct <= 0:
            errors.append("profit_target_pct must be > 0")
        
        if self.stop_loss_pct <= 0:
            errors.append("stop_loss_pct must be > 0")
        
        if self.timeout_minutes <= 0:
            errors.append("timeout_minutes must be > 0")
        
        # Validate timing
        if self.market_open_time >= self.market_close_time:
            errors.append("market_open_time must be before market_close_time")
        
        if self.warmup_time <= self.market_open_time:
            errors.append("warmup_time must be after market_open_time")
        
        # Validate execution parameters
        if self.max_slippage_bps < 0:
            errors.append("max_slippage_bps must be >= 0")
        
        if self.max_spread_pct <= 0:
            errors.append("max_spread_pct must be > 0")
        
        if not (0 < self.partial_fill_threshold <= 100):
            errors.append("partial_fill_threshold must be between 0 and 100")
        
        if not (0 < self.margin_utilization_pct <= 100):
            errors.append("margin_utilization_pct must be between 0 and 100")
        
        return errors
    
    def get_market_hours(self) -> tuple[time, time]:
        """Get trading market hours"""
        return self.market_open_time, self.market_close_time
    
    def get_trading_hours(self) -> tuple[time, time]:
        """Get actual trading hours after filters"""
        start_time = self.warmup_time
        end_time = self.market_close_time
        
        if self.exclude_first_hour:
            # Skip first hour after warmup
            start_hour = start_time.hour + 1
            start_time = time(start_hour, start_time.minute)
        
        if self.exclude_last_hour:
            # Skip last hour before close
            end_hour = end_time.hour - 1
            end_time = time(end_hour, end_time.minute)
        
        return start_time, end_time
    
    def is_trading_time(self, current_time: time) -> bool:
        """Check if current time is within trading hours"""
        start_time, end_time = self.get_trading_hours()
        return start_time <= current_time <= end_time
    
    def get_position_limit(self) -> int:
        """Get maximum position size"""
        return self.max_position_size
    
    def get_risk_limits(self) -> Dict[str, Any]:
        """Get risk management limits"""
        return {
            'daily_loss_limit': float(self.daily_loss_limit),
            'profit_target_pct': float(self.profit_target_pct),
            'stop_loss_pct': float(self.stop_loss_pct),
            'timeout_minutes': self.timeout_minutes,
            'max_consecutive_losses': self.max_consecutive_losses,
            'max_positions_per_day': self.max_positions_per_day,
            'margin_utilization_pct': float(self.margin_utilization_pct)
        }


# Default configuration instance
DEFAULT_CONFIG = VolumeOIConfig() 