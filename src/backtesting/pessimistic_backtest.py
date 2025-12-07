"""
Pessimistic Backtest Mode - Stress-test strategies with worst-case assumptions.

This module implements a "pessimistic" backtest mode that:
- Doubles the bid-ask spread (2x slippage)
- Triples transaction fees (3x fees)
- Adds adverse execution timing
- Models worst-case market impact

If a strategy is profitable under pessimistic assumptions, it has a real edge.
If not, it's likely curve-fitted or relying on unrealistic execution assumptions.

Author: Trading System
Created: 2025-12-04
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PessimisticConfig:
    """Configuration for pessimistic backtest mode."""

    # Slippage multipliers
    spread_multiplier: float = 2.0  # 2x normal spread
    impact_multiplier: float = 2.0  # 2x market impact
    latency_multiplier: float = 2.0  # 2x latency slippage

    # Fee multipliers
    fee_multiplier: float = 3.0  # 3x normal fees

    # Execution assumptions
    fill_rate: float = 0.90  # Only 90% of orders fill at expected price
    adverse_selection_bps: float = 5.0  # Additional slippage from adverse selection

    # Volatility assumptions
    volatility_multiplier: float = 1.5  # Assume 50% higher volatility

    def __post_init__(self):
        """Validate configuration."""
        assert self.spread_multiplier >= 1.0, "Spread multiplier must be >= 1"
        assert self.fee_multiplier >= 1.0, "Fee multiplier must be >= 1"
        assert 0 < self.fill_rate <= 1.0, "Fill rate must be between 0 and 1"


class PessimisticSlippageModel:
    """
    Pessimistic slippage model that assumes worst-case execution.

    This wraps the normal slippage model and applies pessimistic multipliers.
    """

    # Conservative spreads (2x normal)
    PESSIMISTIC_SPREADS = {
        "SPY": 2,  # Normally 1 bps, pessimistic 2 bps
        "QQQ": 2,
        "IWM": 4,  # Normally 2 bps, pessimistic 4 bps
        "VOO": 4,
        "LARGE_CAP": 10,  # Normally 5 bps
        "MID_CAP": 20,  # Normally 10 bps
        "SMALL_CAP": 40,  # Normally 20 bps
        "OPTIONS": 200,  # Normally 100 bps
    }

    def __init__(self, config: PessimisticConfig | None = None):
        """
        Initialize pessimistic slippage model.

        Args:
            config: PessimisticConfig with multipliers (uses defaults if None)
        """
        self.config = config or PessimisticConfig()

        logger.warning(
            f"🔴 PESSIMISTIC MODE ENABLED: "
            f"spread={self.config.spread_multiplier}x, "
            f"fees={self.config.fee_multiplier}x, "
            f"fill_rate={self.config.fill_rate:.0%}"
        )

    def calculate_pessimistic_slippage(
        self,
        price: float,
        quantity: float,
        side: str,
        symbol: str | None = None,
        volume: float | None = None,
        volatility: float | None = None,
    ) -> dict[str, Any]:
        """
        Calculate slippage with pessimistic assumptions.

        Args:
            price: Base price
            quantity: Number of shares
            side: "buy" or "sell"
            symbol: Ticker symbol
            volume: Average daily volume
            volatility: Daily volatility

        Returns:
            Dict with executed_price, slippage_bps, slippage_amount, components
        """
        # Get pessimistic spread
        spread_bps = self._get_pessimistic_spread(symbol)

        # Calculate market impact with pessimistic assumptions
        impact_bps = 0.0
        if volume and volume > 0:
            notional = price * quantity
            adv_notional = price * volume
            participation_rate = min(notional / adv_notional, 0.1)

            # Square-root impact with pessimistic multiplier
            import numpy as np

            impact_bps = (
                10.0  # Base impact
                * np.sqrt(participation_rate)
                * 100
                * self.config.impact_multiplier
            )

        # Add adverse selection (informed traders moving against you)
        adverse_bps = self.config.adverse_selection_bps

        # Volatility adjustment
        vol_multiplier = 1.0
        if volatility:
            baseline_vol = 0.015
            vol_ratio = volatility / baseline_vol
            vol_multiplier = 1 + (vol_ratio - 1) * 0.5 * self.config.volatility_multiplier
            vol_multiplier = max(1.0, min(3.0, vol_multiplier))

        # Total slippage in bps
        total_bps = (spread_bps + impact_bps + adverse_bps) * vol_multiplier

        # Calculate executed price
        direction = 1 if side.lower() == "buy" else -1
        slippage_pct = total_bps / 10000
        slippage_amount = price * slippage_pct * direction
        executed_price = price + slippage_amount

        return {
            "base_price": price,
            "executed_price": executed_price,
            "slippage_bps": total_bps,
            "slippage_pct": slippage_pct * 100,
            "slippage_amount": slippage_amount * quantity,
            "components": {
                "spread_bps": spread_bps,
                "impact_bps": impact_bps,
                "adverse_selection_bps": adverse_bps,
                "volatility_multiplier": vol_multiplier,
            },
        }

    def _get_pessimistic_spread(self, symbol: str | None) -> float:
        """Get pessimistic spread for symbol."""
        if symbol and symbol.upper() in self.PESSIMISTIC_SPREADS:
            return self.PESSIMISTIC_SPREADS[symbol.upper()]
        # Default: 10 bps (2x the normal 5 bps default)
        return 10.0

    def calculate_pessimistic_fees(
        self,
        trade_amount: float,
        is_option: bool = False,
    ) -> float:
        """
        Calculate transaction fees with pessimistic assumptions.

        Args:
            trade_amount: Notional trade amount
            is_option: Whether this is an options trade

        Returns:
            Total fee amount (already multiplied by fee_multiplier)
        """
        # Base fees (typical Alpaca fees are near-zero for stocks)
        # But we model realistic fees for stress testing
        if is_option:
            # Options: $0.65/contract, assume 1 contract per $1000
            contracts = max(1, trade_amount / 1000)
            base_fee = contracts * 0.65
        else:
            # Stocks: ~$0.003/share average, assume $50/share average price
            shares = trade_amount / 50
            base_fee = shares * 0.003

        # SEC fee: $0.0000278/dollar (only on sells, but we apply to all for pessimism)
        sec_fee = trade_amount * 0.0000278

        # FINRA TAF: $0.000145/share, capped at $7.27
        shares = trade_amount / 50  # Assume $50/share
        finra_fee = min(shares * 0.000145, 7.27)

        # Total with pessimistic multiplier
        total_fee = (base_fee + sec_fee + finra_fee) * self.config.fee_multiplier

        return total_fee


def create_pessimistic_backtest_config(
    base_slippage_bps: float = 5.0,
    base_impact_bps: float = 10.0,
) -> dict[str, Any]:
    """
    Create configuration dict for pessimistic backtest engine.

    This returns settings that can be passed to BacktestEngine.

    Returns:
        Dict with pessimistic backtest settings
    """
    config = PessimisticConfig()

    return {
        "enable_slippage": True,
        "slippage_bps": base_slippage_bps * config.spread_multiplier,
        "market_impact_bps": base_impact_bps * config.impact_multiplier,
        "pessimistic_mode": True,
        "pessimistic_config": {
            "spread_multiplier": config.spread_multiplier,
            "fee_multiplier": config.fee_multiplier,
            "fill_rate": config.fill_rate,
            "adverse_selection_bps": config.adverse_selection_bps,
        },
    }


def run_pessimistic_validation(
    normal_results: dict[str, Any],
    pessimistic_results: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare normal vs pessimistic backtest results.

    Args:
        normal_results: Results from normal backtest
        pessimistic_results: Results from pessimistic backtest

    Returns:
        Validation report with pass/fail status
    """
    normal_pnl = normal_results.get("total_pnl", 0)
    pessimistic_pnl = pessimistic_results.get("total_pnl", 0)

    normal_sharpe = normal_results.get("sharpe_ratio", 0)
    pessimistic_sharpe = pessimistic_results.get("sharpe_ratio", 0)

    normal_win_rate = normal_results.get("win_rate", 0)
    pessimistic_win_rate = pessimistic_results.get("win_rate", 0)

    # Calculate degradation
    pnl_degradation = (
        (normal_pnl - pessimistic_pnl) / abs(normal_pnl) * 100 if normal_pnl != 0 else 0
    )

    sharpe_degradation = (
        (normal_sharpe - pessimistic_sharpe) / abs(normal_sharpe) * 100 if normal_sharpe != 0 else 0
    )

    win_rate_degradation = normal_win_rate - pessimistic_win_rate

    # Validation criteria
    # Strategy passes if:
    # 1. Still profitable under pessimistic assumptions
    # 2. Sharpe doesn't drop below 0.5
    # 3. Win rate doesn't drop more than 10%
    is_profitable = pessimistic_pnl > 0
    sharpe_acceptable = pessimistic_sharpe >= 0.5
    win_rate_acceptable = win_rate_degradation <= 10

    passes_validation = is_profitable and sharpe_acceptable and win_rate_acceptable

    return {
        "passes": passes_validation,
        "normal": {
            "pnl": normal_pnl,
            "sharpe": normal_sharpe,
            "win_rate": normal_win_rate,
        },
        "pessimistic": {
            "pnl": pessimistic_pnl,
            "sharpe": pessimistic_sharpe,
            "win_rate": pessimistic_win_rate,
        },
        "degradation": {
            "pnl_pct": pnl_degradation,
            "sharpe_pct": sharpe_degradation,
            "win_rate_points": win_rate_degradation,
        },
        "validation": {
            "is_profitable": is_profitable,
            "sharpe_acceptable": sharpe_acceptable,
            "win_rate_acceptable": win_rate_acceptable,
        },
        "recommendation": (
            "✅ Strategy has robust edge - proceed with live trading"
            if passes_validation
            else "⚠️ Strategy may be overfitted - review execution assumptions"
        ),
    }


if __name__ == "__main__":
    """Demo the pessimistic backtest mode."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("PESSIMISTIC BACKTEST MODE DEMO")
    print("=" * 80)

    # Create pessimistic config
    config = PessimisticConfig()
    print("\nPessimistic Configuration:")
    print(f"  Spread Multiplier: {config.spread_multiplier}x")
    print(f"  Fee Multiplier: {config.fee_multiplier}x")
    print(f"  Fill Rate: {config.fill_rate:.0%}")
    print(f"  Adverse Selection: {config.adverse_selection_bps} bps")

    # Create pessimistic slippage model
    model = PessimisticSlippageModel(config)

    # Test scenarios
    scenarios = [
        {"symbol": "SPY", "price": 450.0, "qty": 100, "side": "buy"},
        {"symbol": "QQQ", "price": 380.0, "qty": 50, "side": "buy"},
        {"symbol": "NVDA", "price": 500.0, "qty": 20, "side": "sell", "volatility": 0.03},
    ]

    print("\n" + "=" * 80)
    print("SLIPPAGE ANALYSIS (Pessimistic)")
    print("=" * 80)

    for s in scenarios:
        result = model.calculate_pessimistic_slippage(
            price=s["price"],
            quantity=s["qty"],
            side=s["side"],
            symbol=s["symbol"],
            volatility=s.get("volatility", 0.02),
        )

        print(f"\n{s['symbol']} ({s['side'].upper()}):")
        print(f"  Base Price: ${s['price']:.2f}")
        print(f"  Executed Price: ${result['executed_price']:.4f}")
        print(f"  Slippage: {result['slippage_bps']:.2f} bps (${result['slippage_amount']:.2f})")
        print(f"  Components: {result['components']}")

    # Demo validation report
    print("\n" + "=" * 80)
    print("VALIDATION COMPARISON DEMO")
    print("=" * 80)

    # Simulate normal vs pessimistic results
    normal = {"total_pnl": 5000, "sharpe_ratio": 1.8, "win_rate": 62}
    pessimistic = {"total_pnl": 2500, "sharpe_ratio": 0.9, "win_rate": 55}

    validation = run_pessimistic_validation(normal, pessimistic)
    print(f"\nValidation Result: {'PASS' if validation['passes'] else 'FAIL'}")
    print(f"Recommendation: {validation['recommendation']}")
    print("\nDegradation:")
    print(f"  P/L: -{validation['degradation']['pnl_pct']:.1f}%")
    print(f"  Sharpe: -{validation['degradation']['sharpe_pct']:.1f}%")
    print(f"  Win Rate: -{validation['degradation']['win_rate_points']:.1f} points")
