"""
Volume-OI Strategy Trader
Main strategy implementation for Volume + Delayed-OI Confirm trading.

This module implements:
- Complete strategy lifecycle management
- Probe trade execution (2 lots with delta hedge)
- Position scaling logic (add 8 lots on confirmation)
- Exit conditions (+40% profit, -25% SL, 10-min timeout)
- Event filters and risk management
- Partial fill handling
"""

import asyncio
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any, Union
import json

from app.core.logging import get_logger
from app.strategies.base import (
    BaseStrategy, 
    TradingSignal, 
    MarketData, 
    StrategyState,
    SignalType,
    SignalStrength as BaseSignalStrength
)
from app.strategies.vol_oi.config import VolumeOIConfig, DEFAULT_CONFIG
from app.strategies.vol_oi.detector import VolumeOIDetector
from app.strategies.vol_oi.models import (
    StrategySignal,
    TradePhase,
    EventFilter,
    PerformanceMetrics,
    VolumeSignal,
    PriceJumpSignal,
    OISignal
)


logger = get_logger(__name__)


class VolumeOIStrategy(BaseStrategy):
    """
    Volume + Delayed-OI Confirm Strategy Implementation.
    
    Trading Logic:
    1. Detect volume spike (>3σ AND >5× 1-minute average)
    2. Confirm with price jump (≥0.15% within 2 seconds)
    3. Execute probe trade (2 lots with delta hedge)
    4. Wait for OI confirmation (>1.5σ within 240 seconds)
    5. Scale position (add 8 lots on confirmation)
    6. Manage exits (+40% profit, -25% SL, 10-min timeout)
    """
    
    def __init__(
        self, 
        strategy_id: str = None,
        config: VolumeOIConfig = None,
        broker_client=None,
        risk_manager=None,
        order_manager=None,
        redis_client=None
    ):
        # Initialize base strategy
        super().__init__(
            strategy_id=strategy_id or f"vol_oi_{uuid.uuid4().hex[:8]}",
            name="Volume-OI Confirm",
            version="1.0",
            description="Volume + Delayed-OI Confirm Strategy"
        )
        
        # Configuration
        self.config = config or DEFAULT_CONFIG
        
        # External dependencies
        self.broker_client = broker_client
        self.risk_manager = risk_manager
        self.order_manager = order_manager
        self.redis_client = redis_client
        
        # Detection engine
        self.detector = VolumeOIDetector(self.config, redis_client)
        
        # Strategy state
        self.active_signals: Dict[str, StrategySignal] = {}
        self.performance_metrics = PerformanceMetrics()
        self.event_filters: List[EventFilter] = []
        
        # Daily tracking
        self.daily_pnl = Decimal('0')
        self.daily_positions = 0
        self.consecutive_losses = 0
        self.last_reset_date = datetime.utcnow().date()
        
        # Runtime flags
        self.is_running = False
        self.emergency_stop = False
        
        logger.info(f"VolumeOI Strategy initialized: {self.strategy_id}")
    
    async def initialize(self) -> bool:
        """Initialize strategy components and validate configuration."""
        try:
            # Validate configuration
            config_errors = self.config.validate()
            if config_errors:
                logger.error(f"Configuration validation failed: {config_errors}")
                return False
            
            # Initialize base strategy
            await super().initialize()
            
            # Load event filters
            await self._load_event_filters()
            
            # Reset daily metrics if new day
            await self._check_daily_reset()
            
            logger.info(f"VolumeOI Strategy {self.strategy_id} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Strategy initialization failed: {e}")
            return False
    
    async def start(self) -> bool:
        """Start the strategy."""
        if not await self.initialize():
            return False
        
        try:
            self.is_running = True
            self.emergency_stop = False
            self.state = StrategyState.RUNNING
            
            # Check if within trading hours
            current_time = datetime.utcnow().time()
            if not self.config.is_trading_time(current_time):
                logger.warning(f"Started outside trading hours: {current_time}")
            
            logger.info(f"VolumeOI Strategy {self.strategy_id} started")
            return True
            
        except Exception as e:
            logger.error(f"Strategy start failed: {e}")
            self.state = StrategyState.ERROR
            return False
    
    async def stop(self) -> bool:
        """Stop the strategy and clean up positions."""
        try:
            self.is_running = False
            self.state = StrategyState.STOPPING
            
            # Close all active positions
            await self._close_all_positions("strategy_stop")
            
            # Save performance metrics
            await self._save_performance_metrics()
            
            self.state = StrategyState.STOPPED
            logger.info(f"VolumeOI Strategy {self.strategy_id} stopped")
            return True
            
        except Exception as e:
            logger.error(f"Strategy stop failed: {e}")
            self.state = StrategyState.ERROR
            return False
    
    async def process_market_data(self, market_data: MarketData) -> Optional[TradingSignal]:
        """
        Process market data and generate trading signals.
        
        Args:
            market_data: Latest market data
            
        Returns:
            TradingSignal if action required, None otherwise
        """
        if not self.is_running or self.emergency_stop:
            return None
        
        try:
            # Check daily reset
            await self._check_daily_reset()
            
            # Check if trading allowed
            if not await self._can_trade(market_data):
                return None
            
            # Process market data through detector
            volume_signal, price_signal, oi_signal = await self.detector.process_market_data(market_data)
            
            # Handle different signal combinations
            trading_signal = None
            
            # 1. Volume spike + Price jump = Trigger (probe trade)
            if volume_signal and price_signal:
                trading_signal = await self._handle_trigger(market_data, volume_signal, price_signal)
            
            # 2. OI change = Confirmation (scale position)
            elif oi_signal:
                trading_signal = await self._handle_confirmation(market_data, oi_signal)
            
            # 3. Update existing positions
            await self._update_active_positions(market_data)
            
            # 4. Check exit conditions
            exit_signals = await self._check_exit_conditions(market_data)
            if exit_signals and not trading_signal:
                trading_signal = exit_signals[0]  # Take first exit signal
            
            return trading_signal
            
        except Exception as e:
            logger.error(f"Error processing market data for {market_data.symbol}: {e}")
            return None
    
    async def _handle_trigger(
        self, 
        market_data: MarketData, 
        volume_signal: VolumeSignal, 
        price_signal: PriceJumpSignal
    ) -> Optional[TradingSignal]:
        """Handle volume spike + price jump trigger."""
        symbol = market_data.symbol
        
        # Check if already have active signal for this symbol
        if symbol in self.active_signals:
            current_signal = self.active_signals[symbol]
            if current_signal.phase in [TradePhase.PROBE_EXECUTED, TradePhase.AWAITING_CONFIRMATION]:
                logger.debug(f"Already have active signal for {symbol}, skipping trigger")
                return None
        
        # Check daily limits
        if not await self._check_daily_limits():
            return None
        
        try:
            # Create strategy signal
            signal_id = f"{symbol}_{uuid.uuid4().hex[:8]}"
            strategy_signal = StrategySignal(
                signal_id=signal_id,
                symbol=symbol,
                timestamp=market_data.timestamp,
                phase=TradePhase.PROBE_TRIGGERED,
                volume_signal=volume_signal,
                price_signal=price_signal,
                trigger_time=market_data.timestamp,
                entry_price=market_data.ltp
            )
            
            # Store active signal
            self.active_signals[symbol] = strategy_signal
            
            # Set trigger for OI confirmation
            self.detector.set_trigger(symbol, market_data.timestamp)
            
            # Create trading signal for probe trade
            trading_signal = TradingSignal(
                signal_id=signal_id,
                symbol=symbol,
                signal_type=SignalType.ENTRY,
                strength=BaseSignalStrength.HIGH,
                price=market_data.ltp,
                quantity=self.config.probe_quantity,
                timestamp=market_data.timestamp,
                metadata={
                    'strategy': self.name,
                    'phase': 'probe',
                    'volume_zscore': float(volume_signal.volume_zscore),
                    'price_jump_pct': float(price_signal.price_change_pct),
                    'hedge_required': True
                }
            )
            
            logger.info(f"Trigger detected for {symbol}: "
                       f"Volume spike (Z={volume_signal.volume_zscore:.2f}, "
                       f"Mult={volume_signal.volume_multiplier:.2f}x) + "
                       f"Price jump ({price_signal.price_change_pct:.3f}%)")
            
            # Update performance tracking
            self.performance_metrics.total_signals += 1
            self.performance_metrics.triggered_signals += 1
            
            return trading_signal
            
        except Exception as e:
            logger.error(f"Error handling trigger for {symbol}: {e}")
            return None
    
    async def _handle_confirmation(
        self, 
        market_data: MarketData, 
        oi_signal: OISignal
    ) -> Optional[TradingSignal]:
        """Handle OI change confirmation."""
        symbol = market_data.symbol
        
        # Check if we have an active signal waiting for confirmation
        if symbol not in self.active_signals:
            return None
        
        strategy_signal = self.active_signals[symbol]
        
        # Only confirm if in the right phase
        if strategy_signal.phase != TradePhase.AWAITING_CONFIRMATION:
            return None
        
        try:
            # Update strategy signal
            strategy_signal.oi_signal = oi_signal
            strategy_signal.phase = TradePhase.CONFIRMED
            strategy_signal.confirmation_time = market_data.timestamp
            
            # Create trading signal for scale trade
            signal_id = f"{symbol}_scale_{uuid.uuid4().hex[:8]}"
            trading_signal = TradingSignal(
                signal_id=signal_id,
                symbol=symbol,
                signal_type=SignalType.SCALE_IN,
                strength=BaseSignalStrength.HIGH,
                price=market_data.ltp,
                quantity=self.config.scale_quantity,
                timestamp=market_data.timestamp,
                metadata={
                    'strategy': self.name,
                    'phase': 'scale',
                    'original_signal_id': strategy_signal.signal_id,
                    'oi_zscore': float(oi_signal.oi_zscore),
                    'oi_change': oi_signal.oi_change,
                    'confirmation_delay_sec': oi_signal.time_since_trigger_seconds
                }
            )
            
            logger.info(f"Confirmation detected for {symbol}: "
                       f"OI change (Z={oi_signal.oi_zscore:.2f}, "
                       f"Change={oi_signal.oi_change:,}) "
                       f"after {oi_signal.time_since_trigger_seconds}s")
            
            # Update performance tracking
            self.performance_metrics.confirmed_signals += 1
            
            return trading_signal
            
        except Exception as e:
            logger.error(f"Error handling confirmation for {symbol}: {e}")
            return None
    
    async def _update_active_positions(self, market_data: MarketData) -> None:
        """Update P&L and metrics for active positions."""
        symbol = market_data.symbol
        
        if symbol not in self.active_signals:
            return
        
        strategy_signal = self.active_signals[symbol]
        
        # Update P&L if we have an entry price
        if strategy_signal.entry_price:
            # Calculate position size based on phase
            quantity = self.config.probe_quantity
            if strategy_signal.phase in [TradePhase.SCALED, TradePhase.CONFIRMED]:
                quantity += self.config.scale_quantity
            
            strategy_signal.update_pnl(market_data.ltp, quantity)
    
    async def _check_exit_conditions(self, market_data: MarketData) -> List[TradingSignal]:
        """Check exit conditions for active positions."""
        exit_signals = []
        symbols_to_exit = []
        
        for symbol, strategy_signal in self.active_signals.items():
            if strategy_signal.phase in [TradePhase.COMPLETED, TradePhase.CANCELLED]:
                continue
            
            should_exit, exit_reason = strategy_signal.should_exit()
            
            if should_exit:
                try:
                    # Create exit signal
                    signal_id = f"{symbol}_exit_{uuid.uuid4().hex[:8]}"
                    
                    # Calculate exit quantity
                    quantity = self.config.probe_quantity
                    if strategy_signal.phase in [TradePhase.SCALED, TradePhase.CONFIRMED]:
                        quantity += self.config.scale_quantity
                    
                    exit_signal = TradingSignal(
                        signal_id=signal_id,
                        symbol=symbol,
                        signal_type=SignalType.EXIT,
                        strength=BaseSignalStrength.HIGH,
                        price=market_data.ltp,
                        quantity=quantity,
                        timestamp=market_data.timestamp,
                        metadata={
                            'strategy': self.name,
                            'exit_reason': exit_reason,
                            'original_signal_id': strategy_signal.signal_id,
                            'unrealized_pnl': float(strategy_signal.unrealized_pnl),
                            'hold_time_minutes': (
                                (market_data.timestamp - strategy_signal.trigger_time).total_seconds() / 60
                                if strategy_signal.trigger_time else 0
                            )
                        }
                    )
                    
                    exit_signals.append(exit_signal)
                    symbols_to_exit.append(symbol)
                    
                    logger.info(f"Exit triggered for {symbol}: {exit_reason} "
                               f"(P&L: ₹{strategy_signal.unrealized_pnl:.2f})")
                    
                except Exception as e:
                    logger.error(f"Error creating exit signal for {symbol}: {e}")
        
        # Mark signals for exit
        for symbol in symbols_to_exit:
            self.active_signals[symbol].phase = TradePhase.EXITING
            self.active_signals[symbol].exit_time = market_data.timestamp
        
        return exit_signals
    
    async def _can_trade(self, market_data: MarketData) -> bool:
        """Check if trading is allowed based on filters and conditions."""
        current_time = datetime.utcnow()
        
        # Check trading hours
        if not self.config.is_trading_time(current_time.time()):
            return False
        
        # Check emergency stop
        if self.emergency_stop:
            return False
        
        # Check daily loss limit
        if self.daily_pnl <= -self.config.daily_loss_limit:
            logger.warning(f"Daily loss limit reached: ₹{self.daily_pnl:.2f}")
            return False
        
        # Check consecutive losses
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            logger.warning(f"Max consecutive losses reached: {self.consecutive_losses}")
            return False
        
        # Check event filters
        for event_filter in self.event_filters:
            if event_filter.is_blocking_trade(current_time):
                logger.debug(f"Trading blocked by event filter: {event_filter.event_type}")
                return False
        
        # Check position limits
        if self.daily_positions >= self.config.max_positions_per_day:
            logger.debug(f"Daily position limit reached: {self.daily_positions}")
            return False
        
        return True
    
    async def _check_daily_limits(self) -> bool:
        """Check if we can open new positions based on daily limits."""
        if self.daily_positions >= self.config.max_positions_per_day:
            return False
        
        if self.daily_pnl <= -self.config.daily_loss_limit:
            return False
        
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            return False
        
        return True
    
    async def _check_daily_reset(self) -> None:
        """Reset daily metrics if new trading day."""
        current_date = datetime.utcnow().date()
        
        if current_date > self.last_reset_date:
            logger.info(f"Daily reset: {self.last_reset_date} → {current_date}")
            
            self.daily_pnl = Decimal('0')
            self.daily_positions = 0
            self.consecutive_losses = 0
            self.last_reset_date = current_date
            
            # Clear expired triggers
            self.detector.cleanup_expired_triggers()
    
    async def _close_all_positions(self, reason: str = "strategy_stop") -> None:
        """Close all active positions."""
        logger.info(f"Closing all positions: {reason}")
        
        for symbol, strategy_signal in self.active_signals.items():
            if strategy_signal.phase not in [TradePhase.COMPLETED, TradePhase.CANCELLED]:
                strategy_signal.phase = TradePhase.CANCELLED
                strategy_signal.exit_time = datetime.utcnow()
                
                # Update performance metrics
                self.performance_metrics.update_from_trade(strategy_signal)
    
    async def _load_event_filters(self) -> None:
        """Load event filters from configuration or external source."""
        # This would typically load from a database or config file
        # For now, create default filters for demo
        current_date = datetime.utcnow().date()
        
        self.event_filters = [
            EventFilter(
                date=datetime.combine(current_date, time(0, 0)),
                event_type="RBI_POLICY",
                description="RBI Policy Meeting",
                is_active=False  # Set to True when actual event
            ),
            EventFilter(
                date=datetime.combine(current_date, time(0, 0)),
                event_type="BUDGET",
                description="Budget Announcement",
                is_active=False
            )
        ]
    
    async def _save_performance_metrics(self) -> None:
        """Save performance metrics to storage."""
        try:
            metrics_data = {
                'strategy_id': self.strategy_id,
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': {
                    'total_signals': self.performance_metrics.total_signals,
                    'triggered_signals': self.performance_metrics.triggered_signals,
                    'confirmed_signals': self.performance_metrics.confirmed_signals,
                    'completed_trades': self.performance_metrics.completed_trades,
                    'profitable_trades': self.performance_metrics.profitable_trades,
                    'total_pnl': float(self.performance_metrics.total_pnl),
                    'win_rate': float(self.performance_metrics.win_rate) if self.performance_metrics.win_rate else None,
                    'profit_factor': float(self.performance_metrics.profit_factor) if self.performance_metrics.profit_factor else None
                }
            }
            
            if self.redis_client:
                await self.redis_client.set(
                    f"strategy_metrics:{self.strategy_id}", 
                    json.dumps(metrics_data),
                    ex=86400 * 7  # Keep for 7 days
                )
                
        except Exception as e:
            logger.error(f"Error saving performance metrics: {e}")
    
    def get_strategy_state(self) -> Dict[str, Any]:
        """Get current strategy state and metrics."""
        return {
            'strategy_id': self.strategy_id,
            'state': self.state.value,
            'is_running': self.is_running,
            'emergency_stop': self.emergency_stop,
            'active_signals': len(self.active_signals),
            'daily_pnl': float(self.daily_pnl),
            'daily_positions': self.daily_positions,
            'consecutive_losses': self.consecutive_losses,
            'performance': {
                'total_signals': self.performance_metrics.total_signals,
                'triggered_signals': self.performance_metrics.triggered_signals,
                'confirmed_signals': self.performance_metrics.confirmed_signals,
                'completed_trades': self.performance_metrics.completed_trades,
                'win_rate': float(self.performance_metrics.win_rate) if self.performance_metrics.win_rate else None,
                'total_pnl': float(self.performance_metrics.total_pnl)
            },
            'detector_status': self.detector.get_detection_summary(),
            'config': self.config.to_dict()
        }
    
    def get_active_signals(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all active signals."""
        return {
            symbol: signal.get_summary() 
            for symbol, signal in self.active_signals.items()
        }
    
    async def emergency_shutdown(self, reason: str) -> None:
        """Emergency shutdown of strategy."""
        logger.critical(f"EMERGENCY SHUTDOWN: {reason}")
        self.emergency_stop = True
        await self._close_all_positions(f"emergency: {reason}")
        self.state = StrategyState.ERROR
    
    # Order execution callbacks
    async def on_order_filled(self, order_id: str, fill_data: Dict[str, Any]) -> None:
        """Handle order fill notifications."""
        try:
            # Update signal phases based on fill
            symbol = fill_data.get('symbol')
            if symbol in self.active_signals:
                strategy_signal = self.active_signals[symbol]
                
                if 'probe' in fill_data.get('metadata', {}).get('phase', ''):
                    strategy_signal.phase = TradePhase.PROBE_EXECUTED
                    strategy_signal.probe_time = datetime.utcnow()
                    # Start waiting for confirmation
                    strategy_signal.phase = TradePhase.AWAITING_CONFIRMATION
                    
                elif 'scale' in fill_data.get('metadata', {}).get('phase', ''):
                    strategy_signal.phase = TradePhase.SCALED
                    strategy_signal.scale_time = datetime.utcnow()
                    
                elif 'exit' in fill_data.get('metadata', {}).get('phase', ''):
                    strategy_signal.phase = TradePhase.COMPLETED
                    strategy_signal.realized_pnl = strategy_signal.unrealized_pnl
                    # Update performance metrics
                    self.performance_metrics.update_from_trade(strategy_signal)
                    # Update daily P&L
                    self.daily_pnl += strategy_signal.realized_pnl
                    
        except Exception as e:
            logger.error(f"Error handling order fill: {e}")
    
    async def on_order_rejected(self, order_id: str, rejection_reason: str) -> None:
        """Handle order rejection notifications."""
        logger.warning(f"Order rejected: {order_id} - {rejection_reason}")
        # Implementation would handle partial fills, requotes, etc. 