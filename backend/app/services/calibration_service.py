"""
Calibration Service for Market Sentiment Analysis
Optimizes thresholds and weights for maximum trading performance
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from scipy.optimize import minimize
from sklearn.metrics import classification_report, confusion_matrix
import json

from .historical_data_service import HistoricalDataService, HistoricalSignal

@dataclass
class CalibrationParams:
    """Parameters for sentiment analysis calibration"""
    rr25_bullish_threshold: float = 1.0
    rr25_bearish_threshold: float = -1.0
    ndt_zscore_threshold: float = 0.5
    gex_zscore_short_gamma: float = -1.0
    gex_zscore_long_gamma: float = 1.0
    pin_distance_expiry: float = 0.30
    pin_distance_normal: float = 0.45
    charm_zscore_threshold: float = 0.5
    iv_rv_threshold: float = 3.0
    fb_ratio_threshold: float = 1.15
    
    # Confidence weights
    db_weight: float = 0.6
    tp_weight: float = 0.8
    pr_weight: float = 0.6

@dataclass
class CalibrationResult:
    """Result of calibration optimization"""
    params: CalibrationParams
    accuracy: float
    precision: Dict[str, float]
    recall: Dict[str, float]
    f1_score: Dict[str, float]
    sharpe_ratio: float
    total_return: float
    max_drawdown: float
    regime_performance: Dict[str, Dict[str, float]]

class CalibrationService:
    """Service for optimizing sentiment analysis parameters"""
    
    def __init__(self, historical_service: HistoricalDataService):
        self.historical_service = historical_service
    
    def classify_regime_with_params(self, signal: HistoricalSignal, 
                                  params: CalibrationParams,
                                  zscore_stats: Dict) -> Tuple[str, float]:
        """Classify regime using specific parameters"""
        
        # Calculate Z-scores
        ndt_z = self.historical_service.calculate_zscore(signal.ndt, 'ndt', zscore_stats)
        gex_z = self.historical_service.calculate_zscore(signal.gex_atm, 'gex_atm', zscore_stats)
        charm_z = self.historical_service.calculate_zscore(signal.charm_sum, 'charm_sum', zscore_stats)
        
        # 1) Directional Bias (DB)
        DB = 0
        if signal.rr25 >= params.rr25_bullish_threshold:
            DB += 1
        elif signal.rr25 <= params.rr25_bearish_threshold:
            DB -= 1
        
        if ndt_z >= params.ndt_zscore_threshold:
            DB += 1
        elif ndt_z <= -params.ndt_zscore_threshold:
            DB -= 1
        
        if signal.fb_ratio >= params.fb_ratio_threshold:
            if signal.vanna_tilt > 0:
                DB += 1
            elif signal.vanna_tilt < 0:
                DB -= 1
        
        # 2) Trend Propensity (TP)
        TP = 0
        if gex_z <= params.gex_zscore_short_gamma:
            TP = 2  # Short gamma - trend prone
        elif gex_z >= params.gex_zscore_long_gamma:
            TP = 1  # Long gamma - mean reversion
        
        # 3) Pinning/Range (PR)
        PR = 0
        pin_threshold = params.pin_distance_expiry  # Assume expiry for simplicity
        if signal.pin_distance <= pin_threshold:
            PR += 1
        
        if (charm_z >= params.charm_zscore_threshold or 
            (signal.iv_front_atm - signal.rv_30m >= params.iv_rv_threshold and signal.gex_atm > 0)):
            PR += 1
        
        # Zero Gamma Level (simplified - assume spot is above/below based on GEX sign)
        spot_above_zg = signal.gex_atm < 0  # Negative GEX suggests spot above zero gamma
        
        # Final regime decision
        if DB >= 1 and TP >= 1 and PR <= 1 and spot_above_zg:
            regime = 'Bullish'
        elif DB <= -1 and TP >= 1 and PR <= 1 and not spot_above_zg:
            regime = 'Bearish'
        elif PR >= 2 or (TP == 0 and abs(DB) <= 1):
            regime = 'Sideways'
        else:
            regime = 'Balanced'
        
        # Confidence calculation
        confidence = self._sigmoid(
            params.db_weight * abs(DB) + 
            params.tp_weight * (1 if TP >= 1 else 0) + 
            params.pr_weight * (1 if regime == 'Sideways' else 0)
        )
        
        return regime, confidence
    
    def _sigmoid(self, x: float) -> float:
        """Sigmoid function for confidence calculation"""
        return 1 / (1 + np.exp(-x))
    
    def evaluate_parameters(self, params: CalibrationParams, 
                          test_data: List[HistoricalSignal],
                          zscore_stats: Dict) -> CalibrationResult:
        """Evaluate parameter set on test data"""
        
        predictions = []
        actual_regimes = []
        returns = []
        confidences = []
        
        for signal in test_data:
            if signal.next_6h_return is None:
                continue
                
            predicted_regime, confidence = self.classify_regime_with_params(
                signal, params, zscore_stats
            )
            
            predictions.append(predicted_regime)
            actual_regimes.append(signal.regime)
            returns.append(signal.next_6h_return)
            confidences.append(confidence)
        
        if not predictions:
            return CalibrationResult(
                params=params,
                accuracy=0.0,
                precision={}, recall={}, f1_score={},
                sharpe_ratio=0.0, total_return=0.0, max_drawdown=0.0,
                regime_performance={}
            )
        
        # Classification metrics
        from sklearn.metrics import accuracy_score, precision_recall_fscore_support
        
        accuracy = accuracy_score(actual_regimes, predictions)
        precision, recall, f1, _ = precision_recall_fscore_support(
            actual_regimes, predictions, average=None, zero_division=0
        )
        
        labels = ['Bullish', 'Bearish', 'Sideways', 'Balanced']
        precision_dict = dict(zip(labels, precision))
        recall_dict = dict(zip(labels, recall))
        f1_dict = dict(zip(labels, f1))
        
        # Trading performance metrics
        regime_returns = self._calculate_regime_returns(predictions, returns, confidences)
        sharpe_ratio = self._calculate_sharpe(regime_returns)
        total_return = np.sum(regime_returns)
        max_drawdown = self._calculate_max_drawdown(regime_returns)
        
        # Per-regime performance
        regime_performance = {}
        for regime in labels:
            regime_indices = [i for i, p in enumerate(predictions) if p == regime]
            if regime_indices:
                regime_rets = [returns[i] for i in regime_indices]
                regime_performance[regime] = {
                    'count': len(regime_indices),
                    'avg_return': np.mean(regime_rets),
                    'win_rate': len([r for r in regime_rets if r > 0]) / len(regime_rets),
                    'sharpe': np.mean(regime_rets) / np.std(regime_rets) if np.std(regime_rets) > 0 else 0
                }
        
        return CalibrationResult(
            params=params,
            accuracy=accuracy,
            precision=precision_dict,
            recall=recall_dict,
            f1_score=f1_dict,
            sharpe_ratio=sharpe_ratio,
            total_return=total_return,
            max_drawdown=max_drawdown,
            regime_performance=regime_performance
        )
    
    def _calculate_regime_returns(self, predictions: List[str], 
                                returns: List[float], 
                                confidences: List[float]) -> List[float]:
        """Calculate returns based on regime predictions"""
        regime_returns = []
        
        for pred, ret, conf in zip(predictions, returns, confidences):
            # Weight returns by confidence
            weighted_return = ret * conf
            
            # Apply regime-specific logic
            if pred == 'Bullish':
                regime_returns.append(weighted_return)
            elif pred == 'Bearish':
                regime_returns.append(-weighted_return)  # Short position
            elif pred == 'Sideways':
                # Range trading - profit from mean reversion
                regime_returns.append(abs(weighted_return) * 0.5)
            else:  # Balanced
                # No position
                regime_returns.append(0.0)
        
        return regime_returns
    
    def _calculate_sharpe(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if not returns or np.std(returns) == 0:
            return 0.0
        return np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not returns:
            return 0.0
        
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return float(np.min(drawdown))
    
    def optimize_parameters(self, lookback_days: int = 60) -> CalibrationResult:
        """Optimize parameters using historical data"""
        
        print(f"Starting parameter optimization with {lookback_days} days of data...")
        
        # Get historical data
        cutoff_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        
        # Load test data (simplified - in practice, load from database)
        test_data = self._load_test_data(cutoff_date)
        zscore_stats = self.historical_service.get_zscore_stats(lookback_days)
        
        if len(test_data) < 50:
            print("Insufficient historical data for optimization")
            return CalibrationResult(
                params=CalibrationParams(),
                accuracy=0.0, precision={}, recall={}, f1_score={},
                sharpe_ratio=0.0, total_return=0.0, max_drawdown=0.0,
                regime_performance={}
            )
        
        # Define parameter bounds for optimization
        bounds = [
            (0.5, 2.5),    # rr25_bullish_threshold
            (-2.5, -0.5),  # rr25_bearish_threshold
            (0.3, 1.0),    # ndt_zscore_threshold
            (-2.0, -0.5),  # gex_zscore_short_gamma
            (0.5, 2.0),    # gex_zscore_long_gamma
            (0.1, 0.5),    # pin_distance_expiry
            (0.2, 0.7),    # pin_distance_normal
            (0.3, 1.0),    # charm_zscore_threshold
            (2.0, 5.0),    # iv_rv_threshold
            (1.05, 1.3),   # fb_ratio_threshold
            (0.4, 0.8),    # db_weight
            (0.6, 1.0),    # tp_weight
            (0.4, 0.8),    # pr_weight
        ]
        
        # Objective function to maximize
        def objective(x):
            params = CalibrationParams(
                rr25_bullish_threshold=x[0],
                rr25_bearish_threshold=x[1],
                ndt_zscore_threshold=x[2],
                gex_zscore_short_gamma=x[3],
                gex_zscore_long_gamma=x[4],
                pin_distance_expiry=x[5],
                pin_distance_normal=x[6],
                charm_zscore_threshold=x[7],
                iv_rv_threshold=x[8],
                fb_ratio_threshold=x[9],
                db_weight=x[10],
                tp_weight=x[11],
                pr_weight=x[12]
            )
            
            result = self.evaluate_parameters(params, test_data, zscore_stats)
            
            # Optimize for combination of accuracy and Sharpe ratio
            score = result.accuracy * 0.4 + (result.sharpe_ratio / 2.0) * 0.6
            return -score  # Minimize negative score
        
        # Initial guess (current default parameters)
        x0 = [1.0, -1.0, 0.5, -1.0, 1.0, 0.3, 0.45, 0.5, 3.0, 1.15, 0.6, 0.8, 0.6]
        
        # Optimize
        print("Running optimization...")
        result = minimize(objective, x0, bounds=bounds, method='L-BFGS-B')
        
        # Create optimized parameters
        optimized_params = CalibrationParams(
            rr25_bullish_threshold=result.x[0],
            rr25_bearish_threshold=result.x[1],
            ndt_zscore_threshold=result.x[2],
            gex_zscore_short_gamma=result.x[3],
            gex_zscore_long_gamma=result.x[4],
            pin_distance_expiry=result.x[5],
            pin_distance_normal=result.x[6],
            charm_zscore_threshold=result.x[7],
            iv_rv_threshold=result.x[8],
            fb_ratio_threshold=result.x[9],
            db_weight=result.x[10],
            tp_weight=result.x[11],
            pr_weight=result.x[12]
        )
        
        # Evaluate final result
        final_result = self.evaluate_parameters(optimized_params, test_data, zscore_stats)
        
        print(f"Optimization complete!")
        print(f"Accuracy: {final_result.accuracy:.3f}")
        print(f"Sharpe Ratio: {final_result.sharpe_ratio:.3f}")
        print(f"Total Return: {final_result.total_return:.3f}")
        
        return final_result
    
    def _load_test_data(self, cutoff_date: str) -> List[HistoricalSignal]:
        """Load test data from database (simplified implementation)"""
        # In practice, this would load from the historical database
        # For now, return mock data
        test_data = []
        
        for i in range(100):  # Mock 100 data points
            signal = HistoricalSignal(
                date=cutoff_date,
                timestamp=f"{cutoff_date}T09:45:00+05:30",
                spot=24500 + np.random.normal(0, 200),
                ndt=np.random.normal(0, 1000),
                gex_atm=np.random.normal(0, 50000),
                charm_sum=np.random.normal(0, 0.1),
                rr25=np.random.normal(0, 2),
                vanna_tilt=np.random.normal(0, 10000),
                fb_ratio=np.random.uniform(0.95, 1.25),
                pin_distance=abs(np.random.normal(0.5, 0.3)),
                iv_front_atm=np.random.uniform(12, 25),
                rv_30m=np.random.uniform(10, 30),
                regime=np.random.choice(['Bullish', 'Bearish', 'Sideways', 'Balanced']),
                next_6h_return=np.random.normal(0, 0.02)
            )
            test_data.append(signal)
        
        return test_data
    
    def save_calibration_result(self, result: CalibrationResult, 
                              filepath: str = "data/calibration_result.json"):
        """Save calibration result to file"""
        result_dict = {
            'timestamp': datetime.now().isoformat(),
            'params': {
                'rr25_bullish_threshold': result.params.rr25_bullish_threshold,
                'rr25_bearish_threshold': result.params.rr25_bearish_threshold,
                'ndt_zscore_threshold': result.params.ndt_zscore_threshold,
                'gex_zscore_short_gamma': result.params.gex_zscore_short_gamma,
                'gex_zscore_long_gamma': result.params.gex_zscore_long_gamma,
                'pin_distance_expiry': result.params.pin_distance_expiry,
                'pin_distance_normal': result.params.pin_distance_normal,
                'charm_zscore_threshold': result.params.charm_zscore_threshold,
                'iv_rv_threshold': result.params.iv_rv_threshold,
                'fb_ratio_threshold': result.params.fb_ratio_threshold,
                'db_weight': result.params.db_weight,
                'tp_weight': result.params.tp_weight,
                'pr_weight': result.params.pr_weight,
            },
            'performance': {
                'accuracy': result.accuracy,
                'sharpe_ratio': result.sharpe_ratio,
                'total_return': result.total_return,
                'max_drawdown': result.max_drawdown,
                'precision': result.precision,
                'recall': result.recall,
                'f1_score': result.f1_score,
                'regime_performance': result.regime_performance
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        print(f"Calibration result saved to {filepath}")

# Singleton instance
calibration_service = CalibrationService(
    HistoricalDataService("data/sentiment_history.db")
)
