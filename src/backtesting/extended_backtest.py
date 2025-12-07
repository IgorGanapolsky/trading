"""
Extended Backtesting Module.

This module provides comprehensive strategy validation by combining
multiple validation techniques:
    - Basic backtest metrics
    - Monte Carlo simulation
    - Walk-forward analysis
    - Transaction cost modeling
    - Regime-aware analysis

This is the one-stop validation module for production readiness.

Author: Trading System
Created: 2025-12-04
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from src.backtesting.backtest_results import BacktestResults
from src.backtesting.monte_carlo import MonteCarloResult, MonteCarloSimulator
from src.backtesting.walk_forward_enhanced import (
    EnhancedWalkForwardResults,
    EnhancedWalkForwardValidator,
)
from src.core.regime_detection import RegimeDetector, RegimeState
from src.core.transaction_costs import AssetClass, TransactionCostModel

logger = logging.getLogger(__name__)


@dataclass
class ValidationCriteria:
    """Criteria for strategy validation."""

    # Monte Carlo criteria
    min_profit_probability: float = 0.6
    max_ruin_probability: float = 0.05
    min_median_sharpe: float = 0.5

    # Walk-forward criteria
    min_efficiency_ratio: float = 0.5
    max_overfitting_score: float = 0.5
    min_fold_consistency: float = 0.5

    # Cost-adjusted criteria
    min_cost_adjusted_sharpe: float = 0.3
    max_cost_drag_pct: float = 30.0  # Max % of returns lost to costs

    # Basic criteria
    min_sharpe: float = 1.0
    max_drawdown: float = 0.20
    min_win_rate: float = 0.45
    min_trades: int = 50


@dataclass
class ExtendedValidationResults:
    """Comprehensive validation results."""

    # Basic backtest
    backtest_results: BacktestResults | None

    # Monte Carlo
    monte_carlo_results: MonteCarloResult | None
    monte_carlo_valid: bool
    monte_carlo_failures: list[str]

    # Walk-forward
    walk_forward_results: EnhancedWalkForwardResults | None
    walk_forward_valid: bool
    walk_forward_failures: list[str]

    # Cost analysis
    gross_return: float
    net_return: float  # After costs
    total_costs: float
    cost_drag_pct: float
    cost_adjusted_sharpe: float

    # Regime analysis
    regime_state: RegimeState | None
    regime_adjusted_score: float

    # Overall assessment
    overall_score: float  # 0-100
    is_valid_for_live_trading: bool
    validation_summary: str
    all_failures: list[str]
    recommendations: list[str]


class ExtendedBacktester:
    """
    Comprehensive strategy validation engine.

    Combines multiple validation techniques to provide a complete
    assessment of strategy viability for live trading.
    """

    def __init__(
        self,
        criteria: ValidationCriteria | None = None,
        monte_carlo_sims: int = 10000,
        walk_forward_train: int = 252,
        walk_forward_test: int = 63,
        initial_capital: float = 100000.0,
    ):
        """
        Initialize extended backtester.

        Args:
            criteria: Validation criteria to use
            monte_carlo_sims: Number of Monte Carlo simulations
            walk_forward_train: Walk-forward training window (days)
            walk_forward_test: Walk-forward test window (days)
            initial_capital: Starting capital for backtests
        """
        self.criteria = criteria or ValidationCriteria()
        self.monte_carlo_sims = monte_carlo_sims
        self.walk_forward_train = walk_forward_train
        self.walk_forward_test = walk_forward_test
        self.initial_capital = initial_capital

        # Initialize components
        self.monte_carlo = MonteCarloSimulator(num_simulations=monte_carlo_sims)
        self.walk_forward = EnhancedWalkForwardValidator(
            train_window=walk_forward_train,
            test_window=walk_forward_test,
        )
        self.cost_model = TransactionCostModel(AssetClass.US_EQUITY)
        self.regime_detector = RegimeDetector()

        logger.info("Initialized extended backtester")

    def validate_strategy(
        self,
        strategy: Any,
        data: pd.DataFrame,
        param_grid: dict[str, list[Any]] | None = None,
        strategy_factory: Callable | None = None,
        run_monte_carlo: bool = True,
        run_walk_forward: bool = True,
        run_cost_analysis: bool = True,
        run_regime_analysis: bool = True,
    ) -> ExtendedValidationResults:
        """
        Run comprehensive strategy validation.

        Args:
            strategy: Strategy instance to validate
            data: Historical price data with datetime index
            param_grid: Parameter grid for walk-forward optimization
            strategy_factory: Factory function for creating strategy instances
            run_monte_carlo: Whether to run Monte Carlo simulation
            run_walk_forward: Whether to run walk-forward analysis
            run_cost_analysis: Whether to run cost analysis
            run_regime_analysis: Whether to run regime analysis

        Returns:
            ExtendedValidationResults with comprehensive assessment
        """
        logger.info("Starting comprehensive strategy validation")

        all_failures: list[str] = []
        recommendations: list[str] = []

        # 1. Run basic backtest
        backtest_results = self._run_basic_backtest(strategy, data)

        if backtest_results is None:
            return self._create_failed_result(
                "Basic backtest failed - cannot proceed with validation"
            )

        # Validate basic metrics
        basic_failures = self._validate_basic_metrics(backtest_results)
        all_failures.extend(basic_failures)

        # 2. Run Monte Carlo simulation
        mc_results = None
        mc_valid = False
        mc_failures: list[str] = []

        if run_monte_carlo and backtest_results.trades:
            mc_results, mc_valid, mc_failures = self._run_monte_carlo(backtest_results.trades)
            all_failures.extend(mc_failures)

            if not mc_valid:
                recommendations.append("Monte Carlo failed: Consider reviewing trade quality")

        # 3. Run walk-forward analysis
        wf_results = None
        wf_valid = False
        wf_failures: list[str] = []

        if run_walk_forward and strategy_factory and param_grid:
            wf_results, wf_valid, wf_failures = self._run_walk_forward(
                data, strategy_factory, param_grid
            )
            all_failures.extend(wf_failures)

            if not wf_valid:
                recommendations.append("Walk-forward failed: Strategy may be overfit")

        # 4. Run cost analysis
        gross_return = backtest_results.total_return
        net_return = gross_return
        total_costs = 0.0
        cost_drag = 0.0
        cost_adjusted_sharpe = backtest_results.sharpe_ratio

        if run_cost_analysis and backtest_results.trades:
            (
                net_return,
                total_costs,
                cost_drag,
                cost_adjusted_sharpe,
            ) = self._run_cost_analysis(backtest_results)

            if cost_drag > self.criteria.max_cost_drag_pct:
                all_failures.append(
                    f"Cost drag {cost_drag:.1f}% > {self.criteria.max_cost_drag_pct:.0f}%"
                )
                recommendations.append(
                    "High transaction costs: Consider fewer trades or larger positions"
                )

        # 5. Run regime analysis
        regime_state = None
        regime_score = 1.0

        if run_regime_analysis:
            if "Close" in data.columns:
                prices = data["Close"]
            elif "close" in data.columns:
                prices = data["close"]
            else:
                prices = data.iloc[:, 0]  # Use first column

            regime_state = self.regime_detector.detect_regime(prices)
            regime_score = regime_state.recommended_position_scale

            if regime_score < 0.5:
                recommendations.append(
                    f"Current regime ({regime_state.market_regime.value}) "
                    "suggests reduced position sizes"
                )

        # Calculate overall score
        overall_score = self._calculate_overall_score(
            backtest_results=backtest_results,
            mc_results=mc_results,
            wf_results=wf_results,
            cost_adjusted_sharpe=cost_adjusted_sharpe,
            regime_score=regime_score,
        )

        # Determine if valid for live trading
        is_valid = (
            len(all_failures) == 0
            and overall_score >= 60
            and (not run_monte_carlo or mc_valid)
            and (not run_walk_forward or wf_valid)
        )

        # Generate summary
        summary = self._generate_summary(is_valid, overall_score, len(all_failures))

        return ExtendedValidationResults(
            backtest_results=backtest_results,
            monte_carlo_results=mc_results,
            monte_carlo_valid=mc_valid,
            monte_carlo_failures=mc_failures,
            walk_forward_results=wf_results,
            walk_forward_valid=wf_valid,
            walk_forward_failures=wf_failures,
            gross_return=gross_return,
            net_return=net_return,
            total_costs=total_costs,
            cost_drag_pct=cost_drag,
            cost_adjusted_sharpe=cost_adjusted_sharpe,
            regime_state=regime_state,
            regime_adjusted_score=regime_score,
            overall_score=overall_score,
            is_valid_for_live_trading=is_valid,
            validation_summary=summary,
            all_failures=all_failures,
            recommendations=recommendations,
        )

    def _run_basic_backtest(
        self,
        strategy: Any,
        data: pd.DataFrame,
    ) -> BacktestResults | None:
        """Run basic backtest and return results."""
        try:
            from src.backtesting.backtest_engine import BacktestEngine

            start_date = data.index.min().strftime("%Y-%m-%d")
            end_date = data.index.max().strftime("%Y-%m-%d")

            engine = BacktestEngine(
                strategy=strategy,
                start_date=start_date,
                end_date=end_date,
                initial_capital=self.initial_capital,
            )

            return engine.run()

        except Exception as e:
            logger.error(f"Basic backtest failed: {e}")
            return None

    def _validate_basic_metrics(
        self,
        results: BacktestResults,
    ) -> list[str]:
        """Validate basic backtest metrics against criteria."""
        failures = []

        if results.sharpe_ratio < self.criteria.min_sharpe:
            failures.append(f"Sharpe {results.sharpe_ratio:.2f} < {self.criteria.min_sharpe:.1f}")

        if results.max_drawdown > self.criteria.max_drawdown:
            failures.append(
                f"Drawdown {results.max_drawdown:.1%} > {self.criteria.max_drawdown:.0%}"
            )

        if results.win_rate < self.criteria.min_win_rate:
            failures.append(f"Win rate {results.win_rate:.1%} < {self.criteria.min_win_rate:.0%}")

        if results.total_trades < self.criteria.min_trades:
            failures.append(
                f"Only {results.total_trades} trades < {self.criteria.min_trades} minimum"
            )

        return failures

    def _run_monte_carlo(
        self,
        trades: list[dict],
    ) -> tuple[MonteCarloResult | None, bool, list[str]]:
        """Run Monte Carlo simulation and validate."""
        try:
            results = self.monte_carlo.run_from_trades(
                trades=trades,
                initial_capital=self.initial_capital,
            )

            is_valid, failures = self.monte_carlo.is_statistically_significant(
                results,
                min_profit_probability=self.criteria.min_profit_probability,
                max_ruin_probability=self.criteria.max_ruin_probability,
                min_sharpe=self.criteria.min_median_sharpe,
            )

            return results, is_valid, failures

        except Exception as e:
            logger.error(f"Monte Carlo failed: {e}")
            return None, False, [f"Monte Carlo simulation failed: {str(e)}"]

    def _run_walk_forward(
        self,
        data: pd.DataFrame,
        strategy_factory: Callable,
        param_grid: dict[str, list[Any]],
    ) -> tuple[EnhancedWalkForwardResults | None, bool, list[str]]:
        """Run walk-forward analysis and validate."""
        try:
            results = self.walk_forward.run_with_optimization(
                data=data,
                strategy_factory=strategy_factory,
                param_grid=param_grid,
            )

            failures = []

            if results.mean_efficiency_ratio < self.criteria.min_efficiency_ratio:
                failures.append(
                    f"Efficiency ratio {results.mean_efficiency_ratio:.2f} "
                    f"< {self.criteria.min_efficiency_ratio:.1f}"
                )

            if results.overfitting_score > self.criteria.max_overfitting_score:
                failures.append(
                    f"Overfitting score {results.overfitting_score:.2f} "
                    f"> {self.criteria.max_overfitting_score:.1f}"
                )

            # Check fold consistency
            positive_folds = sum(
                1 for fd in results.fold_details if fd.out_of_sample_result.total_return > 0
            )
            consistency = positive_folds / len(results.fold_details) if results.fold_details else 0

            if consistency < self.criteria.min_fold_consistency:
                failures.append(
                    f"Fold consistency {consistency:.0%} < {self.criteria.min_fold_consistency:.0%}"
                )

            return results, len(failures) == 0, failures

        except Exception as e:
            logger.error(f"Walk-forward failed: {e}")
            return None, False, [f"Walk-forward analysis failed: {str(e)}"]

    def _run_cost_analysis(
        self,
        results: BacktestResults,
    ) -> tuple[float, float, float, float]:
        """Run transaction cost analysis."""
        if not results.trades:
            return results.total_return, 0.0, 0.0, results.sharpe_ratio

        # Adjust trades for costs
        adjusted_trades = self.cost_model.adjust_returns(results.trades)

        total_costs = sum(t.get("transaction_costs", 0) for t in adjusted_trades)
        gross_pnl = sum(t.get("original_pnl", 0) for t in adjusted_trades)
        net_pnl = sum(t.get("adjusted_pnl", 0) for t in adjusted_trades)

        # Calculate cost drag
        if gross_pnl != 0:
            cost_drag = (total_costs / abs(gross_pnl)) * 100
        else:
            cost_drag = 0.0

        # Calculate net return
        net_return = net_pnl / self.initial_capital * 100

        # Estimate cost-adjusted Sharpe (rough approximation)
        if results.sharpe_ratio > 0:
            cost_impact = cost_drag / 100
            cost_adjusted_sharpe = results.sharpe_ratio * (1 - cost_impact)
        else:
            cost_adjusted_sharpe = results.sharpe_ratio

        return net_return, total_costs, cost_drag, cost_adjusted_sharpe

    def _calculate_overall_score(
        self,
        backtest_results: BacktestResults,
        mc_results: MonteCarloResult | None,
        wf_results: EnhancedWalkForwardResults | None,
        cost_adjusted_sharpe: float,
        regime_score: float,
    ) -> float:
        """Calculate overall validation score (0-100)."""
        scores = []
        weights = []

        # Backtest score (weight: 25%)
        bt_score = min(
            100,
            max(
                0,
                (
                    min(1, backtest_results.sharpe_ratio / 2) * 40
                    + min(1, backtest_results.win_rate / 0.6) * 30
                    + max(0, 1 - backtest_results.max_drawdown / 0.3) * 30
                ),
            ),
        )
        scores.append(bt_score)
        weights.append(0.25)

        # Monte Carlo score (weight: 25%)
        if mc_results:
            mc_score = (
                (1 - mc_results.probability_of_loss) * 50
                + max(0, 1 - mc_results.probability_of_ruin * 10) * 30
                + max(0, 1 - mc_results.drawdown_95_upper / 0.5) * 20
            )
            scores.append(mc_score)
            weights.append(0.25)

        # Walk-forward score (weight: 25%)
        if wf_results:
            wf_score = (
                min(1, wf_results.mean_efficiency_ratio) * 40
                + max(0, 1 - wf_results.overfitting_score) * 40
                + wf_results.mean_param_stability * 20
            ) * 100
            scores.append(wf_score)
            weights.append(0.25)

        # Cost/regime score (weight: 25%)
        misc_score = (min(1, cost_adjusted_sharpe / 1.5) * 50 + regime_score * 50) * 100
        scores.append(misc_score)
        weights.append(0.25)

        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        # Weighted average
        overall = sum(s * w for s, w in zip(scores, normalized_weights))

        return min(100, max(0, overall))

    def _generate_summary(
        self,
        is_valid: bool,
        score: float,
        num_failures: int,
    ) -> str:
        """Generate validation summary string."""
        if is_valid:
            return f"PASS: Strategy validated for live trading (Score: {score:.0f}/100)"
        else:
            return (
                f"FAIL: Strategy not ready for live trading "
                f"(Score: {score:.0f}/100, {num_failures} issues)"
            )

    def _create_failed_result(self, reason: str) -> ExtendedValidationResults:
        """Create a failed validation result."""
        return ExtendedValidationResults(
            backtest_results=None,
            monte_carlo_results=None,
            monte_carlo_valid=False,
            monte_carlo_failures=[],
            walk_forward_results=None,
            walk_forward_valid=False,
            walk_forward_failures=[],
            gross_return=0.0,
            net_return=0.0,
            total_costs=0.0,
            cost_drag_pct=0.0,
            cost_adjusted_sharpe=0.0,
            regime_state=None,
            regime_adjusted_score=0.0,
            overall_score=0.0,
            is_valid_for_live_trading=False,
            validation_summary=f"FAIL: {reason}",
            all_failures=[reason],
            recommendations=["Fix the underlying issue and retry validation"],
        )

    def generate_report(self, results: ExtendedValidationResults) -> str:
        """Generate comprehensive validation report."""
        report = []
        report.append("=" * 80)
        report.append("EXTENDED STRATEGY VALIDATION REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        # Overall status
        report.append("\n" + "-" * 80)
        report.append("OVERALL ASSESSMENT")
        report.append("-" * 80)

        status = "[PASS]" if results.is_valid_for_live_trading else "[FAIL]"
        report.append(f"\nStatus: {status}")
        report.append(f"Score: {results.overall_score:.0f}/100")
        report.append(f"Summary: {results.validation_summary}")

        # Basic backtest
        if results.backtest_results:
            report.append("\n" + "-" * 80)
            report.append("BASIC BACKTEST METRICS")
            report.append("-" * 80)

            bt = results.backtest_results
            report.append(f"\n  Total Return: {bt.total_return:.2f}%")
            report.append(f"  Sharpe Ratio: {bt.sharpe_ratio:.2f}")
            report.append(f"  Max Drawdown: {bt.max_drawdown:.1%}")
            report.append(f"  Win Rate: {bt.win_rate:.1%}")
            report.append(f"  Total Trades: {bt.total_trades}")

        # Monte Carlo
        if results.monte_carlo_results:
            report.append("\n" + "-" * 80)
            report.append("MONTE CARLO SIMULATION")
            report.append("-" * 80)

            mc = results.monte_carlo_results
            mc_status = "[PASS]" if results.monte_carlo_valid else "[FAIL]"
            report.append(f"\n  Status: {mc_status}")
            report.append(f"  Simulations: {mc.num_simulations:,}")
            report.append(f"  Profit Probability: {(1 - mc.probability_of_loss):.1%}")
            report.append(f"  Ruin Probability: {mc.probability_of_ruin:.1%}")
            report.append(f"  Mean Return: {mc.total_return_mean:.1f}%")
            report.append(
                f"  95% CI: {mc.return_95_lower * 100:,.1f}% - {mc.return_95_upper * 100:,.1f}%"
            )

            if results.monte_carlo_failures:
                report.append("  Failures:")
                for f in results.monte_carlo_failures:
                    report.append(f"    - {f}")

        # Walk-forward
        if results.walk_forward_results:
            report.append("\n" + "-" * 80)
            report.append("WALK-FORWARD ANALYSIS")
            report.append("-" * 80)

            wf = results.walk_forward_results
            wf_status = "[PASS]" if results.walk_forward_valid else "[FAIL]"
            report.append(f"\n  Status: {wf_status}")
            report.append(f"  Folds: {len(wf.fold_details)}")
            report.append(f"  Efficiency Ratio: {wf.mean_efficiency_ratio:.2f}")
            report.append(f"  Overfitting Score: {wf.overfitting_score:.2f}")
            report.append(f"  Parameter Stability: {wf.mean_param_stability:.2f}")

            if results.walk_forward_failures:
                report.append("  Failures:")
                for f in results.walk_forward_failures:
                    report.append(f"    - {f}")

        # Cost analysis
        report.append("\n" + "-" * 80)
        report.append("TRANSACTION COST ANALYSIS")
        report.append("-" * 80)

        report.append(f"\n  Gross Return: {results.gross_return:.2f}%")
        report.append(f"  Net Return: {results.net_return:.2f}%")
        report.append(f"  Total Costs: ${results.total_costs:,.2f}")
        report.append(f"  Cost Drag: {results.cost_drag_pct:.1f}%")
        report.append(f"  Cost-Adjusted Sharpe: {results.cost_adjusted_sharpe:.2f}")

        # Regime analysis
        if results.regime_state:
            report.append("\n" + "-" * 80)
            report.append("MARKET REGIME ANALYSIS")
            report.append("-" * 80)

            rs = results.regime_state
            report.append(f"\n  Current Regime: {rs.market_regime.value}")
            report.append(f"  Volatility: {rs.volatility_regime.value}")
            report.append(f"  Trend: {rs.trend_regime.value}")
            report.append(f"  Recommended Position Scale: {rs.recommended_position_scale:.0%}")

        # All failures
        if results.all_failures:
            report.append("\n" + "-" * 80)
            report.append("ALL VALIDATION FAILURES")
            report.append("-" * 80)

            for i, f in enumerate(results.all_failures, 1):
                report.append(f"  {i}. {f}")

        # Recommendations
        if results.recommendations:
            report.append("\n" + "-" * 80)
            report.append("RECOMMENDATIONS")
            report.append("-" * 80)

            for i, r in enumerate(results.recommendations, 1):
                report.append(f"  {i}. {r}")

        report.append("\n" + "=" * 80)

        return "\n".join(report)


def validate_strategy(
    strategy: Any,
    data: pd.DataFrame,
    param_grid: dict[str, list[Any]] | None = None,
    strategy_factory: Callable | None = None,
) -> ExtendedValidationResults:
    """
    Convenience function to validate a strategy.

    Args:
        strategy: Strategy instance to validate
        data: Historical price data
        param_grid: Optional parameter grid for walk-forward
        strategy_factory: Optional factory for creating strategy instances

    Returns:
        ExtendedValidationResults

    Example:
        >>> from src.strategies.momentum import MomentumStrategy
        >>> import yfinance as yf
        >>> data = yf.download("SPY", start="2019-01-01", end="2024-01-01")
        >>> strategy = MomentumStrategy()
        >>> results = validate_strategy(strategy, data)
        >>> print(f"Valid: {results.is_valid_for_live_trading}")
        >>> print(f"Score: {results.overall_score}/100")
    """
    validator = ExtendedBacktester()
    return validator.validate_strategy(
        strategy=strategy,
        data=data,
        param_grid=param_grid,
        strategy_factory=strategy_factory,
        run_walk_forward=param_grid is not None and strategy_factory is not None,
    )
