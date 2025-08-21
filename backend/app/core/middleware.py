"""
FastAPI Middleware Configuration
Request logging, CORS, performance monitoring, and security
"""

import time
import uuid
from typing import Callable, Optional
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import get_logger, log_performance_metric

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests with performance metrics"""
    
    def __init__(self, app: ASGIApp, log_requests: bool = True):
        super().__init__(app)
        self.log_requests = log_requests
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Get client info
        client_ip = self.get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Log request start
        if self.log_requests:
            logger.bind(
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                client_ip=client_ip,
                user_agent=user_agent
            ).info(f"Request started: {request.method} {request.url.path}")
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate timing
            process_time = time.time() - start_time
            
            # Log response
            if self.log_requests:
                logger.bind(
                    request_id=request_id,
                    method=request.method,
                    url=str(request.url),
                    status_code=response.status_code,
                    process_time_ms=round(process_time * 1000, 2),
                    client_ip=client_ip
                ).info(f"Request completed: {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")
            
            # Log performance metrics for slow requests
            if process_time > 1.0:  # Log requests taking more than 1 second
                log_performance_metric(
                    metric_name="slow_request",
                    value=process_time * 1000,
                    unit="ms",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    request_id=request_id
                )
            
            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as e:
            # Calculate timing for failed requests
            process_time = time.time() - start_time
            
            # Log error
            logger.bind(
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                error=str(e),
                process_time_ms=round(process_time * 1000, 2),
                client_ip=client_ip
            ).error(f"Request failed: {request.method} {request.url.path} - {str(e)}")
            
            # Re-raise the exception
            raise
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers (load balancer/proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct connection
        if request.client:
            return request.client.host
        
        return "unknown"


class SecurityMiddleware(BaseHTTPMiddleware):
    """Add security headers and basic protection"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Only add HSTS in production
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Skip logging for health check endpoints"""
    
    def __init__(self, app: ASGIApp, health_paths: Optional[list] = None):
        super().__init__(app)
        self.health_paths = health_paths or ["/healthz", "/health", "/ping"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip detailed logging for health checks
        if request.url.path in self.health_paths:
            request.state.skip_logging = True
        
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Basic rate limiting (in-memory, for development)"""
    
    def __init__(self, app: ASGIApp, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = {}  # Simple in-memory store
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/healthz", "/health", "/ping"]:
            return await call_next(request)
        
        client_ip = self.get_client_ip(request)
        current_time = int(time.time() / 60)  # Current minute
        
        # Clean old entries
        self.cleanup_old_requests(current_time)
        
        # Check rate limit
        if client_ip in self.requests:
            if self.requests[client_ip]["count"] >= self.requests_per_minute:
                logger.warning(f"Rate limit exceeded for {client_ip}")
                return Response(
                    content="Rate limit exceeded. Please try again later.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={"Retry-After": "60"}
                )
            self.requests[client_ip]["count"] += 1
        else:
            self.requests[client_ip] = {"count": 1, "minute": current_time}
        
        return await call_next(request)
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def cleanup_old_requests(self, current_minute: int):
        """Remove old rate limit entries"""
        to_remove = []
        for ip, data in self.requests.items():
            if data["minute"] < current_minute:
                to_remove.append(ip)
        
        for ip in to_remove:
            del self.requests[ip]


def setup_cors_middleware(app):
    """Configure CORS middleware"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "Accept",
            "Origin",
            "User-Agent",
            "X-Request-ID",
            "X-API-Key"
        ],
        expose_headers=[
            "X-Request-ID",
            "X-Process-Time",
            "X-Rate-Limit-Remaining",
            "X-Rate-Limit-Reset"
        ]
    )


def setup_middleware(app):
    """Setup all middleware in the correct order"""
    
    # Security middleware (outermost)
    app.add_middleware(SecurityMiddleware)
    
    # Rate limiting (before request processing)
    if not settings.DEBUG:  # Only in production
        app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
    
    # Health check middleware (before logging)
    app.add_middleware(HealthCheckMiddleware)
    
    # Request logging middleware
    app.add_middleware(RequestLoggingMiddleware, log_requests=True)
    
    # CORS middleware (innermost - closest to the app)
    setup_cors_middleware(app)
    
    logger.info("All middleware configured successfully")


# Export middleware components
__all__ = [
    "RequestLoggingMiddleware",
    "SecurityMiddleware", 
    "HealthCheckMiddleware",
    "RateLimitMiddleware",
    "setup_cors_middleware",
    "setup_middleware"
] 