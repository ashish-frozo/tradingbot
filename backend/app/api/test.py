"""
Test API Endpoints
Testing exception handling and error responses
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from app.core.exceptions import (
    TradingException,
    ErrorCode,
    insufficient_funds_error,
    position_limit_error,
    market_data_unavailable_error,
    trading_disabled_error,
    validation_error,
    not_found_error
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create test router (only in development)
from app.core.config import settings
if settings.DEBUG:
    test_router = APIRouter(prefix="/test", tags=["Testing"])
    
    class TestErrorRequest(BaseModel):
        error_type: str = Field(..., description="Type of error to simulate")
        message: Optional[str] = Field(None, description="Custom error message")
    
    @test_router.get("/error/{error_type}")
    async def test_error_handling(error_type: str):
        """Test different types of errors for development/testing"""
        
        if error_type == "trading_exception":
            raise TradingException(
                message="Test trading exception",
                error_code=ErrorCode.STRATEGY_ERROR,
                details={"test_field": "test_value"},
                suggestion="This is a test suggestion"
            )
        
        elif error_type == "insufficient_funds":
            raise insufficient_funds_error(
                required_amount=10000.0,
                available_amount=5000.0,
                currency="INR"
            )
        
        elif error_type == "position_limit":
            raise position_limit_error(
                symbol="BANKNIFTY2470843500CE",
                current_position=12,
                limit=10
            )
        
        elif error_type == "market_data":
            raise market_data_unavailable_error(
                symbol="INVALID_SYMBOL",
                details={"reason": "Symbol not found"}
            )
        
        elif error_type == "trading_disabled":
            raise trading_disabled_error(
                message="Trading is disabled during market hours check"
            )
        
        elif error_type == "validation":
            raise validation_error(
                message="Invalid input parameters",
                details={"field": "symbol", "error": "Symbol format is invalid"}
            )
        
        elif error_type == "not_found":
            raise not_found_error(
                message="Strategy not found",
                details={"strategy_id": "non_existent_strategy"}
            )
        
        elif error_type == "http_404":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Standard HTTP 404 error"
            )
        
        elif error_type == "database":
            # Simulate database error
            from sqlalchemy.exc import OperationalError
            raise OperationalError("Connection timeout", None, None)
        
        elif error_type == "redis":
            # Simulate Redis error
            from redis.exceptions import ConnectionError
            raise ConnectionError("Redis connection failed")
        
        elif error_type == "unhandled":
            # Simulate unhandled exception
            raise ValueError("This is an unhandled exception for testing")
        
        else:
            return {"error": f"Unknown error type: {error_type}"}
    
    @test_router.post("/validation")
    async def test_validation_error(data: TestErrorRequest):
        """Test validation error handling with Pydantic"""
        return {"message": "Validation successful", "data": data}
    
    @test_router.get("/success")
    async def test_success():
        """Test successful response"""
        return {
            "status": "success",
            "message": "Test endpoint working correctly",
            "data": {"test": True}
        }
else:
    # In production, create empty router
    test_router = APIRouter(prefix="/test", tags=["Testing"])
    
    @test_router.get("/")
    async def test_disabled():
        """Test endpoints are disabled in production"""
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test endpoints are not available in production"
        )

# Export router
__all__ = ["test_router"] 