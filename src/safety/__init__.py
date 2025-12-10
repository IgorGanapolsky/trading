"""Safety systems for trading"""

from .circuit_breakers import CircuitBreaker, SharpeKillSwitch
from .data_backup import (
    DataBackup,
    create_backup,
    get_backup,
)
from .emergency_alerts import (
    EmergencyAlerts,
    get_alerts,
    send_critical_alert,
    send_high_alert,
)
from .failover_system import (
    CircuitBreakerPattern,
    FailoverSystem,
    Watchdog,
    get_failover,
    retry_with_backoff,
    with_failover,
)
from .kill_switch import (
    KillSwitch,
    activate_kill_switch,
    deactivate_kill_switch,
    get_kill_switch,
    is_trading_blocked,
)
from .multi_tier_circuit_breaker import (
    CircuitBreakerAction,
    CircuitBreakerTier,
    MultiTierCircuitBreaker,
    get_circuit_breaker,
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
    # Failover system
    "FailoverSystem",
    "get_failover",
    "retry_with_backoff",
    "with_failover",
    "CircuitBreakerPattern",
    "Watchdog",
]
