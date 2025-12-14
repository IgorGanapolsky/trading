"""Tests for ML Experiment Runner."""

import tempfile
from pathlib import Path

import pytest
from src.experiments.experiment_runner import (
    Experiment,
    ExperimentResult,
    ExperimentRunner,
    ExperimentStatus,
    HyperparameterGrid,
    run_experiment_sweep,
)
from src.experiments.trading_experiments import (
    calculate_backtest_metrics,
    calculate_macd,
    calculate_rsi,
    combined_strategy_backtest,
    generate_mock_data,
    macd_strategy_backtest,
    rsi_strategy_backtest,
)


class TestHyperparameterGrid:
    """Test hyperparameter grid generation."""

    def test_grid_combinations(self):
        """Test full grid generation."""
        grid = HyperparameterGrid(
            {
                "a": [1, 2],
                "b": ["x", "y"],
            }
        )

        combos = grid.get_combinations(mode="grid")

        assert len(combos) == 4
        assert {"a": 1, "b": "x"} in combos
        assert {"a": 2, "b": "y"} in combos

    def test_random_combinations(self):
        """Test random sampling."""
        grid = HyperparameterGrid(
            {
                "a": [1, 2, 3, 4, 5],
                "b": [10, 20, 30, 40, 50],
            }
        )

        combos = grid.get_combinations(mode="random", n_samples=10)

        assert len(combos) == 10
        for combo in combos:
            assert combo["a"] in [1, 2, 3, 4, 5]
            assert combo["b"] in [10, 20, 30, 40, 50]

    def test_total_combinations(self):
        """Test combination count."""
        grid = HyperparameterGrid(
            {
                "a": [1, 2, 3],
                "b": [1, 2],
                "c": [1, 2, 3, 4],
            }
        )

        assert grid.total_combinations == 24  # 3 * 2 * 4

    def test_dependencies(self):
        """Test parameter dependencies."""
        grid = HyperparameterGrid(
            params={"a": [1, 2]},
            dependencies={"b": lambda p: p["a"] * 2},
        )

        combos = grid.get_combinations()

        assert len(combos) == 2
        assert combos[0]["b"] == combos[0]["a"] * 2


class TestExperimentResult:
    """Test experiment result dataclass."""

    def test_serialization(self):
        """Test result serialization."""
        result = ExperimentResult(
            experiment_id="test123",
            params={"a": 1, "b": 2},
            metrics={"sharpe": 1.5, "return": 10.0},
            status=ExperimentStatus.COMPLETED,
        )

        data = result.to_dict()
        restored = ExperimentResult.from_dict(data)

        assert restored.experiment_id == result.experiment_id
        assert restored.params == result.params
        assert restored.metrics == result.metrics
        assert restored.status == result.status


class TestExperimentRunner:
    """Test experiment runner."""

    @pytest.mark.asyncio
    async def test_run_single_experiment(self):
        """Test running a single experiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(storage_path=Path(tmpdir))

            def simple_fn(params):
                return {"result": params["a"] + params["b"]}

            experiment = Experiment(
                params={"a": 1, "b": 2},
                fn=simple_fn,
            )

            result = await runner.run_experiment(experiment)

            assert result.status == ExperimentStatus.COMPLETED
            assert result.metrics["result"] == 3

    @pytest.mark.asyncio
    async def test_run_sweep(self):
        """Test running a parameter sweep."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(storage_path=Path(tmpdir))

            def multiply_fn(params):
                return {"product": params["a"] * params["b"]}

            grid = HyperparameterGrid(
                {
                    "a": [1, 2],
                    "b": [10, 20],
                }
            )

            results = await runner.run_sweep(
                experiment_fn=multiply_fn,
                grid=grid,
                parallel=False,
            )

            assert len(results) == 4
            assert all(r.status == ExperimentStatus.COMPLETED for r in results)

    @pytest.mark.asyncio
    async def test_caching(self):
        """Test that results are cached."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(storage_path=Path(tmpdir))

            call_count = 0

            def counting_fn(params):
                nonlocal call_count
                call_count += 1
                return {"count": call_count}

            experiment = Experiment(
                params={"a": 1},
                fn=counting_fn,
            )

            # First run
            result1 = await runner.run_experiment(experiment)
            assert result1.status == ExperimentStatus.COMPLETED
            assert call_count == 1

            # Second run - should use cache
            result2 = await runner.run_experiment(experiment)
            assert result2.status == ExperimentStatus.SKIPPED
            assert call_count == 1  # Function not called again

    @pytest.mark.asyncio
    async def test_get_best_result(self):
        """Test finding best result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(storage_path=Path(tmpdir))

            def score_fn(params):
                return {"score": params["x"]}

            grid = HyperparameterGrid({"x": [1, 5, 3, 2, 4]})

            results = await runner.run_sweep(
                experiment_fn=score_fn,
                grid=grid,
                parallel=False,
            )

            best = runner.get_best_result(results, "score", maximize=True)
            assert best.metrics["score"] == 5

            worst = runner.get_best_result(results, "score", maximize=False)
            assert worst.metrics["score"] == 1

    @pytest.mark.asyncio
    async def test_param_importance(self):
        """Test parameter importance analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(storage_path=Path(tmpdir))

            def deterministic_fn(params):
                # 'a' has strong impact, 'b' has weak impact
                return {"score": params["a"] * 10 + params["b"]}

            grid = HyperparameterGrid(
                {
                    "a": [1, 2, 3],
                    "b": [0, 1],
                }
            )

            results = await runner.run_sweep(
                experiment_fn=deterministic_fn,
                grid=grid,
                parallel=False,
            )

            importance = runner.analyze_param_importance(results, "score")

            # 'a' should show bigger range than 'b'
            a_range = max(float(v) for v in importance["a"].values()) - min(
                float(v) for v in importance["a"].values()
            )
            b_range = max(float(v) for v in importance["b"].values()) - min(
                float(v) for v in importance["b"].values()
            )

            assert a_range > b_range

    @pytest.mark.asyncio
    async def test_generate_report(self):
        """Test report generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = ExperimentRunner(storage_path=Path(tmpdir))

            def simple_fn(params):
                return {"metric": params["x"] * 2}

            grid = HyperparameterGrid({"x": [1, 2, 3]})

            results = await runner.run_sweep(
                experiment_fn=simple_fn,
                grid=grid,
                parallel=False,
            )

            report = runner.generate_report(results, primary_metric="metric")

            assert "EXPERIMENT SWEEP REPORT" in report
            assert "Total Experiments: 3" in report
            assert "metric" in report


class TestTradingExperiments:
    """Test trading-specific experiment functions."""

    def test_generate_mock_data(self):
        """Test mock data generation."""
        data = generate_mock_data(100)

        assert len(data) == 100
        assert all("close" in d for d in data)
        assert all("high" in d for d in data)
        assert all("low" in d for d in data)

    def test_calculate_rsi(self):
        """Test RSI calculation."""
        prices = [100 + i for i in range(20)]  # Uptrend
        rsi = calculate_rsi(prices, period=14)

        assert len(rsi) == len(prices)
        assert rsi[-1] > 50  # Should be bullish in uptrend

    def test_calculate_macd(self):
        """Test MACD calculation."""
        prices = [100 + i * 0.1 for i in range(50)]
        macd_line, signal_line, histogram = calculate_macd(prices)

        assert len(macd_line) == len(prices)
        assert len(signal_line) == len(prices)
        assert len(histogram) == len(prices)

    def test_rsi_strategy_backtest(self):
        """Test RSI strategy backtest."""
        params = {
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 4.0,
        }

        metrics = rsi_strategy_backtest(params)

        assert "total_return" in metrics
        assert "sharpe_ratio" in metrics
        assert "win_rate" in metrics
        assert "num_trades" in metrics

    def test_macd_strategy_backtest(self):
        """Test MACD strategy backtest."""
        params = {
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "stop_loss_pct": 2.0,
        }

        metrics = macd_strategy_backtest(params)

        assert "total_return" in metrics
        assert "sharpe_ratio" in metrics

    def test_combined_strategy_backtest(self):
        """Test combined strategy backtest."""
        params = {
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0,
        }

        metrics = combined_strategy_backtest(params)

        assert "total_return" in metrics
        assert "profit_factor" in metrics

    def test_calculate_backtest_metrics(self):
        """Test metric calculation from trades."""
        trades = [
            {"pnl_pct": 5.0, "bars_held": 10, "exit_reason": "take_profit"},
            {"pnl_pct": -2.0, "bars_held": 5, "exit_reason": "stop_loss"},
            {"pnl_pct": 3.0, "bars_held": 8, "exit_reason": "signal"},
            {"pnl_pct": 4.0, "bars_held": 12, "exit_reason": "take_profit"},
        ]

        metrics = calculate_backtest_metrics(trades)

        assert metrics["num_trades"] == 4
        assert metrics["win_rate"] == 0.75  # 3 wins, 1 loss
        assert metrics["total_return"] == 10.0  # 5 - 2 + 3 + 4

    def test_empty_trades(self):
        """Test metrics with no trades."""
        metrics = calculate_backtest_metrics([])

        assert metrics["num_trades"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0


class TestConvenienceFunction:
    """Test the convenience function."""

    @pytest.mark.asyncio
    async def test_run_experiment_sweep(self):
        """Test the convenience sweep function."""

        def simple_fn(params):
            return {"value": params["x"] ** 2}

        results, report = await run_experiment_sweep(
            experiment_fn=simple_fn,
            params={"x": [1, 2, 3]},
            parallel=False,
        )

        assert len(results) == 3
        assert "EXPERIMENT SWEEP REPORT" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
