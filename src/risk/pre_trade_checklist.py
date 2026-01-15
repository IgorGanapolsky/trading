"""Pre-trade checklist enforcement per CLAUDE.md.

This module enforces the MANDATORY Pre-Trade Checklist from CLAUDE.md:
1. Is ticker SPY or IWM? (NO individual stocks until proven)
2. Is position size <=5% of account ($248)?
3. Is it a SPREAD (not naked put)?
4. Checked earnings calendar? (No blackout violations)
5. 30-45 DTE expiration?
6. Stop-loss defined before entry?

Phil Town Rule #1: Don't lose money.
"""

from datetime import datetime


class PreTradeChecklist:
    """Enforces CLAUDE.md mandatory pre-trade checklist.

    This class validates all trades against the strict rules defined in CLAUDE.md
    to protect capital and enforce disciplined trading.

    Attributes:
        ALLOWED_TICKERS: Set of approved underlying tickers (SPY, IWM only).
        MAX_POSITION_PCT: Maximum position size as percentage of account (5%).
        MIN_DTE: Minimum days to expiration (30).
        MAX_DTE: Maximum days to expiration (45).
        EARNINGS_BLACKOUTS: Dictionary of ticker blackout periods around earnings.
    """

    ALLOWED_TICKERS = {"SPY", "IWM"}
    MAX_POSITION_PCT = 0.05  # 5% max
    MIN_DTE = 30
    MAX_DTE = 45

    # Earnings blackout periods - no trading during these windows
    EARNINGS_BLACKOUTS: dict[str, dict[str, str]] = {
        "SOFI": {"start": "2026-01-23", "end": "2026-02-01"},
        "F": {"start": "2026-02-03", "end": "2026-02-11"},
    }

    def __init__(self, account_equity: float):
        """Initialize the pre-trade checklist validator.

        Args:
            account_equity: Current account equity in dollars.

        Raises:
            ValueError: If account_equity is negative.
        """
        if account_equity < 0:
            raise ValueError("Account equity cannot be negative")
        self.account_equity = account_equity
        self.max_risk = account_equity * self.MAX_POSITION_PCT

    def validate(
        self,
        symbol: str,
        max_loss: float,
        dte: int,
        is_spread: bool,
        stop_loss_defined: bool = True,
    ) -> tuple[bool, list[str]]:
        """Run all checklist items. Returns (passed, failures).

        Validates a proposed trade against all CLAUDE.md checklist items:
        1. Ticker must be SPY or IWM
        2. Max loss must be <= 5% of account
        3. Must be a spread (not naked)
        4. Must not be in earnings blackout period
        5. DTE must be 30-45
        6. Stop-loss must be defined

        Args:
            symbol: The option symbol or underlying ticker to trade.
            max_loss: Maximum potential loss on the trade in dollars.
            dte: Days to expiration.
            is_spread: True if this is a spread position (not naked).
            stop_loss_defined: True if stop-loss is defined before entry.

        Returns:
            Tuple of (passed: bool, failures: List[str]).
            passed is True only if ALL checks pass.
            failures contains descriptive messages for each failed check.
        """
        failures: list[str] = []

        # 1. Ticker check
        underlying = self._extract_underlying(symbol)
        if underlying not in self.ALLOWED_TICKERS:
            failures.append(f"Ticker {underlying} not allowed (SPY/IWM only)")

        # 2. Position size check
        if max_loss > self.max_risk:
            failures.append(
                f"Max loss ${max_loss:.2f} exceeds 5% limit (${self.max_risk:.2f})"
            )

        # 3. Spread check
        if not is_spread:
            failures.append("Naked positions not allowed - must use spreads")

        # 4. Earnings blackout check
        if underlying in self.EARNINGS_BLACKOUTS:
            blackout = self.EARNINGS_BLACKOUTS[underlying]
            today = datetime.now().date()
            start = datetime.strptime(blackout["start"], "%Y-%m-%d").date()
            end = datetime.strptime(blackout["end"], "%Y-%m-%d").date()
            if start <= today <= end:
                failures.append(
                    f"{underlying} in earnings blackout until {blackout['end']}"
                )

        # 5. DTE check
        if not (self.MIN_DTE <= dte <= self.MAX_DTE):
            failures.append(f"DTE {dte} outside range ({self.MIN_DTE}-{self.MAX_DTE})")

        # 6. Stop-loss check
        if not stop_loss_defined:
            failures.append("Stop-loss must be defined before entry")

        return len(failures) == 0, failures

    def _extract_underlying(self, symbol: str) -> str:
        """Extract underlying ticker from options symbol.

        Options symbols follow OCC format: SPY260221P00555000
        - First 1-6 chars: underlying symbol (left-padded with spaces for <6 chars)
        - Next 6 digits: expiration date YYMMDD
        - Next 1 char: C or P for call/put
        - Last 8 digits: strike price * 1000

        For standard symbols like SPY/IWM (3 chars), the underlying is the first 3.

        Args:
            symbol: The option symbol (e.g., SPY260221P00555000) or underlying.

        Returns:
            The underlying ticker symbol in uppercase.
        """
        symbol = symbol.upper().strip()

        if len(symbol) > 10:  # Options symbol like SPY260221P00555000
            # For SPY/IWM (3 char tickers), underlying is first 3 chars
            if symbol[:3] in self.ALLOWED_TICKERS:
                return symbol[:3]
            # For 4+ char tickers, extract until we hit a digit
            underlying = ""
            for char in symbol:
                if char.isdigit():
                    break
                underlying += char
            return underlying.rstrip() if underlying else symbol[:4]

        return symbol

    def get_checklist_status(
        self,
        symbol: str,
        max_loss: float,
        dte: int,
        is_spread: bool,
        stop_loss_defined: bool = True,
    ) -> dict[str, dict[str, bool | str]]:
        """Get detailed status of each checklist item.

        Returns a dictionary with status for each checklist item,
        useful for displaying in UI or logging.

        Args:
            symbol: The option symbol or underlying ticker.
            max_loss: Maximum potential loss in dollars.
            dte: Days to expiration.
            is_spread: True if spread position.
            stop_loss_defined: True if stop-loss defined.

        Returns:
            Dictionary mapping checklist item names to their status.
        """
        underlying = self._extract_underlying(symbol)

        status = {
            "ticker_allowed": {
                "passed": underlying in self.ALLOWED_TICKERS,
                "value": underlying,
                "requirement": "SPY or IWM only",
            },
            "position_size": {
                "passed": max_loss <= self.max_risk,
                "value": f"${max_loss:.2f}",
                "requirement": f"<= ${self.max_risk:.2f} (5%)",
            },
            "is_spread": {
                "passed": is_spread,
                "value": "Spread" if is_spread else "Naked",
                "requirement": "Must be spread",
            },
            "earnings_blackout": {
                "passed": True,  # Will be updated below
                "value": "Clear",
                "requirement": "Not in blackout period",
            },
            "dte_range": {
                "passed": self.MIN_DTE <= dte <= self.MAX_DTE,
                "value": str(dte),
                "requirement": f"{self.MIN_DTE}-{self.MAX_DTE} DTE",
            },
            "stop_loss": {
                "passed": stop_loss_defined,
                "value": "Defined" if stop_loss_defined else "Missing",
                "requirement": "Must be defined",
            },
        }

        # Check earnings blackout
        if underlying in self.EARNINGS_BLACKOUTS:
            blackout = self.EARNINGS_BLACKOUTS[underlying]
            today = datetime.now().date()
            start = datetime.strptime(blackout["start"], "%Y-%m-%d").date()
            end = datetime.strptime(blackout["end"], "%Y-%m-%d").date()
            if start <= today <= end:
                status["earnings_blackout"]["passed"] = False
                status["earnings_blackout"]["value"] = f"Blackout until {blackout['end']}"

        return status

    def update_equity(self, new_equity: float) -> None:
        """Update account equity and recalculate max risk.

        Args:
            new_equity: New account equity in dollars.

        Raises:
            ValueError: If new_equity is negative.
        """
        if new_equity < 0:
            raise ValueError("Account equity cannot be negative")
        self.account_equity = new_equity
        self.max_risk = new_equity * self.MAX_POSITION_PCT

    @classmethod
    def add_earnings_blackout(
        cls, ticker: str, start_date: str, end_date: str
    ) -> None:
        """Add or update an earnings blackout period.

        Args:
            ticker: The ticker symbol.
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.

        Raises:
            ValueError: If date format is invalid.
        """
        # Validate date format
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format. Use YYYY-MM-DD: {e}") from e

        cls.EARNINGS_BLACKOUTS[ticker.upper()] = {
            "start": start_date,
            "end": end_date,
        }

    @classmethod
    def remove_earnings_blackout(cls, ticker: str) -> bool:
        """Remove an earnings blackout period.

        Args:
            ticker: The ticker symbol to remove.

        Returns:
            True if blackout was removed, False if ticker not found.
        """
        ticker = ticker.upper()
        if ticker in cls.EARNINGS_BLACKOUTS:
            del cls.EARNINGS_BLACKOUTS[ticker]
            return True
        return False
