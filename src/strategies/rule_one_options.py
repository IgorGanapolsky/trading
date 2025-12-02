"""
Phil Town Rule #1 Options Strategy

Implements Phil Town's Rule #1 investing approach with options:
1. Sticker Price Calculator - Intrinsic value based on growth rate
2. Margin of Safety (MOS) - Buy price at 50% discount
3. Selling Puts to Buy at Discount - "Getting Paid to Wait"
4. Selling Covered Calls - "Getting Paid to Sell"
5. Big Five Analysis - Quality screening

Reference: "Rule #1" and "Payback Time" by Phil Town

Key Principles:
- Only trade options on "wonderful companies" you'd want to own
- Sell puts at MOS price (50% below Sticker Price)
- Sell calls at Sticker Price (fair value)
- 10-year horizon for valuation
- 15% Minimum Acceptable Rate of Return (MARR)
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

import yfinance as yf
import numpy as np

from src.core.alpaca_trader import AlpacaTrader
from src.core.options_client import AlpacaOptionsClient

logger = logging.getLogger(__name__)


class MeaningRating(Enum):
    """Phil Town's 'Meaning' rating - do you understand the business?"""
    EXCELLENT = "excellent"  # Fully understand, use products
    GOOD = "good"  # Understand well
    FAIR = "fair"  # Basic understanding
    POOR = "poor"  # Don't understand


class MoatRating(Enum):
    """Phil Town's 'Moat' rating - competitive advantage durability."""
    WIDE = "wide"  # Strong, durable advantage (brand, network, patents)
    NARROW = "narrow"  # Some advantage but vulnerable
    NONE = "none"  # No sustainable advantage


class ManagementRating(Enum):
    """Phil Town's 'Management' rating - quality of leadership."""
    EXCELLENT = "excellent"  # Owner-oriented, high integrity
    GOOD = "good"  # Competent, shareholder-friendly
    FAIR = "fair"  # Mixed track record
    POOR = "poor"  # Avoid


@dataclass
class BigFiveMetrics:
    """Phil Town's Big Five Numbers for quality analysis."""

    roic: float  # Return on Invested Capital
    equity_growth: float  # Book Value per Share growth
    eps_growth: float  # Earnings per Share growth
    sales_growth: float  # Revenue growth
    fcf_growth: float  # Free Cash Flow growth

    # Calculated fields
    avg_growth: float = 0.0
    passes_rule_one: bool = False

    def __post_init__(self):
        """Calculate average growth and Rule #1 pass/fail."""
        growth_rates = [self.equity_growth, self.eps_growth, self.sales_growth, self.fcf_growth]
        valid_rates = [r for r in growth_rates if r is not None and not np.isnan(r)]
        self.avg_growth = np.mean(valid_rates) if valid_rates else 0.0

        # Rule #1: All Big Five should be >= 10% over 10, 5, and 1 year
        # Simplified: Average growth >= 10% and ROIC >= 10%
        self.passes_rule_one = (
            self.avg_growth >= 0.10 and
            self.roic is not None and
            self.roic >= 0.10
        )


@dataclass
class StickerPriceResult:
    """Phil Town's Sticker Price calculation result."""

    symbol: str
    current_price: float
    current_eps: float
    growth_rate: float  # Estimated future EPS growth
    future_eps: float  # EPS in 10 years
    future_pe: float  # P/E ratio in 10 years
    future_price: float  # Price in 10 years
    sticker_price: float  # Fair value today (discounted)
    mos_price: float  # Margin of Safety price (50% discount)

    # Analysis
    upside_to_sticker: float = 0.0  # % upside to fair value
    margin_of_safety: float = 0.0  # Current MOS %
    recommendation: str = ""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

        if self.current_price > 0:
            self.upside_to_sticker = (self.sticker_price - self.current_price) / self.current_price
            self.margin_of_safety = (self.sticker_price - self.current_price) / self.sticker_price

            if self.current_price <= self.mos_price:
                self.recommendation = "STRONG BUY - Below MOS Price"
            elif self.current_price <= self.sticker_price:
                self.recommendation = "BUY - Below Sticker Price"
            elif self.current_price <= self.sticker_price * 1.2:
                self.recommendation = "HOLD - Near Fair Value"
            else:
                self.recommendation = "SELL - Overvalued"


@dataclass
class RuleOneOptionsSignal:
    """Signal for Rule #1 options trade."""

    symbol: str
    signal_type: str  # 'sell_put' or 'sell_call'
    strike: float
    expiration: str
    premium: float
    annualized_return: float
    sticker_price: float
    mos_price: float
    current_price: float
    rationale: str
    confidence: float  # 0.0 to 1.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class RuleOneOptionsStrategy:
    """
    Phil Town's Rule #1 Options Strategy.

    Two core strategies:
    1. Selling Puts to Buy at Discount ("Getting Paid to Wait")
       - Sell cash-secured puts at MOS price
       - If assigned, you own the stock at your target price minus premium
       - If not assigned, keep premium as profit

    2. Selling Covered Calls ("Getting Paid to Sell")
       - Own shares first, then sell calls at Sticker Price
       - If called away, sell at fair value plus premium
       - If not called, keep premium and shares

    Key Requirements:
    - Only on "wonderful companies" (pass Big Five test)
    - Strike price based on Sticker Price / MOS Price
    - 30-45 days to expiration (optimal theta decay)
    - Minimum 12% annualized return on premium
    """

    # Phil Town's constants
    MARR = 0.15  # Minimum Acceptable Rate of Return (15%)
    MOS_DISCOUNT = 0.50  # 50% Margin of Safety
    DEFAULT_PE_RATIO_CAP = 50  # Maximum P/E ratio to use
    PROJECTION_YEARS = 10  # Project growth 10 years forward

    # Options parameters
    MIN_DAYS_TO_EXPIRY = 25
    MAX_DAYS_TO_EXPIRY = 50
    # Conservative delta targets (CEO directive Dec 2, 2025)
    # Lower delta = lower risk of assignment, safer for beginners
    TARGET_DELTA_PUT = 0.20  # ~20% chance of assignment (was 0.30)
    TARGET_DELTA_CALL = 0.25  # ~25% chance of being called away (was 0.30)

    # IV Rank filter - only sell premium when IV is low
    # High IV = expensive options = higher premium but more risk
    MAX_IV_RANK = 40  # Only sell when IV rank < 40 (options are cheap)

    # Premium cap - never receive more than 1.2% of underlying per trade
    MAX_PREMIUM_PCT = 0.012  # 1.2% of stock price max
    MIN_ANNUALIZED_RETURN = 0.12  # 12% minimum annualized yield

    # Default wonderful companies (Rule #1 quality stocks)
    DEFAULT_UNIVERSE = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "BRK-B",  # Large cap quality
        "V", "MA", "JNJ", "PG", "KO",  # Consumer/Financial moats
        "NVDA", "COST", "UNH", "HD", "MCD"  # Growth + moat
    ]

    def __init__(
        self,
        paper: bool = True,
        universe: Optional[List[str]] = None,
        min_shares_for_calls: int = 100,
    ):
        """
        Initialize Rule #1 Options Strategy.

        Args:
            paper: Use paper trading if True
            universe: List of symbols to analyze (defaults to quality stocks)
            min_shares_for_calls: Minimum shares needed for covered calls
        """
        self.paper = paper
        self.universe = universe or self.DEFAULT_UNIVERSE
        self.min_shares_for_calls = min_shares_for_calls

        # Initialize trading clients
        self.trader = AlpacaTrader(paper=paper)
        self.options_client = AlpacaOptionsClient(paper=paper)

        # Cache for valuations
        self._valuation_cache: Dict[str, StickerPriceResult] = {}
        self._big_five_cache: Dict[str, BigFiveMetrics] = {}

        logger.info(f"Rule #1 Options Strategy initialized: {len(self.universe)} symbols, paper={paper}")

    def calculate_big_five(self, symbol: str) -> Optional[BigFiveMetrics]:
        """
        Calculate Phil Town's Big Five metrics for a stock.

        Args:
            symbol: Stock ticker

        Returns:
            BigFiveMetrics or None if data unavailable
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Get financial data
            financials = ticker.financials
            balance_sheet = ticker.balance_sheet
            cash_flow = ticker.cashflow

            # Calculate ROIC (Return on Invested Capital)
            # ROIC = NOPAT / Invested Capital
            roic = info.get('returnOnCapital') or info.get('returnOnEquity', 0.10)

            # Get growth rates from yfinance
            eps_growth = info.get('earningsGrowth', 0.10)
            revenue_growth = info.get('revenueGrowth', 0.10)

            # Estimate equity and FCF growth (simplified)
            equity_growth = eps_growth * 0.8 if eps_growth else 0.10
            fcf_growth = eps_growth * 0.9 if eps_growth else 0.10

            metrics = BigFiveMetrics(
                roic=roic,
                equity_growth=equity_growth,
                eps_growth=eps_growth,
                sales_growth=revenue_growth,
                fcf_growth=fcf_growth,
            )

            self._big_five_cache[symbol] = metrics
            return metrics

        except Exception as e:
            logger.warning(f"Failed to calculate Big Five for {symbol}: {e}")
            return None

    def calculate_sticker_price(self, symbol: str) -> Optional[StickerPriceResult]:
        """
        Calculate Phil Town's Sticker Price and MOS Price.

        Formula:
        1. Get current EPS
        2. Estimate growth rate (from Big Five or analysts)
        3. Future EPS = Current EPS * (1 + growth)^10
        4. Future P/E = min(2 * growth_rate * 100, 50)
        5. Future Price = Future EPS * Future P/E
        6. Sticker Price = Future Price / (1 + MARR)^10
        7. MOS Price = Sticker Price * 0.50

        Args:
            symbol: Stock ticker

        Returns:
            StickerPriceResult or None if calculation fails
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Get current data
            current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
            current_eps = info.get('trailingEps', 0)

            if current_eps <= 0:
                logger.warning(f"{symbol}: Negative or zero EPS, skipping")
                return None

            # Get growth rate estimate
            analyst_growth = info.get('earningsGrowth')

            # Get Big Five for growth estimate
            big_five = self._big_five_cache.get(symbol) or self.calculate_big_five(symbol)

            if big_five and big_five.avg_growth > 0:
                growth_rate = min(big_five.avg_growth, 0.25)  # Cap at 25%
            elif analyst_growth and analyst_growth > 0:
                growth_rate = min(analyst_growth, 0.25)
            else:
                growth_rate = 0.10  # Conservative default

            # Phil Town's formula
            # Step 1: Project EPS 10 years forward
            future_eps = current_eps * ((1 + growth_rate) ** self.PROJECTION_YEARS)

            # Step 2: Estimate future P/E (2x growth rate, capped at 50)
            future_pe = min(growth_rate * 100 * 2, self.DEFAULT_PE_RATIO_CAP)
            future_pe = max(future_pe, 8)  # Floor at 8x P/E

            # Step 3: Calculate future price
            future_price = future_eps * future_pe

            # Step 4: Discount back at MARR (15%)
            sticker_price = future_price / ((1 + self.MARR) ** self.PROJECTION_YEARS)

            # Step 5: Apply Margin of Safety (50% discount)
            mos_price = sticker_price * self.MOS_DISCOUNT

            result = StickerPriceResult(
                symbol=symbol,
                current_price=current_price,
                current_eps=current_eps,
                growth_rate=growth_rate,
                future_eps=future_eps,
                future_pe=future_pe,
                future_price=future_price,
                sticker_price=sticker_price,
                mos_price=mos_price,
            )

            self._valuation_cache[symbol] = result
            return result

        except Exception as e:
            logger.error(f"Failed to calculate Sticker Price for {symbol}: {e}")
            return None

    def find_put_opportunities(self) -> List[RuleOneOptionsSignal]:
        """
        Find opportunities to sell puts at MOS price.

        "Getting Paid to Wait" strategy:
        - Find stocks trading ABOVE their MOS price
        - Sell puts at strike near MOS price
        - If assigned, you get the stock at your target
        - If not, you keep the premium

        Returns:
            List of RuleOneOptionsSignal for put selling opportunities
        """
        signals = []

        for symbol in self.universe:
            try:
                # Get valuation
                valuation = self._valuation_cache.get(symbol) or self.calculate_sticker_price(symbol)
                if not valuation:
                    continue

                # Check Big Five quality
                big_five = self._big_five_cache.get(symbol)
                if big_five and not big_five.passes_rule_one:
                    logger.debug(f"{symbol}: Fails Big Five test, skipping")
                    continue

                # Strategy: Sell puts when stock is ABOVE MOS price
                # We want to get PAID to wait for a better entry
                if valuation.current_price < valuation.mos_price:
                    # Already cheap enough to buy, don't sell puts
                    logger.info(f"{symbol}: Below MOS ${valuation.mos_price:.2f}, just BUY")
                    continue

                # Target strike at MOS price
                target_strike = valuation.mos_price

                # Get options chain
                expiry, premium = self._find_best_put_option(symbol, target_strike)
                if not expiry or premium <= 0:
                    continue

                # Calculate annualized return
                days_to_expiry = (datetime.strptime(expiry, "%Y-%m-%d") - datetime.now()).days
                if days_to_expiry <= 0:
                    continue

                # Annualized return = (premium / strike) * (365 / days)
                annualized_return = (premium / target_strike) * (365 / days_to_expiry)

                if annualized_return < self.MIN_ANNUALIZED_RETURN:
                    logger.debug(f"{symbol}: Annualized return {annualized_return:.1%} below minimum")
                    continue

                signal = RuleOneOptionsSignal(
                    symbol=symbol,
                    signal_type="sell_put",
                    strike=target_strike,
                    expiration=expiry,
                    premium=premium,
                    annualized_return=annualized_return,
                    sticker_price=valuation.sticker_price,
                    mos_price=valuation.mos_price,
                    current_price=valuation.current_price,
                    rationale=f"Sell put at MOS ${target_strike:.2f} to buy {symbol} at discount. "
                              f"If assigned, own at {valuation.margin_of_safety:.0%} below fair value.",
                    confidence=0.8 if big_five and big_five.passes_rule_one else 0.6,
                )
                signals.append(signal)

            except Exception as e:
                logger.warning(f"Error analyzing {symbol} for puts: {e}")

        # Sort by annualized return
        signals.sort(key=lambda x: x.annualized_return, reverse=True)
        return signals

    def find_call_opportunities(self) -> List[RuleOneOptionsSignal]:
        """
        Find opportunities to sell covered calls at Sticker Price.

        "Getting Paid to Sell" strategy:
        - Find stocks you own with >= 100 shares
        - Sell calls at strike near Sticker Price
        - If called away, sell at fair value + premium
        - If not, keep premium and shares

        Returns:
            List of RuleOneOptionsSignal for covered call opportunities
        """
        signals = []

        try:
            positions = self.trader.get_positions()
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return signals

        for pos in positions:
            try:
                symbol = pos.get("symbol")
                qty = float(pos.get("qty", 0))

                if qty < self.min_shares_for_calls:
                    continue

                if symbol not in self.universe:
                    # Only trade options on Rule #1 universe
                    continue

                # Get valuation
                valuation = self._valuation_cache.get(symbol) or self.calculate_sticker_price(symbol)
                if not valuation:
                    continue

                # Strategy: Sell calls at Sticker Price
                # If called away, we sell at fair value (happy outcome)
                target_strike = valuation.sticker_price

                # Get options chain
                expiry, premium = self._find_best_call_option(symbol, target_strike)
                if not expiry or premium <= 0:
                    continue

                # Calculate annualized return
                days_to_expiry = (datetime.strptime(expiry, "%Y-%m-%d") - datetime.now()).days
                if days_to_expiry <= 0:
                    continue

                annualized_return = (premium / valuation.current_price) * (365 / days_to_expiry)

                if annualized_return < self.MIN_ANNUALIZED_RETURN:
                    continue

                # Calculate how many contracts we can write
                num_contracts = int(qty // 100)

                signal = RuleOneOptionsSignal(
                    symbol=symbol,
                    signal_type="sell_call",
                    strike=target_strike,
                    expiration=expiry,
                    premium=premium * num_contracts * 100,  # Total premium for all contracts
                    annualized_return=annualized_return,
                    sticker_price=valuation.sticker_price,
                    mos_price=valuation.mos_price,
                    current_price=valuation.current_price,
                    rationale=f"Sell {num_contracts} covered call(s) at Sticker Price ${target_strike:.2f}. "
                              f"If called away, sell at fair value + ${premium:.2f} premium.",
                    confidence=0.85,
                )
                signals.append(signal)

            except Exception as e:
                logger.warning(f"Error analyzing {pos.get('symbol')} for calls: {e}")

        signals.sort(key=lambda x: x.annualized_return, reverse=True)
        return signals

    def _find_best_put_option(
        self, symbol: str, target_strike: float
    ) -> Tuple[Optional[str], float]:
        """
        Find the best put option near target strike.

        Args:
            symbol: Stock ticker
            target_strike: Desired strike price

        Returns:
            Tuple of (expiration_date, premium) or (None, 0) if not found
        """
        try:
            ticker = yf.Ticker(symbol)

            # Get options expiration dates
            expirations = ticker.options
            if not expirations:
                return None, 0

            # Find expiration in target range (25-50 days)
            today = datetime.now()
            target_expiry = None

            for exp in expirations:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                days_out = (exp_date - today).days

                if self.MIN_DAYS_TO_EXPIRY <= days_out <= self.MAX_DAYS_TO_EXPIRY:
                    target_expiry = exp
                    break

            if not target_expiry:
                # Take first available if none in range
                target_expiry = expirations[0] if expirations else None

            if not target_expiry:
                return None, 0

            # Get put options for that expiration
            options = ticker.option_chain(target_expiry)
            puts = options.puts

            if puts.empty:
                return None, 0

            # Find strike closest to target
            puts['strike_diff'] = abs(puts['strike'] - target_strike)
            best_put = puts.loc[puts['strike_diff'].idxmin()]

            premium = (best_put['bid'] + best_put['ask']) / 2

            return target_expiry, premium

        except Exception as e:
            logger.debug(f"Could not find put option for {symbol}: {e}")
            return None, 0

    def _find_best_call_option(
        self, symbol: str, target_strike: float
    ) -> Tuple[Optional[str], float]:
        """
        Find the best call option near target strike.

        Args:
            symbol: Stock ticker
            target_strike: Desired strike price

        Returns:
            Tuple of (expiration_date, premium) or (None, 0) if not found
        """
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options

            if not expirations:
                return None, 0

            # Find expiration in target range
            today = datetime.now()
            target_expiry = None

            for exp in expirations:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                days_out = (exp_date - today).days

                if self.MIN_DAYS_TO_EXPIRY <= days_out <= self.MAX_DAYS_TO_EXPIRY:
                    target_expiry = exp
                    break

            if not target_expiry:
                target_expiry = expirations[0] if expirations else None

            if not target_expiry:
                return None, 0

            # Get call options
            options = ticker.option_chain(target_expiry)
            calls = options.calls

            if calls.empty:
                return None, 0

            # Find strike closest to target
            calls['strike_diff'] = abs(calls['strike'] - target_strike)
            best_call = calls.loc[calls['strike_diff'].idxmin()]

            premium = (best_call['bid'] + best_call['ask']) / 2

            return target_expiry, premium

        except Exception as e:
            logger.debug(f"Could not find call option for {symbol}: {e}")
            return None, 0

    def analyze_universe(self) -> Dict[str, StickerPriceResult]:
        """
        Analyze all stocks in universe and return valuations.

        Returns:
            Dictionary of symbol -> StickerPriceResult
        """
        results = {}

        for symbol in self.universe:
            big_five = self.calculate_big_five(symbol)
            valuation = self.calculate_sticker_price(symbol)

            if valuation:
                results[symbol] = valuation

                logger.info(
                    f"{symbol}: Price=${valuation.current_price:.2f}, "
                    f"Sticker=${valuation.sticker_price:.2f}, "
                    f"MOS=${valuation.mos_price:.2f}, "
                    f"Growth={valuation.growth_rate:.1%}, "
                    f"Rec={valuation.recommendation}"
                )

        return results

    def generate_daily_signals(self) -> Dict[str, List[RuleOneOptionsSignal]]:
        """
        Generate all Rule #1 options signals for today.

        Returns:
            Dictionary with 'puts' and 'calls' signal lists
        """
        logger.info("Generating Rule #1 options signals...")

        # First analyze universe to populate valuations
        self.analyze_universe()

        put_signals = self.find_put_opportunities()
        call_signals = self.find_call_opportunities()

        logger.info(f"Found {len(put_signals)} put opportunities, {len(call_signals)} call opportunities")

        return {
            "puts": put_signals,
            "calls": call_signals,
            "timestamp": datetime.now().isoformat(),
        }

    def get_portfolio_analysis(self) -> Dict:
        """
        Get comprehensive Rule #1 analysis for current portfolio.

        Returns:
            Dictionary with valuations, signals, and recommendations
        """
        valuations = self.analyze_universe()
        signals = self.generate_daily_signals()

        # Find best opportunities
        best_puts = signals["puts"][:3] if signals["puts"] else []
        best_calls = signals["calls"][:3] if signals["calls"] else []

        # Find undervalued stocks (below MOS)
        undervalued = [
            v for v in valuations.values()
            if v.current_price <= v.mos_price
        ]

        # Find overvalued stocks (above Sticker)
        overvalued = [
            v for v in valuations.values()
            if v.current_price > v.sticker_price * 1.2
        ]

        return {
            "valuations": {s: v.__dict__ for s, v in valuations.items()},
            "put_opportunities": [s.__dict__ for s in best_puts],
            "call_opportunities": [s.__dict__ for s in best_calls],
            "undervalued_stocks": [v.symbol for v in undervalued],
            "overvalued_stocks": [v.symbol for v in overvalued],
            "universe_size": len(self.universe),
            "analyzed_count": len(valuations),
            "timestamp": datetime.now().isoformat(),
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    strategy = RuleOneOptionsStrategy(paper=True)
    analysis = strategy.get_portfolio_analysis()

    print("\n=== RULE #1 OPTIONS ANALYSIS ===")
    print(f"Analyzed: {analysis['analyzed_count']}/{analysis['universe_size']} stocks")

    print("\n--- Top Put Opportunities (Getting Paid to Wait) ---")
    for opp in analysis['put_opportunities']:
        print(f"  {opp['symbol']}: Sell put at ${opp['strike']:.2f}, "
              f"Yield: {opp['annualized_return']:.1%}")

    print("\n--- Top Call Opportunities (Getting Paid to Sell) ---")
    for opp in analysis['call_opportunities']:
        print(f"  {opp['symbol']}: Sell call at ${opp['strike']:.2f}, "
              f"Yield: {opp['annualized_return']:.1%}")

    print("\n--- Undervalued (Below MOS Price) ---")
    for sym in analysis['undervalued_stocks']:
        print(f"  {sym}: STRONG BUY")

    print("\n--- Overvalued (Above Sticker Price) ---")
    for sym in analysis['overvalued_stocks']:
        print(f"  {sym}: Consider selling")
