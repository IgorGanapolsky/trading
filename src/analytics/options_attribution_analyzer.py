"""
Options P&L Attribution Analyzer

Provides comprehensive attribution analysis for options trades:
1. Theta Decay Attribution - P/L from time decay
2. Delta Movement Attribution - P/L from underlying price movement
3. Vega (IV) Attribution - P/L from volatility changes
4. Gamma Attribution - Second-order delta effects
5. Unexplained P/L - Residual not explained by Greeks

Reference: Standard options P&L bridge analysis methodology
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GreeksSnapshot:
    """Point-in-time snapshot of option Greeks."""

    timestamp: datetime
    symbol: str
    underlying_price: float
    option_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    implied_volatility: float
    days_to_expiration: int


@dataclass
class AttributionResult:
    """P&L attribution breakdown for a position or portfolio."""

    period_start: datetime
    period_end: datetime
    total_pnl: float
    delta_pnl: float
    gamma_pnl: float
    theta_pnl: float
    vega_pnl: float
    unexplained_pnl: float
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def explained_pnl(self) -> float:
        """Total P/L explained by Greeks."""
        return self.delta_pnl + self.gamma_pnl + self.theta_pnl + self.vega_pnl

    @property
    def explained_pct(self) -> float:
        """Percentage of P/L explained by Greeks."""
        if self.total_pnl == 0:
            return 0.0
        return self.explained_pnl / self.total_pnl * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_pnl": self.total_pnl,
            "delta_pnl": self.delta_pnl,
            "gamma_pnl": self.gamma_pnl,
            "theta_pnl": self.theta_pnl,
            "vega_pnl": self.vega_pnl,
            "unexplained_pnl": self.unexplained_pnl,
            "explained_pnl": self.explained_pnl,
            "explained_pct": self.explained_pct,
            "details": self.details,
        }


class OptionsAttributionAnalyzer:
    """
    Analyze options P&L attribution by Greek component.

    P&L Bridge Formula:
    Total P/L = Delta P/L + Gamma P/L + Theta P/L + Vega P/L + Unexplained

    Where:
    - Delta P/L = Delta × ΔS (underlying price change)
    - Gamma P/L = 0.5 × Gamma × (ΔS)² (second-order effect)
    - Theta P/L = Theta × Δt (time decay)
    - Vega P/L = Vega × ΔIV (IV change)
    - Unexplained = Total - Sum(Greek P/L)
    """

    def __init__(self, data_dir: Path = Path("data")):
        """Initialize attribution analyzer."""
        self.data_dir = data_dir
        self.snapshots_dir = data_dir / "greeks_snapshots"
        self.attribution_dir = data_dir / "attribution"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.attribution_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Options Attribution Analyzer initialized")

    def save_greeks_snapshot(self, snapshot: GreeksSnapshot) -> None:
        """Save a Greeks snapshot for later attribution analysis."""
        date_str = snapshot.timestamp.strftime("%Y-%m-%d")
        filepath = self.snapshots_dir / f"{date_str}_{snapshot.symbol}.json"

        # Load existing snapshots for this date/symbol
        snapshots = []
        if filepath.exists():
            with open(filepath) as f:
                snapshots = json.load(f)

        # Add new snapshot
        snapshots.append(
            {
                "timestamp": snapshot.timestamp.isoformat(),
                "symbol": snapshot.symbol,
                "underlying_price": snapshot.underlying_price,
                "option_price": snapshot.option_price,
                "delta": snapshot.delta,
                "gamma": snapshot.gamma,
                "theta": snapshot.theta,
                "vega": snapshot.vega,
                "implied_volatility": snapshot.implied_volatility,
                "days_to_expiration": snapshot.days_to_expiration,
            }
        )

        with open(filepath, "w") as f:
            json.dump(snapshots, f, indent=2)

        logger.debug(f"Saved Greeks snapshot for {snapshot.symbol}")

    def calculate_single_position_attribution(
        self,
        entry_snapshot: GreeksSnapshot,
        exit_snapshot: GreeksSnapshot,
        contracts: int = 1,
        contract_multiplier: int = 100,
    ) -> AttributionResult:
        """
        Calculate P&L attribution for a single position.

        Args:
            entry_snapshot: Greeks at position entry
            exit_snapshot: Greeks at position exit
            contracts: Number of contracts
            contract_multiplier: Multiplier per contract (default 100)

        Returns:
            AttributionResult with P/L breakdown
        """
        multiplier = contracts * contract_multiplier

        # Calculate changes
        delta_s = exit_snapshot.underlying_price - entry_snapshot.underlying_price
        delta_t = (exit_snapshot.timestamp - entry_snapshot.timestamp).days / 365.0
        delta_iv = exit_snapshot.implied_volatility - entry_snapshot.implied_volatility

        # Use average Greeks for attribution (more accurate than just entry)
        avg_delta = (entry_snapshot.delta + exit_snapshot.delta) / 2
        avg_gamma = (entry_snapshot.gamma + exit_snapshot.gamma) / 2
        avg_theta = (entry_snapshot.theta + exit_snapshot.theta) / 2
        avg_vega = (entry_snapshot.vega + exit_snapshot.vega) / 2

        # Calculate P/L components
        # Delta P/L = Delta × ΔS
        delta_pnl = avg_delta * delta_s * multiplier

        # Gamma P/L = 0.5 × Gamma × (ΔS)²
        gamma_pnl = 0.5 * avg_gamma * (delta_s**2) * multiplier

        # Theta P/L = Theta × Δt (theta is daily, so adjust)
        days_held = (exit_snapshot.timestamp - entry_snapshot.timestamp).days
        theta_pnl = avg_theta * days_held * multiplier

        # Vega P/L = Vega × ΔIV (vega is per 1% IV change)
        vega_pnl = avg_vega * (delta_iv * 100) * multiplier

        # Total actual P/L
        price_change = exit_snapshot.option_price - entry_snapshot.option_price
        total_pnl = price_change * multiplier

        # Unexplained P/L
        explained_pnl = delta_pnl + gamma_pnl + theta_pnl + vega_pnl
        unexplained_pnl = total_pnl - explained_pnl

        return AttributionResult(
            period_start=entry_snapshot.timestamp,
            period_end=exit_snapshot.timestamp,
            total_pnl=total_pnl,
            delta_pnl=delta_pnl,
            gamma_pnl=gamma_pnl,
            theta_pnl=theta_pnl,
            vega_pnl=vega_pnl,
            unexplained_pnl=unexplained_pnl,
            details={
                "symbol": entry_snapshot.symbol,
                "contracts": contracts,
                "underlying_change": delta_s,
                "underlying_change_pct": delta_s / entry_snapshot.underlying_price * 100,
                "iv_change": delta_iv,
                "iv_change_pct": (
                    delta_iv / entry_snapshot.implied_volatility * 100
                    if entry_snapshot.implied_volatility
                    else 0
                ),
                "days_held": days_held,
                "entry_price": entry_snapshot.option_price,
                "exit_price": exit_snapshot.option_price,
                "entry_greeks": {
                    "delta": entry_snapshot.delta,
                    "gamma": entry_snapshot.gamma,
                    "theta": entry_snapshot.theta,
                    "vega": entry_snapshot.vega,
                    "iv": entry_snapshot.implied_volatility,
                },
                "exit_greeks": {
                    "delta": exit_snapshot.delta,
                    "gamma": exit_snapshot.gamma,
                    "theta": exit_snapshot.theta,
                    "vega": exit_snapshot.vega,
                    "iv": exit_snapshot.implied_volatility,
                },
            },
        )

    def calculate_daily_attribution(
        self,
        positions: list[dict[str, Any]],
        current_prices: dict[str, float],
        current_greeks: dict[str, dict[str, float]],
    ) -> AttributionResult:
        """
        Calculate P&L attribution for today across all positions.

        Args:
            positions: List of open positions with entry data
            current_prices: Current underlying prices
            current_greeks: Current Greeks by symbol

        Returns:
            Aggregated AttributionResult for the day
        """
        total_attribution = AttributionResult(
            period_start=datetime.now().replace(hour=9, minute=30, second=0),
            period_end=datetime.now(),
            total_pnl=0.0,
            delta_pnl=0.0,
            gamma_pnl=0.0,
            theta_pnl=0.0,
            vega_pnl=0.0,
            unexplained_pnl=0.0,
            details={"positions": []},
        )

        for position in positions:
            symbol = position.get("symbol", "")
            greeks = current_greeks.get(symbol, {})

            if not greeks:
                continue

            # Create entry snapshot from position data
            entry_snapshot = GreeksSnapshot(
                timestamp=datetime.fromisoformat(
                    position.get("entry_time", datetime.now().isoformat())
                ),
                symbol=symbol,
                underlying_price=position.get("entry_underlying_price", 0),
                option_price=position.get("entry_price", 0),
                delta=position.get("entry_delta", 0),
                gamma=position.get("entry_gamma", 0),
                theta=position.get("entry_theta", 0),
                vega=position.get("entry_vega", 0),
                implied_volatility=position.get("entry_iv", 0),
                days_to_expiration=position.get("entry_dte", 30),
            )

            # Create current snapshot
            underlying = position.get("underlying", symbol[:4])  # Extract underlying from OCC
            current_underlying_price = current_prices.get(
                underlying, entry_snapshot.underlying_price
            )

            exit_snapshot = GreeksSnapshot(
                timestamp=datetime.now(),
                symbol=symbol,
                underlying_price=current_underlying_price,
                option_price=greeks.get("mark", position.get("current_price", 0)),
                delta=greeks.get("delta", entry_snapshot.delta),
                gamma=greeks.get("gamma", entry_snapshot.gamma),
                theta=greeks.get("theta", entry_snapshot.theta),
                vega=greeks.get("vega", entry_snapshot.vega),
                implied_volatility=greeks.get(
                    "implied_volatility", entry_snapshot.implied_volatility
                ),
                days_to_expiration=greeks.get("dte", entry_snapshot.days_to_expiration - 1),
            )

            # Calculate attribution for this position
            contracts = position.get("contracts", 1)
            pos_attribution = self.calculate_single_position_attribution(
                entry_snapshot, exit_snapshot, contracts
            )

            # Aggregate
            total_attribution.total_pnl += pos_attribution.total_pnl
            total_attribution.delta_pnl += pos_attribution.delta_pnl
            total_attribution.gamma_pnl += pos_attribution.gamma_pnl
            total_attribution.theta_pnl += pos_attribution.theta_pnl
            total_attribution.vega_pnl += pos_attribution.vega_pnl
            total_attribution.unexplained_pnl += pos_attribution.unexplained_pnl

            total_attribution.details["positions"].append(pos_attribution.to_dict())

        return total_attribution

    def save_daily_attribution(self, attribution: AttributionResult) -> str:
        """Save daily attribution report."""
        date_str = date.today().isoformat()
        filepath = self.attribution_dir / f"{date_str}_attribution.json"

        with open(filepath, "w") as f:
            json.dump(attribution.to_dict(), f, indent=2)

        logger.info(f"Saved daily attribution to {filepath}")
        return str(filepath)

    def get_attribution_history(self, days: int = 30) -> list[AttributionResult]:
        """Load attribution history for analysis."""
        results = []
        files = sorted(self.attribution_dir.glob("*_attribution.json"))[-days:]

        for filepath in files:
            with open(filepath) as f:
                data = json.load(f)
                results.append(
                    AttributionResult(
                        period_start=datetime.fromisoformat(data["period_start"]),
                        period_end=datetime.fromisoformat(data["period_end"]),
                        total_pnl=data["total_pnl"],
                        delta_pnl=data["delta_pnl"],
                        gamma_pnl=data["gamma_pnl"],
                        theta_pnl=data["theta_pnl"],
                        vega_pnl=data["vega_pnl"],
                        unexplained_pnl=data["unexplained_pnl"],
                        details=data.get("details", {}),
                    )
                )

        return results

    def generate_attribution_report(self, days: int = 7) -> str:
        """
        Generate markdown report of P&L attribution.

        Args:
            days: Number of days to include

        Returns:
            Markdown formatted report
        """
        history = self.get_attribution_history(days)

        if not history:
            return "# P&L Attribution Report\n\nNo attribution data available."

        # Aggregate totals
        total_pnl = sum(r.total_pnl for r in history)
        total_delta = sum(r.delta_pnl for r in history)
        total_gamma = sum(r.gamma_pnl for r in history)
        total_theta = sum(r.theta_pnl for r in history)
        total_vega = sum(r.vega_pnl for r in history)
        total_unexplained = sum(r.unexplained_pnl for r in history)

        lines = [
            "# Options P&L Attribution Report",
            "",
            f"**Period**: Last {days} days",
            f"**Total P/L**: ${total_pnl:+,.2f}",
            "",
            "## Attribution Breakdown",
            "",
            "| Component | P/L | % of Total |",
            "|-----------|-----|------------|",
            f"| Delta (Directional) | ${total_delta:+,.2f} | {total_delta / total_pnl * 100 if total_pnl else 0:.1f}% |",
            f"| Gamma (Convexity) | ${total_gamma:+,.2f} | {total_gamma / total_pnl * 100 if total_pnl else 0:.1f}% |",
            f"| Theta (Time Decay) | ${total_theta:+,.2f} | {total_theta / total_pnl * 100 if total_pnl else 0:.1f}% |",
            f"| Vega (Volatility) | ${total_vega:+,.2f} | {total_vega / total_pnl * 100 if total_pnl else 0:.1f}% |",
            f"| Unexplained | ${total_unexplained:+,.2f} | {total_unexplained / total_pnl * 100 if total_pnl else 0:.1f}% |",
            "",
            "## Daily Breakdown",
            "",
            "| Date | Total | Delta | Theta | Vega | Unexplained |",
            "|------|-------|-------|-------|------|-------------|",
        ]

        for result in history[-7:]:  # Last 7 days
            date_str = result.period_end.strftime("%Y-%m-%d")
            lines.append(
                f"| {date_str} | ${result.total_pnl:+.2f} | "
                f"${result.delta_pnl:+.2f} | ${result.theta_pnl:+.2f} | "
                f"${result.vega_pnl:+.2f} | ${result.unexplained_pnl:+.2f} |"
            )

        # Key insights
        lines.extend(
            [
                "",
                "## Key Insights",
                "",
            ]
        )

        if total_theta > 0:
            lines.append(
                f"- **Theta Positive**: Earning ${total_theta:.2f} from time decay (good for premium selling)"
            )
        else:
            lines.append(
                f"- **Theta Negative**: Losing ${abs(total_theta):.2f} to time decay (review position sizing)"
            )

        if abs(total_delta) > abs(total_theta):
            lines.append(
                "- **Delta Dominant**: Directional moves driving most P/L (consider hedging)"
            )
        else:
            lines.append("- **Theta Dominant**: Time decay driving P/L (theta strategy working)")

        if abs(total_unexplained) > abs(total_pnl) * 0.2:
            lines.append(
                "- **High Unexplained**: Review Greeks data quality or consider other factors"
            )

        return "\n".join(lines)


def create_test_attribution() -> None:
    """Create test attribution data for demonstration."""
    analyzer = OptionsAttributionAnalyzer()

    # Create mock entry snapshot
    entry = GreeksSnapshot(
        timestamp=datetime(2025, 12, 9, 9, 30),
        symbol="SPY251220P00595000",
        underlying_price=600.00,
        option_price=2.50,
        delta=-0.25,
        gamma=0.02,
        theta=-0.05,
        vega=0.15,
        implied_volatility=0.18,
        days_to_expiration=10,
    )

    # Create mock exit snapshot (next day)
    exit_snap = GreeksSnapshot(
        timestamp=datetime(2025, 12, 10, 15, 30),
        symbol="SPY251220P00595000",
        underlying_price=598.00,  # Underlying dropped $2
        option_price=2.90,  # Option gained value (put)
        delta=-0.28,
        gamma=0.025,
        theta=-0.06,
        vega=0.16,
        implied_volatility=0.19,  # IV increased
        days_to_expiration=9,
    )

    # Calculate attribution
    result = analyzer.calculate_single_position_attribution(entry, exit_snap, contracts=1)

    print("\n=== Options P&L Attribution Demo ===\n")
    print(f"Symbol: {entry.symbol}")
    print(f"Underlying Change: ${entry.underlying_price} -> ${exit_snap.underlying_price}")
    print(f"Option Price Change: ${entry.option_price} -> ${exit_snap.option_price}")
    print(f"IV Change: {entry.implied_volatility:.1%} -> {exit_snap.implied_volatility:.1%}")
    print()
    print("P&L Attribution:")
    print(f"  Total P/L:      ${result.total_pnl:+.2f}")
    print(f"  Delta P/L:      ${result.delta_pnl:+.2f} (from price movement)")
    print(f"  Gamma P/L:      ${result.gamma_pnl:+.2f} (convexity gain)")
    print(f"  Theta P/L:      ${result.theta_pnl:+.2f} (time decay)")
    print(f"  Vega P/L:       ${result.vega_pnl:+.2f} (IV change)")
    print(f"  Unexplained:    ${result.unexplained_pnl:+.2f}")
    print()
    print(f"  Explained:      {result.explained_pct:.1f}% of total P/L explained by Greeks")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_test_attribution()
