"""
Tests for Bond Trading Components

Tests for:
- Bond data ingestion
- Bond yield agent
- Bond risk management
- Treasury ladder strategy

Author: Trading System
Created: 2025-12-03
"""

from unittest.mock import patch

import pytest


class TestBondYieldAgent:
    """Tests for BondYieldAgent class."""

    def test_yield_curve_shape_detection(self):
        """Test yield curve shape classification."""
        from src.agents.bond_yield_agent import BondYieldAgent, YieldCurveShape

        agent = BondYieldAgent()

        # Mock FRED data for different curve shapes
        with patch.object(agent, "_get_yield_data") as mock_yields:
            # Steep curve
            mock_yields.return_value = {"DGS2": 3.4, "DGS10": 5.0, "DGS30": 5.5, "T10Y2Y": 1.6}
            signal = agent.analyze_yield_curve()
            assert signal.shape == YieldCurveShape.STEEP

            # Normal curve
            mock_yields.return_value = {"DGS2": 4.0, "DGS10": 4.8, "DGS30": 5.0, "T10Y2Y": 0.8}
            signal = agent.analyze_yield_curve()
            assert signal.shape == YieldCurveShape.NORMAL

            # Flat curve
            mock_yields.return_value = {"DGS2": 4.5, "DGS10": 4.7, "DGS30": 4.8, "T10Y2Y": 0.2}
            signal = agent.analyze_yield_curve()
            assert signal.shape == YieldCurveShape.FLAT

            # Inverted curve
            mock_yields.return_value = {"DGS2": 5.0, "DGS10": 4.5, "DGS30": 4.3, "T10Y2Y": -0.5}
            signal = agent.analyze_yield_curve()
            assert signal.shape == YieldCurveShape.INVERTED

    def test_bond_allocation_signals(self):
        """Test bond allocation signal generation."""
        from src.agents.bond_yield_agent import BondYieldAgent

        agent = BondYieldAgent(min_confidence=0.0)

        with patch.object(agent, "_get_yield_data") as mock_yields:
            mock_yields.return_value = {"DGS2": 4.0, "DGS10": 4.5, "DGS30": 4.7, "T10Y2Y": 0.5}

            with patch.object(agent, "_check_bond_momentum") as mock_momentum:
                mock_momentum.return_value = (True, {"momentum_gate": "OPEN"})

                signals = agent.generate_bond_signals(daily_allocation=10.0)

                assert len(signals) > 0
                # Should include treasury signals
                treasury_symbols = {s.symbol for s in signals if s.category == "treasury"}
                assert (
                    "SHY" in treasury_symbols
                    or "IEF" in treasury_symbols
                    or "TLT" in treasury_symbols
                )

    def test_duration_target_by_curve_shape(self):
        """Test that duration targets vary by curve shape."""
        from src.agents.bond_yield_agent import BondYieldAgent

        agent = BondYieldAgent()

        # Inverted curve should recommend short duration
        with patch.object(agent, "_get_yield_data") as mock_yields:
            mock_yields.return_value = {"DGS2": 5.0, "DGS10": 4.5, "DGS30": 4.3, "T10Y2Y": -0.5}
            signal = agent.analyze_yield_curve()
            assert signal.recommended_duration == "short"

        # Steep curve should recommend long duration
        with patch.object(agent, "_get_yield_data") as mock_yields:
            mock_yields.return_value = {"DGS2": 3.4, "DGS10": 5.0, "DGS30": 5.5, "T10Y2Y": 1.6}
            signal = agent.analyze_yield_curve()
            assert signal.recommended_duration == "long"


class TestBondRiskManager:
    """Tests for BondRiskManager class."""

    def test_duration_stop_loss_calculation(self):
        """Test duration-adjusted stop loss calculation."""
        from src.risk.bond_risk import BondRiskManager

        manager = BondRiskManager()

        # Short duration bond should have tighter stop
        short_stop = manager.calculate_duration_stop_loss(entry_price=100.0, duration=2.0)
        # Long duration bond should have wider stop
        long_stop = manager.calculate_duration_stop_loss(entry_price=100.0, duration=16.0)

        # Long duration stop should be further from entry
        assert long_stop < short_stop
        # Both should be below entry for long position
        assert short_stop < 100.0
        assert long_stop < 100.0

    def test_portfolio_duration_calculation(self):
        """Test portfolio duration calculation."""
        from src.risk.bond_risk import BondRiskManager

        manager = BondRiskManager()

        positions = [
            {"symbol": "SHY", "market_value": 1000},  # 1.9yr duration
            {"symbol": "TLT", "market_value": 1000},  # 16.5yr duration
        ]

        assessment = manager.assess_portfolio_risk(positions, portfolio_value=100000)

        # Portfolio duration should be weighted average
        expected_duration = (1000 / 100000) * 1.9 + (1000 / 100000) * 16.5
        assert abs(assessment.portfolio_duration - expected_duration) < 0.01

    def test_trade_validation_limits(self):
        """Test trade validation against limits."""
        from src.risk.bond_risk import BondRiskManager

        manager = BondRiskManager(
            max_bond_allocation=0.30,  # 30% max
            max_hy_allocation=0.10,  # 10% max HY
        )

        positions = []
        portfolio_value = 100000

        # Valid trade
        valid, reason = manager.validate_bond_trade(
            symbol="SHY",
            trade_value=5000,
            current_positions=positions,
            portfolio_value=portfolio_value,
        )
        assert valid is True

        # Trade exceeding bond limit
        valid, reason = manager.validate_bond_trade(
            symbol="TLT",
            trade_value=35000,  # Would be 35% of portfolio
            current_positions=positions,
            portfolio_value=portfolio_value,
        )
        assert valid is False
        assert "max bond allocation" in reason.lower()

        # High yield limit
        positions = [{"symbol": "JNK", "market_value": 8000}]  # Already 8%
        valid, reason = manager.validate_bond_trade(
            symbol="HYG",
            trade_value=5000,  # Would make 13% HY
            current_positions=positions,
            portfolio_value=portfolio_value,
        )
        assert valid is False
        assert "high yield" in reason.lower()

    def test_dv01_calculation(self):
        """Test DV01 (Dollar Value of 01) calculation."""
        from src.risk.bond_risk import BondRiskManager

        manager = BondRiskManager()

        # DV01 = Position Value × Duration × 0.0001
        metrics = manager.calculate_position_metrics(
            symbol="TLT",
            position_value=10000,
            portfolio_value=100000,
        )

        # TLT duration is 16.5 years
        expected_dv01 = 10000 * 16.5 * 0.0001  # = 16.5
        assert abs(metrics.dv01 - expected_dv01) < 0.01

    def test_risk_level_classification(self):
        """Test risk level classification by duration."""
        from src.risk.bond_risk import BondRiskLevel, BondRiskManager

        manager = BondRiskManager()

        # Low duration portfolio
        low_dur_positions = [{"symbol": "SHY", "market_value": 5000}]
        assessment = manager.assess_portfolio_risk(low_dur_positions, 100000)
        assert assessment.risk_level == BondRiskLevel.LOW

        # High duration portfolio
        high_dur_positions = [{"symbol": "TLT", "market_value": 80000}]
        assessment = manager.assess_portfolio_risk(high_dur_positions, 100000)
        assert assessment.risk_level == BondRiskLevel.HIGH


class TestTreasuryLadderStrategy:
    """Tests for TreasuryLadderStrategy class."""

    def test_allocation_by_regime(self):
        """Test allocation changes by yield curve regime."""
        from src.strategies.treasury_ladder_strategy import (
            TreasuryLadderStrategy,
        )

        strategy = TreasuryLadderStrategy(daily_allocation=10.0, paper=True)

        # Normal curve allocation
        assert strategy.ALLOCATION_NORMAL["SHY"] == 0.40
        assert strategy.ALLOCATION_NORMAL["IEF"] == 0.40
        assert strategy.ALLOCATION_NORMAL["TLT"] == 0.20

        # Inverted curve should favor short duration
        assert strategy.ALLOCATION_INVERTED["SHY"] == 0.70
        assert strategy.ALLOCATION_INVERTED["TLT"] == 0.05

    def test_rebalance_threshold(self):
        """Test rebalancing threshold logic."""
        from src.strategies.treasury_ladder_strategy import TreasuryLadderStrategy

        strategy = TreasuryLadderStrategy(
            daily_allocation=10.0,
            rebalance_threshold=0.05,
            paper=True,
        )

        assert strategy.rebalance_threshold == 0.05

    def test_initialization_validation(self):
        """Test initialization parameter validation."""
        from src.strategies.treasury_ladder_strategy import TreasuryLadderStrategy

        # Should raise on invalid allocation
        with pytest.raises(ValueError):
            TreasuryLadderStrategy(daily_allocation=-10.0, paper=True)

        # Should raise on invalid threshold
        with pytest.raises(ValueError):
            TreasuryLadderStrategy(daily_allocation=10.0, rebalance_threshold=1.5, paper=True)


class TestBondDataIngester:
    """Tests for bond data ingestion."""

    def test_bond_etf_universe_complete(self):
        """Test that bond ETF universe has required metadata."""
        from scripts.bond_data_ingester import BOND_ETFS

        required_fields = ["name", "category", "duration", "credit_quality"]

        for symbol, metadata in BOND_ETFS.items():
            for field in required_fields:
                assert field in metadata, f"{symbol} missing {field}"

    def test_bond_categories(self):
        """Test bond category classification."""
        from scripts.bond_data_ingester import BOND_ETFS

        categories = {meta["category"] for meta in BOND_ETFS.values()}

        assert "treasury" in categories
        assert "corporate_ig" in categories
        assert "corporate_hy" in categories
        assert "tips" in categories

    def test_duration_classification(self):
        """Test duration classification consistency."""
        from scripts.bond_data_ingester import BOND_ETFS

        for symbol, metadata in BOND_ETFS.items():
            duration = metadata.get("duration")
            duration_years = metadata.get("duration_years", 0)

            if duration == "short":
                assert duration_years < 4, f"{symbol} short duration but {duration_years} years"
            elif duration == "long":
                assert duration_years > 10, f"{symbol} long duration but {duration_years} years"


class TestIntegration:
    """Integration tests for bond trading components."""

    def test_yield_agent_to_risk_manager_flow(self):
        """Test data flow from yield agent to risk manager."""
        from src.agents.bond_yield_agent import BondYieldAgent
        from src.risk.bond_risk import BondRiskManager

        agent = BondYieldAgent(min_confidence=0.0)
        risk_manager = BondRiskManager()

        with patch.object(agent, "_get_yield_data") as mock_yields:
            mock_yields.return_value = {"DGS2": 4.0, "DGS10": 4.5, "T10Y2Y": 0.5}

            with patch.object(agent, "_check_bond_momentum") as mock_momentum:
                mock_momentum.return_value = (True, {"momentum_gate": "OPEN"})

                signals = agent.generate_bond_signals(daily_allocation=10.0)

                # Each signal should be validatable by risk manager
                for signal in signals:
                    if signal.is_buy:
                        valid, reason = risk_manager.validate_bond_trade(
                            symbol=signal.symbol,
                            trade_value=signal.indicators.get("allocation_amount", 1.0),
                            current_positions=[],
                            portfolio_value=100000,
                        )
                        # Should be valid for small trades
                        assert valid is True, f"Trade {signal.symbol} rejected: {reason}"

    def test_duration_consistency_across_modules(self):
        """Test duration estimates are consistent across modules."""
        from scripts.bond_data_ingester import BOND_ETFS
        from src.risk.bond_risk import BondRiskManager

        manager = BondRiskManager()

        # Check key ETFs have matching durations
        key_etfs = ["SHY", "IEF", "TLT", "BND", "LQD", "JNK"]

        for symbol in key_etfs:
            ingester_duration = BOND_ETFS.get(symbol, {}).get("duration_years")
            risk_duration = manager.DURATION_ESTIMATES.get(symbol)

            if ingester_duration and risk_duration:
                assert abs(ingester_duration - risk_duration) < 0.5, (
                    f"{symbol} duration mismatch: ingester={ingester_duration}, "
                    f"risk={risk_duration}"
                )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
