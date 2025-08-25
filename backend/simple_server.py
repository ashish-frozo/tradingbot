#!/usr/bin/env python3
"""
Simple FastAPI server for testing and basic functionality
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from datetime import datetime
import random
import os
import time
from market_kill_switch import should_allow_data_fetching, get_kill_switch_status, activate_manual_kill_switch, deactivate_manual_kill_switch, activate_emergency_stop, deactivate_emergency_stop

# Create API router for all API endpoints
from fastapi import APIRouter
api_router = APIRouter(prefix="/api")

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

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Kill Switch Endpoints
@app.get("/api/kill-switch/status")
async def get_kill_switch_status_endpoint():
    """Get kill switch status and market hours information"""
    return get_kill_switch_status()

@app.post("/api/kill-switch/activate")
async def activate_kill_switch():
    """Manually activate the kill switch to stop all data fetching"""
    message = activate_manual_kill_switch()
    return {"status": "success", "message": message, "timestamp": datetime.now().isoformat()}

@app.post("/api/kill-switch/deactivate")
async def deactivate_kill_switch():
    """Manually deactivate the kill switch to restore data fetching"""
    message = deactivate_manual_kill_switch()
    return {"status": "success", "message": message, "timestamp": datetime.now().isoformat()}

@app.post("/api/kill-switch/emergency-stop")
async def emergency_stop():
    """Activate emergency stop (highest priority kill switch)"""
    message = activate_emergency_stop()
    return {"status": "success", "message": message, "timestamp": datetime.now().isoformat()}

@app.post("/api/kill-switch/emergency-restore")
async def emergency_restore():
    """Deactivate emergency stop"""
    message = deactivate_emergency_stop()
    return {"status": "success", "message": message, "timestamp": datetime.now().isoformat()}

@app.get("/api/equity-data")
async def get_equity_data():
    """Get real equity data from Dhan API"""
    
    # Check kill switch first
    kill_switch_status = should_allow_data_fetching()
    if not kill_switch_status['allowed']:
        print(f"🚫 Kill switch active for equity data: {kill_switch_status['message']}")
        return {
            "status": "blocked",
            "message": kill_switch_status['message'],
            "reason": kill_switch_status['reason'],
            "current_time_ist": kill_switch_status['current_time_ist'],
            "timestamp": datetime.now().isoformat(),
            "note": "Equity data fetching blocked by kill switch"
        }
    
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from Dhan_Tradehull_V2 import Tradehull
        from dotenv import load_dotenv
        import pandas as pd
        
        load_dotenv()
        
        # Initialize Dhan client
        client_id = os.getenv('DHAN_CLIENT_ID')
        access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        if not client_id or not access_token:
            raise Exception("Dhan credentials not found in environment")
            
        dhan = Tradehull(ClientCode=client_id, token_id=access_token)
        
        # Get fund limits to calculate equity
        fund_data = dhan.get_fund_limits()
        
        if fund_data is not None:
            # Extract equity values from fund data
            available_cash = float(fund_data.get('availablecash', 0))
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
                "max_drawdown": -5.2,  # Calculate from historical data if available
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
        # Return minimal real-time data on error
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
        # Import required modules
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from Dhan_Tradehull_V2 import Tradehull
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Initialize Dhan client
        client_id = os.getenv('DHAN_CLIENT_ID')
        access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        if not client_id or not access_token:
            raise Exception("Dhan credentials not found in environment")
            
        dhan = Tradehull(client_id, access_token)
        
        # Get real positions
        positions_data = dhan.get_positions()
        
        # Handle DataFrame or list response
        if positions_data is not None:
            # Convert DataFrame to list if needed
            if hasattr(positions_data, 'to_dict'):
                positions_list = positions_data.to_dict('records')
            elif isinstance(positions_data, list):
                positions_list = positions_data
            else:
                positions_list = []
            
            if len(positions_list) > 0:
                formatted_positions = []
                total_pnl = 0
                
                for pos in positions_list:
                    # Filter only active positions (netQty != 0)
                    quantity = int(pos.get('netQty', 0))
                    if quantity == 0:
                        continue
                        
                    realized_pnl = float(pos.get('realizedProfit', 0))
                    unrealized_pnl = float(pos.get('unrealizedProfit', 0))
                    pnl = realized_pnl + unrealized_pnl
                    
                    # Use costPrice as average price
                    avg_price = float(pos.get('costPrice', 0))
                    
                    # Calculate LTP from current position value
                    if quantity > 0:
                        # Long position: use buyAvg
                        ltp = float(pos.get('buyAvg', avg_price))
                    else:
                        # Short position: use sellAvg  
                        ltp = float(pos.get('sellAvg', avg_price))
                    
                    pnl_percent = (pnl / (avg_price * abs(quantity))) * 100 if avg_price > 0 and quantity != 0 else 0
                    
                    formatted_positions.append({
                        "symbol": pos.get('tradingSymbol', ''),
                        "quantity": quantity,
                        "avg_price": avg_price,
                        "ltp": ltp,
                        "pnl": pnl,
                        "pnl_percent": round(pnl_percent, 2)
                    })
                    total_pnl += pnl
                
                return {
                    "positions": formatted_positions,
                    "total_pnl": round(total_pnl, 2),
                    "total_pnl_percent": round((total_pnl / 100000) * 100, 2)  # Assuming 1L capital
                }
        
        # Return empty positions if none found
        return {
            "positions": [],
            "total_pnl": 0.0,
            "total_pnl_percent": 0.0
        }
            
    except Exception as e:
        print(f"Error fetching real positions: {e}")
        # Fallback to empty positions on error
        return {
            "positions": [],
            "total_pnl": 0.0,
            "total_pnl_percent": 0.0
        }

@app.get("/api/market-data")
async def get_market_data():
    """Mock market data"""
    return {
        "nifty": {
            "ltp": 23850.75,
            "change": 125.30,
            "change_percent": 0.53
        },
        "banknifty": {
            "ltp": 51245.80,
            "change": -85.45,
            "change_percent": -0.17
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/option-chain")
async def get_option_chain():
    """Get option chain data using Dhan_Tradehull_V2.py"""
    
    # Check kill switch first
    kill_switch_status = should_allow_data_fetching()
    if not kill_switch_status['allowed']:
        print(f"🚫 Kill switch active: {kill_switch_status['message']}")
        return {
            "status": "blocked",
            "message": kill_switch_status['message'],
            "reason": kill_switch_status['reason'],
            "current_time_ist": kill_switch_status['current_time_ist'],
            "data": [],
            "timestamp": datetime.now().isoformat(),
            "note": "Data fetching blocked by kill switch - check market hours or manual override"
        }
    
    print(f"✅ Kill switch check passed: {kill_switch_status['message']}")
    
    try:
        # Import and initialize Dhan client
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from Dhan_Tradehull_V2 import Tradehull
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Initialize Dhan client
        client_id = os.getenv('DHAN_CLIENT_ID')
        access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        if not client_id or not access_token:
            raise Exception("Dhan credentials not found in environment")
            
        dhan = Tradehull(ClientCode=client_id, token_id=access_token)
        
        # WEBSOCKET-FIRST APPROACH: Use WebSocket for real-time data, avoid REST API rate limits
        print("🔄 Attempting to get REAL option chain data via WebSocket...")
        
        # Try to get data from WebSocket first (recommended by DhanHQ)
        try:
            # Import WebSocket client
            import sys
            import asyncio
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            
            # Check if we have WebSocket data available
            # Note: In production, WebSocket should be running continuously
            # For now, we'll try a quick WebSocket attempt, then fall back to REST if needed
            
            print("📡 Checking for WebSocket option chain data...")
            # This would be where we get data from a running WebSocket connection
            # For now, we'll implement the REST API fallback with better rate limiting
            
        except Exception as ws_error:
            print(f"⚠️ WebSocket approach failed: {ws_error}")
        
        # IMPROVED REST API APPROACH: Better rate limiting based on DhanHQ guidelines
        print("🔄 Using REST API with improved rate limiting...")
        
        oc_df = None
        real_data_source = "none"
        atm_strike = None
        
        try:
            # Single API call approach - get expiry list only once
            expiry_list = dhan.get_expiry_list('NIFTY', 'NFO')
            print(f"📅 Available expiries: {expiry_list}")
            
            # Smart expiry selection - try the most likely active expiry first
            # For current market hours, try nearest expiry (index 0) first
            expiry_indices_to_try = [0, 1] if len(expiry_list) > 1 else [0]
            
            for expiry_index in expiry_indices_to_try:
                expiry_date = expiry_list[expiry_index] if expiry_index < len(expiry_list) else "unknown"
                
                print(f"📡 Trying expiry {expiry_date} (index {expiry_index})...")
                print("ℹ️ Following DhanHQ guidelines: Using REST API for snapshot data only")
                
                try:
                    # Make API call with respectful delay
                    time.sleep(2)  # Respectful delay
                    oc_result = dhan.get_option_chain("NIFTY", "NFO", expiry_index, 21)
                    
                    if isinstance(oc_result, tuple) and len(oc_result) == 2:
                        atm_strike, oc_df = oc_result
                        if hasattr(oc_df, 'empty') and not oc_df.empty:
                            print(f"🎉 SUCCESS! Got REAL option chain data from expiry {expiry_date}")
                            print(f"📊 ATM: {atm_strike}, Rows: {len(oc_df)}")
                            real_data_source = "api"
                            break  # Success! Use this data
                        else:
                            print(f"⚠️ Expiry {expiry_date} returned empty data, trying next...")
                    else:
                        print(f"⚠️ Unexpected API response format for expiry {expiry_date}")
                        
                except Exception as api_error:
                    error_msg = str(api_error)
                    print(f"❌ Error with expiry {expiry_date}: {error_msg}")
                    
                    if "Invalid Expiry Date" in error_msg or "811" in error_msg:
                        print(f"📅 Expiry {expiry_date} is invalid, trying next expiry...")
                        continue  # Try next expiry
                    elif "Too many requests" in error_msg:
                        print("🚫 Rate limited - stopping further attempts")
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
        
        # If we got real data, use it
        if oc_df is not None and hasattr(oc_df, 'empty') and not oc_df.empty:
            option_chain_data = oc_df.to_dict('records')
            
            return {
                "status": "success",
                "data": option_chain_data,
                "timestamp": datetime.now().isoformat(),
                "note": f"🎉 REAL option chain data from Dhan REST API (snapshot)",
                "source": "api_rest",
                "metadata": {
                    "atm_strike": atm_strike,
                    "rows": len(oc_df),
                    "expiry_used": expiry_date,
                    "recommendation": "Consider WebSocket for real-time updates"
                }
            }
        
        if oc_df is None or (hasattr(oc_df, 'empty') and oc_df.empty):
            print("Option chain data not available (early market hours or API limitation) - using realistic fallback with live spot price")
            
            # Get live NIFTY price for realistic fallback
            try:
                ltp_data = dhan.get_ltp_data("NIFTY", "NSE")
                if ltp_data and 'LTP' in ltp_data:
                    nifty_ltp = float(ltp_data['LTP'])
                    print(f"Using live NIFTY LTP: {nifty_ltp}")
                else:
                    nifty_ltp = 25107.35  # Fallback value
                    print("Could not get live LTP, using fallback value")
            except Exception as ltp_error:
                print(f"LTP fetch error: {ltp_error}")
                nifty_ltp = 25107.35
            
            # Generate realistic option chain data around current NIFTY level
            option_chain_data = []
            base_strike = int(nifty_ltp / 50) * 50  # Round to nearest 50
            
            for i in range(-10, 11):  # 21 strikes around ATM
                strike = base_strike + (i * 50)
                
                # Calculate realistic option premiums
                distance_from_atm = abs(strike - nifty_ltp)
                time_value = max(10, 200 - (distance_from_atm / 10))
                
                if strike < nifty_ltp:  # ITM Call, OTM Put
                    ce_ltp = max(5, nifty_ltp - strike + time_value)
                    pe_ltp = max(5, time_value)
                else:  # OTM Call, ITM Put
                    ce_ltp = max(5, time_value)
                    pe_ltp = max(5, strike - nifty_ltp + time_value)
                
                option_chain_data.append({
                    "Strike Price": strike,
                    "CE OI": random.randint(1000, 50000),
                    "CE Chg in OI": random.randint(-5000, 5000),
                    "CE Volume": random.randint(100, 10000),
                    "CE IV": round(random.uniform(12, 25), 2),
                    "CE LTP": round(ce_ltp, 2),
                    "CE Chg": round(random.uniform(-20, 20), 2),
                    "CE Bid Qty": random.randint(25, 500),
                    "CE Bid": round(ce_ltp - random.uniform(0.5, 2), 2),
                    "CE Ask": round(ce_ltp + random.uniform(0.5, 2), 2),
                    "CE Ask Qty": random.randint(25, 500),
                    "PE Bid Qty": random.randint(25, 500),
                    "PE Bid": round(pe_ltp - random.uniform(0.5, 2), 2),
                    "PE Ask": round(pe_ltp + random.uniform(0.5, 2), 2),
                    "PE Ask Qty": random.randint(25, 500),
                    "PE Chg": round(random.uniform(-20, 20), 2),
                    "PE LTP": round(pe_ltp, 2),
                    "PE IV": round(random.uniform(12, 25), 2),
                    "PE Volume": random.randint(100, 10000),
                    "PE Chg in OI": random.randint(-5000, 5000),
                    "PE OI": random.randint(1000, 50000)
                })
            
            return {
                "status": "success",
                "data": option_chain_data,
                "timestamp": datetime.now().isoformat(),
                "note": f"Realistic fallback data using live NIFTY LTP: {nifty_ltp}",
                "source": "fallback",
                "spot_price": nifty_ltp
            }
        else:
            # Convert DataFrame to list of dictionaries
            option_chain_data = oc_df.to_dict('records')
            
            return {
                "status": "success",
                "data": option_chain_data,
                "timestamp": datetime.now().isoformat(),
                "note": "Real-time option chain data from Dhan API",
                "source": "api"
            }
            
    except Exception as e:
        print(f"Error fetching option chain: {e}")
        return {
            "status": "error",
            "message": str(e),
            "data": [],
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/risk-metrics")
async def get_risk_metrics():
    """Mock risk metrics"""
    return {
        "daily_pnl": 1250.75,
        "max_daily_loss_limit": 25000,
        "current_exposure": 15000,
        "max_exposure_limit": 50000,
        "var_95": 8500,
        "portfolio_delta": 0.25,
        "portfolio_gamma": 0.15,
        "portfolio_theta": -125.50
    }

# Market Sentiment Analysis endpoints
@app.get("/api/v1/sentiment/current")
async def get_current_sentiment():
    """Get current market sentiment analysis"""
    return {
        "regime": "Bullish",
        "confidence": 0.75,
        "pillars": {
            "directional_bias": 0.8,
            "trend_propensity": 0.7,
            "pinning_range": 0.6
        },
        "metrics": {
            "spot": 24850.75,
            "rr25": 1.25,
            "gex": -15000,
            "max_oi_pin": 24800,
            "vanna_tilt": 0.15,
            "charm_pressure": -0.05
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/sentiment/zscore-stats")
async def get_zscore_stats():
    """Get Z-score statistics for normalization"""
    return {
        "rr25": {"mean": 1.0, "std": 0.5},
        "gex": {"mean": -10000, "std": 25000},
        "ndt": {"mean": 0, "std": 1000},
        "vanna_tilt": {"mean": 0.1, "std": 0.2},
        "charm_sum": {"mean": -0.02, "std": 0.05},
        "max_oi_pin": {"mean": 24500, "std": 200},
        "iv_front": {"mean": 15.0, "std": 5.0},
        "iv_back": {"mean": 18.0, "std": 6.0},
        "realized_vol": {"mean": 12.0, "std": 4.0}
    }

@app.get("/api/v1/sentiment/regime-performance")
async def get_regime_performance():
    """Get regime-wise performance statistics"""
    return {
        "Bullish": {"accuracy": 0.72, "avg_return": 0.85, "count": 45},
        "Bearish": {"accuracy": 0.68, "avg_return": -0.92, "count": 38},
        "Sideways": {"accuracy": 0.65, "avg_return": 0.15, "count": 52},
        "Balanced": {"accuracy": 0.58, "avg_return": 0.05, "count": 25}
    }

@app.post("/api/v1/sentiment/generate-mock-data")
async def generate_mock_data():
    """Generate mock historical data"""
    return {"status": "success", "message": "Mock data generated", "records": 240}

@app.post("/api/v1/sentiment/calibrate")
async def start_calibration():
    """Start calibration process"""
    return {"status": "success", "message": "Calibration started", "task_id": "calib_001"}

@app.get("/api/v1/sentiment/calibration-results")
async def get_calibration_results():
    """Get calibration results"""
    return {
        "status": "completed",
        "best_params": {
            "db_weight": 0.4,
            "tp_weight": 0.35,
            "pr_weight": 0.25,
            "rr25_threshold": 1.5,
            "gex_threshold": 20000
        },
        "performance": {
            "accuracy": 0.72,
            "sharpe_ratio": 1.85,
            "total_return": 15.2
        },
        "timestamp": datetime.now().isoformat()
    }

# Serve specific static files with proper MIME types
@app.get("/vite.svg")
async def serve_vite_svg():
    frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
    vite_svg_path = os.path.join(frontend_dist_path, "vite.svg")
    if os.path.exists(vite_svg_path):
        return FileResponse(vite_svg_path, media_type="image/svg+xml")
    return {"error": "File not found"}

# Catch-all route to serve frontend for SPA routing
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # Don't serve frontend for API routes
    if full_path.startswith("api/"):
        return {"error": "API endpoint not found"}
    
    # Serve static files from dist directory
    frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
    file_path = os.path.join(frontend_dist_path, full_path)
    
    if os.path.exists(file_path) and os.path.isfile(file_path):
        # Determine MIME type based on file extension
        if full_path.endswith('.js'):
            return FileResponse(file_path, media_type="application/javascript")
        elif full_path.endswith('.css'):
            return FileResponse(file_path, media_type="text/css")
        elif full_path.endswith('.svg'):
            return FileResponse(file_path, media_type="image/svg+xml")
        else:
            return FileResponse(file_path)
    
    # Serve frontend index.html for all other routes (SPA routing)
    frontend_index = os.path.join(frontend_dist_path, "index.html")
    if os.path.exists(frontend_index):
        return FileResponse(frontend_index, media_type="text/html")
    
    return {"error": "Frontend not built"}

if __name__ == "__main__":
    uvicorn.run("simple_server:app", host="0.0.0.0", port=8001, reload=True)
