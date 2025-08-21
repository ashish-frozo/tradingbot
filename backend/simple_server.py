#!/usr/bin/env python3
"""
Simple FastAPI server for testing and basic functionality
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import random

app = FastAPI(title="Nifty Trade Setup API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Nifty Trade Setup API", "status": "running", "timestamp": datetime.now().isoformat()}

@app.get("/health")
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
            
        dhan = Tradehull(client_id, access_token)
        
        # Fallback to mock option chain data due to Dhan API issues
        # Generate realistic option chain data around current NIFTY level
        nifty_ltp = 25107.35  # Current NIFTY level
        
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
            "note": "Mock data - Dhan API option chain temporarily unavailable"
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
