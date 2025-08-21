"""
Trading enums for Dhan-Tradehull API integration.

This module contains all the enumeration types used in trading operations
including transaction types, order types, exchange segments, and validity types.
"""

from enum import Enum


class TransactionType(Enum):
    """Transaction type for orders."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "SL"
    STOP_LOSS_MARKET = "SLM"


class Validity(Enum):
    """Order validity enumeration."""
    DAY = "DAY"
    IOC = "IOC"  # Immediate or Cancel
    GTD = "GTD"  # Good Till Date


class ExchangeSegment(Enum):
    """Exchange segment enumeration."""
    NSE_EQ = "NSE_EQ"      # NSE Equity
    NSE_FNO = "NSE_FNO"    # NSE Futures & Options
    BSE_EQ = "BSE_EQ"      # BSE Equity
    BSE_FNO = "BSE_FNO"    # BSE Futures & Options
    MCX_COMM = "MCX_COMM"  # MCX Commodities


class ProductType(Enum):
    """Product type enumeration."""
    CNC = "CNC"    # Cash and Carry (Delivery)
    MIS = "MIS"    # Margin Intraday Squareoff
    NRML = "NRML"  # Normal (Carry Forward)


class PositionType(Enum):
    """Position type enumeration."""
    LONG = "LONG"
    SHORT = "SHORT"


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ExchangeCode(Enum):
    """Exchange code enumeration."""
    NSE = "NSE"
    BSE = "BSE"
    MCX = "MCX"


class InstrumentType(Enum):
    """Instrument type enumeration."""
    EQUITY = "EQUITY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    CURRENCY = "CURRENCY"
    COMMODITY = "COMMODITY"


class OptionType(Enum):
    """Option type enumeration."""
    CALL = "CALL"
    PUT = "PUT"


class AMOTime(Enum):
    """After Market Order timing enumeration."""
    OPEN = "OPEN"        # Market open
    OPEN_30 = "OPEN_30"  # 30 minutes after market open
    OPEN_60 = "OPEN_60"  # 60 minutes after market open


class PriceType(Enum):
    """Price type for market data."""
    LTP = "LTP"          # Last Traded Price
    OPEN = "OPEN"        # Opening price
    HIGH = "HIGH"        # Day high
    LOW = "LOW"          # Day low
    CLOSE = "CLOSE"      # Previous close
    VOLUME = "VOLUME"    # Volume
    OI = "OI"           # Open Interest


class RejectionReason(Enum):
    """Common order rejection reasons."""
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    INVALID_PRICE = "INVALID_PRICE"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
    MARKET_CLOSED = "MARKET_CLOSED"
    POSITION_LIMIT_EXCEEDED = "POSITION_LIMIT_EXCEEDED"
    ORDER_LIMIT_EXCEEDED = "ORDER_LIMIT_EXCEEDED"
    INVALID_ORDER_TYPE = "INVALID_ORDER_TYPE"
    PRICE_OUT_OF_RANGE = "PRICE_OUT_OF_RANGE"


class MarketStatus(Enum):
    """Market status enumeration."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    PRE_OPEN = "PRE_OPEN"
    POST_CLOSE = "POST_CLOSE"


class TimeInForce(Enum):
    """Time in force for orders."""
    DAY = "DAY"
    IOC = "IOC"
    FOK = "FOK"  # Fill or Kill
    GTD = "GTD"  # Good Till Date
    GTC = "GTC"  # Good Till Cancelled


# Mapping dictionaries for conversions
TRANSACTION_TYPE_MAP = {
    "B": TransactionType.BUY,
    "S": TransactionType.SELL,
    "BUY": TransactionType.BUY,
    "SELL": TransactionType.SELL
}

ORDER_TYPE_MAP = {
    "MKT": OrderType.MARKET,
    "LMT": OrderType.LIMIT,
    "SL": OrderType.STOP_LOSS,
    "SLM": OrderType.STOP_LOSS_MARKET,
    "MARKET": OrderType.MARKET,
    "LIMIT": OrderType.LIMIT
}

EXCHANGE_SEGMENT_MAP = {
    "NSE": ExchangeSegment.NSE_EQ,
    "NFO": ExchangeSegment.NSE_FNO,
    "BSE": ExchangeSegment.BSE_EQ,
    "BFO": ExchangeSegment.BSE_FNO,
    "MCX": ExchangeSegment.MCX_COMM
}


def get_transaction_type(value: str) -> TransactionType:
    """Get TransactionType enum from string value."""
    return TRANSACTION_TYPE_MAP.get(value.upper(), TransactionType.BUY)


def get_order_type(value: str) -> OrderType:
    """Get OrderType enum from string value."""
    return ORDER_TYPE_MAP.get(value.upper(), OrderType.MARKET)


def get_exchange_segment(value: str) -> ExchangeSegment:
    """Get ExchangeSegment enum from string value."""
    return EXCHANGE_SEGMENT_MAP.get(value.upper(), ExchangeSegment.NSE_EQ) 