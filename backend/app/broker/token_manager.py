"""
Token manager for Dhan-Tradehull API with automatic refresh at 08:50 IST.

This module handles:
- Automatic token refresh at 08:50 IST daily
- Token validation and expiry detection
- Retry logic for failed refresh attempts
- Secure token storage and retrieval
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, Awaitable
import pytz
import aiohttp

from loguru import logger

from app.core.config import settings
from app.core.exceptions import TradingException


class TokenManager:
    """
    Manages Dhan-Tradehull API tokens with automatic refresh capabilities.
    
    Features:
    - Daily token refresh at 08:50 IST
    - Exponential backoff retry logic
    - Token validation and expiry detection
    - Callback notifications for token updates
    """

    def __init__(
        self,
        client_id: str,
        initial_token: str,
        refresh_time_hour: int = 8,
        refresh_time_minute: int = 50
    ):
        """
        Initialize token manager.
        
        Args:
            client_id: Dhan client ID
            initial_token: Initial access token
            refresh_time_hour: Hour for daily refresh (24-hour format)
            refresh_time_minute: Minute for daily refresh
        """
        self.client_id = client_id
        self.current_token = initial_token
        self.refresh_time_hour = refresh_time_hour
        self.refresh_time_minute = refresh_time_minute
        
        # IST timezone
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
        # Token state tracking
        self.last_refresh_time: Optional[datetime] = None
        self.token_expires_at: Optional[datetime] = None
        self.refresh_in_progress = False
        
        # Callback for token updates
        self.token_update_callbacks: list[Callable[[str], Awaitable[None]]] = []
        
        # Retry configuration
        self.max_retries = 3
        self.base_retry_delay = 60  # seconds
        
        # Background task
        self._refresh_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        logger.info(
            f"Token manager initialized for client {client_id}, "
            f"refresh time: {refresh_time_hour:02d}:{refresh_time_minute:02d} IST"
        )

    async def start(self):
        """Start the background token refresh task."""
        if self._refresh_task is None or self._refresh_task.done():
            self._shutdown_event.clear()
            self._refresh_task = asyncio.create_task(self._refresh_loop())
            logger.info("Token manager background task started")

    async def stop(self):
        """Stop the background token refresh task."""
        self._shutdown_event.set()
        
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Token manager background task stopped")

    async def _refresh_loop(self):
        """Background loop for automatic token refresh."""
        while not self._shutdown_event.is_set():
            try:
                now = datetime.now(self.ist_tz)
                next_refresh = self._calculate_next_refresh_time(now)
                
                wait_seconds = (next_refresh - now).total_seconds()
                
                logger.info(
                    f"Next token refresh scheduled for: {next_refresh.strftime('%Y-%m-%d %H:%M:%S IST')} "
                    f"(in {wait_seconds/3600:.1f} hours)"
                )
                
                # Wait until refresh time (or shutdown)
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=wait_seconds
                    )
                    # Shutdown event was set
                    break
                except asyncio.TimeoutError:
                    # Time to refresh token
                    pass
                
                # Perform token refresh
                if not self._shutdown_event.is_set():
                    await self._perform_scheduled_refresh()
                    
            except Exception as e:
                logger.error(f"Error in token refresh loop: {str(e)}")
                # Wait before retrying the loop
                await asyncio.sleep(300)  # 5 minutes

    def _calculate_next_refresh_time(self, current_time: datetime) -> datetime:
        """
        Calculate the next token refresh time.
        
        Args:
            current_time: Current time in IST
            
        Returns:
            Next refresh time in IST
        """
        # Today's refresh time
        today_refresh = current_time.replace(
            hour=self.refresh_time_hour,
            minute=self.refresh_time_minute,
            second=0,
            microsecond=0
        )
        
        # If we've passed today's refresh time, schedule for tomorrow
        if current_time >= today_refresh:
            next_refresh = today_refresh + timedelta(days=1)
        else:
            next_refresh = today_refresh
        
        return next_refresh

    async def _perform_scheduled_refresh(self):
        """Perform scheduled token refresh with retry logic."""
        logger.info("Starting scheduled token refresh")
        
        for attempt in range(self.max_retries):
            try:
                new_token = await self._refresh_token_api_call()
                
                if new_token:
                    old_token = self.current_token
                    self.current_token = new_token
                    self.last_refresh_time = datetime.now(self.ist_tz)
                    
                    # Estimate token expiry (typically 24 hours)
                    self.token_expires_at = self.last_refresh_time + timedelta(hours=23, minutes=30)
                    
                    logger.info("Token refresh successful")
                    
                    # Notify callbacks
                    await self._notify_token_update_callbacks(new_token)
                    
                    return
                    
            except Exception as e:
                logger.error(f"Token refresh attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    delay = self.base_retry_delay * (2 ** attempt)
                    logger.info(f"Retrying token refresh in {delay} seconds")
                    await asyncio.sleep(delay)
        
        # All attempts failed
        logger.error("All token refresh attempts failed")
        await self._handle_refresh_failure()

    async def _refresh_token_api_call(self) -> Optional[str]:
        """
        Make API call to refresh token.
        
        Note: This is a placeholder implementation. The actual Dhan API
        may have different token refresh mechanisms (login API call, etc.)
        
        Returns:
            New access token if successful, None otherwise
        """
        # For Dhan API, token refresh might involve re-authentication
        # This would typically be a login API call with stored credentials
        
        if not hasattr(settings, 'DHAN_USERNAME') or not hasattr(settings, 'DHAN_PASSWORD'):
            logger.warning("DHAN_USERNAME or DHAN_PASSWORD not configured for token refresh")
            return None
        
        refresh_url = "https://api.dhan.co/v2/login"
        
        login_data = {
            "clientId": self.client_id,
            "username": settings.DHAN_USERNAME,
            "password": settings.DHAN_PASSWORD
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(refresh_url, json=login_data) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("status") == "success":
                            access_token = data.get("data", {}).get("accessToken")
                            
                            if access_token:
                                logger.info("Token refresh API call successful")
                                return access_token
                            else:
                                logger.error("Access token not found in refresh response")
                        else:
                            error_msg = data.get("errorMessage", "Unknown error")
                            logger.error(f"Token refresh API error: {error_msg}")
                    else:
                        logger.error(f"Token refresh HTTP error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Token refresh API call failed: {str(e)}")
            raise TradingException(
                message=f"Token refresh failed: {str(e)}",
                error_code="TOKEN_REFRESH_FAILED"
            )
        
        return None

    async def _notify_token_update_callbacks(self, new_token: str):
        """Notify all registered callbacks about token update."""
        for callback in self.token_update_callbacks:
            try:
                await callback(new_token)
            except Exception as e:
                logger.error(f"Token update callback failed: {str(e)}")

    async def _handle_refresh_failure(self):
        """Handle token refresh failure."""
        logger.critical("Token refresh failed completely - manual intervention required")
        
        # You might want to:
        # 1. Send alerts to administrators
        # 2. Disable trading operations
        # 3. Set system to safe mode
        
        # For now, we'll just log the critical error
        # In production, this should trigger proper alerting

    async def refresh_token(self) -> str:
        """
        Manually trigger token refresh.
        
        Returns:
            New access token
            
        Raises:
            TradingException: If refresh fails
        """
        if self.refresh_in_progress:
            logger.warning("Token refresh already in progress")
            # Wait for current refresh to complete
            while self.refresh_in_progress:
                await asyncio.sleep(0.1)
            return self.current_token
        
        self.refresh_in_progress = True
        
        try:
            logger.info("Manual token refresh initiated")
            
            new_token = await self._refresh_token_api_call()
            
            if new_token:
                self.current_token = new_token
                self.last_refresh_time = datetime.now(self.ist_tz)
                self.token_expires_at = self.last_refresh_time + timedelta(hours=23, minutes=30)
                
                await self._notify_token_update_callbacks(new_token)
                
                logger.info("Manual token refresh successful")
                return new_token
            else:
                raise TradingException(
                    message="Token refresh failed",
                    error_code="TOKEN_REFRESH_FAILED"
                )
                
        finally:
            self.refresh_in_progress = False

    def get_current_token(self) -> str:
        """Get the current access token."""
        return self.current_token

    def is_token_valid(self) -> bool:
        """
        Check if current token is still valid.
        
        Returns:
            True if token is valid, False otherwise
        """
        if self.token_expires_at is None:
            # No expiry info, assume valid for now
            return True
        
        now = datetime.now(self.ist_tz)
        # Consider token invalid 30 minutes before actual expiry
        buffer_time = timedelta(minutes=30)
        
        return now < (self.token_expires_at - buffer_time)

    def time_until_refresh(self) -> timedelta:
        """
        Get time until next scheduled refresh.
        
        Returns:
            Time until next refresh
        """
        now = datetime.now(self.ist_tz)
        next_refresh = self._calculate_next_refresh_time(now)
        return next_refresh - now

    def time_until_expiry(self) -> Optional[timedelta]:
        """
        Get time until token expiry.
        
        Returns:
            Time until expiry, or None if expiry time unknown
        """
        if self.token_expires_at is None:
            return None
        
        now = datetime.now(self.ist_tz)
        return self.token_expires_at - now

    def add_token_update_callback(self, callback: Callable[[str], Awaitable[None]]):
        """
        Add a callback to be notified when token is updated.
        
        Args:
            callback: Async function that takes new token as parameter
        """
        self.token_update_callbacks.append(callback)
        logger.info("Token update callback registered")

    def remove_token_update_callback(self, callback: Callable[[str], Awaitable[None]]):
        """Remove a token update callback."""
        if callback in self.token_update_callbacks:
            self.token_update_callbacks.remove(callback)
            logger.info("Token update callback removed")

    def get_status(self) -> Dict[str, Any]:
        """
        Get token manager status information.
        
        Returns:
            Status dictionary with token and refresh information
        """
        now = datetime.now(self.ist_tz)
        
        return {
            "current_token_length": len(self.current_token) if self.current_token else 0,
            "last_refresh_time": self.last_refresh_time.isoformat() if self.last_refresh_time else None,
            "token_expires_at": self.token_expires_at.isoformat() if self.token_expires_at else None,
            "is_token_valid": self.is_token_valid(),
            "refresh_in_progress": self.refresh_in_progress,
            "next_refresh_time": self._calculate_next_refresh_time(now).isoformat(),
            "time_until_refresh_seconds": self.time_until_refresh().total_seconds(),
            "time_until_expiry_seconds": (
                self.time_until_expiry().total_seconds() 
                if self.time_until_expiry() else None
            ),
            "refresh_time_ist": f"{self.refresh_time_hour:02d}:{self.refresh_time_minute:02d}",
            "background_task_running": (
                self._refresh_task is not None and not self._refresh_task.done()
            ),
            "registered_callbacks": len(self.token_update_callbacks)
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop() 