"""
Budget-Aware Agent Framework for Trading
Based on Google's BATS (Budget Aware Test-time Scaling) research
Paper: https://arxiv.org/abs/2511.17006

Enables our trading agents to:
1. Track remaining API/compute budget
2. Dynamically adjust research depth
3. Prioritize high-value operations
4. Skip expensive operations when budget is low
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Monthly budget allocation ($100/month)
MONTHLY_BUDGET = 100.0

# Cost estimates per API call (in dollars)
API_COSTS = {
    "alpaca_trade": 0.00,  # Free (paper trading)
    "alpaca_data": 0.001,  # ~$0.001 per data call
    "openrouter_haiku": 0.0003,  # $0.25/1M tokens
    "openrouter_sonnet": 0.003,  # $3/1M tokens
    "openrouter_opus": 0.015,  # $15/1M tokens
    "gemini_research": 0.01,  # ~$0.01 per research query
    "polygon_data": 0.0001,  # Very cheap
    "yfinance": 0.00,  # Free
    "news_api": 0.001,  # ~$0.001 per call
}

# Priority levels for operations
PRIORITY = {
    "critical": 1,  # Must execute (trades, risk checks)
    "high": 2,  # Important (pre-trade analysis)
    "medium": 3,  # Nice to have (deep research)
    "low": 4,  # Optional (sentiment analysis)
}


@dataclass
class BudgetState:
    """Current budget state"""

    monthly_budget: float
    spent_this_month: float
    remaining: float
    daily_average_remaining: float
    days_left_in_month: int
    budget_health: str  # "healthy", "caution", "critical"
    last_updated: str


class BudgetTracker:
    """
    Lightweight budget tracker that provides continuous budget awareness.
    Reduces API costs by 31.3% based on Google's research.
    """

    def __init__(self, budget_file: str = "data/budget_tracker.json"):
        self.budget_file = Path(budget_file)
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """Load or initialize budget state"""
        if self.budget_file.exists():
            try:
                with open(self.budget_file) as f:
                    return json.load(f)
            except:
                pass

        # Initialize new state
        return {
            "monthly_budget": MONTHLY_BUDGET,
            "spent_this_month": 0.0,
            "api_calls": {},
            "daily_spending": {},
            "month_start": datetime.now().strftime("%Y-%m-01"),
        }

    def _save_state(self):
        """Persist state to disk"""
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.budget_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def _reset_if_new_month(self):
        """Reset counters on new month"""
        current_month = datetime.now().strftime("%Y-%m-01")
        if self.state.get("month_start") != current_month:
            logger.info("🔄 New month detected, resetting budget tracker")
            self.state["month_start"] = current_month
            self.state["spent_this_month"] = 0.0
            self.state["api_calls"] = {}
            self.state["daily_spending"] = {}
            self._save_state()

    def track_call(self, api_name: str, cost: Optional[float] = None) -> bool:
        """
        Track an API call and its cost.
        Returns True if call should proceed, False if budget exceeded.
        """
        self._reset_if_new_month()

        # Get cost estimate
        if cost is None:
            cost = API_COSTS.get(api_name, 0.001)

        # Update tracking
        self.state["spent_this_month"] += cost
        self.state["api_calls"][api_name] = self.state["api_calls"].get(api_name, 0) + 1

        today = datetime.now().strftime("%Y-%m-%d")
        self.state["daily_spending"][today] = self.state["daily_spending"].get(today, 0) + cost

        self._save_state()

        # Check if we should proceed
        remaining = self.state["monthly_budget"] - self.state["spent_this_month"]
        return remaining > 0

    def get_budget_status(self) -> BudgetState:
        """Get current budget status for agent awareness"""
        self._reset_if_new_month()

        spent = self.state["spent_this_month"]
        remaining = self.state["monthly_budget"] - spent

        # Calculate days left in month
        today = datetime.now()
        if today.month == 12:
            next_month = datetime(today.year + 1, 1, 1)
        else:
            next_month = datetime(today.year, today.month + 1, 1)
        days_left = (next_month - today).days

        daily_avg = remaining / max(days_left, 1)

        # Determine health
        pct_remaining = remaining / self.state["monthly_budget"]
        if pct_remaining > 0.5:
            health = "healthy"
        elif pct_remaining > 0.2:
            health = "caution"
        else:
            health = "critical"

        return BudgetState(
            monthly_budget=self.state["monthly_budget"],
            spent_this_month=spent,
            remaining=remaining,
            daily_average_remaining=daily_avg,
            days_left_in_month=days_left,
            budget_health=health,
            last_updated=datetime.now().isoformat(),
        )

    def should_execute(self, operation: str, priority: str = "medium") -> bool:
        """
        BATS-style decision: should we execute this operation given budget?

        Args:
            operation: API/operation name
            priority: "critical", "high", "medium", "low"

        Returns:
            True if operation should proceed
        """
        status = self.get_budget_status()
        priority_level = PRIORITY.get(priority, 3)

        # Critical operations always execute
        if priority_level == 1:
            return True

        # Budget-aware decisions
        if status.budget_health == "critical":
            # Only critical operations
            return priority_level <= 1
        elif status.budget_health == "caution":
            # Critical and high priority only
            return priority_level <= 2
        else:
            # All operations OK
            return True

    def get_prompt_injection(self) -> str:
        """
        Budget Tracker prompt injection for agent awareness.
        This is the key technique from Google's paper.
        """
        status = self.get_budget_status()

        return f"""[BUDGET AWARENESS]
Monthly Budget: ${status.monthly_budget:.2f}
Spent: ${status.spent_this_month:.2f}
Remaining: ${status.remaining:.2f} ({status.days_left_in_month} days left)
Daily Allowance: ${status.daily_average_remaining:.2f}/day
Status: {status.budget_health.upper()}

GUIDANCE:
- {"Proceed normally with all operations" if status.budget_health == "healthy" else ""}
- {"Prioritize critical operations, skip low-priority research" if status.budget_health == "caution" else ""}
- {"CRITICAL: Only execute essential trades and risk checks" if status.budget_health == "critical" else ""}
"""

    def get_recommended_model(self) -> str:
        """
        BATS-style model selection based on budget.
        Use cheaper models when budget is tight.
        """
        status = self.get_budget_status()

        if status.budget_health == "critical":
            return "haiku"  # Cheapest
        elif status.budget_health == "caution":
            return "sonnet"  # Balanced
        else:
            return "opus"  # Best quality


# Singleton instance
_tracker = None


def get_tracker() -> BudgetTracker:
    global _tracker
    if _tracker is None:
        _tracker = BudgetTracker()
    return _tracker


# Convenience functions
def track(api_name: str, cost: Optional[float] = None) -> bool:
    return get_tracker().track_call(api_name, cost)


def should_execute(operation: str, priority: str = "medium") -> bool:
    return get_tracker().should_execute(operation, priority)


def get_budget_prompt() -> str:
    return get_tracker().get_prompt_injection()


def get_model() -> str:
    return get_tracker().get_recommended_model()


if __name__ == "__main__":
    # Test the budget tracker
    tracker = get_tracker()

    print("=== Budget Tracker Test ===")
    print(tracker.get_prompt_injection())

    # Simulate some API calls
    for _ in range(5):
        tracker.track_call("openrouter_sonnet")

    print("\nAfter 5 Sonnet calls:")
    print(tracker.get_prompt_injection())

    print(f"\nRecommended model: {tracker.get_recommended_model()}")
    print(f"Should execute deep research? {tracker.should_execute('gemini_research', 'medium')}")
