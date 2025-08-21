#!/usr/bin/env python3
"""
Test script to verify Dhan API connection and market data fetching
Run this after adding your Dhan credentials to .env file
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# Add backend to path
sys.path.append('./backend')

from app.broker.tradehull_client import DhanTradehullClient
from app.core.config import settings

def test_dhan_connection():
    """Test Dhan API connection with your credentials"""
    
    # Load environment variables
    load_dotenv()
    
    print("🔍 Testing Dhan API Connection...")
    print(f"Client ID: {settings.DHAN_CLIENT_ID}")
    print(f"Access Token: {'***' + settings.DHAN_ACCESS_TOKEN[-4:] if settings.DHAN_ACCESS_TOKEN else 'Not set'}")
    
    if not settings.DHAN_CLIENT_ID or not settings.DHAN_ACCESS_TOKEN:
        print("❌ ERROR: Dhan credentials not set in .env file")
        print("\nPlease add your Dhan credentials to .env file:")
        print("DHAN_CLIENT_ID=your_actual_client_id")
        print("DHAN_ACCESS_TOKEN=your_actual_access_token")
        return False
    
    try:
        # Initialize client
        client = DhanTradehullClient()
        client.connect()
        
        print("✅ Dhan client initialized successfully")
        
        # Test basic API call - get positions
        print("\n🔍 Testing API call - fetching positions...")
        positions = client.get_positions()
        print(f"✅ Positions fetched: {len(positions) if positions else 0} positions")
        
        # Test market data fetch
        print("\n🔍 Testing market data fetch...")
        try:
            # Get NIFTY futures LTP
            ltp_data = client.get_ltp(['26000'])  # NIFTY 50 index
            print(f"✅ LTP data fetched: {ltp_data}")
        except Exception as e:
            print(f"⚠️ LTP fetch warning: {e}")
        
        # Test option chain (this might fail if not subscribed)
        print("\n🔍 Testing option chain fetch...")
        try:
            option_chain = client.get_option_chain('NIFTY', '2025-07-17')
            print(f"✅ Option chain fetched: {len(option_chain) if option_chain else 0} options")
        except Exception as e:
            print(f"⚠️ Option chain warning: {e}")
        
        client.disconnect()
        print("\n✅ All tests completed successfully!")
        print("🎉 Your Dhan API connection is working!")
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("\nPossible issues:")
        print("1. Invalid Dhan credentials")
        print("2. Network connectivity issues")
        print("3. Dhan API service unavailable")
        print("4. Account not activated for API trading")
        return False

async def test_real_time_data():
    """Test real-time market data streaming"""
    print("\n🔍 Testing real-time market data streaming...")
    
    try:
        client = DhanTradehullClient()
        client.connect()
        
        # Subscribe to NIFTY and BANKNIFTY
        symbols = ['26000', '26009']  # NIFTY, BANKNIFTY
        
        print(f"📡 Subscribing to symbols: {symbols}")
        
        # This would normally set up WebSocket connection
        # For now, just test periodic data fetch
        for i in range(3):
            ltp_data = client.get_ltp(symbols)
            print(f"📊 Tick {i+1}: {ltp_data}")
            await asyncio.sleep(1)
        
        client.disconnect()
        print("✅ Real-time data test completed!")
        
    except Exception as e:
        print(f"❌ Real-time data test failed: {e}")

if __name__ == "__main__":
    print("🚀 Dhan API Connection Test")
    print("=" * 50)
    
    success = test_dhan_connection()
    
    if success:
        print("\n" + "=" * 50)
        print("🎯 Next Steps:")
        print("1. Your Dhan API is working!")
        print("2. Restart the backend: cd backend && python main.py")
        print("3. The dashboard should now show 'Connected' status")
        print("4. Real market data will start flowing")
        
        # Test real-time data
        asyncio.run(test_real_time_data())
    else:
        print("\n" + "=" * 50)
        print("🔧 Fix Required:")
        print("1. Add your real Dhan credentials to .env file")
        print("2. Ensure your Dhan account has API access enabled")
        print("3. Check your internet connection")
        print("4. Run this test again") 