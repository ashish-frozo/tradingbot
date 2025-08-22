#!/usr/bin/env python3
"""
Smart Rate-Limited Option Chain Fetcher
Handles Dhan API rate limits to get real option chain data
"""

import time
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Global cache
_option_chain_cache = {}
_last_api_call = 0
_dhan_client = None
_client_initialized = False

class SmartOptionChainFetcher:
    """
    Smart option chain fetcher that handles rate limits and caching
    to maximize chances of getting real data from Dhan API
    """
    
    def __init__(self):
        self.min_interval = 10.0  # 10 seconds between API calls
        self.cache_duration = 60  # Cache for 60 seconds
        
    def get_dhan_client(self):
        """Initialize Dhan client once"""
        global _dhan_client, _client_initialized
        
        if not _client_initialized:
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from Dhan_Tradehull_V2 import Tradehull
            
            load_dotenv()
            
            client_id = os.getenv('DHAN_CLIENT_ID')
            access_token = os.getenv('DHAN_ACCESS_TOKEN')
            
            if not client_id or not access_token:
                raise Exception("Dhan credentials not found")
                
            _dhan_client = Tradehull(ClientCode=client_id, token_id=access_token)
            _client_initialized = True
            print("✅ Dhan client initialized for rate-limited fetching")
            
        return _dhan_client
    
    def is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in _option_chain_cache:
            return False
            
        cached_time = _option_chain_cache[cache_key]['timestamp']
        return (datetime.now() - cached_time).total_seconds() < self.cache_duration
    
    def wait_for_rate_limit(self):
        """Wait if we need to respect rate limits"""
        global _last_api_call
        
        time_since_last_call = time.time() - _last_api_call
        if time_since_last_call < self.min_interval:
            wait_time = self.min_interval - time_since_last_call
            print(f"⏳ Rate limiting: waiting {wait_time:.1f}s before next API call")
            time.sleep(wait_time)
    
    def get_option_chain_smart(self, underlying: str = "NIFTY", exchange: str = "NFO") -> Dict[str, Any]:
        """
        Smart option chain fetching with the following strategy:
        1. Check cache first
        2. If cache miss, try ONE expiry index with rate limiting
        3. Cache successful results
        4. Return structured response
        """
        
        cache_key = f"{underlying}_{exchange}"
        
        # Strategy 1: Check cache first
        if self.is_cache_valid(cache_key):
            cached_data = _option_chain_cache[cache_key]['data']
            print(f"✅ Using cached option chain data (age: {(datetime.now() - _option_chain_cache[cache_key]['timestamp']).total_seconds():.0f}s)")
            return {
                'status': 'success',
                'source': 'cache',
                'data': cached_data['data'],
                'metadata': cached_data['metadata'],
                'timestamp': datetime.now().isoformat()
            }
        
        # Strategy 2: Try to get fresh data with rate limiting
        print("🔄 Fetching fresh option chain data from Dhan API...")
        
        try:
            dhan = self.get_dhan_client()
            
            # Wait for rate limit
            self.wait_for_rate_limit()
            
            # Try current expiry first (most likely to have data)
            global _last_api_call
            _last_api_call = time.time()
            
            # Try current expiry first, then next expiry if needed
             for expiry_index in [0, 1]:
                 print(f"📡 Calling Dhan API for expiry index {expiry_index}...")
                 result = dhan.get_option_chain(underlying, exchange, expiry_index, 21)
                 
                 if result and isinstance(result, tuple) and len(result) == 2:
                     atm_strike, df = result
                     
                     if hasattr(df, 'empty') and not df.empty:
                         print(f"🎉 SUCCESS! Got real option chain data - Expiry: {expiry_index}, ATM: {atm_strike}, Rows: {len(df)}")
                         
                         # Convert to dict for caching
                         option_data = df.to_dict('records')
                         
                         # Cache the successful result
                         cached_result = {
                             'data': option_data,
                             'metadata': {
                                 'atm_strike': atm_strike,
                                 'expiry_index': expiry_index,
                                 'rows': len(df),
                                 'columns': list(df.columns) if hasattr(df, 'columns') else [],
                                 'spot_price': None  # Will be filled if available
                             }
                         }
                         
                         _option_chain_cache[cache_key] = {
                             'data': cached_result,
                             'timestamp': datetime.now()
                         }
                         
                         return {
                             'status': 'success',
                             'source': 'api',
                             'data': option_data,
                             'metadata': cached_result['metadata'],
                             'timestamp': datetime.now().isoformat()
                         }
                     else:
                         print(f"⚠️ Expiry {expiry_index} returned empty DataFrame")
                         
                 else:
                     print(f"⚠️ Unexpected API response format for expiry {expiry_index}: {type(result)}")
                 
                 # If we have another expiry to try, wait for rate limit
                 if expiry_index == 0:
                     print("⏳ Waiting before trying next expiry...")
                     time.sleep(5)  # Short wait between expiry attempts
                
        except Exception as e:
            print(f"❌ API Error: {e}")
            
            if "Too many requests" in str(e):
                print("🚫 Rate limited! Will use longer intervals for next calls")
                self.min_interval = 30.0  # Increase interval after rate limit
        
        # Strategy 3: Return None if no real data available
        return {
            'status': 'failed',
            'source': 'none',
            'data': [],
            'metadata': {'error': 'No real data available due to rate limits or API issues'},
            'timestamp': datetime.now().isoformat()
        }
    
    def get_live_spot_price(self) -> Optional[float]:
        """Get live NIFTY spot price"""
        try:
            dhan = self.get_dhan_client()
            
            # Wait for rate limit
            self.wait_for_rate_limit()
            
            global _last_api_call
            _last_api_call = time.time()
            
            ltp_data = dhan.get_ltp_data("NIFTY", "NSE")
            if ltp_data and 'LTP' in ltp_data:
                spot_price = float(ltp_data['LTP'])
                print(f"📈 Live NIFTY spot: {spot_price}")
                return spot_price
            else:
                print("⚠️ Could not get live spot price")
                return None
                
        except Exception as e:
            print(f"❌ Spot price error: {e}")
            return None


# Singleton instance
_fetcher = SmartOptionChainFetcher()

def get_real_option_chain() -> Dict[str, Any]:
    """
    Main function to get real option chain data
    Uses smart caching and rate limiting
    """
    return _fetcher.get_option_chain_smart()

def get_live_nifty_price() -> Optional[float]:
    """Get live NIFTY price"""
    return _fetcher.get_live_spot_price()


if __name__ == "__main__":
    # Test the smart fetcher
    print("🧪 Testing Smart Option Chain Fetcher...")
    
    # Test 1: Get option chain
    result = get_real_option_chain()
    print(f"\nResult: {result['status']}")
    print(f"Source: {result['source']}")
    print(f"Data points: {len(result['data'])}")
    
    if result['data']:
        print(f"Sample strike: {result['data'][0].get('Strike Price', 'N/A')}")
    
    # Test 2: Get it again (should use cache)
    print("\n🔄 Testing cache...")
    result2 = get_real_option_chain()
    print(f"Second call source: {result2['source']}")
    
    # Test 3: Get live spot price
    print("\n📈 Testing live spot price...")
    spot = get_live_nifty_price()
    print(f"Live NIFTY: {spot}") 