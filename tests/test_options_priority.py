"""Tests to verify options theta strategy has execution priority.

Based on deep research finding (Dec 12, 2025):
- Options theta decay is the proven profit maker (+$327/day from AMD/SPY puts)
- Options must execute BEFORE momentum to guarantee capital allocation

Reference: ll_020_options_primary_strategy_dec12.md
"""

from __future__ import annotations

import inspect


class TestOptionsExecutionPriority:
    """Verify options strategies execute before momentum trading."""

    def test_options_runs_before_momentum_in_source(self):
        """
        Parse the orchestrator source to verify options methods are called
        before the momentum ticker loop.

        This is a static analysis test - it reads the actual source code
        to ensure the execution order is correct.
        """
        from src.orchestrator.main import TradingOrchestrator

        # Get the source code of the run() method
        source = inspect.getsource(TradingOrchestrator.run)

        # Find line numbers for key method calls
        options_strategy_line = None
        iv_options_line = None
        process_ticker_line = None

        for i, line in enumerate(source.split("\n")):
            if "run_options_strategy()" in line and not line.strip().startswith("#"):
                options_strategy_line = i
            if "run_iv_options_execution()" in line and not line.strip().startswith("#"):
                iv_options_line = i
            if "_process_ticker(" in line and not line.strip().startswith("#"):
                process_ticker_line = i

        assert options_strategy_line is not None, (
            "run_options_strategy() not found in TradingOrchestrator.run()"
        )
        assert iv_options_line is not None, (
            "run_iv_options_execution() not found in TradingOrchestrator.run()"
        )
        assert process_ticker_line is not None, (
            "_process_ticker() not found in TradingOrchestrator.run()"
        )

        # Options must come BEFORE momentum
        assert options_strategy_line < process_ticker_line, (
            f"run_options_strategy() (line {options_strategy_line}) must execute "
            f"BEFORE _process_ticker() (line {process_ticker_line}). "
            "Options theta is the proven profit maker - see ll_020."
        )

        assert iv_options_line < process_ticker_line, (
            f"run_iv_options_execution() (line {iv_options_line}) must execute "
            f"BEFORE _process_ticker() (line {process_ticker_line}). "
            "Options theta is the proven profit maker - see ll_020."
        )

    def test_theta_allocation_is_majority(self):
        """Config should allocate 60% to theta strategies."""
        from src.core.config import OPTIMIZED_ALLOCATION

        theta_total = OPTIMIZED_ALLOCATION.get("theta_spy", 0) + OPTIMIZED_ALLOCATION.get(
            "theta_qqq", 0
        )

        assert theta_total >= 0.5, (
            f"Theta allocation is {theta_total * 100:.0f}%, should be >= 50%. "
            "Options theta is the proven profit strategy."
        )

    def test_momentum_is_secondary(self):
        """Momentum should get <= 40% of allocation."""
        from src.core.config import OPTIMIZED_ALLOCATION

        momentum_total = OPTIMIZED_ALLOCATION.get("momentum_etfs", 0)

        assert momentum_total <= 0.4, (
            f"Momentum allocation is {momentum_total * 100:.0f}%, should be <= 40%. "
            "Options theta should be primary strategy."
        )


class TestOptionsStrategyExists:
    """Verify options strategy components are properly configured."""

    def test_options_strategy_method_exists(self):
        """TradingOrchestrator must have run_options_strategy method."""
        from src.orchestrator.main import TradingOrchestrator

        assert hasattr(TradingOrchestrator, "run_options_strategy"), (
            "TradingOrchestrator missing run_options_strategy method"
        )

    def test_iv_options_method_exists(self):
        """TradingOrchestrator must have run_iv_options_execution method."""
        from src.orchestrator.main import TradingOrchestrator

        assert hasattr(TradingOrchestrator, "run_iv_options_execution"), (
            "TradingOrchestrator missing run_iv_options_execution method"
        )
