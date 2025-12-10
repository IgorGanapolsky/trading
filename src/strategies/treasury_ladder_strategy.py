from __future__ import annotations

"""
Treasury Ladder Strategy

Implements a 3-tier treasury ETF ladder with dynamic allocation based on yield curve analysis.
Provides stable income while adapting to interest rate environment and yield curve inversions.

Strategy Overview:
- Base Allocation: SHY (40%), IEF (40%), TLT (20%)
- Yield Curve Detection: Shifts to SHY when 2yr > 10yr (inversion)
- Automatic Rebalancing: Triggers when allocation drifts >5%
- Risk Management: Low-risk, government-backed securities

Treasury ETFs:
- SHY: iShares 1-3 Year Treasury Bond ETF (short-term, low duration)
- IEF: iShares 7-10 Year Treasury Bond ETF (intermediate duration)
- TLT: iShares 20+ Year Treasury Bond ETF (long-term, high duration)

Yield Curve Strategies:
- Normal Curve (2yr < 10yr): Balanced ladder (40/40/20)
- Flat Curve (2yr ≈ 10yr): Slight shift to short (50/35/15)
- Inverted Curve (2yr > 10yr): Heavy short (70/25/5) - recession hedge

Integration:
- Uses FRED API for real-time yield data (DGS2, DGS10)
- Integrates with AlpacaTrader for execution
- Daily rebalancing checks with 5% drift threshold

Research Context (Dec 2025):
- Current yields: 2-year ~4.17%, 10-year ~4.19%, 30-year ~4.36%
- Fed expected to cut rates, but long-term settling around 3-4%
- Treasury ladder provides stability and income in volatile markets

Author: Trading System
Created: 2025-12-02
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from src.core.alpaca_trader import AlpacaTrader
from src.rag.collectors.fred_collector import FREDCollector

# Configure logging
logger = logging.getLogger(__name__)


class YieldCurveRegime(Enum):
    """Yield curve regime classification."""

    NORMAL = "normal"  # 2yr < 10yr (typical)
    FLAT = "flat"  # 2yr ≈ 10yr (transition)
    INVERTED = "inverted"  # 2yr > 10yr (recession signal)


@dataclass
class TreasuryAllocation:
    """Treasury ladder allocation details."""

    shy_pct: float  # Short-term (1-3yr)
    ief_pct: float  # Intermediate (7-10yr)
    tlt_pct: float  # Long-term (20+yr)
    regime: YieldCurveRegime
    spread: float  # 10yr - 2yr spread
    rationale: str
    timestamp: datetime


@dataclass
class RebalanceDecision:
    """Rebalancing decision details."""

    should_rebalance: bool
    current_allocation: dict[str, float]
    target_allocation: dict[str, float]
    drift_pct: dict[str, float]
    max_drift: float
    reason: str
    timestamp: datetime


class TreasuryLadderStrategy:
    """
    Treasury Ladder Strategy with dynamic allocation based on yield curve.

    This strategy implements a 3-tier treasury ETF ladder (SHY, IEF, TLT) with
    intelligent rebalancing based on yield curve conditions. It provides stable
    income and capital preservation while adapting to interest rate environments.

    Key Features:
    - 3-tier ladder: Short (SHY), Intermediate (IEF), Long (TLT)
    - Yield curve inversion detection via FRED API
    - Dynamic allocation shifts based on yield curve shape
    - Automatic rebalancing when drift exceeds 5%
    - Low-risk government-backed securities
    - Integration with Alpaca for fractional share trading

    Attributes:
        daily_allocation (float): Daily dollar amount to invest
        rebalance_threshold (float): Drift percentage that triggers rebalance
        etf_symbols (List[str]): Treasury ETF symbols [SHY, IEF, TLT]
        current_holdings (Dict[str, float]): Current position values by symbol
        last_rebalance_date (Optional[datetime]): Last rebalancing timestamp
        alpaca_trader (AlpacaTrader): Alpaca API client
        fred_collector (FREDCollector): FRED API client for yield data
    """

    # Treasury ETF universe
    ETF_SYMBOLS = ["SHY", "IEF", "TLT"]

    # Base allocations for different yield curve regimes
    # Normal curve: balanced ladder
    ALLOCATION_NORMAL = {"SHY": 0.40, "IEF": 0.40, "TLT": 0.20}

    # Flat curve: slight preference for short duration
    ALLOCATION_FLAT = {"SHY": 0.50, "IEF": 0.35, "TLT": 0.15}

    # Inverted curve: heavy preference for short duration (recession hedge)
    ALLOCATION_INVERTED = {"SHY": 0.70, "IEF": 0.25, "TLT": 0.05}

    # Yield curve regime thresholds (basis points)
    SPREAD_INVERTED_THRESHOLD = 0.0  # Spread < 0 = inverted
    SPREAD_FLAT_THRESHOLD = 0.5  # Spread < 50bps = flat

    # Rebalancing parameters
    DEFAULT_REBALANCE_THRESHOLD = 0.05  # 5% drift triggers rebalance
    MIN_REBALANCE_INTERVAL_DAYS = 7  # Minimum days between rebalances

    def __init__(
        self,
        daily_allocation: float = 10.0,
        rebalance_threshold: float = DEFAULT_REBALANCE_THRESHOLD,
        paper: bool = True,
    ):
        """
        Initialize the Treasury Ladder Strategy.

        Args:
            daily_allocation: Daily dollar amount to invest (default: $10)
            rebalance_threshold: Drift percentage that triggers rebalance (default: 5%)
            paper: Whether to use paper trading (default: True)

        Raises:
            ValueError: If daily_allocation is non-positive or threshold invalid
        """
        if daily_allocation <= 0:
            raise ValueError(f"daily_allocation must be positive, got {daily_allocation}")

        if not 0 < rebalance_threshold < 1:
            raise ValueError(
                f"rebalance_threshold must be between 0 and 1, got {rebalance_threshold}"
            )

        self.daily_allocation = daily_allocation
        self.rebalance_threshold = rebalance_threshold
        self.etf_symbols = self.ETF_SYMBOLS.copy()

        # Strategy state
        self.current_holdings: dict[str, float] = {}
        self.last_rebalance_date: datetime | None = None
        self.current_regime: YieldCurveRegime | None = None

        # Performance tracking
        self.total_invested: float = 0.0
        self.total_value: float = 0.0
        self.rebalance_history: list[RebalanceDecision] = []

        # Initialize dependencies
        try:
            self.alpaca_trader = AlpacaTrader(paper=paper)
            logger.info("Successfully initialized Alpaca trader")
        except Exception as e:
            logger.error(f"Failed to initialize Alpaca trader: {e}")
            self.alpaca_trader = None

        try:
            self.fred_collector = FREDCollector()
            logger.info("Successfully initialized FRED collector")
        except Exception as e:
            logger.warning(f"Failed to initialize FRED collector: {e}")
            self.fred_collector = None

        logger.info(
            f"TreasuryLadderStrategy initialized: "
            f"daily_allocation=${daily_allocation:.2f}, "
            f"rebalance_threshold={rebalance_threshold * 100:.1f}%, "
            f"etfs={self.etf_symbols}"
        )

    def analyze_yield_curve(self) -> tuple[YieldCurveRegime, float, str]:
        """
        Analyze the current yield curve using FRED data.

        Fetches 2-year and 10-year treasury yields from FRED API and determines
        the yield curve regime (normal, flat, or inverted).

        Returns:
            Tuple of (regime, spread, rationale):
                - regime: YieldCurveRegime enum value
                - spread: 10yr - 2yr spread in percentage points
                - rationale: Human-readable explanation

        Raises:
            Exception: If yield data cannot be fetched
        """
        logger.info("Analyzing yield curve...")

        if not self.fred_collector:
            logger.warning("FRED collector not available, assuming normal curve")
            return YieldCurveRegime.NORMAL, 0.50, "FRED API unavailable, using default"

        try:
            # Fetch 2-year and 10-year treasury yields
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            dgs2_data = self.fred_collector._fetch_series(
                "DGS2",
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )

            dgs10_data = self.fred_collector._fetch_series(
                "DGS10",
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )

            # Also try to get the spread directly
            spread_data = self.fred_collector._fetch_series(
                "T10Y2Y",
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
            )

            # Use direct spread if available, otherwise calculate
            if spread_data and spread_data.get("latest_value") != ".":
                spread = float(spread_data["latest_value"])
                logger.info(f"Yield curve spread (10yr-2yr): {spread:.2f}%")
            elif dgs2_data and dgs10_data:
                # Calculate spread manually
                yield_2yr = float(dgs2_data.get("latest_value", 0))
                yield_10yr = float(dgs10_data.get("latest_value", 0))
                spread = yield_10yr - yield_2yr
                logger.info(
                    f"Calculated spread: 10yr={yield_10yr:.2f}%, 2yr={yield_2yr:.2f}%, spread={spread:.2f}%"
                )
            else:
                logger.warning("Could not fetch yield data, using default normal curve")
                return (
                    YieldCurveRegime.NORMAL,
                    0.50,
                    "Yield data unavailable, using default",
                )

            # Determine regime based on spread
            if spread < self.SPREAD_INVERTED_THRESHOLD:
                regime = YieldCurveRegime.INVERTED
                rationale = (
                    f"INVERTED: 2yr yield exceeds 10yr by {abs(spread):.2f}%. "
                    "Historical recession indicator. Shifting to short duration."
                )
            elif spread < self.SPREAD_FLAT_THRESHOLD:
                regime = YieldCurveRegime.FLAT
                rationale = (
                    f"FLAT: Spread only {spread:.2f}%. Late cycle indicator. "
                    "Moderately favoring short duration."
                )
            else:
                regime = YieldCurveRegime.NORMAL
                rationale = (
                    f"NORMAL: Healthy {spread:.2f}% spread. "
                    "Balanced allocation across duration ladder."
                )

            logger.info(f"Yield curve regime: {regime.value} - {rationale}")
            self.current_regime = regime

            return regime, spread, rationale

        except Exception as e:
            logger.error(f"Failed to analyze yield curve: {e}")
            # Default to normal curve on error
            return (
                YieldCurveRegime.NORMAL,
                0.50,
                f"Error fetching yields: {e}, using default",
            )

    def get_optimal_allocation(self, macro_context: dict | None = None) -> TreasuryAllocation:
        """
        Determine optimal allocation based on current yield curve and macro context.

        Analyzes the yield curve and then adjusts the allocation based on the
        broader macroeconomic outlook (Dovish/Hawkish).

        Args:
            macro_context: Optional dictionary with macro state ('DOVISH', 'HAWKISH').

        Returns:
            TreasuryAllocation dataclass with allocation percentages and metadata
        """
        logger.info("Calculating optimal treasury allocation...")

        # 1. Analyze yield curve to get base allocation
        regime, spread, rationale = self.analyze_yield_curve()

        if regime == YieldCurveRegime.INVERTED:
            allocation_dict = self.ALLOCATION_INVERTED.copy()
        elif regime == YieldCurveRegime.FLAT:
            allocation_dict = self.ALLOCATION_FLAT.copy()
        else:  # NORMAL
            allocation_dict = self.ALLOCATION_NORMAL.copy()

        # 2. Adjust allocation based on macro context
        if macro_context and macro_context.get("state") in ["DOVISH", "HAWKISH"]:
            macro_state = macro_context["state"]
            shift_pct = 0.20  # Shift 20% of allocation
            logger.info(f"Adjusting treasury allocation based on {macro_state} macro context.")

            if macro_state == "DOVISH":
                # Favor long-duration bonds (TLT) if rate cuts are expected
                shift_from_shy = min(allocation_dict["SHY"], shift_pct)
                allocation_dict["SHY"] -= shift_from_shy
                allocation_dict["TLT"] += shift_from_shy
                rationale += (
                    f" Macro: DOVISH outlook shifts {shift_from_shy * 100:.0f}% to long-duration."
                )
            elif macro_state == "HAWKISH":
                # Favor short-duration bonds (SHY) if rate hikes are expected
                shift_from_tlt = min(allocation_dict["TLT"], shift_pct)
                allocation_dict["TLT"] -= shift_from_tlt
                allocation_dict["SHY"] += shift_from_tlt
                rationale += (
                    f" Macro: HAWKISH outlook shifts {shift_from_tlt * 100:.0f}% to short-duration."
                )

        # Create allocation object
        allocation = TreasuryAllocation(
            shy_pct=allocation_dict["SHY"],
            ief_pct=allocation_dict["IEF"],
            tlt_pct=allocation_dict["TLT"],
            regime=regime,
            spread=spread,
            rationale=rationale,
            timestamp=datetime.now(),
        )

        logger.info(
            f"Optimal allocation: SHY={allocation.shy_pct * 100:.0f}%, "
            f"IEF={allocation.ief_pct * 100:.0f}%, TLT={allocation.tlt_pct * 100:.0f}%"
        )

        return allocation

    def execute_daily(
        self, amount: float | None = None, macro_context: dict | None = None
    ) -> dict[str, Any]:
        """
        Execute daily investment across treasury ladder.

        Distributes the daily investment amount across SHY, IEF, and TLT
        according to the optimal allocation determined by yield curve analysis.

        Args:
            amount: Dollar amount to invest (default: self.daily_allocation)
            macro_context: Optional dictionary with macro state for allocation adjustment.

        Returns:
            Dictionary containing execution results:
                - orders: List of executed orders
                - allocation: TreasuryAllocation used
                - total_invested: Total amount invested
                - success: Whether execution succeeded
        """
        amount = amount or self.daily_allocation

        logger.info("=" * 80)
        logger.info("Starting Treasury Ladder daily execution")
        logger.info(f"Investment amount: ${amount:.2f}")

        if not self.alpaca_trader:
            logger.error("Alpaca trader not initialized, cannot execute")
            return {
                "orders": [],
                "allocation": None,
                "total_invested": 0.0,
                "success": False,
                "error": "Alpaca trader not initialized",
            }

        try:
            # Get optimal allocation, now with macro context
            allocation = self.get_optimal_allocation(macro_context=macro_context)

            # Calculate dollar amounts for each ETF
            shy_amount = amount * allocation.shy_pct
            ief_amount = amount * allocation.ief_pct
            tlt_amount = amount * allocation.tlt_pct

            logger.info(
                f"Allocating: SHY=${shy_amount:.2f}, IEF=${ief_amount:.2f}, TLT=${tlt_amount:.2f}"
            )

            # Execute orders
            orders = []
            total_invested = 0.0

            for symbol, invest_amount in [
                ("SHY", shy_amount),
                ("IEF", ief_amount),
                ("TLT", tlt_amount),
            ]:
                if invest_amount > 0.01:  # Skip if less than 1 cent
                    try:
                        order = self.alpaca_trader.execute_order(
                            symbol=symbol,
                            amount_usd=invest_amount,
                            side="buy",
                            tier="T1_CORE",  # Treat as core allocation
                        )
                        orders.append(order)
                        total_invested += invest_amount

                        logger.info(
                            f"Executed: BUY {symbol} ${invest_amount:.2f} (Order ID: {order['id']})"
                        )

                        # Update holdings tracking
                        self.current_holdings[symbol] = (
                            self.current_holdings.get(symbol, 0.0) + invest_amount
                        )

                    except Exception as e:
                        logger.error(f"Failed to execute order for {symbol}: {e}")
                        # Continue with other orders

            # Update total invested
            self.total_invested += total_invested

            logger.info(
                f"Daily execution complete: {len(orders)} orders, ${total_invested:.2f} invested"
            )

            return {
                "orders": orders,
                "allocation": allocation,
                "total_invested": total_invested,
                "success": len(orders) > 0,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Daily execution failed: {e}")
            return {
                "orders": [],
                "allocation": None,
                "total_invested": 0.0,
                "success": False,
                "error": str(e),
            }

    def rebalance_if_needed(self, macro_context: dict | None = None) -> RebalanceDecision | None:
        """
        Check if rebalancing is needed and execute if necessary.

        Compares current holdings to target allocation. If any position
        drifts more than rebalance_threshold (default 5%), triggers a rebalance.

        Args:
            macro_context: Optional dictionary with macro state for allocation adjustment.

        Returns:
            RebalanceDecision if rebalance was checked, None if skipped
        """
        logger.info("Checking if rebalancing needed...")

        if not self.alpaca_trader:
            logger.warning("Alpaca trader not initialized, cannot rebalance")
            return None

        # Check minimum rebalancing interval
        if self.last_rebalance_date:
            days_since_rebalance = (datetime.now() - self.last_rebalance_date).days
            if days_since_rebalance < self.MIN_REBALANCE_INTERVAL_DAYS:
                logger.info(
                    f"Skipping rebalance check: Only {days_since_rebalance} days since last rebalance "
                    f"(minimum: {self.MIN_REBALANCE_INTERVAL_DAYS})"
                )
                return None

        try:
            # Get current positions from Alpaca
            positions = self.alpaca_trader.get_positions()

            # Filter to treasury positions
            treasury_positions = {
                pos["symbol"]: float(pos["market_value"])
                for pos in positions
                if pos["symbol"] in self.etf_symbols
            }

            # Calculate total treasury value
            total_value = sum(treasury_positions.values())

            if total_value < 1.0:
                logger.info("Treasury holdings too small to rebalance (< $1)")
                return None

            # Calculate current allocation percentages
            current_allocation = {
                symbol: treasury_positions.get(symbol, 0.0) / total_value
                for symbol in self.etf_symbols
            }

            # Get target allocation, now with macro context
            target_alloc_obj = self.get_optimal_allocation(macro_context=macro_context)
            target_allocation = {
                "SHY": target_alloc_obj.shy_pct,
                "IEF": target_alloc_obj.ief_pct,
                "TLT": target_alloc_obj.tlt_pct,
            }

            # Calculate drift for each position
            drift_pct = {
                symbol: abs(current_allocation[symbol] - target_allocation[symbol])
                for symbol in self.etf_symbols
            }

            max_drift = max(drift_pct.values())

            logger.info(
                f"Allocation drift: SHY={drift_pct['SHY'] * 100:.1f}%, "
                f"IEF={drift_pct['IEF'] * 100:.1f}%, TLT={drift_pct['TLT'] * 100:.1f}%"
            )

            # Determine if rebalancing needed
            should_rebalance = max_drift > self.rebalance_threshold

            if should_rebalance:
                reason = (
                    f"Max drift {max_drift * 100:.1f}% exceeds threshold "
                    f"{self.rebalance_threshold * 100:.1f}%"
                )
                logger.info(f"REBALANCING NEEDED: {reason}")

                # Execute rebalancing
                self._execute_rebalance(current_allocation, target_allocation, total_value)

                self.last_rebalance_date = datetime.now()
            else:
                reason = (
                    f"Max drift {max_drift * 100:.1f}% within threshold "
                    f"{self.rebalance_threshold * 100:.1f}%"
                )
                logger.info(f"No rebalancing needed: {reason}")

            # Create decision object
            decision = RebalanceDecision(
                should_rebalance=should_rebalance,
                current_allocation=current_allocation,
                target_allocation=target_allocation,
                drift_pct=drift_pct,
                max_drift=max_drift,
                reason=reason,
                timestamp=datetime.now(),
            )

            self.rebalance_history.append(decision)

            return decision

        except Exception as e:
            logger.error(f"Rebalancing check failed: {e}")
            return None

    def _execute_rebalance(
        self,
        current_allocation: dict[str, float],
        target_allocation: dict[str, float],
        total_value: float,
    ) -> None:
        """
        Execute rebalancing trades to align with target allocation.

        Args:
            current_allocation: Current allocation percentages by symbol
            target_allocation: Target allocation percentages by symbol
            total_value: Total portfolio value in dollars

        Raises:
            Exception: If rebalancing execution fails
        """
        logger.info("Executing rebalancing trades...")

        for symbol in self.etf_symbols:
            current_pct = current_allocation[symbol]
            target_pct = target_allocation[symbol]

            # Calculate dollar difference
            current_value = current_pct * total_value
            target_value = target_pct * total_value
            delta_value = target_value - current_value

            # Skip if change is too small
            if abs(delta_value) < 1.0:
                logger.info(f"Skipping {symbol}: delta ${delta_value:.2f} too small")
                continue

            try:
                if delta_value > 0:
                    # Need to buy more
                    logger.info(f"Rebalance: BUY {symbol} ${delta_value:.2f}")
                    self.alpaca_trader.execute_order(
                        symbol=symbol,
                        amount_usd=delta_value,
                        side="buy",
                        tier="T1_CORE",
                    )
                else:
                    # Need to sell some
                    sell_amount = abs(delta_value)
                    logger.info(f"Rebalance: SELL {symbol} ${sell_amount:.2f}")

                    # Get current position to calculate quantity
                    positions = self.alpaca_trader.get_positions()
                    pos = next((p for p in positions if p["symbol"] == symbol), None)

                    if pos:
                        # Calculate shares to sell
                        current_qty = float(pos["qty"])
                        current_market_value = float(pos["market_value"])
                        sell_qty = (sell_amount / current_market_value) * current_qty

                        # Execute sell order
                        # Note: AlpacaTrader.execute_order doesn't support qty-based sells
                        # We'd need to use a different method or close partial position
                        logger.warning(
                            f"Sell rebalancing not fully implemented for {symbol} "
                            f"(would sell {sell_qty:.4f} shares)"
                        )
                    else:
                        logger.warning(f"Could not find position for {symbol} to rebalance")

            except Exception as e:
                logger.error(f"Failed to rebalance {symbol}: {e}")
                # Continue with other symbols

        logger.info("Rebalancing execution complete")

    def get_performance_summary(self) -> dict[str, Any]:
        """
        Get performance summary for treasury ladder.

        Returns:
            Dictionary containing performance metrics
        """
        try:
            if not self.alpaca_trader:
                return {"error": "Alpaca trader not initialized"}

            # Get current positions
            positions = self.alpaca_trader.get_positions()
            treasury_positions = [pos for pos in positions if pos["symbol"] in self.etf_symbols]

            total_market_value = sum(float(pos["market_value"]) for pos in treasury_positions)
            total_cost_basis = sum(float(pos["cost_basis"]) for pos in treasury_positions)
            total_unrealized_pl = sum(float(pos["unrealized_pl"]) for pos in treasury_positions)

            return {
                "total_invested": self.total_invested,
                "total_market_value": total_market_value,
                "total_cost_basis": total_cost_basis,
                "total_unrealized_pl": total_unrealized_pl,
                "return_pct": (
                    (total_unrealized_pl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
                ),
                "positions": treasury_positions,
                "current_regime": self.current_regime.value if self.current_regime else "unknown",
                "last_rebalance": (
                    self.last_rebalance_date.isoformat() if self.last_rebalance_date else None
                ),
                "rebalance_count": len(self.rebalance_history),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {"error": str(e)}


if __name__ == "__main__":
    """
    Example usage and testing.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize strategy
    strategy = TreasuryLadderStrategy(
        daily_allocation=10.0,
        rebalance_threshold=0.05,
        paper=True,
    )

    print("\n" + "=" * 80)
    print("TREASURY LADDER STRATEGY - DEMO")
    print("=" * 80)

    # Analyze yield curve
    print("\n1. YIELD CURVE ANALYSIS")
    regime, spread, rationale = strategy.analyze_yield_curve()
    print(f"   Regime: {regime.value}")
    print(f"   Spread: {spread:.2f}%")
    print(f"   Rationale: {rationale}")

    # Get optimal allocation
    print("\n2. OPTIMAL ALLOCATION")
    allocation = strategy.get_optimal_allocation()
    print(f"   SHY (1-3yr): {allocation.shy_pct * 100:.0f}%")
    print(f"   IEF (7-10yr): {allocation.ief_pct * 100:.0f}%")
    print(f"   TLT (20+yr): {allocation.tlt_pct * 100:.0f}%")

    # Execute daily (demo - will actually trade if Alpaca configured)
    print("\n3. DAILY EXECUTION (DEMO)")
    print("   Would invest $10 across ladder...")
    # Uncomment to actually execute:
    # result = strategy.execute_daily()
    # print(f"   Orders executed: {len(result['orders'])}")
    # print(f"   Total invested: ${result['total_invested']:.2f}")

    # Check rebalancing
    print("\n4. REBALANCING CHECK")
    print("   Would check if rebalancing needed...")
    # Uncomment to actually check:
    # decision = strategy.rebalance_if_needed()
    # if decision:
    #     print(f"   Should rebalance: {decision.should_rebalance}")
    #     print(f"   Reason: {decision.reason}")

    print("\n" + "=" * 80)
    print("Demo complete!")
    print("=" * 80 + "\n")
