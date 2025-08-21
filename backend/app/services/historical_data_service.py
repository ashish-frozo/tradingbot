"""
Historical Data Service for Market Sentiment Analysis
Stores and manages historical option chain data for Z-score calculations
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import numpy as np
from pathlib import Path

@dataclass
class HistoricalSignal:
    """Historical signal data for Z-score calculation"""
    date: str
    timestamp: str
    spot: float
    ndt: float  # Net Delta Tilt
    gex_atm: float  # Gamma Exposure ATM
    charm_sum: float  # Charm sum around ATM
    rr25: float  # 25Delta Risk Reversal
    vanna_tilt: float  # Vanna Tilt
    fb_ratio: float  # Front/Back IV ratio
    pin_distance: float  # Pin distance percentage
    iv_front_atm: float  # Front month ATM IV
    rv_30m: float  # 30min Realized Volatility
    regime: str  # Actual regime (for validation)
    next_6h_return: Optional[float] = None  # For performance validation

@dataclass
class ZScoreStats:
    """Z-score statistics for normalization"""
    mean: float
    std: float
    count: int
    last_updated: str

class HistoricalDataService:
    """Service to manage historical data for sentiment analysis"""
    
    def __init__(self, db_path: str = "data/sentiment_history.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS historical_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    spot REAL NOT NULL,
                    ndt REAL NOT NULL,
                    gex_atm REAL NOT NULL,
                    charm_sum REAL NOT NULL,
                    rr25 REAL NOT NULL,
                    vanna_tilt REAL NOT NULL,
                    fb_ratio REAL NOT NULL,
                    pin_distance REAL NOT NULL,
                    iv_front_atm REAL NOT NULL,
                    rv_30m REAL NOT NULL,
                    regime TEXT NOT NULL,
                    next_6h_return REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS zscore_stats (
                    metric TEXT PRIMARY KEY,
                    mean REAL NOT NULL,
                    std REAL NOT NULL,
                    count INTEGER NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_date_timestamp 
                ON historical_signals(date, timestamp)
            """)
    
    def store_signal(self, signal: HistoricalSignal) -> bool:
        """Store a historical signal in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO historical_signals 
                    (date, timestamp, spot, ndt, gex_atm, charm_sum, rr25, 
                     vanna_tilt, fb_ratio, pin_distance, iv_front_atm, rv_30m, 
                     regime, next_6h_return)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal.date, signal.timestamp, signal.spot, signal.ndt,
                    signal.gex_atm, signal.charm_sum, signal.rr25, signal.vanna_tilt,
                    signal.fb_ratio, signal.pin_distance, signal.iv_front_atm,
                    signal.rv_30m, signal.regime, signal.next_6h_return
                ))
            return True
        except Exception as e:
            print(f"Error storing signal: {e}")
            return False
    
    def get_zscore_stats(self, lookback_days: int = 60) -> Dict[str, ZScoreStats]:
        """Get Z-score statistics for the last N days"""
        cutoff_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT ndt, gex_atm, charm_sum, rr25, vanna_tilt, pin_distance
                FROM historical_signals 
                WHERE date >= ?
                ORDER BY date DESC, timestamp DESC
            """, (cutoff_date,))
            
            data = cursor.fetchall()
        
        if not data:
            # Return default stats if no historical data
            return self._get_default_stats()
        
        # Convert to numpy array for calculations
        data_array = np.array(data)
        metrics = ['ndt', 'gex_atm', 'charm_sum', 'rr25', 'vanna_tilt', 'pin_distance']
        
        stats = {}
        for i, metric in enumerate(metrics):
            values = data_array[:, i]
            stats[metric] = ZScoreStats(
                mean=float(np.mean(values)),
                std=float(np.std(values)),
                count=len(values),
                last_updated=datetime.now().isoformat()
            )
        
        # Update cached stats in database
        self._update_cached_stats(stats)
        
        return stats
    
    def _get_default_stats(self) -> Dict[str, ZScoreStats]:
        """Return default Z-score stats when no historical data exists"""
        return {
            'ndt': ZScoreStats(0.0, 1000.0, 0, datetime.now().isoformat()),
            'gex_atm': ZScoreStats(0.0, 50000.0, 0, datetime.now().isoformat()),
            'charm_sum': ZScoreStats(0.0, 0.1, 0, datetime.now().isoformat()),
            'rr25': ZScoreStats(0.0, 2.0, 0, datetime.now().isoformat()),
            'vanna_tilt': ZScoreStats(0.0, 10000.0, 0, datetime.now().isoformat()),
            'pin_distance': ZScoreStats(0.5, 0.3, 0, datetime.now().isoformat())
        }
    
    def _update_cached_stats(self, stats: Dict[str, ZScoreStats]):
        """Update cached Z-score stats in database"""
        with sqlite3.connect(self.db_path) as conn:
            for metric, stat in stats.items():
                conn.execute("""
                    INSERT OR REPLACE INTO zscore_stats 
                    (metric, mean, std, count, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (metric, stat.mean, stat.std, stat.count, stat.last_updated))
    
    def get_cached_stats(self) -> Dict[str, ZScoreStats]:
        """Get cached Z-score stats from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT metric, mean, std, count, last_updated
                FROM zscore_stats
            """)
            
            rows = cursor.fetchall()
        
        if not rows:
            return self._get_default_stats()
        
        stats = {}
        for row in rows:
            metric, mean, std, count, last_updated = row
            stats[metric] = ZScoreStats(mean, std, count, last_updated)
        
        return stats
    
    def calculate_zscore(self, value: float, metric: str, stats: Dict[str, ZScoreStats]) -> float:
        """Calculate Z-score for a given value and metric"""
        if metric not in stats:
            return 0.0
        
        stat = stats[metric]
        if stat.std == 0:
            return 0.0
        
        return (value - stat.mean) / stat.std
    
    def get_historical_performance(self, regime: str, days: int = 30) -> Dict[str, float]:
        """Get historical performance metrics for a regime"""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT next_6h_return, regime
                FROM historical_signals 
                WHERE date >= ? AND next_6h_return IS NOT NULL
            """, (cutoff_date,))
            
            data = cursor.fetchall()
        
        if not data:
            return {'accuracy': 0.0, 'avg_return': 0.0, 'sharpe': 0.0, 'count': 0}
        
        # Filter for specific regime
        regime_returns = [row[0] for row in data if row[1] == regime]
        all_returns = [row[0] for row in data]
        
        if not regime_returns:
            return {'accuracy': 0.0, 'avg_return': 0.0, 'sharpe': 0.0, 'count': 0}
        
        # Calculate performance metrics
        avg_return = np.mean(regime_returns)
        accuracy = len([r for r in regime_returns if r > 0]) / len(regime_returns)
        sharpe = avg_return / np.std(regime_returns) if np.std(regime_returns) > 0 else 0.0
        
        return {
            'accuracy': accuracy,
            'avg_return': avg_return,
            'sharpe': sharpe,
            'count': len(regime_returns)
        }
    
    def generate_mock_historical_data(self, days: int = 60):
        """Generate mock historical data for testing"""
        print(f"Generating {days} days of mock historical data...")
        
        base_date = datetime.now() - timedelta(days=days)
        
        for day in range(days):
            current_date = base_date + timedelta(days=day)
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Generate 4 signals per day (09:15, 09:30, 09:45, 15:30)
            times = ['09:15:00', '09:30:00', '09:45:00', '15:30:00']
            
            for time_str in times:
                # Mock signal generation with realistic distributions
                signal = HistoricalSignal(
                    date=date_str,
                    timestamp=f"{date_str}T{time_str}+05:30",
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
                
                self.store_signal(signal)
        
        print(f"Generated mock data for {days} days")
    
    def cleanup_old_data(self, keep_days: int = 90):
        """Clean up data older than specified days"""
        cutoff_date = (datetime.now() - timedelta(days=keep_days)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM historical_signals WHERE date < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
        
        print(f"Cleaned up {deleted_count} old records")
        return deleted_count

# Singleton instance
historical_service = HistoricalDataService()
