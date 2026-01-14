"""
Phil Town Rule #1 Pre-Trade Validator

Validates that trades comply with Phil Town's Rule #1 Investing principles
BEFORE execution. This gate ensures:

1. Big Five Compliance - All 5 metrics >= 10% growth
2. Sticker Price Validation - Current price <= MOS (50% of Sticker)
3. Wonderful Company Check - Stock is in approved universe

Integration Points:
- TradeGateway.evaluate() - CHECK 13
- OptionsExecutor.validate_order() - Pre-order check

Author: AI Trading System (CTO: Claude)
Date: January 13, 2026
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Approved wonderful companies (Rule #1 compliant or capital-appropriate)
# Per CLAUDE.md: Primary strategy is "CREDIT SPREADS on SPY/IWM ONLY"
# ETFs don't require Big Five analysis - they're index funds
RULE_ONE_UNIVERSE = {
    # PRIMARY: Index ETFs for credit spreads (Jan 14, 2026 - per CLAUDE.md)
    # These are EXEMPT from Big Five analysis as they're not individual companies
    "SPY": {"name": "S&P 500 ETF", "moat": "etf", "capital_tier": "any", "skip_big_five": True},
    "IWM": {"name": "Russell 2000 ETF", "moat": "etf", "capital_tier": "any", "skip_big_five": True},
    # Secondary credit spread targets (low share price, liquid options)
    "F": {"name": "Ford", "moat": "brand", "capital_tier": "small"},
    "SOFI": {"name": "SoFi Technologies", "moat": "switching", "capital_tier": "small"},
    "T": {"name": "AT&T", "moat": "toll", "capital_tier": "small"},
    # Secondary targets
    "PLTR": {"name": "Palantir", "moat": "switching", "capital_tier": "small"},
    "NIO": {"name": "NIO Inc", "moat": "brand", "capital_tier": "small"},
    "RIVN": {"name": "Rivian", "moat": "brand", "capital_tier": "small"},
    # Blue chips (for larger accounts)
    "AAPL": {"name": "Apple", "moat": "brand", "capital_tier": "large"},
    "MSFT": {"name": "Microsoft", "moat": "switching", "capital_tier": "large"},
    "GOOGL": {"name": "Google", "moat": "brand", "capital_tier": "large"},
    "AMZN": {"name": "Amazon", "moat": "price", "capital_tier": "large"},
}

# Big Five thresholds (Phil Town minimum requirements)
BIG_FIVE_MIN_GROWTH = 0.10  # 10% minimum for all metrics
BIG_FIVE_MIN_ROIC = 0.10  # 10% minimum ROIC
MARGIN_OF_SAFETY = 0.50  # 50% discount to Sticker Price
MAX_GROWTH_RATE = 0.15  # Cap growth projections at 15%


@dataclass
class BigFiveResult:
    """Result of Big Five metrics analysis."""

    roic: float | None = None
    sales_growth: float | None = None
    eps_growth: float | None = None
    equity_growth: float | None = None
    fcf_growth: float | None = None
    avg_growth: float = 0.0
    passes: bool = False
    failed_metrics: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Calculate pass/fail status."""
        self.failed_metrics = []

        # Check each metric
        if self.roic is not None and self.roic < BIG_FIVE_MIN_ROIC:
            self.failed_metrics.append(f"ROIC ({self.roic:.1%} < {BIG_FIVE_MIN_ROIC:.0%})")
        if self.sales_growth is not None and self.sales_growth < BIG_FIVE_MIN_GROWTH:
            self.failed_metrics.append(
                f"Sales Growth ({self.sales_growth:.1%} < {BIG_FIVE_MIN_GROWTH:.0%})"
            )
        if self.eps_growth is not None and self.eps_growth < BIG_FIVE_MIN_GROWTH:
            self.failed_metrics.append(
                f"EPS Growth ({self.eps_growth:.1%} < {BIG_FIVE_MIN_GROWTH:.0%})"
            )
        if self.equity_growth is not None and self.equity_growth < BIG_FIVE_MIN_GROWTH:
            self.failed_metrics.append(
                f"Equity Growth ({self.equity_growth:.1%} < {BIG_FIVE_MIN_GROWTH:.0%})"
            )
        if self.fcf_growth is not None and self.fcf_growth < BIG_FIVE_MIN_GROWTH:
            self.failed_metrics.append(
                f"FCF Growth ({self.fcf_growth:.1%} < {BIG_FIVE_MIN_GROWTH:.0%})"
            )

        # Calculate average of available metrics
        metrics = [
            m
            for m in [
                self.sales_growth,
                self.eps_growth,
                self.equity_growth,
                self.fcf_growth,
            ]
            if m is not None
        ]
        self.avg_growth = sum(metrics) / len(metrics) if metrics else 0.0

        # Pass requires ROIC >= 10% AND average growth >= 10%
        self.passes = (
            len(self.failed_metrics) == 0
            and self.roic is not None
            and self.roic >= BIG_FIVE_MIN_ROIC
            and self.avg_growth >= BIG_FIVE_MIN_GROWTH
        )


@dataclass
class StickerPriceResult:
    """Result of Sticker Price calculation."""

    current_price: float = 0.0
    sticker_price: float = 0.0
    mos_price: float = 0.0  # Margin of Safety price (50% of sticker)
    discount_pct: float = 0.0  # Current discount from sticker
    passes: bool = False
    reason: str = ""

    def __post_init__(self):
        """Calculate pass/fail and discount."""
        if self.sticker_price > 0:
            self.discount_pct = (self.sticker_price - self.current_price) / self.sticker_price
            self.passes = self.current_price <= self.mos_price

            if self.passes:
                self.reason = f"Below MOS ({self.discount_pct:.0%} discount)"
            elif self.current_price <= self.sticker_price:
                self.reason = f"Below Sticker but above MOS ({self.discount_pct:.0%} discount)"
            else:
                self.reason = f"Overvalued ({-self.discount_pct:.0%} premium)"


@dataclass
class RuleOneValidationResult:
    """Complete Rule #1 validation result."""

    symbol: str
    approved: bool
    timestamp: datetime = field(default_factory=datetime.now)

    # Component results
    in_universe: bool = False
    universe_info: dict[str, Any] = field(default_factory=dict)
    big_five: BigFiveResult | None = None
    sticker_price: StickerPriceResult | None = None

    # Summary
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 to 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "symbol": self.symbol,
            "approved": self.approved,
            "timestamp": self.timestamp.isoformat(),
            "in_universe": self.in_universe,
            "universe_info": self.universe_info,
            "big_five": {
                "roic": self.big_five.roic if self.big_five else None,
                "avg_growth": self.big_five.avg_growth if self.big_five else None,
                "passes": self.big_five.passes if self.big_five else False,
                "failed_metrics": self.big_five.failed_metrics if self.big_five else [],
            },
            "sticker_price": {
                "current": self.sticker_price.current_price if self.sticker_price else None,
                "sticker": self.sticker_price.sticker_price if self.sticker_price else None,
                "mos": self.sticker_price.mos_price if self.sticker_price else None,
                "discount_pct": self.sticker_price.discount_pct if self.sticker_price else None,
                "passes": self.sticker_price.passes if self.sticker_price else False,
            },
            "rejection_reasons": self.rejection_reasons,
            "warnings": self.warnings,
            "confidence": self.confidence,
        }


class RuleOneValidator:
    """
    Phil Town Rule #1 Pre-Trade Validator.

    Validates trades against Rule #1 principles:
    1. Universe check - Is this a wonderful company?
    2. Big Five check - Do all 5 metrics meet 10% threshold?
    3. Sticker Price check - Is current price <= MOS price?

    Usage:
        validator = RuleOneValidator()
        result = validator.validate(symbol="SOFI")
        if not result.approved:
            print(f"Trade blocked: {result.rejection_reasons}")
    """

    def __init__(self, strict_mode: bool = False, capital_tier: str = "small"):
        """
        Initialize validator.

        Args:
            strict_mode: If True, ALL checks must pass. If False, allow
                        trades on universe stocks with warnings.
            capital_tier: "small" (< $10K) or "large" (>= $10K)
        """
        self.strict_mode = strict_mode
        self.capital_tier = capital_tier
        self._cache: dict[str, tuple[RuleOneValidationResult, datetime]] = {}
        self._cache_ttl_seconds = 3600  # 1 hour cache

    def validate(self, symbol: str, current_price: float | None = None) -> RuleOneValidationResult:
        """
        Validate a symbol against Rule #1 principles.

        Args:
            symbol: Stock ticker symbol
            current_price: Optional current price (fetched if not provided)

        Returns:
            RuleOneValidationResult with approval status and details
        """
        logger.info(f"Rule #1 Validator: Checking {symbol}")

        result = RuleOneValidationResult(symbol=symbol, approved=False)

        # CHECK 1: Universe membership
        result.in_universe = self._check_universe(symbol, result)
        if not result.in_universe:
            result.rejection_reasons.append(f"{symbol} not in Rule #1 wonderful companies universe")
            logger.warning(f"Rule #1 REJECTED: {symbol} not in universe")
            return result

        # CHECK 1.5: ETF bypass (Jan 14, 2026 - per CLAUDE.md)
        # SPY/IWM are index ETFs - they don't require Big Five or Sticker Price analysis
        underlying = self._extract_underlying(symbol)
        universe_info = RULE_ONE_UNIVERSE.get(underlying, {})
        if universe_info.get("skip_big_five", False):
            logger.info(f"Rule #1: {symbol} is ETF - skipping Big Five/Sticker checks")
            result.approved = True
            result.confidence = 0.8  # High confidence for ETFs
            result.warnings.append(f"{underlying} is ETF - Big Five not applicable")
            return result

        # CHECK 2: Big Five metrics
        result.big_five = self._check_big_five(symbol)
        if not result.big_five.passes:
            if self.strict_mode:
                result.rejection_reasons.append(
                    f"Big Five failed: {', '.join(result.big_five.failed_metrics)}"
                )
                logger.warning(f"Rule #1 REJECTED: {symbol} Big Five failed")
            else:
                result.warnings.append(
                    f"Big Five partial: {', '.join(result.big_five.failed_metrics)}"
                )
                logger.info(f"Rule #1 WARNING: {symbol} Big Five partial pass")

        # CHECK 3: Sticker Price / Margin of Safety
        result.sticker_price = self._check_sticker_price(symbol, current_price)
        if not result.sticker_price.passes:
            if self.strict_mode:
                result.rejection_reasons.append(f"Above MOS price: {result.sticker_price.reason}")
                logger.warning(f"Rule #1 REJECTED: {symbol} above MOS")
            else:
                result.warnings.append(f"Price caution: {result.sticker_price.reason}")
                logger.info(f"Rule #1 WARNING: {symbol} {result.sticker_price.reason}")

        # FINAL DECISION
        if len(result.rejection_reasons) == 0:
            result.approved = True
            result.confidence = self._calculate_confidence(result)
            logger.info(f"Rule #1 APPROVED: {symbol} (confidence: {result.confidence:.0%})")
        else:
            logger.warning(f"Rule #1 REJECTED: {symbol} - {', '.join(result.rejection_reasons)}")

        return result

    def _check_universe(self, symbol: str, result: RuleOneValidationResult) -> bool:
        """Check if symbol is in the approved universe."""
        # Extract underlying from option symbol if needed
        underlying = self._extract_underlying(symbol)

        if underlying in RULE_ONE_UNIVERSE:
            info = RULE_ONE_UNIVERSE[underlying]
            result.universe_info = info
            result.in_universe = True

            # Check capital tier compatibility
            if info["capital_tier"] == "large" and self.capital_tier == "small":
                result.warnings.append(
                    f"{underlying} is a large-cap stock; may require more capital"
                )

            return True

        return False

    def _check_big_five(self, symbol: str) -> BigFiveResult:
        """
        Calculate Big Five metrics for symbol.

        Uses existing RuleOneOptionsStrategy if available,
        otherwise fetches from yfinance.
        """
        underlying = self._extract_underlying(symbol)

        try:
            # Try to use existing strategy implementation
            from src.strategies.rule_one_options import RuleOneOptionsStrategy

            strategy = RuleOneOptionsStrategy()
            metrics = strategy.calculate_big_five(underlying)

            if metrics:
                return BigFiveResult(
                    roic=metrics.roic,
                    sales_growth=metrics.sales_growth,
                    eps_growth=metrics.eps_growth,
                    equity_growth=metrics.equity_growth,
                    fcf_growth=metrics.fcf_growth,
                )
        except Exception as e:
            logger.debug(f"RuleOneOptionsStrategy not available: {e}")

        # Fallback: fetch directly from yfinance
        try:
            from src.utils import yfinance_wrapper as yf

            ticker = yf.Ticker(underlying)
            info = ticker.info

            return BigFiveResult(
                roic=info.get("returnOnCapital") or info.get("returnOnEquity"),
                sales_growth=info.get("revenueGrowth"),
                eps_growth=info.get("earningsGrowth"),
                equity_growth=info.get("earningsGrowth", 0) * 0.8
                if info.get("earningsGrowth")
                else None,
                fcf_growth=info.get("earningsGrowth", 0) * 0.9
                if info.get("earningsGrowth")
                else None,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch Big Five for {underlying}: {e}")
            return BigFiveResult()

    def _check_sticker_price(
        self, symbol: str, current_price: float | None = None
    ) -> StickerPriceResult:
        """
        Calculate Sticker Price and check MOS.

        Phil Town's formula:
        1. Future EPS = Current EPS * (1 + Growth Rate)^10
        2. Future PE = min(Growth Rate * 2, Historical High PE)
        3. Future Price = Future EPS * Future PE
        4. Sticker Price = Future Price / (1.15)^10
        5. MOS Price = Sticker Price * 0.50
        """
        underlying = self._extract_underlying(symbol)

        try:
            from src.strategies.rule_one_options import RuleOneOptionsStrategy

            strategy = RuleOneOptionsStrategy()
            result = strategy.calculate_sticker_price(underlying)

            if result:
                return StickerPriceResult(
                    current_price=result.current_price,
                    sticker_price=result.sticker_price,
                    mos_price=result.mos_price,
                )
        except Exception as e:
            logger.debug(f"RuleOneOptionsStrategy sticker calc failed: {e}")

        # Fallback calculation
        try:
            from src.utils import yfinance_wrapper as yf

            ticker = yf.Ticker(underlying)
            info = ticker.info

            price = current_price or info.get("currentPrice") or info.get("regularMarketPrice", 0)
            eps = info.get("trailingEps") or info.get("forwardEps", 1)
            growth = min(info.get("earningsGrowth", 0.10) or 0.10, MAX_GROWTH_RATE)

            # Phil Town formula
            future_eps = eps * ((1 + growth) ** 10)
            future_pe = min(growth * 100 * 2, 40)  # Cap PE at 40
            future_price = future_eps * future_pe
            sticker_price = future_price / (1.15**10)  # 15% MARR
            mos_price = sticker_price * MARGIN_OF_SAFETY

            return StickerPriceResult(
                current_price=price,
                sticker_price=sticker_price,
                mos_price=mos_price,
            )
        except Exception as e:
            logger.warning(f"Failed to calculate sticker price for {underlying}: {e}")
            return StickerPriceResult()

    def _calculate_confidence(self, result: RuleOneValidationResult) -> float:
        """Calculate confidence score based on validation results."""
        score = 0.0

        # Universe membership: 30%
        if result.in_universe:
            score += 0.30

        # Big Five: 35%
        if result.big_five and result.big_five.passes:
            score += 0.35
        elif result.big_five and result.big_five.avg_growth >= 0.08:
            score += 0.20  # Partial credit

        # Sticker Price: 35%
        if result.sticker_price and result.sticker_price.passes:
            score += 0.35
        elif result.sticker_price and result.sticker_price.discount_pct > 0:
            score += 0.15  # Partial credit for any discount

        return min(score, 1.0)

    def _extract_underlying(self, symbol: str) -> str:
        """Extract underlying ticker from option symbol."""
        # Option symbols like SOFI260206P00024000 -> SOFI
        if len(symbol) > 6 and any(c.isdigit() for c in symbol[4:]):
            # Find where digits start
            for i, c in enumerate(symbol):
                if c.isdigit():
                    return symbol[:i]
        return symbol

    def validate_for_credit_spread(
        self,
        symbol: str,
        spread_width: float = 5.0,
        max_collateral: float = 500.0,
    ) -> RuleOneValidationResult:
        """
        Validate specifically for credit spread trades.

        Additional checks per CLAUDE.md:
        - Spread width enforcement ($5 default)
        - Max collateral per spread ($500)
        - Primary targets: F, SOFI, T
        """
        result = self.validate(symbol)

        # Credit spread specific checks
        underlying = self._extract_underlying(symbol)
        primary_targets = {"F", "SOFI", "T"}

        if underlying not in primary_targets:
            result.warnings.append(
                f"{underlying} is not a primary credit spread target (F, SOFI, T)"
            )

        # Collateral check
        if max_collateral > 500:
            result.warnings.append(f"Collateral ${max_collateral} exceeds $500 per-spread limit")

        return result
