"""
IV-Aware Options Signal Generator

Integrates with RAG knowledge base (McMillan + TastyTrade) to generate
intelligent options trading signals based on implied volatility regimes.

Key Features:
- IV regime classification (very_low to very_high)
- Strategy recommendations based on IV + market outlook
- Actionable trade signals with specific strikes, DTE, position sizing
- RAG-powered decision logic using McMillan's and TastyTrade's rules

Author: Claude (CTO)
Created: 2025-12-10
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class IVRegime(Enum):
    """Implied Volatility Regimes based on IV Rank"""
    VERY_LOW = "very_low"      # IV Rank < 20
    LOW = "low"                # IV Rank 20-30
    NEUTRAL = "neutral"        # IV Rank 30-50
    HIGH = "high"              # IV Rank 50-75
    VERY_HIGH = "very_high"    # IV Rank > 75


class MarketOutlook(Enum):
    """Market directional bias"""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


@dataclass
class OptionsStrategy:
    """Options strategy recommendation"""
    name: str
    description: str
    max_profit: str
    max_loss: str
    breakeven: str
    probability_of_profit: str
    ideal_dte: tuple[int, int]
    delta_range: Optional[tuple[float, float]]
    management_rules: dict[str, str]
    rag_source: list[str]  # RAG chunk IDs supporting this recommendation


@dataclass
class TradeSignal:
    """Actionable options trade signal"""
    ticker: str
    strategy: str
    action: str  # "BUY" or "SELL"
    legs: list[dict[str, any]]  # List of option legs
    rationale: str
    iv_regime: str
    iv_rank: float
    iv_percentile: float
    expected_profit: float
    max_risk: float
    probability_profit: float
    position_size_pct: float  # % of portfolio to allocate
    entry_dte: tuple[int, int]
    exit_criteria: dict[str, str]
    rag_citations: list[str]  # RAG chunks used for this signal


class OptionsIVSignalGenerator:
    """
    Generate IV-aware options signals using RAG knowledge base.

    Integrates McMillan's Strategic Investment principles with
    TastyTrade's mechanical rules for optimal decision-making.
    """

    def __init__(self, rag_base_path: str = "/home/user/trading/rag_knowledge/chunks"):
        self.rag_base_path = Path(rag_base_path)
        self.mcmillan_chunks = self._load_rag_chunks("mcmillan_options_strategic_investment_2025.json")
        self.tastytrade_chunks = self._load_rag_chunks("tastytrade_options_education_2025.json")
        self.all_chunks = self.mcmillan_chunks.get("chunks", []) + self.tastytrade_chunks.get("chunks", [])

        # Cache strategy mappings
        self._strategy_cache = {}
        self._build_strategy_mappings()

    def _load_rag_chunks(self, filename: str) -> dict:
        """Load RAG chunks from JSON file"""
        filepath = self.rag_base_path / filename
        try:
            with open(filepath) as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: RAG file not found: {filepath}")
            return {"chunks": []}
        except json.JSONDecodeError as e:
            print(f"Error parsing RAG file {filepath}: {e}")
            return {"chunks": []}

    def _build_strategy_mappings(self):
        """Build internal mappings of strategies from RAG"""
        for chunk in self.all_chunks:
            strategy_type = chunk.get("strategy_type")
            if strategy_type and strategy_type not in self._strategy_cache:
                self._strategy_cache[strategy_type] = []
            if strategy_type:
                self._strategy_cache[strategy_type].append(chunk)

    def _search_rag(self, keywords: list[str], strategy_type: Optional[str] = None) -> list[dict]:
        """Search RAG chunks by keywords and/or strategy type"""
        results = []
        search_pool = self._strategy_cache.get(strategy_type, self.all_chunks) if strategy_type else self.all_chunks

        for chunk in search_pool:
            content = chunk.get("content", "").lower()
            topic = chunk.get("topic", "").lower()

            # Check if any keyword matches
            if any(keyword.lower() in content or keyword.lower() in topic for keyword in keywords):
                results.append(chunk)

        return results

    def get_iv_regime(self, iv_rank: float) -> str:
        """
        Classify IV regime based on IV Rank.

        Based on McMillan's and TastyTrade's research:
        - IV Rank < 20: Options are cheap (buy premium)
        - IV Rank 20-30: Low but not extreme
        - IV Rank 30-50: Neutral zone
        - IV Rank 50-75: High IV (sell premium)
        - IV Rank > 75: Very high IV (aggressive premium selling)

        Args:
            iv_rank: IV Rank value (0-100)

        Returns:
            IV regime classification string
        """
        if iv_rank < 20:
            return IVRegime.VERY_LOW.value
        elif iv_rank < 30:
            return IVRegime.LOW.value
        elif iv_rank < 50:
            return IVRegime.NEUTRAL.value
        elif iv_rank < 75:
            return IVRegime.HIGH.value
        else:
            return IVRegime.VERY_HIGH.value

    def get_strategy_recommendation(
        self,
        iv_rank: float,
        market_outlook: str,
        iv_percentile: Optional[float] = None
    ) -> OptionsStrategy:
        """
        Get optimal strategy recommendation based on IV and market outlook.

        Integrates:
        - McMillan's IV-based strategy selection (mcm_volatility_trading_001)
        - TastyTrade's mechanical entry rules (tt_iv_rank_001)
        - Greeks-based risk analysis

        Args:
            iv_rank: IV Rank (0-100)
            market_outlook: Directional bias (bullish, bearish, neutral, etc.)
            iv_percentile: Optional IV Percentile for additional confirmation

        Returns:
            OptionsStrategy with detailed recommendation
        """
        iv_regime = self.get_iv_regime(iv_rank)
        outlook = MarketOutlook(market_outlook) if isinstance(market_outlook, str) else market_outlook

        # Strategy selection matrix
        strategy = None
        rag_sources = []

        # VERY LOW IV (< 20): BUY PREMIUM
        if iv_regime == IVRegime.VERY_LOW.value:
            if outlook == MarketOutlook.STRONG_BULLISH:
                # Long calls or bull call spreads
                chunks = self._search_rag(["bull call spread", "bull spread"], "vertical_spread")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Bull Call Spread",
                    description="Buy lower strike call, sell higher strike call. Limited risk directional play.",
                    max_profit="(Spread Width - Debit) × 100",
                    max_loss="Debit Paid × 100",
                    breakeven="Lower Strike + Debit Paid",
                    probability_of_profit="~60-70% (ITM/ATM entry)",
                    ideal_dte=(45, 60),
                    delta_range=(0.60, 0.80),  # Buy ITM/ATM
                    management_rules={
                        "profit_target": "50% of max profit",
                        "stop_loss": "50% of debit (original investment)",
                        "time_exit": "Close by 21 DTE or if underlying stalls"
                    },
                    rag_source=rag_sources
                )

            elif outlook == MarketOutlook.BULLISH:
                chunks = self._search_rag(["bull call spread", "debit spread"], "vertical_spread")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Bull Call Spread (OTM)",
                    description="Buy ATM call, sell OTM call. Moderate cost, defined risk.",
                    max_profit="(Spread Width - Debit) × 100",
                    max_loss="Debit Paid × 100",
                    breakeven="Lower Strike + Debit",
                    probability_of_profit="~55-65%",
                    ideal_dte=(45, 60),
                    delta_range=(0.40, 0.60),
                    management_rules={
                        "profit_target": "50% max profit",
                        "stop_loss": "50% of debit",
                        "adjustment": "Roll out and up if needed"
                    },
                    rag_source=rag_sources
                )

            elif outlook == MarketOutlook.STRONG_BEARISH:
                chunks = self._search_rag(["bear put spread"], "vertical_spread")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Bear Put Spread",
                    description="Buy higher strike put, sell lower strike put. Bearish debit spread.",
                    max_profit="(Spread Width - Debit) × 100",
                    max_loss="Debit Paid × 100",
                    breakeven="Higher Strike - Debit",
                    probability_of_profit="~60-70% (ITM entry)",
                    ideal_dte=(45, 60),
                    delta_range=(-0.60, -0.80),  # Buy ITM puts
                    management_rules={
                        "profit_target": "50% max profit",
                        "stop_loss": "50% of debit",
                        "time_exit": "Close by 21 DTE"
                    },
                    rag_source=rag_sources
                )

            elif outlook == MarketOutlook.NEUTRAL:
                chunks = self._search_rag(["straddle", "strangle"], "straddle")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Long Straddle",
                    description="Buy ATM call + ATM put. Profit from large move in either direction.",
                    max_profit="Unlimited (either direction)",
                    max_loss="Total Premium Paid",
                    breakeven="Strike ± Total Premium",
                    probability_of_profit="~40-50% (needs volatility expansion)",
                    ideal_dte=(60, 90),  # Longer duration for vol expansion
                    delta_range=(0.0, 0.0),  # Delta neutral
                    management_rules={
                        "profit_target": "100-200% return on debit",
                        "stop_loss": "50% of debit if IV contracts",
                        "iv_exit": "Sell when IV Rank > 50%"
                    },
                    rag_source=rag_sources
                )

        # LOW IV (20-30): STILL FAVOR BUYING
        elif iv_regime == IVRegime.LOW.value:
            if outlook in [MarketOutlook.BULLISH, MarketOutlook.STRONG_BULLISH]:
                chunks = self._search_rag(["bull call spread"], "vertical_spread")
                rag_sources = [c["id"] for c in chunks[:1]]
                strategy = OptionsStrategy(
                    name="Bull Call Spread",
                    description="Buy ATM call, sell OTM call. Low IV reduces cost.",
                    max_profit="(Spread Width - Debit) × 100",
                    max_loss="Debit × 100",
                    breakeven="Lower Strike + Debit",
                    probability_of_profit="~55-65%",
                    ideal_dte=(45, 60),
                    delta_range=(0.50, 0.70),
                    management_rules={
                        "profit_target": "50% max profit",
                        "stop_loss": "50% debit",
                        "roll": "If underlying moves against, consider rolling"
                    },
                    rag_source=rag_sources
                )
            else:
                # Neutral/bearish in low IV - wait or use calendars
                chunks = self._search_rag(["calendar spread"], "calendar")
                rag_sources = [c["id"] for c in chunks[:1]]
                strategy = OptionsStrategy(
                    name="Calendar Spread",
                    description="Sell front-month, buy back-month (same strike). Profit from time decay differential.",
                    max_profit="Complex - max at strike at front expiration",
                    max_loss="Net Debit Paid",
                    breakeven="Varies based on IV changes",
                    probability_of_profit="~60% (if underlying stays near strike)",
                    ideal_dte=(30, 90),  # Front/back month combo
                    delta_range=(0.40, 0.60),  # ATM strike
                    management_rules={
                        "profit_target": "25-40% return on debit",
                        "stop_loss": "50% of debit",
                        "iv_benefit": "Benefits from IV increase (long vega)"
                    },
                    rag_source=rag_sources
                )

        # NEUTRAL IV (30-50): NEUTRAL STRATEGIES
        elif iv_regime == IVRegime.NEUTRAL.value:
            if outlook == MarketOutlook.NEUTRAL:
                chunks = self._search_rag(["iron condor"], "iron_condor")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Iron Condor",
                    description="Sell OTM put spread + OTM call spread. Profit from range-bound movement.",
                    max_profit="Net Credit Received",
                    max_loss="Width of Wider Spread - Credit",
                    breakeven="Short strikes ± credit",
                    probability_of_profit="~65-75% (wide range)",
                    ideal_dte=(30, 45),
                    delta_range=(0.16, 0.30),  # ~70-84% P.OTM
                    management_rules={
                        "profit_target": "50% of max profit (TastyTrade research)",
                        "exit_dte": "Close by 21 DTE (avoid gamma spike)",
                        "adjustment": "Roll tested side if breached"
                    },
                    rag_source=rag_sources
                )
            elif outlook == MarketOutlook.BULLISH:
                chunks = self._search_rag(["bull put spread", "credit spread"], "credit_spread")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Bull Put Spread",
                    description="Sell OTM put, buy further OTM put. Credit spread with bullish bias.",
                    max_profit="Net Credit",
                    max_loss="(Spread Width - Credit) × 100",
                    breakeven="Short Strike - Credit",
                    probability_of_profit="~70-80% (based on short delta)",
                    ideal_dte=(30, 45),
                    delta_range=(0.16, 0.30),  # Short put delta
                    management_rules={
                        "profit_target": "50% credit",
                        "max_loss": "2× credit (McMillan rule)",
                        "roll": "If tested, roll out and down for credit"
                    },
                    rag_source=rag_sources
                )
            elif outlook == MarketOutlook.BEARISH:
                chunks = self._search_rag(["bear call spread", "credit spread"], "credit_spread")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Bear Call Spread",
                    description="Sell OTM call, buy further OTM call. Credit spread with bearish bias.",
                    max_profit="Net Credit",
                    max_loss="(Spread Width - Credit) × 100",
                    breakeven="Short Strike + Credit",
                    probability_of_profit="~70-80%",
                    ideal_dte=(30, 45),
                    delta_range=(0.16, 0.30),
                    management_rules={
                        "profit_target": "50% credit",
                        "max_loss": "2× credit",
                        "roll": "If tested, roll out and up for credit"
                    },
                    rag_source=rag_sources
                )
            else:
                # Slight directional bias - calendar or butterfly
                chunks = self._search_rag(["butterfly"], "butterfly")
                rag_sources = [c["id"] for c in chunks[:1]]
                strategy = OptionsStrategy(
                    name="Butterfly Spread",
                    description="Buy 1 lower call, sell 2 middle calls, buy 1 upper call. Very low cost, specific target.",
                    max_profit="(Middle Strike - Lower Strike) - Net Debit",
                    max_loss="Net Debit",
                    breakeven="Lower/Upper ± Debit",
                    probability_of_profit="~40-50% (narrow profit zone)",
                    ideal_dte=(21, 45),
                    delta_range=(0.40, 0.60),
                    management_rules={
                        "profit_target": "50-75% max profit",
                        "stop_loss": "50% debit",
                        "use_case": "Pinning expectations, expiration plays"
                    },
                    rag_source=rag_sources
                )

        # HIGH IV (50-75): SELL PREMIUM
        elif iv_regime == IVRegime.HIGH.value:
            if outlook == MarketOutlook.NEUTRAL:
                chunks = self._search_rag(["iron condor", "short strangle"], "iron_condor")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Iron Condor (High IV)",
                    description="Premium collection strategy. Sell wide OTM spreads in high IV.",
                    max_profit="Net Credit",
                    max_loss="Width - Credit",
                    breakeven="Short strikes ± credit",
                    probability_of_profit="~70-80%",
                    ideal_dte=(30, 45),
                    delta_range=(0.16, 0.25),  # ~75-84% P.OTM
                    management_rules={
                        "profit_target": "50% credit (critical in high IV)",
                        "exit_dte": "21 DTE maximum",
                        "iv_benefit": "High IV = high credit, expect contraction"
                    },
                    rag_source=rag_sources
                )
            elif outlook == MarketOutlook.BULLISH:
                chunks = self._search_rag(["cash secured put", "naked put"], "cash_secured_put")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Cash-Secured Put (Wheel Entry)",
                    description="Sell OTM put to collect premium and potentially own stock at discount.",
                    max_profit="Premium Collected",
                    max_loss="Strike × 100 - Premium (if stock goes to $0)",
                    breakeven="Strike - Premium",
                    probability_of_profit="~75-85% (OTM delta dependent)",
                    ideal_dte=(30, 45),
                    delta_range=(0.20, 0.35),
                    management_rules={
                        "profit_target": "50% credit or hold to expiration",
                        "assignment": "If assigned, wheel into covered call",
                        "stock_selection": "Only on stocks you want to own (McMillan rule)"
                    },
                    rag_source=rag_sources
                )
            elif outlook == MarketOutlook.BEARISH:
                chunks = self._search_rag(["bear call spread"], "credit_spread")
                rag_sources = [c["id"] for c in chunks[:1]]
                strategy = OptionsStrategy(
                    name="Bear Call Spread (High IV)",
                    description="Sell call spreads in high IV to capture premium and IV crush.",
                    max_profit="Net Credit",
                    max_loss="(Width - Credit) × 100",
                    breakeven="Short Strike + Credit",
                    probability_of_profit="~75-85%",
                    ideal_dte=(30, 45),
                    delta_range=(0.16, 0.25),
                    management_rules={
                        "profit_target": "50% credit",
                        "max_loss": "2× credit (McMillan)",
                        "roll": "Roll up and out for credit if tested"
                    },
                    rag_source=rag_sources
                )
            else:
                # Covered calls if holding stock
                chunks = self._search_rag(["covered call"], "covered_call")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Covered Call (High IV)",
                    description="Own 100 shares, sell OTM call. High IV = high premium.",
                    max_profit="(Strike - Stock Price) + Premium",
                    max_loss="Stock Price - Premium (if stock drops to $0)",
                    breakeven="Stock Price - Premium",
                    probability_of_profit="~65-75% (delta dependent)",
                    ideal_dte=(30, 45),
                    delta_range=(0.25, 0.35),  # ~65-75% P.OTM
                    management_rules={
                        "profit_target": "50% of premium or let assign",
                        "adjustment": "Roll up and out if called away early",
                        "stock_holding": "Must own or be willing to own stock"
                    },
                    rag_source=rag_sources
                )

        # VERY HIGH IV (> 75): AGGRESSIVE PREMIUM SELLING
        elif iv_regime == IVRegime.VERY_HIGH.value:
            if outlook == MarketOutlook.NEUTRAL:
                chunks = self._search_rag(["short strangle", "iron condor"], "strangle")
                rag_sources = [c["id"] for c in chunks[:2]]
                strategy = OptionsStrategy(
                    name="Short Strangle (Very High IV)",
                    description="Sell OTM put + OTM call. Collect massive premium, defined risk via stops.",
                    max_profit="Total Premium",
                    max_loss="Unlimited (but manage with stops)",
                    breakeven="Short strikes ± total premium",
                    probability_of_profit="~70-85% (wide breakevens)",
                    ideal_dte=(30, 45),
                    delta_range=(0.10, 0.20),  # Very wide strikes
                    management_rules={
                        "profit_target": "50% credit (exit fast in extreme IV)",
                        "stop_loss": "2× credit per side (McMillan rule)",
                        "iv_watch": "Exit if IV continues rising (trend following)"
                    },
                    rag_source=rag_sources
                )
            else:
                # Credit spreads in very high IV (defined risk preferred)
                chunks = self._search_rag(["credit spread"], "credit_spread")
                rag_sources = [c["id"] for c in chunks[:2]]
                direction = "Put" if outlook in [MarketOutlook.BULLISH, MarketOutlook.STRONG_BULLISH] else "Call"
                strategy = OptionsStrategy(
                    name=f"{'Bull' if direction == 'Put' else 'Bear'} {direction} Spread (Extreme IV)",
                    description=f"Sell {direction.lower()} spreads in extreme IV. Defined risk, high premium.",
                    max_profit="Net Credit",
                    max_loss="(Width - Credit) × 100",
                    breakeven="Short strike ± credit",
                    probability_of_profit="~75-90%",
                    ideal_dte=(30, 45),
                    delta_range=(0.10, 0.20),  # Very OTM
                    management_rules={
                        "profit_target": "50% credit (take profits quickly)",
                        "max_loss": "2× credit",
                        "spread_width": "Wider spreads for better risk/reward"
                    },
                    rag_source=rag_sources
                )

        # Fallback if no strategy matched
        if strategy is None:
            strategy = OptionsStrategy(
                name="WAIT - No Clear Edge",
                description=f"IV regime {iv_regime} with {outlook.value} outlook has no clear mechanical advantage. Wait for better setup.",
                max_profit="N/A",
                max_loss="N/A",
                breakeven="N/A",
                probability_of_profit="N/A",
                ideal_dte=(0, 0),
                delta_range=None,
                management_rules={"recommendation": "Wait for IV Rank < 20 or > 50 for clearer edge"},
                rag_source=[]
            )

        return strategy

    def generate_trade_signal(
        self,
        ticker: str,
        iv_rank: float,
        iv_percentile: float,
        stock_price: float,
        market_outlook: str = "neutral",
        portfolio_value: float = 10000.0,
        options_chain: Optional[dict] = None
    ) -> TradeSignal:
        """
        Generate actionable options trade signal with specific strikes and sizing.

        Args:
            ticker: Stock symbol
            iv_rank: Current IV Rank (0-100)
            iv_percentile: Current IV Percentile (0-100)
            stock_price: Current stock price
            market_outlook: Directional bias
            portfolio_value: Total portfolio value for position sizing
            options_chain: Optional dict with available strikes and premiums

        Returns:
            TradeSignal with complete trade details
        """
        # Get strategy recommendation
        strategy = self.get_strategy_recommendation(iv_rank, market_outlook, iv_percentile)
        iv_regime = self.get_iv_regime(iv_rank)

        # Build trade signal based on strategy
        legs = []
        action = "BUY" if "Buy" in strategy.name or "Long" in strategy.name else "SELL"

        # Position sizing based on TastyTrade rules (1-5% risk per trade)
        max_risk_pct = 0.03  # 3% of portfolio

        # Construct legs based on strategy type
        if "Bull Call Spread" in strategy.name:
            # Example: Buy ATM call, sell OTM call
            lower_strike = round(stock_price * 0.99 / 5) * 5  # Round to nearest $5
            upper_strike = lower_strike + 10  # $10 wide spread

            # Estimate premiums (would use real options_chain if provided)
            buy_premium = stock_price * 0.05  # ~5% for ATM
            sell_premium = stock_price * 0.02  # ~2% for OTM
            net_debit = buy_premium - sell_premium

            legs = [
                {
                    "action": "BUY",
                    "option_type": "CALL",
                    "strike": lower_strike,
                    "quantity": 1,
                    "premium": buy_premium,
                    "dte": 45
                },
                {
                    "action": "SELL",
                    "option_type": "CALL",
                    "strike": upper_strike,
                    "quantity": 1,
                    "premium": sell_premium,
                    "dte": 45
                }
            ]

            max_risk = net_debit * 100
            expected_profit = (upper_strike - lower_strike - net_debit) * 100
            probability_profit = 0.60  # Approximate based on delta

        elif "Bear Put Spread" in strategy.name:
            upper_strike = round(stock_price * 1.01 / 5) * 5
            lower_strike = upper_strike - 10

            buy_premium = stock_price * 0.04
            sell_premium = stock_price * 0.015
            net_debit = buy_premium - sell_premium

            legs = [
                {
                    "action": "BUY",
                    "option_type": "PUT",
                    "strike": upper_strike,
                    "quantity": 1,
                    "premium": buy_premium,
                    "dte": 45
                },
                {
                    "action": "SELL",
                    "option_type": "PUT",
                    "strike": lower_strike,
                    "quantity": 1,
                    "premium": sell_premium,
                    "dte": 45
                }
            ]

            max_risk = net_debit * 100
            expected_profit = (upper_strike - lower_strike - net_debit) * 100
            probability_profit = 0.60

        elif "Bull Put Spread" in strategy.name or "Bear Call Spread" in strategy.name:
            is_put = "Put" in strategy.name
            option_type = "PUT" if is_put else "CALL"

            # Credit spreads: sell closer to price, buy further
            if is_put:
                short_strike = round(stock_price * 0.95 / 5) * 5  # 5% OTM
                long_strike = short_strike - 5  # $5 wide
                short_premium = stock_price * 0.025
                long_premium = stock_price * 0.01
            else:
                short_strike = round(stock_price * 1.05 / 5) * 5
                long_strike = short_strike + 5
                short_premium = stock_price * 0.025
                long_premium = stock_price * 0.01

            net_credit = short_premium - long_premium

            legs = [
                {
                    "action": "SELL",
                    "option_type": option_type,
                    "strike": short_strike,
                    "quantity": 1,
                    "premium": short_premium,
                    "dte": 40
                },
                {
                    "action": "BUY",
                    "option_type": option_type,
                    "strike": long_strike,
                    "quantity": 1,
                    "premium": long_premium,
                    "dte": 40
                }
            ]

            max_risk = (abs(short_strike - long_strike) - net_credit) * 100
            expected_profit = net_credit * 100
            probability_profit = 0.75  # ~75% P.OTM for delta 0.25

        elif "Iron Condor" in strategy.name:
            # Sell OTM put spread + call spread
            put_short = round(stock_price * 0.92 / 5) * 5  # 8% OTM
            put_long = put_short - 5
            call_short = round(stock_price * 1.08 / 5) * 5  # 8% OTM
            call_long = call_short + 5

            put_short_prem = stock_price * 0.02
            put_long_prem = stock_price * 0.008
            call_short_prem = stock_price * 0.02
            call_long_prem = stock_price * 0.008

            net_credit = (put_short_prem - put_long_prem) + (call_short_prem - call_long_prem)

            legs = [
                {"action": "SELL", "option_type": "PUT", "strike": put_short, "quantity": 1, "premium": put_short_prem, "dte": 40},
                {"action": "BUY", "option_type": "PUT", "strike": put_long, "quantity": 1, "premium": put_long_prem, "dte": 40},
                {"action": "SELL", "option_type": "CALL", "strike": call_short, "quantity": 1, "premium": call_short_prem, "dte": 40},
                {"action": "BUY", "option_type": "CALL", "strike": call_long, "quantity": 1, "premium": call_long_prem, "dte": 40}
            ]

            max_risk = (5 - net_credit) * 100  # $5 wide spreads
            expected_profit = net_credit * 100
            probability_profit = 0.70

        elif "Cash-Secured Put" in strategy.name:
            strike = round(stock_price * 0.95 / 5) * 5  # 5% OTM
            premium = stock_price * 0.03

            legs = [
                {
                    "action": "SELL",
                    "option_type": "PUT",
                    "strike": strike,
                    "quantity": 1,
                    "premium": premium,
                    "dte": 40
                }
            ]

            max_risk = (strike * 100) - (premium * 100)  # If stock goes to $0
            expected_profit = premium * 100
            probability_profit = 0.80  # High P.OTM

        elif "Covered Call" in strategy.name:
            strike = round(stock_price * 1.05 / 5) * 5  # 5% OTM
            premium = stock_price * 0.025

            legs = [
                {
                    "action": "OWN",
                    "option_type": "STOCK",
                    "strike": stock_price,
                    "quantity": 100,
                    "premium": 0,
                    "dte": 0
                },
                {
                    "action": "SELL",
                    "option_type": "CALL",
                    "strike": strike,
                    "quantity": 1,
                    "premium": premium,
                    "dte": 40
                }
            ]

            max_risk = stock_price * 100 - premium * 100  # Downside on stock
            expected_profit = (strike - stock_price + premium) * 100
            probability_profit = 0.70

        elif "Straddle" in strategy.name:
            strike = round(stock_price / 5) * 5  # ATM
            call_premium = stock_price * 0.04
            put_premium = stock_price * 0.04
            total_premium = call_premium + put_premium

            legs = [
                {"action": "BUY", "option_type": "CALL", "strike": strike, "quantity": 1, "premium": call_premium, "dte": 60},
                {"action": "BUY", "option_type": "PUT", "strike": strike, "quantity": 1, "premium": put_premium, "dte": 60}
            ]

            max_risk = total_premium * 100
            expected_profit = stock_price * 0.20 * 100  # If 20% move
            probability_profit = 0.45

        else:
            # Default/fallback - no trade
            legs = []
            max_risk = 0
            expected_profit = 0
            probability_profit = 0

        # Position sizing
        if max_risk > 0:
            position_size_pct = min(max_risk_pct, max_risk / portfolio_value)
        else:
            position_size_pct = 0

        # Build rationale with RAG citations
        rationale_parts = [
            f"IV Regime: {iv_regime.upper()} (IV Rank: {iv_rank:.1f}%, IV Percentile: {iv_percentile:.1f}%)",
            f"Strategy: {strategy.name}",
            f"Market Outlook: {market_outlook}",
            f"Key Rule: {strategy.description}",
        ]

        # Add McMillan/TastyTrade specific rules
        if iv_rank < 20:
            rationale_parts.append("McMillan Rule: IV Rank < 20 → BUY premium (options cheap)")
        elif iv_rank > 50:
            rationale_parts.append("McMillan/TastyTrade Rule: IV Rank > 50 → SELL premium (options expensive)")

        rationale_parts.append(f"Position Sizing: {position_size_pct*100:.1f}% of portfolio (TastyTrade max 3-5% per trade)")

        rationale = " | ".join(rationale_parts)

        # Exit criteria
        exit_criteria = strategy.management_rules.copy()
        exit_criteria["dte_exit"] = "Close by 21 DTE to avoid gamma spike"

        return TradeSignal(
            ticker=ticker,
            strategy=strategy.name,
            action=action,
            legs=legs,
            rationale=rationale,
            iv_regime=iv_regime,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            expected_profit=expected_profit,
            max_risk=max_risk,
            probability_profit=probability_profit,
            position_size_pct=position_size_pct,
            entry_dte=strategy.ideal_dte,
            exit_criteria=exit_criteria,
            rag_citations=strategy.rag_source
        )

    def format_signal_report(self, signal: TradeSignal) -> str:
        """Format trade signal as human-readable report"""
        report = f"""
========================================
OPTIONS TRADE SIGNAL: {signal.ticker}
========================================

STRATEGY: {signal.strategy}
ACTION: {signal.action}

VOLATILITY ANALYSIS:
- IV Regime: {signal.iv_regime.upper()}
- IV Rank: {signal.iv_rank:.1f}%
- IV Percentile: {signal.iv_percentile:.1f}%

TRADE STRUCTURE:
"""
        for i, leg in enumerate(signal.legs, 1):
            report += f"  Leg {i}: {leg['action']} {leg['quantity']} {leg['option_type']} @ ${leg['strike']:.2f}"
            if leg.get('premium', 0) > 0:
                report += f" for ${leg['premium']:.2f}"
            if leg.get('dte', 0) > 0:
                report += f" ({leg['dte']} DTE)"
            report += "\n"

        report += f"""
RISK/REWARD:
- Max Profit: ${signal.expected_profit:.2f}
- Max Risk: ${signal.max_risk:.2f}
- Risk/Reward Ratio: {signal.expected_profit/signal.max_risk if signal.max_risk > 0 else 0:.2f}
- Probability of Profit: {signal.probability_profit*100:.1f}%

POSITION SIZING:
- Allocate: {signal.position_size_pct*100:.1f}% of portfolio

MANAGEMENT RULES:
"""
        for rule, value in signal.exit_criteria.items():
            report += f"- {rule.replace('_', ' ').title()}: {value}\n"

        report += f"""
RATIONALE:
{signal.rationale}

RAG KNOWLEDGE SOURCES:
"""
        for citation_id in signal.rag_citations[:5]:  # Show top 5
            # Find the chunk
            chunk = next((c for c in self.all_chunks if c.get("id") == citation_id), None)
            if chunk:
                report += f"- [{citation_id}] {chunk.get('topic', 'N/A')}\n"

        report += "========================================\n"

        return report


# Example usage
if __name__ == "__main__":
    # Initialize generator
    generator = OptionsIVSignalGenerator()

    # Example 1: High IV, neutral outlook → Iron Condor
    print("EXAMPLE 1: High IV + Neutral Outlook")
    print("=" * 60)
    signal1 = generator.generate_trade_signal(
        ticker="SPY",
        iv_rank=65.0,
        iv_percentile=70.0,
        stock_price=450.0,
        market_outlook="neutral",
        portfolio_value=50000.0
    )
    print(generator.format_signal_report(signal1))

    # Example 2: Low IV, bullish outlook → Bull Call Spread
    print("\nEXAMPLE 2: Low IV + Bullish Outlook")
    print("=" * 60)
    signal2 = generator.generate_trade_signal(
        ticker="AAPL",
        iv_rank=18.0,
        iv_percentile=15.0,
        stock_price=180.0,
        market_outlook="bullish",
        portfolio_value=50000.0
    )
    print(generator.format_signal_report(signal2))

    # Example 3: Very high IV, neutral → Short Strangle
    print("\nEXAMPLE 3: Very High IV + Neutral Outlook")
    print("=" * 60)
    signal3 = generator.generate_trade_signal(
        ticker="TSLA",
        iv_rank=82.0,
        iv_percentile=88.0,
        stock_price=250.0,
        market_outlook="neutral",
        portfolio_value=50000.0
    )
    print(generator.format_signal_report(signal3))

    # Example 4: Test IV regime classification
    print("\nIV REGIME CLASSIFICATION TEST")
    print("=" * 60)
    test_values = [10, 25, 35, 60, 85]
    for iv_rank in test_values:
        regime = generator.get_iv_regime(iv_rank)
        print(f"IV Rank {iv_rank}% → {regime.upper()}")
