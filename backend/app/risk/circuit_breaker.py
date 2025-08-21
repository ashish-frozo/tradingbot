"""
Circuit Breaker System

Monitors market conditions and triggers circuit breakers when:
- India VIX exceeds +3σ from its rolling mean
- Market-wide circuit breakers are triggered
- Specific market events occur (RBI announcements, budget, etc.)
- Exchange halts or technical issues
"""

import asyncio
import statistics
from datetime import datetime, timezone, time, date
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import json
import math

from loguru import logger

from app.core.config import get_settings
from app.cache.redis import redis_client


class CircuitBreakerType(Enum):
    """Types of circuit breakers"""
    VIX_SPIKE = "vix_spike"
    MARKET_CIRCUIT = "market_circuit"
    SCHEDULED_EVENT = "scheduled_event"
    EXCHANGE_HALT = "exchange_halt"
    MANUAL = "manual"
    SYSTEM_ERROR = "system_error"


class CircuitBreakerStatus(Enum):
    """Circuit breaker status"""
    NORMAL = "normal"
    WARNING = "warning"
    TRIGGERED = "triggered"
    MANUAL_OVERRIDE = "manual_override"


class MarketEvent(Enum):
    """Known market events that trigger circuit breakers"""
    RBI_POLICY = "rbi_policy"
    BUDGET_DAY = "budget_day"
    US_CPI = "us_cpi"
    US_FOMC = "us_fomc"
    ELECTION_RESULTS = "election_results"
    MARKET_HOLIDAY = "market_holiday"
    QUARTERLY_EXPIRY = "quarterly_expiry"
    MONTHLY_EXPIRY = "monthly_expiry"


@dataclass
class VIXData:
    """VIX data point"""
    timestamp: datetime
    value: float
    source: str = "live"


@dataclass
class CircuitBreakerEvent:
    """Circuit breaker event record"""
    timestamp: datetime
    trigger_type: CircuitBreakerType
    severity: CircuitBreakerStatus
    description: str
    vix_value: Optional[float] = None
    vix_threshold: Optional[float] = None
    action_taken: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VIXStats:
    """VIX statistical measures"""
    current_value: float
    rolling_mean: float
    rolling_std: float
    z_score: float
    threshold_3sigma: float
    samples_count: int
    last_updated: datetime


class CircuitBreaker:
    """
    Circuit breaker system for market risk management
    
    Features:
    - India VIX monitoring with 3σ threshold
    - Market event detection and scheduled halts
    - Exchange circuit breaker monitoring
    - Manual override capabilities
    - Integration with risk manager
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logger.bind(module="circuit_breaker")
        
        # VIX monitoring configuration
        self.vix_window_size = 252  # 1 year of trading days for baseline
        self.vix_threshold_sigma = 3.0  # 3 standard deviations
        self.vix_buffer: deque = deque(maxlen=self.vix_window_size)
        
        # Circuit breaker state
        self.status = CircuitBreakerStatus.NORMAL
        self.active_breakers: Set[CircuitBreakerType] = set()
        self.last_vix_check = datetime.now(timezone.utc)
        self.events: List[CircuitBreakerEvent] = []
        
        # Market event calendar (hardcoded, can be moved to external source)
        self.scheduled_events = self._initialize_event_calendar()
        
        # Redis keys for persistence
        self.redis_prefix = "circuit_breaker"
        self.vix_data_key = f"{self.redis_prefix}:vix_data"
        self.status_key = f"{self.redis_prefix}:status"
        self.events_key = f"{self.redis_prefix}:events"
        
        # Callbacks
        self.halt_callback: Optional[Callable] = None
        self.alert_callback: Optional[Callable] = None
    
    def _initialize_event_calendar(self) -> Dict[date, MarketEvent]:
        """Initialize known market events calendar"""
        # This would typically be loaded from an external calendar
        # For now, including some fixed dates as examples
        current_year = datetime.now().year
        
        events = {
            # RBI Policy dates (typical months)
            date(current_year, 2, 8): MarketEvent.RBI_POLICY,
            date(current_year, 4, 6): MarketEvent.RBI_POLICY,
            date(current_year, 6, 8): MarketEvent.RBI_POLICY,
            date(current_year, 8, 10): MarketEvent.RBI_POLICY,
            date(current_year, 10, 9): MarketEvent.RBI_POLICY,
            date(current_year, 12, 8): MarketEvent.RBI_POLICY,
            
            # Budget day (typically February 1)
            date(current_year, 2, 1): MarketEvent.BUDGET_DAY,
            
            # Quarterly expiry dates (last Thursday of Mar, Jun, Sep, Dec)
            date(current_year, 3, 28): MarketEvent.QUARTERLY_EXPIRY,
            date(current_year, 6, 27): MarketEvent.QUARTERLY_EXPIRY,
            date(current_year, 9, 26): MarketEvent.QUARTERLY_EXPIRY,
            date(current_year, 12, 26): MarketEvent.QUARTERLY_EXPIRY,
        }
        
        return events
    
    async def initialize(self):
        """Initialize circuit breaker system"""
        try:
            # Load persisted VIX data
            stored_vix = await redis_client.get(self.vix_data_key)
            if stored_vix:
                vix_data = json.loads(stored_vix)
                for item in vix_data:
                    self.vix_buffer.append(VIXData(
                        timestamp=datetime.fromisoformat(item["timestamp"]),
                        value=item["value"],
                        source=item.get("source", "stored")
                    ))
            
            # Load status
            stored_status = await redis_client.get(self.status_key)
            if stored_status:
                self.status = CircuitBreakerStatus(stored_status)
            
            # Check for today's scheduled events
            await self._check_scheduled_events()
            
            self.logger.info(
                f"Circuit breaker initialized: Status={self.status.value}, "
                f"VIX samples={len(self.vix_buffer)}",
                extra={
                    "status": self.status.value,
                    "vix_samples": len(self.vix_buffer),
                    "active_breakers": [b.value for b in self.active_breakers]
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error initializing circuit breaker: {e}")
            raise
    
    async def update_vix(self, vix_value: float, source: str = "live"):
        """
        Update VIX value and check for circuit breaker triggers
        
        Args:
            vix_value: Current VIX value
            source: Source of VIX data (live, feed, manual)
        """
        try:
            # Add to buffer
            vix_data = VIXData(
                timestamp=datetime.now(timezone.utc),
                value=vix_value,
                source=source
            )
            self.vix_buffer.append(vix_data)
            
            # Calculate statistics if we have enough data
            if len(self.vix_buffer) >= 30:  # Minimum 30 samples for meaningful stats
                stats = self._calculate_vix_stats()
                
                # Check for circuit breaker trigger
                await self._check_vix_circuit_breaker(stats)
                
                # Persist VIX data
                await self._persist_vix_data()
                
                self.logger.debug(
                    f"VIX updated: {vix_value:.2f} (Z-score: {stats.z_score:.2f}, "
                    f"Threshold: {stats.threshold_3sigma:.2f})",
                    extra={
                        "vix_value": vix_value,
                        "z_score": stats.z_score,
                        "threshold": stats.threshold_3sigma,
                        "samples": len(self.vix_buffer)
                    }
                )
            else:
                self.logger.debug(f"VIX updated: {vix_value:.2f} (insufficient data for stats)")
            
            self.last_vix_check = datetime.now(timezone.utc)
            
        except Exception as e:
            self.logger.error(f"Error updating VIX: {e}")
    
    def _calculate_vix_stats(self) -> VIXStats:
        """Calculate VIX statistics for circuit breaker evaluation"""
        try:
            values = [item.value for item in self.vix_buffer]
            current_value = values[-1]
            
            # Calculate rolling statistics
            rolling_mean = statistics.mean(values)
            rolling_std = statistics.stdev(values) if len(values) > 1 else 0
            
            # Calculate Z-score
            z_score = (current_value - rolling_mean) / rolling_std if rolling_std > 0 else 0
            
            # Calculate threshold
            threshold_3sigma = rolling_mean + (self.vix_threshold_sigma * rolling_std)
            
            return VIXStats(
                current_value=current_value,
                rolling_mean=rolling_mean,
                rolling_std=rolling_std,
                z_score=z_score,
                threshold_3sigma=threshold_3sigma,
                samples_count=len(values),
                last_updated=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating VIX stats: {e}")
            # Return safe defaults
            return VIXStats(
                current_value=self.vix_buffer[-1].value if self.vix_buffer else 0,
                rolling_mean=0,
                rolling_std=0,
                z_score=0,
                threshold_3sigma=0,
                samples_count=len(self.vix_buffer),
                last_updated=datetime.now(timezone.utc)
            )
    
    async def _check_vix_circuit_breaker(self, stats: VIXStats):
        """Check if VIX breach triggers circuit breaker"""
        try:
            # Check if VIX exceeds 3 sigma threshold
            if stats.z_score >= self.vix_threshold_sigma:
                if CircuitBreakerType.VIX_SPIKE not in self.active_breakers:
                    await self._trigger_circuit_breaker(
                        CircuitBreakerType.VIX_SPIKE,
                        f"VIX spike detected: {stats.current_value:.2f} "
                        f"(Z-score: {stats.z_score:.2f}, Threshold: {stats.threshold_3sigma:.2f})",
                        {
                            "vix_value": stats.current_value,
                            "z_score": stats.z_score,
                            "threshold": stats.threshold_3sigma,
                            "rolling_mean": stats.rolling_mean,
                            "rolling_std": stats.rolling_std
                        }
                    )
            else:
                # VIX is back to normal, clear the breaker if active
                if CircuitBreakerType.VIX_SPIKE in self.active_breakers:
                    await self._clear_circuit_breaker(
                        CircuitBreakerType.VIX_SPIKE,
                        f"VIX normalized: {stats.current_value:.2f} (Z-score: {stats.z_score:.2f})"
                    )
            
        except Exception as e:
            self.logger.error(f"Error checking VIX circuit breaker: {e}")
    
    async def _check_scheduled_events(self):
        """Check for scheduled market events today"""
        try:
            today = datetime.now(timezone.utc).date()
            
            if today in self.scheduled_events:
                event = self.scheduled_events[today]
                
                if CircuitBreakerType.SCHEDULED_EVENT not in self.active_breakers:
                    await self._trigger_circuit_breaker(
                        CircuitBreakerType.SCHEDULED_EVENT,
                        f"Scheduled market event: {event.value}",
                        {"event_type": event.value, "date": today.isoformat()}
                    )
            
        except Exception as e:
            self.logger.error(f"Error checking scheduled events: {e}")
    
    async def manual_circuit_breaker(self, reason: str, duration_minutes: int = 60):
        """
        Manually trigger circuit breaker
        
        Args:
            reason: Reason for manual circuit breaker
            duration_minutes: Duration in minutes (0 = indefinite)
        """
        try:
            await self._trigger_circuit_breaker(
                CircuitBreakerType.MANUAL,
                f"Manual circuit breaker: {reason}",
                {"duration_minutes": duration_minutes, "reason": reason}
            )
            
            # Schedule auto-clear if duration is specified
            if duration_minutes > 0:
                asyncio.create_task(self._auto_clear_manual_breaker(duration_minutes))
            
        except Exception as e:
            self.logger.error(f"Error in manual circuit breaker: {e}")
            raise
    
    async def _auto_clear_manual_breaker(self, duration_minutes: int):
        """Auto-clear manual circuit breaker after duration"""
        try:
            await asyncio.sleep(duration_minutes * 60)
            
            if CircuitBreakerType.MANUAL in self.active_breakers:
                await self._clear_circuit_breaker(
                    CircuitBreakerType.MANUAL,
                    f"Manual circuit breaker auto-cleared after {duration_minutes} minutes"
                )
            
        except Exception as e:
            self.logger.error(f"Error auto-clearing manual breaker: {e}")
    
    async def force_market_halt(self, reason: str):
        """
        Force immediate market halt (use in emergencies)
        
        Args:
            reason: Reason for forced halt
        """
        try:
            await self._trigger_circuit_breaker(
                CircuitBreakerType.EXCHANGE_HALT,
                f"Forced market halt: {reason}",
                {"emergency": True, "reason": reason}
            )
            
        except Exception as e:
            self.logger.error(f"Error in forced market halt: {e}")
            raise
    
    async def _trigger_circuit_breaker(
        self,
        breaker_type: CircuitBreakerType,
        description: str,
        metadata: Optional[Dict] = None
    ):
        """
        Trigger a circuit breaker
        
        Args:
            breaker_type: Type of circuit breaker
            description: Description of the trigger
            metadata: Additional metadata
        """
        try:
            # Add to active breakers
            self.active_breakers.add(breaker_type)
            
            # Update status
            if breaker_type in [CircuitBreakerType.VIX_SPIKE, CircuitBreakerType.EXCHANGE_HALT]:
                self.status = CircuitBreakerStatus.TRIGGERED
            elif self.status == CircuitBreakerStatus.NORMAL:
                self.status = CircuitBreakerStatus.WARNING
            
            # Log event
            event = CircuitBreakerEvent(
                timestamp=datetime.now(timezone.utc),
                trigger_type=breaker_type,
                severity=self.status,
                description=description,
                vix_value=self.vix_buffer[-1].value if self.vix_buffer else None,
                action_taken="trading_halted",
                metadata=metadata or {}
            )
            
            self.events.append(event)
            await self._persist_events()
            
            # Execute halt callback
            if self.halt_callback:
                await self.halt_callback(breaker_type, description)
            
            # Send alert
            if self.alert_callback:
                await self.alert_callback(
                    f"🚨 CIRCUIT BREAKER: {breaker_type.value.upper()}",
                    description,
                    "critical"
                )
            
            self.logger.critical(
                f"🚨 CIRCUIT BREAKER TRIGGERED: {breaker_type.value} - {description}",
                extra={
                    "breaker_type": breaker_type.value,
                    "description": description,
                    "status": self.status.value,
                    "active_breakers": [b.value for b in self.active_breakers],
                    "metadata": metadata
                }
            )
            
            # Persist status
            await redis_client.set(self.status_key, self.status.value)
            
        except Exception as e:
            self.logger.error(f"Error triggering circuit breaker: {e}")
            raise
    
    async def _clear_circuit_breaker(
        self,
        breaker_type: CircuitBreakerType,
        description: str
    ):
        """
        Clear a circuit breaker
        
        Args:
            breaker_type: Type of circuit breaker to clear
            description: Description of the clearing
        """
        try:
            # Remove from active breakers
            self.active_breakers.discard(breaker_type)
            
            # Update status
            if not self.active_breakers:
                self.status = CircuitBreakerStatus.NORMAL
            elif CircuitBreakerType.VIX_SPIKE not in self.active_breakers:
                self.status = CircuitBreakerStatus.WARNING
            
            # Log event
            event = CircuitBreakerEvent(
                timestamp=datetime.now(timezone.utc),
                trigger_type=breaker_type,
                severity=self.status,
                description=f"CLEARED: {description}",
                vix_value=self.vix_buffer[-1].value if self.vix_buffer else None,
                action_taken="trading_resumed"
            )
            
            self.events.append(event)
            await self._persist_events()
            
            self.logger.warning(
                f"Circuit breaker cleared: {breaker_type.value} - {description}",
                extra={
                    "breaker_type": breaker_type.value,
                    "description": description,
                    "status": self.status.value,
                    "active_breakers": [b.value for b in self.active_breakers]
                }
            )
            
            # Persist status
            await redis_client.set(self.status_key, self.status.value)
            
        except Exception as e:
            self.logger.error(f"Error clearing circuit breaker: {e}")
    
    async def clear_all_breakers(self, reason: str = "Manual override"):
        """
        Clear all active circuit breakers (emergency override)
        
        Args:
            reason: Reason for clearing all breakers
        """
        try:
            breakers_to_clear = list(self.active_breakers)
            
            for breaker in breakers_to_clear:
                await self._clear_circuit_breaker(breaker, f"Override: {reason}")
            
            self.status = CircuitBreakerStatus.MANUAL_OVERRIDE
            await redis_client.set(self.status_key, self.status.value)
            
            self.logger.warning(f"All circuit breakers cleared: {reason}")
            
        except Exception as e:
            self.logger.error(f"Error clearing all breakers: {e}")
            raise
    
    def is_trading_allowed(self) -> Tuple[bool, List[str]]:
        """
        Check if trading is allowed based on circuit breaker status
        
        Returns:
            Tuple of (is_allowed, reasons_if_blocked)
        """
        try:
            if not self.active_breakers:
                return True, []
            
            blocking_breakers = [
                CircuitBreakerType.VIX_SPIKE,
                CircuitBreakerType.EXCHANGE_HALT,
                CircuitBreakerType.MARKET_CIRCUIT
            ]
            
            blocked_by = [
                breaker.value for breaker in self.active_breakers
                if breaker in blocking_breakers
            ]
            
            if blocked_by:
                return False, blocked_by
            
            # Warning breakers allow trading but with caution
            warning_breakers = [breaker.value for breaker in self.active_breakers]
            return True, warning_breakers
            
        except Exception as e:
            self.logger.error(f"Error checking trading allowance: {e}")
            return False, ["Circuit breaker check error"]
    
    async def _persist_vix_data(self):
        """Persist VIX data to Redis"""
        try:
            # Keep last 1000 data points
            data_to_store = list(self.vix_buffer)[-1000:]
            serializable_data = [
                {
                    "timestamp": item.timestamp.isoformat(),
                    "value": item.value,
                    "source": item.source
                }
                for item in data_to_store
            ]
            
            await redis_client.set(
                self.vix_data_key,
                json.dumps(serializable_data),
                ex=86400 * 7  # Keep for 7 days
            )
            
        except Exception as e:
            self.logger.error(f"Error persisting VIX data: {e}")
    
    async def _persist_events(self):
        """Persist circuit breaker events to Redis"""
        try:
            # Keep last 100 events
            events_to_store = self.events[-100:]
            serializable_events = [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "trigger_type": event.trigger_type.value,
                    "severity": event.severity.value,
                    "description": event.description,
                    "vix_value": event.vix_value,
                    "vix_threshold": event.vix_threshold,
                    "action_taken": event.action_taken,
                    "metadata": event.metadata
                }
                for event in events_to_store
            ]
            
            await redis_client.set(
                self.events_key,
                json.dumps(serializable_events),
                ex=86400 * 30  # Keep for 30 days
            )
            
        except Exception as e:
            self.logger.error(f"Error persisting events: {e}")
    
    def register_halt_callback(self, callback: Callable):
        """Register callback for trading halt"""
        self.halt_callback = callback
        self.logger.info("Halt callback registered")
    
    def register_alert_callback(self, callback: Callable):
        """Register callback for alerts"""
        self.alert_callback = callback
        self.logger.info("Alert callback registered")
    
    async def get_status_summary(self) -> Dict[str, Any]:
        """Get current circuit breaker status summary"""
        try:
            vix_stats = None
            if len(self.vix_buffer) >= 30:
                vix_stats = self._calculate_vix_stats()
            
            trading_allowed, reasons = self.is_trading_allowed()
            
            return {
                "status": self.status.value,
                "trading_allowed": trading_allowed,
                "blocking_reasons": reasons,
                "active_breakers": [b.value for b in self.active_breakers],
                "vix_stats": {
                    "current": vix_stats.current_value if vix_stats else None,
                    "z_score": vix_stats.z_score if vix_stats else None,
                    "threshold": vix_stats.threshold_3sigma if vix_stats else None,
                    "samples": len(self.vix_buffer)
                },
                "last_vix_update": self.last_vix_check.isoformat(),
                "recent_events": len(self.events),
                "scheduled_events_today": len([
                    event for event_date, event in self.scheduled_events.items()
                    if event_date == datetime.now(timezone.utc).date()
                ])
            }
            
        except Exception as e:
            self.logger.error(f"Error getting status summary: {e}")
            return {"error": str(e)}


# Global instance  
circuit_breaker = CircuitBreaker() 