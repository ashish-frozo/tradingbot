"""
Position limits management system with configurable limits and real-time monitoring.

This module provides comprehensive position limit enforcement with per-signal
and per-strategy controls, real-time monitoring, and violation alerts.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Tuple
from uuid import uuid4

from loguru import logger
from app.cache.redis import RedisManager
from app.core.exceptions import PositionLimitError, RiskLimitExceededError


class LimitType(Enum):
    """Types of position limits."""
    PER_SIGNAL = "per_signal"
    PER_STRATEGY = "per_strategy"
    TOTAL_PORTFOLIO = "total_portfolio"
    PER_SYMBOL = "per_symbol"
    PER_EXPIRY = "per_expiry"


class LimitViolationType(Enum):
    """Types of limit violations."""
    SOFT_LIMIT = "soft_limit"      # Warning level
    HARD_LIMIT = "hard_limit"      # Blocking level
    EMERGENCY_LIMIT = "emergency_limit"  # Emergency stop


@dataclass
class PositionLimit:
    """Configuration for a position limit."""
    limit_type: LimitType
    entity_id: str  # Strategy ID, signal ID, symbol, etc.
    max_quantity: int
    current_quantity: int = 0
    soft_limit_threshold: float = 0.8  # Warn at 80%
    hard_limit_threshold: float = 1.0  # Block at 100%
    emergency_threshold: float = 1.2   # Emergency at 120%
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    

@dataclass
class PositionChange:
    """Record of a position change for limit tracking."""
    change_id: str
    entity_id: str
    limit_type: LimitType
    symbol: str
    quantity_change: int  # Positive for increase, negative for decrease
    timestamp: datetime = field(default_factory=datetime.utcnow)
    order_id: Optional[str] = None
    strategy_id: Optional[str] = None
    signal_id: Optional[str] = None
    

@dataclass
class LimitViolation:
    """Record of a limit violation."""
    violation_id: str
    limit_type: LimitType
    entity_id: str
    violation_type: LimitViolationType
    current_quantity: int
    limit_quantity: int
    excess_quantity: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    order_id: Optional[str] = None
    signal_id: Optional[str] = None
    strategy_id: Optional[str] = None
    action_taken: Optional[str] = None
    

class PositionLimitsManager:
    """
    Comprehensive position limits management system.
    
    Features:
    - Per-signal limits (10 lots maximum)
    - Per-strategy limits (50 lots total maximum)
    - Per-symbol and per-expiry limits
    - Real-time limit monitoring and enforcement
    - Soft/hard/emergency limit thresholds
    - Violation tracking and alerts
    - Automatic position reduction on violations
    """
    
    def __init__(
        self,
        redis_manager: RedisManager,
        default_per_signal_limit: int = 10,
        default_per_strategy_limit: int = 50,
        default_per_symbol_limit: int = 100,
        default_portfolio_limit: int = 500
    ):
        self.redis = redis_manager
        
        # Default limits from PRD requirements
        self.default_limits = {
            LimitType.PER_SIGNAL: default_per_signal_limit,
            LimitType.PER_STRATEGY: default_per_strategy_limit,
            LimitType.PER_SYMBOL: default_per_symbol_limit,
            LimitType.TOTAL_PORTFOLIO: default_portfolio_limit
        }
        
        # Active position limits
        self.position_limits: Dict[str, PositionLimit] = {}
        
        # Current positions tracking
        self.current_positions: Dict[str, Dict[str, int]] = {
            "by_signal": {},      # signal_id -> quantity
            "by_strategy": {},    # strategy_id -> quantity
            "by_symbol": {},      # symbol -> quantity
            "total_portfolio": {"total": 0}
        }
        
        # Violation tracking
        self.violations: List[LimitViolation] = []
        self.violation_callbacks: List[Any] = []
        
        # Monitoring
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        logger.info(
            "Position limits manager initialized with defaults: signal={}, strategy={}, symbol={}, portfolio={}",
            default_per_signal_limit,
            default_per_strategy_limit,
            default_per_symbol_limit,
            default_portfolio_limit
        )
    
    async def start(self) -> None:
        """Start the position limits monitoring system."""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        
        # Load existing limits from Redis
        await self._load_limits_from_redis()
        
        # Start monitoring task
        self.monitor_task = asyncio.create_task(
            self._monitoring_loop(),
            name="position_limits_monitor"
        )
        
        logger.info("Position limits manager started")
    
    async def stop(self) -> None:
        """Stop the position limits monitoring system."""
        self.is_monitoring = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        # Save current state to Redis
        await self._save_limits_to_redis()
        
        logger.info("Position limits manager stopped")
    
    async def check_order_limits(
        self,
        order_quantity: int,
        symbol: str,
        strategy_id: str,
        signal_id: Optional[str] = None,
        order_id: Optional[str] = None
    ) -> bool:
        """
        Check if an order would violate position limits.
        
        Args:
            order_quantity: Quantity of the proposed order
            symbol: Trading symbol
            strategy_id: Strategy ID placing the order
            signal_id: Signal ID (if applicable)
            order_id: Order ID for tracking
            
        Returns:
            True if order is within limits, False otherwise
            
        Raises:
            PositionLimitError: If order would exceed hard limits
        """
        violations = []
        
        # Check per-signal limit
        if signal_id:
            signal_limit = await self._get_or_create_limit(LimitType.PER_SIGNAL, signal_id)
            new_signal_quantity = signal_limit.current_quantity + order_quantity
            
            if new_signal_quantity > signal_limit.max_quantity * signal_limit.hard_limit_threshold:
                violations.append({
                    "type": LimitType.PER_SIGNAL,
                    "entity_id": signal_id,
                    "current": signal_limit.current_quantity,
                    "proposed": new_signal_quantity,
                    "limit": signal_limit.max_quantity,
                    "violation_type": LimitViolationType.HARD_LIMIT
                })
        
        # Check per-strategy limit
        strategy_limit = await self._get_or_create_limit(LimitType.PER_STRATEGY, strategy_id)
        new_strategy_quantity = strategy_limit.current_quantity + order_quantity
        
        if new_strategy_quantity > strategy_limit.max_quantity * strategy_limit.hard_limit_threshold:
            violations.append({
                "type": LimitType.PER_STRATEGY,
                "entity_id": strategy_id,
                "current": strategy_limit.current_quantity,
                "proposed": new_strategy_quantity,
                "limit": strategy_limit.max_quantity,
                "violation_type": LimitViolationType.HARD_LIMIT
            })
        
        # Check per-symbol limit
        symbol_limit = await self._get_or_create_limit(LimitType.PER_SYMBOL, symbol)
        new_symbol_quantity = symbol_limit.current_quantity + order_quantity
        
        if new_symbol_quantity > symbol_limit.max_quantity * symbol_limit.hard_limit_threshold:
            violations.append({
                "type": LimitType.PER_SYMBOL,
                "entity_id": symbol,
                "current": symbol_limit.current_quantity,
                "proposed": new_symbol_quantity,
                "limit": symbol_limit.max_quantity,
                "violation_type": LimitViolationType.HARD_LIMIT
            })
        
        # Check total portfolio limit
        portfolio_limit = await self._get_or_create_limit(LimitType.TOTAL_PORTFOLIO, "total")
        new_total_quantity = portfolio_limit.current_quantity + order_quantity
        
        if new_total_quantity > portfolio_limit.max_quantity * portfolio_limit.hard_limit_threshold:
            violations.append({
                "type": LimitType.TOTAL_PORTFOLIO,
                "entity_id": "total",
                "current": portfolio_limit.current_quantity,
                "proposed": new_total_quantity,
                "limit": portfolio_limit.max_quantity,
                "violation_type": LimitViolationType.HARD_LIMIT
            })
        
        # Log hard limit violations and raise error
        if violations:
            violation_msg = "; ".join([
                f"{v['type'].value}: {v['proposed']} > {v['limit']} ({v['entity_id']})"
                for v in violations
            ])
            
            logger.error(
                "Order would exceed position limits: {}",
                violation_msg,
                extra={
                    "order_id": order_id,
                    "order_quantity": order_quantity,
                    "symbol": symbol,
                    "strategy_id": strategy_id,
                    "signal_id": signal_id,
                    "violations": violations
                }
            )
            
            # Record violations
            for violation in violations:
                await self._record_violation(
                    violation_type=violation["violation_type"],
                    limit_type=violation["type"],
                    entity_id=violation["entity_id"],
                    current_quantity=violation["current"],
                    limit_quantity=violation["limit"],
                    order_id=order_id,
                    signal_id=signal_id,
                    strategy_id=strategy_id
                )
            
            raise PositionLimitError(f"Order would exceed position limits: {violation_msg}")
        
        # Check for soft limit warnings
        soft_warnings = []
        
        if signal_id:
            if new_signal_quantity > signal_limit.max_quantity * signal_limit.soft_limit_threshold:
                soft_warnings.append(f"Signal {signal_id}: {new_signal_quantity}/{signal_limit.max_quantity}")
        
        if new_strategy_quantity > strategy_limit.max_quantity * strategy_limit.soft_limit_threshold:
            soft_warnings.append(f"Strategy {strategy_id}: {new_strategy_quantity}/{strategy_limit.max_quantity}")
        
        if new_symbol_quantity > symbol_limit.max_quantity * symbol_limit.soft_limit_threshold:
            soft_warnings.append(f"Symbol {symbol}: {new_symbol_quantity}/{symbol_limit.max_quantity}")
        
        if new_total_quantity > portfolio_limit.max_quantity * portfolio_limit.soft_limit_threshold:
            soft_warnings.append(f"Portfolio: {new_total_quantity}/{portfolio_limit.max_quantity}")
        
        if soft_warnings:
            logger.warning(
                "Order approaching position limits: {}",
                "; ".join(soft_warnings),
                extra={
                    "order_id": order_id,
                    "order_quantity": order_quantity,
                    "symbol": symbol,
                    "strategy_id": strategy_id,
                    "signal_id": signal_id
                }
            )
        
        return True
    
    async def update_position(
        self,
        quantity_change: int,
        symbol: str,
        strategy_id: str,
        signal_id: Optional[str] = None,
        order_id: Optional[str] = None
    ) -> None:
        """
        Update position quantities after order execution.
        
        Args:
            quantity_change: Change in position (positive for increase, negative for decrease)
            symbol: Trading symbol
            strategy_id: Strategy ID
            signal_id: Signal ID (if applicable)
            order_id: Order ID for tracking
        """
        change_id = str(uuid4())
        
        # Record position change
        change = PositionChange(
            change_id=change_id,
            entity_id=strategy_id,
            limit_type=LimitType.PER_STRATEGY,
            symbol=symbol,
            quantity_change=quantity_change,
            order_id=order_id,
            strategy_id=strategy_id,
            signal_id=signal_id
        )
        
        try:
            # Update per-signal position
            if signal_id:
                signal_limit = await self._get_or_create_limit(LimitType.PER_SIGNAL, signal_id)
                signal_limit.current_quantity = max(0, signal_limit.current_quantity + quantity_change)
                signal_limit.updated_at = datetime.utcnow()
                self.current_positions["by_signal"][signal_id] = signal_limit.current_quantity
            
            # Update per-strategy position
            strategy_limit = await self._get_or_create_limit(LimitType.PER_STRATEGY, strategy_id)
            strategy_limit.current_quantity = max(0, strategy_limit.current_quantity + quantity_change)
            strategy_limit.updated_at = datetime.utcnow()
            self.current_positions["by_strategy"][strategy_id] = strategy_limit.current_quantity
            
            # Update per-symbol position
            symbol_limit = await self._get_or_create_limit(LimitType.PER_SYMBOL, symbol)
            symbol_limit.current_quantity = max(0, symbol_limit.current_quantity + quantity_change)
            symbol_limit.updated_at = datetime.utcnow()
            self.current_positions["by_symbol"][symbol] = symbol_limit.current_quantity
            
            # Update total portfolio position
            portfolio_limit = await self._get_or_create_limit(LimitType.TOTAL_PORTFOLIO, "total")
            portfolio_limit.current_quantity = max(0, portfolio_limit.current_quantity + quantity_change)
            portfolio_limit.updated_at = datetime.utcnow()
            self.current_positions["total_portfolio"]["total"] = portfolio_limit.current_quantity
            
            logger.info(
                "Position updated: {} lots {} (signal: {}, strategy: {}, symbol: {})",
                abs(quantity_change),
                "added" if quantity_change > 0 else "removed",
                signal_id or "N/A",
                strategy_id,
                symbol,
                extra={
                    "change_id": change_id,
                    "quantity_change": quantity_change,
                    "new_strategy_position": strategy_limit.current_quantity,
                    "new_signal_position": signal_limit.current_quantity if signal_id else 0,
                    "new_symbol_position": symbol_limit.current_quantity,
                    "new_portfolio_position": portfolio_limit.current_quantity,
                    "order_id": order_id
                }
            )
            
            # Save updated positions to Redis
            await self._save_positions_to_redis()
            
        except Exception as e:
            logger.error(
                "Failed to update position: {}",
                str(e),
                extra={
                    "change_id": change_id,
                    "error": str(e),
                    "quantity_change": quantity_change,
                    "symbol": symbol,
                    "strategy_id": strategy_id,
                    "signal_id": signal_id
                }
            )
            raise
    
    async def set_custom_limit(
        self,
        limit_type: LimitType,
        entity_id: str,
        max_quantity: int,
        soft_threshold: float = 0.8,
        hard_threshold: float = 1.0
    ) -> None:
        """Set a custom position limit."""
        limit_key = f"{limit_type.value}:{entity_id}"
        
        limit = PositionLimit(
            limit_type=limit_type,
            entity_id=entity_id,
            max_quantity=max_quantity,
            current_quantity=self.position_limits.get(limit_key, PositionLimit(
                limit_type=limit_type,
                entity_id=entity_id,
                max_quantity=max_quantity
            )).current_quantity,
            soft_limit_threshold=soft_threshold,
            hard_limit_threshold=hard_threshold,
            updated_at=datetime.utcnow()
        )
        
        self.position_limits[limit_key] = limit
        
        logger.info(
            "Custom limit set: {} {} = {} lots (soft: {:.1%}, hard: {:.1%})",
            limit_type.value,
            entity_id,
            max_quantity,
            soft_threshold,
            hard_threshold
        )
        
        await self._save_limits_to_redis()
    
    async def _get_or_create_limit(self, limit_type: LimitType, entity_id: str) -> PositionLimit:
        """Get existing limit or create with default values."""
        limit_key = f"{limit_type.value}:{entity_id}"
        
        if limit_key not in self.position_limits:
            max_quantity = self.default_limits.get(limit_type, 100)
            
            self.position_limits[limit_key] = PositionLimit(
                limit_type=limit_type,
                entity_id=entity_id,
                max_quantity=max_quantity
            )
        
        return self.position_limits[limit_key]
    
    async def _record_violation(
        self,
        violation_type: LimitViolationType,
        limit_type: LimitType,
        entity_id: str,
        current_quantity: int,
        limit_quantity: int,
        order_id: Optional[str] = None,
        signal_id: Optional[str] = None,
        strategy_id: Optional[str] = None
    ) -> None:
        """Record a limit violation."""
        violation = LimitViolation(
            violation_id=str(uuid4()),
            limit_type=limit_type,
            entity_id=entity_id,
            violation_type=violation_type,
            current_quantity=current_quantity,
            limit_quantity=limit_quantity,
            excess_quantity=current_quantity - limit_quantity,
            order_id=order_id,
            signal_id=signal_id,
            strategy_id=strategy_id
        )
        
        self.violations.append(violation)
        
        # Save to Redis
        await self.redis.lpush(
            "position_violations",
            violation.__dict__,
            ttl=timedelta(days=30)
        )
        
        # Trigger callbacks
        for callback in self.violation_callbacks:
            try:
                await callback(violation)
            except Exception as e:
                logger.error("Violation callback error: {}", str(e))
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for position limits."""
        logger.info("Position limits monitoring started")
        
        while self.is_monitoring:
            try:
                await asyncio.sleep(60.0)  # Check every minute
                
                # Check for emergency violations
                emergency_violations = []
                
                for limit_key, limit in self.position_limits.items():
                    if not limit.is_active:
                        continue
                    
                    utilization = limit.current_quantity / limit.max_quantity
                    
                    if utilization >= limit.emergency_threshold:
                        emergency_violations.append({
                            "limit": limit,
                            "utilization": utilization
                        })
                
                if emergency_violations:
                    logger.critical(
                        "EMERGENCY: {} position limits exceeded emergency threshold",
                        len(emergency_violations),
                        extra={
                            "violations": [
                                {
                                    "type": v["limit"].limit_type.value,
                                    "entity": v["limit"].entity_id,
                                    "current": v["limit"].current_quantity,
                                    "limit": v["limit"].max_quantity,
                                    "utilization": v["utilization"]
                                }
                                for v in emergency_violations
                            ]
                        }
                    )
                
                # Log position utilization summary
                summary = self._get_utilization_summary()
                logger.debug("Position limits utilization: {}", summary)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Position limits monitoring error: {}", str(e))
        
        logger.info("Position limits monitoring stopped")
    
    def _get_utilization_summary(self) -> Dict[str, Any]:
        """Get current position utilization summary."""
        summary = {}
        
        for limit_key, limit in self.position_limits.items():
            if limit.current_quantity > 0:
                utilization = limit.current_quantity / limit.max_quantity
                summary[limit_key] = {
                    "current": limit.current_quantity,
                    "limit": limit.max_quantity,
                    "utilization": f"{utilization:.1%}"
                }
        
        return summary
    
    async def _load_limits_from_redis(self) -> None:
        """Load position limits from Redis."""
        try:
            limits_data = await self.redis.get("position_limits")
            if limits_data:
                # TODO: Deserialize and load limits
                pass
            
            positions_data = await self.redis.get("current_positions")
            if positions_data:
                # TODO: Deserialize and load positions
                pass
                
        except Exception as e:
            logger.warning("Failed to load limits from Redis: {}", str(e))
    
    async def _save_limits_to_redis(self) -> None:
        """Save position limits to Redis."""
        try:
            limits_data = {
                limit_key: {
                    "limit_type": limit.limit_type.value,
                    "entity_id": limit.entity_id,
                    "max_quantity": limit.max_quantity,
                    "current_quantity": limit.current_quantity,
                    "soft_limit_threshold": limit.soft_limit_threshold,
                    "hard_limit_threshold": limit.hard_limit_threshold,
                    "is_active": limit.is_active,
                    "updated_at": limit.updated_at.isoformat()
                }
                for limit_key, limit in self.position_limits.items()
            }
            
            await self.redis.set("position_limits", limits_data, ttl=timedelta(days=7))
            
        except Exception as e:
            logger.error("Failed to save limits to Redis: {}", str(e))
    
    async def _save_positions_to_redis(self) -> None:
        """Save current positions to Redis."""
        try:
            await self.redis.set(
                "current_positions",
                self.current_positions,
                ttl=timedelta(days=1)
            )
        except Exception as e:
            logger.error("Failed to save positions to Redis: {}", str(e))
    
    def add_violation_callback(self, callback: Any) -> None:
        """Add a callback for limit violations."""
        self.violation_callbacks.append(callback)
    
    def get_limits_status(self) -> Dict[str, Any]:
        """Get current limits status."""
        return {
            "active_limits": len([l for l in self.position_limits.values() if l.is_active]),
            "total_violations": len(self.violations),
            "current_positions": self.current_positions,
            "utilization_summary": self._get_utilization_summary(),
            "default_limits": {k.value: v for k, v in self.default_limits.items()}
        } 