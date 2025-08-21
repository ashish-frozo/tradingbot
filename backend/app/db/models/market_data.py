"""
Market Data Models
Database models for storing various types of market data with different retention periods
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum

from sqlmodel import SQLModel, Field, Column, JSON, UniqueConstraint, Index

class DataType(str, Enum):
    """Types of market data"""
    RAW_TICK = "raw_tick"           # Raw tick data from WebSocket
    LTP = "ltp"                     # Last traded price
    OPTION_CHAIN = "option_chain"   # Option chain data
    DERIVED_METRIC = "derived_metric"  # Calculated metrics
    MINUTE_BAR = "minute_bar"       # OHLCV minute bars
    
class MarketDataSource(str, Enum):
    """Sources of market data"""
    TRADEHULL_WS = "tradehull_ws"   # Tradehull WebSocket
    TRADEHULL_API = "tradehull_api" # Tradehull REST API
    CALCULATED = "calculated"       # Internal calculations
    
# Raw WebSocket Data (7 days retention)
class RawTickData(SQLModel, table=True):
    """
    Raw tick data from WebSocket feeds
    Retention: 7 days (short-term, high frequency)
    """
    __tablename__ = "raw_tick_data"
    __table_args__ = (
        Index("idx_raw_tick_symbol_timestamp", "symbol", "timestamp"),
        Index("idx_raw_tick_timestamp", "timestamp"),
        Index("idx_raw_tick_source", "source"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Market identifiers
    symbol: str = Field(max_length=50, index=True)
    exchange: str = Field(max_length=20)
    segment: str = Field(max_length=20)
    security_id: str = Field(max_length=50)
    
    # Timestamp (UTC)
    timestamp: datetime = Field(index=True)
    
    # Raw data fields
    ltp: Optional[Decimal] = Field(decimal_places=2)
    bid_price: Optional[Decimal] = Field(decimal_places=2) 
    ask_price: Optional[Decimal] = Field(decimal_places=2)
    bid_qty: Optional[int]
    ask_qty: Optional[int]
    volume: Optional[int]
    open_interest: Optional[int]
    
    # OHLC (if available in tick)
    open_price: Optional[Decimal] = Field(decimal_places=2)
    high_price: Optional[Decimal] = Field(decimal_places=2)
    low_price: Optional[Decimal] = Field(decimal_places=2)
    close_price: Optional[Decimal] = Field(decimal_places=2)
    
    # Source and metadata
    source: MarketDataSource = Field(default=MarketDataSource.TRADEHULL_WS)
    raw_data: Dict[str, Any] = Field(sa_column=Column(JSON), default={})
    
    # System fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processing_latency_ms: Optional[float]  # Time from market to storage

# Derived Metrics (2 years retention)
class DerivedMetric(SQLModel, table=True):
    """
    Derived metrics and calculated values
    Retention: 2 years (long-term analytics)
    """
    __tablename__ = "derived_metrics"
    __table_args__ = (
        Index("idx_derived_symbol_timestamp", "symbol", "timestamp"),
        Index("idx_derived_metric_type", "metric_type"),
        Index("idx_derived_timestamp", "timestamp"),
        UniqueConstraint("symbol", "metric_type", "timestamp", "timeframe", name="uq_metric_symbol_type_time"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Market identifiers
    symbol: str = Field(max_length=50, index=True)
    
    # Metric identification
    metric_type: str = Field(max_length=50)  # e.g., "moving_average", "volatility", "volume_profile"
    timeframe: str = Field(max_length=20)    # e.g., "1m", "5m", "15m", "1h", "1d"
    
    # Timestamp (UTC)
    timestamp: datetime = Field(index=True)
    
    # Metric values
    value: Optional[Decimal] = Field(decimal_places=6)
    value_json: Optional[Dict[str, Any]] = Field(sa_column=Column(JSON))  # For complex metrics
    
    # Statistical properties
    count: Optional[int]        # Sample count
    std_dev: Optional[Decimal] = Field(decimal_places=6)
    min_value: Optional[Decimal] = Field(decimal_places=6)
    max_value: Optional[Decimal] = Field(decimal_places=6)
    
    # Metadata
    calculation_method: Optional[str] = Field(max_length=100)
    parameters: Dict[str, Any] = Field(sa_column=Column(JSON), default={})
    
    # System fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    calculated_by: str = Field(max_length=50, default="system")

# Minute Bars (90 days retention)
class MinuteBar(SQLModel, table=True):
    """
    OHLCV minute bars for technical analysis
    Retention: 90 days (medium-term trading)
    """
    __tablename__ = "minute_bars"
    __table_args__ = (
        Index("idx_minute_bar_symbol_timestamp", "symbol", "timestamp"),
        Index("idx_minute_bar_timestamp", "timestamp"),
        UniqueConstraint("symbol", "timestamp", name="uq_minute_bar_symbol_time"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Market identifiers  
    symbol: str = Field(max_length=50, index=True)
    exchange: str = Field(max_length=20)
    segment: str = Field(max_length=20)
    
    # Timestamp (start of minute, UTC)
    timestamp: datetime = Field(index=True)
    
    # OHLCV data
    open_price: Decimal = Field(decimal_places=2)
    high_price: Decimal = Field(decimal_places=2) 
    low_price: Decimal = Field(decimal_places=2)
    close_price: Decimal = Field(decimal_places=2)
    volume: int = Field(default=0)
    
    # Option-specific fields
    open_interest: Optional[int]
    open_interest_change: Optional[int]
    
    # Price action metrics
    vwap: Optional[Decimal] = Field(decimal_places=2)  # Volume weighted average price
    tick_count: Optional[int]  # Number of ticks in this minute
    
    # Spread and liquidity metrics
    avg_bid_ask_spread: Optional[Decimal] = Field(decimal_places=4)
    avg_bid_qty: Optional[int]
    avg_ask_qty: Optional[int]
    
    # Greeks (for options)
    delta: Optional[Decimal] = Field(decimal_places=6)
    gamma: Optional[Decimal] = Field(decimal_places=6)
    theta: Optional[Decimal] = Field(decimal_places=6)
    vega: Optional[Decimal] = Field(decimal_places=6)
    iv: Optional[Decimal] = Field(decimal_places=4)  # Implied volatility
    
    # System fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: MarketDataSource = Field(default=MarketDataSource.CALCULATED)
    
    # Quality metrics
    completeness_pct: Optional[float]  # Percentage of expected ticks received
    data_quality_score: Optional[float]  # Overall quality score (0-1)

# Market Data Summary (for dashboard)
class MarketDataSummary(SQLModel, table=True):
    """
    Daily summary statistics for market data
    Used for quick dashboard queries and health monitoring
    """
    __tablename__ = "market_data_summary"
    __table_args__ = (
        Index("idx_summary_symbol_date", "symbol", "date"),
        UniqueConstraint("symbol", "date", name="uq_summary_symbol_date"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Market identifiers
    symbol: str = Field(max_length=50, index=True)
    date: datetime = Field(index=True)  # Date only (YYYY-MM-DD)
    
    # Volume and activity
    total_volume: Optional[int]
    total_tick_count: Optional[int] 
    active_minutes: Optional[int]  # Minutes with actual trading
    
    # Price statistics  
    day_open: Optional[Decimal] = Field(decimal_places=2)
    day_high: Optional[Decimal] = Field(decimal_places=2)
    day_low: Optional[Decimal] = Field(decimal_places=2)
    day_close: Optional[Decimal] = Field(decimal_places=2)
    day_change_pct: Optional[Decimal] = Field(decimal_places=4)
    
    # Volatility metrics
    realized_volatility: Optional[Decimal] = Field(decimal_places=6)
    price_range_pct: Optional[Decimal] = Field(decimal_places=4)
    
    # Data quality metrics
    avg_latency_ms: Optional[float]
    data_completeness_pct: Optional[float]
    feed_uptime_pct: Optional[float]
    
    # System fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)) 