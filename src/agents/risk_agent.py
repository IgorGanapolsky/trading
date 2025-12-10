"""
Risk Agent: Portfolio risk management and position sizing

Responsibilities:
- Calculate position sizes (Kelly Criterion)
- Set stop-loss levels
- Portfolio risk assessment
- Circuit breaker checks

Ensures we never blow up the account
"""

import builtins
import contextlib
import logging
from typing import Any

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """
    Risk Agent manages portfolio risk and position sizing.

    Key functions:
    - Position sizing based on Kelly Criterion
    - Stop-loss calculation
    - Portfolio diversification checks
    - Circuit breakers
    """

    def __init__(self, max_portfolio_risk: float = 0.02, max_position_size: float = 0.05):
        super().__init__(name="RiskAgent", role="Portfolio risk management and position sizing")
        self.max_portfolio_risk = max_portfolio_risk  # Max 2% risk per trade
        self.max_position_size = max_position_size  # Max 5% per position

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Assess risk and calculate position sizing.

        Args:
            data: Portfolio state, proposed trade, market conditions

        Returns:
            Risk analysis with position size recommendation
        """
        portfolio_value = data.get("portfolio_value", 100000)
        proposed_action = data.get("proposed_action", "HOLD")
        symbol = data.get("symbol", "UNKNOWN")
        confidence = data.get("confidence", 0.5)
        volatility = data.get("volatility", 0.20)
        win_rate = data.get("historical_win_rate", 0.60)

        # Calculate position size
        position_size = self._calculate_position_size(
            portfolio_value, confidence, volatility, win_rate
        )

        # Calculate stop-loss
        stop_loss_pct = self._calculate_stop_loss(volatility)

        # Risk assessment
        memory_context = self.get_memory_context(limit=3)

        # Prompt following Anthropic best practices:
        # - XML tags for structure (Claude trained on XML)
        # - Motivation/context explaining WHY capital protection matters
        # - Clear examples covering approve, reduce, and reject scenarios
        prompt = f"""Evaluate the risk of {proposed_action} on {symbol}.

<context>
You are a risk manager with one paramount rule: protect capital first, returns second.
A 50% loss requires a 100% gain to recover - survival is non-negotiable.
Position sizing is the most underappreciated edge in trading.
</context>

<portfolio>
Value: ${portfolio_value:,.0f} | Max Risk: {self.max_portfolio_risk:.1%}/trade | Max Position: {self.max_position_size:.1%}
</portfolio>

<trade_proposal>
Action: {proposed_action} | Confidence: {confidence:.0%} | Volatility: {volatility:.1%} | Historical Win Rate: {win_rate:.0%}
</trade_proposal>

<calculated_parameters>
Suggested Size: ${position_size:,.0f} ({position_size / portfolio_value:.1%} of portfolio)
Stop Loss: {stop_loss_pct:.1%}
Max Loss if Stopped: ${position_size * stop_loss_pct:,.0f}
</calculated_parameters>

{memory_context}

<principles>
Kelly Criterion + Safety rules (each prevents a different failure mode):
- Never risk more than 2% of portfolio on single trade (weight: 35%) - Survival rule prevents ruin
- High volatility above 25% = reduce position 50% (weight: 25%) - Volatility scaling prevents outsized losses
- Low confidence below 0.6 = reduce or reject (weight: 25%) - Conviction filter prevents FOMO trades
- Correlation risk: reject if more than 3 similar positions open (weight: 15%) - Diversification prevents concentration blowup
</principles>

<examples>
<example type="approve_full">
RISK_SCORE: 3
POSITION_APPROVAL: APPROVE
POSITION_SIZE: $2,500
STOP_LOSS: 4%
RISKS: Normal market risk, sector correlation with existing QQQ position
RECOMMENDATION: APPROVE
</example>

<example type="reduce_volatility">
RISK_SCORE: 7
POSITION_APPROVAL: REDUCE
POSITION_SIZE: $1,200
STOP_LOSS: 8%
RISKS: High volatility requires tighter sizing, earnings in 3 days adds event risk
RECOMMENDATION: APPROVE
</example>

<example type="reject">
RISK_SCORE: 9
POSITION_APPROVAL: REJECT
POSITION_SIZE: $0
STOP_LOSS: N/A
RISKS: Confidence too low (0.45), already 4 tech positions, max drawdown approaching limit
RECOMMENDATION: REJECT
</example>
</examples>

<task>
Evaluate {symbol} {proposed_action} now and respond in this exact format:
RISK_SCORE: [1-10]
POSITION_APPROVAL: [APPROVE/REDUCE/REJECT]
POSITION_SIZE: [$ amount]
STOP_LOSS: [%]
RISKS: [top 2 risks]
RECOMMENDATION: [APPROVE/REJECT]
</task>"""

        # Get LLM analysis
        response = self.reason_with_llm(prompt)

        # Parse response
        analysis = self._parse_risk_response(response["reasoning"])
        analysis["calculated_position_size"] = position_size
        analysis["calculated_stop_loss"] = stop_loss_pct
        analysis["full_reasoning"] = response["reasoning"]

        # Log decision
        self.log_decision(analysis)

        return analysis

    def _calculate_position_size(
        self,
        portfolio_value: float,
        confidence: float,
        volatility: float,
        win_rate: float,
    ) -> float:
        """
        Calculate position size using Kelly Criterion with safety adjustments.

        Args:
            portfolio_value: Total portfolio value
            confidence: Trade confidence (0-1)
            volatility: Symbol volatility
            win_rate: Historical win rate

        Returns:
            Position size in dollars
        """
        # Kelly Criterion: f = (p * b - q) / b
        # where p = win probability, q = loss probability, b = win/loss ratio

        win_prob = min(confidence * win_rate, 0.8)  # Cap at 80%
        loss_prob = 1 - win_prob
        win_loss_ratio = 1.5  # Assume 1.5:1 reward/risk

        kelly_fraction = (win_prob * win_loss_ratio - loss_prob) / win_loss_ratio

        # Safety: Use half-Kelly and cap at max position size
        safe_fraction = max(kelly_fraction * 0.5, 0.01)  # Min 1%
        safe_fraction = min(safe_fraction, self.max_position_size)  # Max 5%

        # Adjust for volatility (higher vol = smaller position)
        volatility_adjustment = 1.0 / (1.0 + volatility * 2)
        adjusted_fraction = safe_fraction * volatility_adjustment

        position_size = portfolio_value * adjusted_fraction

        # Enforce minimums and maximums
        position_size = max(position_size, 10.0)  # Min $10
        position_size = min(position_size, portfolio_value * self.max_position_size)

        return position_size

    def _calculate_stop_loss(self, volatility: float) -> float:
        """
        Calculate stop-loss percentage based on volatility.

        Args:
            volatility: Symbol volatility

        Returns:
            Stop-loss percentage (e.g., 0.05 = 5%)
        """
        # 2x volatility as stop-loss (gives room for normal fluctuations)
        stop_loss = volatility * 2

        # Cap between 2% and 10%
        stop_loss = max(stop_loss, 0.02)
        stop_loss = min(stop_loss, 0.10)

        return stop_loss

    def _parse_risk_response(self, reasoning: str) -> dict[str, Any]:
        """Parse LLM response into structured risk assessment."""
        lines = reasoning.split("\n")
        analysis = {
            "risk_score": 5,
            "position_approval": "APPROVE",
            "position_size": 0,
            "stop_loss": 0.05,
            "risks": "",
            "action": "APPROVE",
        }

        for line in lines:
            line = line.strip()
            if line.startswith("RISK_SCORE:"):
                with contextlib.suppress(builtins.BaseException):
                    analysis["risk_score"] = int(line.split(":")[1].strip())
            elif line.startswith("POSITION_APPROVAL:"):
                approval = line.split(":")[1].strip().upper()
                if approval in ["APPROVE", "REDUCE", "REJECT"]:
                    analysis["position_approval"] = approval
            elif line.startswith("POSITION_SIZE:"):
                try:
                    size_str = line.split(":")[1].strip().replace("$", "").replace(",", "")
                    analysis["position_size"] = float(size_str)
                except Exception:
                    pass
            elif line.startswith("STOP_LOSS:"):
                try:
                    sl_str = line.split(":")[1].strip().replace("%", "")
                    analysis["stop_loss"] = float(sl_str) / 100
                except Exception:
                    pass
            elif line.startswith("RISKS:"):
                analysis["risks"] = line.split(":", 1)[1].strip()
            elif line.startswith("RECOMMENDATION:"):
                rec = line.split(":")[1].strip().upper()
                if rec in ["APPROVE", "REJECT"]:
                    analysis["action"] = rec

        return analysis
