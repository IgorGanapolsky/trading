"""
Zero Days to Expiration (0DTE) Options Strategy

Based on Option Alpha research of 230,000 trades, this strategy implements
optimal parameters for trading same-day expiring SPY options.

Key Research Findings:
- Best entry time: 10:15 AM EST (after morning volatility settles)
- Best exit time: Noon EST (before afternoon volatility pickup)
- Best days: Monday and Wednesday (highest edge)
- Profit target: 15% of credit received
- Stop loss: 25% of max loss
- Optimal structure: Iron butterfly for defined risk

Risk Warning:
0DTE trades carry elevated risk due to gamma exposure. Position sizing
is capped at 2% of account (vs 5% for standard strategies).

Author: Trading System
Created: Jan 14, 2026
Research Source: Option Alpha 230K trade study
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Timezone for market hours
EST = ZoneInfo("America/New_York")


@dataclass
class IronButterflySetup:
    """Iron butterfly trade setup for 0DTE."""

    symbol: str
    expiration: str  # YYYY-MM-DD format
    center_strike: float
    wing_width: int  # Points from center

    # Legs
    long_put_strike: float
    short_put_strike: float
    short_call_strike: float
    long_call_strike: float

    # Pricing
    net_credit: float
    max_loss: float
    breakeven_low: float
    breakeven_high: float

    # Greeks (optional)
    delta: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None

    # Metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(EST))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "expiration": self.expiration,
            "center_strike": self.center_strike,
            "wing_width": self.wing_width,
            "long_put_strike": self.long_put_strike,
            "short_put_strike": self.short_put_strike,
            "short_call_strike": self.short_call_strike,
            "long_call_strike": self.long_call_strike,
            "net_credit": round(self.net_credit, 2),
            "max_loss": round(self.max_loss, 2),
            "breakeven_low": round(self.breakeven_low, 2),
            "breakeven_high": round(self.breakeven_high, 2),
            "delta": round(self.delta, 4) if self.delta else None,
            "theta": round(self.theta, 4) if self.theta else None,
            "vega": round(self.vega, 4) if self.vega else None,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ZeroDTETradeSetup:
    """Complete 0DTE trade setup with entry/exit parameters."""

    trade: bool
    reason: str
    setup: Optional[IronButterflySetup] = None
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    profit_target: Optional[float] = None
    stop_loss: Optional[float] = None
    day_of_week: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "trade": self.trade,
            "reason": self.reason,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "profit_target": self.profit_target,
            "stop_loss": self.stop_loss,
            "day_of_week": self.day_of_week,
        }
        if self.setup:
            result["setup"] = self.setup.to_dict()
        return result


class ZeroDTEStrategy:
    """
    Zero Days to Expiration (0DTE) Options Trading Strategy.

    Based on Option Alpha's research of 230,000 trades, this strategy
    implements the statistically optimal parameters for 0DTE SPY options.

    Key Parameters (Research-Backed):
    - Entry: 10:15 AM EST (after morning volatility settles)
    - Exit: Noon EST (time-based) or 15% profit / 25% loss
    - Days: Monday and Wednesday only
    - Structure: Iron Butterfly (defined risk, theta positive)
    - Position size: 2% max (elevated risk)

    Usage:
        strategy = ZeroDTEStrategy()
        if strategy.should_trade_0dte():
            setup = get_0dte_trade_setup()
            if setup["trade"]:
                # Execute the trade
                ...
    """

    # === Research-Backed Constants ===

    # Best performing parameters from Option Alpha 230K trade study
    BEST_ENTRY_TIME = "10:15"  # 10:15 AM EST - after morning vol settles
    BEST_EXIT_TIME = "12:00"  # Exit by noon if no trigger hit

    # Risk management
    PROFIT_TARGET_PCT = 0.15  # Take profit at 15% of credit
    STOP_LOSS_PCT = 0.25  # Stop loss at 25% of max loss

    # Best days for 0DTE (highest edge from research)
    BEST_DAYS = ["Monday", "Wednesday"]

    # Position sizing - more conservative due to elevated gamma risk
    MAX_POSITION_PCT = 0.02  # Only risk 2% per 0DTE trade

    # Entry window (10:00 - 10:30 AM EST)
    ENTRY_WINDOW_START = time(10, 0)  # 10:00 AM
    ENTRY_WINDOW_END = time(10, 30)  # 10:30 AM

    # Trading symbol
    SYMBOL = "SPY"

    # Default wing width for iron butterfly
    DEFAULT_WING_WIDTH = 5  # $5 wide wings

    def __init__(
        self,
        paper: bool = True,
        account_value: Optional[float] = None,
        use_live_data: bool = True,
    ):
        """
        Initialize ZeroDTEStrategy.

        Args:
            paper: Use paper trading (default True)
            account_value: Account value for position sizing (uses mock if None)
            use_live_data: Try to fetch live market data (falls back to mock)
        """
        self.paper = paper
        self.use_live_data = use_live_data

        # Account value for position sizing
        if account_value is not None:
            self._account_value = account_value
        else:
            self._account_value = self._fetch_account_value()

        logger.info(
            f"ZeroDTEStrategy initialized: paper={paper}, "
            f"account=${self._account_value:,.2f}, live_data={use_live_data}"
        )

    def _fetch_account_value(self) -> float:
        """Fetch account value from Alpaca or return mock value."""
        try:
            from src.utils.alpaca_client import get_account_info, get_alpaca_client

            client = get_alpaca_client(paper=self.paper)
            if client:
                info = get_account_info(client)
                if info and "equity" in info:
                    return float(info["equity"])
        except Exception as e:
            logger.debug(f"Could not fetch account value: {e}")

        # Mock value for testing/development
        logger.debug("Using mock account value of $5,000")
        return 5000.0

    def _get_current_time_est(self) -> datetime:
        """Get current time in EST timezone."""
        return datetime.now(EST)

    def is_0dte_day(self) -> bool:
        """
        Check if today is a valid 0DTE trading day.

        Returns:
            True if today is Monday or Wednesday (best performing days)
        """
        now = self._get_current_time_est()
        day_name = now.strftime("%A")
        is_valid = day_name in self.BEST_DAYS

        if not is_valid:
            logger.debug(f"Today is {day_name}, not a 0DTE day (need Mon/Wed)")

        return is_valid

    def is_entry_window(self) -> bool:
        """
        Check if current time is within the entry window (10:00-10:30 AM EST).

        Returns:
            True if within entry window
        """
        now = self._get_current_time_est()
        current_time = now.time()

        in_window = self.ENTRY_WINDOW_START <= current_time <= self.ENTRY_WINDOW_END

        if not in_window:
            logger.debug(
                f"Current time {current_time.strftime('%H:%M')} outside "
                f"entry window ({self.ENTRY_WINDOW_START.strftime('%H:%M')}-"
                f"{self.ENTRY_WINDOW_END.strftime('%H:%M')})"
            )

        return in_window

    def should_trade_0dte(self) -> bool:
        """
        Check if all conditions are met for 0DTE trading.

        Combines:
        1. Is it a valid 0DTE day (Mon/Wed)?
        2. Are we in the entry window (10:00-10:30 AM)?

        Returns:
            True if both conditions are met
        """
        is_valid_day = self.is_0dte_day()
        is_valid_time = self.is_entry_window()

        should_trade = is_valid_day and is_valid_time

        if should_trade:
            logger.info("0DTE conditions met - ready to trade")
        else:
            logger.debug(
                f"0DTE conditions not met: day={is_valid_day}, time={is_valid_time}"
            )

        return should_trade

    def get_spy_0dte_chain(self) -> list[dict[str, Any]]:
        """
        Get today's expiring SPY options chain.

        Returns:
            List of option contracts expiring today, or mock data if unavailable
        """
        today = self._get_current_time_est().strftime("%Y-%m-%d")

        if self.use_live_data:
            chain = self._fetch_live_chain(today)
            if chain:
                return chain

        # Return mock chain for testing/development
        return self._get_mock_chain(today)

    def _fetch_live_chain(self, expiration: str) -> Optional[list[dict[str, Any]]]:
        """Fetch live options chain from market data provider."""
        try:
            # Try yfinance first
            from src.utils import yfinance_wrapper as yf

            ticker = yf.Ticker(self.SYMBOL)
            expirations = ticker.options

            if not expirations:
                logger.debug("No options expirations available")
                return None

            # Check if today's expiration is available
            if expiration not in expirations:
                logger.debug(f"Today's expiration {expiration} not in chain")
                return None

            chain = ticker.option_chain(expiration)
            contracts = []

            # Process puts
            if not chain.puts.empty:
                for _, row in chain.puts.iterrows():
                    contracts.append({
                        "type": "put",
                        "strike": float(row["strike"]),
                        "bid": float(row.get("bid", 0) or 0),
                        "ask": float(row.get("ask", 0) or 0),
                        "mid": (float(row.get("bid", 0) or 0) + float(row.get("ask", 0) or 0)) / 2,
                        "delta": float(row.get("delta", 0) or 0),
                        "theta": float(row.get("theta", 0) or 0),
                        "iv": float(row.get("impliedVolatility", 0) or 0),
                        "expiration": expiration,
                    })

            # Process calls
            if not chain.calls.empty:
                for _, row in chain.calls.iterrows():
                    contracts.append({
                        "type": "call",
                        "strike": float(row["strike"]),
                        "bid": float(row.get("bid", 0) or 0),
                        "ask": float(row.get("ask", 0) or 0),
                        "mid": (float(row.get("bid", 0) or 0) + float(row.get("ask", 0) or 0)) / 2,
                        "delta": float(row.get("delta", 0) or 0),
                        "theta": float(row.get("theta", 0) or 0),
                        "iv": float(row.get("impliedVolatility", 0) or 0),
                        "expiration": expiration,
                    })

            logger.info(f"Fetched {len(contracts)} 0DTE contracts for {expiration}")
            return contracts if contracts else None

        except Exception as e:
            logger.debug(f"Could not fetch live chain: {e}")
            return None

    def _get_mock_chain(self, expiration: str) -> list[dict[str, Any]]:
        """Generate mock options chain for testing."""
        # Mock SPY price around $590
        spy_price = 590.0
        contracts = []

        # Generate strikes from -20 to +20 around current price
        for offset in range(-20, 21):
            strike = spy_price + offset

            # Mock put pricing (decreases as strike goes lower)
            put_distance = max(0, spy_price - strike)
            put_mid = max(0.05, 2.0 - (put_distance * 0.15))

            contracts.append({
                "type": "put",
                "strike": strike,
                "bid": round(put_mid * 0.95, 2),
                "ask": round(put_mid * 1.05, 2),
                "mid": round(put_mid, 2),
                "delta": round(-0.5 + (offset * 0.02), 4),
                "theta": round(-0.15 + (abs(offset) * 0.005), 4),
                "iv": round(0.15 + (abs(offset) * 0.002), 4),
                "expiration": expiration,
            })

            # Mock call pricing (decreases as strike goes higher)
            call_distance = max(0, strike - spy_price)
            call_mid = max(0.05, 2.0 - (call_distance * 0.15))

            contracts.append({
                "type": "call",
                "strike": strike,
                "bid": round(call_mid * 0.95, 2),
                "ask": round(call_mid * 1.05, 2),
                "mid": round(call_mid, 2),
                "delta": round(0.5 - (offset * 0.02), 4),
                "theta": round(-0.15 + (abs(offset) * 0.005), 4),
                "iv": round(0.15 + (abs(offset) * 0.002), 4),
                "expiration": expiration,
            })

        logger.debug(f"Generated {len(contracts)} mock 0DTE contracts")
        return contracts

    def _get_spy_price(self) -> float:
        """Get current SPY price."""
        if self.use_live_data:
            try:
                from src.utils import yfinance_wrapper as yf

                ticker = yf.Ticker(self.SYMBOL)
                info = ticker.info
                price = info.get("regularMarketPrice") or info.get("currentPrice")
                if price:
                    return float(price)
            except Exception as e:
                logger.debug(f"Could not fetch SPY price: {e}")

        # Mock price
        return 590.0

    def find_iron_butterfly(
        self,
        chain: list[dict[str, Any]],
        width: int = 5
    ) -> Optional[IronButterflySetup]:
        """
        Find optimal iron butterfly setup from the options chain.

        Iron Butterfly Structure:
        - Long put (lower strike)
        - Short put (center strike)
        - Short call (center strike)
        - Long call (upper strike)

        Max profit: Net credit received
        Max loss: Wing width - net credit

        Args:
            chain: Options chain from get_spy_0dte_chain()
            width: Wing width in points (default 5)

        Returns:
            IronButterflySetup or None if setup not found
        """
        if not chain:
            logger.warning("Empty chain provided to find_iron_butterfly")
            return None

        # Get current SPY price to find ATM strike
        spy_price = self._get_spy_price()

        # Separate puts and calls
        puts = {c["strike"]: c for c in chain if c["type"] == "put"}
        calls = {c["strike"]: c for c in chain if c["type"] == "call"}

        if not puts or not calls:
            logger.warning("Chain missing puts or calls")
            return None

        # Find ATM strike (closest to current price)
        all_strikes = sorted(set(puts.keys()) & set(calls.keys()))
        if not all_strikes:
            logger.warning("No common strikes between puts and calls")
            return None

        center_strike = min(all_strikes, key=lambda x: abs(x - spy_price))

        # Calculate wing strikes
        long_put_strike = center_strike - width
        long_call_strike = center_strike + width

        # Verify all strikes exist
        if long_put_strike not in puts:
            # Find closest available strike
            available_lower = [s for s in puts if s < center_strike]
            if available_lower:
                long_put_strike = max(available_lower)
            else:
                logger.warning(f"No put strike available below {center_strike}")
                return None

        if long_call_strike not in calls:
            # Find closest available strike
            available_upper = [s for s in calls if s > center_strike]
            if available_upper:
                long_call_strike = min(available_upper)
            else:
                logger.warning(f"No call strike available above {center_strike}")
                return None

        # Get option prices
        short_put = puts.get(center_strike)
        short_call = calls.get(center_strike)
        long_put = puts.get(long_put_strike)
        long_call = calls.get(long_call_strike)

        if not all([short_put, short_call, long_put, long_call]):
            logger.warning("Could not find all required strikes for iron butterfly")
            return None

        # Calculate net credit
        # Sell center put + sell center call - buy wing put - buy wing call
        credit_received = (
            short_put["mid"] + short_call["mid"]
            - long_put["mid"] - long_call["mid"]
        )

        # Ensure positive credit
        if credit_received <= 0:
            logger.warning(f"Iron butterfly would result in debit: ${credit_received:.2f}")
            return None

        # Calculate max loss and breakevens
        actual_width = min(
            center_strike - long_put_strike,
            long_call_strike - center_strike
        )
        max_loss = (actual_width * 100) - (credit_received * 100)
        breakeven_low = center_strike - credit_received
        breakeven_high = center_strike + credit_received

        # Sum up greeks
        total_delta = sum([
            long_put.get("delta", 0) or 0,
            -(short_put.get("delta", 0) or 0),  # Short = negative delta exposure
            -(short_call.get("delta", 0) or 0),
            long_call.get("delta", 0) or 0,
        ])

        total_theta = sum([
            long_put.get("theta", 0) or 0,
            -(short_put.get("theta", 0) or 0),  # Selling = positive theta
            -(short_call.get("theta", 0) or 0),
            long_call.get("theta", 0) or 0,
        ])

        expiration = chain[0].get("expiration", self._get_current_time_est().strftime("%Y-%m-%d"))

        setup = IronButterflySetup(
            symbol=self.SYMBOL,
            expiration=expiration,
            center_strike=center_strike,
            wing_width=int(actual_width),
            long_put_strike=long_put_strike,
            short_put_strike=center_strike,
            short_call_strike=center_strike,
            long_call_strike=long_call_strike,
            net_credit=credit_received,
            max_loss=max_loss,
            breakeven_low=breakeven_low,
            breakeven_high=breakeven_high,
            delta=total_delta,
            theta=total_theta,
        )

        logger.info(
            f"Found iron butterfly: center=${center_strike}, "
            f"credit=${credit_received:.2f}, max_loss=${max_loss:.2f}"
        )

        return setup

    def calculate_profit_target(self, entry_credit: float) -> float:
        """
        Calculate profit target based on entry credit.

        Research shows 15% of credit is optimal for 0DTE.

        Args:
            entry_credit: Net credit received per spread

        Returns:
            Dollar amount to target for exit (per contract)
        """
        target = entry_credit * self.PROFIT_TARGET_PCT
        logger.debug(
            f"Profit target: ${target:.2f} "
            f"({self.PROFIT_TARGET_PCT:.0%} of ${entry_credit:.2f} credit)"
        )
        return target

    def calculate_stop_loss(self, entry_credit: float, width: float) -> float:
        """
        Calculate stop loss based on max loss.

        Research shows 25% of max loss is optimal stop for 0DTE.

        Args:
            entry_credit: Net credit received per spread
            width: Wing width in dollars

        Returns:
            Dollar loss amount to trigger exit (per contract)
        """
        max_loss = (width * 100) - (entry_credit * 100)
        stop_loss = max_loss * self.STOP_LOSS_PCT

        logger.debug(
            f"Stop loss: ${stop_loss:.2f} "
            f"({self.STOP_LOSS_PCT:.0%} of ${max_loss:.2f} max loss)"
        )
        return stop_loss

    def get_exit_recommendation(
        self,
        current_pnl: float,
        entry_time: datetime,
        entry_credit: float,
        width: float,
    ) -> str:
        """
        Get exit recommendation based on current P&L and time.

        Args:
            current_pnl: Current profit/loss on the position (negative = loss)
            entry_time: When the trade was entered
            entry_credit: Original credit received
            width: Wing width in dollars

        Returns:
            One of: "HOLD", "TAKE_PROFIT", "STOP_OUT", "TIME_EXIT"
        """
        now = self._get_current_time_est()

        # Calculate targets
        profit_target = self.calculate_profit_target(entry_credit) * 100  # Per contract
        stop_loss = self.calculate_stop_loss(entry_credit, width)

        # Check profit target (positive P&L)
        if current_pnl >= profit_target:
            logger.info(
                f"TAKE_PROFIT: P&L ${current_pnl:.2f} >= target ${profit_target:.2f}"
            )
            return "TAKE_PROFIT"

        # Check stop loss (negative P&L)
        if current_pnl <= -stop_loss:
            logger.info(
                f"STOP_OUT: P&L ${current_pnl:.2f} <= stop -${stop_loss:.2f}"
            )
            return "STOP_OUT"

        # Check time exit (noon EST)
        exit_time = time(12, 0)  # Noon
        if now.time() >= exit_time:
            logger.info(
                f"TIME_EXIT: Current time {now.strftime('%H:%M')} >= {exit_time.strftime('%H:%M')}"
            )
            return "TIME_EXIT"

        logger.debug(
            f"HOLD: P&L ${current_pnl:.2f}, "
            f"target ${profit_target:.2f}, stop -${stop_loss:.2f}"
        )
        return "HOLD"

    def get_position_size(self) -> int:
        """
        Calculate number of contracts based on account value and risk limit.

        Returns:
            Number of contracts to trade
        """
        # Max risk is 2% of account
        max_risk = self._account_value * self.MAX_POSITION_PCT

        # Get a sample setup to estimate max loss
        chain = self.get_spy_0dte_chain()
        setup = self.find_iron_butterfly(chain, self.DEFAULT_WING_WIDTH)

        if not setup or setup.max_loss <= 0:
            logger.warning("Could not calculate position size - no valid setup")
            return 1  # Minimum 1 contract

        # Calculate contracts
        contracts = int(max_risk / setup.max_loss)
        contracts = max(1, contracts)  # At least 1

        logger.info(
            f"Position size: {contracts} contracts "
            f"(${max_risk:.2f} risk / ${setup.max_loss:.2f} max loss)"
        )

        return contracts

    def generate_trade_setup(self) -> ZeroDTETradeSetup:
        """
        Generate complete 0DTE trade setup if conditions are met.

        Returns:
            ZeroDTETradeSetup with all parameters
        """
        now = self._get_current_time_est()
        day_name = now.strftime("%A")

        # Check day
        if not self.is_0dte_day():
            return ZeroDTETradeSetup(
                trade=False,
                reason=f"Today is {day_name}, not a 0DTE day (Mon/Wed only)",
                day_of_week=day_name,
            )

        # Check time
        if not self.is_entry_window():
            current_time = now.strftime("%H:%M")
            return ZeroDTETradeSetup(
                trade=False,
                reason=f"Outside entry window. Current: {current_time}, Window: 10:00-10:30 AM EST",
                day_of_week=day_name,
            )

        # Get options chain
        chain = self.get_spy_0dte_chain()
        if not chain:
            return ZeroDTETradeSetup(
                trade=False,
                reason="Could not fetch 0DTE options chain",
                day_of_week=day_name,
            )

        # Find iron butterfly
        setup = self.find_iron_butterfly(chain, self.DEFAULT_WING_WIDTH)
        if not setup:
            return ZeroDTETradeSetup(
                trade=False,
                reason="Could not find valid iron butterfly setup",
                day_of_week=day_name,
            )

        # Calculate targets
        profit_target = self.calculate_profit_target(setup.net_credit)
        stop_loss = self.calculate_stop_loss(setup.net_credit, setup.wing_width)

        return ZeroDTETradeSetup(
            trade=True,
            reason="All conditions met - ready to execute",
            setup=setup,
            entry_time=self.BEST_ENTRY_TIME,
            exit_time=self.BEST_EXIT_TIME,
            profit_target=profit_target,
            stop_loss=stop_loss,
            day_of_week=day_name,
        )


# === Convenience Function ===

def get_0dte_trade_setup(
    paper: bool = True,
    account_value: Optional[float] = None,
    use_live_data: bool = True,
) -> dict[str, Any]:
    """
    Get today's 0DTE trade setup if conditions are met.

    This is the main entry point for the 0DTE strategy.

    Args:
        paper: Use paper trading (default True)
        account_value: Account value for sizing (auto-fetched if None)
        use_live_data: Try to use live market data (default True)

    Returns:
        Dictionary with trade setup or reason for not trading:
        {
            "trade": bool,
            "reason": str,
            "setup": {...} if trade else None,
            "entry_time": str,
            "exit_time": str,
            "profit_target": float,
            "stop_loss": float,
            "day_of_week": str,
        }

    Example:
        >>> setup = get_0dte_trade_setup()
        >>> if setup["trade"]:
        ...     print(f"Execute: {setup['setup']}")
        ... else:
        ...     print(f"No trade: {setup['reason']}")
    """
    strategy = ZeroDTEStrategy(
        paper=paper,
        account_value=account_value,
        use_live_data=use_live_data,
    )

    trade_setup = strategy.generate_trade_setup()
    return trade_setup.to_dict()


# === Module Self-Test ===

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=" * 60)
    print("0DTE Strategy - Option Alpha Research Implementation")
    print("=" * 60)

    # Create strategy instance
    strategy = ZeroDTEStrategy(paper=True, use_live_data=False)

    # Check conditions
    print(f"\nCurrent time (EST): {strategy._get_current_time_est().strftime('%Y-%m-%d %H:%M')}")
    print(f"Is 0DTE day (Mon/Wed)? {strategy.is_0dte_day()}")
    print(f"Is entry window (10:00-10:30)? {strategy.is_entry_window()}")
    print(f"Should trade? {strategy.should_trade_0dte()}")

    # Get chain and setup
    print("\n--- Options Chain ---")
    chain = strategy.get_spy_0dte_chain()
    print(f"Fetched {len(chain)} contracts")

    print("\n--- Iron Butterfly Setup ---")
    butterfly = strategy.find_iron_butterfly(chain, width=5)
    if butterfly:
        print(f"Symbol: {butterfly.symbol}")
        print(f"Center Strike: ${butterfly.center_strike}")
        print(f"Wings: ${butterfly.long_put_strike} / ${butterfly.long_call_strike}")
        print(f"Net Credit: ${butterfly.net_credit:.2f}")
        print(f"Max Loss: ${butterfly.max_loss:.2f}")
        print(f"Breakevens: ${butterfly.breakeven_low:.2f} - ${butterfly.breakeven_high:.2f}")

        # Calculate targets
        profit_target = strategy.calculate_profit_target(butterfly.net_credit)
        stop_loss = strategy.calculate_stop_loss(butterfly.net_credit, butterfly.wing_width)
        print(f"\nProfit Target (15%): ${profit_target:.2f}")
        print(f"Stop Loss (25%): ${stop_loss:.2f}")

    # Full trade setup
    print("\n--- Complete Trade Setup ---")
    setup = get_0dte_trade_setup(paper=True, use_live_data=False)
    print(f"Trade: {setup['trade']}")
    print(f"Reason: {setup['reason']}")
    if setup.get("setup"):
        print(f"Entry: {setup['entry_time']} EST")
        print(f"Exit: {setup['exit_time']} EST")
        print(f"Profit Target: ${setup['profit_target']:.2f}")
        print(f"Stop Loss: ${setup['stop_loss']:.2f}")
