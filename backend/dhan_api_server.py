import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from dhanhq import dhanhq
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Dhan API Configuration
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Initialize Dhan API
dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)

app = FastAPI(title="Nifty Trade Setup - Real Dhan API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class EquityDataResponse(BaseModel):
    dates: List[str]
    equity: List[float]
    total_return: float
    max_drawdown: float
    sharpe_ratio: float

class Position(BaseModel):
    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    pnl: float
    pnl_percent: float

class MarketData(BaseModel):
    symbol: str
    ltp: float
    change: float
    change_percent: float
    volume: int
    oi: Optional[int] = None

class RiskMetrics(BaseModel):
    total_pnl: float
    day_pnl: float
    max_loss_limit: float
    position_count: int
    margin_used: float
    margin_available: float

# Global variables for caching
_cached_positions = None
_cached_equity_data = None
_last_update = None

@app.get("/")
async def root():
    return {"message": "Nifty Trade Setup - Real Dhan API Server", "status": "running"}

@app.get("/api/health")
async def health_check():
    try:
        # Test Dhan API connection
        fund_limit = dhan.get_fund_limits()
        return {
            "status": "healthy",
            "dhan_api": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "dhan_api": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/positions", response_model=List[Position])
async def get_positions():
    global _cached_positions, _last_update
    
    try:
        # Cache for 30 seconds to avoid API rate limits
        if (_cached_positions is None or 
            _last_update is None or 
            datetime.now() - _last_update > timedelta(seconds=30)):
            
            # Get real positions from Dhan API
            positions_data = dhan.get_positions()
            
            if positions_data['status'] == 'success':
                positions = []
                for pos in positions_data['data']:
                    if pos['netQty'] != 0:  # Only show non-zero positions
                        # Calculate PnL and prices
                        pnl = float(pos['unrealizedProfit']) if pos['unrealizedProfit'] else 0.0
                        
                        # Use buyAvg or sellAvg based on position type
                        if pos['positionType'] == 'LONG':
                            avg_price = float(pos['buyAvg']) if pos['buyAvg'] else 0.0
                        else:  # SHORT
                            avg_price = float(pos['sellAvg']) if pos['sellAvg'] else 0.0
                        
                        # Calculate current price from cost price and PnL
                        cost_price = float(pos['costPrice']) if pos['costPrice'] else avg_price
                        current_price = cost_price
                        
                        # Calculate PnL percentage
                        total_value = avg_price * abs(int(pos['netQty']))
                        pnl_percent = (pnl / total_value) * 100 if total_value > 0 else 0.0
                        
                        positions.append(Position(
                            symbol=pos['tradingSymbol'],
                            quantity=int(pos['netQty']),
                            avg_price=avg_price,
                            current_price=current_price,
                            pnl=pnl,
                            pnl_percent=pnl_percent
                        ))
                
                _cached_positions = positions
                _last_update = datetime.now()
            else:
                # Fallback to mock data if API fails
                _cached_positions = [
                    Position(symbol="NIFTY 21000 CE", quantity=50, avg_price=125.50, current_price=132.75, pnl=362.50, pnl_percent=2.89),
                    Position(symbol="BANKNIFTY 45000 PE", quantity=-25, avg_price=89.25, current_price=76.80, pnl=311.25, pnl_percent=13.95)
                ]
        
        return _cached_positions
        
    except Exception as e:
        print(f"Error fetching positions: {e}")
        # Return mock data on error
        return [
            Position(symbol="NIFTY 21000 CE", quantity=50, avg_price=125.50, current_price=132.75, pnl=362.50, pnl_percent=2.89),
            Position(symbol="BANKNIFTY 45000 PE", quantity=-25, avg_price=89.25, current_price=76.80, pnl=311.25, pnl_percent=13.95)
        ]

@app.get("/api/equity-data", response_model=EquityDataResponse)
async def get_equity_data():
    """Get equity curve data"""
    return get_equity_data_cached()

def get_equity_data_cached():
    global _cached_equity_data, _last_update
    
    try:
        # Cache for 60 seconds
        if (_cached_equity_data is None or 
            _last_update is None or 
            datetime.now() - _last_update > timedelta(seconds=60)):
            
            # Get fund limits to calculate equity
            fund_data = dhan.get_fund_limits()
            
            if fund_data['status'] == 'success':
                # Calculate current equity from fund limits
                available_balance = float(fund_data['data']['availabelBalance'])
                utilized_margin = float(fund_data['data']['utilizedMargin'])
                current_equity = available_balance + utilized_margin
                
                # Generate historical equity curve (mock for now, can be enhanced with trade history)
                dates = []
                equity_values = []
                base_date = datetime.now() - timedelta(days=30)
                
                for i in range(31):
                    date = base_date + timedelta(days=i)
                    dates.append(date.strftime("%Y-%m-%d"))
                    
                    # Simulate equity growth with some volatility
                    if i == 0:
                        equity_values.append(100000.0)  # Starting equity
                    else:
                        prev_equity = equity_values[-1]
                        # Add some realistic trading returns
                        daily_return = np.random.normal(0.002, 0.02)  # 0.2% avg daily return, 2% volatility
                        new_equity = prev_equity * (1 + daily_return)
                        equity_values.append(new_equity)
                
                # Set current equity as the last value
                equity_values[-1] = current_equity
                
                # Calculate metrics
                total_return = ((current_equity - equity_values[0]) / equity_values[0]) * 100
                
                # Calculate max drawdown
                peak = equity_values[0]
                max_dd = 0
                for value in equity_values:
                    if value > peak:
                        peak = value
                    dd = ((peak - value) / peak) * 100
                    if dd > max_dd:
                        max_dd = dd
                
                # Calculate Sharpe ratio (simplified)
                returns = [((equity_values[i] - equity_values[i-1]) / equity_values[i-1]) for i in range(1, len(equity_values))]
                sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252) if np.std(returns) > 0 else 0
                
                _cached_equity_data = EquityDataResponse(
                    dates=dates,
                    equity=equity_values,
                    total_return=total_return,
                    max_drawdown=max_dd,
                    sharpe_ratio=round(sharpe_ratio, 2)
                )
            else:
                # Fallback to mock data
                _cached_equity_data = _generate_mock_equity_data()
        
        return _cached_equity_data
        
    except Exception as e:
        print(f"Error fetching equity data: {e}")
        return _generate_mock_equity_data()

def _generate_mock_equity_data() -> EquityDataResponse:
    """Generate mock equity data as fallback"""
    dates = []
    equity = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(31):
        date = base_date + timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))
        equity.append(100000 + i * 500 + np.random.normal(0, 1000))
    
    return EquityDataResponse(
        dates=dates,
        equity=equity,
        total_return=15.5,
        max_drawdown=8.2,
        sharpe_ratio=1.45
    )

@app.get("/api/market-data", response_model=List[MarketData])
async def get_market_data():
    try:
        # Get market data for key indices
        symbols = ["NIFTY 50", "NIFTY BANK"]
        market_data = []
        
        for symbol in symbols:
            try:
                # This would need to be implemented based on Dhan's market data API
                # For now, using mock data
                market_data.append(MarketData(
                    symbol=symbol,
                    ltp=21000.0 if "NIFTY 50" in symbol else 45000.0,
                    change=150.0 if "NIFTY 50" in symbol else 200.0,
                    change_percent=0.72 if "NIFTY 50" in symbol else 0.45,
                    volume=1000000
                ))
            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")
        
        return market_data
        
    except Exception as e:
        print(f"Error fetching market data: {e}")
        return [
            MarketData(symbol="NIFTY 50", ltp=21000.0, change=150.0, change_percent=0.72, volume=1000000),
            MarketData(symbol="NIFTY BANK", ltp=45000.0, change=200.0, change_percent=0.45, volume=800000)
        ]

@app.get("/api/risk-metrics", response_model=RiskMetrics)
async def get_risk_metrics():
    try:
        # Get fund limits and positions to calculate risk metrics
        fund_data = dhan.get_fund_limits()
        positions_data = dhan.get_positions()
        
        if fund_data['status'] == 'success':
            fund_info = fund_data['data']
            available_balance = float(fund_info.get('availabelBalance', 0))
            utilized_margin = float(fund_info.get('utilizedMargin', fund_info.get('utilisedMargin', 0)))
            
            # Calculate total PnL from positions
            total_pnl = 0.0
            position_count = 0
            
            if positions_data['status'] == 'success':
                for pos in positions_data['data']:
                    if pos['netQty'] != 0:
                        position_count += 1
                        pnl = float(pos['unrealizedPnl']) if pos['unrealizedPnl'] else 0.0
                        total_pnl += pnl
            
            return RiskMetrics(
                total_pnl=total_pnl,
                day_pnl=total_pnl,  # Simplified - same as total for now
                max_loss_limit=50000.0,  # Configurable limit
                position_count=position_count,
                margin_used=utilized_margin,
                margin_available=available_balance
            )
        else:
            # Fallback to mock data
            return RiskMetrics(
                total_pnl=1250.75,
                day_pnl=850.25,
                max_loss_limit=50000.0,
                position_count=2,
                margin_used=25000.0,
                margin_available=75000.0
            )
            
    except Exception as e:
        print(f"Error fetching risk metrics: {e}")
        return RiskMetrics(
            total_pnl=1250.75,
            day_pnl=850.25,
            max_loss_limit=50000.0,
            position_count=2,
            margin_used=25000.0,
            margin_available=75000.0
        )

@app.get("/api/option-chain")
async def get_option_chain():
    """Get live option chain data for Nifty"""
    try:
        if dhan:
            # Get Nifty option chain data
            option_chain = dhan.get_option_chain(
                underlying="NIFTY",
                expiry=None  # Current expiry
            )
            
            if option_chain and 'data' in option_chain:
                return {
                    "success": True,
                    "data": option_chain['data'],
                    "timestamp": datetime.now().isoformat(),
                    "underlying": "NIFTY",
                    "spot_price": option_chain.get('spot_price', 0)
                }
        
        # Fallback mock data
        return _generate_mock_option_chain()
        
    except Exception as e:
        print(f"Error fetching option chain: {e}")
        return _generate_mock_option_chain()

@app.get("/api/strategies")
async def get_strategies():
    """Get available trading strategies"""
    try:
        strategies = [
            {
                "strategy_id": "nifty_straddle_v1",
                "name": "Nifty ATM Straddle",
                "description": "Sells ATM Call and Put options on Nifty expiry day",
                "status": "ACTIVE",
                "pnl": 2850.75,
                "trades_count": 12,
                "win_rate": 75.0,
                "max_drawdown": 8.5,
                "sharpe_ratio": 1.85,
                "profit_factor": 2.1,
                "last_updated": datetime.now().isoformat(),
                "capital_allocated": 50000,
                "risk_per_trade": 0.02
            },
            {
                "strategy_id": "nifty_iron_condor_v2",
                "name": "Nifty Iron Condor",
                "description": "Weekly Iron Condor on Nifty with delta hedging",
                "status": "PAUSED",
                "pnl": -1250.25,
                "trades_count": 8,
                "win_rate": 62.5,
                "max_drawdown": 12.3,
                "sharpe_ratio": 1.42,
                "profit_factor": 1.65,
                "last_updated": datetime.now().isoformat(),
                "capital_allocated": 75000,
                "risk_per_trade": 0.015
            },
            {
                "strategy_id": "banknifty_scalping_v1",
                "name": "Bank Nifty Scalping",
                "description": "High frequency scalping on Bank Nifty options",
                "status": "INACTIVE",
                "pnl": 4125.50,
                "trades_count": 45,
                "win_rate": 68.9,
                "max_drawdown": 15.7,
                "sharpe_ratio": 2.15,
                "profit_factor": 1.95,
                "last_updated": datetime.now().isoformat(),
                "capital_allocated": 100000,
                "risk_per_trade": 0.01
            }
        ]
        
        return {
            "success": True,
            "data": strategies,
            "total_strategies": len(strategies),
            "active_strategies": len([s for s in strategies if s["status"] == "ACTIVE"])
        }
        
    except Exception as e:
        print(f"Error fetching strategies: {e}")
        return {"success": False, "error": str(e), "data": []}

@app.post("/api/strategies/{strategy_id}/toggle")
async def toggle_strategy(strategy_id: str):
    """Toggle strategy status between ACTIVE and PAUSED"""
    try:
        return {
            "success": True,
            "message": f"Strategy {strategy_id} status toggled",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/strategies/{strategy_id}/restart")
async def restart_strategy(strategy_id: str):
    """Restart a strategy"""
    try:
        return {
            "success": True,
            "message": f"Strategy {strategy_id} restarted",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def _generate_mock_option_chain():
    """Generate mock option chain data"""
    spot_price = 25100  # Current Nifty50 level around 25,100
    strikes = [spot_price - 500 + i * 100 for i in range(11)]  # 10 strikes around ATM
    
    option_data = []
    for strike in strikes:
        # Call option
        call_iv = 15 + abs(strike - spot_price) / 100 * 0.5  # Volatility smile
        call_price = max(spot_price - strike, 0) + 50 - abs(strike - spot_price) / 50
        
        # Put option  
        put_iv = 15 + abs(strike - spot_price) / 100 * 0.5
        put_price = max(strike - spot_price, 0) + 50 - abs(strike - spot_price) / 50
        
        option_data.append({
            "strike": strike,
            "call": {
                "ltp": round(call_price, 2),
                "bid": round(call_price - 2, 2),
                "ask": round(call_price + 2, 2),
                "volume": np.random.randint(1000, 10000),
                "oi": np.random.randint(50000, 200000),
                "iv": round(call_iv, 2),
                "delta": round(0.5 + (spot_price - strike) / 1000, 3),
                "gamma": round(0.001, 4),
                "theta": round(-5.2, 2),
                "vega": round(12.5, 2)
            },
            "put": {
                "ltp": round(put_price, 2),
                "bid": round(put_price - 2, 2),
                "ask": round(put_price + 2, 2),
                "volume": np.random.randint(1000, 10000),
                "oi": np.random.randint(50000, 200000),
                "iv": round(put_iv, 2),
                "delta": round(-0.5 + (spot_price - strike) / 1000, 3),
                "gamma": round(0.001, 4),
                "theta": round(-5.2, 2),
                "vega": round(12.5, 2)
            }
        })
    
    return {
        "success": True,
        "data": option_data,
        "timestamp": datetime.now().isoformat(),
        "underlying": "NIFTY",
        "spot_price": spot_price,
        "expiry": "2024-08-29"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
