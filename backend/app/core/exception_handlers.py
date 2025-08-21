"""
FastAPI Exception Handlers
Global exception handling for consistent error responses
"""

import traceback
from typing import Any, Dict
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from pydantic import ValidationError

from app.core.logging import get_logger, log_risk_event
from app.core.exceptions import (
    TradingException,
    TradingHTTPException,
    ErrorCode,
    DatabaseException,
    CacheException,
    internal_error,
    validation_error
)

logger = get_logger(__name__)


async def trading_exception_handler(request: Request, exc: TradingException) -> JSONResponse:
    """Handle custom trading exceptions"""
    logger.error(f"Trading exception: {exc.message}", extra={
        "error_code": exc.error_code.value,
        "details": exc.details,
        "path": request.url.path,
        "method": request.method
    })
    
    # Log as risk event if it's a trading-related error
    if exc.error_code in [
        ErrorCode.RISK_LIMIT_EXCEEDED,
        ErrorCode.POSITION_LIMIT_EXCEEDED,
        ErrorCode.INSUFFICIENT_FUNDS,
        ErrorCode.ORDER_REJECTED
    ]:
        log_risk_event(
            event_type=exc.error_code.value,
            details={
                "message": exc.message,
                "path": request.url.path,
                **exc.details
            }
        )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=exc.to_dict()
    )


async def trading_http_exception_handler(request: Request, exc: TradingHTTPException) -> JSONResponse:
    """Handle custom trading HTTP exceptions"""
    logger.error(f"Trading HTTP exception: {exc.message}", extra={
        "error_code": exc.error_code.value,
        "status_code": exc.status_code,
        "details": exc.details,
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        headers=exc.headers
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors"""
    # Extract field-specific error details
    error_details = {}
    field_errors = []
    
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        field_errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input")
        })
        
        if field_path not in error_details:
            error_details[field_path] = []
        error_details[field_path].append(error["msg"])
    
    logger.warning(f"Validation error for {request.method} {request.url.path}", extra={
        "field_errors": field_errors,
        "user_agent": request.headers.get("user-agent"),
        "client_ip": get_client_ip(request)
    })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": ErrorCode.VALIDATION_ERROR.value,
            "message": "Invalid input data",
            "details": {
                "field_errors": field_errors,
                "error_count": len(field_errors)
            },
            "suggestion": "Please check the input data and fix the validation errors"
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle standard FastAPI HTTP exceptions"""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}", extra={
        "status_code": exc.status_code,
        "path": request.url.path,
        "method": request.method,
        "user_agent": request.headers.get("user-agent"),
        "client_ip": get_client_ip(request)
    })
    
    # Convert to standardized format
    if isinstance(exc.detail, dict):
        # Already in our format
        content = exc.detail
    else:
        # Convert string detail to our format
        error_code = get_error_code_for_status(exc.status_code)
        content = {
            "error_code": error_code.value,
            "message": str(exc.detail),
            "details": {}
        }
        
        # Add suggestions for common errors
        if exc.status_code == 404:
            content["suggestion"] = "Check the URL path and try again"
        elif exc.status_code == 405:
            content["suggestion"] = "Check the HTTP method (GET, POST, etc.)"
        elif exc.status_code == 401:
            content["suggestion"] = "Please provide valid authentication credentials"
    
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, 'headers', None)
    )


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle database errors"""
    error_message = "Database operation failed"
    error_code = ErrorCode.DATABASE_QUERY_ERROR
    details = {"error_type": type(exc).__name__}
    
    # Categorize database errors
    if isinstance(exc, OperationalError):
        error_code = ErrorCode.DATABASE_CONNECTION_ERROR
        error_message = "Database connection error"
        details["suggestion"] = "Database may be temporarily unavailable"
    elif isinstance(exc, IntegrityError):
        error_code = ErrorCode.DATABASE_CONSTRAINT_ERROR
        error_message = "Database constraint violation"
        details["suggestion"] = "Check for duplicate data or missing references"
    
    logger.error(f"Database error: {error_message}", extra={
        "error_type": type(exc).__name__,
        "error_details": str(exc),
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": error_code.value,
            "message": error_message,
            "details": details,
            "suggestion": details.get("suggestion", "Please try again or contact support")
        }
    )


async def redis_exception_handler(request: Request, exc: RedisError) -> JSONResponse:
    """Handle Redis/cache errors"""
    error_message = "Cache operation failed"
    error_code = ErrorCode.CACHE_OPERATION_ERROR
    
    if isinstance(exc, RedisConnectionError):
        error_code = ErrorCode.CACHE_CONNECTION_ERROR
        error_message = "Cache connection error"
    
    logger.error(f"Redis error: {error_message}", extra={
        "error_type": type(exc).__name__,
        "error_details": str(exc),
        "path": request.url.path,
        "method": request.method
    })
    
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error_code": error_code.value,
            "message": error_message,
            "details": {"error_type": type(exc).__name__},
            "suggestion": "Cache service may be temporarily unavailable"
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other unhandled exceptions"""
    # Generate unique error ID for tracking
    import uuid
    error_id = str(uuid.uuid4())[:8]
    
    # Log full traceback for debugging
    logger.error(f"Unhandled exception [{error_id}]: {type(exc).__name__}: {str(exc)}", extra={
        "error_id": error_id,
        "error_type": type(exc).__name__,
        "path": request.url.path,
        "method": request.method,
        "user_agent": request.headers.get("user-agent"),
        "client_ip": get_client_ip(request),
        "traceback": traceback.format_exc()
    })
    
    # Don't expose internal error details in production
    from app.core.config import settings
    if settings.DEBUG:
        details = {
            "error_type": type(exc).__name__,
            "error_details": str(exc),
            "error_id": error_id
        }
    else:
        details = {"error_id": error_id}
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_code": ErrorCode.INTERNAL_ERROR.value,
            "message": "An internal error occurred",
            "details": details,
            "suggestion": f"Please contact support with error ID: {error_id}"
        }
    )


# Helper functions
def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    if request.client:
        return request.client.host
    
    return "unknown"


def get_error_code_for_status(status_code: int) -> ErrorCode:
    """Map HTTP status codes to error codes"""
    mapping = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.UNAUTHORIZED,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        429: ErrorCode.RATE_LIMITED,
        500: ErrorCode.INTERNAL_ERROR,
    }
    return mapping.get(status_code, ErrorCode.INTERNAL_ERROR)


def setup_exception_handlers(app):
    """Register all exception handlers with FastAPI app"""
    
    # Custom trading exceptions
    app.add_exception_handler(TradingException, trading_exception_handler)
    app.add_exception_handler(TradingHTTPException, trading_http_exception_handler)
    
    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # Standard HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # Database errors
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    
    # Redis/Cache errors
    app.add_exception_handler(RedisError, redis_exception_handler)
    
    # Catch-all for unhandled exceptions
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("All exception handlers registered successfully")


# Export functions
__all__ = [
    "setup_exception_handlers",
    "trading_exception_handler",
    "trading_http_exception_handler", 
    "validation_exception_handler",
    "http_exception_handler",
    "database_exception_handler",
    "redis_exception_handler",
    "general_exception_handler"
] 