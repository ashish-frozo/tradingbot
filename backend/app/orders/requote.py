"""
Intelligent re-quote system with price chasing and retry management.

This module provides smart order re-quoting with controlled price chasing,
maximum retry limits, and adaptive pricing strategies.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Tuple
from uuid import uuid4

from loguru import logger
from app.broker.tradehull_client import TradehullClient
from app.broker.enums import TransactionType, OrderType
from app.orders.models import OrderRequest, OrderResponse, OrderStatus
from app.core.exceptions import RequoteError, MaxRetriesExceededError


class RequoteStrategy(Enum):
    """Re-quote pricing strategies."""
    CONSERVATIVE = "conservative"  # Smaller price movements
    AGGRESSIVE = "aggressive"      # Larger price movements  
    ADAPTIVE = "adaptive"          # Adapt based on market conditions


class RequoteReason(Enum):
    """Reasons for re-quoting an order."""
    PARTIAL_FILL = "partial_fill"
    REJECTION = "rejection"
    TIMEOUT = "timeout"
    SLIPPAGE = "slippage"
    MARKET_MOVE = "market_move"


@dataclass
class RequoteConfig:
    """Configuration for re-quote behavior."""
    max_retries: int = 3
    max_price_chase_rs: float = 0.10  # ₹0.10 maximum price chase
    retry_delay_ms: int = 100         # Delay between retries
    timeout_seconds: int = 30         # Order timeout before re-quote
    price_improvement_rs: float = 0.05  # ₹0.05 price improvement per retry
    adaptive_threshold: float = 0.02   # Market volatility threshold for adaptive mode
    

@dataclass
class RequoteAttempt:
    """Tracking data for a single re-quote attempt."""
    attempt_number: int
    original_price: float
    new_price: float
    reason: RequoteReason
    timestamp: datetime
    market_data: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    broker_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class RequoteContext:
    """Context for managing re-quote sessions."""
    original_order_id: str
    strategy_id: str
    symbol: str
    original_request: OrderRequest
    config: RequoteConfig
    attempts: List[RequoteAttempt] = field(default_factory=list)
    total_price_movement: float = 0.0
    start_time: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True
    

class OrderRequoter:
    """
    Intelligent order re-quoting system with price chasing controls.
    
    Features:
    - Maximum 3 retries per order with ≤₹0.10 total price chase
    - Adaptive pricing strategies based on market conditions
    - Configurable retry delays and timeouts
    - Comprehensive tracking and analytics
    - Circuit breaker for excessive re-quotes
    """
    
    def __init__(
        self,
        broker_client: TradehullClient,
        default_config: Optional[RequoteConfig] = None
    ):
        self.broker_client = broker_client
        self.default_config = default_config or RequoteConfig()
        
        # Active re-quote sessions
        self.active_requotes: Dict[str, RequoteContext] = {}
        
        # Performance tracking
        self.requote_stats = {
            "total_attempts": 0,
            "successful_requotes": 0,
            "failed_requotes": 0,
            "average_attempts": 0.0,
            "price_chase_violations": 0
        }
        
        # Circuit breaker for excessive re-quotes
        self.circuit_breaker = {
            "failure_count": 0,
            "last_failure_time": None,
            "is_open": False,
            "failure_threshold": 10,
            "recovery_time_seconds": 300  # 5 minutes
        }
        
        logger.info("Order re-quoter initialized with default config: {}", self.default_config)
    
    async def requote_order(
        self,
        original_order_id: str,
        strategy_id: str,
        reason: RequoteReason,
        market_data: Optional[Dict[str, Any]] = None,
        custom_config: Optional[RequoteConfig] = None
    ) -> OrderResponse:
        """
        Attempt to re-quote an order with intelligent pricing.
        
        Args:
            original_order_id: ID of the original order to re-quote
            strategy_id: Strategy requesting the re-quote
            reason: Reason for re-quoting
            market_data: Current market data for pricing decisions
            custom_config: Custom re-quote configuration
            
        Returns:
            OrderResponse with re-quote results
        """
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            raise RequoteError("Re-quote circuit breaker is open")
        
        config = custom_config or self.default_config
        
        # Get or create re-quote context
        context = self.active_requotes.get(original_order_id)
        if not context:
            raise RequoteError(f"No active re-quote context for order {original_order_id}")
        
        # Check if we've exceeded max retries
        if len(context.attempts) >= config.max_retries:
            context.is_active = False
            self.active_requotes.pop(original_order_id, None)
            raise MaxRetriesExceededError(
                f"Maximum re-quote attempts ({config.max_retries}) exceeded for order {original_order_id}"
            )
        
        attempt_number = len(context.attempts) + 1
        
        try:
            # Calculate new price for re-quote
            new_price = await self._calculate_requote_price(
                context, reason, market_data or {}, config
            )
            
            # Validate price chase limits
            price_movement = abs(new_price - context.original_request.price)
            total_movement = context.total_price_movement + price_movement
            
            if total_movement > config.max_price_chase_rs:
                logger.warning(
                    "Re-quote would exceed price chase limit: ₹{:.3f} > ₹{:.3f}",
                    total_movement,
                    config.max_price_chase_rs,
                    extra={
                        "order_id": original_order_id,
                        "attempt": attempt_number,
                        "total_movement": total_movement,
                        "limit": config.max_price_chase_rs
                    }
                )
                
                self.requote_stats["price_chase_violations"] += 1
                context.is_active = False
                self.active_requotes.pop(original_order_id, None)
                
                raise RequoteError(
                    f"Re-quote would exceed maximum price chase limit of ₹{config.max_price_chase_rs:.2f}"
                )
            
            # Create re-quote attempt record
            attempt = RequoteAttempt(
                attempt_number=attempt_number,
                original_price=context.original_request.price,
                new_price=new_price,
                reason=reason,
                timestamp=datetime.utcnow(),
                market_data=market_data or {}
            )
            
            # Add delay between retries (except first attempt)
            if attempt_number > 1:
                await asyncio.sleep(config.retry_delay_ms / 1000.0)
            
            # Create modified order request
            modified_request = context.original_request.model_copy()
            modified_request.price = new_price
            
            # Submit re-quote to broker
            logger.info(
                "Submitting re-quote attempt {}/{}: {} {} @ ₹{:.2f} (reason: {})",
                attempt_number,
                config.max_retries,
                modified_request.transaction_type.value,
                modified_request.symbol,
                new_price,
                reason.value,
                extra={
                    "order_id": original_order_id,
                    "strategy_id": strategy_id,
                    "original_price": context.original_request.price,
                    "price_movement": price_movement,
                    "total_movement": total_movement
                }
            )
            
            # Execute the re-quote
            broker_response = await self.broker_client.place_order(
                symbol=modified_request.symbol,
                quantity=modified_request.quantity,
                price=new_price,
                transaction_type=modified_request.transaction_type,
                product_type=modified_request.product_type,
                order_type=modified_request.order_type,
                validity=modified_request.validity
            )
            
            # Update attempt with success
            attempt.success = True
            attempt.broker_response = broker_response
            
            # Update context
            context.attempts.append(attempt)
            context.total_price_movement = total_movement
            
            # Update statistics
            self.requote_stats["total_attempts"] += 1
            self.requote_stats["successful_requotes"] += 1
            self._update_average_attempts()
            
            logger.info(
                "Re-quote successful: order {} attempt {}/{}",
                original_order_id,
                attempt_number,
                config.max_retries,
                extra={
                    "broker_order_id": broker_response.get("order_id"),
                    "final_price": new_price,
                    "total_price_movement": total_movement
                }
            )
            
            return OrderResponse(
                order_id=broker_response.get("order_id", str(uuid4())),
                status=OrderStatus.SUBMITTED,
                broker_order_id=broker_response.get("order_id"),
                message=f"Re-quote successful (attempt {attempt_number})",
                execution_time_ms=0.0,  # TODO: Track execution time
                requote_attempt=attempt_number,
                total_price_movement=total_movement
            )
            
        except Exception as e:
            # Create failed attempt record
            attempt = RequoteAttempt(
                attempt_number=attempt_number,
                original_price=context.original_request.price,
                new_price=new_price if 'new_price' in locals() else context.original_request.price,
                reason=reason,
                timestamp=datetime.utcnow(),
                market_data=market_data or {},
                success=False,
                error=str(e)
            )
            
            context.attempts.append(attempt)
            
            # Update statistics
            self.requote_stats["total_attempts"] += 1
            self.requote_stats["failed_requotes"] += 1
            self._update_circuit_breaker(True)
            self._update_average_attempts()
            
            logger.error(
                "Re-quote attempt {}/{} failed: {}",
                attempt_number,
                config.max_retries,
                str(e),
                extra={
                    "order_id": original_order_id,
                    "strategy_id": strategy_id,
                    "error": str(e)
                }
            )
            
            # If this was the last attempt, deactivate context
            if attempt_number >= config.max_retries:
                context.is_active = False
                self.active_requotes.pop(original_order_id, None)
            
            raise RequoteError(f"Re-quote attempt {attempt_number} failed: {e}")
    
    async def start_requote_session(
        self,
        original_order_id: str,
        strategy_id: str,
        original_request: OrderRequest,
        config: Optional[RequoteConfig] = None
    ) -> str:
        """Start a new re-quote session for an order."""
        session_config = config or self.default_config
        
        context = RequoteContext(
            original_order_id=original_order_id,
            strategy_id=strategy_id,
            symbol=original_request.symbol,
            original_request=original_request,
            config=session_config
        )
        
        self.active_requotes[original_order_id] = context
        
        logger.info(
            "Started re-quote session for order: {} (symbol: {})",
            original_order_id,
            original_request.symbol,
            extra={
                "strategy_id": strategy_id,
                "max_retries": session_config.max_retries,
                "max_price_chase": session_config.max_price_chase_rs
            }
        )
        
        return original_order_id
    
    def stop_requote_session(self, order_id: str) -> bool:
        """Stop an active re-quote session."""
        context = self.active_requotes.pop(order_id, None)
        if context:
            context.is_active = False
            logger.info("Stopped re-quote session for order: {}", order_id)
            return True
        return False
    
    async def _calculate_requote_price(
        self,
        context: RequoteContext,
        reason: RequoteReason,
        market_data: Dict[str, Any],
        config: RequoteConfig
    ) -> float:
        """Calculate the new price for re-quote based on strategy and market conditions."""
        original_price = context.original_request.price
        transaction_type = context.original_request.transaction_type
        
        # Get current market prices
        bid_price = market_data.get("bid", original_price)
        ask_price = market_data.get("ask", original_price)
        ltp = market_data.get("ltp", original_price)
        
        # Calculate market volatility for adaptive pricing
        volatility = self._calculate_market_volatility(market_data)
        
        # Determine pricing strategy
        if volatility > config.adaptive_threshold:
            strategy = RequoteStrategy.AGGRESSIVE
        else:
            strategy = RequoteStrategy.CONSERVATIVE
        
        # Base price improvement
        base_improvement = config.price_improvement_rs
        
        # Adjust based on strategy
        if strategy == RequoteStrategy.AGGRESSIVE:
            price_improvement = base_improvement * 1.5
        elif strategy == RequoteStrategy.CONSERVATIVE:
            price_improvement = base_improvement * 0.8
        else:  # ADAPTIVE
            price_improvement = base_improvement * (1 + volatility)
        
        # Calculate new price based on transaction type and reason
        if transaction_type == TransactionType.BUY:
            if reason in [RequoteReason.REJECTION, RequoteReason.TIMEOUT]:
                # For buy orders, increase price (chase higher)
                new_price = min(ask_price, original_price + price_improvement)
            else:
                # For partial fills, be more conservative
                new_price = min(ltp + 0.05, original_price + price_improvement * 0.5)
        else:  # SELL
            if reason in [RequoteReason.REJECTION, RequoteReason.TIMEOUT]:
                # For sell orders, decrease price (chase lower)
                new_price = max(bid_price, original_price - price_improvement)
            else:
                # For partial fills, be more conservative
                new_price = max(ltp - 0.05, original_price - price_improvement * 0.5)
        
        # Ensure we don't go below minimum tick size (₹0.05 for options)
        min_tick = 0.05
        new_price = round(new_price / min_tick) * min_tick
        
        # Validate price movement doesn't exceed remaining chase limit
        remaining_chase = config.max_price_chase_rs - context.total_price_movement
        price_movement = abs(new_price - original_price)
        
        if price_movement > remaining_chase:
            # Scale back to remaining limit
            if transaction_type == TransactionType.BUY:
                new_price = original_price + remaining_chase
            else:
                new_price = original_price - remaining_chase
            
            new_price = round(new_price / min_tick) * min_tick
        
        logger.debug(
            "Calculated re-quote price: ₹{:.2f} -> ₹{:.2f} (movement: ₹{:.3f}, strategy: {})",
            original_price,
            new_price,
            abs(new_price - original_price),
            strategy.value,
            extra={
                "reason": reason.value,
                "market_volatility": volatility,
                "bid": bid_price,
                "ask": ask_price,
                "ltp": ltp
            }
        )
        
        return new_price
    
    def _calculate_market_volatility(self, market_data: Dict[str, Any]) -> float:
        """Calculate market volatility from market data."""
        # Simple volatility calculation based on bid-ask spread
        bid = market_data.get("bid", 0)
        ask = market_data.get("ask", 0)
        ltp = market_data.get("ltp", 1)
        
        if bid > 0 and ask > 0 and ltp > 0:
            spread_ratio = (ask - bid) / ltp
            return min(spread_ratio, 0.1)  # Cap at 10%
        
        return 0.01  # Default low volatility
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if the circuit breaker is open."""
        if not self.circuit_breaker["is_open"]:
            return False
        
        # Check if recovery time has passed
        if self.circuit_breaker["last_failure_time"]:
            time_since_failure = time.time() - self.circuit_breaker["last_failure_time"]
            if time_since_failure > self.circuit_breaker["recovery_time_seconds"]:
                # Reset circuit breaker
                self.circuit_breaker["is_open"] = False
                self.circuit_breaker["failure_count"] = 0
                logger.info("Re-quote circuit breaker reset after recovery period")
                return False
        
        return True
    
    def _update_circuit_breaker(self, is_failure: bool) -> None:
        """Update circuit breaker state."""
        if is_failure:
            self.circuit_breaker["failure_count"] += 1
            self.circuit_breaker["last_failure_time"] = time.time()
            
            if self.circuit_breaker["failure_count"] >= self.circuit_breaker["failure_threshold"]:
                self.circuit_breaker["is_open"] = True
                logger.warning(
                    "Re-quote circuit breaker opened after {} failures",
                    self.circuit_breaker["failure_count"]
                )
        else:
            # Reset failure count on success
            self.circuit_breaker["failure_count"] = max(0, self.circuit_breaker["failure_count"] - 1)
    
    def _update_average_attempts(self) -> None:
        """Update average attempts statistic."""
        total = self.requote_stats["successful_requotes"] + self.requote_stats["failed_requotes"]
        if total > 0:
            self.requote_stats["average_attempts"] = self.requote_stats["total_attempts"] / total
    
    def get_requote_stats(self) -> Dict[str, Any]:
        """Get current re-quote statistics."""
        return {
            **self.requote_stats,
            "active_sessions": len(self.active_requotes),
            "circuit_breaker_status": {
                "is_open": self.circuit_breaker["is_open"],
                "failure_count": self.circuit_breaker["failure_count"],
                "time_until_recovery": max(
                    0,
                    self.circuit_breaker["recovery_time_seconds"] - 
                    (time.time() - (self.circuit_breaker["last_failure_time"] or 0))
                ) if self.circuit_breaker["is_open"] else 0
            }
        }
    
    def get_session_details(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific re-quote session."""
        context = self.active_requotes.get(order_id)
        if not context:
            return None
        
        return {
            "order_id": order_id,
            "strategy_id": context.strategy_id,
            "symbol": context.symbol,
            "original_price": context.original_request.price,
            "attempts": len(context.attempts),
            "max_attempts": context.config.max_retries,
            "total_price_movement": context.total_price_movement,
            "max_price_chase": context.config.max_price_chase_rs,
            "is_active": context.is_active,
            "start_time": context.start_time.isoformat(),
            "attempt_history": [
                {
                    "attempt": attempt.attempt_number,
                    "price": attempt.new_price,
                    "reason": attempt.reason.value,
                    "success": attempt.success,
                    "timestamp": attempt.timestamp.isoformat(),
                    "error": attempt.error
                }
                for attempt in context.attempts
            ]
        } 