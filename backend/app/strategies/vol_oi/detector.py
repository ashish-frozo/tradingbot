"""
Volume-OI Detection Engine
Implements detection logic for volume spikes, price jumps, and OI changes.

This module contains the core detection algorithms for:
- Volume spike detection (>3σ AND >5× 1-minute average)
- Mid-price jump detection (≥0.15% within 2 seconds)
- OI change confirmation (>1.5σ within 240 seconds)
"""

import asyncio
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Tuple, Deque, Any
import statistics
import math

from app.core.logging import get_logger
from app.strategies.base import MarketData
from app.strategies.vol_oi.models import (
    VolumeSignal, 
    PriceJumpSignal, 
    OISignal, 
    SignalStrength
)
from app.strategies.vol_oi.config import VolumeOIConfig
from app.data.processor import StatisticalProcessor


logger = get_logger(__name__)


class VolumeOIDetector:
    """
    Detection engine for Volume-OI strategy signals.
    
    Implements real-time detection of volume spikes, price jumps, and OI changes
    using rolling statistics and configurable thresholds.
    """
    
    def __init__(self, config: VolumeOIConfig, redis_client=None):
        self.config = config
        self.redis_client = redis_client
        
        # Data buffers for rolling calculations
        self.volume_buffer: Dict[str, Deque[Tuple[datetime, int]]] = {}
        self.price_buffer: Dict[str, Deque[Tuple[datetime, Decimal]]] = {}
        self.oi_buffer: Dict[str, Deque[Tuple[datetime, int]]] = {}
        
        # Rolling statistics
        self.volume_stats: Dict[str, Dict[str, float]] = {}
        self.oi_stats: Dict[str, Dict[str, float]] = {}
        
        # Trigger tracking for confirmation windows
        self.trigger_times: Dict[str, datetime] = {}
        
        # Statistical processor for advanced calculations
        self.stat_processor = StatisticalProcessor(redis_client)
        
        logger.info(f"VolumeOI Detector initialized with config: {config.strategy_name}")
    
    async def process_market_data(self, market_data: MarketData) -> Tuple[Optional[VolumeSignal], Optional[PriceJumpSignal], Optional[OISignal]]:
        """
        Process market data and detect volume spikes, price jumps, and OI changes.
        
        Args:
            market_data: Latest market data snapshot
            
        Returns:
            Tuple of (VolumeSignal, PriceJumpSignal, OISignal) - None if no signal detected
        """
        try:
            symbol = market_data.symbol
            
            # Update data buffers
            await self._update_buffers(market_data)
            
            # Detect signals
            volume_signal = await self._detect_volume_spike(market_data)
            price_signal = await self._detect_price_jump(market_data)
            oi_signal = await self._detect_oi_change(market_data)
            
            return volume_signal, price_signal, oi_signal
            
        except Exception as e:
            logger.error(f"Error processing market data for {market_data.symbol}: {e}")
            return None, None, None
    
    async def _update_buffers(self, market_data: MarketData) -> None:
        """Update rolling data buffers for statistics calculation."""
        symbol = market_data.symbol
        timestamp = market_data.timestamp
        
        # Initialize buffers if needed
        if symbol not in self.volume_buffer:
            self.volume_buffer[symbol] = deque(maxlen=self.config.volume_lookback_periods)
            self.price_buffer[symbol] = deque(maxlen=10)  # Keep last 10 prices for jump detection
            self.oi_buffer[symbol] = deque(maxlen=self.config.oi_lookback_periods)
            self.volume_stats[symbol] = {}
            self.oi_stats[symbol] = {}
        
        # Add new data points
        self.volume_buffer[symbol].append((timestamp, market_data.volume))
        self.price_buffer[symbol].append((timestamp, market_data.ltp))
        self.oi_buffer[symbol].append((timestamp, market_data.open_interest))
        
        # Update rolling statistics
        await self._update_rolling_stats(symbol)
    
    async def _update_rolling_stats(self, symbol: str) -> None:
        """Update rolling statistics for volume and OI."""
        try:
            # Volume statistics
            if len(self.volume_buffer[symbol]) >= 2:
                volumes = [vol for _, vol in self.volume_buffer[symbol]]
                self.volume_stats[symbol] = {
                    'mean': statistics.mean(volumes),
                    'stddev': statistics.stdev(volumes) if len(volumes) > 1 else 0,
                    'min': min(volumes),
                    'max': max(volumes),
                    'count': len(volumes)
                }
                
                # Calculate 1-minute average (last 20 periods assuming 3-second intervals)
                recent_volumes = volumes[-20:] if len(volumes) >= 20 else volumes
                self.volume_stats[symbol]['1min_avg'] = statistics.mean(recent_volumes)
            
            # OI statistics
            if len(self.oi_buffer[symbol]) >= 2:
                ois = [oi for _, oi in self.oi_buffer[symbol]]
                oi_changes = []
                for i in range(1, len(ois)):
                    change = ois[i] - ois[i-1]
                    oi_changes.append(change)
                
                if oi_changes:
                    self.oi_stats[symbol] = {
                        'mean_change': statistics.mean(oi_changes),
                        'stddev_change': statistics.stdev(oi_changes) if len(oi_changes) > 1 else 0,
                        'current_oi': ois[-1],
                        'previous_oi': ois[-2] if len(ois) >= 2 else ois[-1]
                    }
                    
        except Exception as e:
            logger.error(f"Error updating rolling stats for {symbol}: {e}")
    
    async def _detect_volume_spike(self, market_data: MarketData) -> Optional[VolumeSignal]:
        """
        Detect volume spike: >3σ AND >5× 1-minute average.
        
        Args:
            market_data: Current market data
            
        Returns:
            VolumeSignal if spike detected, None otherwise
        """
        try:
            symbol = market_data.symbol
            current_volume = market_data.volume
            
            # Need sufficient data for statistics
            if (symbol not in self.volume_stats or 
                len(self.volume_buffer[symbol]) < self.config.volume_lookback_periods // 2):
                return None
            
            stats = self.volume_stats[symbol]
            
            # Check minimum volume threshold
            if current_volume < self.config.min_volume_threshold:
                return None
            
            # Calculate z-score
            if stats['stddev'] == 0:
                volume_zscore = 0
            else:
                volume_zscore = (current_volume - stats['mean']) / stats['stddev']
            
            # Calculate multiplier vs 1-minute average
            volume_multiplier = current_volume / stats['1min_avg'] if stats['1min_avg'] > 0 else 0
            
            # Create volume signal
            volume_signal = VolumeSignal(
                symbol=symbol,
                timestamp=market_data.timestamp,
                current_volume=current_volume,
                volume_1min_avg=int(stats['1min_avg']),
                volume_stddev=Decimal(str(stats['stddev'])),
                volume_zscore=Decimal(str(volume_zscore)),
                volume_multiplier=Decimal(str(volume_multiplier)),
                strength=SignalStrength.WEAK,  # Will be set in __post_init__
                is_spike=False  # Will be set in __post_init__
            )
            
            # Log significant volume activity
            if volume_signal.is_spike:
                logger.info(f"Volume spike detected: {symbol} - "
                          f"Volume: {current_volume:,} "
                          f"(Z-score: {volume_zscore:.2f}, "
                          f"Multiplier: {volume_multiplier:.2f}x)")
            
            return volume_signal if volume_signal.is_spike else None
            
        except Exception as e:
            logger.error(f"Error detecting volume spike for {symbol}: {e}")
            return None
    
    async def _detect_price_jump(self, market_data: MarketData) -> Optional[PriceJumpSignal]:
        """
        Detect price jump: ≥0.15% within 2 seconds.
        
        Args:
            market_data: Current market data
            
        Returns:
            PriceJumpSignal if jump detected, None otherwise
        """
        try:
            symbol = market_data.symbol
            current_price = market_data.ltp
            current_time = market_data.timestamp
            
            # Need at least 2 price points
            if symbol not in self.price_buffer or len(self.price_buffer[symbol]) < 2:
                return None
            
            # Look for price jumps within the time window
            time_threshold = current_time - timedelta(seconds=self.config.price_jump_window_seconds)
            
            for past_time, past_price in reversed(list(self.price_buffer[symbol])[:-1]):
                if past_time < time_threshold:
                    break
                
                # Calculate price change
                if past_price > 0:
                    price_change_pct = abs((current_price - past_price) / past_price * 100)
                    time_diff = (current_time - past_time).total_seconds()
                    
                    # Check if jump threshold met
                    if (price_change_pct >= float(self.config.price_jump_threshold_pct) and 
                        time_diff <= self.config.price_jump_window_seconds):
                        
                        price_signal = PriceJumpSignal(
                            symbol=symbol,
                            timestamp=current_time,
                            previous_price=past_price,
                            current_price=current_price,
                            price_change_pct=Decimal(str(price_change_pct)),
                            time_window_seconds=int(time_diff),
                            is_jump=True,  # Will be validated in __post_init__
                            direction="up" if current_price > past_price else "down"
                        )
                        
                        logger.info(f"Price jump detected: {symbol} - "
                                  f"Change: {price_change_pct:.3f}% "
                                  f"in {time_diff:.1f}s "
                                  f"({past_price} → {current_price})")
                        
                        return price_signal
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting price jump for {symbol}: {e}")
            return None
    
    async def _detect_oi_change(self, market_data: MarketData) -> Optional[OISignal]:
        """
        Detect OI change confirmation: >1.5σ within 240 seconds of trigger.
        
        Args:
            market_data: Current market data
            
        Returns:
            OISignal if confirmation detected, None otherwise
        """
        try:
            symbol = market_data.symbol
            current_oi = market_data.open_interest
            current_time = market_data.timestamp
            
            # Check if we have a trigger to confirm
            if symbol not in self.trigger_times:
                return None
            
            # Check if within confirmation window
            trigger_time = self.trigger_times[symbol]
            time_since_trigger = (current_time - trigger_time).total_seconds()
            
            if time_since_trigger > self.config.oi_confirmation_window_seconds:
                # Remove expired trigger
                del self.trigger_times[symbol]
                return None
            
            # Need sufficient OI data
            if (symbol not in self.oi_stats or 
                len(self.oi_buffer[symbol]) < self.config.oi_lookback_periods // 2):
                return None
            
            # Check minimum OI threshold
            if current_oi < self.config.min_oi_threshold:
                return None
            
            stats = self.oi_stats[symbol]
            previous_oi = stats['previous_oi']
            oi_change = current_oi - previous_oi
            
            # Calculate z-score of OI change
            if stats['stddev_change'] == 0:
                oi_zscore = 0
            else:
                oi_zscore = (oi_change - stats['mean_change']) / stats['stddev_change']
            
            # Create OI signal
            oi_signal = OISignal(
                symbol=symbol,
                timestamp=current_time,
                previous_oi=previous_oi,
                current_oi=current_oi,
                oi_change=oi_change,
                oi_change_pct=Decimal('0'),  # Will be calculated in __post_init__
                oi_stddev=Decimal(str(stats['stddev_change'])),
                oi_zscore=Decimal(str(oi_zscore)),
                time_since_trigger_seconds=int(time_since_trigger),
                is_confirmation=False,  # Will be set in __post_init__
                strength=SignalStrength.WEAK  # Will be set in __post_init__
            )
            
            # Log significant OI changes
            if oi_signal.is_confirmation:
                logger.info(f"OI confirmation detected: {symbol} - "
                          f"Change: {oi_change:,} "
                          f"(Z-score: {oi_zscore:.2f}) "
                          f"after {time_since_trigger:.1f}s")
                
                # Remove trigger since confirmed
                del self.trigger_times[symbol]
            
            return oi_signal if oi_signal.is_confirmation else None
            
        except Exception as e:
            logger.error(f"Error detecting OI change for {symbol}: {e}")
            return None
    
    def set_trigger(self, symbol: str, trigger_time: datetime) -> None:
        """
        Set trigger time for OI confirmation window.
        
        Args:
            symbol: Symbol to track
            trigger_time: When the volume/price trigger occurred
        """
        self.trigger_times[symbol] = trigger_time
        logger.debug(f"Trigger set for {symbol} at {trigger_time}")
    
    def clear_trigger(self, symbol: str) -> None:
        """
        Clear trigger for symbol.
        
        Args:
            symbol: Symbol to clear
        """
        if symbol in self.trigger_times:
            del self.trigger_times[symbol]
            logger.debug(f"Trigger cleared for {symbol}")
    
    def get_active_triggers(self) -> Dict[str, datetime]:
        """Get all active triggers awaiting confirmation."""
        return self.trigger_times.copy()
    
    def cleanup_expired_triggers(self) -> int:
        """
        Remove expired triggers that are beyond confirmation window.
        
        Returns:
            Number of triggers cleaned up
        """
        current_time = datetime.utcnow()
        expired_symbols = []
        
        for symbol, trigger_time in self.trigger_times.items():
            time_since_trigger = (current_time - trigger_time).total_seconds()
            if time_since_trigger > self.config.oi_confirmation_window_seconds:
                expired_symbols.append(symbol)
        
        for symbol in expired_symbols:
            del self.trigger_times[symbol]
            logger.debug(f"Expired trigger cleaned up for {symbol}")
        
        return len(expired_symbols)
    
    def get_volume_stats(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current volume statistics for symbol."""
        return self.volume_stats.get(symbol)
    
    def get_oi_stats(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current OI statistics for symbol."""
        return self.oi_stats.get(symbol)
    
    def get_buffer_sizes(self) -> Dict[str, Dict[str, int]]:
        """Get current buffer sizes for monitoring."""
        buffer_info = {}
        
        for symbol in self.volume_buffer.keys():
            buffer_info[symbol] = {
                'volume_buffer': len(self.volume_buffer[symbol]),
                'price_buffer': len(self.price_buffer[symbol]),
                'oi_buffer': len(self.oi_buffer[symbol])
            }
        
        return buffer_info
    
    def reset_symbol_data(self, symbol: str) -> None:
        """Reset all data for a specific symbol."""
        if symbol in self.volume_buffer:
            del self.volume_buffer[symbol]
        if symbol in self.price_buffer:
            del self.price_buffer[symbol]
        if symbol in self.oi_buffer:
            del self.oi_buffer[symbol]
        if symbol in self.volume_stats:
            del self.volume_stats[symbol]
        if symbol in self.oi_stats:
            del self.oi_stats[symbol]
        if symbol in self.trigger_times:
            del self.trigger_times[symbol]
        
        logger.info(f"Reset all data for symbol: {symbol}")
    
    def get_detection_summary(self) -> Dict[str, Any]:
        """Get detection engine status summary."""
        return {
            'tracked_symbols': list(self.volume_buffer.keys()),
            'active_triggers': len(self.trigger_times),
            'trigger_symbols': list(self.trigger_times.keys()),
            'buffer_sizes': self.get_buffer_sizes(),
            'config': {
                'volume_threshold_sigma': float(self.config.volume_spike_threshold_sigma),
                'volume_multiplier_threshold': float(self.config.volume_multiplier_threshold),
                'price_jump_threshold_pct': float(self.config.price_jump_threshold_pct),
                'oi_threshold_sigma': float(self.config.oi_change_threshold_sigma),
                'confirmation_window_seconds': self.config.oi_confirmation_window_seconds
            }
        } 