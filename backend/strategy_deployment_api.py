"""
Strategy Deployment API - Execute strategies from StrategySelector recommendations
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime
import asyncio

from app.orders.executor import OrderExecutor
from app.broker.tradehull_client import DhanTradehullClient
from app.risk.manager import RiskManager
from app.cache.redis import RedisManager

router = APIRouter(prefix="/api/strategy", tags=["strategy-deployment"])

@router.post("/deploy")
async def deploy_strategy(strategy_recommendation: Dict[str, Any]):
    """
    Deploy a strategy recommendation from StrategySelector
    
    Expected format:
    {
        "strategy": "Expiry Iron Fly",
        "legs": [
            {"type": "SELL", "opt": "CALL", "strike": 25000, "dte": "today"},
            {"type": "SELL", "opt": "PUT", "strike": 25000, "dte": "today"},
            {"type": "BUY", "opt": "CALL", "strike": 25050, "dte": "today"},
            {"type": "BUY", "opt": "PUT", "strike": 24950, "dte": "today"}
        ],
        "suggestedLots": 2,
        "maxRisk": 10000
    }
    """
    try:
        # Initialize components (in production, these would be injected)
        broker_client = DhanTradehullClient()
        risk_manager = RiskManager()
        redis_manager = RedisManager()
        order_executor = OrderExecutor(broker_client, redis_manager)
        
        # Validate strategy recommendation
        if not strategy_recommendation.get("legs"):
            raise HTTPException(status_code=400, detail="No strategy legs provided")
        
        # Convert strategy legs to order requests
        order_requests = []
        for leg in strategy_recommendation["legs"]:
            # Convert leg to order format
            order_request = {
                "symbol": f"NIFTY{leg['strike']}{leg['opt'][0]}E",  # NIFTY25000CE format
                "quantity": strategy_recommendation.get("suggestedLots", 1) * 50,  # NIFTY lot size
                "transaction_type": "BUY" if leg["type"] == "BUY" else "SELL",
                "product_type": "MIS",  # Intraday
                "order_type": "MARKET",  # Market orders for immediate execution
                "validity": "DAY"
            }
            order_requests.append(order_request)
        
        # Execute orders through OrderExecutor
        execution_results = []
        for order_request in order_requests:
            result = await order_executor.execute_order(
                order_request=order_request,
                strategy_id="strategy_selector_auto",
                priority="HIGH"
            )
            execution_results.append(result)
        
        return {
            "status": "success",
            "strategy": strategy_recommendation["strategy"],
            "orders_placed": len(execution_results),
            "execution_results": execution_results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Strategy deployment failed: {str(e)}")

@router.post("/schedule-deployment")
async def schedule_strategy_deployment(
    strategy_recommendation: Dict[str, Any],
    deployment_time: str = "09:45"  # HH:MM format
):
    """
    Schedule a strategy for automatic deployment at specified time
    """
    try:
        # Parse deployment time
        hour, minute = map(int, deployment_time.split(":"))
        
        # Calculate seconds until deployment
        now = datetime.now()
        deployment_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if deployment_datetime <= now:
            # If time has passed today, schedule for tomorrow
            deployment_datetime = deployment_datetime.replace(day=deployment_datetime.day + 1)
        
        seconds_until_deployment = (deployment_datetime - now).total_seconds()
        
        # Schedule deployment
        asyncio.create_task(_delayed_deployment(strategy_recommendation, seconds_until_deployment))
        
        return {
            "status": "scheduled",
            "strategy": strategy_recommendation["strategy"],
            "deployment_time": deployment_datetime.isoformat(),
            "seconds_until_deployment": seconds_until_deployment
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scheduling failed: {str(e)}")

async def _delayed_deployment(strategy_recommendation: Dict[str, Any], delay_seconds: float):
    """Internal function to handle delayed strategy deployment"""
    await asyncio.sleep(delay_seconds)
    
    try:
        # Deploy the strategy
        result = await deploy_strategy(strategy_recommendation)
        print(f"🚀 AUTO-DEPLOYED STRATEGY: {result}")
        
    except Exception as e:
        print(f"❌ AUTO-DEPLOYMENT FAILED: {e}")
