"""
Trade Execution Evals - Deterministic validation for trading agent behavior.

Based on OpenAI's eval skills framework:
- Outcome goals: Did the trade execute correctly?
- Process goals: Were all checks performed in order?
- Style goals: Does output follow conventions?
- Efficiency goals: No redundant operations?

These evals ensure Phil Town Rule #1 compliance before any trade executes.
"""

from dataclasses import dataclass
from decimal import Decimal

import pytest


@dataclass
class TradeProposal:
    """Represents a proposed trade for evaluation."""

    ticker: str
    strategy: str  # "iron_condor", "credit_spread", etc.
    legs: int  # Number of option legs
    short_put_delta: float
    short_call_delta: float
    dte: int  # Days to expiration
    max_risk: Decimal  # Maximum loss if trade goes wrong
    credit_received: Decimal
    stop_loss_multiplier: float  # e.g., 2.0 = 200% of credit
    account_value: Decimal


@dataclass
class EvalResult:
    """Result of an evaluation check."""

    passed: bool
    rule: str
    message: str
    severity: str = "error"  # "error", "warning", "info"


class TradeExecutionEvals:
    """Deterministic evaluation framework for trade proposals."""

    def __init__(self, account_value: Decimal = Decimal("30000")):
        self.account_value = account_value
        self.max_position_pct = Decimal("0.05")  # 5% max per trade
        self.allowed_tickers = ["SPY", "SPX", "XSP"]
        self.allowed_strategies = ["iron_condor"]
        self.min_dte = 30
        self.max_dte = 45
        self.target_delta_min = 0.15
        self.target_delta_max = 0.20
        self.required_stop_loss_multiplier = 2.0

    def eval_ticker(self, proposal: TradeProposal) -> EvalResult:
        """EVAL-001: Ticker must be SPY, SPX, or XSP."""
        passed = proposal.ticker in self.allowed_tickers
        return EvalResult(
            passed=passed,
            rule="EVAL-001",
            message=f"Ticker {proposal.ticker} {'allowed' if passed else 'NOT allowed. SPY/SPX/XSP ONLY.'}",
        )

    def eval_strategy(self, proposal: TradeProposal) -> EvalResult:
        """EVAL-002: Strategy must be iron condor."""
        passed = proposal.strategy in self.allowed_strategies
        return EvalResult(
            passed=passed,
            rule="EVAL-002",
            message=f"Strategy {proposal.strategy} {'allowed' if passed else 'NOT allowed. Iron condors ONLY.'}",
        )

    def eval_position_size(self, proposal: TradeProposal) -> EvalResult:
        """EVAL-003: Position size must be ≤5% of account."""
        max_allowed = self.account_value * self.max_position_pct
        passed = proposal.max_risk <= max_allowed
        return EvalResult(
            passed=passed,
            rule="EVAL-003",
            message=f"Max risk ${proposal.max_risk} {'≤' if passed else '>'} 5% limit (${max_allowed})",
        )

    def eval_iron_condor_legs(self, proposal: TradeProposal) -> EvalResult:
        """EVAL-004: Iron condor must have exactly 4 legs."""
        passed = proposal.legs == 4
        return EvalResult(
            passed=passed,
            rule="EVAL-004",
            message=f"Iron condor has {proposal.legs} legs {'(correct)' if passed else '(must be 4)'}",
        )

    def eval_delta_range(self, proposal: TradeProposal) -> EvalResult:
        """EVAL-005: Short strikes must be 15-20 delta."""
        put_ok = self.target_delta_min <= proposal.short_put_delta <= self.target_delta_max
        call_ok = self.target_delta_min <= proposal.short_call_delta <= self.target_delta_max
        passed = put_ok and call_ok
        return EvalResult(
            passed=passed,
            rule="EVAL-005",
            message=f"Deltas: put={proposal.short_put_delta}, call={proposal.short_call_delta} "
            f"{'in range' if passed else 'OUTSIDE 15-20 delta range'}",
        )

    def eval_dte(self, proposal: TradeProposal) -> EvalResult:
        """EVAL-006: DTE must be 30-45 days."""
        passed = self.min_dte <= proposal.dte <= self.max_dte
        return EvalResult(
            passed=passed,
            rule="EVAL-006",
            message=f"DTE {proposal.dte} {'in range' if passed else f'OUTSIDE {self.min_dte}-{self.max_dte} range'}",
        )

    def eval_stop_loss_defined(self, proposal: TradeProposal) -> EvalResult:
        """EVAL-007: Stop loss at 200% of credit must be defined."""
        passed = proposal.stop_loss_multiplier == self.required_stop_loss_multiplier
        return EvalResult(
            passed=passed,
            rule="EVAL-007",
            message=f"Stop loss multiplier {proposal.stop_loss_multiplier}x "
            f"{'correct' if passed else f'(must be {self.required_stop_loss_multiplier}x)'}",
        )

    def eval_risk_reward(self, proposal: TradeProposal) -> EvalResult:
        """EVAL-008: Risk/reward should be reasonable (≤2:1)."""
        if proposal.credit_received <= 0:
            return EvalResult(
                passed=False,
                rule="EVAL-008",
                message="Credit received must be positive",
            )
        ratio = float(proposal.max_risk / proposal.credit_received)
        passed = ratio <= 2.0
        return EvalResult(
            passed=passed,
            rule="EVAL-008",
            message=f"Risk/reward ratio {ratio:.2f}:1 {'acceptable' if passed else 'TOO HIGH (max 2:1)'}",
            severity="warning" if not passed else "info",
        )

    def run_all_evals(self, proposal: TradeProposal) -> list[EvalResult]:
        """Run all evaluations and return results."""
        return [
            self.eval_ticker(proposal),
            self.eval_strategy(proposal),
            self.eval_position_size(proposal),
            self.eval_iron_condor_legs(proposal),
            self.eval_delta_range(proposal),
            self.eval_dte(proposal),
            self.eval_stop_loss_defined(proposal),
            self.eval_risk_reward(proposal),
        ]

    def validate_trade(self, proposal: TradeProposal) -> tuple[bool, list[EvalResult]]:
        """
        Validate a trade proposal. Returns (all_passed, results).

        This is the gate before any trade executes.
        """
        results = self.run_all_evals(proposal)
        errors = [r for r in results if not r.passed and r.severity == "error"]
        return len(errors) == 0, results


# ============================================================================
# PYTEST TEST CASES
# ============================================================================


class TestTradeExecutionEvals:
    """Test suite for trade execution evals."""

    @pytest.fixture
    def evals(self):
        return TradeExecutionEvals(account_value=Decimal("30000"))

    @pytest.fixture
    def valid_proposal(self):
        """A valid iron condor proposal that should pass all evals."""
        return TradeProposal(
            ticker="SPY",
            strategy="iron_condor",
            legs=4,
            short_put_delta=0.15,
            short_call_delta=0.16,
            dte=35,
            max_risk=Decimal("500"),
            credit_received=Decimal("300"),
            stop_loss_multiplier=2.0,
            account_value=Decimal("30000"),
        )

    def test_valid_proposal_passes_all(self, evals, valid_proposal):
        """A properly structured iron condor should pass all evals."""
        passed, results = evals.validate_trade(valid_proposal)
        assert passed, f"Valid proposal failed: {[r for r in results if not r.passed]}"

    def test_wrong_ticker_fails(self, evals, valid_proposal):
        """EVAL-001: Non-SPY ticker must fail."""
        valid_proposal.ticker = "SOFI"
        result = evals.eval_ticker(valid_proposal)
        assert not result.passed
        assert "NOT allowed" in result.message

    def test_wrong_strategy_fails(self, evals, valid_proposal):
        """EVAL-002: Non-iron-condor strategy must fail."""
        valid_proposal.strategy = "credit_spread"
        result = evals.eval_strategy(valid_proposal)
        assert not result.passed

    def test_oversized_position_fails(self, evals, valid_proposal):
        """EVAL-003: Position >5% of account must fail."""
        valid_proposal.max_risk = Decimal("2000")  # >$1500 limit
        result = evals.eval_position_size(valid_proposal)
        assert not result.passed

    def test_wrong_leg_count_fails(self, evals, valid_proposal):
        """EVAL-004: Iron condor without 4 legs must fail."""
        valid_proposal.legs = 2  # Credit spread, not iron condor
        result = evals.eval_iron_condor_legs(valid_proposal)
        assert not result.passed

    def test_delta_too_high_fails(self, evals, valid_proposal):
        """EVAL-005: Delta outside 15-20 range must fail."""
        valid_proposal.short_put_delta = 0.30  # Too aggressive
        result = evals.eval_delta_range(valid_proposal)
        assert not result.passed

    def test_dte_too_short_fails(self, evals, valid_proposal):
        """EVAL-006: DTE <30 must fail."""
        valid_proposal.dte = 14
        result = evals.eval_dte(valid_proposal)
        assert not result.passed

    def test_missing_stop_loss_fails(self, evals, valid_proposal):
        """EVAL-007: Stop loss not at 200% must fail."""
        valid_proposal.stop_loss_multiplier = 1.5
        result = evals.eval_stop_loss_defined(valid_proposal)
        assert not result.passed

    def test_bad_risk_reward_warns(self, evals, valid_proposal):
        """EVAL-008: Risk/reward >2:1 should warn."""
        valid_proposal.max_risk = Decimal("1000")
        valid_proposal.credit_received = Decimal("200")  # 5:1 ratio
        result = evals.eval_risk_reward(valid_proposal)
        assert not result.passed
        assert result.severity == "warning"

    def test_full_validation_blocks_bad_trade(self, evals, valid_proposal):
        """Integration test: Bad trade should be blocked."""
        valid_proposal.ticker = "TSLA"
        valid_proposal.max_risk = Decimal("5000")
        passed, results = evals.validate_trade(valid_proposal)
        assert not passed
        failed = [r for r in results if not r.passed]
        assert len(failed) >= 2  # At least ticker and position size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
