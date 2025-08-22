#!/usr/bin/env python3
"""
Production Option Chain Fetcher
Uses actual expiry dates and smart fallbacks to get real option chain data
"""

import time
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Global cache
_option_chain_cache = {}
_expiry_cache = {}
_last_api_call = 0
_dhan_client = None
_client_initialized = False

class ProductionOptionChainFetcher:
    """
    Production-ready option chain fetcher that:
    1. Gets actual expiry dates
    2. Tries the most likely expiry to have data
    3. Handles rate limits properly
    4. Caches results efficiently
    """
    
    def __init__(self):
        self.min_interval = 12.0  # 12 seconds between API calls
        self.cache_duration = 120  # Cache for 2 minutes
        self.expiry_cache_duration = 300  # Cache expiry list for 5 minutes
        
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
            print("✅ Dhan client initialized for production fetching")
            
        return _dhan_client
    
    def wait_for_rate_limit(self):
        """Wait if we need to respect rate limits"""
        global _last_api_call
        
        time_since_last_call = time.time() - _last_api_call
        if time_since_last_call < self.min_interval:
            wait_time = self.min_interval - time_since_last_call
            print(f"⏳ Rate limiting: waiting {wait_time:.1f}s")
            time.sleep(wait_time)
    
    def get_expiry_dates(self) -> List[str]:
        """Get available expiry dates with caching"""
        global _expiry_cache
        
        # Check cache first
        if 'expiry_list' in _expiry_cache:
            cached_time = _expiry_cache['expiry_list']['timestamp']
            if (datetime.now() - cached_time).total_seconds() < self.expiry_cache_duration:
                expiry_list = _expiry_cache['expiry_list']['data']
                print(f"✅ Using cached expiry list: {expiry_list}")
                return expiry_list
        
        # Fetch fresh expiry list
        try:
            dhan = self.get_dhan_client()
            self.wait_for_rate_limit()
            
            global _last_api_call
            _last_api_call = time.time()
            
            expiry_list = dhan.get_expiry_list('NIFTY', 'NFO')
            print(f"📅 Fetched expiry dates: {expiry_list}")
            
            # Cache the result
            _expiry_cache['expiry_list'] = {
                'data': expiry_list,
                'timestamp': datetime.now()
            }
            
            return expiry_list
            
        except Exception as e:
            print(f"❌ Error getting expiry dates: {e}")
            return []
    
    def is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in _option_chain_cache:
            return False
            
        cached_time = _option_chain_cache[cache_key]['timestamp']
        return (datetime.now() - cached_time).total_seconds() < self.cache_duration
    
    def get_best_expiry_index(self, expiry_dates: List[str]) -> int:
        """
        Determine the best expiry index to use:
        - If current expiry is today or tomorrow, use next expiry
        - Otherwise use current expiry
        """
        if not expiry_dates:
            return 0
        
        try:
            current_expiry = datetime.strptime(expiry_dates[0], '%Y-%m-%d').date()
            today = datetime.now().date()
            days_to_expiry = (current_expiry - today).days
            
            print(f"📅 Current expiry: {current_expiry}, Days to expiry: {days_to_expiry}")
            
            # If expiry is today or tomorrow, try next expiry
            if days_to_expiry <= 1 and len(expiry_dates) > 1:
                print("⚠️ Current expiry too close, using next expiry")
                return 1
            else:
                print("✅ Using current expiry")
                return 0
                
        except Exception as e:
            print(f"⚠️ Error parsing expiry date: {e}, using index 0")
            return 0
    
    def get_option_chain_production(self) -> Dict[str, Any]:
        """
        Production option chain fetching:
        1. Check cache
        2. Get expiry dates
        3. Choose best expiry
        4. Fetch data with rate limiting
        5. Cache results
        """
        
        cache_key = "NIFTY_NFO_production"
        
        # Strategy 1: Check cache first
        if self.is_cache_valid(cache_key):
            cached_data = _option_chain_cache[cache_key]['data']
            cache_age = (datetime.now() - _option_chain_cache[cache_key]['timestamp']).total_seconds()
            print(f"✅ Using cached option chain data (age: {cache_age:.0f}s)")
            return {
                'status': 'success',
                'source': 'cache',
                'data': cached_data['data'],
                'metadata': cached_data['metadata'],
                'timestamp': datetime.now().isoformat()
            }
        
        # Strategy 2: Get fresh data
        print("🔄 Fetching fresh option chain data...")
        
        try:
            # Get expiry dates
            expiry_dates = self.get_expiry_dates()
            if not expiry_dates:
                raise Exception("No expiry dates available")
            
                         # Try multiple expiry indices to find data
             dhan = self.get_dhan_client()
             
             # Try the most likely expiries in order
             expiry_indices_to_try = [self.get_best_expiry_index(expiry_dates)]
             # Also try the next expiry if available
             if len(expiry_dates) > 1 and expiry_indices_to_try[0] == 0:
                 expiry_indices_to_try.append(1)
             elif len(expiry_dates) > 0 and expiry_indices_to_try[0] == 1:
                 expiry_indices_to_try.insert(0, 0)  # Try current first, then next
             
             for expiry_index in expiry_indices_to_try:
                 if expiry_index >= len(expiry_dates):
                     continue
                     
                 expiry_date = expiry_dates[expiry_index]
                 
                 self.wait_for_rate_limit()
                 
                 global _last_api_call
                 _last_api_call = time.time()
                 
                 print(f"📡 Fetching option chain for expiry {expiry_date} (index {expiry_index})...")
                 result = dhan.get_option_chain("NIFTY", "NFO", expiry_index, 21)
                 
                 if result and isinstance(result, tuple) and len(result) == 2:
                     atm_strike, df = result
                     
                     if hasattr(df, 'empty') and not df.empty:
                         print(f"🎉 SUCCESS! Real option chain data - Expiry: {expiry_date}, ATM: {atm_strike}, Rows: {len(df)}")
                         
                         # Convert to dict for caching
                         option_data = df.to_dict('records')
                         
                         # Cache the successful result
                         cached_result = {
                             'data': option_data,
                             'metadata': {
                                 'atm_strike': atm_strike,
                                 'expiry_date': expiry_date,
                                 'expiry_index': expiry_index,
                                 'rows': len(df),
                                 'columns': list(df.columns) if hasattr(df, 'columns') else [],
                                 'fetch_time': datetime.now().isoformat()
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
                         print(f"⚠️ Expiry {expiry_date} returned empty DataFrame")
                 else:
                     print(f"⚠️ Unexpected API response for expiry {expiry_date}: {type(result)}")
                 
                 # Small delay between attempts
                 if expiry_index != expiry_indices_to_try[-1]:
                     print("⏳ Brief pause before trying next expiry...")
                     time.sleep(3)
                
        except Exception as e:
            print(f"❌ Production fetch error: {e}")
            
            if "Too many requests" in str(e):
                print("🚫 Rate limited! Increasing intervals")
                self.min_interval = 25.0
        
        # Strategy 3: Return failure
        return {
            'status': 'failed',
            'source': 'none',
            'data': [],
            'metadata': {'error': 'No real option chain data available'},
            'timestamp': datetime.now().isoformat()
        }


# Singleton instance
_production_fetcher = ProductionOptionChainFetcher()

def get_production_option_chain() -> Dict[str, Any]:
    """
    Get real option chain data using production-ready fetching
    """
    return _production_fetcher.get_option_chain_production()


if __name__ == "__main__":
    print("🏭 Testing Production Option Chain Fetcher...")
    
    # Test the production fetcher
    result = get_production_option_chain()
    
    print(f"\n🏭 Production Result:")
    print(f"📊 Status: {result['status']}")
    print(f"📊 Source: {result['source']}")
    print(f"📊 Data points: {len(result['data'])}")
    
    if result['status'] == 'success' and result['data']:
        metadata = result['metadata']
        print(f"📊 ATM Strike: {metadata.get('atm_strike')}")
        print(f"📊 Expiry Date: {metadata.get('expiry_date')}")
        print(f"📊 Rows: {metadata.get('rows')}")
        
        sample_strike = result['data'][0]
        print(f"📊 Sample Strike: {sample_strike.get('Strike Price', 'N/A')}")
        
        # Show some actual option data
        if 'CE LTP' in sample_strike and 'PE LTP' in sample_strike:
            print(f"📊 CE LTP: {sample_strike.get('CE LTP')}")
            print(f"📊 PE LTP: {sample_strike.get('PE LTP')}")
    
    # Test cache
    print(f"\n🔄 Testing cache...")
    result2 = get_production_option_chain()
    print(f"📊 Second call source: {result2['source']}") 