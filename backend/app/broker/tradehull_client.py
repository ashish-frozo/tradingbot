"""
Async wrapper for Dhan-Tradehull API client with comprehensive trading functionality.

This module provides an async interface to the Dhan-Tradehull API with:
- Rate limiting (20 orders/sec, 20 modifications/order)
- Automatic token refresh at 08:50 IST daily
- Comprehensive error handling and retries
- Market data feeds and order management
- Position and portfolio tracking
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
from contextlib import asynccontextmanager
import pytz

import aiohttp
from dhanhq import dhanhq
from loguru import logger

from app.core.config import settings
from app.core.exceptions import TradingException
from app.broker.enums import TransactionType, OrderType, Validity, ExchangeSegment
from app.broker.rate_limiter import RateLimiter
from app.broker.token_manager import TokenManager


class DhanTradehullClient:
    """
    Async wrapper for Dhan-Tradehull API with comprehensive trading functionality.
    
    Features:
    - Async operations with proper error handling
    - Rate limiting for order operations
    - Automatic token refresh
    - Market data streaming
    - Position and portfolio management
    """

    def __init__(
        self,
        client_id: str,
        access_token: str,
        base_url: Optional[str] = None
    ):
        """
        Initialize the Dhan-Tradehull async client.
        
        Args:
            client_id: Dhan client ID
            access_token: Access token for API authentication
            base_url: Optional base URL for API (defaults to production)
        """
        self.client_id = client_id
        self.access_token = access_token
        self.base_url = base_url or "https://api.dhan.co"
        
        # Initialize synchronous Dhan client for certain operations
        self._sync_client = dhanhq(client_id, access_token)
        
        # Rate limiters for different operations
        self.order_rate_limiter = RateLimiter(max_requests=20, time_window=1.0)
        self.modification_rate_limiter = RateLimiter(max_requests=20, time_window=1.0)
        self.data_rate_limiter = RateLimiter(max_requests=10, time_window=1.0)
        
        # Token manager for automatic refresh
        self.token_manager = TokenManager(client_id, access_token)
        
        # HTTP session for async operations
        self._session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Internal state tracking
        self._last_token_refresh = None
        self._order_modification_count: Dict[str, int] = {}
        
        logger.info(f"DhanTradehullClient initialized for client: {client_id}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Initialize HTTP session and connections."""
        if self._session is None:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            timeout = aiohttp.ClientTimeout(
                total=30,
                connect=10,
                sock_read=15
            )
            
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self._headers,
                raise_for_status=False
            )
            
            logger.info("DhanTradehullClient session connected")

    async def disconnect(self):
        """Close HTTP session and cleanup."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info("DhanTradehullClient session disconnected")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        rate_limiter: Optional[RateLimiter] = None
    ) -> Dict[str, Any]:
        """
        Make async HTTP request with error handling and rate limiting.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request body data
            params: Query parameters
            rate_limiter: Optional rate limiter to apply
            
        Returns:
            Response data as dictionary
            
        Raises:
            TradingException: For API errors or rate limit violations
        """
        if not self._session:
            await self.connect()

        # Apply rate limiting if specified
        if rate_limiter:
            await rate_limiter.acquire()

        url = f"{self.base_url}{endpoint}"
        
        try:
            # Check if token needs refresh
            await self._check_token_refresh()
            
            async with self._session.request(
                method=method,
                url=url,
                json=data,
                params=params
            ) as response:
                
                response_data = await response.json()
                
                # Log request for audit
                logger.info(
                    f"API Request: {method} {endpoint}",
                    extra={
                        "endpoint": endpoint,
                        "status_code": response.status,
                        "response_time_ms": response.headers.get("X-Response-Time", "N/A")
                    }
                )
                
                # Handle API errors
                if response.status >= 400:
                    error_code = response_data.get("errorCode", "UNKNOWN_ERROR")
                    error_message = response_data.get("errorMessage", "Unknown error occurred")
                    
                    logger.error(
                        f"API Error: {error_code} - {error_message}",
                        extra={"status_code": response.status, "endpoint": endpoint}
                    )
                    
                    raise TradingException(
                        message=f"Dhan API Error: {error_message}",
                        error_code=error_code,
                        details={"endpoint": endpoint, "status_code": response.status}
                    )
                
                return response_data
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP Client Error: {str(e)}", extra={"endpoint": endpoint})
            raise TradingException(
                message=f"HTTP Error: {str(e)}",
                error_code="HTTP_ERROR",
                details={"endpoint": endpoint}
            )
        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {endpoint}")
            raise TradingException(
                message="Request timeout",
                error_code="TIMEOUT_ERROR",
                details={"endpoint": endpoint}
            )

    async def _check_token_refresh(self):
        """Check if token needs refresh and refresh if necessary."""
        ist_tz = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_tz)
        
        # Check if it's time for daily token refresh (08:50 IST)
        refresh_time = now.replace(hour=8, minute=50, second=0, microsecond=0)
        
        if (self._last_token_refresh is None or 
            (now > refresh_time and 
             (self._last_token_refresh is None or self._last_token_refresh.date() < now.date()))):
            
            try:
                new_token = await self.token_manager.refresh_token()
                self.access_token = new_token
                self._headers["Authorization"] = f"Bearer {new_token}"
                self._last_token_refresh = now
                
                logger.info("Token refreshed successfully")
                
            except Exception as e:
                logger.error(f"Token refresh failed: {str(e)}")
                raise TradingException(
                    message="Token refresh failed",
                    error_code="TOKEN_REFRESH_ERROR",
                    details={"error": str(e)}
                )

    # ========== ORDER MANAGEMENT ==========

    async def place_order(
        self,
        transaction_type: TransactionType,
        exchange_segment: ExchangeSegment,
        product_type: str,
        order_type: OrderType,
        validity: Validity,
        trading_symbol: str,
        security_id: str,
        quantity: int,
        disclosed_quantity: int = 0,
        price: float = 0.0,
        trigger_price: float = 0.0,
        after_market_order: bool = False,
        amo_time: str = "OPEN",
        bolt_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Place a new order with comprehensive validation and rate limiting.
        
        Args:
            transaction_type: BUY or SELL
            exchange_segment: NSE_EQ, NSE_FNO, etc.
            product_type: CNC, MIS, NRML
            order_type: MARKET, LIMIT, SL, SLM
            validity: DAY, IOC
            trading_symbol: Trading symbol
            security_id: Dhan security ID
            quantity: Order quantity
            disclosed_quantity: Disclosed quantity for iceberg orders
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for SL orders)
            after_market_order: Whether it's an AMO
            amo_time: AMO timing (OPEN, OPEN_30, OPEN_60)
            bolt_id: Optional bolt ID for bracket orders
            
        Returns:
            Order placement response
        """
        order_data = {
            "transactionType": transaction_type.value,
            "exchangeSegment": exchange_segment.value,
            "productType": product_type,
            "orderType": order_type.value,
            "validity": validity.value,
            "tradingSymbol": trading_symbol,
            "securityId": security_id,
            "quantity": quantity,
            "disclosedQuantity": disclosed_quantity,
            "price": price,
            "triggerPrice": trigger_price,
            "afterMarketOrder": after_market_order,
            "amoTime": amo_time
        }
        
        if bolt_id:
            order_data["boltId"] = bolt_id

        logger.info(
            f"Placing order: {transaction_type.value} {quantity} {trading_symbol} @ {price}",
            extra={"order_data": order_data}
        )

        response = await self._make_request(
            method="POST",
            endpoint="/v2/orders",
            data=order_data,
            rate_limiter=self.order_rate_limiter
        )
        
        order_id = response.get("data", {}).get("orderId")
        if order_id:
            self._order_modification_count[order_id] = 0
            
        logger.info(f"Order placed successfully: {order_id}")
        return response

    async def modify_order(
        self,
        order_id: str,
        order_type: OrderType,
        leg_name: str,
        quantity: int,
        price: float = 0.0,
        trigger_price: float = 0.0,
        disclosed_quantity: int = 0,
        validity: Validity = Validity.DAY
    ) -> Dict[str, Any]:
        """
        Modify an existing order with modification count tracking.
        
        Args:
            order_id: Order ID to modify
            order_type: New order type
            leg_name: Leg name for the order
            quantity: New quantity
            price: New price
            trigger_price: New trigger price
            disclosed_quantity: New disclosed quantity
            validity: Order validity
            
        Returns:
            Order modification response
            
        Raises:
            TradingException: If modification limit exceeded
        """
        # Check modification limit (max 20 per order)
        modification_count = self._order_modification_count.get(order_id, 0)
        if modification_count >= 20:
            raise TradingException(
                message=f"Maximum modifications (20) exceeded for order {order_id}",
                error_code="MODIFICATION_LIMIT_EXCEEDED",
                details={"order_id": order_id, "modification_count": modification_count}
            )

        modify_data = {
            "orderId": order_id,
            "orderType": order_type.value,
            "legName": leg_name,
            "quantity": quantity,
            "price": price,
            "triggerPrice": trigger_price,
            "disclosedQuantity": disclosed_quantity,
            "validity": validity.value
        }

        logger.info(
            f"Modifying order {order_id}: qty={quantity}, price={price}",
            extra={"modify_data": modify_data}
        )

        response = await self._make_request(
            method="PUT",
            endpoint="/v2/orders",
            data=modify_data,
            rate_limiter=self.modification_rate_limiter
        )
        
        # Increment modification count
        self._order_modification_count[order_id] = modification_count + 1
        
        logger.info(f"Order modified successfully: {order_id}")
        return response

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel an existing order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Order cancellation response
        """
        logger.info(f"Cancelling order: {order_id}")
        
        response = await self._make_request(
            method="DELETE",
            endpoint=f"/v2/orders/{order_id}"
        )
        
        # Clean up modification tracking
        self._order_modification_count.pop(order_id, None)
        
        logger.info(f"Order cancelled successfully: {order_id}")
        return response

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get status of a specific order.
        
        Args:
            order_id: Order ID to check
            
        Returns:
            Order status information
        """
        response = await self._make_request(
            method="GET",
            endpoint=f"/v2/orders/{order_id}"
        )
        return response

    async def get_order_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all orders for the day.
        
        Returns:
            List of orders
        """
        response = await self._make_request(
            method="GET",
            endpoint="/v2/orders"
        )
        return response.get("data", [])

    # ========== POSITION MANAGEMENT ==========

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions.
        
        Returns:
            List of positions
        """
        response = await self._make_request(
            method="GET",
            endpoint="/v2/positions"
        )
        return response.get("data", [])

    async def convert_position(
        self,
        security_id: str,
        exchange_segment: ExchangeSegment,
        transaction_type: TransactionType,
        position_type: str,
        quantity: int,
        from_product_type: str,
        to_product_type: str
    ) -> Dict[str, Any]:
        """
        Convert position from one product type to another.
        
        Args:
            security_id: Security ID
            exchange_segment: Exchange segment
            transaction_type: Transaction type
            position_type: Position type
            quantity: Quantity to convert
            from_product_type: Current product type
            to_product_type: Target product type
            
        Returns:
            Position conversion response
        """
        convert_data = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment.value,
            "transactionType": transaction_type.value,
            "positionType": position_type,
            "quantity": quantity,
            "fromProductType": from_product_type,
            "toProductType": to_product_type
        }

        response = await self._make_request(
            method="POST",
            endpoint="/v2/positions/convert",
            data=convert_data
        )
        
        logger.info(f"Position converted: {from_product_type} → {to_product_type}")
        return response

    # ========== MARKET DATA ==========

    async def get_market_quote(self, security_id: str, exchange_segment: ExchangeSegment) -> Dict[str, Any]:
        """
        Get market quote for a security.
        
        Args:
            security_id: Security ID
            exchange_segment: Exchange segment
            
        Returns:
            Market quote data
        """
        params = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment.value
        }
        
        response = await self._make_request(
            method="GET",
            endpoint="/v2/marketfeed/quote",
            params=params,
            rate_limiter=self.data_rate_limiter
        )
        return response

    async def get_market_depth(self, security_id: str, exchange_segment: ExchangeSegment) -> Dict[str, Any]:
        """
        Get market depth for a security.
        
        Args:
            security_id: Security ID
            exchange_segment: Exchange segment
            
        Returns:
            Market depth data
        """
        params = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment.value
        }
        
        response = await self._make_request(
            method="GET",
            endpoint="/v2/marketfeed/depth",
            params=params,
            rate_limiter=self.data_rate_limiter
        )
        return response

    async def get_option_chain(
        self,
        underlying_security_id: str,
        exchange_segment: ExchangeSegment,
        expiry_date: str
    ) -> Dict[str, Any]:
        """
        Get option chain data for an underlying.
        
        Args:
            underlying_security_id: Underlying security ID
            exchange_segment: Exchange segment
            expiry_date: Expiry date (YYYY-MM-DD)
            
        Returns:
            Option chain data
        """
        params = {
            "underlyingSecurityId": underlying_security_id,
            "exchangeSegment": exchange_segment.value,
            "expiryDate": expiry_date
        }
        
        response = await self._make_request(
            method="GET",
            endpoint="/v2/marketfeed/optionchain",
            params=params,
            rate_limiter=self.data_rate_limiter
        )
        return response

    # ========== PORTFOLIO & FUNDS ==========

    async def get_fund_limits(self) -> Dict[str, Any]:
        """
        Get fund limits and available margins.
        
        Returns:
            Fund limits data
        """
        response = await self._make_request(
            method="GET",
            endpoint="/v2/fundlimit"
        )
        return response

    async def get_holdings(self) -> List[Dict[str, Any]]:
        """
        Get current holdings.
        
        Returns:
            List of holdings
        """
        response = await self._make_request(
            method="GET",
            endpoint="/v2/holdings"
        )
        return response.get("data", [])

    # ========== UTILITY METHODS ==========

    async def flatten_all_positions(self) -> List[Dict[str, Any]]:
        """
        Emergency function to flatten all open positions.
        
        Returns:
            List of order responses for flatten operations
        """
        logger.warning("FLATTEN ALL POSITIONS initiated")
        
        positions = await self.get_positions()
        flatten_orders = []
        
        for position in positions:
            if position.get("netQty", 0) != 0:
                try:
                    # Determine transaction type to close position
                    net_qty = position["netQty"]
                    transaction_type = TransactionType.SELL if net_qty > 0 else TransactionType.BUY
                    quantity = abs(net_qty)
                    
                    order = await self.place_order(
                        transaction_type=transaction_type,
                        exchange_segment=ExchangeSegment(position["exchangeSegment"]),
                        product_type=position["productType"],
                        order_type=OrderType.MARKET,
                        validity=Validity.DAY,
                        trading_symbol=position["tradingSymbol"],
                        security_id=position["securityId"],
                        quantity=quantity
                    )
                    
                    flatten_orders.append(order)
                    
                except Exception as e:
                    logger.error(f"Failed to flatten position {position['tradingSymbol']}: {str(e)}")
        
        logger.warning(f"Flatten all completed. {len(flatten_orders)} orders placed.")
        return flatten_orders

    def get_modification_count(self, order_id: str) -> int:
        """Get modification count for an order."""
        return self._order_modification_count.get(order_id, 0)

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of the client.
        
        Returns:
            Health status information
        """
        try:
            # Simple API call to check connectivity
            fund_limits = await self.get_fund_limits()
            
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "last_token_refresh": self._last_token_refresh.isoformat() if self._last_token_refresh else None,
                "session_active": self._session is not None,
                "api_accessible": True
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "session_active": self._session is not None,
                "api_accessible": False
            }


# ========== FACTORY FUNCTION ==========

@asynccontextmanager
async def create_dhan_client():
    """
    Factory function to create and manage DhanTradehullClient lifecycle.
    
    Usage:
        async with create_dhan_client() as client:
            positions = await client.get_positions()
    """
    client = DhanTradehullClient(
        client_id=settings.DHAN_CLIENT_ID,
        access_token=settings.DHAN_ACCESS_TOKEN
    )
    
    try:
        await client.connect()
        yield client
    finally:
        await client.disconnect() 