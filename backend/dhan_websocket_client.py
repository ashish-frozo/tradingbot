#!/usr/bin/env python3
"""
DhanHQ WebSocket Client for Real-Time Market Data
Follows DhanHQ best practices to avoid rate limiting
"""

import asyncio
import websockets
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DhanWebSocketClient:
    """
    DhanHQ WebSocket client for real-time market data
    Follows best practices from https://madefortrade.in/t/live-market-feed-websocket-vs-market-quote-rest-api-on-dhanhq/50766
    """
    
    def __init__(self):
        load_dotenv()
        
        self.client_id = os.getenv('DHAN_CLIENT_ID')
        self.access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        if not self.client_id or not self.access_token:
            raise Exception("Dhan credentials not found in environment")
        
        # WebSocket connection details
        self.ws_url = "wss://api.dhan.co"
        self.websocket = None
        self.is_connected = False
        
        # Data storage
        self.latest_option_chain = {}
        self.latest_ltp_data = {}
        self.subscribers = []  # Callback functions for data updates
        
        # Connection management
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        
        logger.info("✅ DhanHQ WebSocket client initialized")
    
    async def connect(self) -> bool:
        """
        Connect to DhanHQ WebSocket
        Follows rate limiting guidelines: max 10 connections per minute
        """
        try:
            # Prepare authentication headers
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Client-ID": self.client_id
            }
            
            logger.info(f"🔗 Connecting to DhanHQ WebSocket: {self.ws_url}")
            
            # Connect with proper headers and timeout
            self.websocket = await websockets.connect(
                self.ws_url,
                extra_headers=headers,
                ping_interval=30,  # Keep connection alive
                ping_timeout=10,
                close_timeout=10
            )
            
            self.is_connected = True
            self.reconnect_attempts = 0
            
            logger.info("🎉 Successfully connected to DhanHQ WebSocket")
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            self.is_connected = False
            return False
    
    async def subscribe_to_option_chain(self, symbol: str = "NIFTY", exchange: str = "NFO"):
        """
        Subscribe to real-time option chain data
        This is the correct way to get option chain data according to DhanHQ guidelines
        """
        if not self.is_connected:
            logger.error("❌ Not connected to WebSocket. Call connect() first.")
            return False
        
        try:
            # Prepare subscription message for option chain
            subscription_message = {
                "RequestCode": 21,  # Option chain subscription
                "InstrumentType": 1,  # Options
                "ExchangeSegment": 2 if exchange == "NFO" else 1,  # NFO = 2, NSE = 1
                "InstrumentID": symbol
            }
            
            await self.websocket.send(json.dumps(subscription_message))
            logger.info(f"📡 Subscribed to {symbol} option chain on {exchange}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to option chain: {e}")
            return False
    
    async def subscribe_to_ltp(self, instruments: List[Dict[str, Any]]):
        """
        Subscribe to Live Traded Price (LTP) for specific instruments
        """
        if not self.is_connected:
            logger.error("❌ Not connected to WebSocket. Call connect() first.")
            return False
        
        try:
            # Prepare LTP subscription message
            subscription_message = {
                "RequestCode": 15,  # LTP subscription
                "InstrumentCount": len(instruments),
                "InstrumentList": instruments
            }
            
            await self.websocket.send(json.dumps(subscription_message))
            logger.info(f"📈 Subscribed to LTP for {len(instruments)} instruments")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to subscribe to LTP: {e}")
            return False
    
    async def listen_for_data(self):
        """
        Listen for incoming WebSocket data
        This runs continuously and processes real-time updates
        """
        if not self.is_connected or not self.websocket:
            logger.error("❌ Not connected to WebSocket")
            return
        
        try:
            logger.info("👂 Listening for real-time market data...")
            
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                    
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Received non-JSON message: {message}")
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("🔌 WebSocket connection closed")
            self.is_connected = False
            await self._handle_reconnection()
            
        except Exception as e:
            logger.error(f"❌ Error in data listener: {e}")
            self.is_connected = False
    
    async def _process_message(self, data: Dict[str, Any]):
        """Process incoming WebSocket messages"""
        try:
            message_type = data.get("MessageType")
            
            if message_type == "OptionChain":
                # Process option chain data
                self.latest_option_chain = {
                    "data": data.get("OptionChainData", []),
                    "timestamp": datetime.now().isoformat(),
                    "source": "websocket",
                    "symbol": data.get("Symbol", "NIFTY")
                }
                
                logger.info(f"📊 Received option chain update: {len(self.latest_option_chain['data'])} strikes")
                
            elif message_type == "LTP":
                # Process LTP data
                instrument_token = data.get("InstrumentToken")
                ltp = data.get("LastTradedPrice")
                
                self.latest_ltp_data[instrument_token] = {
                    "ltp": ltp,
                    "timestamp": datetime.now().isoformat(),
                    "volume": data.get("Volume"),
                    "change": data.get("Change")
                }
                
                logger.debug(f"📈 LTP update: {instrument_token} = {ltp}")
            
            # Notify subscribers
            for callback in self.subscribers:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"❌ Error in subscriber callback: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error processing WebSocket message: {e}")
    
    async def _handle_reconnection(self):
        """Handle WebSocket reconnection with exponential backoff"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"❌ Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            return
        
        self.reconnect_attempts += 1
        delay = self.reconnect_delay * (2 ** (self.reconnect_attempts - 1))  # Exponential backoff
        
        logger.info(f"🔄 Reconnecting in {delay} seconds (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        await asyncio.sleep(delay)
        
        if await self.connect():
            # Re-subscribe to previous subscriptions
            await self.subscribe_to_option_chain()
            await self.listen_for_data()
    
    def add_subscriber(self, callback: Callable):
        """Add a callback function to receive real-time data updates"""
        self.subscribers.append(callback)
        logger.info(f"➕ Added data subscriber (total: {len(self.subscribers)})")
    
    def get_latest_option_chain(self) -> Dict[str, Any]:
        """Get the latest option chain data received via WebSocket"""
        return self.latest_option_chain
    
    def get_latest_ltp(self, instrument_token: str = None) -> Dict[str, Any]:
        """Get the latest LTP data"""
        if instrument_token:
            return self.latest_ltp_data.get(instrument_token, {})
        return self.latest_ltp_data
    
    async def disconnect(self):
        """Properly disconnect from WebSocket"""
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            logger.info("🔌 Disconnected from DhanHQ WebSocket")
        
        self.is_connected = False
        self.websocket = None


# Global WebSocket client instance
_ws_client = None

async def get_websocket_client() -> DhanWebSocketClient:
    """Get or create WebSocket client instance"""
    global _ws_client
    
    if _ws_client is None:
        _ws_client = DhanWebSocketClient()
    
    return _ws_client

async def start_real_time_option_chain(symbol: str = "NIFTY") -> bool:
    """
    Start real-time option chain data streaming
    This is the recommended approach for continuous option chain updates
    """
    try:
        client = await get_websocket_client()
        
        # Connect to WebSocket
        if not await client.connect():
            return False
        
        # Subscribe to option chain
        if not await client.subscribe_to_option_chain(symbol):
            return False
        
        # Start listening in background
        asyncio.create_task(client.listen_for_data())
        
        logger.info(f"🚀 Real-time option chain started for {symbol}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to start real-time option chain: {e}")
        return False

def get_current_option_chain() -> Dict[str, Any]:
    """
    Get current option chain data from WebSocket
    This avoids REST API rate limiting
    """
    global _ws_client
    
    if _ws_client and _ws_client.is_connected:
        return _ws_client.get_latest_option_chain()
    else:
        return {
            "status": "not_connected",
            "message": "WebSocket not connected. Call start_real_time_option_chain() first.",
            "data": []
        }


if __name__ == "__main__":
    # Test the WebSocket client
    async def test_websocket():
        print("🧪 Testing DhanHQ WebSocket Client...")
        
        # Test data callback
        async def data_callback(data):
            print(f"📊 Received data: {data.get('MessageType', 'Unknown')}")
        
        client = await get_websocket_client()
        client.add_subscriber(data_callback)
        
        # Start real-time option chain
        if await start_real_time_option_chain():
            print("✅ WebSocket started successfully")
            
            # Let it run for a few seconds
            await asyncio.sleep(10)
            
            # Check received data
            option_chain = get_current_option_chain()
            print(f"📊 Latest option chain: {len(option_chain.get('data', []))} strikes")
            
        await client.disconnect()
    
    # Run the test
    asyncio.run(test_websocket()) 