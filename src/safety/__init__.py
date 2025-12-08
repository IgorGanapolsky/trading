"""Safety systems for trading"""

from .circuit_breakers import CircuitBreaker, SharpeKillSwitch
from .multi_tier_circuit_breaker import (
    CircuitBreakerAction,
    CircuitBreakerTier,
    MultiTierCircuitBreaker,
    get_circuit_breaker,
)
from .kill_switch import (
    KillSwitch,
    get_kill_switch,
    is_trading_blocked,
    activate_kill_switch,
    deactivate_kill_switch,
)
from .emergency_alerts import (
    EmergencyAlerts,
    get_alerts,
    send_critical_alert,
    send_high_alert,
)
from .data_backup import (
    DataBackup,
    get_backup,
    create_backup,
)

__all__ = [
    # Circuit breakers
    "CircuitBreaker",
    "SharpeKillSwitch",
    "MultiTierCircuitBreaker",
    "CircuitBreakerTier",
    "CircuitBreakerAction",
    "get_circuit_breaker",
    # Kill switch
    "KillSwitch",
    "get_kill_switch",
    "is_trading_blocked",
    "activate_kill_switch",
    "deactivate_kill_switch",
    # Emergency alerts
    "EmergencyAlerts",
    "get_alerts",
    "send_critical_alert",
    "send_high_alert",
    # Data backup
    "DataBackup",
    "get_backup",
    "create_backup",
]
