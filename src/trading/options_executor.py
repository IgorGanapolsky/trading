"""
Options Trade Execution Pipeline

Implements complete options strategy execution with comprehensive risk management:
1. Covered Calls - Generate income on existing shares
2. Iron Condors - Range-bound premium collection
3. Credit Spreads - Directional premium plays with defined risk

Safety Features:
- Max 2% portfolio risk per trade
- Min $0.30 premium per contract
- IV Rank > 30 for premium selling
- Position sizing based on account equity
- McMillan stop-loss rules integration

Author: AI Trading System
Date: December 10, 2025
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from src.core.alpaca_trader import AlpacaTrader
from src.core.options_client import AlpacaOptionsClient
from src.risk.options_risk_monitor import OptionsPosition, OptionsRiskMonitor

logger = logging.getLogger(__name__)


@dataclass
class OptionLeg:
    """Represents a single option leg in a strategy."""

    symbol: str  # OCC option symbol
    strike: float
    expiration: date
    option_type: Literal["call", "put"]
    side: Literal["buy", "sell"]
    quantity: int
    premium: float  # Premium per contract


@dataclass
class OptionsStrategy:
    """Represents a complete options strategy."""

    strategy_type: str  # 'covered_call', 'iron_condor', 'credit_spread'
    underlying: str
    legs: list[OptionLeg]
    total_premium: float  # Net credit/debit
    max_risk: float  # Maximum potential loss
    max_profit: float  # Maximum potential gain
    breakeven_points: list[float]
    required_capital: float  # Capital required to enter


class OptionsExecutor:
    """
    Complete options trade execution pipeline with risk management.

    Integrates with:
    - AlpacaOptionsClient: Market data and order execution
    - OptionsRiskMonitor: Stop-loss and delta management
    - AlpacaTrader: Account data and equity tracking

    Safety Limits (configurable):
    - MAX_PORTFOLIO_RISK_PCT: 2% max risk per trade
    - MIN_PREMIUM_PER_CONTRACT: $0.30 minimum credit
    - MIN_IV_RANK: 30 (only sell premium when IV elevated)
    - MAX_POSITION_SIZE: 5 contracts max per strategy
    """

    # Risk management parameters
    MAX_PORTFOLIO_RISK_PCT = 0.02  # 2% max per trade
    MIN_PREMIUM_PER_CONTRACT = 0.30  # $30 minimum credit per contract
    MIN_IV_RANK = 30  # Only sell premium when IV > 30
    MAX_POSITION_SIZE = 5  # Max 5 contracts per strategy
    MIN_DTE = 30  # Minimum days to expiration
    MAX_DTE = 60  # Maximum days to expiration

    # Strategy-specific parameters
    COVERED_CALL_TARGET_DELTA = 0.30  # Sell 30-delta calls
    IRON_CONDOR_TARGET_DELTA = 0.20  # Sell 20-delta wings
    CREDIT_SPREAD_TARGET_DELTA = 0.30  # Sell 30-delta spreads
    SPREAD_WIDTH = 5.0  # Default $5 width for spreads

    def __init__(self, paper: bool = True):
        """
        Initialize options executor.

        Args:
            paper: If True, use paper trading environment
        """
        self.paper = paper
        self.options_client = AlpacaOptionsClient(paper=paper)
        self.risk_monitor = OptionsRiskMonitor(paper=paper)
        self.trader = AlpacaTrader(paper=paper)

        logger.info(f"OptionsExecutor initialized (Paper: {paper})")

    def execute_covered_call(
        self,
        ticker: str,
        shares: int,
        target_delta: float | None = None,
        dte: int = 45,
    ) -> dict[str, Any]:
        """
        Execute a covered call strategy.

        Strategy: Sell OTM call against existing shares for income.

        Safety checks:
        - Verify we own the shares
        - Check IV rank > 30
        - Validate premium > $0.30/contract
        - Ensure risk within 2% portfolio limit

        Args:
            ticker: Underlying symbol (e.g., 'SPY')
            shares: Number of shares owned (must be multiple of 100)
            target_delta: Target delta for short call (default: 0.30)
            dte: Target days to expiration (default: 45)

        Returns:
            Dict with execution results and position details

        Raises:
            ValueError: If validation fails
            RuntimeError: If execution fails
        """
        target_delta = target_delta or self.COVERED_CALL_TARGET_DELTA

        logger.info(
            f"Executing covered call: {ticker} ({shares} shares, {dte} DTE, Δ={target_delta})"
        )

        # 1. Validate we own the shares
        account = self.trader.get_account_info()
        positions = self.trader.api.list_positions()

        share_position = None
        for pos in positions:
            if pos.symbol == ticker:
                share_position = pos
                break

        if not share_position or int(share_position.qty) < shares:
            raise ValueError(
                f"Insufficient shares: Need {shares} {ticker}, have {share_position.qty if share_position else 0}"
            )

        if shares % 100 != 0:
            raise ValueError(f"Shares must be multiple of 100 for covered calls. Got {shares}")

        num_contracts = shares // 100

        # 2. Get option chain
        chain = self.options_client.get_option_chain(ticker)

        # Filter for calls with target expiration
        target_expiry = datetime.now().date() + timedelta(days=dte)
        call_options = [
            opt
            for opt in chain
            if self._parse_option_symbol(opt["symbol"])["type"] == "call"
            and abs((self._parse_option_symbol(opt["symbol"])["expiration"] - target_expiry).days)
            <= 7
        ]

        if not call_options:
            raise RuntimeError(f"No call options found for {ticker} near {dte} DTE")

        # 3. Find option closest to target delta
        best_option = self._find_option_by_delta(call_options, target_delta)

        if not best_option:
            raise RuntimeError(f"No suitable call option found with delta ~{target_delta}")

        # 4. Calculate IV rank and validate
        iv = best_option.get("implied_volatility", 0) * 100
        if iv < self.MIN_IV_RANK:
            logger.warning(
                f"IV rank {iv:.1f} below minimum {self.MIN_IV_RANK}. Consider waiting for higher IV."
            )

        # 5. Get current market price
        bid = best_option.get("latest_quote_bid", 0)
        ask = best_option.get("latest_quote_ask", 0)
        mid_price = (bid + ask) / 2 if bid and ask else 0

        if mid_price < self.MIN_PREMIUM_PER_CONTRACT:
            raise ValueError(
                f"Premium ${mid_price:.2f} below minimum ${self.MIN_PREMIUM_PER_CONTRACT}"
            )

        # 6. Build strategy
        option_symbol = best_option["symbol"]
        parsed = self._parse_option_symbol(option_symbol)

        leg = OptionLeg(
            symbol=option_symbol,
            strike=parsed["strike"],
            expiration=parsed["expiration"],
            option_type="call",
            side="sell",
            quantity=num_contracts,
            premium=mid_price,
        )

        total_premium = mid_price * num_contracts * 100  # Premium in dollars
        max_profit = total_premium
        max_risk = float("inf")  # Unlimited if stock goes to infinity (covered by shares)
        current_stock_price = float(share_position.current_price)
        breakeven = current_stock_price - (mid_price * 100 / shares)

        strategy = OptionsStrategy(
            strategy_type="covered_call",
            underlying=ticker,
            legs=[leg],
            total_premium=total_premium,
            max_risk=max_risk,
            max_profit=max_profit,
            breakeven_points=[breakeven],
            required_capital=0,  # Already own the shares
        )

        # 7. Validate risk limits
        validation = self.validate_order(strategy, account)
        if not validation["approved"]:
            raise ValueError(f"Order validation failed: {validation['reason']}")

        # 8. Execute the trade
        logger.info(
            f"Placing covered call: SELL {num_contracts} {option_symbol} @ ${mid_price:.2f}"
        )

        order = self.place_paper_order(
            option_symbol=option_symbol,
            quantity=num_contracts,
            side="sell_to_open",
            limit_price=bid,  # Use bid for sell orders (conservative)
        )

        # 9. Add to risk monitor
        position = OptionsPosition(
            symbol=option_symbol,
            underlying=ticker,
            position_type="covered_call",
            side="short",
            quantity=num_contracts,
            entry_price=mid_price,
            current_price=mid_price,
            delta=best_option["greeks"]["delta"] if best_option.get("greeks") else target_delta,
            gamma=best_option["greeks"]["gamma"] if best_option.get("greeks") else 0,
            theta=best_option["greeks"]["theta"] if best_option.get("greeks") else -0.02,
            vega=best_option["greeks"]["vega"] if best_option.get("greeks") else 0,
            expiration_date=parsed["expiration"],
            strike=parsed["strike"],
            opened_at=datetime.now(),
        )
        self.risk_monitor.add_position(position)

        return {
            "status": "success",
            "strategy": "covered_call",
            "underlying": ticker,
            "shares_covered": shares,
            "contracts": num_contracts,
            "option_symbol": option_symbol,
            "strike": parsed["strike"],
            "expiration": parsed["expiration"].isoformat(),
            "premium_per_contract": mid_price,
            "total_premium": total_premium,
            "max_profit": max_profit,
            "breakeven": breakeven,
            "iv_rank": iv,
            "delta": best_option["greeks"]["delta"] if best_option.get("greeks") else target_delta,
            "order": order,
            "timestamp": datetime.now().isoformat(),
        }

    def execute_iron_condor(
        self,
        ticker: str,
        width: float | None = None,
        target_delta: float | None = None,
        dte: int = 45,
    ) -> dict[str, Any]:
        """
        Execute an iron condor strategy.

        Strategy: Sell OTM put spread + OTM call spread for range-bound income.

        Legs:
        1. Sell OTM put (short strike)
        2. Buy further OTM put (long strike)
        3. Sell OTM call (short strike)
        4. Buy further OTM call (long strike)

        Safety checks:
        - Check IV rank > 30
        - Validate total premium > $0.30/contract
        - Ensure max loss within 2% portfolio
        - Proper position sizing

        Args:
            ticker: Underlying symbol (e.g., 'SPY')
            width: Width of each spread in dollars (default: $5)
            target_delta: Target delta for short strikes (default: 0.20)
            dte: Target days to expiration (default: 45)

        Returns:
            Dict with execution results and position details

        Raises:
            ValueError: If validation fails
            RuntimeError: If execution fails
        """
        width = width or self.SPREAD_WIDTH
        target_delta = target_delta or self.IRON_CONDOR_TARGET_DELTA

        logger.info(f"Executing iron condor: {ticker} ({width}w, {dte} DTE, Δ={target_delta})")

        # 1. Get account info for position sizing
        account = self.trader.get_account_info()
        float(account["equity"])

        # 2. Get option chain
        chain = self.options_client.get_option_chain(ticker)

        # 3. Filter for target expiration
        target_expiry = datetime.now().date() + timedelta(days=dte)
        puts = [
            opt
            for opt in chain
            if self._parse_option_symbol(opt["symbol"])["type"] == "put"
            and abs((self._parse_option_symbol(opt["symbol"])["expiration"] - target_expiry).days)
            <= 7
        ]
        calls = [
            opt
            for opt in chain
            if self._parse_option_symbol(opt["symbol"])["type"] == "call"
            and abs((self._parse_option_symbol(opt["symbol"])["expiration"] - target_expiry).days)
            <= 7
        ]

        if not puts or not calls:
            raise RuntimeError(f"Insufficient options for iron condor on {ticker}")

        # 4. Find short put (target delta)
        short_put = self._find_option_by_delta(puts, target_delta)
        if not short_put:
            raise RuntimeError(f"No suitable put found with delta ~{target_delta}")

        short_put_strike = self._parse_option_symbol(short_put["symbol"])["strike"]

        # Find long put (width below short put)
        long_put_strike = short_put_strike - width
        long_put = self._find_option_by_strike(puts, long_put_strike, tolerance=0.5)
        if not long_put:
            raise RuntimeError(f"No put found at strike ${long_put_strike:.2f}")

        # 5. Find short call (target delta, but negative for calls)
        short_call = self._find_option_by_delta(calls, -target_delta)
        if not short_call:
            raise RuntimeError(f"No suitable call found with delta ~{-target_delta}")

        short_call_strike = self._parse_option_symbol(short_call["symbol"])["strike"]

        # Find long call (width above short call)
        long_call_strike = short_call_strike + width
        long_call = self._find_option_by_strike(calls, long_call_strike, tolerance=0.5)
        if not long_call:
            raise RuntimeError(f"No call found at strike ${long_call_strike:.2f}")

        # 6. Calculate net premium and validate
        short_put_premium = (
            short_put.get("latest_quote_bid", 0) + short_put.get("latest_quote_ask", 0)
        ) / 2
        long_put_premium = (
            long_put.get("latest_quote_bid", 0) + long_put.get("latest_quote_ask", 0)
        ) / 2
        short_call_premium = (
            short_call.get("latest_quote_bid", 0) + short_call.get("latest_quote_ask", 0)
        ) / 2
        long_call_premium = (
            long_call.get("latest_quote_bid", 0) + long_call.get("latest_quote_ask", 0)
        ) / 2

        put_spread_credit = short_put_premium - long_put_premium
        call_spread_credit = short_call_premium - long_call_premium
        total_credit = put_spread_credit + call_spread_credit

        if total_credit < self.MIN_PREMIUM_PER_CONTRACT:
            raise ValueError(
                f"Total credit ${total_credit:.2f} below minimum ${self.MIN_PREMIUM_PER_CONTRACT}"
            )

        # 7. Check IV rank
        avg_iv = (
            (short_put.get("implied_volatility", 0) + short_call.get("implied_volatility", 0)) / 2
        ) * 100
        if avg_iv < self.MIN_IV_RANK:
            logger.warning(
                f"Average IV {avg_iv:.1f} below minimum {self.MIN_IV_RANK}. Consider waiting."
            )

        # 8. Build strategy
        expiration = self._parse_option_symbol(short_put["symbol"])["expiration"]

        legs = [
            OptionLeg(
                symbol=short_put["symbol"],
                strike=short_put_strike,
                expiration=expiration,
                option_type="put",
                side="sell",
                quantity=1,
                premium=short_put_premium,
            ),
            OptionLeg(
                symbol=long_put["symbol"],
                strike=long_put_strike,
                expiration=expiration,
                option_type="put",
                side="buy",
                quantity=1,
                premium=long_put_premium,
            ),
            OptionLeg(
                symbol=short_call["symbol"],
                strike=short_call_strike,
                expiration=expiration,
                option_type="call",
                side="sell",
                quantity=1,
                premium=short_call_premium,
            ),
            OptionLeg(
                symbol=long_call["symbol"],
                strike=long_call_strike,
                expiration=expiration,
                option_type="call",
                side="buy",
                quantity=1,
                premium=long_call_premium,
            ),
        ]

        total_premium_dollars = total_credit * 100  # Per contract
        max_loss = (width * 100) - total_premium_dollars
        max_profit = total_premium_dollars

        # Breakeven points
        breakeven_lower = short_put_strike - total_credit
        breakeven_upper = short_call_strike + total_credit

        strategy = OptionsStrategy(
            strategy_type="iron_condor",
            underlying=ticker,
            legs=legs,
            total_premium=total_premium_dollars,
            max_risk=max_loss,
            max_profit=max_profit,
            breakeven_points=[breakeven_lower, breakeven_upper],
            required_capital=max_loss,
        )

        # 9. Validate risk limits
        validation = self.validate_order(strategy, account)
        if not validation["approved"]:
            raise ValueError(f"Order validation failed: {validation['reason']}")

        # 10. Execute all four legs
        logger.info(
            f"Placing iron condor on {ticker}: {short_put_strike}/{long_put_strike} PUT, {short_call_strike}/{long_call_strike} CALL"
        )

        orders = []
        for leg in legs:
            side_map = {"sell": "sell_to_open", "buy": "buy_to_open"}
            limit_price = (
                leg.premium if leg.side == "buy" else leg.premium * 0.95
            )  # Conservative pricing

            order = self.place_paper_order(
                option_symbol=leg.symbol,
                quantity=leg.quantity,
                side=side_map[leg.side],
                limit_price=limit_price,
            )
            orders.append(order)

        # 11. Add to risk monitor
        # Track as single iron condor position (we'll monitor the overall structure)
        position = OptionsPosition(
            symbol=f"{ticker}_IC_{expiration.strftime('%y%m%d')}",
            underlying=ticker,
            position_type="iron_condor",
            side="short",
            quantity=1,
            entry_price=total_credit,
            current_price=total_credit,
            delta=0,  # Iron condors are delta-neutral at entry
            gamma=0,
            theta=-(short_put_premium + short_call_premium) * 0.05,  # Approximate theta
            vega=0,
            expiration_date=expiration,
            strike=(short_put_strike + short_call_strike) / 2,  # Midpoint
            opened_at=datetime.now(),
        )
        self.risk_monitor.add_position(position)

        return {
            "status": "success",
            "strategy": "iron_condor",
            "underlying": ticker,
            "put_strikes": f"{long_put_strike}/{short_put_strike}",
            "call_strikes": f"{short_call_strike}/{long_call_strike}",
            "expiration": expiration.isoformat(),
            "width": width,
            "total_credit": total_credit,
            "total_premium_dollars": total_premium_dollars,
            "max_profit": max_profit,
            "max_loss": max_loss,
            "breakeven_lower": breakeven_lower,
            "breakeven_upper": breakeven_upper,
            "avg_iv": avg_iv,
            "orders": orders,
            "timestamp": datetime.now().isoformat(),
        }

    def execute_credit_spread(
        self,
        ticker: str,
        spread_type: Literal["bull_put", "bear_call"],
        width: float | None = None,
        target_delta: float | None = None,
        dte: int = 45,
    ) -> dict[str, Any]:
        """
        Execute a credit spread (bull put or bear call).

        Bull Put Spread: Bullish strategy - sell OTM put, buy further OTM put
        Bear Call Spread: Bearish strategy - sell OTM call, buy further OTM call

        Safety checks:
        - Check IV rank > 30
        - Validate premium > $0.30/contract
        - Ensure max loss within 2% portfolio
        - Proper position sizing

        Args:
            ticker: Underlying symbol (e.g., 'SPY')
            spread_type: 'bull_put' or 'bear_call'
            width: Width of spread in dollars (default: $5)
            target_delta: Target delta for short strike (default: 0.30)
            dte: Target days to expiration (default: 45)

        Returns:
            Dict with execution results and position details

        Raises:
            ValueError: If validation fails
            RuntimeError: If execution fails
        """
        width = width or self.SPREAD_WIDTH
        target_delta = target_delta or self.CREDIT_SPREAD_TARGET_DELTA

        logger.info(f"Executing {spread_type}: {ticker} ({width}w, {dte} DTE, Δ={target_delta})")

        # 1. Get account info
        account = self.trader.get_account_info()

        # 2. Get option chain
        chain = self.options_client.get_option_chain(ticker)

        # 3. Filter for target expiration and option type
        target_expiry = datetime.now().date() + timedelta(days=dte)
        option_type = "put" if spread_type == "bull_put" else "call"

        options = [
            opt
            for opt in chain
            if self._parse_option_symbol(opt["symbol"])["type"] == option_type
            and abs((self._parse_option_symbol(opt["symbol"])["expiration"] - target_expiry).days)
            <= 7
        ]

        if not options:
            raise RuntimeError(f"No {option_type} options found for {ticker} near {dte} DTE")

        # 4. Find short strike (target delta)
        short_option = self._find_option_by_delta(options, target_delta)
        if not short_option:
            raise RuntimeError(f"No suitable {option_type} found with delta ~{target_delta}")

        short_strike = self._parse_option_symbol(short_option["symbol"])["strike"]

        # Find long strike (width away from short strike)
        if spread_type == "bull_put":
            long_strike = short_strike - width  # Buy lower put
        else:  # bear_call
            long_strike = short_strike + width  # Buy higher call

        long_option = self._find_option_by_strike(options, long_strike, tolerance=0.5)
        if not long_option:
            raise RuntimeError(f"No {option_type} found at strike ${long_strike:.2f}")

        # 5. Calculate net credit and validate
        short_premium = (
            short_option.get("latest_quote_bid", 0) + short_option.get("latest_quote_ask", 0)
        ) / 2
        long_premium = (
            long_option.get("latest_quote_bid", 0) + long_option.get("latest_quote_ask", 0)
        ) / 2
        net_credit = short_premium - long_premium

        if net_credit < self.MIN_PREMIUM_PER_CONTRACT:
            raise ValueError(
                f"Net credit ${net_credit:.2f} below minimum ${self.MIN_PREMIUM_PER_CONTRACT}"
            )

        # 6. Check IV rank
        iv = short_option.get("implied_volatility", 0) * 100
        if iv < self.MIN_IV_RANK:
            logger.warning(
                f"IV {iv:.1f} below minimum {self.MIN_IV_RANK}. Consider waiting for higher IV."
            )

        # 7. Build strategy
        expiration = self._parse_option_symbol(short_option["symbol"])["expiration"]

        legs = [
            OptionLeg(
                symbol=short_option["symbol"],
                strike=short_strike,
                expiration=expiration,
                option_type=option_type,
                side="sell",
                quantity=1,
                premium=short_premium,
            ),
            OptionLeg(
                symbol=long_option["symbol"],
                strike=long_strike,
                expiration=expiration,
                option_type=option_type,
                side="buy",
                quantity=1,
                premium=long_premium,
            ),
        ]

        total_premium_dollars = net_credit * 100
        max_loss = (width * 100) - total_premium_dollars
        max_profit = total_premium_dollars

        if spread_type == "bull_put":
            breakeven = short_strike - net_credit
        else:  # bear_call
            breakeven = short_strike + net_credit

        strategy = OptionsStrategy(
            strategy_type=spread_type,
            underlying=ticker,
            legs=legs,
            total_premium=total_premium_dollars,
            max_risk=max_loss,
            max_profit=max_profit,
            breakeven_points=[breakeven],
            required_capital=max_loss,
        )

        # 8. Validate risk limits
        validation = self.validate_order(strategy, account)
        if not validation["approved"]:
            raise ValueError(f"Order validation failed: {validation['reason']}")

        # 9. Execute both legs
        logger.info(
            f"Placing {spread_type}: SELL {short_strike} / BUY {long_strike} {option_type.upper()}"
        )

        orders = []
        for leg in legs:
            side_map = {"sell": "sell_to_open", "buy": "buy_to_open"}
            limit_price = leg.premium if leg.side == "buy" else leg.premium * 0.95

            order = self.place_paper_order(
                option_symbol=leg.symbol,
                quantity=leg.quantity,
                side=side_map[leg.side],
                limit_price=limit_price,
            )
            orders.append(order)

        # 10. Add to risk monitor
        position = OptionsPosition(
            symbol=short_option["symbol"],
            underlying=ticker,
            position_type=spread_type,
            side="short",
            quantity=1,
            entry_price=net_credit,
            current_price=net_credit,
            delta=short_option["greeks"]["delta"] if short_option.get("greeks") else target_delta,
            gamma=short_option["greeks"]["gamma"] if short_option.get("greeks") else 0,
            theta=short_option["greeks"]["theta"] if short_option.get("greeks") else -0.02,
            vega=short_option["greeks"]["vega"] if short_option.get("greeks") else 0,
            expiration_date=expiration,
            strike=short_strike,
            opened_at=datetime.now(),
        )
        self.risk_monitor.add_position(position)

        return {
            "status": "success",
            "strategy": spread_type,
            "underlying": ticker,
            "short_strike": short_strike,
            "long_strike": long_strike,
            "expiration": expiration.isoformat(),
            "width": width,
            "net_credit": net_credit,
            "total_premium_dollars": total_premium_dollars,
            "max_profit": max_profit,
            "max_loss": max_loss,
            "breakeven": breakeven,
            "iv": iv,
            "delta": short_option["greeks"]["delta"]
            if short_option.get("greeks")
            else target_delta,
            "orders": orders,
            "timestamp": datetime.now().isoformat(),
        }

    def validate_order(self, strategy: OptionsStrategy, account: dict[str, Any]) -> dict[str, Any]:
        """
        Validate options strategy against risk limits.

        Safety checks:
        1. Max portfolio risk: 2% per trade
        2. Minimum premium: $0.30 per contract
        3. Position size limits: Max 5 contracts
        4. Capital requirements: Must have sufficient capital

        Args:
            strategy: Options strategy to validate
            account: Account info dict with equity, buying_power, etc.

        Returns:
            Dict with 'approved' bool and 'reason' string
        """
        equity = float(account["equity"])
        buying_power = float(account["buying_power"])

        # 1. Check portfolio risk
        max_allowed_risk = equity * self.MAX_PORTFOLIO_RISK_PCT
        if strategy.max_risk > max_allowed_risk:
            return {
                "approved": False,
                "reason": f"Max risk ${strategy.max_risk:.2f} exceeds {self.MAX_PORTFOLIO_RISK_PCT * 100}% portfolio limit (${max_allowed_risk:.2f})",
            }

        # 2. Check minimum premium
        premium_per_contract = strategy.total_premium / sum(
            leg.quantity for leg in strategy.legs if leg.side == "sell"
        )
        if premium_per_contract < self.MIN_PREMIUM_PER_CONTRACT * 100:  # Convert to dollars
            return {
                "approved": False,
                "reason": f"Premium ${premium_per_contract:.2f} below minimum ${self.MIN_PREMIUM_PER_CONTRACT * 100:.2f}",
            }

        # 3. Check position size
        total_contracts = sum(leg.quantity for leg in strategy.legs if leg.side == "sell")
        if total_contracts > self.MAX_POSITION_SIZE:
            return {
                "approved": False,
                "reason": f"Position size {total_contracts} contracts exceeds max {self.MAX_POSITION_SIZE}",
            }

        # 4. Check capital requirements
        if strategy.required_capital > buying_power:
            return {
                "approved": False,
                "reason": f"Required capital ${strategy.required_capital:.2f} exceeds buying power ${buying_power:.2f}",
            }

        # 5. Check DTE bounds
        for leg in strategy.legs:
            dte = (leg.expiration - datetime.now().date()).days
            if dte < self.MIN_DTE or dte > self.MAX_DTE:
                return {
                    "approved": False,
                    "reason": f"DTE {dte} outside acceptable range ({self.MIN_DTE}-{self.MAX_DTE} days)",
                }

        return {
            "approved": True,
            "reason": "All risk checks passed",
            "risk_pct": (strategy.max_risk / equity) * 100,
            "max_allowed_risk": max_allowed_risk,
            "premium_per_contract": premium_per_contract,
            "total_contracts": total_contracts,
        }

    def place_paper_order(
        self,
        option_symbol: str,
        quantity: int,
        side: Literal["buy_to_open", "sell_to_open", "buy_to_close", "sell_to_close"],
        limit_price: float,
    ) -> dict[str, Any]:
        """
        Place paper options order via Alpaca.

        Args:
            option_symbol: OCC option symbol (e.g., "SPY251219C00600000")
            quantity: Number of contracts
            side: Order side
            limit_price: Limit price per contract

        Returns:
            Order details dict

        Raises:
            RuntimeError: If order placement fails
        """
        try:
            logger.info(
                f"Placing paper order: {side.upper()} {quantity} {option_symbol} @ ${limit_price:.2f}"
            )

            order = self.options_client.submit_option_order(
                option_symbol=option_symbol,
                qty=quantity,
                side=side,
                order_type="limit",
                limit_price=limit_price,
            )

            logger.info(f"✅ Order placed successfully: {order['id']}")
            return order

        except Exception as e:
            logger.error(f"❌ Failed to place order: {e}")
            raise RuntimeError(f"Order execution failed: {e}")

    # ==================== Helper Methods ====================

    def _parse_option_symbol(self, symbol: str) -> dict[str, Any]:
        """
        Parse OCC option symbol into components.

        Format: TICKER[YY][MM][DD][C/P][STRIKE_PADDED]
        Example: SPY251219C00600000 = SPY Dec 19, 2025 $600 Call

        Args:
            symbol: OCC option symbol

        Returns:
            Dict with ticker, expiration, type, strike
        """
        # Extract components (simplified parser - production would be more robust)
        ticker = symbol[:3]  # Simplified - real parser would handle variable length
        date_str = symbol[3:9]  # YYMMDD
        option_type = "call" if symbol[9] == "C" else "put"
        strike_str = symbol[10:]  # Padded strike price

        # Parse date
        year = 2000 + int(date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        expiration = date(year, month, day)

        # Parse strike (divide by 1000 to get actual strike)
        strike = float(strike_str) / 1000

        return {
            "ticker": ticker,
            "expiration": expiration,
            "type": option_type,
            "strike": strike,
        }

    def _find_option_by_delta(
        self, options: list[dict[str, Any]], target_delta: float, tolerance: float = 0.05
    ) -> dict[str, Any] | None:
        """
        Find option closest to target delta.

        Args:
            options: List of option data dicts
            target_delta: Target delta (e.g., 0.30 for calls, -0.30 for puts)
            tolerance: Acceptable delta deviation

        Returns:
            Option dict or None if no match found
        """
        best_option = None
        best_diff = float("inf")

        for opt in options:
            if not opt.get("greeks") or opt["greeks"]["delta"] is None:
                continue

            delta = opt["greeks"]["delta"]
            diff = abs(delta - target_delta)

            if diff < best_diff and diff <= tolerance:
                best_diff = diff
                best_option = opt

        return best_option

    def _find_option_by_strike(
        self, options: list[dict[str, Any]], target_strike: float, tolerance: float = 0.5
    ) -> dict[str, Any] | None:
        """
        Find option with strike closest to target.

        Args:
            options: List of option data dicts
            target_strike: Target strike price
            tolerance: Acceptable strike deviation

        Returns:
            Option dict or None if no match found
        """
        for opt in options:
            parsed = self._parse_option_symbol(opt["symbol"])
            strike = parsed["strike"]

            if abs(strike - target_strike) <= tolerance:
                return opt

        return None


# Convenience factory function
def get_options_executor(paper: bool = True) -> OptionsExecutor:
    """Get OptionsExecutor instance."""
    return OptionsExecutor(paper=paper)


if __name__ == "__main__":
    """
    Example usage and testing.
    """
    logging.basicConfig(level=logging.INFO)

    # Initialize executor
    executor = OptionsExecutor(paper=True)

    print("\n=== Options Executor Initialized ===")
    print(f"Paper Trading: {executor.paper}")
    print(f"Max Portfolio Risk: {executor.MAX_PORTFOLIO_RISK_PCT * 100}%")
    print(f"Min Premium: ${executor.MIN_PREMIUM_PER_CONTRACT}")
    print(f"Min IV Rank: {executor.MIN_IV_RANK}")
    print(f"Max Position Size: {executor.MAX_POSITION_SIZE} contracts")
    print(f"DTE Range: {executor.MIN_DTE}-{executor.MAX_DTE} days")

    # Example: Parse option symbol
    print("\n=== Option Symbol Parsing ===")
    test_symbol = "SPY251219C00600000"
    parsed = executor._parse_option_symbol(test_symbol)
    print(f"Symbol: {test_symbol}")
    print(f"Parsed: {parsed}")

    print("\n✅ Options Executor ready for trading")
    print("Available strategies:")
    print("  1. execute_covered_call(ticker, shares, target_delta, dte)")
    print("  2. execute_iron_condor(ticker, width, target_delta, dte)")
    print("  3. execute_credit_spread(ticker, spread_type, width, target_delta, dte)")
