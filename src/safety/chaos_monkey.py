import logging
import random
import time
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class ChaosMonkey:
    """
    Chaos Engineering utility for the trading system.
    Injects simulated failures (latency, errors, data corruption) to test resilience.
    """

    def __init__(self, enabled: bool = False, probability: float = 0.1):
        self.enabled = enabled
        self.probability = probability
        self.active_scenarios = []

    def inject_latency(self, min_ms: int = 100, max_ms: int = 2000):
        """Decorator to inject random latency."""

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if self.enabled and random.random() < self.probability:
                    delay = random.randint(min_ms, max_ms) / 1000.0
                    logger.warning(
                        f"🐒 Chaos Monkey: Injecting {delay:.2f}s latency into {func.__name__}"
                    )
                    time.sleep(delay)
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def inject_error(self, exception_cls: type = Exception, message: str = "Chaos Monkey Error"):
        """Decorator to inject random exceptions."""

        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if self.enabled and random.random() < self.probability:
                    logger.warning(f"🐒 Chaos Monkey: Injecting error into {func.__name__}")
                    raise exception_cls(message)
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def corrupt_data(self, data: Any) -> Any:
        """Randomly corrupt data structures (for testing validation logic)."""
        if not self.enabled or random.random() >= self.probability:
            return data

        logger.warning("🐒 Chaos Monkey: Corrupting data")
        if isinstance(data, dict):
            # Drop a random key
            if data:
                key_to_drop = random.choice(list(data.keys()))
                del data[key_to_drop]
        elif isinstance(data, list):
            # Drop a random item
            if data:
                data.pop(random.randint(0, len(data) - 1))
        elif isinstance(data, (int, float)):
            # Return None or garbage
            return None

        return data


# Global instance
chaos_monkey = ChaosMonkey(enabled=False)  # Disabled by default
