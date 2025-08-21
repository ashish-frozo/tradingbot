"""
Exception Handling System
Custom exceptions and error handling for trading application
"""

from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, status
from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes for the trading system"""
    
    # General system errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    
    # Database errors
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    DATABASE_QUERY_ERROR = "DATABASE_QUERY_ERROR"
    DATABASE_CONSTRAINT_ERROR = "DATABASE_CONSTRAINT_ERROR"
    
    # Cache/Redis errors
    CACHE_CONNECTION_ERROR = "CACHE_CONNECTION_ERROR"
    CACHE_OPERATION_ERROR = "CACHE_OPERATION_ERROR"
    
    # Trading specific errors
    TRADING_DISABLED = "TRADING_DISABLED"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    INVALID_ORDER = "INVALID_ORDER"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    POSITION_LIMIT_EXCEEDED = "POSITION_LIMIT_EXCEEDED"
    RISK_LIMIT_EXCEEDED = "RISK_LIMIT_EXCEEDED"
    MARKET_CLOSED = "MARKET_CLOSED"
    ORDER_REJECTED = "ORDER_REJECTED"
    
    # Strategy errors
    STRATEGY_ERROR = "STRATEGY_ERROR"
    STRATEGY_NOT_FOUND = "STRATEGY_NOT_FOUND"
    INVALID_STRATEGY_CONFIG = "INVALID_STRATEGY_CONFIG"
    
    # Market data errors
    MARKET_DATA_ERROR = "MARKET_DATA_ERROR"
    MARKET_DATA_UNAVAILABLE = "MARKET_DATA_UNAVAILABLE"
    MARKET_DATA_STALE = "MARKET_DATA_STALE"
    
    # API/External service errors
    DHAN_API_ERROR = "DHAN_API_ERROR"
    DHAN_CONNECTION_ERROR = "DHAN_CONNECTION_ERROR"
    DHAN_AUTHENTICATION_ERROR = "DHAN_AUTHENTICATION_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"


class TradingException(Exception):
    """Base exception for all trading-related errors"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestion = suggestion
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        result = {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details
        }
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result


class DatabaseException(TradingException):
    """Database-related exceptions"""
    pass


class CacheException(TradingException):
    """Cache/Redis-related exceptions"""
    pass


class OrderException(TradingException):
    """Order management exceptions"""
    pass


class StrategyException(TradingException):
    """Strategy execution exceptions"""
    pass


class MarketDataException(TradingException):
    """Market data exceptions"""
    pass


class RiskManagementException(TradingException):
    """Risk management exceptions"""
    pass


class DhanAPIException(TradingException):
    """Dhan API related exceptions"""
    pass


class ValidationException(TradingException):
    """Input validation exceptions"""
    pass


# Custom HTTP exceptions with standardized format
class TradingHTTPException(HTTPException):
    """Custom HTTP exception with standardized error format"""
    
    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion
        
        # Create detailed error response
        detail = {
            "error_code": error_code.value,
            "message": message,
            "details": self.details
        }
        if suggestion:
            detail["suggestion"] = suggestion
        
        super().__init__(status_code=status_code, detail=detail, headers=headers)


# Convenience functions for common HTTP exceptions
def not_found_error(
    message: str = "Resource not found",
    details: Optional[Dict[str, Any]] = None,
    suggestion: Optional[str] = None
) -> TradingHTTPException:
    """Create a 404 Not Found error"""
    return TradingHTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        error_code=ErrorCode.NOT_FOUND,
        message=message,
        details=details,
        suggestion=suggestion
    )


def validation_error(
    message: str = "Invalid input data",
    details: Optional[Dict[str, Any]] = None,
    suggestion: Optional[str] = None
) -> TradingHTTPException:
    """Create a 422 Validation Error"""
    return TradingHTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code=ErrorCode.VALIDATION_ERROR,
        message=message,
        details=details,
        suggestion=suggestion
    )


def unauthorized_error(
    message: str = "Authentication required",
    details: Optional[Dict[str, Any]] = None,
    suggestion: Optional[str] = "Please provide valid authentication credentials"
) -> TradingHTTPException:
    """Create a 401 Unauthorized error"""
    return TradingHTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        error_code=ErrorCode.UNAUTHORIZED,
        message=message,
        details=details,
        suggestion=suggestion,
        headers={"WWW-Authenticate": "Bearer"}
    )


def forbidden_error(
    message: str = "Access forbidden",
    details: Optional[Dict[str, Any]] = None,
    suggestion: Optional[str] = None
) -> TradingHTTPException:
    """Create a 403 Forbidden error"""
    return TradingHTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        error_code=ErrorCode.FORBIDDEN,
        message=message,
        details=details,
        suggestion=suggestion
    )


def internal_error(
    message: str = "Internal server error",
    details: Optional[Dict[str, Any]] = None,
    suggestion: Optional[str] = "Please try again later or contact support"
) -> TradingHTTPException:
    """Create a 500 Internal Server Error"""
    return TradingHTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code=ErrorCode.INTERNAL_ERROR,
        message=message,
        details=details,
        suggestion=suggestion
    )


def rate_limit_error(
    message: str = "Rate limit exceeded",
    details: Optional[Dict[str, Any]] = None,
    retry_after: int = 60
) -> TradingHTTPException:
    """Create a 429 Rate Limit error"""
    return TradingHTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        error_code=ErrorCode.RATE_LIMITED,
        message=message,
        details=details,
        suggestion=f"Please wait {retry_after} seconds before retrying",
        headers={"Retry-After": str(retry_after)}
    )


# Trading-specific error functions
def trading_disabled_error(
    message: str = "Trading is currently disabled",
    details: Optional[Dict[str, Any]] = None
) -> TradingHTTPException:
    """Create trading disabled error"""
    return TradingHTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_code=ErrorCode.TRADING_DISABLED,
        message=message,
        details=details,
        suggestion="Check system status or contact administrator"
    )


def insufficient_funds_error(
    required_amount: float,
    available_amount: float,
    currency: str = "INR"
) -> TradingHTTPException:
    """Create insufficient funds error"""
    return TradingHTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code=ErrorCode.INSUFFICIENT_FUNDS,
        message="Insufficient funds for this order",
        details={
            "required_amount": required_amount,
            "available_amount": available_amount,
            "currency": currency,
            "shortage": required_amount - available_amount
        },
        suggestion="Add more funds to your account or reduce order size"
    )


def position_limit_error(
    symbol: str,
    current_position: int,
    limit: int
) -> TradingHTTPException:
    """Create position limit exceeded error"""
    return TradingHTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code=ErrorCode.POSITION_LIMIT_EXCEEDED,
        message=f"Position limit exceeded for {symbol}",
        details={
            "symbol": symbol,
            "current_position": current_position,
            "limit": limit,
            "excess": current_position - limit
        },
        suggestion="Close some positions or increase position limits"
    )


def risk_limit_error(
    limit_type: str,
    current_value: float,
    limit_value: float
) -> TradingHTTPException:
    """Create risk limit exceeded error"""
    return TradingHTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code=ErrorCode.RISK_LIMIT_EXCEEDED,
        message=f"Risk limit exceeded: {limit_type}",
        details={
            "limit_type": limit_type,
            "current_value": current_value,
            "limit_value": limit_value,
            "excess": current_value - limit_value
        },
        suggestion="Reduce position size or risk exposure"
    )


def market_data_unavailable_error(
    symbol: str,
    details: Optional[Dict[str, Any]] = None
) -> TradingHTTPException:
    """Create market data unavailable error"""
    return TradingHTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        error_code=ErrorCode.MARKET_DATA_UNAVAILABLE,
        message=f"Market data unavailable for {symbol}",
        details=details or {"symbol": symbol},
        suggestion="Try again later or contact support if problem persists"
    )


# Export all exception classes and functions
__all__ = [
    "ErrorCode",
    "TradingException",
    "DatabaseException",
    "CacheException", 
    "OrderException",
    "StrategyException",
    "MarketDataException",
    "RiskManagementException",
    "DhanAPIException",
    "ValidationException",
    "TradingHTTPException",
    "not_found_error",
    "validation_error",
    "unauthorized_error",
    "forbidden_error",
    "internal_error",
    "rate_limit_error",
    "trading_disabled_error",
    "insufficient_funds_error",
    "position_limit_error",
    "risk_limit_error",
    "market_data_unavailable_error"
] 