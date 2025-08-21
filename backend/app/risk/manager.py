"""
Risk Manager Module

Comprehensive risk management system for the trading bot.
Key features:
- Daily P&L stop loss with ₹25k hard cap
- Auto-flatten functionality on limit breach
- Real-time position monitoring  
- Circuit breaker integration
- Emergency stop mechanisms
"""

import asyncio
from datetime import datetime, timezone, time
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

from loguru import logger

from app.core.config import get_settings
from app.cache.redis import redis_client
from .calculator import risk_calculator, PortfolioRisk, RiskLevel


class RiskStatus(Enum):
    """Risk management status"""
    NORMAL = "normal"
    WARNING = "warning"
    DANGER = "danger"
    LOCKED = "locked"
    EMERGENCY = "emergency"


class StopLossType(Enum):
    """Types of stop loss triggers"""
    DAILY_PNL = "daily_pnl"
    POSITION_PNL = "position_pnl"
    MARGIN_BREACH = "margin_breach"
    MANUAL = "manual"
    EMERGENCY = "emergency"


@dataclass
class RiskLimits:
    """Risk limits configuration"""
    daily_loss_limit: float = 25000.0  # ₹25k per PRD
    daily_profit_limit: float = 100000.0  # Optional profit booking
    max_margin_utilization: float = 0.80  # 80% max margin usage
    max_positions_per_strategy: int = 10  # 10 lots per signal per PRD
    max_total_positions: int = 50  # 50 lots total per PRD
    max_open_orders: int = 20  # Maximum pending orders
    position_concentration_limit: float = 0.30  # 30% max in single position


@dataclass 
class RiskEvent:
    """Risk event for logging and alerts"""
    timestamp: datetime
    event_type: StopLossType
    severity: RiskStatus
    description: str
    current_pnl: float
    action_taken: str
    position_count: int
    strategy_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class RiskManager:
    """
    Comprehensive risk management system
    
    Features:
    - Daily P&L monitoring with hard stop at ₹25k loss
    - Auto-flatten on limit breach
    - Position size and concentration monitoring
    - Integration with trading strategies
    - Real-time risk alerts
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logger.bind(module="risk_manager")
        
        # Risk configuration
        self.limits = RiskLimits()
        self.current_status = RiskStatus.NORMAL
        self.is_flatten_in_progress = False
        self.is_trading_halted = False
        
        # Callbacks for external systems
        self.flatten_callback: Optional[Callable] = None
        self.alert_callback: Optional[Callable] = None
        self.position_callback: Optional[Callable] = None
        
        # Risk tracking
        self.daily_pnl = 0.0
        self.start_of_day_balance = 0.0
        self.last_risk_check = datetime.now(timezone.utc)
        self.risk_events: List[RiskEvent] = []
        
        # Redis keys for persistence
        self.redis_prefix = "risk_manager"
        self.daily_pnl_key = f"{self.redis_prefix}:daily_pnl"
        self.risk_status_key = f"{self.redis_prefix}:status"
        self.risk_events_key = f"{self.redis_prefix}:events"
        
    async def initialize(self):
        """Initialize risk manager and load persisted state"""
        try:
            # Load persisted daily P&L
            stored_pnl = await redis_client.get(self.daily_pnl_key)
            if stored_pnl:
                self.daily_pnl = float(stored_pnl)
            
            # Load risk status
            stored_status = await redis_client.get(self.risk_status_key)
            if stored_status:
                self.current_status = RiskStatus(stored_status)
            
            # Check if we need to reset daily counters
            await self._check_daily_reset()
            
            self.logger.info(
                f"Risk manager initialized: Status={self.current_status.value}, "
                f"Daily P&L=₹{self.daily_pnl:,.0f}",
                extra={
                    "status": self.current_status.value,
                    "daily_pnl": self.daily_pnl,
                    "limits": self.limits.__dict__
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error initializing risk manager: {e}")
            raise
    
    async def _check_daily_reset(self):
        """Check if we need to reset daily counters at market open"""
        try:
            # Get market open time (9:15 AM IST)
            now = datetime.now(timezone.utc)
            ist_now = now.astimezone(timezone.utc).replace(tzinfo=None)
            
            # Check if it's a new trading day (after 9:15 AM IST)
            market_open_time = time(3, 45)  # 9:15 AM IST in UTC (assuming UTC+5:30)
            last_reset_key = f"{self.redis_prefix}:last_reset"
            last_reset = await redis_client.get(last_reset_key)
            
            if last_reset:
                last_reset_date = datetime.fromisoformat(last_reset).date()
                current_date = ist_now.date()
                
                # Reset if it's a new day and past market open
                if current_date > last_reset_date and ist_now.time() >= market_open_time:
                    await self._reset_daily_counters()
                    await redis_client.set(last_reset_key, ist_now.isoformat())
            else:
                # First time setup
                await redis_client.set(last_reset_key, ist_now.isoformat())
                
        except Exception as e:
            self.logger.error(f"Error checking daily reset: {e}")
    
    async def _reset_daily_counters(self):
        """Reset daily risk counters"""
        try:
            self.daily_pnl = 0.0
            self.current_status = RiskStatus.NORMAL
            self.is_trading_halted = False
            self.risk_events.clear()
            
            # Clear Redis keys
            await redis_client.delete(self.daily_pnl_key)
            await redis_client.delete(self.risk_status_key)
            await redis_client.delete(self.risk_events_key)
            
            self.logger.info("Daily risk counters reset for new trading day")
            
        except Exception as e:
            self.logger.error(f"Error resetting daily counters: {e}")
    
    async def update_daily_pnl(self, realized_pnl: float, unrealized_pnl: float = 0):
        """
        Update daily P&L and check risk limits
        
        Args:
            realized_pnl: Realized P&L for the day
            unrealized_pnl: Current unrealized P&L
        """
        try:
            # Update daily P&L (realized + unrealized)
            self.daily_pnl = realized_pnl + unrealized_pnl
            
            # Persist to Redis
            await redis_client.set(self.daily_pnl_key, str(self.daily_pnl))
            
            # Check risk limits
            await self._check_daily_loss_limit()
            
            self.logger.debug(
                f"Daily P&L updated: ₹{self.daily_pnl:,.0f} "
                f"(Realized: ₹{realized_pnl:,.0f}, Unrealized: ₹{unrealized_pnl:,.0f})",
                extra={
                    "daily_pnl": self.daily_pnl,
                    "realized_pnl": realized_pnl,
                    "unrealized_pnl": unrealized_pnl,
                    "risk_status": self.current_status.value
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error updating daily P&L: {e}")
    
    async def _check_daily_loss_limit(self):
        """Check if daily loss limit is breached and trigger auto-flatten"""
        try:
            # Check hard stop loss limit
            if self.daily_pnl <= -self.limits.daily_loss_limit:
                if not self.is_flatten_in_progress:
                    await self._trigger_auto_flatten(
                        StopLossType.DAILY_PNL,
                        f"Daily loss limit breached: ₹{self.daily_pnl:,.0f} <= -₹{self.limits.daily_loss_limit:,.0f}"
                    )
                return
            
            # Warning levels
            warning_threshold = -self.limits.daily_loss_limit * 0.80  # 80% of limit
            danger_threshold = -self.limits.daily_loss_limit * 0.95   # 95% of limit
            
            previous_status = self.current_status
            
            if self.daily_pnl <= danger_threshold:
                self.current_status = RiskStatus.DANGER
            elif self.daily_pnl <= warning_threshold:
                self.current_status = RiskStatus.WARNING
            else:
                self.current_status = RiskStatus.NORMAL
            
            # Log status changes
            if self.current_status != previous_status:
                await self._log_risk_event(
                    StopLossType.DAILY_PNL,
                    self.current_status,
                    f"Risk status changed from {previous_status.value} to {self.current_status.value}",
                    "status_change"
                )
                
                # Update Redis
                await redis_client.set(self.risk_status_key, self.current_status.value)
            
        except Exception as e:
            self.logger.error(f"Error checking daily loss limit: {e}")
    
    async def _trigger_auto_flatten(self, trigger_type: StopLossType, reason: str):
        """
        Trigger auto-flatten of all positions
        
        Args:
            trigger_type: Type of stop loss trigger
            reason: Reason for auto-flatten
        """
        try:
            if self.is_flatten_in_progress:
                self.logger.warning("Auto-flatten already in progress, skipping")
                return
            
            self.is_flatten_in_progress = True
            self.current_status = RiskStatus.EMERGENCY
            self.is_trading_halted = True
            
            # Log critical risk event
            await self._log_risk_event(
                trigger_type,
                RiskStatus.EMERGENCY,
                reason,
                "auto_flatten_triggered"
            )
            
            self.logger.critical(
                f"🚨 AUTO-FLATTEN TRIGGERED: {reason}",
                extra={
                    "trigger_type": trigger_type.value,
                    "daily_pnl": self.daily_pnl,
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Execute flatten if callback is registered
            if self.flatten_callback:
                try:
                    await self.flatten_callback(reason, trigger_type)
                    
                    await self._log_risk_event(
                        trigger_type,
                        RiskStatus.EMERGENCY,
                        "Auto-flatten executed successfully",
                        "flatten_executed"
                    )
                    
                except Exception as e:
                    await self._log_risk_event(
                        trigger_type,
                        RiskStatus.EMERGENCY,
                        f"Auto-flatten failed: {e}",
                        "flatten_failed"
                    )
                    raise
            else:
                self.logger.error("No flatten callback registered!")
            
            # Send alert if callback is registered
            if self.alert_callback:
                await self.alert_callback(
                    "CRITICAL: Auto-flatten triggered",
                    f"Daily P&L: ₹{self.daily_pnl:,.0f}\nReason: {reason}",
                    "critical"
                )
            
        except Exception as e:
            self.logger.error(f"Error in auto-flatten: {e}")
            self.is_flatten_in_progress = False
            raise
    
    async def check_position_limits(
        self,
        new_lots: int,
        strategy_name: str,
        current_positions: List[Dict]
    ) -> Tuple[bool, List[str]]:
        """
        Check if new position violates risk limits
        
        Args:
            new_lots: Number of lots for new position
            strategy_name: Name of strategy
            current_positions: List of current positions
            
        Returns:
            Tuple of (is_allowed, warnings)
        """
        try:
            warnings = []
            is_allowed = True
            
            # Check if trading is halted
            if self.is_trading_halted:
                warnings.append("Trading is halted due to risk limits")
                return False, warnings
            
            # Check daily P&L status
            if self.current_status in [RiskStatus.EMERGENCY, RiskStatus.LOCKED]:
                warnings.append(f"Trading blocked due to risk status: {self.current_status.value}")
                return False, warnings
            
            # Use risk calculator for position limit validation
            current_total_lots = sum(pos.get("lots", 0) for pos in current_positions)
            is_valid, calc_warnings = risk_calculator.validate_position_limits(
                new_lots, current_total_lots, strategy_name
            )
            
            if not is_valid:
                warnings.extend(calc_warnings)
                is_allowed = False
            
            # Check concentration risk
            if current_positions:
                portfolio_value = sum(abs(pos.get("market_value", 0)) for pos in current_positions)
                max_position_value = max(abs(pos.get("market_value", 0)) for pos in current_positions)
                
                if portfolio_value > 0:
                    concentration_pct = max_position_value / portfolio_value
                    if concentration_pct > self.limits.position_concentration_limit:
                        warnings.append(f"High concentration risk: {concentration_pct:.1%}")
                        if concentration_pct > 0.50:  # Hard limit at 50%
                            is_allowed = False
            
            # Warning for danger status
            if self.current_status == RiskStatus.DANGER:
                warnings.append("Trading in DANGER zone - position will be monitored closely")
            
            self.logger.debug(
                f"Position limit check for {strategy_name}: "
                f"{'ALLOWED' if is_allowed else 'BLOCKED'} - {new_lots} lots",
                extra={
                    "strategy": strategy_name,
                    "new_lots": new_lots,
                    "allowed": is_allowed,
                    "warnings": warnings,
                    "risk_status": self.current_status.value
                }
            )
            
            return is_allowed, warnings
            
        except Exception as e:
            self.logger.error(f"Error checking position limits: {e}")
            return False, [f"Position check error: {str(e)}"]
    
    async def manual_flatten_all(self, reason: str = "Manual override"):
        """
        Manually trigger flatten all positions
        
        Args:
            reason: Reason for manual flatten
        """
        try:
            await self._trigger_auto_flatten(StopLossType.MANUAL, f"Manual flatten: {reason}")
            
        except Exception as e:
            self.logger.error(f"Error in manual flatten: {e}")
            raise
    
    async def emergency_stop(self, reason: str = "Emergency stop"):
        """
        Emergency stop all trading activity
        
        Args:
            reason: Reason for emergency stop
        """
        try:
            self.is_trading_halted = True
            self.current_status = RiskStatus.EMERGENCY
            
            await self._log_risk_event(
                StopLossType.EMERGENCY,
                RiskStatus.EMERGENCY,
                reason,
                "emergency_stop"
            )
            
            # Trigger flatten
            await self._trigger_auto_flatten(StopLossType.EMERGENCY, reason)
            
            self.logger.critical(f"🚨 EMERGENCY STOP: {reason}")
            
        except Exception as e:
            self.logger.error(f"Error in emergency stop: {e}")
            raise
    
    async def reset_trading_halt(self, reason: str = "Manual reset"):
        """
        Reset trading halt (use with caution)
        
        Args:
            reason: Reason for reset
        """
        try:
            if self.current_status == RiskStatus.EMERGENCY:
                self.logger.warning("Cannot reset from EMERGENCY status automatically")
                return False
            
            self.is_trading_halted = False
            self.is_flatten_in_progress = False
            
            await self._log_risk_event(
                StopLossType.MANUAL,
                RiskStatus.WARNING,
                f"Trading halt reset: {reason}",
                "trading_resumed"
            )
            
            self.logger.warning(f"Trading halt reset: {reason}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resetting trading halt: {e}")
            return False
    
    async def _log_risk_event(
        self,
        event_type: StopLossType,
        severity: RiskStatus,
        description: str,
        action: str,
        strategy_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log risk event for audit and monitoring"""
        try:
            event = RiskEvent(
                timestamp=datetime.now(timezone.utc),
                event_type=event_type,
                severity=severity,
                description=description,
                current_pnl=self.daily_pnl,
                action_taken=action,
                position_count=0,  # Will be updated by caller if needed
                strategy_name=strategy_name,
                metadata=metadata or {}
            )
            
            self.risk_events.append(event)
            
            # Persist to Redis (keep last 100 events)
            events_data = [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type.value,
                    "severity": e.severity.value,
                    "description": e.description,
                    "current_pnl": e.current_pnl,
                    "action_taken": e.action_taken,
                    "strategy_name": e.strategy_name,
                    "metadata": e.metadata
                }
                for e in self.risk_events[-100:]
            ]
            
            await redis_client.set(
                self.risk_events_key,
                json.dumps(events_data),
                ex=86400 * 7  # Keep for 7 days
            )
            
        except Exception as e:
            self.logger.error(f"Error logging risk event: {e}")
    
    def register_flatten_callback(self, callback: Callable):
        """Register callback for auto-flatten execution"""
        self.flatten_callback = callback
        self.logger.info("Flatten callback registered")
    
    def register_alert_callback(self, callback: Callable):
        """Register callback for risk alerts"""
        self.alert_callback = callback
        self.logger.info("Alert callback registered")
    
    def register_position_callback(self, callback: Callable):
        """Register callback for position updates"""
        self.position_callback = callback
        self.logger.info("Position callback registered")
    
    async def get_risk_summary(self) -> Dict[str, Any]:
        """Get current risk summary"""
        try:
            return {
                "status": self.current_status.value,
                "daily_pnl": self.daily_pnl,
                "daily_loss_limit": self.limits.daily_loss_limit,
                "utilization_pct": abs(self.daily_pnl) / self.limits.daily_loss_limit * 100,
                "is_trading_halted": self.is_trading_halted,
                "is_flatten_in_progress": self.is_flatten_in_progress,
                "limits": self.limits.__dict__,
                "last_update": self.last_risk_check.isoformat(),
                "recent_events": len(self.risk_events)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting risk summary: {e}")
            return {"error": str(e)}


# Global instance
risk_manager = RiskManager() 