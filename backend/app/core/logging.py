"""
Centralized Logging Configuration
Structured JSON logging for production and development
"""

import sys
import json
from datetime import datetime
from typing import Dict, Any
from loguru import logger
from .config import settings


class StructuredFormatter:
    """Custom formatter for structured JSON logging"""
    
    def format(self, record: Dict[str, Any]) -> str:
        """Format log record as structured JSON"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
        }
        
        # Add extra fields if present
        if record.get("extra"):
            log_entry.update(record["extra"])
        
        return json.dumps(log_entry)


def setup_logging() -> None:
    """Configure application logging"""
    
    # Remove default loguru handler
    logger.remove()
    
    # Development logging (human-readable)
    if settings.DEBUG:
        logger.add(
            sys.stderr,
            level=settings.LOG_LEVEL,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True,
            backtrace=True,
            diagnose=True
        )
    else:
        # Production logging (JSON structured)
        logger.add(
            sys.stderr,
            level=settings.LOG_LEVEL,
            serialize=True
        )
    
    # Add file logging for critical errors
    logger.add(
        "logs/error.log",
        level="ERROR",
        rotation="100 MB",
        retention="30 days",
        compression="zip",  # Changed from gzip to zip
        backtrace=True,
        diagnose=True
    )
    
    # Add trading-specific log file
    logger.add(
        "logs/trading.log",
        level="INFO",
        rotation="50 MB",
        retention="7 days",
        compression="zip",  # Changed from gzip to zip
        filter=lambda record: "trading" in record.get("extra", {}).get("category", "")
    )
    
    # Add performance metrics log
    logger.add(
        "logs/performance.log",
        level="INFO",
        rotation="50 MB",
        retention="7 days",
        compression="zip",  # Changed from gzip to zip
        filter=lambda record: "performance" in record.get("extra", {}).get("category", "")
    )


def get_logger(name: str) -> logger:
    """Get logger instance with module name"""
    return logger.bind(module=name)


# Trading-specific logging functions
def log_trade_execution(order_id: str, symbol: str, side: str, quantity: int, price: float, latency_ms: int) -> None:
    """Log trade execution with structured data"""
    logger.bind(
        category="trading",
        order_id=order_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        latency_ms=latency_ms
    ).info(f"Trade executed: {side} {quantity} {symbol} @ ₹{price} (latency: {latency_ms}ms)")


def log_strategy_signal(strategy_name: str, signal_type: str, symbol: str, confidence: float, **kwargs) -> None:
    """Log strategy signal with metadata"""
    logger.bind(
        category="trading",
        strategy=strategy_name,
        signal_type=signal_type,
        symbol=symbol,
        confidence=confidence,
        **kwargs
    ).info(f"Strategy signal: {strategy_name} - {signal_type} for {symbol} (confidence: {confidence:.2f})")


def log_risk_event(event_type: str, details: Dict[str, Any]) -> None:
    """Log risk management events"""
    logger.bind(
        category="risk",
        event_type=event_type,
        **details
    ).warning(f"Risk event: {event_type}")


def log_performance_metric(metric_name: str, value: float, unit: str = "", **context) -> None:
    """Log performance metrics"""
    logger.bind(
        category="performance",
        metric=metric_name,
        value=value,
        unit=unit,
        **context
    ).info(f"Performance metric: {metric_name} = {value}{unit}")


def log_system_health(component: str, status: str, **metrics) -> None:
    """Log system health metrics"""
    logger.bind(
        category="system",
        component=component,
        status=status,
        **metrics
    ).info(f"System health: {component} - {status}")


# Export commonly used functions
__all__ = [
    "setup_logging",
    "get_logger",
    "log_trade_execution",
    "log_strategy_signal",
    "log_risk_event",
    "log_performance_metric",
    "log_system_health"
] 