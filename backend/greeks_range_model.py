#!/usr/bin/env python3
"""
Greeks Range Model (GRM) - Production-ready support/resistance calculation
Based on option chain Greeks: gamma walls, vanna shifts, charm compression
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, time
import logging

class GreeksRangeModel:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Historical data for z-scoring (60 days)
        self.gex_history = []
        self.charm_history = []
        
    def calculate_dealer_gex(self, option_chain: pd.DataFrame) -> Dict[float, float]:
        """
        Calculate Dealer Gamma Exposure (GEX) for each strike
        Dealer GEX = -(Customer OI) * Gamma (dealers are short when customers are long)
        """
        gex = {}
        
        for _, row in option_chain.iterrows():
            strike = float(row['strike'])
            call_oi = float(row.get('call_oi', 0))
            put_oi = float(row.get('put_oi', 0))
            gamma = float(row.get('gamma', 0))
            
            # Dealer GEX (negative of customer GEX)
            gex[strike] = -(call_oi + put_oi) * gamma
            
        return gex
    
    def find_zero_gamma_level(self, gex: Dict[float, float]) -> float:
        """
        Find Zero-Gamma level where cumulative GEX crosses zero
        """
        strikes = sorted(gex.keys())
        cumulative_gex = 0
        
        for i, strike in enumerate(strikes):
            prev_cumulative = cumulative_gex
            cumulative_gex += gex[strike]
            
            # Check for zero crossing
            if prev_cumulative <= 0 <= cumulative_gex or cumulative_gex <= 0 <= prev_cumulative:
                if i == 0:
                    return strike
                
                # Linear interpolation between strikes
                prev_strike = strikes[i-1]
                if cumulative_gex == prev_cumulative:
                    return strike
                
                ratio = abs(prev_cumulative) / abs(cumulative_gex - prev_cumulative)
                return prev_strike + ratio * (strike - prev_strike)
        
        # If no crossing found, return middle strike
        return strikes[len(strikes) // 2] if strikes else 0
    
    def find_gamma_walls(self, gex: Dict[float, float], zero_gamma: float, spot_price: float) -> Tuple[float, float]:
        """
        Find gamma walls (first local extrema of |GEX| above and below ZG)
        Within ±3% of spot price
        """
        strikes = sorted(gex.keys())
        spot_range = spot_price * 0.03  # ±3%
        
        # Filter strikes within range
        valid_strikes = [s for s in strikes if abs(s - spot_price) <= spot_range]
        
        if not valid_strikes:
            return spot_price * 0.98, spot_price * 1.02
        
        # Find strikes above and below zero gamma
        above_zg = [s for s in valid_strikes if s > zero_gamma]
        below_zg = [s for s in valid_strikes if s < zero_gamma]
        
        # Find first local maximum above ZG
        upper_wall = spot_price * 1.02  # default
        if above_zg:
            max_gex = 0
            for strike in above_zg:
                if abs(gex[strike]) > max_gex:
                    max_gex = abs(gex[strike])
                    upper_wall = strike
        
        # Find first local maximum below ZG
        lower_wall = spot_price * 0.98  # default
        if below_zg:
            max_gex = 0
            for strike in reversed(below_zg):
                if abs(gex[strike]) > max_gex:
                    max_gex = abs(gex[strike])
                    lower_wall = strike
        
        return lower_wall, upper_wall
    
    def calculate_gex_regime(self, gex: Dict[float, float], spot_price: float) -> str:
        """
        Determine GEX regime around ATM (±2% window)
        """
        window = spot_price * 0.02
        atm_gex = sum(gex_val for strike, gex_val in gex.items() 
                     if abs(strike - spot_price) <= window)
        
        # Z-score against historical data
        if len(self.gex_history) > 10:
            gex_mean = np.mean(self.gex_history)
            gex_std = np.std(self.gex_history)
            z_score = (atm_gex - gex_mean) / gex_std if gex_std > 0 else 0
        else:
            z_score = 0
        
        self.gex_history.append(atm_gex)
        if len(self.gex_history) > 60:  # Keep 60 days
            self.gex_history.pop(0)
        
        if z_score >= 1.0:
            return "long_gamma"
        elif z_score <= -1.0:
            return "short_gamma"
        else:
            return "neutral"
    
    def calculate_vanna_shift(self, option_chain: pd.DataFrame, spot_price: float, 
                            front_iv: float, back_iv: float) -> float:
        """
        Calculate vanna-based spot shift
        """
        # Expected IV change (front > back suggests compression)
        alpha = 0.5  # IV reversion fraction
        delta_sigma = alpha * max(0.0, front_iv - back_iv)
        
        if delta_sigma == 0:
            return 0
        
        # Sum vanna and gamma in ±1.5% band around ATM
        window = spot_price * 0.015
        vanna_net = 0
        gamma_net = 0
        
        for _, row in option_chain.iterrows():
            strike = float(row['strike'])
            if abs(strike - spot_price) <= window:
                vanna = float(row.get('vanna', 0))
                gamma = float(row.get('gamma', 0))
                oi = float(row.get('call_oi', 0)) + float(row.get('put_oi', 0))
                
                vanna_net += vanna * oi
                gamma_net += abs(gamma) * oi
        
        if gamma_net == 0:
            return 0
        
        # Vanna shift calculation
        return -(vanna_net * delta_sigma) / gamma_net
    
    def calculate_charm_modifier(self, option_chain: pd.DataFrame, spot_price: float) -> float:
        """
        Calculate charm-based range modifier
        """
        # Sum charm in ±1.5% band around ATM
        window = spot_price * 0.015
        charm_net = 0
        
        for _, row in option_chain.iterrows():
            strike = float(row['strike'])
            if abs(strike - spot_price) <= window:
                charm = float(row.get('charm', 0))
                oi = float(row.get('call_oi', 0)) + float(row.get('put_oi', 0))
                charm_net += charm * oi
        
        # Z-score against historical data
        if len(self.charm_history) > 10:
            charm_mean = np.mean(self.charm_history)
            charm_std = np.std(self.charm_history)
            z_score = (charm_net - charm_mean) / charm_std if charm_std > 0 else 0
        else:
            z_score = 0
        
        self.charm_history.append(charm_net)
        if len(self.charm_history) > 60:  # Keep 60 days
            self.charm_history.pop(0)
        
        # Charm modifier based on z-score
        if z_score >= 0.5:
            return 0.8  # Positive charm -> narrower range
        elif z_score <= -0.5:
            return 1.2  # Negative charm -> wider range
        else:
            return 1.0  # Neutral
    
    def calculate_expected_move(self, option_chain: pd.DataFrame, spot_price: float, 
                              hours_to_close: float = 6.5) -> float:
        """
        Calculate expected move using straddle method
        """
        # Find ATM options
        atm_strike = min(option_chain['strike'], key=lambda x: abs(x - spot_price))
        atm_row = option_chain[option_chain['strike'] == atm_strike].iloc[0]
        
        call_price = float(atm_row.get('call_price', 0))
        put_price = float(atm_row.get('put_price', 0))
        
        # Expected move as percentage
        em_pct = (call_price + put_price) / spot_price
        
        # Scale by time (for intraday)
        time_factor = np.sqrt(hours_to_close / (252 * 6.5))
        
        return em_pct * time_factor * spot_price
    
    def greeks_range_model(self, option_chain: pd.DataFrame, spot_price: float, 
                          front_iv: float, back_iv: float, 
                          hours_to_close: float = 6.5) -> Dict:
        """
        Main GRM calculation function
        """
        try:
            # Step 1: Calculate Dealer GEX and find gamma map
            gex = self.calculate_dealer_gex(option_chain)
            zero_gamma = self.find_zero_gamma_level(gex)
            wall_lo, wall_hi = self.find_gamma_walls(gex, zero_gamma, spot_price)
            gex_regime = self.calculate_gex_regime(gex, spot_price)
            
            # Step 2: Calculate vanna shift
            vanna_shift = self.calculate_vanna_shift(option_chain, spot_price, front_iv, back_iv)
            vanna_center = np.clip(spot_price + vanna_shift, wall_lo, wall_hi)
            
            # Step 3: Calculate charm modifier
            charm_modifier = self.calculate_charm_modifier(option_chain, spot_price)
            
            # Step 4: Calculate expected move
            expected_move = self.calculate_expected_move(option_chain, spot_price, hours_to_close)
            band_value = charm_modifier * expected_move
            
            # Step 5: Build final range
            # Blend center based on regime
            if gex_regime == "short_gamma":
                w = 0.7
            else:
                w = 0.5
            
            center = w * vanna_center + (1 - w) * zero_gamma
            
            # Calculate support and resistance, clipped to gamma walls
            resistance = min(center + band_value, wall_hi)
            support = max(center - band_value, wall_lo)
            
            # Find secondary walls for short gamma regime
            secondary_support = None
            secondary_resistance = None
            
            if gex_regime == "short_gamma":
                # Find next gamma walls beyond primary walls
                strikes = sorted(gex.keys())
                for strike in strikes:
                    if strike < wall_lo and abs(gex[strike]) > abs(gex.get(wall_lo, 0)) * 0.5:
                        secondary_support = strike
                        break
                
                for strike in reversed(strikes):
                    if strike > wall_hi and abs(gex[strike]) > abs(gex.get(wall_hi, 0)) * 0.5:
                        secondary_resistance = strike
                        break
            
            return {
                "center": round(center, 2),
                "support": round(support, 2),
                "resistance": round(resistance, 2),
                "support2": round(secondary_support, 2) if secondary_support else None,
                "resistance2": round(secondary_resistance, 2) if secondary_resistance else None,
                "zero_gamma": round(zero_gamma, 2),
                "gamma_wall_low": round(wall_lo, 2),
                "gamma_wall_high": round(wall_hi, 2),
                "gex_regime": gex_regime,
                "expected_move": round(expected_move, 2),
                "charm_modifier": round(charm_modifier, 2),
                "vanna_shift": round(vanna_shift, 2),
                "timestamp": datetime.now().isoformat(),
                "trading_strategy": self._get_trading_strategy(gex_regime, center, support, resistance)
            }
            
        except Exception as e:
            self.logger.error(f"Error in GRM calculation: {e}")
            return {
                "error": str(e),
                "center": spot_price,
                "support": spot_price * 0.99,
                "resistance": spot_price * 1.01,
                "gex_regime": "unknown"
            }
    
    def _get_trading_strategy(self, regime: str, center: float, support: float, resistance: float) -> Dict:
        """
        Generate trading strategy based on GEX regime
        """
        if regime == "long_gamma":
            return {
                "type": "Range-bound",
                "description": "Expect mean reversion between support and resistance",
                "strategy": "Favor premium sells around edges, fade moves into walls",
                "key_level": center,
                "bias": "neutral"
            }
        elif regime == "short_gamma":
            return {
                "type": "Trend-prone", 
                "description": "Expect tests of walls, breakouts possible",
                "strategy": "Use S/R as breakout lines, prefer directional plays",
                "key_level": None,
                "bias": "directional"
            }
        else:
            return {
                "type": "Neutral",
                "description": "Mixed signals, trade with caution",
                "strategy": "Wait for clearer regime signals",
                "key_level": center,
                "bias": "neutral"
            }

# Global GRM instance
grm = GreeksRangeModel()
