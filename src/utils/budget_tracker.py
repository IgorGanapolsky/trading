"""
Budget Tracker - BATS-style budget awareness for trading system.

Implements Google's Budget Aware Test-time Scaling (BATS) framework
to optimize API costs and maintain $100/month budget constraint.

Reference: https://arxiv.org/abs/2511.17006
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# API cost estimates (per call)
API_COSTS = {
    "alpaca_trade": 0.00,
    "alpaca_data": 0.001,
    "openrouter_haiku": 0.0003,
    "openrouter_sonnet": 0.003,
    "openrouter_opus": 0.015,
    "gemini_research": 0.01,
    "polygon_data": 0.0001,
    "yfinance": 0.00,
    "news_api": 0.001,
}

MONTHLY_BUDGET = 100.00
DATA_FILE = Path(__file__).parent.parent.parent / "data" / "budget_tracker.json"


@dataclass
class BudgetStatus:
    """Current budget status."""

    monthly_budget: float
    spent_this_month: float
    remaining: float
    daily_average_remaining: float
    days_left_in_month: int
    budget_health: Literal["healthy", "caution", "critical"]
    last_updated: str


class BudgetTracker:
    """Track and manage API spending for budget awareness."""

    def __init__(self):
        self.data = self._load_data()

    def _load_data(self) -> dict:
        """Load budget data from file or initialize."""
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE) as f:
                    data = json.load(f)
                # Reset if new month
                current_month = datetime.now().strftime("%Y-%m")
                if data.get("current_month") != current_month:
                    return self._initialize_month()
                return data
            except (json.JSONDecodeError, KeyError):
                return self._initialize_month()
        return self._initialize_month()

    def _initialize_month(self) -> dict:
        """Initialize fresh month data."""
        return {
            "monthly_budget": MONTHLY_BUDGET,
            "spent_this_month": 0.0,
            "current_month": datetime.now().strftime("%Y-%m"),
            "api_calls": {},
            "daily_spending": {},
            "last_updated": datetime.now().isoformat(),
        }

    def _save_data(self):
        """Save budget data to file."""
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.data["last_updated"] = datetime.now().isoformat()
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def track(self, api_name: str, cost: float | None = None) -> bool:
        """
        Track an API call and check if budget allows.

        Returns True if call should proceed, False if budget exceeded.
        """
        actual_cost = cost if cost is not None else API_COSTS.get(api_name, 0.001)

        # Update spending
        self.data["spent_this_month"] += actual_cost
        self.data["api_calls"][api_name] = self.data["api_calls"].get(api_name, 0) + 1

        # Track daily spending
        today = datetime.now().strftime("%Y-%m-%d")
        self.data["daily_spending"][today] = (
            self.data["daily_spending"].get(today, 0.0) + actual_cost
        )

        self._save_data()

        remaining = MONTHLY_BUDGET - self.data["spent_this_month"]
        if remaining <= 0:
            logger.warning(f"Budget EXCEEDED: ${self.data['spent_this_month']:.2f} spent")
            return False
        return True

    def should_execute(
        self, operation: str, priority: Literal["critical", "high", "medium", "low"]
    ) -> bool:
        """
        BATS-style decision: should we execute this operation?

        Priority levels:
        - critical: Always runs (trades, risk checks)
        - high: Runs unless critical budget (pre-trade analysis)
        - medium: Skipped in caution mode (deep research)
        - low: Only runs when healthy (optional features)
        """
        health = self._get_health()

        if priority == "critical":
            return True
        if priority == "high":
            return health != "critical"
        if priority == "medium":
            return health == "healthy"
        # low priority
        return health == "healthy"

    def _get_health(self) -> Literal["healthy", "caution", "critical"]:
        """Get budget health status."""
        remaining = MONTHLY_BUDGET - self.data["spent_this_month"]
        pct_remaining = remaining / MONTHLY_BUDGET

        if pct_remaining > 0.50:
            return "healthy"
        if pct_remaining > 0.20:
            return "caution"
        return "critical"

    def get_budget_status(self) -> BudgetStatus:
        """Get comprehensive budget status."""
        remaining = MONTHLY_BUDGET - self.data["spent_this_month"]
        now = datetime.now()
        days_left = 32 - now.day  # Approximate days left in month

        return BudgetStatus(
            monthly_budget=MONTHLY_BUDGET,
            spent_this_month=self.data["spent_this_month"],
            remaining=remaining,
            daily_average_remaining=remaining / max(days_left, 1),
            days_left_in_month=days_left,
            budget_health=self._get_health(),
            last_updated=self.data["last_updated"],
        )

    def get_recommended_model(self) -> Literal["opus", "sonnet", "haiku"]:
        """BATS-style model selection based on budget health."""
        health = self._get_health()
        if health == "healthy":
            return "opus"
        if health == "caution":
            return "sonnet"
        return "haiku"

    def get_prompt_injection(self) -> str:
        """Get budget awareness prompt for LLM agents."""
        status = self.get_budget_status()

        guidance = {
            "healthy": "Proceed normally with all operations.",
            "caution": "Skip medium/low priority operations. Use Sonnet instead of Opus.",
            "critical": "Only critical operations. Use Haiku model.",
        }

        return f"""[BUDGET AWARENESS]
Monthly Budget: ${status.monthly_budget:.2f}
Spent: ${status.spent_this_month:.2f}
Remaining: ${status.remaining:.2f} ({status.days_left_in_month} days left)
Daily Allowance: ${status.daily_average_remaining:.2f}/day
Status: {status.budget_health.upper()}

GUIDANCE: {guidance[status.budget_health]}
"""


# Global instance
_tracker: BudgetTracker | None = None


def get_tracker() -> BudgetTracker:
    """Get global budget tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = BudgetTracker()
    return _tracker


# Convenience functions matching SKILL.md API
def track(api_name: str, cost: float | None = None) -> bool:
    """Track an API call."""
    return get_tracker().track(api_name, cost)


def should_execute(operation: str, priority: Literal["critical", "high", "medium", "low"]) -> bool:
    """Check if operation should execute."""
    return get_tracker().should_execute(operation, priority)


def get_model() -> Literal["opus", "sonnet", "haiku"]:
    """Get recommended model based on budget."""
    return get_tracker().get_recommended_model()


def get_budget_prompt() -> str:
    """Get budget awareness prompt injection."""
    return get_tracker().get_prompt_injection()


if __name__ == "__main__":
    # Test the budget tracker
    tracker = get_tracker()
    print(tracker.get_prompt_injection())
    print(f"\nRecommended model: {get_model()}")
    print(f"Should execute deep_research (medium): {should_execute('deep_research', 'medium')}")
    print(f"Should execute trade (critical): {should_execute('trade', 'critical')}")
