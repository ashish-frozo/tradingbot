#!/usr/bin/env python3
"""
Real Option Chain Fetcher - Simple Integration Version
For use in simple_server.py to get real option chain data
"""

import time
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

def get_real_option_chain_data():
    """
    Simple function to get real option chain data with smart expiry selection
    Returns dict with status, data, and metadata
    """
    try:
        # Initialize Dhan client
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from Dhan_Tradehull_V2 import Tradehull
        
        load_dotenv()
        
        client_id = os.getenv('DHAN_CLIENT_ID')
        access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        if not client_id or not access_token:
            raise Exception("Dhan credentials not found")
            
        dhan = Tradehull(ClientCode=client_id, token_id=access_token)
        print("✅ Dhan client connected for real option chain")
        
        # Step 1: Get available expiry dates
        try:
            expiry_list = dhan.get_expiry_list('NIFTY', 'NFO')
            print(f"📅 Available expiries: {expiry_list}")
            
            if not expiry_list:
                raise Exception("No expiry dates available")
                
        except Exception as e:
            print(f"❌ Error getting expiry dates: {e}")
            return {'status': 'failed', 'error': 'Could not get expiry dates', 'data': []}
        
        # Step 2: Try to get option chain data - try next expiry first (more likely to have data)
        expiry_indices_to_try = [1, 0] if len(expiry_list) > 1 else [0]
        
        for expiry_index in expiry_indices_to_try:
            if expiry_index >= len(expiry_list):
                continue
                
            expiry_date = expiry_list[expiry_index]
            print(f"📡 Trying expiry {expiry_date} (index {expiry_index})...")
            
            try:
                # Add small delay to avoid rate limiting
                time.sleep(2)
                
                result = dhan.get_option_chain("NIFTY", "NFO", expiry_index, 21)
                
                if result and isinstance(result, tuple) and len(result) == 2:
                    atm_strike, df = result
                    
                    if hasattr(df, 'empty') and not df.empty:
                        print(f"🎉 SUCCESS! Got real option chain data")
                        print(f"📊 Expiry: {expiry_date}, ATM: {atm_strike}, Rows: {len(df)}")
                        
                        # Convert to list of dicts
                        option_data = df.to_dict('records')
                        
                        return {
                            'status': 'success',
                            'source': 'api',
                            'data': option_data,
                            'metadata': {
                                'atm_strike': atm_strike,
                                'expiry_date': expiry_date,
                                'expiry_index': expiry_index,
                                'rows': len(df),
                                'fetch_time': datetime.now().isoformat()
                            }
                        }
                    else:
                        print(f"⚠️ Expiry {expiry_date} has empty data")
                        
                else:
                    print(f"⚠️ Unexpected response format for {expiry_date}")
                    
            except Exception as api_error:
                print(f"❌ API error for expiry {expiry_date}: {api_error}")
                
                if "Too many requests" in str(api_error):
                    print("🚫 Rate limited - stopping attempts")
                    break
                    
                continue
        
        # If we get here, no expiry had data
        print("⚠️ No expiry returned valid option chain data")
        return {
            'status': 'failed', 
            'error': 'No valid option chain data from any expiry',
            'data': [],
            'attempted_expiries': expiry_list
        }
        
    except Exception as e:
        print(f"❌ Real option chain fetch failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'data': []
        }


if __name__ == "__main__":
    print("🧪 Testing Real Option Chain Fetcher...")
    
    result = get_real_option_chain_data()
    
    print(f"\n📊 Status: {result['status']}")
    
    if result['status'] == 'success':
        print(f"📊 Data points: {len(result['data'])}")
        print(f"📊 ATM Strike: {result['metadata']['atm_strike']}")
        print(f"📊 Expiry: {result['metadata']['expiry_date']}")
        
        if result['data']:
            sample = result['data'][0]
            print(f"📊 Sample Strike: {sample.get('Strike Price', 'N/A')}")
            print(f"📊 Available columns: {list(sample.keys())[:8]}...")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
        if 'attempted_expiries' in result:
            print(f"📅 Tried expiries: {result['attempted_expiries']}") 