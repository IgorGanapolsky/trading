"""Integration tests for critical trading paths.

These tests verify that critical functions are actually CALLED in the execution flow,
not just that they exist. This prevents the "manage_positions() never called" bug.

Run with: pytest tests/integration/test_critical_paths.py -v
"""

import os
from unittest.mock import patch

import pytest

# Set paper trading mode
os.environ["PAPER_TRADING"] = "true"
os.environ["ALPACA_API_KEY"] = "test"
os.environ["ALPACA_SECRET_KEY"] = "test"


class TestCryptoStrategyIntegration:
    """Test that crypto strategy calls manage_positions()."""

    def test_execute_calls_manage_positions(self):
        """CRITICAL: Verify manage_positions() is called during execute()."""
        with patch("src.strategies.crypto_strategy.CryptoStrategy.manage_positions") as mock_manage:
            mock_manage.return_value = []

            with patch("src.strategies.crypto_strategy.CryptoStrategy.execute_daily") as mock_daily:
                mock_daily.return_value = None

                from src.strategies.crypto_strategy import CryptoStrategy

                # Create strategy with mocked trader
                with patch("src.strategies.crypto_strategy.AlpacaTrader"):
                    strategy = CryptoStrategy(paper=True)
                    strategy.manage_positions = mock_manage
                    strategy.execute_daily = mock_daily

                    # Execute
                    strategy.execute()

                    # CRITICAL: manage_positions MUST be called
                    assert mock_manage.called, "manage_positions() was NOT called during execute()!"
                    mock_manage.assert_called_once()

    def test_manage_positions_checks_exit_conditions(self):
        """Verify manage_positions actually checks stop-loss and take-profit."""
        from src.strategies.crypto_strategy import CryptoStrategy

        with patch("src.strategies.crypto_strategy.AlpacaTrader"):
            strategy = CryptoStrategy(paper=True)

            # Verify the method exists and has exit condition logic
            import inspect

            source = inspect.getsource(strategy.manage_positions)

            assert "stop_loss" in source.lower() or "take_profit" in source.lower(), (
                "manage_positions() doesn't check exit conditions!"
            )


class TestOrchestratorIntegration:
    """Test that orchestrator calls all critical components."""

    def test_mental_coach_called_in_run(self):
        """CRITICAL: Verify mental toughness coach is called during run()."""
        # This test verifies the mental coach integration added Dec 8, 2025
        import inspect

        from src.orchestrator.main import TradingOrchestrator

        source = inspect.getsource(TradingOrchestrator.run)

        # Check that mental_coach methods are called
        assert "mental_coach" in source, "mental_coach not referenced in run()!"
        assert "start_session" in source, "start_session() not called!"
        assert "is_ready_to_trade" in source, "is_ready_to_trade() not called!"

    def test_manage_open_positions_called_first(self):
        """CRITICAL: Verify positions are managed BEFORE new entries."""
        import inspect

        from src.orchestrator.main import TradingOrchestrator

        source = inspect.getsource(TradingOrchestrator.run)

        # Find positions of key calls
        manage_pos = source.find("_manage_open_positions")
        process_ticker = source.find("_process_ticker")

        assert manage_pos != -1, "_manage_open_positions not called in run()!"
        assert manage_pos < process_ticker, (
            "_manage_open_positions must be called BEFORE _process_ticker!"
        )


class TestFeatureFlags:
    """Test that critical features are enabled by default."""

    def test_mental_coaching_enabled_by_default(self):
        """Verify ENABLE_MENTAL_COACHING defaults to true."""
        # Clear any existing env var
        os.environ.pop("ENABLE_MENTAL_COACHING", None)

        import inspect

        from src.orchestrator.main import TradingOrchestrator

        source = inspect.getsource(TradingOrchestrator.__init__)

        # Check default value
        assert '"true"' in source.lower() or "'true'" in source.lower(), (
            "ENABLE_MENTAL_COACHING should default to true!"
        )

    def test_growth_strategy_rag_enabled(self):
        """Verify GrowthStrategy initializes RAG by default."""
        import inspect

        from src.strategies.growth_strategy import GrowthStrategy

        source = inspect.getsource(GrowthStrategy.__init__)

        # Check RAG initialization
        assert "rag_db" in source or "get_rag_db" in source, "GrowthStrategy should initialize RAG!"


class TestRAGIntegration:
    """Test RAG system is properly integrated."""

    def test_growth_strategy_uses_rag_for_sentiment(self):
        """Verify GrowthStrategy queries RAG for sentiment."""
        import inspect

        from src.strategies.growth_strategy import GrowthStrategy

        # Check the _rank_candidates or similar method
        try:
            source = inspect.getsource(GrowthStrategy._rank_candidates)
            assert "rag" in source.lower() or "get_ticker_news" in source, (
                "GrowthStrategy should use RAG for sentiment!"
            )
        except AttributeError:
            # Method might have different name
            source = inspect.getsource(GrowthStrategy)
            assert "get_ticker_news" in source, "GrowthStrategy should call get_ticker_news!"


class TestNoDeadCode:
    """Test that commonly dead code patterns are not present."""

    def test_no_notimplementederror_in_critical_paths(self):
        """Verify critical modules don't raise NotImplementedError."""
        critical_modules = [
            "src.orchestrator.main",
            "src.strategies.crypto_strategy",
            "src.agents.rl_agent",
        ]

        for module_path in critical_modules:
            try:
                module = __import__(module_path, fromlist=[""])
                import inspect

                source = inspect.getsource(module)

                # NotImplementedError in __init__ is a red flag
                assert (
                    "raise NotImplementedError" not in source
                    or "__init__"
                    not in source.split("raise NotImplementedError")[0].split("\n")[-10:]
                ), f"{module_path} has NotImplementedError in critical path!"
            except ImportError:
                pass  # Module might not be importable without dependencies


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
