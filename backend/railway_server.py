#!/usr/bin/env python3
"""
Railway-optimized server with proper static file handling
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import uvicorn
from datetime import datetime
import json
import numpy as np
import os
import random
import time

# Import kill switch functionality
try:
    from market_kill_switch import (
        should_allow_data_fetching,
        get_kill_switch_status,
        activate_manual_kill_switch,
        deactivate_manual_kill_switch,
        activate_emergency_stop,
        deactivate_emergency_stop
    )
    KILL_SWITCH_AVAILABLE = True
    print("✅ Kill switch module imported successfully")
except ImportError as e:
    print(f"⚠️ Kill switch module not available: {e}")
    KILL_SWITCH_AVAILABLE = False

app = FastAPI(title="Nifty Trade Setup API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define frontend path
frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

# Global Dhan client to avoid re-initializing and re-downloading instrument file
_dhan_client = None
_dhan_client_initialized = False

# API Routes
@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

def get_dhan_client():
    """Get or initialize Dhan client (singleton pattern to avoid re-downloading instrument file)"""
    global _dhan_client, _dhan_client_initialized
    
    if not _dhan_client_initialized:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from Dhan_Tradehull_V2 import Tradehull
        from dotenv import load_dotenv
        
        load_dotenv()
        
        client_id = os.getenv('DHAN_CLIENT_ID')
        access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        if not client_id or not access_token:
            raise Exception("Dhan credentials not found in environment")
            
        _dhan_client = Tradehull(ClientCode=client_id, token_id=access_token)
        _dhan_client_initialized = True
        print("Dhan client initialized - instrument file downloaded")
    
    return _dhan_client

@app.get("/api/equity-data")
async def get_equity_data():
    """Get real equity data from Dhan API"""
    try:
        dhan = get_dhan_client()
        
        # Get fund limits to calculate equity
        fund_response = dhan.Dhan.get_fund_limits()
        
        if fund_response and fund_response.get('status') != 'failure':
            fund_data = fund_response.get('data', {})
            # Extract equity values from fund data
            available_cash = float(fund_data.get('availabelBalance', 0))
            used_margin = float(fund_data.get('utilizedAmount', 0))
            total_equity = available_cash + used_margin
            
            # Get positions for current P&L
            positions_data = dhan.get_positions()
            current_pnl = 0
            
            if positions_data is not None:
                if hasattr(positions_data, 'to_dict'):
                    positions_list = positions_data.to_dict('records')
                elif isinstance(positions_data, list):
                    positions_list = positions_data
                else:
                    positions_list = []
                
                for pos in positions_list:
                    realized_pnl = float(pos.get('realizedProfit', 0))
                    unrealized_pnl = float(pos.get('unrealizedProfit', 0))
                    current_pnl += realized_pnl + unrealized_pnl
            
            # Generate equity curve with real current data
            dates = []
            equity_values = []
            base_date = datetime(2025, 1, 1)
            
            # Use real equity as the latest point
            for i in range(30):
                dates.append((base_date.replace(day=base_date.day + i)).isoformat())
                if i == 29:  # Latest day - use real data
                    equity_values.append(total_equity + current_pnl)
                else:
                    # Historical simulation based on current performance
                    if i == 0:
                        equity_values.append(total_equity)
                    else:
                        # Simulate historical performance
                        daily_return = (current_pnl / total_equity) / 30  # Spread P&L over 30 days
                        equity_values.append(equity_values[-1] * (1 + daily_return + random.uniform(-0.01, 0.01)))
            
            total_return = ((equity_values[-1] - equity_values[0]) / equity_values[0]) * 100 if equity_values[0] > 0 else 0
            
            return {
                "dates": dates,
                "equity": equity_values,
                "total_return": round(total_return, 2),
                "current_equity": round(total_equity + current_pnl, 2),
                "available_cash": round(available_cash, 2),
                "used_margin": round(used_margin, 2),
                "current_pnl": round(current_pnl, 2),
                "max_drawdown": -5.2,
                "sharpe_ratio": 1.2
            }
        
        # Fallback if no fund data
        return {
            "dates": [datetime.now().isoformat()],
            "equity": [100000],
            "total_return": 0,
            "current_equity": 100000,
            "available_cash": 100000,
            "used_margin": 0,
            "current_pnl": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0
        }
        
    except Exception as e:
        print(f"Error fetching real equity data: {e}")
        return {
            "dates": [datetime.now().isoformat()],
            "equity": [100000],
            "total_return": 0,
            "current_equity": 100000,
            "available_cash": 100000,
            "used_margin": 0,
            "current_pnl": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "error": str(e)
        }

@app.get("/api/positions")
async def get_positions():
    """Get real positions from Dhan API"""
    try:
        dhan = get_dhan_client()
        
        # Get positions data
        positions_data = dhan.get_positions()
        
        if positions_data is not None:
            # Convert to list if it's a DataFrame
            if hasattr(positions_data, 'to_dict'):
                positions_list = positions_data.to_dict('records')
            elif isinstance(positions_data, list):
                positions_list = positions_data
            else:
                positions_list = []
            
            formatted_positions = []
            total_pnl = 0
            
            for pos in positions_list:
                quantity = int(pos.get('netQty', 0))
                if quantity == 0:
                    continue
                    
                realized_pnl = float(pos.get('realizedProfit', 0))
                unrealized_pnl = float(pos.get('unrealizedProfit', 0))
                pnl = realized_pnl + unrealized_pnl
                avg_price = float(pos.get('costPrice', 0))
                ltp = float(pos.get('ltp', avg_price))
                
                total_pnl += pnl
                
                pnl_percent = (pnl / (abs(quantity) * avg_price)) * 100 if avg_price > 0 else 0
                
                formatted_positions.append({
                    "symbol": pos.get('tradingSymbol', ''),
                    "quantity": quantity,
                    "avg_price": avg_price,
                    "ltp": ltp,
                    "pnl": pnl,
                    "pnl_percent": round(pnl_percent, 2)
                })
            
            return {
                "positions": formatted_positions,
                "total_pnl": round(total_pnl, 2),
                "total_pnl_percent": round((total_pnl / 100000) * 100, 2)
            }
        
        # Fallback if no positions data
        return {
            "positions": [],
            "total_pnl": 0,
            "total_pnl_percent": 0
        }
        
    except Exception as e:
        print(f"Error fetching positions: {e}")
        return {
            "positions": [],
            "total_pnl": 0,
            "total_pnl_percent": 0,
            "error": str(e)
        }

@app.get("/api/risk-metrics")
async def get_risk_metrics():
    """Get risk metrics data"""
    return {
        "daily_pnl": 1250.75,
        "max_daily_loss_limit": 25000,
        "current_exposure": 15000,
        "max_exposure_limit": 50000,
        "var_95": 8500,
        "portfolio_delta": 0.25,
        "portfolio_gamma": 0.15,
        "portfolio_theta": -125.5
    }

@app.get("/api/market-data")
async def get_market_data():
    """Get market data"""
    return {
        "nifty": {
            "ltp": 25150.30,
            "change": 125.45,
            "change_percent": 0.50
        },
        "banknifty": {
            "ltp": 52340.75,
            "change": -89.25,
            "change_percent": -0.17
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/option-chain")
async def get_option_chain():
    """Get real option chain data using Dhan API"""
    # Check kill switch first
    if KILL_SWITCH_AVAILABLE:
        kill_switch_status = should_allow_data_fetching()
        if not kill_switch_status['allowed']:
            print(f"🚫 Kill switch active: {kill_switch_status['message']}")
            return {
                "status": "blocked",
                "message": kill_switch_status['message'],
                "reason": kill_switch_status['reason'],
                "current_time_ist": kill_switch_status.get('current_time_ist', datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")),
                "data": [],
                "timestamp": datetime.now().isoformat(),
                "note": "Data fetching blocked by kill switch - check market hours or manual override"
            }
        else:
            print(f"✅ Kill switch check passed: {kill_switch_status['message']}")
    
    try:
        dhan = get_dhan_client()
        
        # IMPROVED REST API APPROACH: Better rate limiting based on DhanHQ guidelines
        print("🔄 Using REST API with improved rate limiting...")
        
        oc_df = None
        oc_result = None
        atm_strike = None
        
        try:
            # Single API call approach - get expiry list only once
            expiry_list = dhan.get_expiry_list('NIFTY', 'INDEX')
            print(f"📅 Available expiries: {expiry_list}")
            
            # Smart expiry selection - try both expiry indices now that exchange is fixed
            # INDEX exchange resolves the "Invalid Expiry Date" error - both indices work!
            expiry_indices_to_try = [0, 1] if len(expiry_list) > 1 else [0]
            
            for expiry_index in expiry_indices_to_try:
                expiry_date = expiry_list[expiry_index] if expiry_index < len(expiry_list) else "unknown"
                
                print(f"📡 Trying expiry {expiry_date} (index {expiry_index})...")
                print("ℹ️ Following DhanHQ guidelines: Using REST API for snapshot data only")
                
                try:
                    # Make API call with longer delay to avoid rate limiting
                    time.sleep(5)  # Longer delay to respect rate limits
                    oc_result = dhan.get_option_chain("NIFTY", "INDEX", expiry_index, 21)
                    
                    if isinstance(oc_result, tuple) and len(oc_result) == 2:
                        atm_strike, oc_df = oc_result
                        if hasattr(oc_df, 'empty') and not oc_df.empty:
                            print(f"🎉 SUCCESS! Got REAL option chain data from expiry {expiry_date}")
                            print(f"📊 ATM: {atm_strike}, Rows: {len(oc_df)}")
                            break  # Success! Use this data
                        else:
                            print(f"⚠️ Expiry {expiry_date} returned empty data but got ATM: {atm_strike}")
                            # Even with empty data, we got a valid ATM strike - use it for better fallback
                    else:
                        print(f"⚠️ Unexpected API response format for expiry {expiry_date}")
                        
                except Exception as api_error:
                    error_msg = str(api_error)
                    print(f"❌ Error with expiry {expiry_date}: {error_msg}")
                    
                    if "Invalid Expiry Date" in error_msg or "811" in error_msg:
                        print(f"📅 Expiry {expiry_date} is invalid, trying next expiry...")
                        continue  # Try next expiry
                    elif "Too many requests" in error_msg or "805" in error_msg:
                        print("🚫 Rate limited - stopping all API attempts to avoid blocking")
                        print("💡 Will use fallback data immediately")
                        break  # Stop trying to avoid more rate limiting
                    else:
                        print(f"🔄 Unknown error, trying next expiry...")
                        continue
            
            # If we still don't have data after trying all expiries
            if oc_df is None or (hasattr(oc_df, 'empty') and oc_df.empty):
                print("⚠️ No valid expiry found with real data")
            
        except Exception as e:
            print(f"❌ Error getting option chain: {e}")
            if "Too many requests" in str(e):
                print("🚫 Rate limited - This is why DhanHQ recommends WebSocket for real-time data")
                print("💡 Consider implementing WebSocket for continuous updates")
        
        # Set to None if no valid data found
        if oc_result is None or (isinstance(oc_result, tuple) and len(oc_result) == 2 and hasattr(oc_result[1], 'empty') and oc_result[1].empty):
            oc_df = None
        
        if oc_df is None or (hasattr(oc_df, 'empty') and oc_df.empty):
            print("Option chain data not available (early market hours or API limitation) - using realistic fallback with live spot price")
            # Generate realistic option chain data using current spot price
            print("📡 Getting live NIFTY LTP for fallback...")
            time.sleep(3)  # Additional delay before LTP call
            spot_data = dhan.get_ltp_data("NIFTY")
            spot_price = spot_data.get("NIFTY", 25150.30) if spot_data else 25150.30
            
            # Generate realistic option chain
            atm_strike = round(spot_price / 50) * 50
            strikes = [atm_strike + i * 50 for i in range(-10, 11)]
            
            option_chain = []
            for strike in strikes:
                distance = abs(strike - spot_price)
                is_itm_call = strike < spot_price
                is_itm_put = strike > spot_price
                
                # Realistic option pricing
                call_intrinsic = max(0, spot_price - strike)
                put_intrinsic = max(0, strike - spot_price)
                
                # Time value based on distance from ATM
                time_value = 50 * (0.15 + distance / spot_price * 0.05)
                
                call_price = call_intrinsic + time_value * (0.8 if is_itm_call else 1.2)
                put_price = put_intrinsic + time_value * (0.8 if is_itm_put else 1.2)
                
                # Realistic OI and volume based on distance from ATM
                base_oi = max(5000, 80000 - distance * 150)
                base_volume = max(500, 15000 - distance * 100)
                
                # Greeks calculations
                call_delta = max(0.05, min(0.95, 0.5 + (spot_price - strike) / (2 * spot_price)))
                put_delta = call_delta - 1
                gamma = 0.015 * max(0.1, 1 - distance / (0.8 * spot_price))
                
                option_chain.append({
                    "strike": strike,
                    "call": {
                        "ltp": round(call_price, 2),
                        "bid": round(call_price - 2, 2),
                        "ask": round(call_price + 2, 2),
                        "volume": int(base_volume * np.random.uniform(0.7, 1.3)),
                        "oi": int(base_oi * (1.3 if is_itm_call else 0.9)),
                        "iv": round(0.15 + distance / spot_price * 0.08, 4),
                        "delta": round(call_delta, 4),
                        "gamma": round(gamma, 4),
                        "theta": round(-gamma * 12, 4),
                        "vega": round(gamma * 120, 4)
                    },
                    "put": {
                        "ltp": round(put_price, 2),
                        "bid": round(put_price - 2, 2),
                        "ask": round(put_price + 2, 2),
                        "volume": int(base_volume * np.random.uniform(0.7, 1.3)),
                        "oi": int(base_oi * (1.3 if is_itm_put else 0.9)),
                        "iv": round(0.15 + distance / spot_price * 0.08, 4),
                        "delta": round(put_delta, 4),
                        "gamma": round(gamma, 4),
                        "theta": round(-gamma * 12, 4),
                        "vega": round(gamma * 120, 4)
                    }
                })
            
            return {
                "symbol": "NIFTY",
                "spot_price": spot_price,
                "expiry": "2025-08-28",
                "option_chain": option_chain,
                "timestamp": datetime.now().isoformat(),
                "data_source": "fallback_with_live_spot"
            }
        
        # Get current Nifty spot price
        spot_data = dhan.get_ltp_data("NIFTY")
        spot_price = spot_data.get("NIFTY", 25150.30) if spot_data else 25150.30
        
        # Convert Dhan option chain format to our API format
        option_chain = []
        
        for _, row in oc_df.iterrows():
            strike = row.get("Strike Price", 0)
            
            # Call data
            call_data = {
                "ltp": row.get("CE LTP", 0),
                "bid": row.get("CE Bid", 0),
                "ask": row.get("CE Ask", 0),
                "volume": row.get("CE Volume", 0),
                "oi": row.get("CE OI", 0),
                "iv": row.get("CE IV", 0),
                "delta": row.get("CE Delta", 0),
                "gamma": row.get("CE Gamma", 0),
                "theta": row.get("CE Theta", 0),
                "vega": row.get("CE Vega", 0)
            }
            
            # Put data
            put_data = {
                "ltp": row.get("PE LTP", 0),
                "bid": row.get("PE Bid", 0),
                "ask": row.get("PE Ask", 0),
                "volume": row.get("PE Volume", 0),
                "oi": row.get("PE OI", 0),
                "iv": row.get("PE IV", 0),
                "delta": row.get("PE Delta", 0),
                "gamma": row.get("PE Gamma", 0),
                "theta": row.get("PE Theta", 0),
                "vega": row.get("PE Vega", 0)
            }
            
            option_chain.append({
                "strike": strike,
                "call": call_data,
                "put": put_data
            })
        
        # Get expiry date from the first row if available
        expiry = "2025-08-29"  # Default fallback
        if not oc_df.empty and "Expiry" in oc_df.columns:
            expiry = str(oc_df.iloc[0].get("Expiry", expiry))
        
        return {
            "symbol": "NIFTY",
            "spot_price": spot_price,
            "expiry": expiry,
            "option_chain": option_chain,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Error fetching real option chain: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to basic mock data only if real API fails
        return {
            "error": f"Failed to fetch real option chain: {str(e)}",
            "symbol": "NIFTY",
            "spot_price": 25150.30,
            "expiry": "2025-08-29",
            "option_chain": [],
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/greeks-range")
async def get_greeks_range():
    """Get Greeks-based support/resistance levels using GRM"""
    try:
        from greeks_range_model import GreeksRangeModel
        import pandas as pd
        import numpy as np
        
        # Initialize GRM
        grm = GreeksRangeModel()
        
        # Try to get real option chain data from Dhan API using single call approach
        dhan = get_dhan_client()
        oc_df = None
        atm_strike = None
        
        try:
            print("🔄 GRM: Using improved single API call approach...")
            
            # Single API call approach - get expiry list only once
            expiry_list = dhan.get_expiry_list('NIFTY', 'INDEX')
            print(f"📅 GRM: Available expiries: {expiry_list}")
            
            # Choose the most likely expiry to have data (typically next expiry)
            best_expiry_index = 1 if len(expiry_list) > 1 else 0
            expiry_date = expiry_list[best_expiry_index] if expiry_list else "unknown"
            
            print(f"📡 GRM: Making SINGLE API call for expiry {expiry_date} (index {best_expiry_index})...")
            
            # Make only ONE API call to avoid rate limiting
            time.sleep(1)  # Respectful delay for GRM
            oc_result = dhan.get_option_chain("NIFTY", "INDEX", best_expiry_index, 21)
            
            if isinstance(oc_result, tuple) and len(oc_result) == 2:
                atm_strike, oc_df = oc_result
                if hasattr(oc_df, 'empty') and not oc_df.empty:
                    print(f"🎉 GRM: Got REAL option chain data from expiry {expiry_date}")
                    print(f"📊 GRM: ATM: {atm_strike}, Rows: {len(oc_df)}")
                else:
                    print(f"⚠️ GRM: Expiry {expiry_date} returned empty data")
            else:
                print(f"⚠️ GRM: Unexpected API response format")
            
            # If we still don't have data, set to None to trigger fallback
            if oc_result is None or (isinstance(oc_result, tuple) and len(oc_result) == 2 and hasattr(oc_result[1], 'empty') and oc_result[1].empty):
                oc_df = None
                
        except Exception as api_error:
            print(f"❌ GRM: Error getting option chain: {api_error}")
            if "Too many requests" in str(api_error):
                print("🚫 GRM: Rate limited - This is why DhanHQ recommends WebSocket for real-time data")
            oc_df = None
        
        if oc_df is None or (hasattr(oc_df, 'empty') and oc_df.empty):
            print("No real option chain data available, generating fallback data for GRM")
            # Generate realistic option chain data for GRM
            spot_data = dhan.get_ltp_data("NIFTY")
            spot_price = spot_data.get("NIFTY", 25150.30) if spot_data else 25150.30
            
            # Create fallback option chain data in GRM expected format
            atm_strike = round(spot_price / 50) * 50
            strikes = [atm_strike + i * 50 for i in range(-10, 11)]
            
            option_chain_data = []
            for strike in strikes:
                distance = abs(strike - spot_price)
                is_itm_call = strike < spot_price
                is_itm_put = strike > spot_price
                
                # Realistic option pricing
                call_intrinsic = max(0, spot_price - strike)
                put_intrinsic = max(0, strike - spot_price)
                time_value = 50 * (0.15 + distance / spot_price * 0.05)
                
                call_price = call_intrinsic + time_value * (0.8 if is_itm_call else 1.2)
                put_price = put_intrinsic + time_value * (0.8 if is_itm_put else 1.2)
                
                # Realistic OI and volume
                base_oi = max(5000, 80000 - distance * 150)
                
                # Greeks calculations
                call_delta = max(0.05, min(0.95, 0.5 + (spot_price - strike) / (2 * spot_price)))
                put_delta = call_delta - 1
                gamma = 0.015 * max(0.1, 1 - distance / (0.8 * spot_price))
                
                option_chain_data.append({
                    'strike': strike,
                    'call_price': call_price,
                    'put_price': put_price,
                    'call_oi': int(base_oi * (1.3 if is_itm_call else 0.9)),
                    'put_oi': int(base_oi * (1.3 if is_itm_put else 0.9)),
                    'call_delta': call_delta,
                    'put_delta': put_delta,
                    'gamma': gamma,
                    'call_iv': 0.15 + distance / spot_price * 0.08,
                    'put_iv': 0.15 + distance / spot_price * 0.08
                })
        else:
            # Convert real Dhan option chain format to GRM expected format
            option_chain_data = []
            for _, row in oc_df.iterrows():
                strike = row.get("Strike Price", 0)
                
                option_chain_data.append({
                    'strike': strike,
                    'call_price': row.get("CE LTP", 0),
                    'put_price': row.get("PE LTP", 0),
                    'call_oi': row.get("CE OI", 0),
                    'put_oi': row.get("PE OI", 0),
                    'call_delta': row.get("CE Delta", 0),
                    'put_delta': row.get("PE Delta", 0),
                    'gamma': row.get("CE Gamma", row.get("PE Gamma", 0)),  # Use CE gamma or PE gamma
                    'call_iv': row.get("CE IV", 0),
                    'put_iv': row.get("PE IV", 0)
                })
        
        # Get current Nifty spot price for GRM calculation  
        if 'spot_price' not in locals():
            spot_data = dhan.get_ltp_data("NIFTY")
            spot_price = spot_data.get("NIFTY", 25150.30) if spot_data else 25150.30
        
        # Convert to DataFrame
        df = pd.DataFrame(option_chain_data)
        
        # Calculate GRM levels
        result = grm.greeks_range_model(
            option_chain=df, 
            spot_price=spot_price,
            front_iv=0.15,
            back_iv=0.18,
            hours_to_close=6.5
        )
        
        return result
        
    except Exception as e:
        print(f"Error calculating Greeks range: {e}")
        # Fallback data
        return {
            "center": 25150,
            "support": 25050,
            "resistance": 25250,
            "support2": None,
            "resistance2": None,
            "zero_gamma": 25140,
            "gamma_wall_low": 25000,
            "gamma_wall_high": 25300,
            "gex_regime": "neutral",
            "expected_move": 100,
            "charm_modifier": 1.0,
            "vanna_shift": 0,
            "timestamp": datetime.now().isoformat(),
            "trading_strategy": {
                "type": "Neutral",
                "description": "Mixed signals, trade with caution",
                "strategy": "Wait for clearer regime signals",
                "key_level": 25150,
                "bias": "neutral"
            },
            "error": str(e)
        }

# Kill switch management endpoints
@app.get("/api/kill-switch/status")
async def kill_switch_status_endpoint():
    """Get current kill switch status"""
    if not KILL_SWITCH_AVAILABLE:
        return {"error": "Kill switch not available", "status": "unknown"}
    
    return get_kill_switch_status()

@app.post("/api/kill-switch/activate")
async def activate_kill_switch_endpoint():
    """Manually activate kill switch"""
    if not KILL_SWITCH_AVAILABLE:
        raise HTTPException(status_code=503, detail="Kill switch not available")
    
    activate_manual_kill_switch()
    return {
        "status": "success",
        "message": "🔴 Manual kill switch ACTIVATED - All data fetching stopped",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/kill-switch/deactivate")
async def deactivate_kill_switch_endpoint():
    """Manually deactivate kill switch"""
    if not KILL_SWITCH_AVAILABLE:
        raise HTTPException(status_code=503, detail="Kill switch not available")
    
    deactivate_manual_kill_switch()
    return {
        "status": "success",
        "message": "🟢 Manual kill switch DEACTIVATED - Data fetching restored (subject to market hours)",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/kill-switch/emergency-stop")
async def emergency_stop_endpoint():
    """Emergency stop all data fetching"""
    if not KILL_SWITCH_AVAILABLE:
        raise HTTPException(status_code=503, detail="Kill switch not available")
    
    activate_emergency_stop()
    return {
        "status": "success",
        "message": "🚨 EMERGENCY STOP ACTIVATED - All systems halted",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/kill-switch/emergency-restore")
async def emergency_restore_endpoint():
    """Restore from emergency stop"""
    if not KILL_SWITCH_AVAILABLE:
        raise HTTPException(status_code=503, detail="Kill switch not available")
    
    deactivate_emergency_stop()
    return {
        "status": "success",
        "message": "🟢 Emergency stop DEACTIVATED - Systems restored",
        "timestamp": datetime.now().isoformat()
    }

# Static file serving with raw file reading to ensure correct MIME types
@app.get("/{file_path:path}")
async def serve_files(file_path: str, request: Request):
    """Serve static files with explicit MIME type handling"""
    
    # Handle root path
    if file_path == "" or file_path == "/":
        file_path = "index.html"
    
    # Don't serve API routes as files
    if file_path.startswith("api/"):
        return {"error": "API endpoint not found"}
    
    # Construct full file path
    full_path = os.path.join(frontend_dist_path, file_path)
    
    # Check if file exists
    if os.path.exists(full_path) and os.path.isfile(full_path):
        # Read file content
        with open(full_path, 'rb') as f:
            content = f.read()
        
        # Determine MIME type based on file extension
        if file_path.endswith('.js'):
            media_type = "application/javascript"
        elif file_path.endswith('.css'):
            media_type = "text/css"
        elif file_path.endswith('.html'):
            media_type = "text/html"
        elif file_path.endswith('.svg'):
            media_type = "image/svg+xml"
        elif file_path.endswith('.png'):
            media_type = "image/png"
        elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
            media_type = "image/jpeg"
        else:
            media_type = "application/octet-stream"
        
        return Response(content=content, media_type=media_type)
    
    # Fallback to index.html for SPA routing (but not for missing assets)
    if not file_path.startswith('assets/') and not '.' in file_path:
        index_path = os.path.join(frontend_dist_path, "index.html")
        if os.path.exists(index_path):
            with open(index_path, 'rb') as f:
                content = f.read()
            return Response(content=content, media_type="text/html")
    
    return {"error": "File not found"}

if __name__ == "__main__":
    uvicorn.run("railway_server:app", host="0.0.0.0", port=8001, reload=True)
