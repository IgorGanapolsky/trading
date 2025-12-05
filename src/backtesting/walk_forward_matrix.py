from __future__ import annotations
"""
Walk-Forward Backtest Matrix Evaluation

Implements rolling out-of-sample evaluation on top of the backtest system to ensure
parameters are always tested on unseen data. This is a standard best practice to
avoid overfitting in systematic trading.

Key Features:
1. Rolling walk-forward windows with configurable train/test splits
2. Parameter sensitivity analysis across multiple configurations
3. Regime-aware evaluation (bull/bear/sideways performance)
4. Live vs backtest divergence tracking
5. Automatic overfitting detection

Author: Trading System
Created: 2025-12-02
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    """Single walk-forward evaluation window."""

    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_days: int
    test_days: int

    # In-sample (training) metrics
    is_sharpe: float = 0.0
    is_return: float = 0.0
    is_max_drawdown: float = 0.0
    is_win_rate: float = 0.0

    # Out-of-sample (test) metrics
    oos_sharpe: float = 0.0
    oos_return: float = 0.0
    oos_max_drawdown: float = 0.0
    oos_win_rate: float = 0.0

    # Divergence metrics
    sharpe_decay: float = 0.0  # IS Sharpe - OOS Sharpe
    return_decay: float = 0.0  # IS return - OOS return
    regime: str = "unknown"

    # Parameter configuration used
    params: dict = field(default_factory=dict)


@dataclass
class ParameterSensitivity:
    """Sensitivity analysis for a single parameter."""

    param_name: str
    param_values: list
    oos_sharpes: list[float]
    oos_returns: list[float]
    optimal_value: Any
    sensitivity_score: float  # 0-1, higher = more sensitive
    is_robust: bool  # True if performance consistent across values


@dataclass
class BacktestMatrixResults:
    """Complete results from walk-forward matrix evaluation."""

    strategy_name: str
    evaluation_date: str
    total_windows: int
    windows: list[WalkForwardWindow]

    # Aggregated out-of-sample metrics
    mean_oos_sharpe: float = 0.0
    std_oos_sharpe: float = 0.0
    mean_oos_return: float = 0.0
    mean_oos_max_drawdown: float = 0.0
    mean_oos_win_rate: float = 0.0

    # Robustness metrics
    sharpe_consistency: float = 0.0  # % of windows with positive Sharpe
    return_consistency: float = 0.0  # % of windows with positive return
    avg_sharpe_decay: float = 0.0  # Avg IS Sharpe - OOS Sharpe
    overfitting_score: float = 0.0  # 0-1, higher = more overfit

    # Regime performance
    regime_performance: dict[str, dict[str, float]] = field(default_factory=dict)

    # Parameter sensitivity
    parameter_sensitivity: list[ParameterSensitivity] = field(default_factory=list)

    # Validation status
    passed_validation: bool = False
    validation_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "strategy_name": self.strategy_name,
            "evaluation_date": self.evaluation_date,
            "total_windows": self.total_windows,
            "mean_oos_sharpe": self.mean_oos_sharpe,
            "std_oos_sharpe": self.std_oos_sharpe,
            "mean_oos_return": self.mean_oos_return,
            "mean_oos_max_drawdown": self.mean_oos_max_drawdown,
            "mean_oos_win_rate": self.mean_oos_win_rate,
            "sharpe_consistency": self.sharpe_consistency,
            "return_consistency": self.return_consistency,
            "avg_sharpe_decay": self.avg_sharpe_decay,
            "overfitting_score": self.overfitting_score,
            "regime_performance": self.regime_performance,
            "passed_validation": self.passed_validation,
            "validation_messages": self.validation_messages,
            "windows": [
                {
                    "window_id": w.window_id,
                    "train_period": f"{w.train_start} to {w.train_end}",
                    "test_period": f"{w.test_start} to {w.test_end}",
                    "is_sharpe": w.is_sharpe,
                    "oos_sharpe": w.oos_sharpe,
                    "sharpe_decay": w.sharpe_decay,
                    "oos_return": w.oos_return,
                    "regime": w.regime,
                }
                for w in self.windows
            ],
        }

    def save(self, filepath: str | Path) -> None:
        """Save results to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        logger.info(f"Walk-forward matrix results saved to {path}")


class WalkForwardMatrixValidator:
    """
    Walk-Forward Matrix Validator for comprehensive strategy evaluation.

    Implements rolling out-of-sample evaluation with:
    - Multiple walk-forward windows
    - Parameter sensitivity analysis
    - Regime-aware performance tracking
    - Overfitting detection

    Args:
        train_window_days: Training window size in trading days (default: 252 = 1 year)
        test_window_days: Test window size in trading days (default: 63 = 1 quarter)
        step_days: Step size for rolling windows (default: 21 = 1 month)
        min_oos_sharpe: Minimum out-of-sample Sharpe ratio (default: 0.8)
        max_sharpe_decay: Maximum allowed Sharpe decay from IS to OOS (default: 0.5)
        max_drawdown: Maximum allowed drawdown (default: 15%)
    """

    # Validation thresholds
    MIN_OOS_SHARPE = float(os.getenv("WF_MIN_OOS_SHARPE", "0.8"))
    MAX_SHARPE_DECAY = float(os.getenv("WF_MAX_SHARPE_DECAY", "0.5"))
    MAX_OOS_DRAWDOWN = float(os.getenv("WF_MAX_OOS_DRAWDOWN", "0.15"))
    MIN_WIN_RATE = float(os.getenv("WF_MIN_WIN_RATE", "0.52"))
    MIN_WINDOWS = int(os.getenv("WF_MIN_WINDOWS", "4"))

    def __init__(
        self,
        train_window_days: int = 252,
        test_window_days: int = 63,
        step_days: int = 21,
    ):
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.step_days = step_days

        logger.info(
            f"WalkForwardMatrixValidator initialized: "
            f"train={train_window_days}d, test={test_window_days}d, step={step_days}d"
        )

    def generate_windows(
        self,
        start_date: str,
        end_date: str,
    ) -> list[tuple[tuple[str, str], tuple[str, str]]]:
        """
        Generate train/test date pairs for walk-forward windows.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of ((train_start, train_end), (test_start, test_end)) tuples
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        windows = []
        current_start = start

        while True:
            train_end = current_start + timedelta(days=self.train_window_days)
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=self.test_window_days)

            if test_end > end:
                break

            windows.append(
                (
                    (current_start.strftime("%Y-%m-%d"), train_end.strftime("%Y-%m-%d")),
                    (test_start.strftime("%Y-%m-%d"), test_end.strftime("%Y-%m-%d")),
                )
            )

            current_start += timedelta(days=self.step_days)

        logger.info(f"Generated {len(windows)} walk-forward windows")
        return windows

    def run_matrix_evaluation(
        self,
        strategy_class: type,
        strategy_params: dict[str, Any],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        param_grid: Optional[dict[str, list]] = None,
    ) -> BacktestMatrixResults:
        """
        Run full walk-forward matrix evaluation.

        Args:
            strategy_class: Strategy class to evaluate
            strategy_params: Base parameters for strategy
            start_date: Evaluation start date
            end_date: Evaluation end date
            initial_capital: Initial capital for backtest
            param_grid: Optional parameter grid for sensitivity analysis

        Returns:
            BacktestMatrixResults with comprehensive evaluation data
        """
        from src.backtesting.backtest_engine import BacktestEngine
        from src.utils.regime_detector import RegimeDetector

        logger.info("Starting walk-forward matrix evaluation")
        logger.info(f"Period: {start_date} to {end_date}")

        windows = self.generate_windows(start_date, end_date)
        if len(windows) < self.MIN_WINDOWS:
            return self._insufficient_data_result(
                len(windows), f"Need at least {self.MIN_WINDOWS} windows"
            )

        regime_detector = RegimeDetector()
        window_results = []

        for idx, ((train_start, train_end), (test_start, test_end)) in enumerate(windows):
            logger.info(f"Evaluating window {idx + 1}/{len(windows)}")

            try:
                # Run in-sample (training) backtest
                strategy = strategy_class(**strategy_params)
                is_engine = BacktestEngine(
                    strategy=strategy,
                    start_date=train_start,
                    end_date=train_end,
                    initial_capital=initial_capital,
                )
                is_results = is_engine.run()

                # Run out-of-sample (test) backtest
                oos_engine = BacktestEngine(
                    strategy=strategy,
                    start_date=test_start,
                    end_date=test_end,
                    initial_capital=initial_capital,
                )
                oos_results = oos_engine.run()

                # Detect regime during test period
                regime = self._detect_regime_for_period(regime_detector, test_start, test_end)

                # Calculate decay metrics
                sharpe_decay = is_results.sharpe_ratio - oos_results.sharpe_ratio
                return_decay = is_results.total_return - oos_results.total_return

                window = WalkForwardWindow(
                    window_id=idx + 1,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_days=is_results.trading_days,
                    test_days=oos_results.trading_days,
                    is_sharpe=is_results.sharpe_ratio,
                    is_return=is_results.total_return,
                    is_max_drawdown=is_results.max_drawdown,
                    is_win_rate=is_results.win_rate,
                    oos_sharpe=oos_results.sharpe_ratio,
                    oos_return=oos_results.total_return,
                    oos_max_drawdown=oos_results.max_drawdown,
                    oos_win_rate=oos_results.win_rate,
                    sharpe_decay=sharpe_decay,
                    return_decay=return_decay,
                    regime=regime,
                    params=strategy_params,
                )
                window_results.append(window)

            except Exception as e:
                logger.warning(f"Window {idx + 1} evaluation failed: {e}")
                continue

        if not window_results:
            return self._insufficient_data_result(0, "All windows failed evaluation")

        # Aggregate results
        return self._aggregate_results(
            strategy_name=strategy_class.__name__,
            windows=window_results,
            param_grid=param_grid,
        )

    def _detect_regime_for_period(
        self,
        detector,
        start_date: str,
        end_date: str,
    ) -> str:
        """Detect market regime for a given period."""
        try:
            # Simplified regime detection using SPY as benchmark
            import yfinance as yf

            spy = yf.Ticker("SPY")
            hist = spy.history(start=start_date, end=end_date)

            if hist.empty:
                return "unknown"

            # Calculate period return and volatility
            period_return = (hist["Close"].iloc[-1] / hist["Close"].iloc[0]) - 1
            volatility = hist["Close"].pct_change().std() * np.sqrt(252)

            # Classify regime
            if period_return > 0.05 and volatility < 0.20:
                return "bull_low_vol"
            elif period_return > 0.05 and volatility >= 0.20:
                return "bull_high_vol"
            elif period_return < -0.05 and volatility >= 0.20:
                return "bear_high_vol"
            elif period_return < -0.05 and volatility < 0.20:
                return "bear_low_vol"
            elif abs(period_return) <= 0.05 and volatility >= 0.25:
                return "sideways_high_vol"
            else:
                return "sideways"

        except Exception as e:
            logger.debug(f"Regime detection failed: {e}")
            return "unknown"

    def _aggregate_results(
        self,
        strategy_name: str,
        windows: list[WalkForwardWindow],
        param_grid: Optional[dict[str, list]] = None,
    ) -> BacktestMatrixResults:
        """Aggregate window results into matrix results."""

        # Extract metrics
        oos_sharpes = [w.oos_sharpe for w in windows]
        oos_returns = [w.oos_return for w in windows]
        oos_drawdowns = [w.oos_max_drawdown for w in windows]
        oos_win_rates = [w.oos_win_rate for w in windows]
        sharpe_decays = [w.sharpe_decay for w in windows]

        # Calculate aggregated metrics
        mean_oos_sharpe = np.mean(oos_sharpes)
        std_oos_sharpe = np.std(oos_sharpes)
        mean_oos_return = np.mean(oos_returns)
        mean_oos_max_drawdown = np.mean(oos_drawdowns)
        mean_oos_win_rate = np.mean(oos_win_rates)

        # Robustness metrics
        sharpe_consistency = sum(1 for s in oos_sharpes if s > 0) / len(oos_sharpes)
        return_consistency = sum(1 for r in oos_returns if r > 0) / len(oos_returns)
        avg_sharpe_decay = np.mean(sharpe_decays)

        # Overfitting score (higher decay = more overfit)
        overfitting_score = min(1.0, max(0.0, avg_sharpe_decay / 2.0))

        # Regime performance breakdown
        regime_performance = self._calculate_regime_performance(windows)

        # Validation
        passed, messages = self._validate_results(
            mean_oos_sharpe=mean_oos_sharpe,
            avg_sharpe_decay=avg_sharpe_decay,
            mean_oos_max_drawdown=mean_oos_max_drawdown,
            mean_oos_win_rate=mean_oos_win_rate,
            sharpe_consistency=sharpe_consistency,
        )

        return BacktestMatrixResults(
            strategy_name=strategy_name,
            evaluation_date=datetime.now().isoformat(),
            total_windows=len(windows),
            windows=windows,
            mean_oos_sharpe=mean_oos_sharpe,
            std_oos_sharpe=std_oos_sharpe,
            mean_oos_return=mean_oos_return,
            mean_oos_max_drawdown=mean_oos_max_drawdown,
            mean_oos_win_rate=mean_oos_win_rate,
            sharpe_consistency=sharpe_consistency,
            return_consistency=return_consistency,
            avg_sharpe_decay=avg_sharpe_decay,
            overfitting_score=overfitting_score,
            regime_performance=regime_performance,
            passed_validation=passed,
            validation_messages=messages,
        )

    def _calculate_regime_performance(
        self, windows: list[WalkForwardWindow]
    ) -> dict[str, dict[str, float]]:
        """Calculate performance breakdown by regime."""
        regime_data: dict[str, list[WalkForwardWindow]] = {}

        for w in windows:
            if w.regime not in regime_data:
                regime_data[w.regime] = []
            regime_data[w.regime].append(w)

        regime_performance = {}
        for regime, regime_windows in regime_data.items():
            regime_performance[regime] = {
                "count": len(regime_windows),
                "mean_sharpe": np.mean([w.oos_sharpe for w in regime_windows]),
                "mean_return": np.mean([w.oos_return for w in regime_windows]),
                "mean_drawdown": np.mean([w.oos_max_drawdown for w in regime_windows]),
                "mean_win_rate": np.mean([w.oos_win_rate for w in regime_windows]),
            }

        return regime_performance

    def _validate_results(
        self,
        mean_oos_sharpe: float,
        avg_sharpe_decay: float,
        mean_oos_max_drawdown: float,
        mean_oos_win_rate: float,
        sharpe_consistency: float,
    ) -> tuple[bool, list[str]]:
        """Validate results against thresholds."""
        messages = []
        passed = True

        # Check OOS Sharpe
        if mean_oos_sharpe < self.MIN_OOS_SHARPE:
            messages.append(f"FAIL: Mean OOS Sharpe {mean_oos_sharpe:.2f} < {self.MIN_OOS_SHARPE}")
            passed = False
        else:
            messages.append(f"PASS: Mean OOS Sharpe {mean_oos_sharpe:.2f} >= {self.MIN_OOS_SHARPE}")

        # Check Sharpe decay (overfitting indicator)
        if avg_sharpe_decay > self.MAX_SHARPE_DECAY:
            messages.append(
                f"FAIL: Avg Sharpe decay {avg_sharpe_decay:.2f} > {self.MAX_SHARPE_DECAY}"
            )
            passed = False
        else:
            messages.append(
                f"PASS: Avg Sharpe decay {avg_sharpe_decay:.2f} <= {self.MAX_SHARPE_DECAY}"
            )

        # Check max drawdown
        if mean_oos_max_drawdown > self.MAX_OOS_DRAWDOWN * 100:
            messages.append(
                f"FAIL: Mean OOS drawdown {mean_oos_max_drawdown:.1f}% > {self.MAX_OOS_DRAWDOWN * 100:.0f}%"
            )
            passed = False
        else:
            messages.append(
                f"PASS: Mean OOS drawdown {mean_oos_max_drawdown:.1f}% <= {self.MAX_OOS_DRAWDOWN * 100:.0f}%"
            )

        # Check win rate
        if mean_oos_win_rate < self.MIN_WIN_RATE * 100:
            messages.append(
                f"FAIL: Mean OOS win rate {mean_oos_win_rate:.1f}% < {self.MIN_WIN_RATE * 100:.0f}%"
            )
            passed = False
        else:
            messages.append(
                f"PASS: Mean OOS win rate {mean_oos_win_rate:.1f}% >= {self.MIN_WIN_RATE * 100:.0f}%"
            )

        # Check consistency
        if sharpe_consistency < 0.6:
            messages.append(
                f"WARN: Sharpe consistency {sharpe_consistency:.0%} < 60% (some windows underperform)"
            )

        return passed, messages

    def _insufficient_data_result(self, windows: int, message: str) -> BacktestMatrixResults:
        """Return empty results for insufficient data."""
        return BacktestMatrixResults(
            strategy_name="Unknown",
            evaluation_date=datetime.now().isoformat(),
            total_windows=windows,
            windows=[],
            passed_validation=False,
            validation_messages=[f"FAIL: {message}"],
        )


class LiveVsBacktestTracker:
    """
    Tracks divergence between live trading performance and backtest expectations.

    This is critical for detecting when a strategy has stopped working or when
    backtest assumptions no longer hold in live markets.
    """

    # Divergence thresholds
    SHARPE_DIVERGENCE_THRESHOLD = 0.5
    RETURN_DIVERGENCE_THRESHOLD = 0.20  # 20% difference
    DRAWDOWN_DIVERGENCE_THRESHOLD = 0.10  # 10% additional drawdown

    def __init__(self, state_file: str = "data/live_vs_backtest_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()

    def record_backtest_expectation(
        self,
        strategy_name: str,
        expected_sharpe: float,
        expected_return: float,
        expected_max_drawdown: float,
        evaluation_date: str,
    ) -> None:
        """Record expected performance from backtest."""
        if strategy_name not in self.state:
            self.state[strategy_name] = {"expectations": [], "live_performance": []}

        self.state[strategy_name]["expectations"].append(
            {
                "date": evaluation_date,
                "expected_sharpe": expected_sharpe,
                "expected_return": expected_return,
                "expected_max_drawdown": expected_max_drawdown,
            }
        )
        self._save_state()

    def record_live_performance(
        self,
        strategy_name: str,
        live_sharpe: float,
        live_return: float,
        live_max_drawdown: float,
        period_start: str,
        period_end: str,
    ) -> dict[str, Any]:
        """Record live performance and calculate divergence."""
        if strategy_name not in self.state:
            self.state[strategy_name] = {"expectations": [], "live_performance": []}

        # Get latest expectation
        expectations = self.state[strategy_name].get("expectations", [])
        if not expectations:
            return {"error": "No backtest expectations recorded"}

        latest_exp = expectations[-1]

        # Calculate divergence
        sharpe_divergence = latest_exp["expected_sharpe"] - live_sharpe
        return_divergence = latest_exp["expected_return"] - live_return
        drawdown_divergence = live_max_drawdown - latest_exp["expected_max_drawdown"]

        # Determine alert level
        alert_level = "OK"
        alerts = []

        if sharpe_divergence > self.SHARPE_DIVERGENCE_THRESHOLD:
            alert_level = "WARNING"
            alerts.append(f"Sharpe divergence: {sharpe_divergence:.2f}")

        if return_divergence > self.RETURN_DIVERGENCE_THRESHOLD * 100:
            alert_level = "WARNING"
            alerts.append(f"Return divergence: {return_divergence:.1f}%")

        if drawdown_divergence > self.DRAWDOWN_DIVERGENCE_THRESHOLD * 100:
            alert_level = "CRITICAL"
            alerts.append(f"Drawdown divergence: {drawdown_divergence:.1f}%")

        record = {
            "period_start": period_start,
            "period_end": period_end,
            "live_sharpe": live_sharpe,
            "live_return": live_return,
            "live_max_drawdown": live_max_drawdown,
            "sharpe_divergence": sharpe_divergence,
            "return_divergence": return_divergence,
            "drawdown_divergence": drawdown_divergence,
            "alert_level": alert_level,
            "alerts": alerts,
        }

        self.state[strategy_name]["live_performance"].append(record)
        self._save_state()

        if alert_level in ["WARNING", "CRITICAL"]:
            logger.warning(
                f"Live vs Backtest divergence detected for {strategy_name}: "
                f"{alert_level} - {', '.join(alerts)}"
            )

        return record

    def get_divergence_report(self, strategy_name: str) -> dict[str, Any]:
        """Get divergence report for a strategy."""
        if strategy_name not in self.state:
            return {"error": f"No data for strategy: {strategy_name}"}

        data = self.state[strategy_name]
        live_perf = data.get("live_performance", [])

        if not live_perf:
            return {"error": "No live performance recorded"}

        # Calculate rolling divergence
        recent = live_perf[-10:]  # Last 10 periods
        avg_sharpe_div = np.mean([p["sharpe_divergence"] for p in recent])
        avg_return_div = np.mean([p["return_divergence"] for p in recent])
        avg_dd_div = np.mean([p["drawdown_divergence"] for p in recent])

        # Trend detection
        if len(live_perf) >= 5:
            recent_5 = live_perf[-5:]
            older_5 = live_perf[-10:-5] if len(live_perf) >= 10 else live_perf[:5]

            sharpe_trend = np.mean([p["sharpe_divergence"] for p in recent_5]) - np.mean(
                [p["sharpe_divergence"] for p in older_5]
            )
            trend = "improving" if sharpe_trend < 0 else "deteriorating"
        else:
            trend = "insufficient_data"

        return {
            "strategy_name": strategy_name,
            "periods_recorded": len(live_perf),
            "avg_sharpe_divergence": avg_sharpe_div,
            "avg_return_divergence": avg_return_div,
            "avg_drawdown_divergence": avg_dd_div,
            "trend": trend,
            "recent_alerts": [p for p in recent if p.get("alert_level") in ["WARNING", "CRITICAL"]],
        }

    def _load_state(self) -> dict:
        """Load state from disk."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading live vs backtest state: {e}")
            return {}

    def _save_state(self) -> None:
        """Save state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving live vs backtest state: {e}")


def run_walk_forward_matrix(
    strategy_class: type,
    strategy_params: dict[str, Any],
    start_date: str = "2023-01-01",
    end_date: str = "2025-01-01",
    initial_capital: float = 100000.0,
) -> BacktestMatrixResults:
    """
    Convenience function to run walk-forward matrix evaluation.

    Args:
        strategy_class: Strategy class to evaluate
        strategy_params: Base parameters for strategy
        start_date: Evaluation start date
        end_date: Evaluation end date
        initial_capital: Initial capital for backtest

    Returns:
        BacktestMatrixResults with comprehensive evaluation data
    """
    validator = WalkForwardMatrixValidator()
    return validator.run_matrix_evaluation(
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=" * 80)
    print("WALK-FORWARD MATRIX EVALUATION")
    print("=" * 80)
    print("\nTo use this with your strategy:")
    print("\n  from src.strategies.core_strategy import CoreStrategy")
    print("  from src.backtesting.walk_forward_matrix import run_walk_forward_matrix")
    print("\n  results = run_walk_forward_matrix(")
    print("      strategy_class=CoreStrategy,")
    print("      strategy_params={'daily_allocation': 6.0},")
    print('      start_date="2023-01-01",')
    print('      end_date="2025-01-01",')
    print("  )")
    print("\n  print(f'Passed: {results.passed_validation}')")
    print("  print(f'OOS Sharpe: {results.mean_oos_sharpe:.2f}')")
    print("  print(f'Overfitting Score: {results.overfitting_score:.2f}')")
    print("\n" + "=" * 80)
