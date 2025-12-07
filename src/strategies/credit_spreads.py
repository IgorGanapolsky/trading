"""
Credit Spreads Strategy - Defined Risk Premium Selling

Credit spreads provide a safer alternative to naked options by defining
maximum risk while still generating income from premium decay.

Types of Credit Spreads:
1. BULL PUT SPREAD (Bullish on stock)
   - Sell OTM put (higher strike)
   - Buy further OTM put (lower strike)
   - Max profit: Net credit received
   - Max loss: Width of spread - Credit

2. BEAR CALL SPREAD (Bearish on stock)
   - Sell OTM call (lower strike)
   - Buy further OTM call (higher strike)
   - Max profit: Net credit received
   - Max loss: Width of spread - Credit

Advantages:
- Defined risk (know max loss before entering)
- Lower capital requirement than CSPs
- Can scale position size more safely
- Benefits from theta decay (time is on your side)

Key Parameters (from McMillan):
- IV Rank > 50% for premium selling (higher = better)
- DTE: 30-45 days optimal
- Delta on short leg: 0.20-0.30
- Width: 5-10 points (depends on stock price)
- Close at 50-70% of max profit
- Stop loss at 2x credit received

Reference: Lawrence McMillan "Options as a Strategic Investment"
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SpreadDirection(Enum):
    """Direction of credit spread."""

    BULL_PUT = "bull_put"  # Bullish: Sell put spread
    BEAR_CALL = "bear_call"  # Bearish: Sell call spread


@dataclass
class CreditSpread:
    """Represents a credit spread position."""

    symbol: str
    direction: SpreadDirection
    expiration: str

    # Short leg (the one we sold)
    short_strike: float
    short_premium: float

    # Long leg (the one we bought for protection)
    long_strike: float
    long_premium: float

    # Position details
    contracts: int = 1
    net_credit: float = 0.0  # Premium received (short - long)
    max_loss: float = 0.0  # Width - Credit
    max_profit: float = 0.0  # Net credit
    width: float = 0.0  # Strike difference

    # Greeks
    short_delta: float | None = None
    position_delta: float | None = None

    # Status
    entry_date: datetime = field(default_factory=datetime.now)
    status: str = "open"  # open, closed, expired, assigned

    def __post_init__(self):
        self.width = abs(self.short_strike - self.long_strike)
        self.net_credit = self.short_premium - self.long_premium
        self.max_profit = self.net_credit * 100 * self.contracts
        self.max_loss = (self.width - self.net_credit) * 100 * self.contracts

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction.value,
            "expiration": self.expiration,
            "short_strike": self.short_strike,
            "short_premium": self.short_premium,
            "long_strike": self.long_strike,
            "long_premium": self.long_premium,
            "contracts": self.contracts,
            "net_credit": self.net_credit,
            "max_loss": self.max_loss,
            "max_profit": self.max_profit,
            "width": self.width,
            "short_delta": self.short_delta,
            "position_delta": self.position_delta,
            "entry_date": self.entry_date.isoformat(),
            "status": self.status,
        }


@dataclass
class SpreadOpportunity:
    """A potential credit spread opportunity."""

    symbol: str
    direction: SpreadDirection
    expiration: str
    dte: int

    # Strikes
    short_strike: float
    long_strike: float
    width: float

    # Premiums
    short_premium: float
    long_premium: float
    net_credit: float

    # Risk/Reward
    max_profit: float
    max_loss: float
    probability_of_profit: float  # Based on delta
    return_on_risk: float  # Credit / Max Loss

    # Quality metrics
    iv_rank: float | None = None
    short_delta: float | None = None
    bid_ask_quality: float = 0.0  # 0-1, higher is better

    # Recommendation
    confidence: float = 0.0  # 0-1
    rationale: str = ""


class CreditSpreadsStrategy:
    """
    Credit Spreads Strategy - Defined risk premium selling.

    Uses IV Rank and delta targeting to identify high-probability
    credit spread opportunities for consistent income generation.
    """

    # Strategy parameters (McMillan guidelines)
    MIN_IV_RANK = 30  # Minimum IV rank for premium selling
    OPTIMAL_IV_RANK = 50  # Prefer higher IV for better premiums
    TARGET_DELTA = 0.25  # ~25% probability of being breached
    DELTA_TOLERANCE = 0.05
    MIN_DTE = 25
    MAX_DTE = 50
    OPTIMAL_DTE = 35

    # Spread configuration
    MIN_WIDTH = 2.5  # Minimum spread width ($2.50)
    MAX_WIDTH = 10.0  # Maximum spread width ($10)
    MIN_CREDIT = 0.30  # Minimum credit ($0.30)
    MIN_RETURN_ON_RISK = 0.25  # Minimum 25% return on max risk

    # Risk management
    PROFIT_TARGET_PCT = 0.50  # Close at 50% of max profit
    STOP_LOSS_MULTIPLIER = 2.0  # Stop at 2x credit received
    MAX_PORTFOLIO_RISK_PCT = 0.02  # Max 2% portfolio risk per spread

    # High-liquidity universe for spreads
    SPREAD_UNIVERSE = [
        # Highly liquid ETFs (best for spreads)
        "SPY",
        "QQQ",
        "IWM",
        "EEM",
        "XLF",
        "XLE",
        # Large cap tech
        "AAPL",
        "MSFT",
        "GOOGL",
        "META",
        "AMZN",
        "NVDA",
        # Other liquid stocks
        "TSLA",
        "AMD",
        "NFLX",
        "JPM",
        "BAC",
    ]

    def __init__(self, paper: bool = True, state_file: str = "data/credit_spreads_state.json"):
        """
        Initialize Credit Spreads Strategy.

        Args:
            paper: Use paper trading
            state_file: Path to persist positions
        """
        self.paper = paper
        self.state_file = Path(state_file)
        self.positions: list[CreditSpread] = []

        # Initialize clients
        try:
            from src.core.options_client import AlpacaOptionsClient
            from src.utils.iv_analyzer import IVAnalyzer

            self.options_client = AlpacaOptionsClient(paper=paper)
            self.iv_analyzer = IVAnalyzer()
        except ImportError as e:
            logger.warning(f"Could not import clients: {e}")
            self.options_client = None
            self.iv_analyzer = None

        self._load_state()
        logger.info(f"Credit Spreads Strategy initialized: {len(self.positions)} positions")

    def _load_state(self) -> None:
        """Load positions from disk."""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    data = json.load(f)
                    for pos_data in data.get("positions", []):
                        spread = CreditSpread(
                            symbol=pos_data["symbol"],
                            direction=SpreadDirection(pos_data["direction"]),
                            expiration=pos_data["expiration"],
                            short_strike=pos_data["short_strike"],
                            short_premium=pos_data["short_premium"],
                            long_strike=pos_data["long_strike"],
                            long_premium=pos_data["long_premium"],
                            contracts=pos_data.get("contracts", 1),
                            short_delta=pos_data.get("short_delta"),
                            status=pos_data.get("status", "open"),
                        )
                        self.positions.append(spread)
        except Exception as e:
            logger.warning(f"Could not load state: {e}")

    def _save_state(self) -> None:
        """Persist positions to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "positions": [p.to_dict() for p in self.positions],
                "updated_at": datetime.now().isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _get_market_direction(self, symbol: str) -> SpreadDirection:
        """
        Determine whether to use bull put or bear call based on trend.

        Simple heuristic: Use 20-day SMA direction
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")

            if len(hist) < 20:
                return SpreadDirection.BULL_PUT  # Default bullish

            sma_20 = hist["Close"].rolling(20).mean().iloc[-1]
            current = hist["Close"].iloc[-1]

            if current > sma_20:
                return SpreadDirection.BULL_PUT  # Bullish - sell put spreads
            else:
                return SpreadDirection.BEAR_CALL  # Bearish - sell call spreads

        except Exception:
            return SpreadDirection.BULL_PUT  # Default

    def find_spread_opportunity(
        self,
        symbol: str,
        direction: SpreadDirection | None = None,
    ) -> SpreadOpportunity | None:
        """
        Find the best credit spread opportunity for a symbol.

        Args:
            symbol: Stock ticker
            direction: Force direction, or auto-detect from trend

        Returns:
            SpreadOpportunity if found
        """
        try:
            import yfinance as yf

            # Get current price
            ticker = yf.Ticker(symbol)
            current_price = ticker.info.get("currentPrice") or ticker.info.get(
                "regularMarketPrice", 0
            )

            if not current_price:
                return None

            # Get IV rank
            iv_rank = None
            if self.iv_analyzer:
                try:
                    iv_data = self.iv_analyzer.get_recommendation(symbol)
                    iv_rank = (
                        iv_data.iv_rank if hasattr(iv_data, "iv_rank") else iv_data.get("iv_rank")
                    )
                except Exception:
                    pass

            # Check IV threshold
            if iv_rank and iv_rank < self.MIN_IV_RANK:
                logger.debug(f"{symbol}: IV Rank {iv_rank:.1f} below minimum {self.MIN_IV_RANK}")
                return None

            # Determine direction
            if direction is None:
                direction = self._get_market_direction(symbol)

            # Get options chain
            expirations = ticker.options
            if not expirations:
                return None

            # Find target expiration
            today = datetime.now()
            target_exp = None
            target_dte = 0

            for exp in expirations:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                dte = (exp_date - today).days
                if self.MIN_DTE <= dte <= self.MAX_DTE:
                    target_exp = exp
                    target_dte = dte
                    break

            if not target_exp:
                return None

            # Get options chain for target expiration
            chain = ticker.option_chain(target_exp)

            if direction == SpreadDirection.BULL_PUT:
                options = chain.puts
            else:
                options = chain.calls

            if options.empty:
                return None

            # Find short strike at target delta
            # For puts: negative delta, we want ~-0.25
            # For calls: positive delta, we want ~0.25
            if "delta" in options.columns:
                if direction == SpreadDirection.BULL_PUT:
                    # For puts, find delta around -0.25
                    options["delta_diff"] = abs(options["delta"] + self.TARGET_DELTA)
                else:
                    # For calls, find delta around 0.25
                    options["delta_diff"] = abs(options["delta"] - self.TARGET_DELTA)

                best_idx = options["delta_diff"].idxmin()
                short_option = options.loc[best_idx]
            else:
                # No delta available, use OTM percentage
                if direction == SpreadDirection.BULL_PUT:
                    target_strike = current_price * (1 - self.TARGET_DELTA * 0.5)  # ~5% OTM
                    options["strike_diff"] = abs(options["strike"] - target_strike)
                else:
                    target_strike = current_price * (1 + self.TARGET_DELTA * 0.5)
                    options["strike_diff"] = abs(options["strike"] - target_strike)

                best_idx = options["strike_diff"].idxmin()
                short_option = options.loc[best_idx]

            short_strike = float(short_option["strike"])
            short_bid = float(short_option.get("bid", 0) or 0)
            short_ask = float(short_option.get("ask", 0) or 0)
            short_delta = short_option.get("delta")

            # Calculate long strike (protection)
            # Width based on stock price (roughly 2-5% of price)
            width = min(max(current_price * 0.03, self.MIN_WIDTH), self.MAX_WIDTH)
            width = round(width * 2) / 2  # Round to $0.50

            if direction == SpreadDirection.BULL_PUT:
                long_strike = short_strike - width
            else:
                long_strike = short_strike + width

            # Find long option
            long_options = options[options["strike"] == long_strike]
            if long_options.empty:
                # Find closest available strike
                options["long_diff"] = abs(options["strike"] - long_strike)
                long_idx = options["long_diff"].idxmin()
                long_option = options.loc[long_idx]
            else:
                long_option = long_options.iloc[0]

            long_strike = float(long_option["strike"])
            long_bid = float(long_option.get("bid", 0) or 0)
            long_ask = float(long_option.get("ask", 0) or 0)

            # Calculate premiums (sell at bid, buy at ask)
            short_premium = short_bid if short_bid > 0 else (short_bid + short_ask) / 2
            long_premium = long_ask if long_ask > 0 else (long_bid + long_ask) / 2

            net_credit = short_premium - long_premium
            actual_width = abs(short_strike - long_strike)

            if net_credit < self.MIN_CREDIT:
                logger.debug(f"{symbol}: Credit ${net_credit:.2f} below minimum")
                return None

            # Calculate risk/reward
            max_profit = net_credit * 100
            max_loss = (actual_width - net_credit) * 100
            return_on_risk = (
                net_credit / (actual_width - net_credit) if actual_width > net_credit else 0
            )

            if return_on_risk < self.MIN_RETURN_ON_RISK:
                logger.debug(f"{symbol}: Return on risk {return_on_risk:.1%} below minimum")
                return None

            # Probability of profit (based on delta)
            if short_delta:
                pop = 1 - abs(float(short_delta))
            else:
                pop = 0.70  # Estimate based on target delta

            # Bid-ask quality (tighter spreads = better)
            short_spread = (short_ask - short_bid) / short_bid if short_bid > 0 else 1
            bid_ask_quality = max(0, 1 - short_spread)

            # Calculate confidence
            confidence = 0.5  # Base confidence
            if iv_rank and iv_rank > self.OPTIMAL_IV_RANK:
                confidence += 0.15
            if self.OPTIMAL_DTE - 10 <= target_dte <= self.OPTIMAL_DTE + 10:
                confidence += 0.1
            if bid_ask_quality > 0.8:
                confidence += 0.1
            if return_on_risk > 0.35:
                confidence += 0.1

            # Build rationale
            direction_str = "Bull Put" if direction == SpreadDirection.BULL_PUT else "Bear Call"
            rationale = (
                f"{direction_str} spread: Sell ${short_strike:.2f}/{long_strike:.2f} "
                f"for ${net_credit:.2f} credit. "
                f"IV Rank: {iv_rank:.1f}% "
                if iv_rank
                else f"DTE: {target_dte}, POP: {pop:.0%}, Return on Risk: {return_on_risk:.0%}"
            )

            return SpreadOpportunity(
                symbol=symbol,
                direction=direction,
                expiration=target_exp,
                dte=target_dte,
                short_strike=short_strike,
                long_strike=long_strike,
                width=actual_width,
                short_premium=short_premium,
                long_premium=long_premium,
                net_credit=net_credit,
                max_profit=max_profit,
                max_loss=max_loss,
                probability_of_profit=pop,
                return_on_risk=return_on_risk,
                iv_rank=iv_rank,
                short_delta=float(short_delta) if short_delta else None,
                bid_ask_quality=bid_ask_quality,
                confidence=min(confidence, 0.95),
                rationale=rationale,
            )

        except Exception as e:
            logger.warning(f"Failed to find spread for {symbol}: {e}")
            return None

    def scan_universe(self) -> list[SpreadOpportunity]:
        """
        Scan the universe for credit spread opportunities.

        Returns:
            List of opportunities sorted by confidence
        """
        opportunities = []

        for symbol in self.SPREAD_UNIVERSE:
            opp = self.find_spread_opportunity(symbol)
            if opp:
                opportunities.append(opp)

        # Sort by confidence then return on risk
        opportunities.sort(key=lambda x: (x.confidence, x.return_on_risk), reverse=True)

        logger.info(f"Found {len(opportunities)} spread opportunities")
        return opportunities

    def execute_spread(
        self, opportunity: SpreadOpportunity, contracts: int = 1
    ) -> dict[str, Any] | None:
        """
        Execute a credit spread trade.

        Args:
            opportunity: SpreadOpportunity to execute
            contracts: Number of spread contracts

        Returns:
            Execution result dict
        """
        if not self.options_client:
            logger.error("Options client not initialized")
            return None

        symbol = opportunity.symbol
        direction = opportunity.direction

        try:
            # Build OCC symbols
            exp_str = opportunity.expiration.replace("-", "")[2:]  # YYMMDD
            type_char = "P" if direction == SpreadDirection.BULL_PUT else "C"

            short_strike_str = f"{int(opportunity.short_strike * 1000):08d}"
            long_strike_str = f"{int(opportunity.long_strike * 1000):08d}"

            short_occ = f"{symbol}{exp_str}{type_char}{short_strike_str}"
            long_occ = f"{symbol}{exp_str}{type_char}{long_strike_str}"

            logger.info(
                f"Executing {direction.value} spread on {symbol}: "
                f"SELL {short_occ} / BUY {long_occ} x{contracts}"
            )

            # Submit short leg (sell to open)
            short_result = self.options_client.submit_option_order(
                option_symbol=short_occ,
                qty=contracts,
                side="sell_to_open",
                order_type="limit",
                limit_price=opportunity.short_premium,
            )

            # Submit long leg (buy to open)
            long_result = self.options_client.submit_option_order(
                option_symbol=long_occ,
                qty=contracts,
                side="buy_to_open",
                order_type="limit",
                limit_price=opportunity.long_premium,
            )

            # Create position record
            spread = CreditSpread(
                symbol=symbol,
                direction=direction,
                expiration=opportunity.expiration,
                short_strike=opportunity.short_strike,
                short_premium=opportunity.short_premium,
                long_strike=opportunity.long_strike,
                long_premium=opportunity.long_premium,
                contracts=contracts,
                short_delta=opportunity.short_delta,
            )
            self.positions.append(spread)
            self._save_state()

            return {
                "action": "CREDIT_SPREAD_OPENED",
                "symbol": symbol,
                "direction": direction.value,
                "short_occ": short_occ,
                "long_occ": long_occ,
                "short_strike": opportunity.short_strike,
                "long_strike": opportunity.long_strike,
                "net_credit": opportunity.net_credit,
                "max_profit": opportunity.max_profit,
                "max_loss": opportunity.max_loss,
                "contracts": contracts,
                "probability_of_profit": opportunity.probability_of_profit,
                "short_order_id": short_result.get("id"),
                "long_order_id": long_result.get("id"),
                "iv_rank": opportunity.iv_rank,
                "dte": opportunity.dte,
            }

        except Exception as e:
            logger.error(f"Failed to execute spread: {e}")
            return None

    def check_exit_conditions(self) -> list[dict[str, Any]]:
        """
        Check all open positions for exit conditions.

        Exit conditions:
        1. Profit target reached (50% of max)
        2. Stop loss hit (2x credit)
        3. Near expiration (< 7 DTE)

        Returns:
            List of recommended actions
        """
        actions = []

        for spread in self.positions:
            if spread.status != "open":
                continue

            try:
                import yfinance as yf

                # Get current option prices
                ticker = yf.Ticker(spread.symbol)
                chain = ticker.option_chain(spread.expiration)

                if spread.direction == SpreadDirection.BULL_PUT:
                    options = chain.puts
                else:
                    options = chain.calls

                # Get current prices for our strikes
                short_opt = options[options["strike"] == spread.short_strike]
                long_opt = options[options["strike"] == spread.long_strike]

                if short_opt.empty or long_opt.empty:
                    continue

                # Current values (buy to close short, sell to close long)
                short_ask = float(short_opt["ask"].iloc[0] or 0)
                long_bid = float(long_opt["bid"].iloc[0] or 0)
                current_cost_to_close = short_ask - long_bid

                # Original credit received
                original_credit = spread.net_credit

                # Current P/L
                current_pnl = (original_credit - current_cost_to_close) * 100 * spread.contracts

                # Check profit target
                if current_pnl >= spread.max_profit * self.PROFIT_TARGET_PCT:
                    actions.append(
                        {
                            "symbol": spread.symbol,
                            "action": "CLOSE_PROFIT_TARGET",
                            "current_pnl": current_pnl,
                            "max_profit": spread.max_profit,
                            "pct_of_max": current_pnl / spread.max_profit,
                            "reason": f"Profit target reached ({current_pnl / spread.max_profit:.0%} of max)",
                        }
                    )

                # Check stop loss
                if (
                    current_pnl
                    <= -spread.net_credit * 100 * self.STOP_LOSS_MULTIPLIER * spread.contracts
                ):
                    actions.append(
                        {
                            "symbol": spread.symbol,
                            "action": "CLOSE_STOP_LOSS",
                            "current_pnl": current_pnl,
                            "stop_loss_level": -spread.net_credit
                            * 100
                            * self.STOP_LOSS_MULTIPLIER
                            * spread.contracts,
                            "reason": "Stop loss hit (2x credit)",
                        }
                    )

                # Check DTE
                exp_date = datetime.strptime(spread.expiration, "%Y-%m-%d")
                dte = (exp_date - datetime.now()).days

                if dte <= 7:
                    actions.append(
                        {
                            "symbol": spread.symbol,
                            "action": "CLOSE_NEAR_EXPIRATION",
                            "dte": dte,
                            "current_pnl": current_pnl,
                            "reason": f"Near expiration ({dte} DTE), close to avoid assignment risk",
                        }
                    )

            except Exception as e:
                logger.warning(f"Error checking exit for {spread.symbol}: {e}")

        return actions

    def get_summary(self) -> dict[str, Any]:
        """Get strategy summary."""
        open_positions = [p for p in self.positions if p.status == "open"]
        total_credit = sum(p.net_credit * 100 * p.contracts for p in open_positions)
        total_max_risk = sum(p.max_loss for p in open_positions)

        return {
            "total_positions": len(self.positions),
            "open_positions": len(open_positions),
            "total_credit_received": total_credit,
            "total_max_risk": total_max_risk,
            "positions": [p.to_dict() for p in self.positions],
            "timestamp": datetime.now().isoformat(),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    strategy = CreditSpreadsStrategy(paper=True)

    print("\n=== CREDIT SPREADS SCANNER ===")

    opportunities = strategy.scan_universe()

    print(f"\n--- Top Opportunities ({len(opportunities)} found) ---")
    for opp in opportunities[:5]:
        direction_str = "Bull Put" if opp.direction == SpreadDirection.BULL_PUT else "Bear Call"
        print(
            f"  {opp.symbol} ({direction_str}): "
            f"${opp.short_strike:.2f}/${opp.long_strike:.2f} "
            f"for ${opp.net_credit:.2f} credit "
            f"(POP: {opp.probability_of_profit:.0%}, RoR: {opp.return_on_risk:.0%})"
        )
        if opp.iv_rank:
            print(
                f"    IV Rank: {opp.iv_rank:.1f}%, DTE: {opp.dte}, Confidence: {opp.confidence:.0%}"
            )
