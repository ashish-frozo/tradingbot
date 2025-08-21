"""
Order Manager Module

Comprehensive order management system with slippage controls.
Key features:
- Slippage filtering (reject if >₹0.30/leg or spread >0.3%)
- Pre-trade risk validation
- Order lifecycle management
- Fill tracking and monitoring
- Integration with risk management
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import json

from loguru import logger

from app.core.config import get_settings
from app.cache.redis import redis_client
from app.risk import risk_manager, circuit_breaker
from .models import (
    Order, OrderRequest, OrderStatus, OrderType, SlippageStatus, RejectReason,
    PriceData, SlippageMetrics, Fill, ExecutionReport, OrderBook
)


@dataclass
class SlippageConfig:
    """Slippage filtering configuration"""
    max_slippage_per_leg: float = 0.30  # ₹0.30 per PRD
    max_spread_percentage: float = 0.3   # 0.3% per PRD
    warning_slippage_threshold: float = 0.20  # ₹0.20 warning
    warning_spread_percentage: float = 0.2    # 0.2% warning
    enable_spread_check: bool = True
    enable_slippage_check: bool = True


@dataclass
class OrderValidationResult:
    """Order validation result"""
    is_valid: bool
    rejection_reason: Optional[RejectReason] = None
    warnings: List[str] = None
    slippage_check: Optional[SlippageMetrics] = None
    spread_check: Optional[PriceData] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class OrderManager:
    """
    Comprehensive order management system
    
    Features:
    - Pre-trade slippage and spread validation  
    - Risk integration with position limits
    - Circuit breaker integration
    - Order lifecycle tracking
    - Fill monitoring and reporting
    - Retry and modification logic
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logger.bind(module="order_manager")
        
        # Configuration
        self.slippage_config = SlippageConfig()
        
        # Order tracking
        self.active_orders: Dict[str, Order] = {}
        self.completed_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        
        # Market data cache for slippage calculation
        self.market_data_cache: Dict[str, PriceData] = {}
        self.order_books: Dict[str, OrderBook] = {}
        
        # Statistics
        self.daily_stats = {
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_rejected": 0,
            "slippage_rejections": 0,
            "spread_rejections": 0,
            "total_slippage": 0.0,
            "avg_fill_latency": 0.0
        }
        
        # Callbacks
        self.execution_callback: Optional[Callable] = None
        self.alert_callback: Optional[Callable] = None
        
        # Redis keys
        self.redis_prefix = "order_manager"
        self.stats_key = f"{self.redis_prefix}:daily_stats"
        
    async def initialize(self):
        """Initialize order manager"""
        try:
            # Load daily stats
            stored_stats = await redis_client.get(self.stats_key)
            if stored_stats:
                self.daily_stats.update(json.loads(stored_stats))
            
            # Check for daily reset
            await self._check_daily_reset()
            
            self.logger.info(
                f"Order manager initialized: {len(self.active_orders)} active orders",
                extra={
                    "active_orders": len(self.active_orders),
                    "daily_stats": self.daily_stats,
                    "slippage_config": self.slippage_config.__dict__
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error initializing order manager: {e}")
            raise
    
    async def _check_daily_reset(self):
        """Check if we need to reset daily statistics"""
        try:
            # Reset daily stats at market open (similar to risk manager)
            last_reset_key = f"{self.redis_prefix}:last_reset"
            last_reset = await redis_client.get(last_reset_key)
            
            now = datetime.now(timezone.utc)
            current_date = now.date()
            
            if last_reset:
                last_reset_date = datetime.fromisoformat(last_reset).date()
                if current_date > last_reset_date:
                    await self._reset_daily_stats()
                    await redis_client.set(last_reset_key, now.isoformat())
            else:
                await redis_client.set(last_reset_key, now.isoformat())
                
        except Exception as e:
            self.logger.error(f"Error checking daily reset: {e}")
    
    async def _reset_daily_stats(self):
        """Reset daily statistics"""
        try:
            self.daily_stats = {
                "orders_submitted": 0,
                "orders_filled": 0,
                "orders_rejected": 0,
                "slippage_rejections": 0,
                "spread_rejections": 0,
                "total_slippage": 0.0,
                "avg_fill_latency": 0.0
            }
            
            await redis_client.delete(self.stats_key)
            self.logger.info("Daily order statistics reset")
            
        except Exception as e:
            self.logger.error(f"Error resetting daily stats: {e}")
    
    async def update_market_data(self, symbol: str, bid: float, ask: float, ltp: float):
        """
        Update market data for slippage calculation
        
        Args:
            symbol: Option symbol
            bid: Best bid price
            ask: Best ask price  
            ltp: Last traded price
        """
        try:
            price_data = PriceData(
                bid=bid,
                ask=ask,
                ltp=ltp,
                spread_points=0,  # Will be calculated in __post_init__
                spread_percentage=0,  # Will be calculated in __post_init__
                timestamp=datetime.now(timezone.utc)
            )
            
            self.market_data_cache[symbol] = price_data
            
            self.logger.debug(
                f"Market data updated for {symbol}: "
                f"Bid={bid:.2f}, Ask={ask:.2f}, LTP={ltp:.2f}, "
                f"Spread={price_data.spread_percentage:.2f}%"
            )
            
        except Exception as e:
            self.logger.error(f"Error updating market data for {symbol}: {e}")
    
    async def validate_order_pre_submission(
        self,
        order_request: OrderRequest,
        expected_price: float,
        lot_size: int
    ) -> OrderValidationResult:
        """
        Comprehensive pre-submission order validation
        
        Args:
            order_request: Order request to validate
            expected_price: Expected execution price
            lot_size: Lot size for the instrument
            
        Returns:
            OrderValidationResult with validation details
        """
        try:
            warnings = []
            rejection_reason = None
            slippage_check = None
            spread_check = None
            
            # Create symbol for market data lookup
            symbol = f"{order_request.symbol}_{order_request.strike}_{order_request.option_type}_{order_request.expiry}"
            
            # Check circuit breakers first
            trading_allowed, circuit_reasons = circuit_breaker.is_trading_allowed()
            if not trading_allowed:
                return OrderValidationResult(
                    is_valid=False,
                    rejection_reason=RejectReason.CIRCUIT_BREAKER,
                    warnings=[f"Circuit breaker active: {', '.join(circuit_reasons)}"]
                )
            
            # Get market data for slippage validation
            market_data = self.market_data_cache.get(symbol)
            if not market_data:
                warnings.append("No market data available for slippage validation")
                # Allow order but with warning
            else:
                # Check spread filter (per PRD: reject if spread >0.3%)
                if self.slippage_config.enable_spread_check:
                    spread_check = market_data
                    
                    if market_data.spread_percentage > self.slippage_config.max_spread_percentage:
                        return OrderValidationResult(
                            is_valid=False,
                            rejection_reason=RejectReason.SPREAD_TOO_WIDE,
                            warnings=[f"Spread too wide: {market_data.spread_percentage:.2f}% > {self.slippage_config.max_spread_percentage}%"],
                            spread_check=spread_check
                        )
                    elif market_data.spread_percentage > self.slippage_config.warning_spread_percentage:
                        warnings.append(f"Wide spread warning: {market_data.spread_percentage:.2f}%")
                
                # Check slippage filter for market orders
                if (self.slippage_config.enable_slippage_check and 
                    order_request.order_type == OrderType.MARKET):
                    
                    # Estimate slippage based on bid-ask spread
                    estimated_execution_price = market_data.ask if order_request.transaction_type.value == "BUY" else market_data.bid
                    
                    lots = order_request.quantity // lot_size
                    slippage_check = SlippageMetrics(
                        expected_price=expected_price,
                        actual_price=estimated_execution_price,
                        slippage_points=0,  # Will be calculated in __post_init__
                        slippage_percentage=0,  # Will be calculated in __post_init__
                        slippage_amount=0,  # Will be calculated in __post_init__
                        lot_size=lot_size,
                        lots=lots,
                        status=SlippageStatus.ACCEPTABLE,  # Will be calculated in __post_init__
                        warning_threshold=self.slippage_config.warning_slippage_threshold,
                        rejection_threshold=self.slippage_config.max_slippage_per_leg
                    )
                    
                    if slippage_check.status == SlippageStatus.REJECTED:
                        return OrderValidationResult(
                            is_valid=False,
                            rejection_reason=RejectReason.SLIPPAGE_EXCEEDED,
                            warnings=[f"Slippage too high: ₹{slippage_check.slippage_points:.2f} > ₹{self.slippage_config.max_slippage_per_leg}"],
                            slippage_check=slippage_check,
                            spread_check=spread_check
                        )
                    elif slippage_check.status == SlippageStatus.HIGH_WARNING:
                        warnings.append(f"High slippage warning: ₹{slippage_check.slippage_points:.2f}")
            
            # Check risk limits
            risk_allowed, risk_warnings = await risk_manager.check_position_limits(
                order_request.quantity // lot_size,
                order_request.strategy_name,
                []  # Would pass current positions in real implementation
            )
            
            if not risk_allowed:
                return OrderValidationResult(
                    is_valid=False,
                    rejection_reason=RejectReason.RISK_LIMITS,
                    warnings=risk_warnings,
                    slippage_check=slippage_check,
                    spread_check=spread_check
                )
            
            warnings.extend(risk_warnings)
            
            # Validate price sanity
            if order_request.price is not None and order_request.price <= 0:
                return OrderValidationResult(
                    is_valid=False,
                    rejection_reason=RejectReason.INVALID_PRICE,
                    warnings=["Invalid price: must be positive"],
                    slippage_check=slippage_check,
                    spread_check=spread_check
                )
            
            # Order passes all validations
            return OrderValidationResult(
                is_valid=True,
                warnings=warnings,
                slippage_check=slippage_check,
                spread_check=spread_check
            )
            
        except Exception as e:
            self.logger.error(f"Error validating order: {e}")
            return OrderValidationResult(
                is_valid=False,
                rejection_reason=RejectReason.SYSTEM_ERROR,
                warnings=[f"Validation error: {str(e)}"]
            )
    
    async def submit_order(
        self,
        order_request: OrderRequest,
        expected_price: Optional[float] = None,
        lot_size: int = 75  # Default NIFTY lot size
    ) -> Tuple[Order, bool]:
        """
        Submit order with comprehensive validation
        
        Args:
            order_request: Order details
            expected_price: Expected execution price for slippage calculation
            lot_size: Lot size for the instrument
            
        Returns:
            Tuple of (Order object, was_submitted_successfully)
        """
        try:
            # Generate order ID
            order_id = f"ORD_{uuid.uuid4().hex[:8].upper()}"
            
            # Create order object
            order = Order(
                order_id=order_id,
                request=order_request,
                status=OrderStatus.PENDING
            )
            
            # Validate order pre-submission
            if expected_price:
                validation = await self.validate_order_pre_submission(
                    order_request, expected_price, lot_size
                )
                
                if not validation.is_valid:
                    # Reject order
                    order.rejection_reason = validation.rejection_reason
                    order.status = OrderStatus.REJECTED
                    order.status_message = "; ".join(validation.warnings)
                    
                    # Store market data at rejection
                    symbol = f"{order_request.symbol}_{order_request.strike}_{order_request.option_type}_{order_request.expiry}"
                    order.market_data_at_submission = self.market_data_cache.get(symbol)
                    
                    # Update statistics
                    self.daily_stats["orders_rejected"] += 1
                    if validation.rejection_reason == RejectReason.SLIPPAGE_EXCEEDED:
                        self.daily_stats["slippage_rejections"] += 1
                    elif validation.rejection_reason == RejectReason.SPREAD_TOO_WIDE:
                        self.daily_stats["spread_rejections"] += 1
                    
                    await self._persist_daily_stats()
                    
                    self.logger.warning(
                        f"Order {order_id} rejected: {validation.rejection_reason.value}",
                        extra={
                            "order_id": order_id,
                            "rejection_reason": validation.rejection_reason.value,
                            "warnings": validation.warnings,
                            "symbol": order_request.symbol,
                            "strategy": order_request.strategy_name
                        }
                    )
                    
                    # Store in completed orders
                    self.completed_orders[order_id] = order
                    return order, False
                
                # Add validation warnings to order
                if validation.warnings:
                    order.status_message = "; ".join(validation.warnings)
            
            # Order passed validation, prepare for submission
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now(timezone.utc)
            order.submitted_price = order_request.price
            
            # Store market data at submission
            symbol = f"{order_request.symbol}_{order_request.strike}_{order_request.option_type}_{order_request.expiry}"
            order.market_data_at_submission = self.market_data_cache.get(symbol)
            
            # Add to active orders
            self.active_orders[order_id] = order
            
            # Update statistics
            self.daily_stats["orders_submitted"] += 1
            await self._persist_daily_stats()
            
            self.logger.info(
                f"Order {order_id} submitted: {order_request.transaction_type.value} "
                f"{order_request.quantity} {order_request.symbol} {order_request.strike}{order_request.option_type}",
                extra={
                    "order_id": order_id,
                    "symbol": order_request.symbol,
                    "transaction_type": order_request.transaction_type.value,
                    "quantity": order_request.quantity,
                    "price": order_request.price,
                    "strategy": order_request.strategy_name
                }
            )
            
            # Here you would integrate with the actual broker API
            # For now, we'll simulate successful submission
            
            return order, True
            
        except Exception as e:
            self.logger.error(f"Error submitting order: {e}")
            
            # Create error order
            error_order = Order(
                order_id=f"ERR_{uuid.uuid4().hex[:8].upper()}",
                request=order_request,
                status=OrderStatus.REJECTED,
                rejection_reason=RejectReason.SYSTEM_ERROR,
                status_message=f"Submission error: {str(e)}"
            )
            
            return error_order, False
    
    async def process_execution_report(self, report: ExecutionReport):
        """
        Process execution report from broker
        
        Args:
            report: Execution report with fill details
        """
        try:
            order = self.active_orders.get(report.order_id)
            if not order:
                self.logger.warning(f"Received execution report for unknown order: {report.order_id}")
                return
            
            # Update order status
            order.update_status(report.status, report.message)
            order.external_order_id = report.external_order_id
            
            # Process fill if present
            if report.fill_details:
                order.add_fill(report.fill_details)
                
                # Calculate slippage if this is the first fill
                if len(order.fills) == 1 and order.request:
                    expected_price = order.submitted_price or order.market_data_at_submission.ltp if order.market_data_at_submission else None
                    if expected_price:
                        # Estimate lot size based on symbol
                        lot_size = 75 if "NIFTY" in order.request.symbol else 15  # NIFTY vs BANKNIFTY
                        order.calculate_slippage(expected_price, lot_size)
                        
                        # Update slippage statistics
                        if order.slippage_metrics:
                            self.daily_stats["total_slippage"] += order.slippage_metrics.slippage_amount
            
            # Move to completed if terminal
            if order.is_terminal():
                self.completed_orders[order.order_id] = order
                del self.active_orders[order.order_id]
                
                if order.status == OrderStatus.FILLED:
                    self.daily_stats["orders_filled"] += 1
                
                # Update average latency
                if order.latency_metrics and order.latency_metrics.total_latency_ms:
                    current_count = self.daily_stats["orders_filled"] + self.daily_stats["orders_rejected"]
                    if current_count > 0:
                        current_avg = self.daily_stats["avg_fill_latency"]
                        self.daily_stats["avg_fill_latency"] = (
                            (current_avg * (current_count - 1) + order.latency_metrics.total_latency_ms) / current_count
                        )
                    else:
                        self.daily_stats["avg_fill_latency"] = order.latency_metrics.total_latency_ms
                
                await self._persist_daily_stats()
            
            self.logger.debug(
                f"Processed execution report for {report.order_id}: "
                f"{report.status.value} - {report.message}",
                extra={
                    "order_id": report.order_id,
                    "status": report.status.value,
                    "filled_quantity": report.filled_quantity,
                    "average_price": report.average_price
                }
            )
            
            # Execute callback if registered
            if self.execution_callback:
                await self.execution_callback(order, report)
                
        except Exception as e:
            self.logger.error(f"Error processing execution report: {e}")
    
    async def cancel_order(self, order_id: str, reason: str = "User request") -> bool:
        """
        Cancel an active order
        
        Args:
            order_id: Order ID to cancel
            reason: Cancellation reason
            
        Returns:
            True if cancellation was initiated successfully
        """
        try:
            order = self.active_orders.get(order_id)
            if not order:
                self.logger.warning(f"Cannot cancel unknown order: {order_id}")
                return False
            
            if not order.is_active():
                self.logger.warning(f"Cannot cancel non-active order: {order_id} (status: {order.status})")
                return False
            
            # Update order status
            order.update_status(OrderStatus.CANCELLED, f"Cancelled: {reason}")
            
            # Move to completed
            self.completed_orders[order_id] = order
            del self.active_orders[order_id]
            
            self.logger.info(f"Order {order_id} cancelled: {reason}")
            
            # Here you would integrate with broker API to actually cancel
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def cancel_all_orders(self, reason: str = "Emergency cancel") -> int:
        """
        Cancel all active orders
        
        Args:
            reason: Cancellation reason
            
        Returns:
            Number of orders cancelled
        """
        try:
            active_order_ids = list(self.active_orders.keys())
            cancelled_count = 0
            
            for order_id in active_order_ids:
                if await self.cancel_order(order_id, reason):
                    cancelled_count += 1
            
            self.logger.warning(
                f"Emergency cancel: {cancelled_count}/{len(active_order_ids)} orders cancelled",
                extra={"reason": reason, "cancelled_count": cancelled_count}
            )
            
            return cancelled_count
            
        except Exception as e:
            self.logger.error(f"Error in cancel all orders: {e}")
            return 0
    
    async def _persist_daily_stats(self):
        """Persist daily statistics to Redis"""
        try:
            await redis_client.set(
                self.stats_key,
                json.dumps(self.daily_stats),
                ex=86400  # Keep for 24 hours
            )
        except Exception as e:
            self.logger.error(f"Error persisting daily stats: {e}")
    
    def register_execution_callback(self, callback: Callable):
        """Register callback for execution reports"""
        self.execution_callback = callback
        self.logger.info("Execution callback registered")
    
    def register_alert_callback(self, callback: Callable):
        """Register callback for alerts"""
        self.alert_callback = callback
        self.logger.info("Alert callback registered")
    
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get order status by ID"""
        return self.active_orders.get(order_id) or self.completed_orders.get(order_id)
    
    async def get_active_orders(self) -> List[Order]:
        """Get all active orders"""
        return list(self.active_orders.values())
    
    async def get_daily_summary(self) -> Dict[str, Any]:
        """Get daily order management summary"""
        try:
            active_orders = len(self.active_orders)
            
            # Calculate slippage stats
            completed_orders_with_slippage = [
                order for order in self.completed_orders.values()
                if order.slippage_metrics is not None
            ]
            
            avg_slippage = 0.0
            if completed_orders_with_slippage:
                avg_slippage = sum(
                    order.slippage_metrics.slippage_amount 
                    for order in completed_orders_with_slippage
                ) / len(completed_orders_with_slippage)
            
            return {
                "active_orders": active_orders,
                "daily_stats": self.daily_stats,
                "slippage_config": self.slippage_config.__dict__,
                "avg_slippage_amount": avg_slippage,
                "market_data_symbols": len(self.market_data_cache),
                "completed_orders": len(self.completed_orders),
                "rejection_rate": (
                    self.daily_stats["orders_rejected"] / 
                    max(1, self.daily_stats["orders_submitted"] + self.daily_stats["orders_rejected"])
                ) * 100,
                "fill_rate": (
                    self.daily_stats["orders_filled"] / 
                    max(1, self.daily_stats["orders_submitted"])
                ) * 100
            }
            
        except Exception as e:
            self.logger.error(f"Error getting daily summary: {e}")
            return {"error": str(e)}


# Global instance
order_manager = OrderManager() 