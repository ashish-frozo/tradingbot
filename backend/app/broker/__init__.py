"""
Broker package for Dhan-Tradehull integration.

This package provides comprehensive trading functionality including:
- Async API client wrapper
- Rate limiting and token management  
- Trading enums and exceptions
- Order and position management
"""

from .tradehull_client import DhanTradehullClient, create_dhan_client
from .enums import (
    TransactionType,
    OrderType,
    Validity,
    ExchangeSegment,
    ProductType,
    PositionType,
    OrderStatus,
    get_transaction_type,
    get_order_type,
    get_exchange_segment,
)
from .rate_limiter import (
    RateLimiter,
    OrderRateLimiter,
    MarketDataRateLimiter,
    AdaptiveRateLimiter,
)
from .token_manager import TokenManager
from .exceptions import (
    DhanAPIException,
    DhanAuthenticationException,
    DhanTokenExpiredException,
    DhanRateLimitException,
    DhanOrderException,
    DhanOrderRejectionException,
    DhanInsufficientFundsException,
    DhanPositionLimitException,
    DhanMarketDataException,
    DhanSymbolNotFoundException,
    DhanMarketClosedException,
    DhanNetworkException,
    DhanServerException,
    DhanConfigurationException,
    create_dhan_exception_from_api_error,
    create_dhan_exception_from_rejection,
    is_retryable_error,
    get_retry_delay,
)

__all__ = [
    # Main client
    "DhanTradehullClient",
    "create_dhan_client",
    
    # Enums
    "TransactionType",
    "OrderType", 
    "Validity",
    "ExchangeSegment",
    "ProductType",
    "PositionType",
    "OrderStatus",
    "get_transaction_type",
    "get_order_type",
    "get_exchange_segment",
    
    # Rate limiting
    "RateLimiter",
    "OrderRateLimiter",
    "MarketDataRateLimiter", 
    "AdaptiveRateLimiter",
    
    # Token management
    "TokenManager",
    
    # Exceptions
    "DhanAPIException",
    "DhanAuthenticationException",
    "DhanTokenExpiredException",
    "DhanRateLimitException",
    "DhanOrderException",
    "DhanOrderRejectionException",
    "DhanInsufficientFundsException",
    "DhanPositionLimitException",
    "DhanMarketDataException",
    "DhanSymbolNotFoundException",
    "DhanMarketClosedException",
    "DhanNetworkException",
    "DhanServerException",
    "DhanConfigurationException",
    "create_dhan_exception_from_api_error",
    "create_dhan_exception_from_rejection",
    "is_retryable_error",
    "get_retry_delay",
] 