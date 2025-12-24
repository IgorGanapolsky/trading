"""
Earnings Calendar - Avoid Holding Options Through Earnings

Critical for options traders: Never hold short options through earnings!

Why Earnings Are Dangerous:
1. IV Crush: Implied volatility drops 20-50% immediately after earnings
2. Gap Risk: Stock can gap up/down 10-20% overnight
3. Unpredictable: Even good earnings can tank stock (and vice versa)
4. Binary Event: All your analysis becomes worthless vs a coin flip

Best Practices (McMillan):
- Close short options 3-5 days BEFORE earnings
- Never open new positions within 2 weeks of earnings
- If holding through earnings, use defined-risk (spreads, not naked)
- IV is typically highest 1-2 weeks before earnings

Reference: McMillan "Options as Strategic Investment" Ch. 22
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EarningsEvent:
    """Represents an earnings announcement."""

    symbol: str
    earnings_date: datetime
    time_of_day: (
        str  # "BMO" (before market open), "AMC" (after market close), "TAS" (time after session)
    )
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None
    source: str = "unknown"

    @property
    def days_until(self) -> int:
        """Days until earnings."""
        return (self.earnings_date.date() - datetime.now().date()).days

    @property
    def is_upcoming(self) -> bool:
        """True if earnings haven't happened yet."""
        return self.days_until > 0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "earnings_date": self.earnings_date.isoformat(),
            "time_of_day": self.time_of_day,
            "days_until": self.days_until,
            "eps_estimate": self.eps_estimate,
            "source": self.source,
        }


@dataclass
class EarningsRisk:
    """Risk assessment for holding options through earnings."""

    symbol: str
    earnings_date: datetime | None
    days_until_earnings: int | None

    # Risk levels
    risk_level: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW", "SAFE"
    risk_score: int  # 0-100

    # Recommendations
    should_close_position: bool = False
    should_avoid_new_position: bool = False
    max_dte_allowed: int = 0  # Max days to expiration if opening new position

    rationale: str = ""


class EarningsCalendar:
    """
    Earnings Calendar for options risk management.

    Provides:
    - Upcoming earnings dates for any symbol
    - Risk assessment for holding options
    - Recommendations for closing/avoiding positions
    """

    # Risk thresholds (days before earnings)
    CRITICAL_ZONE = 3  # Close ALL short options
    HIGH_RISK_ZONE = 7  # Consider closing
    MEDIUM_RISK_ZONE = 14  # Avoid new positions
    LOW_RISK_ZONE = 21  # Trade with caution

    # Cache settings
    CACHE_FILE = Path("data/earnings_cache.json")
    CACHE_DURATION_HOURS = 24

    def __init__(self):
        """Initialize Earnings Calendar."""
        self._cache: dict[str, EarningsEvent] = {}
        self._cache_timestamp: datetime | None = None
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached earnings data."""
        try:
            if self.CACHE_FILE.exists():
                with open(self.CACHE_FILE) as f:
                    data = json.load(f)
                    self._cache_timestamp = datetime.fromisoformat(data.get("timestamp", ""))
                    for symbol, event_data in data.get("events", {}).items():
                        self._cache[symbol] = EarningsEvent(
                            symbol=symbol,
                            earnings_date=datetime.fromisoformat(event_data["earnings_date"]),
                            time_of_day=event_data.get("time_of_day", "TAS"),
                            eps_estimate=event_data.get("eps_estimate"),
                            source=event_data.get("source", "cache"),
                        )
        except Exception as e:
            logger.debug(f"Could not load earnings cache: {e}")

    def _save_cache(self) -> None:
        """Save earnings cache."""
        try:
            self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "timestamp": datetime.now().isoformat(),
                "events": {s: e.to_dict() for s, e in self._cache.items()},
            }
            with open(self.CACHE_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save earnings cache: {e}")

    def _is_cache_valid(self, symbol: str) -> bool:
        """Check if cached data is still valid."""
        if symbol not in self._cache:
            return False
        if self._cache_timestamp is None:
            return False
        age = datetime.now() - self._cache_timestamp
        return age < timedelta(hours=self.CACHE_DURATION_HOURS)

    def get_next_earnings(self, symbol: str) -> EarningsEvent | None:
        """
        Get the next earnings date for a symbol.

        Uses multiple data sources:
        1. Cache (if fresh)
        2. yfinance
        3. Other APIs if available

        Args:
            symbol: Stock ticker

        Returns:
            EarningsEvent if found
        """
        # Check cache first
        if self._is_cache_valid(symbol):
            cached = self._cache.get(symbol)
            if cached and cached.is_upcoming:
                return cached

        # Try yfinance
        try:
            from src.utils import yfinance_wrapper as yf

            ticker = yf.Ticker(symbol)

            # Try calendar (earnings info)
            try:
                calendar = ticker.calendar
                if calendar is not None:
                    # Different yfinance versions return different formats
                    if isinstance(calendar, dict):
                        earnings_date = calendar.get("Earnings Date")
                        if earnings_date:
                            if isinstance(earnings_date, list) and len(earnings_date) > 0:
                                earnings_dt = earnings_date[0]
                            else:
                                earnings_dt = earnings_date

                            # Convert to datetime if needed
                            if hasattr(earnings_dt, "to_pydatetime"):
                                earnings_dt = earnings_dt.to_pydatetime()
                            elif isinstance(earnings_dt, str):
                                earnings_dt = datetime.fromisoformat(earnings_dt)

                            if isinstance(earnings_dt, datetime):
                                event = EarningsEvent(
                                    symbol=symbol,
                                    earnings_date=earnings_dt,
                                    time_of_day="TAS",  # yfinance doesn't always provide this
                                    source="yfinance_calendar",
                                )
                                self._cache[symbol] = event
                                self._save_cache()
                                return event
            except Exception as e:
                logger.debug(f"Could not get calendar for {symbol}: {e}")

            # Try earnings_dates property
            try:
                earnings_dates = ticker.earnings_dates
                if earnings_dates is not None and not earnings_dates.empty:
                    # Get next future date
                    now = datetime.now()
                    future_dates = [d for d in earnings_dates.index if d.to_pydatetime() > now]
                    if future_dates:
                        next_date = min(future_dates).to_pydatetime()
                        event = EarningsEvent(
                            symbol=symbol,
                            earnings_date=next_date,
                            time_of_day="TAS",
                            source="yfinance_earnings_dates",
                        )
                        self._cache[symbol] = event
                        self._save_cache()
                        return event
            except Exception as e:
                logger.debug(f"Could not get earnings_dates for {symbol}: {e}")

        except ImportError:
            logger.warning("yfinance not available for earnings data")
        except Exception as e:
            logger.warning(f"Failed to get earnings for {symbol}: {e}")

        return None

    def assess_earnings_risk(
        self,
        symbol: str,
        position_expiration: str | None = None,
    ) -> EarningsRisk:
        """
        Assess earnings risk for a position or potential trade.

        Args:
            symbol: Stock ticker
            position_expiration: Option expiration date (YYYY-MM-DD) if checking existing position

        Returns:
            EarningsRisk assessment
        """
        earnings = self.get_next_earnings(symbol)

        if not earnings:
            return EarningsRisk(
                symbol=symbol,
                earnings_date=None,
                days_until_earnings=None,
                risk_level="UNKNOWN",
                risk_score=50,  # Unknown = medium risk
                should_close_position=False,
                should_avoid_new_position=False,
                max_dte_allowed=45,
                rationale="Could not determine earnings date. Proceed with caution.",
            )

        days_until = earnings.days_until

        # Check if position expires before earnings
        position_safe = False
        if position_expiration:
            try:
                exp_date = datetime.strptime(position_expiration, "%Y-%m-%d")
                if exp_date.date() < earnings.earnings_date.date():
                    position_safe = True
            except Exception:
                pass

        # Determine risk level
        if days_until <= self.CRITICAL_ZONE:
            risk_level = "CRITICAL"
            risk_score = 95
            should_close = not position_safe
            should_avoid = True
            max_dte = 0  # No new positions
            rationale = (
                f"EARNINGS IN {days_until} DAYS! "
                f"IV crush and gap risk extreme. "
                f"Close all short options immediately unless position expires before."
            )

        elif days_until <= self.HIGH_RISK_ZONE:
            risk_level = "HIGH"
            risk_score = 80
            should_close = not position_safe
            should_avoid = True
            max_dte = days_until - 3  # Must expire before earnings
            rationale = (
                f"Earnings in {days_until} days. High IV crush risk. "
                f"Consider closing short options or ensure expiration is before earnings."
            )

        elif days_until <= self.MEDIUM_RISK_ZONE:
            risk_level = "MEDIUM"
            risk_score = 50
            should_close = False
            should_avoid = True
            max_dte = days_until - 3
            rationale = (
                f"Earnings in {days_until} days. Avoid opening new positions that "
                f"expire after earnings unless using defined-risk strategies."
            )

        elif days_until <= self.LOW_RISK_ZONE:
            risk_level = "LOW"
            risk_score = 25
            should_close = False
            should_avoid = False
            max_dte = days_until - 3
            rationale = (
                f"Earnings in {days_until} days. Low risk if position expires before. "
                f"Monitor IV levels for premium selling opportunities."
            )

        else:
            risk_level = "SAFE"
            risk_score = 10
            should_close = False
            should_avoid = False
            max_dte = 45  # Normal trading
            rationale = (
                f"Earnings {days_until}+ days away. Normal trading conditions. "
                f"Watch for IV build-up as earnings approach."
            )

        return EarningsRisk(
            symbol=symbol,
            earnings_date=earnings.earnings_date,
            days_until_earnings=days_until,
            risk_level=risk_level,
            risk_score=risk_score,
            should_close_position=should_close,
            should_avoid_new_position=should_avoid,
            max_dte_allowed=max_dte,
            rationale=rationale,
        )

    def filter_safe_for_trading(
        self,
        symbols: list[str],
        min_days_buffer: int = 7,
    ) -> list[str]:
        """
        Filter symbols that are safe for options trading (no near-term earnings).

        Args:
            symbols: List of symbols to check
            min_days_buffer: Minimum days before earnings required

        Returns:
            Filtered list of safe symbols
        """
        safe_symbols = []

        for symbol in symbols:
            risk = self.assess_earnings_risk(symbol)
            if risk.days_until_earnings is None or risk.days_until_earnings >= min_days_buffer:
                safe_symbols.append(symbol)
            else:
                logger.info(f"Filtering out {symbol}: Earnings in {risk.days_until_earnings} days")

        return safe_symbols

    def get_earnings_calendar(
        self,
        symbols: list[str],
        days_ahead: int = 30,
    ) -> list[EarningsEvent]:
        """
        Get earnings calendar for multiple symbols.

        Args:
            symbols: List of symbols
            days_ahead: Look ahead period

        Returns:
            List of upcoming EarningsEvents sorted by date
        """
        events = []
        cutoff = datetime.now() + timedelta(days=days_ahead)

        for symbol in symbols:
            earnings = self.get_next_earnings(symbol)
            if earnings and earnings.is_upcoming and earnings.earnings_date <= cutoff:
                events.append(earnings)

        # Sort by date
        events.sort(key=lambda x: x.earnings_date)

        return events

    def check_position_safety(
        self,
        symbol: str,
        expiration: str,
        is_short: bool = True,
    ) -> dict:
        """
        Check if an existing option position is safe from earnings risk.

        Args:
            symbol: Stock ticker
            expiration: Option expiration (YYYY-MM-DD)
            is_short: True if short position (sold options)

        Returns:
            Safety assessment dict
        """
        risk = self.assess_earnings_risk(symbol, position_expiration=expiration)

        # Parse expiration
        try:
            exp_date = datetime.strptime(expiration, "%Y-%m-%d")
        except Exception:
            exp_date = None

        # Check if expiration is before earnings
        expires_before_earnings = False
        if exp_date and risk.earnings_date:
            expires_before_earnings = exp_date.date() < risk.earnings_date.date()

        # Determine safety
        if expires_before_earnings:
            safety = "SAFE"
            action = "HOLD"
            reason = f"Position expires {expiration} before earnings"
        elif risk.risk_level == "CRITICAL" and is_short:
            safety = "DANGEROUS"
            action = "CLOSE_IMMEDIATELY"
            reason = f"Short position through earnings in {risk.days_until_earnings} days!"
        elif risk.risk_level == "HIGH" and is_short:
            safety = "RISKY"
            action = "CLOSE_SOON"
            reason = f"Short position with earnings in {risk.days_until_earnings} days"
        elif risk.risk_level in ["MEDIUM", "LOW"]:
            safety = "MONITOR"
            action = "WATCH"
            reason = f"Earnings in {risk.days_until_earnings} days, monitor closely"
        else:
            safety = "OK"
            action = "HOLD"
            reason = "No imminent earnings risk"

        return {
            "symbol": symbol,
            "expiration": expiration,
            "is_short": is_short,
            "safety": safety,
            "action": action,
            "reason": reason,
            "earnings_date": risk.earnings_date.isoformat() if risk.earnings_date else None,
            "days_until_earnings": risk.days_until_earnings,
            "expires_before_earnings": expires_before_earnings,
        }


# Singleton instance for easy access
_earnings_calendar: EarningsCalendar | None = None


def get_earnings_calendar() -> EarningsCalendar:
    """Get singleton EarningsCalendar instance."""
    global _earnings_calendar
    if _earnings_calendar is None:
        _earnings_calendar = EarningsCalendar()
    return _earnings_calendar


def check_earnings_risk(symbol: str) -> EarningsRisk:
    """Quick check for earnings risk on a symbol."""
    return get_earnings_calendar().assess_earnings_risk(symbol)


def is_safe_to_trade(symbol: str, min_days: int = 7) -> bool:
    """Check if it's safe to open options on this symbol."""
    risk = check_earnings_risk(symbol)
    return risk.days_until_earnings is None or risk.days_until_earnings >= min_days


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    calendar = EarningsCalendar()

    # Test symbols
    test_symbols = ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA"]

    print("\n=== EARNINGS CALENDAR CHECK ===\n")

    for symbol in test_symbols:
        risk = calendar.assess_earnings_risk(symbol)
        print(f"{symbol}:")
        if risk.earnings_date:
            print(
                f"  Earnings: {risk.earnings_date.strftime('%Y-%m-%d')} ({risk.days_until_earnings} days)"
            )
        else:
            print("  Earnings: Unknown")
        print(f"  Risk Level: {risk.risk_level} (Score: {risk.risk_score})")
        print(f"  Action: {risk.rationale}")
        print()

    # Check a hypothetical position
    print("\n=== POSITION SAFETY CHECK ===")
    safety = calendar.check_position_safety("NVDA", "2025-12-20", is_short=True)
    print("NVDA short option expiring 2025-12-20:")
    print(f"  Safety: {safety['safety']}")
    print(f"  Action: {safety['action']}")
    print(f"  Reason: {safety['reason']}")
