"""
System Configuration Model
Manages application-wide settings and parameters
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum
from sqlmodel import SQLModel, Field, Column, DateTime, Numeric, JSON
from sqlalchemy import Index


class ConfigCategory(str, Enum):
    """Configuration category enumeration"""
    SYSTEM = "system"
    TRADING = "trading"
    RISK = "risk"
    BROKER = "broker"
    MARKET_DATA = "market_data"
    NOTIFICATION = "notification"
    LOGGING = "logging"
    PERFORMANCE = "performance"


class SystemConfig(SQLModel, table=True):
    """
    System configuration model
    Stores application-wide settings and parameters
    """
    
    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Configuration identification
    key: str = Field(max_length=100, unique=True, index=True)
    category: ConfigCategory = Field(index=True)
    description: str = Field(max_length=500)
    
    # Configuration value (supports multiple types)
    value: Optional[str] = Field(default=None, max_length=1000)
    value_type: str = Field(max_length=20)  # 'string', 'int', 'float', 'bool', 'json'
    
    # Typed values for easier access
    string_value: Optional[str] = Field(default=None, max_length=1000)
    int_value: Optional[int] = Field(default=None)
    float_value: Optional[Decimal] = Field(
        sa_column=Column(Numeric(15, 6)), default=None
    )
    bool_value: Optional[bool] = Field(default=None)
    json_value: Optional[Dict[str, Any]] = Field(
        sa_column=Column(JSON), default=None
    )
    
    # Default values
    default_value: Optional[str] = Field(default=None, max_length=1000)
    
    # Validation and constraints
    min_value: Optional[Decimal] = Field(
        sa_column=Column(Numeric(15, 6)), default=None
    )
    max_value: Optional[Decimal] = Field(
        sa_column=Column(Numeric(15, 6)), default=None
    )
    allowed_values: Optional[str] = Field(default=None, max_length=500)  # CSV format
    validation_regex: Optional[str] = Field(default=None, max_length=200)
    
    # Metadata
    is_required: bool = Field(default=False)
    is_sensitive: bool = Field(default=False)  # For passwords, API keys
    is_readonly: bool = Field(default=False)
    requires_restart: bool = Field(default=False)
    
    # Environment and deployment
    environment: Optional[str] = Field(default=None, max_length=20)  # 'dev', 'test', 'prod'
    
    # Version and change tracking
    version: int = Field(default=1)
    last_modified_by: Optional[str] = Field(default=None, max_length=100)
    change_reason: Optional[str] = Field(default=None, max_length=300)
    
    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)), 
        default_factory=datetime.utcnow
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True)), 
        default_factory=datetime.utcnow
    )
    
    class Config:
        """Pydantic configuration"""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
    
    def get_typed_value(self) -> Any:
        """Get the configuration value in its proper type"""
        if self.value_type == "string":
            return self.string_value or self.value
        elif self.value_type == "int":
            return self.int_value if self.int_value is not None else (
                int(self.value) if self.value else None
            )
        elif self.value_type == "float":
            return float(self.float_value) if self.float_value is not None else (
                float(self.value) if self.value else None
            )
        elif self.value_type == "bool":
            return self.bool_value if self.bool_value is not None else (
                self.value.lower() in ('true', '1', 'yes', 'on') if self.value else None
            )
        elif self.value_type == "json":
            return self.json_value if self.json_value is not None else (
                eval(self.value) if self.value else None
            )
        else:
            return self.value
    
    def set_typed_value(self, value: Any) -> None:
        """Set the configuration value with proper type conversion"""
        self.value = str(value)
        
        if self.value_type == "string":
            self.string_value = str(value)
        elif self.value_type == "int":
            self.int_value = int(value)
        elif self.value_type == "float":
            self.float_value = Decimal(str(value))
        elif self.value_type == "bool":
            self.bool_value = bool(value)
        elif self.value_type == "json":
            self.json_value = value if isinstance(value, dict) else {"value": value}
        
        self.updated_at = datetime.utcnow()
        self.version += 1
    
    def validate_value(self, value: Any) -> bool:
        """Validate the configuration value against constraints"""
        if self.value_type in ("int", "float"):
            num_value = float(value)
            if self.min_value is not None and num_value < float(self.min_value):
                return False
            if self.max_value is not None and num_value > float(self.max_value):
                return False
        
        if self.allowed_values:
            allowed = [v.strip() for v in self.allowed_values.split(',')]
            if str(value) not in allowed:
                return False
        
        if self.validation_regex:
            import re
            if not re.match(self.validation_regex, str(value)):
                return False
        
        return True
    
    def get_display_value(self) -> str:
        """Get display-safe value (masks sensitive data)"""
        if self.is_sensitive and self.value:
            return "*" * min(len(self.value), 8)
        return self.value or ""


# Create indexes for performance
SystemConfig.__table_args__ = (
    Index('idx_config_category_key', 'category', 'key'),
    Index('idx_config_environment', 'environment', 'category'),
    Index('idx_config_updated', 'updated_at'),
)


# Default system configurations
DEFAULT_CONFIGS = [
    # System settings
    {
        "key": "app_name",
        "category": ConfigCategory.SYSTEM,
        "description": "Application name",
        "value": "QuantHub Trading Bot",
        "value_type": "string",
        "is_required": True,
        "is_readonly": True
    },
    {
        "key": "app_version", 
        "category": ConfigCategory.SYSTEM,
        "description": "Application version",
        "value": "1.0.0",
        "value_type": "string",
        "is_readonly": True
    },
    {
        "key": "debug_mode",
        "category": ConfigCategory.SYSTEM, 
        "description": "Enable debug logging",
        "value": "false",
        "value_type": "bool",
        "requires_restart": True
    },
    
    # Trading settings
    {
        "key": "max_daily_trades",
        "category": ConfigCategory.TRADING,
        "description": "Maximum trades per day",
        "value": "100",
        "value_type": "int",
        "min_value": Decimal('1'),
        "max_value": Decimal('500')
    },
    {
        "key": "default_strategy",
        "category": ConfigCategory.TRADING,
        "description": "Default trading strategy",
        "value": "volume_oi_confirm",
        "value_type": "string"
    },
    
    # Risk management
    {
        "key": "max_portfolio_risk",
        "category": ConfigCategory.RISK,
        "description": "Maximum portfolio risk percentage",
        "value": "5.0",
        "value_type": "float",
        "min_value": Decimal('0.1'),
        "max_value": Decimal('20.0')
    },
    {
        "key": "daily_loss_limit",
        "category": ConfigCategory.RISK,
        "description": "Daily loss limit in INR",
        "value": "25000",
        "value_type": "float",
        "min_value": Decimal('1000')
    },
    
    # Broker settings
    {
        "key": "broker_name",
        "category": ConfigCategory.BROKER,
        "description": "Broker name",
        "value": "Dhan",
        "value_type": "string",
        "is_readonly": True
    },
    {
        "key": "order_timeout_seconds",
        "category": ConfigCategory.BROKER,
        "description": "Order timeout in seconds",
        "value": "30",
        "value_type": "int",
        "min_value": Decimal('5'),
        "max_value": Decimal('300')
    },
    
    # Performance settings
    {
        "key": "max_latency_ms",
        "category": ConfigCategory.PERFORMANCE,
        "description": "Maximum acceptable latency in milliseconds",
        "value": "150",
        "value_type": "int",
        "min_value": Decimal('50'),
        "max_value": Decimal('1000')
    },
    {
        "key": "min_uptime_pct",
        "category": ConfigCategory.PERFORMANCE,
        "description": "Minimum uptime percentage",
        "value": "99.5",
        "value_type": "float",
        "min_value": Decimal('95.0'),
        "max_value": Decimal('100.0')
    }
] 