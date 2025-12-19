"""Stub module - original safety deleted in cleanup."""


class CircuitBreakerPattern:
    """Stub for deleted circuit breaker."""

    def __init__(self, *args, **kwargs):
        self.open = False

    def is_open(self) -> bool:
        return False

    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution."""
        return not self.open

    def record_success(self) -> None:
        pass

    def record_failure(self) -> None:
        pass

    def __call__(self, func):
        """Decorator that does nothing."""
        return func
