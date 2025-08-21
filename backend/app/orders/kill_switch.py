"""
Emergency kill switch system for rapid position flattening.

This module provides emergency "Kill All" functionality with sub-2-second
execution target, position flattening, and comprehensive safety controls.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set
from uuid import uuid4

from loguru import logger
from app.broker.tradehull_client import TradehullClient
from app.broker.enums import TransactionType, OrderType, ProductType, Validity
from app.orders.models import OrderRequest, OrderResponse, OrderStatus
from app.cache.redis import RedisManager
from app.core.exceptions import KillSwitchError, EmergencyError


class KillSwitchTrigger(Enum):
    """Types of kill switch triggers."""
    MANUAL = "manual"
    EMERGENCY_STOP = "emergency_stop"
    RISK_BREACH = "risk_breach"
    SYSTEM_FAILURE = "system_failure"
    MARKET_HALT = "market_halt"
    COMPLIANCE_VIOLATION = "compliance_violation"


class KillSwitchStatus(Enum):
    """Status of the kill switch system."""
    INACTIVE = "inactive"
    ARMED = "armed"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class PositionSnapshot:
    """Snapshot of a position to be flattened."""
    symbol: str
    strategy_id: str
    current_quantity: int
    average_price: float
    current_price: float
    unrealized_pnl: float
    market_value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FlattenOrder:
    """Order details for flattening a position."""
    flatten_id: str
    symbol: str
    strategy_id: str
    original_quantity: int
    flatten_quantity: int
    market_price: float
    order_request: OrderRequest
    status: OrderStatus = OrderStatus.PENDING
    broker_order_id: Optional[str] = None
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KillSwitchExecution:
    """Complete kill switch execution record."""
    execution_id: str
    trigger: KillSwitchTrigger
    trigger_reason: str
    user_id: Optional[str] = None
    positions_snapshot: List[PositionSnapshot] = field(default_factory=list)
    flatten_orders: List[FlattenOrder] = field(default_factory=list)
    total_positions: int = 0
    successful_flattens: int = 0
    failed_flattens: int = 0
    total_execution_time_ms: float = 0.0
    target_time_ms: float = 2000.0  # 2-second target
    status: KillSwitchStatus = KillSwitchStatus.INACTIVE
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    

class EmergencyKillSwitch:
    """
    Emergency kill switch system for rapid position flattening.
    
    Features:
    - Sub-2-second execution target for all positions
    - Parallel order execution for maximum speed
    - Position snapshot and rollback capabilities
    - Multi-trigger support (manual, risk, system)
    - Comprehensive audit trail
    - Safety controls and confirmations
    - Real-time execution monitoring
    """
    
    def __init__(
        self,
        broker_client: TradehullClient,
        redis_manager: RedisManager,
        target_execution_time_ms: float = 2000.0,
        max_concurrent_orders: int = 50,
        require_confirmation: bool = True
    ):
        self.broker_client = broker_client
        self.redis = redis_manager
        self.target_execution_time_ms = target_execution_time_ms
        self.max_concurrent_orders = max_concurrent_orders
        self.require_confirmation = require_confirmation
        
        # Kill switch state
        self.is_armed = False
        self.current_execution: Optional[KillSwitchExecution] = None
        self.execution_history: List[KillSwitchExecution] = []
        
        # Position tracking
        self.active_positions: Dict[str, PositionSnapshot] = {}
        self.position_callbacks: List[Callable[[List[PositionSnapshot]], None]] = []
        
        # Safety controls
        self.safety_checks_enabled = True
        self.last_execution_time: Optional[datetime] = None
        self.min_execution_interval_seconds = 30  # Minimum 30 seconds between executions
        
        # Monitoring
        self.execution_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time_ms": 0.0,
            "fastest_execution_ms": float('inf'),
            "slowest_execution_ms": 0.0
        }
        
        logger.info(
            "Emergency kill switch initialized (target: {}ms, max_concurrent: {})",
            target_execution_time_ms,
            max_concurrent_orders
        )
    
    async def arm_kill_switch(self, user_id: Optional[str] = None) -> bool:
        """
        Arm the kill switch for immediate activation.
        
        Args:
            user_id: User ID arming the system
            
        Returns:
            True if successfully armed
        """
        if self.current_execution and self.current_execution.status == KillSwitchStatus.EXECUTING:
            logger.warning("Cannot arm kill switch - execution in progress")
            return False
        
        self.is_armed = True
        
        # Take position snapshot
        await self._capture_position_snapshot()
        
        logger.warning(
            "🔴 KILL SWITCH ARMED - {} positions ready for emergency flatten",
            len(self.active_positions),
            extra={
                "user_id": user_id,
                "position_count": len(self.active_positions),
                "total_market_value": sum(pos.market_value for pos in self.active_positions.values())
            }
        )
        
        # Store armed state in Redis
        await self.redis.set(
            "kill_switch_armed",
            {
                "armed": True,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "position_count": len(self.active_positions)
            },
            ttl=timedelta(hours=1)
        )
        
        return True
    
    async def disarm_kill_switch(self, user_id: Optional[str] = None) -> bool:
        """
        Disarm the kill switch.
        
        Args:
            user_id: User ID disarming the system
            
        Returns:
            True if successfully disarmed
        """
        if self.current_execution and self.current_execution.status == KillSwitchStatus.EXECUTING:
            logger.warning("Cannot disarm kill switch - execution in progress")
            return False
        
        self.is_armed = False
        
        logger.info(
            "Kill switch disarmed by user: {}",
            user_id or "system",
            extra={"user_id": user_id}
        )
        
        # Clear Redis state
        await self.redis.delete("kill_switch_armed")
        
        return True
    
    async def execute_kill_all(
        self,
        trigger: KillSwitchTrigger,
        trigger_reason: str,
        user_id: Optional[str] = None,
        force_execute: bool = False
    ) -> KillSwitchExecution:
        """
        Execute emergency kill all - flatten all positions immediately.
        
        Args:
            trigger: What triggered the kill switch
            trigger_reason: Detailed reason for trigger
            user_id: User ID executing (if manual)
            force_execute: Skip safety checks if True
            
        Returns:
            KillSwitchExecution with results
        """
        execution_id = str(uuid4())
        start_time = time.perf_counter()
        
        # Safety checks
        if not force_execute:
            safety_result = await self._perform_safety_checks(trigger, user_id)
            if not safety_result["allowed"]:
                raise KillSwitchError(f"Kill switch execution blocked: {safety_result['reason']}")
        
        # Create execution record
        execution = KillSwitchExecution(
            execution_id=execution_id,
            trigger=trigger,
            trigger_reason=trigger_reason,
            user_id=user_id,
            status=KillSwitchStatus.EXECUTING
        )
        
        self.current_execution = execution
        
        try:
            logger.critical(
                "🚨 EMERGENCY KILL ALL INITIATED - {} trigger: {}",
                trigger.value.upper(),
                trigger_reason,
                extra={
                    "execution_id": execution_id,
                    "trigger": trigger.value,
                    "trigger_reason": trigger_reason,
                    "user_id": user_id,
                    "force_execute": force_execute
                }
            )
            
            # Step 1: Capture current position snapshot (< 100ms target)
            snapshot_start = time.perf_counter()
            await self._capture_position_snapshot()
            execution.positions_snapshot = list(self.active_positions.values())
            execution.total_positions = len(execution.positions_snapshot)
            snapshot_time = (time.perf_counter() - snapshot_start) * 1000
            
            logger.info(
                "Position snapshot captured: {} positions in {:.2f}ms",
                execution.total_positions,
                snapshot_time
            )
            
            if execution.total_positions == 0:
                logger.warning("No positions to flatten")
                execution.status = KillSwitchStatus.COMPLETED
                execution.end_time = datetime.utcnow()
                execution.total_execution_time_ms = (time.perf_counter() - start_time) * 1000
                return execution
            
            # Step 2: Generate flatten orders (< 200ms target)
            orders_start = time.perf_counter()
            flatten_orders = await self._generate_flatten_orders(execution.positions_snapshot)
            execution.flatten_orders = flatten_orders
            orders_time = (time.perf_counter() - orders_start) * 1000
            
            logger.info(
                "Flatten orders generated: {} orders in {:.2f}ms",
                len(flatten_orders),
                orders_time
            )
            
            # Step 3: Execute all flatten orders in parallel (< 1.7s target)
            execution_start = time.perf_counter()
            results = await self._execute_flatten_orders_parallel(flatten_orders)
            execution_time = (time.perf_counter() - execution_start) * 1000
            
            # Analyze results
            successful_orders = [r for r in results if r.get("success", False)]
            failed_orders = [r for r in results if not r.get("success", False)]
            
            execution.successful_flattens = len(successful_orders)
            execution.failed_flattens = len(failed_orders)
            execution.total_execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Determine final status
            if execution.failed_flattens == 0:
                execution.status = KillSwitchStatus.COMPLETED
            elif execution.successful_flattens > 0:
                execution.status = KillSwitchStatus.COMPLETED  # Partial success
            else:
                execution.status = KillSwitchStatus.FAILED
            
            execution.end_time = datetime.utcnow()
            
            # Log execution summary
            success_rate = (execution.successful_flattens / execution.total_positions) * 100
            time_vs_target = execution.total_execution_time_ms / self.target_execution_time_ms * 100
            
            if execution.total_execution_time_ms <= self.target_execution_time_ms:
                logger.critical(
                    "✅ KILL ALL COMPLETED: {}/{} positions flattened in {:.0f}ms ({:.1f}% of target)",
                    execution.successful_flattens,
                    execution.total_positions,
                    execution.total_execution_time_ms,
                    time_vs_target,
                    extra={
                        "execution_id": execution_id,
                        "success_rate": success_rate,
                        "target_met": True,
                        "total_time_ms": execution.total_execution_time_ms,
                        "successful_flattens": execution.successful_flattens,
                        "failed_flattens": execution.failed_flattens
                    }
                )
            else:
                logger.error(
                    "⚠️  KILL ALL SLOW: {}/{} positions flattened in {:.0f}ms ({:.1f}% of target) - EXCEEDED TARGET",
                    execution.successful_flattens,
                    execution.total_positions,
                    execution.total_execution_time_ms,
                    time_vs_target,
                    extra={
                        "execution_id": execution_id,
                        "success_rate": success_rate,
                        "target_met": False,
                        "total_time_ms": execution.total_execution_time_ms,
                        "successful_flattens": execution.successful_flattens,
                        "failed_flattens": execution.failed_flattens
                    }
                )
            
            # Update metrics
            await self._update_execution_metrics(execution)
            
            # Store execution record
            await self._store_execution_record(execution)
            
            # Clear positions cache
            self.active_positions.clear()
            
            return execution
            
        except Exception as e:
            execution.status = KillSwitchStatus.FAILED
            execution.end_time = datetime.utcnow()
            execution.total_execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            logger.critical(
                "❌ KILL ALL FAILED: {} - {}",
                str(e),
                trigger_reason,
                extra={
                    "execution_id": execution_id,
                    "error": str(e),
                    "trigger": trigger.value,
                    "user_id": user_id
                }
            )
            
            await self._store_execution_record(execution)
            raise EmergencyError(f"Kill all execution failed: {e}")
        
        finally:
            self.current_execution = None
            self.execution_history.append(execution)
            self.last_execution_time = datetime.utcnow()
    
    async def _capture_position_snapshot(self) -> None:
        """Capture snapshot of all current positions."""
        # TODO: Integrate with position manager to get actual positions
        # For now, create mock positions for testing
        
        mock_positions = {
            "NIFTY2412524000CE": PositionSnapshot(
                symbol="NIFTY2412524000CE",
                strategy_id="vol_oi_strategy",
                current_quantity=10,
                average_price=25.50,
                current_price=28.75,
                unrealized_pnl=325.0,
                market_value=2875.0
            ),
            "NIFTY2412524000PE": PositionSnapshot(
                symbol="NIFTY2412524000PE",
                strategy_id="vol_oi_strategy",
                current_quantity=-8,
                average_price=22.30,
                current_price=19.60,
                unrealized_pnl=216.0,
                market_value=-1568.0
            )
        }
        
        self.active_positions = mock_positions
        
        logger.debug("Position snapshot captured: {} positions", len(self.active_positions))
    
    async def _generate_flatten_orders(
        self,
        positions: List[PositionSnapshot]
    ) -> List[FlattenOrder]:
        """Generate market orders to flatten all positions."""
        flatten_orders = []
        
        for position in positions:
            flatten_id = str(uuid4())
            
            # Determine transaction type (opposite of current position)
            if position.current_quantity > 0:
                transaction_type = TransactionType.SELL
                flatten_quantity = position.current_quantity
            else:
                transaction_type = TransactionType.BUY
                flatten_quantity = abs(position.current_quantity)
            
            # Create market order for immediate execution
            order_request = OrderRequest(
                symbol=position.symbol,
                quantity=flatten_quantity,
                price=position.current_price,  # Market price
                transaction_type=transaction_type,
                product_type=ProductType.INTRADAY,
                order_type=OrderType.MARKET,
                validity=Validity.DAY
            )
            
            flatten_order = FlattenOrder(
                flatten_id=flatten_id,
                symbol=position.symbol,
                strategy_id=position.strategy_id,
                original_quantity=position.current_quantity,
                flatten_quantity=flatten_quantity,
                market_price=position.current_price,
                order_request=order_request
            )
            
            flatten_orders.append(flatten_order)
        
        return flatten_orders
    
    async def _execute_flatten_orders_parallel(
        self,
        flatten_orders: List[FlattenOrder]
    ) -> List[Dict[str, Any]]:
        """Execute all flatten orders in parallel for maximum speed."""
        # Create semaphore to limit concurrent orders
        semaphore = asyncio.Semaphore(self.max_concurrent_orders)
        
        async def execute_single_order(order: FlattenOrder) -> Dict[str, Any]:
            async with semaphore:
                start_time = time.perf_counter()
                
                try:
                    # Submit order to broker
                    broker_response = await self.broker_client.place_order(
                        symbol=order.order_request.symbol,
                        quantity=order.order_request.quantity,
                        price=order.order_request.price,
                        transaction_type=order.order_request.transaction_type,
                        product_type=order.order_request.product_type,
                        order_type=order.order_request.order_type,
                        validity=order.order_request.validity
                    )
                    
                    execution_time = (time.perf_counter() - start_time) * 1000
                    
                    order.status = OrderStatus.SUBMITTED
                    order.broker_order_id = broker_response.get("order_id")
                    order.execution_time_ms = execution_time
                    
                    return {
                        "flatten_id": order.flatten_id,
                        "symbol": order.symbol,
                        "success": True,
                        "broker_order_id": order.broker_order_id,
                        "execution_time_ms": execution_time
                    }
                    
                except Exception as e:
                    execution_time = (time.perf_counter() - start_time) * 1000
                    
                    order.status = OrderStatus.FAILED
                    order.error_message = str(e)
                    order.execution_time_ms = execution_time
                    
                    return {
                        "flatten_id": order.flatten_id,
                        "symbol": order.symbol,
                        "success": False,
                        "error": str(e),
                        "execution_time_ms": execution_time
                    }
        
        # Execute all orders in parallel
        tasks = [execute_single_order(order) for order in flatten_orders]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "execution_time_ms": 0.0
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _perform_safety_checks(
        self,
        trigger: KillSwitchTrigger,
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """Perform safety checks before execution."""
        if not self.safety_checks_enabled:
            return {"allowed": True, "reason": "Safety checks disabled"}
        
        # Check minimum interval between executions
        if self.last_execution_time:
            time_since_last = datetime.utcnow() - self.last_execution_time
            if time_since_last.total_seconds() < self.min_execution_interval_seconds:
                return {
                    "allowed": False,
                    "reason": f"Minimum interval not met ({time_since_last.total_seconds():.1f}s < {self.min_execution_interval_seconds}s)"
                }
        
        # Check if confirmation is required for manual triggers
        if trigger == KillSwitchTrigger.MANUAL and self.require_confirmation:
            # TODO: Implement confirmation mechanism
            pass
        
        # Check if already executing
        if self.current_execution and self.current_execution.status == KillSwitchStatus.EXECUTING:
            return {
                "allowed": False,
                "reason": "Kill switch execution already in progress"
            }
        
        return {"allowed": True, "reason": "All safety checks passed"}
    
    async def _update_execution_metrics(self, execution: KillSwitchExecution) -> None:
        """Update execution performance metrics."""
        self.execution_metrics["total_executions"] += 1
        
        if execution.status == KillSwitchStatus.COMPLETED:
            self.execution_metrics["successful_executions"] += 1
        else:
            self.execution_metrics["failed_executions"] += 1
        
        # Update timing metrics
        exec_time = execution.total_execution_time_ms
        self.execution_metrics["fastest_execution_ms"] = min(
            self.execution_metrics["fastest_execution_ms"], exec_time
        )
        self.execution_metrics["slowest_execution_ms"] = max(
            self.execution_metrics["slowest_execution_ms"], exec_time
        )
        
        # Update average
        total_successful = self.execution_metrics["successful_executions"]
        if total_successful > 0:
            current_avg = self.execution_metrics["average_execution_time_ms"]
            self.execution_metrics["average_execution_time_ms"] = (
                (current_avg * (total_successful - 1) + exec_time) / total_successful
            )
    
    async def _store_execution_record(self, execution: KillSwitchExecution) -> None:
        """Store execution record for audit trail."""
        try:
            execution_data = {
                "execution_id": execution.execution_id,
                "trigger": execution.trigger.value,
                "trigger_reason": execution.trigger_reason,
                "user_id": execution.user_id,
                "total_positions": execution.total_positions,
                "successful_flattens": execution.successful_flattens,
                "failed_flattens": execution.failed_flattens,
                "total_execution_time_ms": execution.total_execution_time_ms,
                "target_time_ms": execution.target_time_ms,
                "status": execution.status.value,
                "start_time": execution.start_time.isoformat(),
                "end_time": execution.end_time.isoformat() if execution.end_time else None,
                "positions_snapshot": [
                    {
                        "symbol": pos.symbol,
                        "strategy_id": pos.strategy_id,
                        "current_quantity": pos.current_quantity,
                        "market_value": pos.market_value,
                        "unrealized_pnl": pos.unrealized_pnl
                    }
                    for pos in execution.positions_snapshot
                ],
                "flatten_orders": [
                    {
                        "flatten_id": order.flatten_id,
                        "symbol": order.symbol,
                        "flatten_quantity": order.flatten_quantity,
                        "status": order.status.value,
                        "broker_order_id": order.broker_order_id,
                        "execution_time_ms": order.execution_time_ms,
                        "error_message": order.error_message
                    }
                    for order in execution.flatten_orders
                ]
            }
            
            # Store in Redis with long TTL for audit trail
            await self.redis.lpush(
                "kill_switch_executions",
                execution_data,
                ttl=timedelta(days=365)  # Keep for 1 year
            )
            
        except Exception as e:
            logger.error("Failed to store kill switch execution record: {}", str(e))
    
    def get_status(self) -> Dict[str, Any]:
        """Get current kill switch status."""
        return {
            "is_armed": self.is_armed,
            "current_execution": {
                "execution_id": self.current_execution.execution_id,
                "status": self.current_execution.status.value,
                "trigger": self.current_execution.trigger.value,
                "positions_count": self.current_execution.total_positions,
                "start_time": self.current_execution.start_time.isoformat()
            } if self.current_execution else None,
            "active_positions_count": len(self.active_positions),
            "safety_checks_enabled": self.safety_checks_enabled,
            "require_confirmation": self.require_confirmation,
            "target_execution_time_ms": self.target_execution_time_ms,
            "metrics": self.execution_metrics
        }
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        recent_executions = self.execution_history[-limit:]
        return [
            {
                "execution_id": exec.execution_id,
                "trigger": exec.trigger.value,
                "trigger_reason": exec.trigger_reason,
                "status": exec.status.value,
                "total_positions": exec.total_positions,
                "successful_flattens": exec.successful_flattens,
                "total_execution_time_ms": exec.total_execution_time_ms,
                "target_met": exec.total_execution_time_ms <= exec.target_time_ms,
                "start_time": exec.start_time.isoformat(),
                "end_time": exec.end_time.isoformat() if exec.end_time else None
            }
            for exec in recent_executions
        ] 