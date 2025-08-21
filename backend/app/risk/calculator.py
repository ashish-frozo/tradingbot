"""
Risk Calculator Module

This module provides margin calculation and dynamic lot sizing functionality.
Key features:
- Dynamic lot sizing based on 40% margin utilization target
- Margin requirement calculations for options strategies
- Position size validation and limits
- Portfolio-level risk calculations
"""

import asyncio
import math
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from loguru import logger

from app.broker.enums import TransactionType, ProductType
from app.core.config import get_settings


class RiskLevel(Enum):
    """Risk levels for position sizing"""
    CONSERVATIVE = "conservative"  # 20% margin utilization
    MODERATE = "moderate"         # 40% margin utilization (default)
    AGGRESSIVE = "aggressive"     # 60% margin utilization


@dataclass
class MarginRequirement:
    """Margin requirement details for a position"""
    span_margin: float
    exposure_margin: float
    premium_margin: float
    total_margin: float
    currency: str = "INR"


@dataclass
class PositionSizing:
    """Position sizing calculation result"""
    recommended_lots: int
    max_lots_by_margin: int
    max_lots_by_limits: int
    total_margin_required: float
    margin_utilization_pct: float
    risk_level: RiskLevel
    warnings: List[str]


@dataclass
class PortfolioRisk:
    """Portfolio-level risk metrics"""
    total_margin_used: float
    total_margin_available: float
    margin_utilization_pct: float
    daily_pnl: float
    unrealized_pnl: float
    total_positions: int
    max_position_value: float
    concentration_risk_pct: float


class RiskCalculator:
    """
    Risk calculator for dynamic lot sizing and margin calculations
    
    Features:
    - Dynamic lot sizing based on margin utilization targets
    - Margin requirement calculations for different option strategies
    - Portfolio-level risk monitoring
    - Position limits validation
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logger.bind(module="risk_calculator")
        
        # Risk parameters (can be made configurable)
        self.default_margin_utilization = 0.40  # 40% target
        self.max_margin_utilization = 0.80      # 80% hard limit
        self.min_lots_per_signal = 2            # Minimum position size
        self.max_lots_per_signal = 10           # Per PRD: 10 lots/signal
        self.max_total_lots = 50                # Per PRD: 50 lots total/strategy
        
        # Indian options typical margin requirements (approximate)
        self.margin_multipliers = {
            "nifty": {
                "span_pct": 0.12,      # 12% of notional
                "exposure_pct": 0.05,   # 5% of notional  
                "premium_pct": 1.0      # 100% of premium for shorts
            },
            "banknifty": {
                "span_pct": 0.15,      # 15% of notional
                "exposure_pct": 0.06,   # 6% of notional
                "premium_pct": 1.0      # 100% of premium for shorts
            }
        }
    
    async def calculate_margin_requirement(
        self,
        symbol: str,
        strike: float,
        option_type: str,  # "CE" or "PE"
        transaction_type: TransactionType,
        lot_size: int,
        lots: int,
        ltp: float,
        underlying_price: float
    ) -> MarginRequirement:
        """
        Calculate margin requirement for an options position
        
        Args:
            symbol: Underlying symbol (NIFTY, BANKNIFTY)
            strike: Strike price
            option_type: "CE" or "PE" 
            transaction_type: BUY or SELL
            lot_size: Lot size (75 for NIFTY, 15 for BANKNIFTY)
            lots: Number of lots
            ltp: Last traded price of option
            underlying_price: Current price of underlying
            
        Returns:
            MarginRequirement with detailed breakdown
        """
        
        try:
            # Normalize symbol for lookup
            symbol_key = symbol.lower().replace("_", "")
            if "nifty" in symbol_key and "bank" not in symbol_key:
                multipliers = self.margin_multipliers["nifty"]
            elif "bank" in symbol_key and "nifty" in symbol_key:
                multipliers = self.margin_multipliers["banknifty"]
            else:
                # Default to NIFTY margins for unknown symbols
                multipliers = self.margin_multipliers["nifty"]
                self.logger.warning(f"Unknown symbol {symbol}, using NIFTY margins")
            
            # Calculate notional value
            notional_value = underlying_price * lot_size * lots
            premium_value = ltp * lot_size * lots
            
            if transaction_type == TransactionType.BUY:
                # For long options, only premium is required
                span_margin = 0
                exposure_margin = 0
                premium_margin = premium_value
            else:
                # For short options, calculate SPAN + Exposure + Premium
                span_margin = notional_value * multipliers["span_pct"]
                exposure_margin = notional_value * multipliers["exposure_pct"]
                premium_margin = premium_value * multipliers["premium_pct"]
            
            total_margin = span_margin + exposure_margin + premium_margin
            
            margin_req = MarginRequirement(
                span_margin=round(span_margin, 2),
                exposure_margin=round(exposure_margin, 2),
                premium_margin=round(premium_margin, 2),
                total_margin=round(total_margin, 2)
            )
            
            self.logger.debug(
                f"Margin calculated for {symbol} {strike}{option_type} "
                f"{transaction_type.value} {lots}x: ₹{total_margin:,.2f}",
                extra={
                    "symbol": symbol,
                    "strike": strike,
                    "option_type": option_type,
                    "lots": lots,
                    "margin_requirement": total_margin
                }
            )
            
            return margin_req
            
        except Exception as e:
            self.logger.error(f"Error calculating margin requirement: {e}")
            # Return conservative estimate
            conservative_margin = underlying_price * lot_size * lots * 0.20
            return MarginRequirement(
                span_margin=conservative_margin * 0.6,
                exposure_margin=conservative_margin * 0.3,
                premium_margin=conservative_margin * 0.1,
                total_margin=conservative_margin
            )
    
    async def calculate_dynamic_lot_sizing(
        self,
        available_margin: float,
        margin_per_lot: float,
        current_positions: int = 0,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        strategy_name: str = "default"
    ) -> PositionSizing:
        """
        Calculate optimal lot sizing based on margin utilization
        
        Args:
            available_margin: Total available margin balance
            margin_per_lot: Margin required per lot for the position
            current_positions: Current number of lots in portfolio
            risk_level: Risk level for margin utilization
            strategy_name: Name of strategy for logging
            
        Returns:
            PositionSizing with recommended lots and risk metrics
        """
        
        try:
            warnings = []
            
            # Set target margin utilization based on risk level
            target_utilization = {
                RiskLevel.CONSERVATIVE: 0.20,
                RiskLevel.MODERATE: 0.40,
                RiskLevel.AGGRESSIVE: 0.60
            }.get(risk_level, 0.40)
            
            # Calculate target margin to use
            target_margin_amount = available_margin * target_utilization
            
            # Calculate lots that can be afforded
            if margin_per_lot <= 0:
                warnings.append("Invalid margin per lot")
                return PositionSizing(
                    recommended_lots=0,
                    max_lots_by_margin=0,
                    max_lots_by_limits=0,
                    total_margin_required=0,
                    margin_utilization_pct=0,
                    risk_level=risk_level,
                    warnings=warnings
                )
            
            max_lots_by_margin = int(target_margin_amount / margin_per_lot)
            
            # Apply position limits
            remaining_capacity = self.max_total_lots - current_positions
            max_lots_by_limits = min(self.max_lots_per_signal, remaining_capacity)
            
            # Take minimum of margin and limit constraints
            recommended_lots = min(max_lots_by_margin, max_lots_by_limits)
            
            # Apply minimum lot size
            if recommended_lots < self.min_lots_per_signal:
                if max_lots_by_margin >= self.min_lots_per_signal:
                    warnings.append(f"Position limit prevents minimum {self.min_lots_per_signal} lots")
                else:
                    warnings.append(f"Insufficient margin for minimum {self.min_lots_per_signal} lots")
                recommended_lots = 0
            
            # Calculate final metrics
            total_margin_required = recommended_lots * margin_per_lot
            final_utilization = (total_margin_required / available_margin) * 100 if available_margin > 0 else 0
            
            # Add warnings for edge cases
            if final_utilization > 70:
                warnings.append(f"High margin utilization: {final_utilization:.1f}%")
            
            if recommended_lots == 0 and available_margin > margin_per_lot * self.min_lots_per_signal:
                warnings.append("Position limits prevent trading despite sufficient margin")
            
            sizing = PositionSizing(
                recommended_lots=recommended_lots,
                max_lots_by_margin=max_lots_by_margin,
                max_lots_by_limits=max_lots_by_limits,
                total_margin_required=total_margin_required,
                margin_utilization_pct=final_utilization,
                risk_level=risk_level,
                warnings=warnings
            )
            
            self.logger.info(
                f"Dynamic lot sizing for {strategy_name}: {recommended_lots} lots "
                f"(margin: {final_utilization:.1f}%, ₹{total_margin_required:,.0f})",
                extra={
                    "strategy": strategy_name,
                    "recommended_lots": recommended_lots,
                    "margin_utilization": final_utilization,
                    "margin_required": total_margin_required,
                    "available_margin": available_margin,
                    "risk_level": risk_level.value
                }
            )
            
            return sizing
            
        except Exception as e:
            self.logger.error(f"Error in dynamic lot sizing calculation: {e}")
            return PositionSizing(
                recommended_lots=0,
                max_lots_by_margin=0,
                max_lots_by_limits=0,
                total_margin_required=0,
                margin_utilization_pct=0,
                risk_level=risk_level,
                warnings=[f"Calculation error: {str(e)}"]
            )
    
    async def calculate_portfolio_risk(
        self,
        positions: List[Dict],
        available_margin: float,
        daily_pnl: float = 0
    ) -> PortfolioRisk:
        """
        Calculate portfolio-level risk metrics
        
        Args:
            positions: List of current positions with margin and PnL data
            available_margin: Total available margin
            daily_pnl: Today's realized P&L
            
        Returns:
            PortfolioRisk with comprehensive risk metrics
        """
        
        try:
            total_margin_used = sum(pos.get("margin_used", 0) for pos in positions)
            unrealized_pnl = sum(pos.get("unrealized_pnl", 0) for pos in positions)
            total_positions = sum(pos.get("lots", 0) for pos in positions)
            
            # Calculate largest position value
            max_position_value = max(
                (abs(pos.get("market_value", 0)) for pos in positions),
                default=0
            )
            
            # Calculate margin utilization
            total_margin_available = available_margin + total_margin_used
            margin_utilization_pct = (total_margin_used / total_margin_available * 100) if total_margin_available > 0 else 0
            
            # Calculate concentration risk (largest position as % of portfolio)
            total_portfolio_value = sum(abs(pos.get("market_value", 0)) for pos in positions)
            concentration_risk_pct = (max_position_value / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
            
            portfolio_risk = PortfolioRisk(
                total_margin_used=total_margin_used,
                total_margin_available=total_margin_available,
                margin_utilization_pct=margin_utilization_pct,
                daily_pnl=daily_pnl,
                unrealized_pnl=unrealized_pnl,
                total_positions=total_positions,
                max_position_value=max_position_value,
                concentration_risk_pct=concentration_risk_pct
            )
            
            self.logger.debug(
                f"Portfolio risk: {margin_utilization_pct:.1f}% margin, "
                f"₹{daily_pnl:,.0f} daily P&L, {total_positions} lots",
                extra={
                    "margin_utilization": margin_utilization_pct,
                    "daily_pnl": daily_pnl,
                    "total_positions": total_positions,
                    "concentration_risk": concentration_risk_pct
                }
            )
            
            return portfolio_risk
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio risk: {e}")
            return PortfolioRisk(
                total_margin_used=0,
                total_margin_available=available_margin,
                margin_utilization_pct=0,
                daily_pnl=daily_pnl,
                unrealized_pnl=0,
                total_positions=0,
                max_position_value=0,
                concentration_risk_pct=0
            )
    
    def validate_position_limits(
        self,
        new_lots: int,
        current_total_lots: int,
        strategy_name: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate position against limits
        
        Args:
            new_lots: New lots to add
            current_total_lots: Current total lots in portfolio
            strategy_name: Strategy name for logging
            
        Returns:
            Tuple of (is_valid, warnings)
        """
        
        warnings = []
        is_valid = True
        
        # Check per-signal limit
        if new_lots > self.max_lots_per_signal:
            warnings.append(f"Exceeds max lots per signal: {new_lots} > {self.max_lots_per_signal}")
            is_valid = False
        
        # Check total portfolio limit
        if current_total_lots + new_lots > self.max_total_lots:
            warnings.append(f"Exceeds total lots limit: {current_total_lots + new_lots} > {self.max_total_lots}")
            is_valid = False
        
        # Check minimum size
        if new_lots < self.min_lots_per_signal and new_lots > 0:
            warnings.append(f"Below minimum lots per signal: {new_lots} < {self.min_lots_per_signal}")
            is_valid = False
        
        if not is_valid:
            self.logger.warning(
                f"Position limit validation failed for {strategy_name}: {'; '.join(warnings)}",
                extra={"strategy": strategy_name, "new_lots": new_lots, "current_lots": current_total_lots}
            )
        
        return is_valid, warnings


# Global instance
risk_calculator = RiskCalculator() 