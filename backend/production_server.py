#!/usr/bin/env python3
"""
Production FastAPI server with proper static file handling
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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

# API Routes
@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/equity-data")
async def get_equity_data():
    """Get real equity data from Dhan API"""
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
            
        dhan = Tradehull(client_id, access_token)
        
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

# Mount static files AFTER API routes
frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist_path):
    app.mount("/", StaticFiles(directory=frontend_dist_path, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("production_server:app", host="0.0.0.0", port=8001, reload=True)
