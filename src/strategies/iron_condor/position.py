"""
Iron Condor Position Model - Step 5 of Strategy Upgrade.
Defines a first-class object for managing iron condor state and invariants.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IronCondorPosition:
    """Canonical model for an active Iron Condor position."""

    underlying: str
    expiry: date
    # Legs (OCC symbols)
    short_put_sym: str
    long_put_sym: str
    short_call_sym: str
    long_call_sym: str
    # Strikes
    short_put_strike: float
    long_put_strike: float
    short_call_strike: float
    long_call_strike: float

    quantity: int
    entry_credit: float  # Total credit received per condor (e.g. 1.50)
    entry_date: date = field(default_factory=lambda: datetime.now().date())

    # Metadata for tracking
    entry_vix: float | None = None
    entry_iv: float | None = None

    @property
    def max_profit(self) -> float:
        return self.entry_credit * 100 * self.quantity

    @property
    def max_loss(self) -> float:
        width = max(
            self.short_put_strike - self.long_put_strike,
            self.long_call_strike - self.short_call_strike,
        )
        return (width - self.entry_credit) * 100 * self.quantity

    @property
    def dte(self) -> int:
        return (self.expiry - datetime.now().date()).days

    def calculate_pnl(self, current_mark: float) -> float:
        """Calculate current PnL based on the cost to close the whole condor."""
        # current_mark is the debit to close (e.g. 0.75)
        return (self.entry_credit - current_mark) * 100 * self.quantity

    def get_pnl_pct(self, current_mark: float) -> float:
        """PnL as a percentage of entry credit (used for profit target)."""
        if self.entry_credit == 0:
            return 0.0
        return (self.entry_credit - current_mark) / self.entry_credit

    def to_dict(self) -> dict[str, Any]:
        return {
            "underlying": self.underlying,
            "expiry": self.expiry.isoformat(),
            "short_put": self.short_put_strike,
            "long_put": self.long_put_strike,
            "short_call": self.short_call_strike,
            "long_call": self.long_call_strike,
            "entry_credit": self.entry_credit,
            "quantity": self.quantity,
            "dte": self.dte,
            "entry_date": self.entry_date.isoformat(),
        }
