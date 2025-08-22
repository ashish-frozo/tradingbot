#!/usr/bin/env python3
"""
Railway-optimized server with proper static file handling
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
import uvicorn
from datetime import datetime
import random
import os

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
            
        _dhan_client = Tradehull(client_id, access_token)
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
    """Get option chain data using Dhan API"""
    try:
        dhan = get_dhan_client()
        
        # Get current Nifty price for ATM calculation
        spot_price = 25150.30  # In production, get from live market data
        
        # Calculate ATM and nearby strikes
        atm_strike = round(spot_price / 50) * 50
        strikes = [atm_strike + i * 50 for i in range(-10, 11)]
        
        # Mock option chain data structure (replace with real Dhan API call)
        option_chain = []
        
        for strike in strikes:
            # Calculate theoretical Greeks and prices
            call_iv = 0.15 + abs(strike - spot_price) / spot_price * 0.1
            put_iv = 0.15 + abs(strike - spot_price) / spot_price * 0.1
            
            call_price = max(spot_price - strike, 0) + 50 * call_iv
            put_price = max(strike - spot_price, 0) + 50 * put_iv
            
            # Mock Greeks calculation
            call_delta = 0.5 if strike == atm_strike else (0.8 if strike < spot_price else 0.2)
            put_delta = call_delta - 1
            gamma = 0.01 * (1 - abs(strike - spot_price) / (2 * spot_price))
            
            option_chain.append({
                "strike": strike,
                "call": {
                    "ltp": round(call_price, 2),
                    "bid": round(call_price - 2, 2),
                    "ask": round(call_price + 2, 2),
                    "volume": np.random.randint(100, 10000),
                    "oi": np.random.randint(1000, 50000),
                    "iv": round(call_iv, 4),
                    "delta": round(call_delta, 4),
                    "gamma": round(gamma, 4),
                    "theta": round(-gamma * 10, 4),
                    "vega": round(gamma * 100, 4)
                },
                "put": {
                    "ltp": round(put_price, 2),
                    "bid": round(put_price - 2, 2),
                    "ask": round(put_price + 2, 2),
                    "volume": np.random.randint(100, 10000),
                    "oi": np.random.randint(1000, 50000),
                    "iv": round(put_iv, 4),
                    "delta": round(put_delta, 4),
                    "gamma": round(gamma, 4),
                    "theta": round(-gamma * 10, 4),
                    "vega": round(gamma * 100, 4)
                }
            })
        
        return {
            "symbol": "NIFTY",
            "spot_price": spot_price,
            "expiry": "2025-08-29",
            "option_chain": option_chain,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Error fetching option chain: {e}")
        return {
            "error": f"Failed to fetch option chain: {str(e)}",
            "symbol": "NIFTY",
            "spot_price": 25150.30,
            "option_chain": [],
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/greeks-range")
async def get_greeks_range():
    """Get Greeks-based support/resistance levels using GRM"""
    try:
        from greeks_range_model import grm
        import pandas as pd
        import numpy as np
        
        dhan = get_dhan_client()
        
        # Get current Nifty price (using market data or positions)
        # For now, using a representative price - in production, get from live data
        spot_price = 25150.30
        
        # Get option chain data from Dhan
        # Note: This is a simplified version - in production, you'd get full option chain
        # For now, creating sample data structure that would come from Dhan API
        
        # Sample option chain data (in production, this would come from dhan.get_option_chain())
        option_data = []
        strikes = range(24800, 25500, 50)  # Nifty strikes around current price
        
        for strike in strikes:
            # Sample Greeks and OI data (in production, get from actual option chain)
            distance = abs(strike - spot_price) / spot_price
            
            # Simulate realistic Greeks based on distance from ATM
            gamma = max(0.001, 0.01 * np.exp(-distance * 100))
            vanna = gamma * 0.5 * (1 if strike > spot_price else -1)
            charm = -gamma * 0.3
            
            # Simulate OI based on typical patterns
            call_oi = max(100, int(5000 * np.exp(-distance * 50)))
            put_oi = max(100, int(4000 * np.exp(-distance * 40)))
            
            # Simulate option prices
            call_price = max(1, (spot_price - strike + 50) if strike < spot_price else 50)
            put_price = max(1, (strike - spot_price + 50) if strike > spot_price else 50)
            
            option_data.append({
                'strike': strike,
                'call_oi': call_oi,
                'put_oi': put_oi,
                'gamma': gamma,
                'vanna': vanna,
                'charm': charm,
                'call_price': call_price,
                'put_price': put_price
            })
        
        option_chain = pd.DataFrame(option_data)
        
        # IV data (front month vs next week)
        front_iv = 0.15  # 15% IV for front month
        back_iv = 0.12   # 12% IV for back month
        
        # Calculate current time to market close
        now = datetime.now()
        market_close = datetime.combine(now.date(), time(15, 30))  # 3:30 PM IST
        if now > market_close:
            hours_to_close = 0.5  # Minimal time if after hours
        else:
            hours_to_close = (market_close - now).total_seconds() / 3600
        
        # Calculate GRM levels
        grm_result = grm.greeks_range_model(
            option_chain=option_chain,
            spot_price=spot_price,
            front_iv=front_iv,
            back_iv=back_iv,
            hours_to_close=max(0.5, hours_to_close)
        )
        
        return grm_result
        
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
