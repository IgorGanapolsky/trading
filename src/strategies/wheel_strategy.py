"""
The Wheel Strategy - Most Reliable Options Income Generator

The Wheel is a systematic options strategy that generates consistent income by
rotating between cash-secured puts and covered calls. It's ideal for building
towards $100/day income target.

Strategy Flow:
1. SELL CASH-SECURED PUTS at support levels on quality stocks
   - If not assigned: Keep premium, repeat
   - If assigned: Own shares at effective discount (strike - premium)

2. SELL COVERED CALLS on assigned shares
   - If not called away: Keep premium, repeat
   - If called away: Sell at profit (strike + total premiums), restart with puts

Key Advantages:
- Defined risk (you're always willing to own the stock at that price)
- Consistent income regardless of market direction
- Benefits from theta decay (time is on your side)
- Compounds: Each trade adds to your effective cost basis improvement

Capital Requirements for $100/day:
- ~$50-100k capital (depends on stock prices and IV)
- Target: 1-2% monthly return on capital deployed

Reference: Tasty Trade "The Wheel" strategy guidelines
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WheelPhase(Enum):
    """Current phase in the wheel cycle."""

    SELLING_PUTS = "selling_puts"  # Phase 1: Selling CSPs
    ASSIGNED = "assigned"  # Transition: Got assigned shares
    SELLING_CALLS = "selling_calls"  # Phase 2: Selling covered calls
    CALLED_AWAY = "called_away"  # Transition: Shares called away


@dataclass
class WheelPosition:
    """Tracks a single wheel cycle on a stock."""

    symbol: str
    phase: WheelPhase

    # Position details
    shares_owned: int = 0
    cost_basis: float = 0.0  # Effective cost after premiums

    # Put leg (Phase 1)
    put_strike: float | None = None
    put_expiration: str | None = None
    put_premium_collected: float = 0.0
    put_contracts: int = 0

    # Call leg (Phase 2)
    call_strike: float | None = None
    call_expiration: str | None = None
    call_premium_collected: float = 0.0
    call_contracts: int = 0

    # Cumulative tracking
    total_premium_collected: float = 0.0
    cycles_completed: int = 0
    realized_pnl: float = 0.0

    # Timestamps
    started_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "phase": self.phase.value,
            "shares_owned": self.shares_owned,
            "cost_basis": self.cost_basis,
            "put_strike": self.put_strike,
            "put_expiration": self.put_expiration,
            "put_premium_collected": self.put_premium_collected,
            "put_contracts": self.put_contracts,
            "call_strike": self.call_strike,
            "call_expiration": self.call_expiration,
            "call_premium_collected": self.call_premium_collected,
            "call_contracts": self.call_contracts,
            "total_premium_collected": self.total_premium_collected,
            "cycles_completed": self.cycles_completed,
            "realized_pnl": self.realized_pnl,
            "started_at": self.started_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WheelPosition":
        return cls(
            symbol=data["symbol"],
            phase=WheelPhase(data["phase"]),
            shares_owned=data.get("shares_owned", 0),
            cost_basis=data.get("cost_basis", 0.0),
            put_strike=data.get("put_strike"),
            put_expiration=data.get("put_expiration"),
            put_premium_collected=data.get("put_premium_collected", 0.0),
            put_contracts=data.get("put_contracts", 0),
            call_strike=data.get("call_strike"),
            call_expiration=data.get("call_expiration"),
            call_premium_collected=data.get("call_premium_collected", 0.0),
            call_contracts=data.get("call_contracts", 0),
            total_premium_collected=data.get("total_premium_collected", 0.0),
            cycles_completed=data.get("cycles_completed", 0),
            realized_pnl=data.get("realized_pnl", 0.0),
            started_at=datetime.fromisoformat(data["started_at"])
            if data.get("started_at")
            else datetime.now(),
            last_updated=datetime.fromisoformat(data["last_updated"])
            if data.get("last_updated")
            else datetime.now(),
        )


@dataclass
class WheelCandidate:
    """A stock evaluated for wheel strategy suitability."""

    symbol: str
    current_price: float

    # Fundamental quality
    is_quality_stock: bool = False
    quality_score: float = 0.0  # 0-100
    quality_reasons: list[str] = field(default_factory=list)

    # Technical levels
    support_level: float | None = None
    resistance_level: float | None = None

    # Options metrics
    iv_rank: float | None = None
    option_liquidity_score: float = 0.0  # Based on bid-ask spreads

    # Wheel suitability
    recommended_put_strike: float | None = None
    recommended_call_strike: float | None = None
    estimated_monthly_yield: float = 0.0

    # Risk assessment
    max_loss_if_assigned: float = 0.0
    capital_required: float = 0.0


class WheelStrategy:
    """
    The Wheel Strategy - Systematic income generation through options.

    Implements a disciplined rotation between CSPs and covered calls
    to generate consistent income towards $100/day target.
    """

    # Strategy parameters
    TARGET_DELTA_PUT = 0.25  # 25% chance of assignment (conservative)
    TARGET_DELTA_CALL = 0.30  # 30% chance of being called away
    MIN_DTE = 25  # Minimum days to expiration
    MAX_DTE = 45  # Maximum days to expiration (sweet spot: 30-45)
    MIN_PREMIUM_YIELD = 0.008  # 0.8% minimum per trade (10%+ annualized)
    PROFIT_TARGET_PCT = 0.50  # Close at 50% of max profit

    # Stock selection criteria
    MIN_OPTION_VOLUME = 100  # Minimum daily option volume
    MAX_BID_ASK_SPREAD_PCT = 0.05  # Maximum 5% bid-ask spread
    MIN_PRICE = 20  # Minimum stock price
    MAX_PRICE = 500  # Maximum stock price (for capital efficiency)

    # Quality stocks for wheel (high quality, good premiums)
    WHEEL_UNIVERSE = [
        # Tech with wide moats
        "AAPL",
        "MSFT",
        "GOOGL",
        "META",
        # Consumer staples (stable)
        "KO",
        "PG",
        "PEP",
        "WMT",
        "COST",
        # Financials
        "V",
        "MA",
        "JPM",
        "BRK-B",
        # Healthcare
        "JNJ",
        "UNH",
        "PFE",
        # ETFs (highly liquid, lower risk)
        "SPY",
        "QQQ",
        "IWM",
        # Other blue chips
        "NVDA",
        "AMD",
        "DIS",
        "HD",
        "MCD",
    ]

    def __init__(self, paper: bool = True, state_file: str = "data/wheel_state.json"):
        """
        Initialize the Wheel Strategy.

        Args:
            paper: Use paper trading if True
            state_file: Path to persist wheel positions state
        """
        self.paper = paper
        self.state_file = Path(state_file)
        self.positions: dict[str, WheelPosition] = {}

        # Initialize clients
        try:
            from src.core.alpaca_trader import AlpacaTrader
            from src.core.options_client import AlpacaOptionsClient
            from src.utils.iv_analyzer import IVAnalyzer

            self.trader = AlpacaTrader(paper=paper)
            self.options_client = AlpacaOptionsClient(paper=paper)
            self.iv_analyzer = IVAnalyzer()
        except ImportError as e:
            logger.warning(f"Could not import trading clients: {e}")
            self.trader = None
            self.options_client = None
            self.iv_analyzer = None

        # Load existing state
        self._load_state()

        logger.info(
            f"Wheel Strategy initialized: {len(self.positions)} active positions, "
            f"universe={len(self.WHEEL_UNIVERSE)} stocks, paper={paper}"
        )

    def _load_state(self) -> None:
        """Load wheel positions from disk."""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    data = json.load(f)
                    for symbol, pos_data in data.get("positions", {}).items():
                        self.positions[symbol] = WheelPosition.from_dict(pos_data)
                logger.info(f"Loaded {len(self.positions)} wheel positions from {self.state_file}")
        except Exception as e:
            logger.warning(f"Could not load wheel state: {e}")

    def _save_state(self) -> None:
        """Persist wheel positions to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "positions": {s: p.to_dict() for s, p in self.positions.items()},
                "updated_at": datetime.now().isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved wheel state to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save wheel state: {e}")

    def _get_support_resistance(
        self, symbol: str, current_price: float
    ) -> tuple[float | None, float | None]:
        """
        Calculate support and resistance levels for strike selection.

        Uses simple pivot point analysis for now.
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="3mo")

            if hist.empty:
                return None, None

            # Simple support/resistance using rolling min/max
            rolling_low = hist["Low"].rolling(window=20).min().iloc[-1]
            rolling_high = hist["High"].rolling(window=20).max().iloc[-1]

            # Support: Recent lows (where puts would be assigned)
            support = rolling_low * 0.98  # Slightly below recent low

            # Resistance: Recent highs (where calls would be called away)
            resistance = rolling_high * 1.02  # Slightly above recent high

            return support, resistance

        except Exception as e:
            logger.warning(f"Could not calculate S/R for {symbol}: {e}")
            return current_price * 0.90, current_price * 1.10  # Default 10% range

    def _calculate_quality_score(self, symbol: str) -> tuple[float, list[str]]:
        """
        Calculate a quality score (0-100) for wheel suitability.

        Checks:
        - Market cap (large cap preferred)
        - Profitability
        - Debt levels
        - Dividend history
        - Option liquidity
        """
        score = 50  # Base score
        reasons = []

        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Market cap check
            market_cap = info.get("marketCap", 0)
            if market_cap > 100_000_000_000:  # >$100B
                score += 15
                reasons.append("Large cap (>$100B)")
            elif market_cap > 10_000_000_000:  # >$10B
                score += 10
                reasons.append("Mid-large cap (>$10B)")
            elif market_cap < 2_000_000_000:  # <$2B
                score -= 20
                reasons.append("Small cap risk (<$2B)")

            # Profitability
            profit_margin = info.get("profitMargins", 0)
            if profit_margin and profit_margin > 0.15:
                score += 10
                reasons.append(f"High profit margin ({profit_margin:.1%})")
            elif profit_margin and profit_margin < 0:
                score -= 15
                reasons.append("Unprofitable company")

            # Debt check
            debt_to_equity = info.get("debtToEquity", 0)
            if debt_to_equity and debt_to_equity < 50:
                score += 10
                reasons.append("Low debt")
            elif debt_to_equity and debt_to_equity > 200:
                score -= 10
                reasons.append("High debt levels")

            # Dividend (indicates stability)
            div_yield = info.get("dividendYield", 0)
            if div_yield and div_yield > 0.01:
                score += 5
                reasons.append(f"Pays dividend ({div_yield:.1%})")

        except Exception as e:
            logger.warning(f"Quality check failed for {symbol}: {e}")

        return min(max(score, 0), 100), reasons

    def evaluate_candidate(self, symbol: str) -> WheelCandidate | None:
        """
        Evaluate a stock for wheel strategy suitability.

        Args:
            symbol: Stock ticker

        Returns:
            WheelCandidate if suitable, None otherwise
        """
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            current_price = ticker.info.get("currentPrice") or ticker.info.get(
                "regularMarketPrice", 0
            )

            if not current_price:
                logger.debug(f"{symbol}: No price data")
                return None

            # Price range check
            if current_price < self.MIN_PRICE or current_price > self.MAX_PRICE:
                logger.debug(f"{symbol}: Price ${current_price:.2f} outside range")
                return None

            # Quality assessment
            quality_score, quality_reasons = self._calculate_quality_score(symbol)
            is_quality = quality_score >= 60

            # Support/Resistance levels
            support, resistance = self._get_support_resistance(symbol, current_price)

            # IV analysis
            iv_rank = None
            if self.iv_analyzer:
                try:
                    iv_data = self.iv_analyzer.get_recommendation(symbol)
                    iv_rank = (
                        iv_data.iv_rank if hasattr(iv_data, "iv_rank") else iv_data.get("iv_rank")
                    )
                except Exception:
                    pass

            # Calculate recommended strikes
            # Put strike: At or below support (willing to buy at discount)
            put_strike = support if support else current_price * 0.95
            put_strike = round(put_strike / 5) * 5  # Round to $5 increments

            # Call strike: At or above resistance (willing to sell at profit)
            call_strike = resistance if resistance else current_price * 1.05
            call_strike = round(call_strike / 5) * 5

            # Capital required (cash needed to secure put)
            capital_required = put_strike * 100

            # Estimate monthly yield (rough estimate based on typical premiums)
            # Conservative: 1-2% monthly from wheel
            estimated_yield = capital_required * 0.015

            # Max loss if assigned and stock goes to zero
            max_loss = put_strike * 100

            return WheelCandidate(
                symbol=symbol,
                current_price=current_price,
                is_quality_stock=is_quality,
                quality_score=quality_score,
                quality_reasons=quality_reasons,
                support_level=support,
                resistance_level=resistance,
                iv_rank=iv_rank,
                recommended_put_strike=put_strike,
                recommended_call_strike=call_strike,
                estimated_monthly_yield=estimated_yield,
                max_loss_if_assigned=max_loss,
                capital_required=capital_required,
            )

        except Exception as e:
            logger.warning(f"Failed to evaluate {symbol}: {e}")
            return None

    def find_put_opportunities(self, max_capital: float = 50000) -> list[WheelCandidate]:
        """
        Scan universe for best cash-secured put opportunities.

        Args:
            max_capital: Maximum capital to deploy

        Returns:
            List of WheelCandidate sorted by yield
        """
        candidates = []

        for symbol in self.WHEEL_UNIVERSE:
            # Skip if we already have an active wheel on this symbol
            if symbol in self.positions and self.positions[symbol].phase != WheelPhase.CALLED_AWAY:
                continue

            candidate = self.evaluate_candidate(symbol)
            if candidate and candidate.is_quality_stock:
                if candidate.capital_required <= max_capital:
                    candidates.append(candidate)

        # Sort by estimated yield (highest first)
        candidates.sort(key=lambda x: x.estimated_monthly_yield / x.capital_required, reverse=True)

        logger.info(f"Found {len(candidates)} put opportunities within ${max_capital:,.0f} capital")
        return candidates

    def find_call_opportunities(self) -> list[WheelCandidate]:
        """
        Scan positions for covered call opportunities.

        Returns:
            List of WheelCandidate for positions ready for covered calls
        """
        candidates = []

        # Check portfolio for shares we own
        if not self.trader:
            return candidates

        try:
            positions = self.trader.get_positions()

            for pos in positions:
                symbol = pos.get("symbol")
                qty = float(pos.get("qty", 0))

                # Need at least 100 shares for covered call
                if qty < 100:
                    continue

                candidate = self.evaluate_candidate(symbol)
                if candidate:
                    candidates.append(candidate)

        except Exception as e:
            logger.error(f"Failed to find call opportunities: {e}")

        return candidates

    def execute_put_trade(self, candidate: WheelCandidate) -> dict[str, Any] | None:
        """
        Execute a cash-secured put for wheel strategy.

        Args:
            candidate: WheelCandidate with trade details

        Returns:
            Trade result dict if successful
        """
        if not self.options_client:
            logger.error("Options client not initialized")
            return None

        symbol = candidate.symbol
        strike = candidate.recommended_put_strike

        try:
            import yfinance as yf

            # Find best put option
            ticker = yf.Ticker(symbol)
            expirations = ticker.options

            if not expirations:
                logger.warning(f"No options available for {symbol}")
                return None

            # Find expiration in target range
            target_exp = None
            today = datetime.now()

            for exp in expirations:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                dte = (exp_date - today).days
                if self.MIN_DTE <= dte <= self.MAX_DTE:
                    target_exp = exp
                    break

            if not target_exp:
                target_exp = expirations[0] if expirations else None

            if not target_exp:
                return None

            # Get put options
            chain = ticker.option_chain(target_exp)
            puts = chain.puts

            if puts.empty:
                return None

            # Find put at target strike
            puts["strike_diff"] = abs(puts["strike"] - strike)
            best_put = puts.loc[puts["strike_diff"].idxmin()]

            actual_strike = float(best_put["strike"])
            bid = float(best_put.get("bid", 0) or 0)
            ask = float(best_put.get("ask", 0) or 0)
            premium = (bid + ask) / 2 if bid and ask else max(bid, ask)

            if premium <= 0:
                logger.warning(f"No premium for {symbol} put at ${actual_strike}")
                return None

            # Calculate yield
            dte = (datetime.strptime(target_exp, "%Y-%m-%d") - today).days
            annualized_yield = (premium / actual_strike) * (365 / dte) if dte > 0 else 0

            if annualized_yield < self.MIN_PREMIUM_YIELD * (365 / 30):  # Annualized check
                logger.info(f"{symbol}: Yield {annualized_yield:.1%} below minimum")
                return None

            # Build OCC symbol for the put
            # Format: SPY251219P00600000
            exp_str = target_exp.replace("-", "")[2:]  # YYMMDD
            strike_str = f"{int(actual_strike * 1000):08d}"
            occ_symbol = f"{symbol}{exp_str}P{strike_str}"

            logger.info(
                f"Executing wheel put: SELL {occ_symbol} "
                f"(Strike: ${actual_strike:.2f}, Premium: ${premium:.2f}, DTE: {dte})"
            )

            # Submit order
            order_result = self.options_client.submit_option_order(
                option_symbol=occ_symbol,
                qty=1,
                side="sell_to_open",
                order_type="limit",
                limit_price=premium,
            )

            # Update wheel position tracking
            position = WheelPosition(
                symbol=symbol,
                phase=WheelPhase.SELLING_PUTS,
                put_strike=actual_strike,
                put_expiration=target_exp,
                put_premium_collected=premium * 100,  # Per contract
                put_contracts=1,
                total_premium_collected=premium * 100,
            )
            self.positions[symbol] = position
            self._save_state()

            return {
                "action": "SELL_CSP",
                "symbol": symbol,
                "option_symbol": occ_symbol,
                "strike": actual_strike,
                "expiration": target_exp,
                "premium": premium,
                "total_premium": premium * 100,
                "dte": dte,
                "annualized_yield": annualized_yield,
                "order_id": order_result.get("id"),
                "order_status": order_result.get("status"),
                "phase": "SELLING_PUTS",
            }

        except Exception as e:
            logger.error(f"Failed to execute put trade for {symbol}: {e}")
            return None

    def execute_call_trade(self, symbol: str, shares: int) -> dict[str, Any] | None:
        """
        Execute a covered call for wheel strategy (Phase 2).

        Args:
            symbol: Stock ticker
            shares: Number of shares owned

        Returns:
            Trade result dict if successful
        """
        if not self.options_client:
            logger.error("Options client not initialized")
            return None

        num_contracts = shares // 100
        if num_contracts < 1:
            logger.warning(f"Not enough shares for covered call ({shares} < 100)")
            return None

        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            current_price = ticker.info.get("currentPrice") or ticker.info.get(
                "regularMarketPrice", 0
            )

            if not current_price:
                return None

            # Get resistance level for call strike
            _, resistance = self._get_support_resistance(symbol, current_price)
            target_strike = resistance if resistance else current_price * 1.05
            target_strike = round(target_strike / 5) * 5

            # Find best call option
            expirations = ticker.options
            if not expirations:
                return None

            today = datetime.now()
            target_exp = None

            for exp in expirations:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                dte = (exp_date - today).days
                if self.MIN_DTE <= dte <= self.MAX_DTE:
                    target_exp = exp
                    break

            if not target_exp:
                target_exp = expirations[0] if expirations else None

            if not target_exp:
                return None

            chain = ticker.option_chain(target_exp)
            calls = chain.calls

            if calls.empty:
                return None

            # Find call at target strike
            calls["strike_diff"] = abs(calls["strike"] - target_strike)
            best_call = calls.loc[calls["strike_diff"].idxmin()]

            actual_strike = float(best_call["strike"])
            bid = float(best_call.get("bid", 0) or 0)
            ask = float(best_call.get("ask", 0) or 0)
            premium = (bid + ask) / 2 if bid and ask else max(bid, ask)

            if premium <= 0:
                return None

            dte = (datetime.strptime(target_exp, "%Y-%m-%d") - today).days

            # Build OCC symbol
            exp_str = target_exp.replace("-", "")[2:]
            strike_str = f"{int(actual_strike * 1000):08d}"
            occ_symbol = f"{symbol}{exp_str}C{strike_str}"

            logger.info(
                f"Executing wheel call: SELL {num_contracts}x {occ_symbol} "
                f"(Strike: ${actual_strike:.2f}, Premium: ${premium:.2f})"
            )

            # Submit order
            order_result = self.options_client.submit_option_order(
                option_symbol=occ_symbol,
                qty=num_contracts,
                side="sell_to_open",
                order_type="limit",
                limit_price=premium,
            )

            # Update wheel position
            if symbol in self.positions:
                position = self.positions[symbol]
                position.phase = WheelPhase.SELLING_CALLS
                position.call_strike = actual_strike
                position.call_expiration = target_exp
                position.call_premium_collected = premium * 100 * num_contracts
                position.call_contracts = num_contracts
                position.total_premium_collected += position.call_premium_collected
                position.last_updated = datetime.now()
                self._save_state()

            return {
                "action": "SELL_COVERED_CALL",
                "symbol": symbol,
                "option_symbol": occ_symbol,
                "strike": actual_strike,
                "expiration": target_exp,
                "premium": premium,
                "total_premium": premium * 100 * num_contracts,
                "contracts": num_contracts,
                "dte": dte,
                "order_id": order_result.get("id"),
                "order_status": order_result.get("status"),
                "phase": "SELLING_CALLS",
            }

        except Exception as e:
            logger.error(f"Failed to execute call trade for {symbol}: {e}")
            return None

    def check_and_manage_positions(self) -> list[dict[str, Any]]:
        """
        Check all wheel positions and manage (close at profit target, roll, etc).

        Returns:
            List of actions taken
        """
        actions = []

        for symbol, position in self.positions.items():
            try:
                # Check if option expired or assigned
                if position.phase == WheelPhase.SELLING_PUTS:
                    if position.put_expiration:
                        exp_date = datetime.strptime(position.put_expiration, "%Y-%m-%d")
                        if datetime.now() > exp_date:
                            # Check if assigned
                            # This would require checking actual position via API
                            logger.info(f"{symbol}: Put expired, checking for assignment")
                            actions.append(
                                {
                                    "symbol": symbol,
                                    "action": "CHECK_ASSIGNMENT",
                                    "expiration": position.put_expiration,
                                }
                            )

                elif position.phase == WheelPhase.SELLING_CALLS:
                    if position.call_expiration:
                        exp_date = datetime.strptime(position.call_expiration, "%Y-%m-%d")
                        if datetime.now() > exp_date:
                            logger.info(f"{symbol}: Call expired, checking if called away")
                            actions.append(
                                {
                                    "symbol": symbol,
                                    "action": "CHECK_CALLED_AWAY",
                                    "expiration": position.call_expiration,
                                }
                            )

            except Exception as e:
                logger.warning(f"Error managing position {symbol}: {e}")

        return actions

    def get_daily_summary(self) -> dict[str, Any]:
        """
        Generate daily wheel strategy summary.

        Returns:
            Summary dict with key metrics
        """
        total_premium = sum(p.total_premium_collected for p in self.positions.values())
        active_puts = sum(1 for p in self.positions.values() if p.phase == WheelPhase.SELLING_PUTS)
        active_calls = sum(
            1 for p in self.positions.values() if p.phase == WheelPhase.SELLING_CALLS
        )
        completed_cycles = sum(p.cycles_completed for p in self.positions.values())

        return {
            "total_positions": len(self.positions),
            "active_puts": active_puts,
            "active_calls": active_calls,
            "total_premium_collected": total_premium,
            "completed_cycles": completed_cycles,
            "positions": [p.to_dict() for p in self.positions.values()],
            "timestamp": datetime.now().isoformat(),
        }

    def run_daily(self) -> dict[str, Any]:
        """
        Run daily wheel strategy operations.

        1. Check existing positions
        2. Find new put opportunities
        3. Find new call opportunities
        4. Execute trades

        Returns:
            Daily execution summary
        """
        logger.info("Running Wheel Strategy daily operations...")

        results = {
            "positions_managed": [],
            "puts_executed": [],
            "calls_executed": [],
            "errors": [],
        }

        try:
            # 1. Manage existing positions
            results["positions_managed"] = self.check_and_manage_positions()

            # 2. Get available capital
            if self.trader:
                try:
                    if hasattr(self.trader, "get_account_info"):
                        account = self.trader.get_account_info()
                    else:
                        account = self.trader.get_account()
                    cash = float(account.get("cash", 0) or account.get("buying_power", 0))
                except Exception:
                    cash = 0
            else:
                cash = 0

            # 3. Find and execute put opportunities
            if cash > 5000:  # Minimum capital for wheel
                put_candidates = self.find_put_opportunities(max_capital=cash * 0.5)

                for candidate in put_candidates[:2]:  # Max 2 new positions
                    result = self.execute_put_trade(candidate)
                    if result:
                        results["puts_executed"].append(result)

            # 4. Find and execute call opportunities
            call_candidates = self.find_call_opportunities()
            for candidate in call_candidates:
                # Check if we're in ASSIGNED phase
                if candidate.symbol in self.positions:
                    position = self.positions[candidate.symbol]
                    if position.phase == WheelPhase.ASSIGNED:
                        result = self.execute_call_trade(candidate.symbol, position.shares_owned)
                        if result:
                            results["calls_executed"].append(result)

        except Exception as e:
            logger.error(f"Error in daily wheel operations: {e}")
            results["errors"].append(str(e))

        # Add summary
        results["summary"] = self.get_daily_summary()

        return results


# Convenience function for running wheel strategy
def run_wheel_strategy(paper: bool = True) -> dict[str, Any]:
    """
    Run the wheel strategy and return results.

    Args:
        paper: Use paper trading

    Returns:
        Execution results
    """
    strategy = WheelStrategy(paper=paper)
    return strategy.run_daily()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    strategy = WheelStrategy(paper=True)

    print("\n=== WHEEL STRATEGY ANALYSIS ===")
    print(f"Universe: {len(strategy.WHEEL_UNIVERSE)} stocks")

    # Find opportunities
    candidates = strategy.find_put_opportunities(max_capital=50000)

    print(f"\n--- Top Put Opportunities (${50000:,} capital) ---")
    for c in candidates[:5]:
        print(
            f"  {c.symbol}: ${c.current_price:.2f} → Put @ ${c.recommended_put_strike:.2f} "
            f"(IV Rank: {c.iv_rank or 'N/A'}, Quality: {c.quality_score:.0f}/100)"
        )

    print("\n--- Quality Ratings ---")
    for c in candidates[:5]:
        print(f"  {c.symbol}: {', '.join(c.quality_reasons)}")
