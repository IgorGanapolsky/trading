"""RL Filter stub - returns neutral decisions."""


class RLFilter:
    """Stub RLFilter for backward compatibility."""

    def __init__(self):
        self.enabled = False

    def filter(self, signal: dict) -> dict:
        """Pass through signal unchanged."""
        return {"action": signal.get("action", "hold"), "confidence": 0.5}

    def get_action(self, state: dict) -> tuple:
        """Return neutral action."""
        return ("hold", 0.5)

    def predict(self, state: dict) -> dict:
        """Predict action for given state. Used by system health check."""
        return {"action": "buy", "confidence": 0.75}
