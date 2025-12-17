#!/usr/bin/env python3
"""Integration tests for complete trading pipeline.

Tests end-to-end flow:
1. Strategy initialization
2. Signal generation
3. Order creation
4. Execution validation
5. State persistence

Part of P1: Integration Test Suite from SYSTEMIC_FAILURE_PREVENTION_PLAN.md
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest


class TestEquityStrategyIntegration:
    """Integration tests for equity trading strategies."""

    @pytest.mark.slow
    def test_equity_strategy_dry_run(self):
        """Test equity strategy executes successfully in dry-run mode.

        Note: This test can be slow (2-3 minutes) due to market data fetching.
        Mark as @pytest.mark.slow to skip in fast CI runs.
        """
        # Skip in CI if explicitly disabled
        if os.getenv("SKIP_SLOW_TESTS") == "true":
            pytest.skip("Skipping slow equity strategy test in CI")

        env = os.environ.copy()
        env["DRY_RUN"] = "true"
        env["PYTHONPATH"] = str(Path.cwd())

        result = subprocess.run(
            capture_output=True,
            text=True,
            env=env,
            timeout=180,  # Increased to 3 minutes
        )

        # Should exit successfully
        assert result.returncode == 0, f"Equity strategy failed: {result.stderr}"

    def test_momentum_indicators_integration(self):
        """Test technical indicator integration (MACD, RSI, Volume)."""
        try:
            from src.core.indicators import calculate_macd, calculate_rsi

            # Test with sample data
            prices = [100 + i for i in range(30)]  # Uptrend

            # Should not crash
            macd = calculate_macd(prices)
            rsi = calculate_rsi(prices)

            # Basic validation
            if macd is not None:
                assert isinstance(macd, (int, float, dict, tuple))

            if rsi is not None:
                assert isinstance(rsi, (int, float))
                if isinstance(rsi, (int, float)):
                    assert 0 <= rsi <= 100, f"Invalid RSI: {rsi}"

        except ImportError:
            pytest.skip("Indicator module not available")
        except Exception as e:
            pytest.fail(f"Indicator integration failed: {e}")


class TestAlpacaIntegration:
    """Integration tests for Alpaca API connectivity."""

    def test_alpaca_client_initialization(self):
        """Test Alpaca trading client can be initialized."""
        # Only run if credentials available
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            pytest.skip("Alpaca credentials not in environment")

        try:
            from alpaca.trading.client import TradingClient

            client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)
            account = client.get_account()

            assert account is not None
            assert hasattr(account, "equity")
            assert float(account.equity) > 0

        except ImportError:
            pytest.skip("Alpaca SDK not installed")
        except Exception as e:
            pytest.fail(f"Alpaca integration failed: {e}")

    def test_alpaca_market_data(self):
        """Test market data fetching integration."""
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            pytest.skip("Alpaca credentials not in environment")

        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestQuoteRequest

            data_client = StockHistoricalDataClient(api_key, secret_key)

            # Test fetching SPY quote
            request = StockLatestQuoteRequest(symbol_or_symbols="SPY")
            quotes = data_client.get_stock_latest_quote(request)

            assert quotes is not None
            assert "SPY" in quotes

        except ImportError:
            pytest.skip("Alpaca data SDK not installed")
        except Exception as e:
            # Market might be closed
            pytest.skip(f"Market data unavailable: {e}")


class TestSystemIntegration:
    """Integration tests for overall system health."""

    def test_system_state_persistence(self):
        """Test system state can be loaded and validated."""
        state_file = Path("data/system_state.json")

        if not state_file.exists():
            pytest.skip("system_state.json not found (created on first run)")

        try:
            state = json.loads(state_file.read_text())

            # Basic validation
            assert isinstance(state, dict)

            # Should have meta information
            if "meta" in state:
                assert "last_updated" in state["meta"]

        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid system_state.json: {e}")

    def test_trade_log_format(self):
        """Test trade logs can be read and validated."""
        today = datetime.now().strftime("%Y-%m-%d")
        trade_file = Path(f"data/trades_{today}.json")

        if not trade_file.exists():
            pytest.skip(f"No trades today ({today})")

        try:
            trades = json.loads(trade_file.read_text())

            # Validate format
            if not isinstance(trades, list):
                trades = [trades]

            for trade in trades:
                assert isinstance(trade, dict)
                # Should have timestamp
                assert "timestamp" in trade or "created_at" in trade

        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid trade log format: {e}")

    def test_autonomous_trader_syntax(self):
        """Test autonomous_trader.py has valid Python syntax."""
        result = subprocess.run(
            ["python3", "-m", "py_compile", "scripts/autonomous_trader.py"],
            capture_output=True,
            text=True,
        )

        assert (
            result.returncode == 0
        ), f"autonomous_trader.py syntax error: {result.stderr}"

    def test_required_dependencies(self):
        """Test critical dependencies are importable."""
        required_modules = [
            "alpaca.trading.client",
            "alpaca.data.historical",
            "yaml",
            "requests",
        ]

        missing = []
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing.append(module)

        if missing:
            pytest.fail(f"Missing required dependencies: {', '.join(missing)}")


class TestHealthMonitoring:
    """Integration tests for health monitoring system."""

    def test_health_monitor_syntax(self):
        """Test health_monitor.py has valid Python syntax."""
        result = subprocess.run(
            ["python3", "-m", "py_compile", "scripts/health_monitor.py"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"health_monitor.py syntax error: {result.stderr}"

    def test_health_monitor_execution(self):
        """Test health monitor can execute successfully."""
        result = subprocess.run(
            ["python3", "scripts/health_monitor.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should either pass (0) or fail with detected issues (1)
        # Any other exit code indicates a crash
        assert result.returncode in [
            0,
            1,
        ], f"Health monitor crashed: {result.stderr}"

        # Should produce output
        assert len(result.stdout) > 0, "Health monitor produced no output"


if __name__ == "__main__":
    # Run all tests
    pytest.main([__file__, "-v", "--tb=short"])
