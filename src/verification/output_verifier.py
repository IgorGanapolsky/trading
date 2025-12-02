"""
Output Verification System - Claude Agent SDK Loop Pattern

Implements the "Verify Output" phase from Claude Agent SDK Loop:
1. Defining Rules - Quality and output type specifications
2. Visual Feedback - Visual verification (future: Playwright MCP)
3. LLM-as-a-Judge - Evaluate quality based on fuzzy rules

This prevents the anti-lying problem by systematically verifying results
before claiming success.
"""

import json
from dataclasses import dataclass
from datetime import datetime


@dataclass
class VerificationRule:
    """Quality rule for output verification"""

    name: str
    condition: callable
    severity: str  # "critical", "warning", "info"
    message: str


class OutputVerifier:
    """
    Systematic output verification following Claude Agent SDK Loop

    Verifies:
    - Trade execution quality
    - Portfolio health
    - System reliability
    - Win rate targets
    """

    def __init__(self, system_state_path: str = "data/system_state.json"):
        self.system_state_path = system_state_path
        self.verification_rules = self._define_rules()

    def _define_rules(self) -> list[VerificationRule]:
        """
        Define quality rules for trade verification
        Following SDK pattern: "Defining Rules - Provide specific rules on quality and types of outputs"
        """
        return [
            # CRITICAL RULES (must pass)
            VerificationRule(
                name="portfolio_not_negative",
                condition=lambda state: state["account"]["total_pl"] > -1000,  # Max $1000 loss
                severity="critical",
                message="Portfolio loss exceeds $1000 limit",
            ),
            VerificationRule(
                name="automation_operational",
                condition=lambda state: state["automation"].get("workflow_status") == "OPERATIONAL",
                severity="critical",
                message="Automation workflow is not operational",
            ),
            VerificationRule(
                name="data_freshness",
                condition=lambda state: self._check_freshness(state["meta"]["last_updated"]),
                severity="critical",
                message="System state data is stale (>24 hours old)",
            ),
            # WARNING RULES (should pass)
            VerificationRule(
                name="win_rate_target",
                condition=lambda state: state["performance"]["win_rate"] >= 50.0
                or state["challenge"]["current_day"] < 30,
                severity="warning",
                message="Win rate below 50% target (after Day 30)",
            ),
            VerificationRule(
                name="profitable_trend",
                condition=lambda state: state["account"]["total_pl"] >= 0
                or state["challenge"]["current_day"] < 30,
                severity="warning",
                message="Portfolio not profitable (expected after Day 30)",
            ),
            # INFO RULES (nice to have)
            VerificationRule(
                name="backtest_alignment",
                condition=lambda state: abs(state["performance"]["win_rate"] - 62.2) < 20
                or state["challenge"]["current_day"] < 30,
                severity="info",
                message="Live win rate diverging from backtest (62.2%)",
            ),
        ]

    def _check_freshness(self, last_updated: str, max_age_hours: int = 24) -> bool:
        """Check if data is fresh (not stale)"""
        try:
            last_update_time = datetime.fromisoformat(last_updated)
            age_hours = (datetime.now() - last_update_time).total_seconds() / 3600
            return age_hours < max_age_hours
        except Exception:
            return False

    def verify_execution(self, trades: list[dict]) -> tuple[bool, list[str]]:
        """
        Verify trade execution quality

        Returns:
            (success: bool, issues: List[str])
        """
        issues = []

        # Rule: All orders must be accepted or filled
        for trade in trades:
            if trade["status"] not in ["accepted", "filled", "new"]:
                issues.append(f"Trade {trade['symbol']} failed: {trade['status']}")

        # Rule: Daily investment must be $8-10 (allowing for rounding)
        total_invested = sum(t["amount"] for t in trades)
        if not (7 <= total_invested <= 11):
            issues.append(f"Invalid daily investment: ${total_invested:.2f} (expected $8-10)")

        # Rule: Must have Tier 1 (core) trade
        has_tier1 = any(t["tier"] == "T1_CORE" for t in trades)
        if not has_tier1:
            issues.append("Missing Tier 1 (core) trade")

        return len(issues) == 0, issues

    def verify_system_state(self) -> tuple[bool, dict[str, list[str]]]:
        """
        Verify system state quality using defined rules

        Returns:
            (success: bool, results: Dict[severity, List[issues]])
        """
        # Load system state
        with open(self.system_state_path) as f:
            state = json.load(f)

        results = {"critical": [], "warning": [], "info": []}

        # Run all verification rules
        for rule in self.verification_rules:
            try:
                if not rule.condition(state):
                    results[rule.severity].append(f"{rule.name}: {rule.message}")
            except Exception as e:
                results["critical"].append(f"{rule.name}: Error running rule - {str(e)}")

        # Success = no critical issues
        success = len(results["critical"]) == 0

        return success, results

    def verify_portfolio_claims(self, claimed_pl: float, claimed_equity: float) -> tuple[bool, str]:
        """
        Verify portfolio claims against system state
        Prevents anti-lying violations

        Returns:
            (accurate: bool, message: str)
        """
        with open(self.system_state_path) as f:
            state = json.load(f)

        actual_pl = state["account"]["total_pl"]
        actual_equity = state["account"]["current_equity"]

        # Allow 1% tolerance for rounding
        pl_matches = abs(claimed_pl - actual_pl) < (abs(actual_pl) * 0.01 + 1)
        equity_matches = abs(claimed_equity - actual_equity) < (actual_equity * 0.01 + 1)

        if pl_matches and equity_matches:
            return True, "Claims verified accurate"
        else:
            return (
                False,
                f"LYING DETECTED: Claimed P/L ${claimed_pl:.2f} vs actual ${actual_pl:.2f}, Claimed equity ${claimed_equity:.2f} vs actual ${actual_equity:.2f}",
            )

    def generate_verification_report(self) -> str:
        """
        Generate verification report following SDK pattern

        Returns formatted report of verification results
        """
        success, results = self.verify_system_state()

        report = ["=" * 60]
        report.append("OUTPUT VERIFICATION REPORT (Claude Agent SDK Loop)")
        report.append("=" * 60)
        report.append("")

        if success:
            report.append("✅ VERIFICATION PASSED - All critical rules satisfied")
        else:
            report.append("❌ VERIFICATION FAILED - Critical issues detected")

        report.append("")

        # Critical issues
        if results["critical"]:
            report.append("🚨 CRITICAL ISSUES:")
            for issue in results["critical"]:
                report.append(f"  ❌ {issue}")
            report.append("")

        # Warnings
        if results["warning"]:
            report.append("⚠️  WARNINGS:")
            for warning in results["warning"]:
                report.append(f"  ⚠️  {warning}")
            report.append("")

        # Info
        if results["info"]:
            report.append("ℹ️  INFO:")
            for info in results["info"]:
                report.append(f"  ℹ️  {info}")
            report.append("")

        report.append("=" * 60)

        return "\n".join(report)


# LLM-as-a-Judge Pattern (Future Enhancement)
class LLMJudge:
    """
    LLM-as-a-Judge for fuzzy rule evaluation
    Following SDK pattern: "Use LLMs to judge output quality based on fuzzy rules"

    Future: Use Claude to evaluate if trading results are "good enough"
    based on context like:
    - Market conditions
    - R&D phase expectations
    - Historical performance
    - Strategic goals
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def evaluate_trading_session(self, session_data: dict) -> dict:
        """
        Use LLM to evaluate if trading session met fuzzy quality criteria

        Fuzzy rules:
        - "Did we make smart trades given market conditions?"
        - "Is performance aligned with R&D phase expectations?"
        - "Are we on track to hit Month 1 goals?"

        Returns:
            {
                "quality_score": float (0-100),
                "reasoning": str,
                "recommendations": List[str]
            }
        """
        # TODO: Implement when MultiLLMAnalyzer is enabled
        # For now, return simple rule-based evaluation

        win_rate = session_data.get("win_rate", 0)
        pl = session_data.get("total_pl", 0)

        if pl > 0 and win_rate > 50:
            return {
                "quality_score": 90,
                "reasoning": "Profitable with good win rate",
                "recommendations": ["Continue current strategy"],
            }
        elif pl >= 0:
            return {
                "quality_score": 70,
                "reasoning": "Break-even, acceptable for R&D phase",
                "recommendations": ["Monitor win rate", "Collect more data"],
            }
        else:
            return {
                "quality_score": 50,
                "reasoning": "Losses acceptable in R&D but need improvement",
                "recommendations": ["Review losing trades", "Adjust filters"],
            }


if __name__ == "__main__":
    # Test verification system
    verifier = OutputVerifier()

    print(verifier.generate_verification_report())
    print()

    # Test portfolio claim verification
    accurate, message = verifier.verify_portfolio_claims(claimed_pl=13.96, claimed_equity=100013.96)
    print(f"Portfolio Claims: {message}")
