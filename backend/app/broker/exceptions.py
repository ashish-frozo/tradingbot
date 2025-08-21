"""
Broker-specific exceptions for Dhan-Tradehull integration.

This module contains custom exceptions for handling Dhan API errors,
trading-specific errors, and broker-related operational issues.
"""

from typing import Dict, Any, Optional
from app.core.exceptions import TradingException


class DhanAPIException(TradingException):
    """Base exception for Dhan API related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "DHAN_API_ERROR",
        details: Optional[Dict[str, Any]] = None,
        api_error_code: Optional[str] = None,
        api_error_message: Optional[str] = None
    ):
        super().__init__(message, error_code, details)
        self.api_error_code = api_error_code
        self.api_error_message = api_error_message


class DhanAuthenticationException(DhanAPIException):
    """Authentication related errors."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DHAN_AUTH_ERROR",
            details=details
        )


class DhanTokenExpiredException(DhanAuthenticationException):
    """Token expired or invalid."""
    
    def __init__(
        self,
        message: str = "Access token expired or invalid",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details
        )
        self.error_code = "DHAN_TOKEN_EXPIRED"


class DhanRateLimitException(DhanAPIException):
    """Rate limit exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DHAN_RATE_LIMIT",
            details=details
        )
        self.retry_after = retry_after


class DhanOrderException(DhanAPIException):
    """Order related errors."""
    
    def __init__(
        self,
        message: str,
        order_id: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DHAN_ORDER_ERROR",
            details=details
        )
        self.order_id = order_id
        self.rejection_reason = rejection_reason


class DhanOrderRejectionException(DhanOrderException):
    """Order rejection specific errors."""
    
    def __init__(
        self,
        message: str,
        order_id: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        rejection_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            order_id=order_id,
            rejection_reason=rejection_reason,
            details=details
        )
        self.error_code = "DHAN_ORDER_REJECTED"
        self.rejection_code = rejection_code


class DhanInsufficientFundsException(DhanOrderRejectionException):
    """Insufficient funds for order."""
    
    def __init__(
        self,
        required_amount: Optional[float] = None,
        available_amount: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = "Insufficient funds for order"
        if required_amount and available_amount:
            message += f" (Required: ₹{required_amount:.2f}, Available: ₹{available_amount:.2f})"
        
        super().__init__(
            message=message,
            rejection_reason="INSUFFICIENT_FUNDS",
            rejection_code="RMS_FUNDS",
            details=details
        )
        self.required_amount = required_amount
        self.available_amount = available_amount


class DhanPositionLimitException(DhanOrderRejectionException):
    """Position limit exceeded."""
    
    def __init__(
        self,
        symbol: Optional[str] = None,
        current_position: Optional[int] = None,
        position_limit: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = "Position limit exceeded"
        if symbol:
            message += f" for {symbol}"
        if current_position and position_limit:
            message += f" (Current: {current_position}, Limit: {position_limit})"
        
        super().__init__(
            message=message,
            rejection_reason="POSITION_LIMIT_EXCEEDED",
            rejection_code="RMS_POSITION_LIMIT",
            details=details
        )
        self.symbol = symbol
        self.current_position = current_position
        self.position_limit = position_limit


class DhanOrderModificationException(DhanOrderException):
    """Order modification related errors."""
    
    def __init__(
        self,
        message: str,
        order_id: Optional[str] = None,
        modification_count: Optional[int] = None,
        max_modifications: int = 20,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            order_id=order_id,
            details=details
        )
        self.error_code = "DHAN_ORDER_MODIFICATION_ERROR"
        self.modification_count = modification_count
        self.max_modifications = max_modifications


class DhanMarketDataException(DhanAPIException):
    """Market data related errors."""
    
    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DHAN_MARKET_DATA_ERROR",
            details=details
        )
        self.symbol = symbol
        self.exchange = exchange


class DhanSymbolNotFoundException(DhanMarketDataException):
    """Symbol not found in market data."""
    
    def __init__(
        self,
        symbol: str,
        exchange: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Symbol '{symbol}' not found"
        if exchange:
            message += f" on {exchange}"
        
        super().__init__(
            message=message,
            symbol=symbol,
            exchange=exchange,
            details=details
        )
        self.error_code = "DHAN_SYMBOL_NOT_FOUND"


class DhanMarketClosedException(DhanAPIException):
    """Market is closed for trading."""
    
    def __init__(
        self,
        market: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = "Market is closed for trading"
        if market:
            message += f" ({market})"
        
        super().__init__(
            message=message,
            error_code="DHAN_MARKET_CLOSED",
            details=details
        )
        self.market = market


class DhanNetworkException(DhanAPIException):
    """Network related errors."""
    
    def __init__(
        self,
        message: str = "Network error occurred",
        timeout: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DHAN_NETWORK_ERROR",
            details=details
        )
        self.timeout = timeout


class DhanServerException(DhanAPIException):
    """Dhan server errors (5xx status codes)."""
    
    def __init__(
        self,
        message: str = "Dhan server error",
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DHAN_SERVER_ERROR",
            details=details
        )
        self.status_code = status_code


class DhanConfigurationException(DhanAPIException):
    """Configuration related errors."""
    
    def __init__(
        self,
        message: str,
        missing_config: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="DHAN_CONFIG_ERROR",
            details=details
        )
        self.missing_config = missing_config


# Error code mapping for common Dhan API errors
DHAN_ERROR_CODE_MAP = {
    "AUTH001": DhanAuthenticationException,
    "AUTH002": DhanTokenExpiredException,
    "ORD001": DhanOrderRejectionException,
    "ORD002": DhanInsufficientFundsException,
    "ORD003": DhanPositionLimitException,
    "ORD004": DhanOrderModificationException,
    "MKT001": DhanMarketDataException,
    "MKT002": DhanSymbolNotFoundException,
    "MKT003": DhanMarketClosedException,
    "NET001": DhanNetworkException,
    "SRV001": DhanServerException,
    "CFG001": DhanConfigurationException,
}

# Common rejection reason mapping
REJECTION_REASON_MAP = {
    "INSUFFICIENT_FUNDS": DhanInsufficientFundsException,
    "POSITION_LIMIT_EXCEEDED": DhanPositionLimitException,
    "ORDER_LIMIT_EXCEEDED": DhanOrderRejectionException,
    "INVALID_PRICE": DhanOrderRejectionException,
    "MARKET_CLOSED": DhanMarketClosedException,
    "SYMBOL_NOT_FOUND": DhanSymbolNotFoundException,
    "INVALID_QUANTITY": DhanOrderRejectionException,
    "RISK_MANAGEMENT": DhanOrderRejectionException,
}


def create_dhan_exception_from_api_error(
    api_error_code: str,
    api_error_message: str,
    details: Optional[Dict[str, Any]] = None
) -> DhanAPIException:
    """
    Create appropriate Dhan exception from API error response.
    
    Args:
        api_error_code: Error code from Dhan API
        api_error_message: Error message from Dhan API
        details: Additional error details
        
    Returns:
        Appropriate DhanAPIException subclass
    """
    exception_class = DHAN_ERROR_CODE_MAP.get(api_error_code, DhanAPIException)
    
    return exception_class(
        message=api_error_message,
        api_error_code=api_error_code,
        api_error_message=api_error_message,
        details=details
    )


def create_dhan_exception_from_rejection(
    rejection_reason: str,
    order_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> DhanOrderRejectionException:
    """
    Create appropriate Dhan exception from order rejection.
    
    Args:
        rejection_reason: Rejection reason from API
        order_id: Order ID that was rejected
        details: Additional rejection details
        
    Returns:
        Appropriate DhanOrderRejectionException subclass
    """
    exception_class = REJECTION_REASON_MAP.get(
        rejection_reason,
        DhanOrderRejectionException
    )
    
    if exception_class == DhanInsufficientFundsException:
        return exception_class(
            required_amount=details.get("required_amount") if details else None,
            available_amount=details.get("available_amount") if details else None,
            details=details
        )
    elif exception_class == DhanPositionLimitException:
        return exception_class(
            symbol=details.get("symbol") if details else None,
            current_position=details.get("current_position") if details else None,
            position_limit=details.get("position_limit") if details else None,
            details=details
        )
    else:
        return exception_class(
            message=f"Order rejected: {rejection_reason}",
            order_id=order_id,
            rejection_reason=rejection_reason,
            details=details
        )


def is_retryable_error(exception: Exception) -> bool:
    """
    Check if an error is retryable.
    
    Args:
        exception: Exception to check
        
    Returns:
        True if error is retryable, False otherwise
    """
    # Network errors are generally retryable
    if isinstance(exception, DhanNetworkException):
        return True
    
    # Server errors (5xx) are retryable
    if isinstance(exception, DhanServerException):
        return True
    
    # Rate limit errors are retryable after delay
    if isinstance(exception, DhanRateLimitException):
        return True
    
    # Authentication errors are not retryable without new token
    if isinstance(exception, DhanAuthenticationException):
        return False
    
    # Order rejections are generally not retryable
    if isinstance(exception, DhanOrderRejectionException):
        return False
    
    # Configuration errors are not retryable
    if isinstance(exception, DhanConfigurationException):
        return False
    
    # Default to non-retryable for safety
    return False


def get_retry_delay(exception: Exception) -> Optional[float]:
    """
    Get recommended retry delay for an exception.
    
    Args:
        exception: Exception to get retry delay for
        
    Returns:
        Retry delay in seconds, or None if not retryable
    """
    if not is_retryable_error(exception):
        return None
    
    if isinstance(exception, DhanRateLimitException):
        # Use the retry_after from rate limit response
        return exception.retry_after or 1.0
    
    if isinstance(exception, DhanNetworkException):
        # Short delay for network errors
        return 0.5
    
    if isinstance(exception, DhanServerException):
        # Longer delay for server errors
        return 2.0
    
    # Default retry delay
    return 1.0 