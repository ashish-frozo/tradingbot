"""
Audit Log Model
Tracks system events, user actions, and compliance logs
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum
from sqlmodel import SQLModel, Field, Column, DateTime, Numeric, JSON
from sqlalchemy import Index


class AuditAction(str, Enum):
    """Audit action enumeration"""
    # Authentication and authorization
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    
    # Trading actions
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"
    STRATEGY_PAUSED = "strategy_paused"
    TRADE_EXECUTED = "trade_executed"
    ORDER_PLACED = "order_placed"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_MODIFIED = "order_modified"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    
    # Risk management
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    RISK_LIMIT_BREACHED = "risk_limit_breached"
    LOSS_LIMIT_REACHED = "loss_limit_reached"
    MARGIN_CALL = "margin_call"
    
    # Configuration changes
    CONFIG_UPDATED = "config_updated"
    STRATEGY_CONFIG_UPDATED = "strategy_config_updated"
    SYSTEM_CONFIG_UPDATED = "system_config_updated"
    
    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    DATABASE_BACKUP = "database_backup"
    DATABASE_RESTORE = "database_restore"
    
    # Market data events
    MARKET_DATA_CONNECTED = "market_data_connected"
    MARKET_DATA_DISCONNECTED = "market_data_disconnected"
    BROKER_CONNECTED = "broker_connected"
    BROKER_DISCONNECTED = "broker_disconnected"
    
    # Errors and exceptions
    SYSTEM_ERROR = "system_error"
    TRADING_ERROR = "trading_error"
    DATA_ERROR = "data_error"
    CONNECTIVITY_ERROR = "connectivity_error"
    
    # Compliance and regulatory
    COMPLIANCE_REPORT_GENERATED = "compliance_report_generated"
    AUDIT_TRAIL_EXPORTED = "audit_trail_exported"
    REGULATORY_ALERT = "regulatory_alert"


class AuditLog(SQLModel, table=True):
    """
    Audit log model for compliance and tracking
    Records all significant system events and user actions
    """
    
    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Event identification
    action: AuditAction = Field(index=True)
    event_id: Optional[str] = Field(default=None, max_length=100, index=True)
    correlation_id: Optional[str] = Field(default=None, max_length=100, index=True)
    
    # Event details
    description: str = Field(max_length=1000)
    category: str = Field(max_length=50, index=True)
    severity: str = Field(max_length=20)  # 'info', 'warning', 'error', 'critical'
    
    # Actor information
    user_id: Optional[str] = Field(default=None, max_length=100, index=True)
    username: Optional[str] = Field(default=None, max_length=100)
    session_id: Optional[str] = Field(default=None, max_length=100)
    ip_address: Optional[str] = Field(default=None, max_length=45)  # IPv6 compatible
    user_agent: Optional[str] = Field(default=None, max_length=500)
    
    # Resource information
    resource_type: Optional[str] = Field(default=None, max_length=50)  # 'trade', 'strategy', 'config'
    resource_id: Optional[str] = Field(default=None, max_length=100)
    resource_name: Optional[str] = Field(default=None, max_length=200)
    
    # Trading specific fields
    symbol: Optional[str] = Field(default=None, max_length=100, index=True)
    strategy_name: Optional[str] = Field(default=None, max_length=100, index=True)
    order_id: Optional[str] = Field(default=None, max_length=100)
    trade_id: Optional[str] = Field(default=None, max_length=100)
    
    # Financial data
    amount: Optional[Decimal] = Field(
        sa_column=Column(Numeric(15, 2)), default=None
    )
    quantity: Optional[int] = Field(default=None)
    price: Optional[Decimal] = Field(
        sa_column=Column(Numeric(10, 2)), default=None
    )
    
    # Before and after states (for change tracking)
    old_value: Optional[str] = Field(default=None, max_length=1000)
    new_value: Optional[str] = Field(default=None, max_length=1000)
    
    # Additional context and metadata
    event_metadata: Optional[Dict[str, Any]] = Field(
        sa_column=Column(JSON), default=None
    )
    
    # Request/response data for API calls
    request_data: Optional[Dict[str, Any]] = Field(
        sa_column=Column(JSON), default=None
    )
    response_data: Optional[Dict[str, Any]] = Field(
        sa_column=Column(JSON), default=None
    )
    
    # Error information
    error_code: Optional[str] = Field(default=None, max_length=50)
    error_message: Optional[str] = Field(default=None, max_length=1000)
    stack_trace: Optional[str] = Field(default=None)  # Full stack trace for errors
    
    # System information
    module: Optional[str] = Field(default=None, max_length=100)  # Source module/component
    function: Optional[str] = Field(default=None, max_length=100)  # Source function
    process_id: Optional[int] = Field(default=None)
    thread_id: Optional[str] = Field(default=None, max_length=50)
    
    # Performance metrics
    execution_time_ms: Optional[int] = Field(default=None)
    memory_usage_mb: Optional[Decimal] = Field(
        sa_column=Column(Numeric(8, 2)), default=None
    )
    
    # Compliance and regulatory
    regulatory_flag: bool = Field(default=False)
    compliance_category: Optional[str] = Field(default=None, max_length=100)
    retention_period_days: Optional[int] = Field(default=None)
    
    # Archival information
    is_archived: bool = Field(default=False)
    archived_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True)), default=None
    )
    
    # Timestamps
    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True)), 
        default_factory=datetime.utcnow
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)), 
        default_factory=datetime.utcnow
    )
    
    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
    
    def is_error(self) -> bool:
        """Check if this is an error event"""
        return self.severity in ('error', 'critical')
    
    def is_critical(self) -> bool:
        """Check if this is a critical event"""
        return self.severity == 'critical'
    
    def is_trading_related(self) -> bool:
        """Check if this event is trading related"""
        trading_actions = [
            AuditAction.TRADE_EXECUTED,
            AuditAction.ORDER_PLACED,
            AuditAction.ORDER_CANCELLED,
            AuditAction.ORDER_MODIFIED,
            AuditAction.POSITION_OPENED,
            AuditAction.POSITION_CLOSED,
            AuditAction.STRATEGY_STARTED,
            AuditAction.STRATEGY_STOPPED,
            AuditAction.STRATEGY_PAUSED
        ]
        return self.action in trading_actions
    
    def is_risk_related(self) -> bool:
        """Check if this event is risk related"""
        risk_actions = [
            AuditAction.CIRCUIT_BREAKER_TRIGGERED,
            AuditAction.RISK_LIMIT_BREACHED,
            AuditAction.LOSS_LIMIT_REACHED,
            AuditAction.MARGIN_CALL
        ]
        return self.action in risk_actions
    
    def should_alert(self) -> bool:
        """Determine if this event should trigger alerts"""
        return (self.is_critical() or 
                self.is_risk_related() or 
                self.regulatory_flag)
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the event"""
        base = f"{self.action.value}: {self.description}"
        
        if self.username:
            base = f"[{self.username}] {base}"
        
        if self.symbol:
            base = f"{base} ({self.symbol})"
        
        if self.amount:
            base = f"{base} - ₹{self.amount}"
        
        return base
    
    @classmethod
    def create_audit_log(
        cls,
        action: AuditAction,
        description: str,
        category: str = "general",
        severity: str = "info",
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        **kwargs
    ) -> "AuditLog":
        """Factory method to create audit log entries"""
        return cls(
            action=action,
            description=description,
            category=category,
            severity=severity,
            user_id=user_id,
            username=username,
            **kwargs
        )


# Create indexes for performance and querying
AuditLog.__table_args__ = (
    Index('idx_audit_action_timestamp', 'action', 'timestamp'),
    Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
    Index('idx_audit_symbol_timestamp', 'symbol', 'timestamp'),
    Index('idx_audit_strategy_timestamp', 'strategy_name', 'timestamp'),
    Index('idx_audit_severity_timestamp', 'severity', 'timestamp'),
    Index('idx_audit_category_timestamp', 'category', 'timestamp'),
    Index('idx_audit_regulatory', 'regulatory_flag', 'compliance_category'),
    Index('idx_audit_correlation', 'correlation_id'),
    Index('idx_audit_archived', 'is_archived', 'archived_at'),
) 