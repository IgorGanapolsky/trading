"""
Tests for Phil Town Rule #1 Validator

Validates that the RuleOneValidator correctly:
1. Checks universe membership
2. Validates Big Five metrics
3. Calculates Sticker Price and MOS
4. Integrates with TradeGateway
"""

import pytest
from unittest.mock import patch, MagicMock

from src.validators.rule_one_validator import (
    RuleOneValidator,
    RuleOneValidationResult,
    BigFiveResult,
    StickerPriceResult,
    BIG_FIVE_MIN_GROWTH,
)


class TestBigFiveResult:
    """Tests for BigFiveResult dataclass."""

    def test_passes_when_all_metrics_above_threshold(self):
        """All metrics >= 10% should pass."""
        result = BigFiveResult(
            roic=0.15,
            sales_growth=0.12,
            eps_growth=0.11,
            equity_growth=0.13,
            fcf_growth=0.10,
        )
        assert result.passes is True
        assert len(result.failed_metrics) == 0
        assert result.avg_growth >= BIG_FIVE_MIN_GROWTH

    def test_fails_when_roic_below_threshold(self):
        """ROIC < 10% should fail."""
        result = BigFiveResult(
            roic=0.08,  # Below threshold
            sales_growth=0.12,
            eps_growth=0.11,
            equity_growth=0.13,
            fcf_growth=0.10,
        )
        assert result.passes is False
        assert any("ROIC" in m for m in result.failed_metrics)

    def test_fails_when_growth_below_threshold(self):
        """Growth metrics < 10% should fail."""
        result = BigFiveResult(
            roic=0.15,
            sales_growth=0.05,  # Below threshold
            eps_growth=0.11,
            equity_growth=0.13,
            fcf_growth=0.10,
        )
        assert result.passes is False
        assert any("Sales" in m for m in result.failed_metrics)

    def test_calculates_average_growth(self):
        """Average growth should be calculated correctly."""
        result = BigFiveResult(
            roic=0.15,
            sales_growth=0.10,
            eps_growth=0.20,
            equity_growth=0.10,
            fcf_growth=0.20,
        )
        # Average of 0.10, 0.20, 0.10, 0.20 = 0.15
        assert result.avg_growth == pytest.approx(0.15, abs=0.01)


class TestStickerPriceResult:
    """Tests for StickerPriceResult dataclass."""

    def test_passes_when_below_mos(self):
        """Current price below MOS should pass."""
        result = StickerPriceResult(
            current_price=10.0,
            sticker_price=30.0,
            mos_price=15.0,  # 50% of sticker
        )
        assert result.passes is True
        assert result.discount_pct == pytest.approx(0.67, abs=0.01)
        assert "Below MOS" in result.reason

    def test_fails_when_above_mos(self):
        """Current price above MOS should fail."""
        result = StickerPriceResult(
            current_price=20.0,
            sticker_price=30.0,
            mos_price=15.0,
        )
        assert result.passes is False
        assert "above MOS" in result.reason

    def test_fails_when_overvalued(self):
        """Current price above sticker should be overvalued."""
        result = StickerPriceResult(
            current_price=40.0,
            sticker_price=30.0,
            mos_price=15.0,
        )
        assert result.passes is False
        assert "Overvalued" in result.reason


class TestRuleOneValidator:
    """Tests for RuleOneValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance."""
        return RuleOneValidator(strict_mode=False, capital_tier="small")

    @pytest.fixture
    def strict_validator(self):
        """Create a strict mode validator."""
        return RuleOneValidator(strict_mode=True, capital_tier="small")

    def test_universe_check_passes_for_known_stocks(self, validator):
        """Stocks in RULE_ONE_UNIVERSE should pass universe check."""
        for symbol in ["F", "SOFI", "T", "AAPL"]:
            result = RuleOneValidationResult(symbol=symbol, approved=False)
            assert validator._check_universe(symbol, result) is True
            assert result.in_universe is True

    def test_universe_check_fails_for_unknown_stocks(self, validator):
        """Stocks not in RULE_ONE_UNIVERSE should fail."""
        result = RuleOneValidationResult(symbol="UNKNOWN", approved=False)
        assert validator._check_universe("UNKNOWN", result) is False

    def test_extracts_underlying_from_option_symbol(self, validator):
        """Should extract underlying from option symbol."""
        assert validator._extract_underlying("SOFI260206P00024000") == "SOFI"
        assert validator._extract_underlying("F260117P00012000") == "F"
        assert validator._extract_underlying("AAPL") == "AAPL"

    def test_validate_approved_for_good_stock(self, validator):
        """A stock passing all checks should be approved."""
        # Mock Big Five result
        mock_big_five = BigFiveResult(
            roic=0.15,
            sales_growth=0.12,
            eps_growth=0.11,
            equity_growth=0.13,
            fcf_growth=0.10,
        )

        # Mock Sticker Price result
        mock_sticker = StickerPriceResult(
            current_price=10.0,
            sticker_price=30.0,
            mos_price=15.0,
        )

        with patch.object(validator, "_check_big_five", return_value=mock_big_five):
            with patch.object(validator, "_check_sticker_price", return_value=mock_sticker):
                result = validator.validate("SOFI")
                assert result.approved is True
                assert result.in_universe is True
                assert len(result.rejection_reasons) == 0

    def test_validate_rejected_for_unknown_stock(self, validator):
        """Unknown stock should be rejected."""
        result = validator.validate("UNKNOWN_TICKER_XYZ")
        assert result.approved is False
        assert result.in_universe is False
        assert any("not in" in r for r in result.rejection_reasons)

    def test_strict_mode_rejects_partial_pass(self, strict_validator):
        """Strict mode should reject stocks that only partially pass."""
        with patch.object(strict_validator, "_check_big_five") as mock_big_five:
            mock_big_five.return_value = BigFiveResult(
                roic=0.08,  # Below threshold
                sales_growth=0.12,
                eps_growth=0.11,
                equity_growth=0.13,
                fcf_growth=0.10,
            )
            with patch.object(strict_validator, "_check_sticker_price") as mock_sticker:
                mock_sticker.return_value = StickerPriceResult(
                    current_price=20.0,
                    sticker_price=30.0,
                    mos_price=15.0,
                )
                result = strict_validator.validate("SOFI")
                assert result.approved is False
                assert any("Big Five" in r for r in result.rejection_reasons)

    def test_credit_spread_validation(self, validator):
        """Credit spread validation should add specific warnings."""
        with patch.object(validator, "validate") as mock_validate:
            mock_validate.return_value = RuleOneValidationResult(
                symbol="GOOGL",
                approved=True,
                in_universe=True,
            )
            result = validator.validate_for_credit_spread(
                "GOOGL",
                spread_width=5.0,
                max_collateral=600.0,  # Above $500 limit
            )
            # Should have warning about collateral
            assert any("$500" in w for w in result.warnings)

    def test_confidence_calculation(self, validator):
        """Confidence should be calculated based on validation results."""
        result = RuleOneValidationResult(
            symbol="SOFI",
            approved=True,
            in_universe=True,
            big_five=BigFiveResult(
                roic=0.15,
                sales_growth=0.12,
                eps_growth=0.11,
                equity_growth=0.13,
                fcf_growth=0.10,
            ),
            sticker_price=StickerPriceResult(
                current_price=10.0,
                sticker_price=30.0,
                mos_price=15.0,
            ),
        )
        confidence = validator._calculate_confidence(result)
        # Should be high confidence (universe + big five + sticker all pass)
        assert confidence >= 0.90


class TestTradeGatewayIntegration:
    """Tests for TradeGateway CHECK 13 integration."""

    @pytest.fixture
    def mock_trader(self):
        """Create mock AlpacaTrader."""
        trader = MagicMock()
        trader.get_account.return_value = {
            "equity": "5000",
            "cash": "5000",
            "buying_power": "5000",
        }
        trader.get_positions.return_value = []
        return trader

    @patch("src.risk.trade_gateway.RuleOneValidator")
    def test_gateway_uses_rule_one_validator(self, mock_validator_class, mock_trader):
        """TradeGateway should use RuleOneValidator for CHECK 13."""
        from src.risk.trade_gateway import TradeGateway, TradeRequest

        # Setup mock validator
        mock_validator = mock_validator_class.return_value
        mock_result = RuleOneValidationResult(
            symbol="SOFI",
            approved=True,
            in_universe=True,
            confidence=0.85,
        )
        mock_validator.validate.return_value = mock_result

        # Create gateway and evaluate
        gateway = TradeGateway(executor=mock_trader, paper=True)
        request = TradeRequest(
            symbol="SOFI",
            side="buy",
            notional=100.0,
        )

        with patch.object(gateway, "_get_total_pl", return_value=100.0):
            with patch.object(gateway, "_get_account_equity", return_value=5000.0):
                with patch.object(gateway, "_get_positions", return_value=[]):
                    with patch.object(gateway, "_get_price", return_value=10.0):
                        with patch.object(gateway, "_count_recent_trades", return_value=0):
                            with patch.object(gateway, "_update_daily_pnl"):
                                with patch.object(gateway, "_get_drawdown", return_value=0.0):
                                    gateway.evaluate(request)  # Testing side effect

        # Validator should have been called
        mock_validator.validate.assert_called_once_with("SOFI")

    @patch("src.risk.trade_gateway.RuleOneValidator")
    def test_gateway_rejects_rule_one_violation(self, mock_validator_class, mock_trader):
        """TradeGateway should reject trades that fail Rule #1."""
        from src.risk.trade_gateway import TradeGateway, TradeRequest, RejectionReason

        # Setup mock validator to reject
        mock_validator = mock_validator_class.return_value
        mock_result = RuleOneValidationResult(
            symbol="UNKNOWN",
            approved=False,
            in_universe=False,
            rejection_reasons=["UNKNOWN not in Rule #1 wonderful companies universe"],
        )
        mock_result.to_dict = MagicMock(return_value={"approved": False})
        mock_validator.validate.return_value = mock_result

        # Create gateway and evaluate
        gateway = TradeGateway(executor=mock_trader, paper=True)
        request = TradeRequest(
            symbol="UNKNOWN",
            side="buy",
            notional=100.0,
        )

        with patch.object(gateway, "_get_total_pl", return_value=100.0):
            with patch.object(gateway, "_get_account_equity", return_value=5000.0):
                with patch.object(gateway, "_get_positions", return_value=[]):
                    with patch.object(gateway, "_get_price", return_value=10.0):
                        with patch.object(gateway, "_count_recent_trades", return_value=0):
                            with patch.object(gateway, "_update_daily_pnl"):
                                with patch.object(gateway, "_get_drawdown", return_value=0.0):
                                    decision = gateway.evaluate(request)

        # Should be rejected for Rule #1 violation
        assert RejectionReason.RULE_ONE_VIOLATION in decision.rejection_reasons


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
