"""
Trading Strategies Module
Provides the strategy engine with pluggable architecture for trading strategies.

This module contains:
- BaseStrategy: Abstract base class for all strategies
- StrategyRegistry: Dynamic loading and management system
- Strategy implementations (vol_oi, etc.)
"""

from app.strategies.base import (
    BaseStrategy,
    TradingSignal,
    MarketData,
    StrategyState,
    SignalType,
    SignalStrength
)

from app.strategies.registry import (
    StrategyRegistry,
    strategy_registry,
    register_strategy
)

# Import Volume-OI strategy
from app.strategies.vol_oi import VolumeOIStrategy, VolumeOIConfig

# Register strategies
strategy_registry.register_strategy(VolumeOIStrategy, 'volume_oi_confirm')

__all__ = [
    # Base classes
    'BaseStrategy',
    'TradingSignal', 
    'MarketData',
    'StrategyState',
    'SignalType',
    'SignalStrength',
    
    # Registry system
    'StrategyRegistry',
    'strategy_registry',
    'register_strategy',
    
    # Strategy implementations
    'VolumeOIStrategy',
    'VolumeOIConfig'
] 