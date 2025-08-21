"""
Volume + Delayed-OI Confirm Strategy Module
Implements the primary trading strategy for detecting volume spikes with OI confirmation.

This strategy module contains:
- Volume spike detection (>3σ AND >5× 1-min average)
- Mid-price jump detection (≥0.15% within 2 seconds)
- OI change confirmation (>1.5σ within 240 seconds)
- Probe and scale trading logic
- Risk management and exit conditions
"""

from app.strategies.vol_oi.detector import VolumeOIDetector
from app.strategies.vol_oi.trader import VolumeOIStrategy
from app.strategies.vol_oi.config import VolumeOIConfig
from app.strategies.vol_oi.models import (
    VolumeSignal,
    OISignal,
    PriceJumpSignal,
    StrategySignal
)

__all__ = [
    'VolumeOIDetector',
    'VolumeOIStrategy', 
    'VolumeOIConfig',
    'VolumeSignal',
    'OISignal',
    'PriceJumpSignal',
    'StrategySignal'
] 