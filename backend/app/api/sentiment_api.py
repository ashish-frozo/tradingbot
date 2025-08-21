"""
API endpoints for Market Sentiment Analysis
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio

from ..services.historical_data_service import historical_service, HistoricalSignal
from ..services.calibration_service import calibration_service, CalibrationParams

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

@router.get("/current")
async def get_current_sentiment():
    """Get current market sentiment analysis"""
    try:
        # Get current Z-score stats
        zscore_stats = historical_service.get_cached_stats()
        
        # Mock current market data (replace with real data in production)
        current_signal = HistoricalSignal(
            date=datetime.now().strftime('%Y-%m-%d'),
            timestamp=datetime.now().isoformat(),
            spot=24500,
            ndt=500,
            gex_atm=-25000,
            charm_sum=0.05,
            rr25=1.2,
            vanna_tilt=5000,
            fb_ratio=1.18,
            pin_distance=0.25,
            iv_front_atm=18.5,
            rv_30m=16.2,
            regime="Unknown"
        )
        
        # Use default calibration parameters
        params = CalibrationParams()
        
        # Calculate regime and confidence
        regime, confidence = calibration_service.classify_regime_with_params(
            current_signal, params, zscore_stats
        )
        
        return {
            "regime": regime,
            "confidence": confidence,
            "asof": current_signal.timestamp,
            "drivers": {
                "DB": 1,  # Mock values - replace with actual calculation
                "TP": 2,
                "PR": 0,
                "RR25": current_signal.rr25,
                "GEX_atm_z": historical_service.calculate_zscore(
                    current_signal.gex_atm, 'gex_atm', zscore_stats
                ),
                "pin_dist_pct": current_signal.pin_distance,
                "ZG": 24450,
                "NDT_z": historical_service.calculate_zscore(
                    current_signal.ndt, 'ndt', zscore_stats
                ),
                "VT": current_signal.vanna_tilt,
                "FB_ratio": current_signal.fb_ratio
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_zscore_stats():
    """Get current Z-score statistics"""
    try:
        stats = historical_service.get_zscore_stats()
        return {
            metric: {
                "mean": stat.mean,
                "std": stat.std,
                "count": stat.count,
                "last_updated": stat.last_updated
            }
            for metric, stat in stats.items()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/store-signal")
async def store_historical_signal(signal_data: dict):
    """Store a historical signal for calibration"""
    try:
        signal = HistoricalSignal(
            date=signal_data['date'],
            timestamp=signal_data['timestamp'],
            spot=signal_data['spot'],
            ndt=signal_data['ndt'],
            gex_atm=signal_data['gex_atm'],
            charm_sum=signal_data['charm_sum'],
            rr25=signal_data['rr25'],
            vanna_tilt=signal_data['vanna_tilt'],
            fb_ratio=signal_data['fb_ratio'],
            pin_distance=signal_data['pin_distance'],
            iv_front_atm=signal_data['iv_front_atm'],
            rv_30m=signal_data['rv_30m'],
            regime=signal_data['regime'],
            next_6h_return=signal_data.get('next_6h_return')
        )
        
        success = historical_service.store_signal(signal)
        
        if success:
            return {"status": "success", "message": "Signal stored successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to store signal")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/{regime}")
async def get_regime_performance(regime: str, days: int = 30):
    """Get historical performance for a specific regime"""
    try:
        performance = historical_service.get_historical_performance(regime, days)
        return performance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/calibrate")
async def calibrate_parameters(background_tasks: BackgroundTasks, 
                             lookback_days: int = 60):
    """Run parameter calibration optimization"""
    try:
        # Run calibration in background
        background_tasks.add_task(run_calibration, lookback_days)
        
        return {
            "status": "started",
            "message": f"Calibration started with {lookback_days} days of data"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/calibration-result")
async def get_calibration_result():
    """Get latest calibration result"""
    try:
        # Load from file (simplified)
        import json
        from pathlib import Path
        
        result_file = Path("data/calibration_result.json")
        if not result_file.exists():
            return {"status": "no_calibration", "message": "No calibration result found"}
        
        with open(result_file, 'r') as f:
            result = json.load(f)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-mock-data")
async def generate_mock_data(days: int = 60):
    """Generate mock historical data for testing"""
    try:
        historical_service.generate_mock_historical_data(days)
        return {
            "status": "success",
            "message": f"Generated {days} days of mock data"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cleanup-data")
async def cleanup_old_data(keep_days: int = 90):
    """Clean up old historical data"""
    try:
        deleted_count = historical_service.cleanup_old_data(keep_days)
        return {
            "status": "success",
            "message": f"Deleted {deleted_count} old records"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_calibration(lookback_days: int):
    """Background task to run calibration"""
    try:
        print(f"Starting calibration with {lookback_days} days...")
        result = calibration_service.optimize_parameters(lookback_days)
        calibration_service.save_calibration_result(result)
        print("Calibration completed successfully")
    except Exception as e:
        print(f"Calibration failed: {e}")
