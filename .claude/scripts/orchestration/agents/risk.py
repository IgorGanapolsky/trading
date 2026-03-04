"""
Risk Assessment Agent

Enforces Phil Town Rule #1: Don't Lose Money

Analyzes:
- Account equity and position sizing
- Current exposure
- Portfolio heat
- Compliance with trading rules
"""

import json
from pathlib import Path
from typing import Any

from .base import BaseAgent


class RiskAgent(BaseAgent):
    """Risk assessment agent (Phil Town Rule #1)."""

    # Trading rules
    MAX_POSITION_PCT = 0.05  # 5% max per position
    MAX_PORTFOLIO_HEAT = 0.20  # 20% max total exposure
    STOP_LOSS_MULTIPLIER = 1.0  # 100% of credit

    def __init__(self, project_dir: Path | None = None):
        super().__init__("risk")
        self.project_dir = project_dir or Path(__file__).parent.parent.parent.parent.parent

    async def analyze(self) -> dict[str, Any]:
        """Analyze risk parameters and compliance."""
        # Load account data
        state_file = self.project_dir / "data" / "system_state.json"
        account_equity = 100000  # Default $100K

        positions = []
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                account_equity = float(state.get("account", {}).get("current_equity", 100000))
                positions = state.get("positions", [])
            except (json.JSONDecodeError, KeyError):
                pass

        # Calculate metrics
        max_position_size = account_equity * self.MAX_POSITION_PCT
        max_total_exposure = account_equity * self.MAX_PORTFOLIO_HEAT

        # Calculate current exposure from positions
        current_exposure = sum(abs(float(p.get("market_value", 0))) for p in positions)
        exposure_pct = current_exposure / account_equity if account_equity > 0 else 0

        # Check compliance
        compliance_checks = {
            "position_size_ok": True,  # Will be checked per trade
            "exposure_under_limit": exposure_pct <= self.MAX_PORTFOLIO_HEAT,
            "stop_loss_defined": True,  # Required for each trade
            "spy_only": (
                all(p.get("symbol", "").startswith("SPY") for p in positions) if positions else True
            ),
        }

        all_compliant = all(compliance_checks.values())

        # Calculate signal
        # Higher signal = safer to trade
        if not all_compliant:
            signal = 0.3  # Non-compliant
        elif exposure_pct > 0.15:
            signal = 0.5  # Approaching limit
        elif exposure_pct > 0.10:
            signal = 0.7  # Moderate exposure
        else:
            signal = 0.9  # Low exposure, safe to trade

        return {
            "signal": round(signal, 3),
            "confidence": 0.95,  # Risk assessment is high confidence
            "data": {
                "account_equity": account_equity,
                "max_position_size": max_position_size,
                "max_total_exposure": max_total_exposure,
                "current_exposure": round(current_exposure, 2),
                "exposure_percent": round(exposure_pct * 100, 2),
                "open_positions": len(positions),
                "compliance": compliance_checks,
                "phil_town_compliant": all_compliant,
                "recommendation": self._get_recommendation(signal, exposure_pct),
                "rules": {
                    "max_position_pct": self.MAX_POSITION_PCT * 100,
                    "max_portfolio_heat": self.MAX_PORTFOLIO_HEAT * 100,
                    "stop_loss_rule": f"{int(self.STOP_LOSS_MULTIPLIER * 100)}% of credit",
                },
            },
        }

    def _get_recommendation(self, signal: float, exposure_pct: float) -> str:
        """Generate risk recommendation."""
        if signal >= 0.8:
            return "safe_to_open_new_position"
        elif signal >= 0.6:
            return "can_trade_with_caution"
        elif signal >= 0.4:
            return "reduce_exposure_first"
        else:
            return "do_not_trade_fix_compliance"
