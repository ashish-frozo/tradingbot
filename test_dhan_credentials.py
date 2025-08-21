#!/usr/bin/env python3
"""
Quick test to verify your Dhan API credentials
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the existing Dhan script
from Dhan_Tradehull_V2 import Tradehull

def test_dhan_credentials():
    """Test your Dhan API credentials"""
    
    client_code = os.getenv('DHAN_CLIENT_ID')
    access_token = os.getenv('DHAN_ACCESS_TOKEN')
    
    print("🔍 Testing Dhan API Credentials...")
    print(f"Client Code: {client_code}")
    print(f"Access Token: {'***' + access_token[-4:] if access_token else 'Not set'}")
    
    if not client_code or not access_token:
        print("❌ ERROR: Please set your Dhan credentials in .env file:")
        print("DHAN_CLIENT_ID=your_actual_client_code")
        print("DHAN_ACCESS_TOKEN=your_actual_access_token")
        return False
    
    try:
        # Test connection
        dhan = Tradehull(client_code, access_token)
        print("✅ Dhan API connection successful!")
        
        # Test getting positions
        positions = dhan.get_positions()
        print(f"📊 Positions: {len(positions) if positions else 0}")
        
        # Test getting balance
        balance = dhan.get_balance()
        print(f"💰 Balance: {balance}")
        
        # Test getting LTP for NIFTY
        ltp_data = dhan.get_ltp_data(['NIFTY 50'])
        print(f"📈 NIFTY LTP: {ltp_data}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("\nPossible issues:")
        print("1. Invalid Dhan credentials")
        print("2. Network connectivity issues")
        print("3. Dhan API service unavailable")
        return False

if __name__ == "__main__":
    print("🚀 Dhan API Credentials Test")
    print("=" * 50)
    
    success = test_dhan_credentials()
    
    if success:
        print("\n✅ SUCCESS: Your Dhan API is working!")
        print("Now you can restart the backend to get real market data.")
    else:
        print("\n❌ FAILED: Fix your credentials and try again.") 