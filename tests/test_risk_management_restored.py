"""
Tests for restored risk management components.

Created: January 12, 2026
Purpose: Verify VIX circuit breaker and risk manager work correctly.
"""

from src.risk.vix_circuit_breaker import VIXCircuitBreaker, AlertLevel, VIXStatus
from src.risk.risk_manager import RiskManager, RiskCheck


class TestVIXCircuitBreaker:
    """Tests for VIX circuit breaker."""

    def test_init(self):
        """Test circuit breaker initialization."""
        cb = VIXCircuitBreaker()
        assert cb.halt_threshold == 30.0
        assert cb._cached_status is None

    def test_custom_threshold(self):
        """Test custom halt threshold."""
        cb = VIXCircuitBreaker(halt_threshold=25.0)
        assert cb.halt_threshold == 25.0

    def test_alert_level_normal(self):
        """Test normal VIX level detection."""
        cb = VIXCircuitBreaker()
        assert cb._get_alert_level(12.0) == AlertLevel.NORMAL
        assert cb._get_alert_level(14.9) == AlertLevel.NORMAL

    def test_alert_level_elevated(self):
        """Test elevated VIX level detection."""
        cb = VIXCircuitBreaker()
        assert cb._get_alert_level(15.0) == AlertLevel.ELEVATED
        assert cb._get_alert_level(19.9) == AlertLevel.ELEVATED

    def test_alert_level_high(self):
        """Test high VIX level detection."""
        cb = VIXCircuitBreaker()
        assert cb._get_alert_level(20.0) == AlertLevel.HIGH
        assert cb._get_alert_level(24.9) == AlertLevel.HIGH

    def test_alert_level_very_high(self):
        """Test very high VIX level detection."""
        cb = VIXCircuitBreaker()
        assert cb._get_alert_level(25.0) == AlertLevel.VERY_HIGH
        assert cb._get_alert_level(29.9) == AlertLevel.VERY_HIGH

    def test_alert_level_extreme(self):
        """Test extreme VIX level detection."""
        cb = VIXCircuitBreaker()
        assert cb._get_alert_level(30.0) == AlertLevel.EXTREME
        assert cb._get_alert_level(39.9) == AlertLevel.EXTREME

    def test_alert_level_spike(self):
        """Test spike VIX level detection."""
        cb = VIXCircuitBreaker()
        assert cb._get_alert_level(40.0) == AlertLevel.SPIKE
        assert cb._get_alert_level(80.0) == AlertLevel.SPIKE

    def test_vix_status_dataclass(self):
        """Test VIXStatus dataclass."""
        status = VIXStatus(
            current_level=15.5,
            alert_level=AlertLevel.ELEVATED,
            message="Test message",
        )
        assert status.current_level == 15.5
        assert status.alert_level == AlertLevel.ELEVATED
        assert status.timestamp is not None


class TestRiskManager:
    """Tests for risk manager."""

    def test_init_default(self):
        """Test default initialization."""
        rm = RiskManager()
        assert rm.portfolio_value == 5000.0
        assert rm.max_position_pct == 0.20
        assert rm.max_daily_loss_pct == 0.02

    def test_init_custom(self):
        """Test custom initialization."""
        rm = RiskManager(
            portfolio_value=10000.0,
            max_position_pct=0.10,
            max_daily_loss_pct=0.01,
        )
        assert rm.portfolio_value == 10000.0
        assert rm.max_position_pct == 0.10
        assert rm.max_daily_loss_pct == 0.01

    def test_position_size_check_pass(self):
        """Test position size check passes for valid size."""
        rm = RiskManager(portfolio_value=5000.0)
        result = rm.check_position_size("AAPL", 500.0)  # 10% of portfolio
        assert result.passed is True
        assert "within limit" in result.reason

    def test_position_size_check_fail(self):
        """Test position size check fails for oversized position."""
        rm = RiskManager(portfolio_value=5000.0)
        result = rm.check_position_size("AAPL", 2000.0)  # 40% of portfolio
        assert result.passed is False
        assert "exceeds max" in result.reason

    def test_daily_loss_check_pass(self):
        """Test daily loss check passes within limit."""
        rm = RiskManager(portfolio_value=5000.0)
        result = rm.check_daily_loss(50.0)  # 1% loss
        assert result.passed is True

    def test_daily_loss_check_fail(self):
        """Test daily loss check fails when exceeded."""
        rm = RiskManager(portfolio_value=5000.0)
        result = rm.check_daily_loss(200.0)  # 4% loss
        assert result.passed is False
        assert "exceed limit" in result.reason

    def test_cash_reserve_check_pass(self):
        """Test cash reserve check passes with sufficient reserve."""
        rm = RiskManager(portfolio_value=5000.0)
        result = rm.check_cash_reserve(cash_available=2000.0, trade_cost=500.0)
        assert result.passed is True

    def test_cash_reserve_check_fail(self):
        """Test cash reserve check fails when reserve too low."""
        rm = RiskManager(portfolio_value=5000.0)
        result = rm.check_cash_reserve(cash_available=1000.0, trade_cost=900.0)
        assert result.passed is False
        assert "below minimum" in result.reason

    def test_get_position_limit(self):
        """Test position limit calculation."""
        rm = RiskManager(portfolio_value=5000.0, max_position_pct=0.20)
        assert rm.get_position_limit("AAPL") == 1000.0

    def test_get_max_contracts(self):
        """Test max contracts calculation."""
        rm = RiskManager(portfolio_value=5000.0)
        # With $5K portfolio, $5 strike, 20% reserve
        # Usable: $4000 (80% of $5K)
        # Collateral per contract: $500 ($5 x 100)
        # Max by cash: 8 contracts
        # Max by position (20%): $1000 / $500 = 2 contracts
        max_contracts = rm.get_max_contracts(strike_price=5.0, cash_available=5000.0)
        assert max_contracts == 2

    def test_calculate_risk(self):
        """Test comprehensive risk calculation."""
        rm = RiskManager(portfolio_value=5000.0)
        risk = rm.calculate_risk(
            symbol="F",
            notional_value=500.0,
            cash_available=5000.0,
            potential_loss=50.0,
        )
        assert risk["approved"] is True
        assert "risk_score" in risk
        assert "position_check" in risk
        assert "daily_loss_check" in risk
        assert "cash_reserve_check" in risk

    def test_approve_trade_pass(self):
        """Test trade approval for valid trade."""
        rm = RiskManager(portfolio_value=5000.0)
        approved, reason = rm.approve_trade(
            symbol="F",
            notional_value=500.0,
            cash_available=5000.0,
            potential_loss=50.0,
        )
        assert approved is True
        assert "approved" in reason.lower()

    def test_approve_trade_fail_position(self):
        """Test trade rejection for oversized position."""
        rm = RiskManager(portfolio_value=5000.0)
        approved, reason = rm.approve_trade(
            symbol="F",
            notional_value=2000.0,  # 40% - too large
            cash_available=5000.0,
        )
        assert approved is False
        assert "exceeds" in reason

    def test_record_pnl(self):
        """Test P&L recording."""
        rm = RiskManager(portfolio_value=5000.0)
        rm.record_pnl(-50.0)
        assert rm._daily_pnl == -50.0
        rm.record_pnl(25.0)
        assert rm._daily_pnl == -25.0

    def test_risk_check_dataclass(self):
        """Test RiskCheck dataclass."""
        check = RiskCheck(passed=True, reason="Test passed", risk_score=0.1)
        assert check.passed is True
        assert check.reason == "Test passed"
        assert check.risk_score == 0.1
        assert check.timestamp is not None


class TestIntegration:
    """Integration tests for risk management."""

    def test_full_trade_workflow(self):
        """Test complete trade risk assessment workflow."""
        rm = RiskManager(portfolio_value=5000.0)
        # VIXCircuitBreaker would be used for volatility checks in production

        # Simulate a CSP trade on F at $5 strike
        symbol = "F"
        strike = 5.0
        collateral = strike * 100  # $500

        # Check position size
        pos_check = rm.check_position_size(symbol, collateral)
        assert pos_check.passed is True

        # Check daily loss (assume max loss is premium received)
        loss_check = rm.check_daily_loss(15.0)  # $0.15 premium per share
        assert loss_check.passed is True

        # Check cash reserve
        cash_check = rm.check_cash_reserve(5000.0, collateral)
        assert cash_check.passed is True

        # Full approval
        approved, reason = rm.approve_trade(symbol, collateral, 5000.0, 15.0)
        assert approved is True

    def test_multiple_contracts_sizing(self):
        """Test sizing for multiple CSP contracts."""
        rm = RiskManager(portfolio_value=10000.0)

        # With $10K, $5 strike
        # Max contracts should be limited by position size (20%)
        max_contracts = rm.get_max_contracts(strike_price=5.0, cash_available=10000.0)

        # Position limit: $2000 (20% of $10K)
        # Collateral per: $500
        # Max: 4 contracts
        assert max_contracts == 4
