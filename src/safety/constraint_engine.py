from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.core.trading_constants import ALLOWED_TICKERS, extract_underlying
from src.safety.mandatory_trade_gate import GateResult

logger = logging.getLogger(__name__)


@dataclass
class ConstraintEngine:
    """
    Core safety gate engine for all trade entries.
    Implements deterministic rules that override LLM/ML suggestions.
    """

    max_positions: int = 8  # 2 ICs * 4 legs
    max_trades_per_day: int = 5

    def __post_init__(self):
        self.VIX_MAX_GATE = 25.0
        self.MIN_LEG_WIDTH = 10.0
        # ALLOWED_WEEKDAYS: empty list = no weekday restriction. The prior value
        # `[3]` (Thursday-only) was retired 2026-05-20 because
        # docs/research/2026-05-19-edge-analysis.md showed the "60% Thursday"
        # claim does not survive Bonferroni correction (adj_p = 0.190 at α=0.05,
        # n=10). Enforcing it silently blocked Mon/Tue/Wed/Fri entries on bad
        # evidence. Re-enable only with a fresh, statistically valid hypothesis.
        self.ALLOWED_WEEKDAYS: list[int] = []
        self.MIN_ENTRY_DTE = 14
        self.MANDATORY_EXIT_DTE = 7  # LL-268

    def validate_trade(
        self,
        symbol: str,
        position_size: float,
        current_positions: int,
        trades_today: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> GateResult:
        """
        Run all deterministic checks for a proposed trade.
        """
        violations = []
        out_metadata = {}
        trade_meta = metadata or {}

        # 1. VIX Gate (P0 Risk Protection)
        vix = trade_meta.get("vix", 0)
        if vix > self.VIX_MAX_GATE:
            violations.append(f"VIX {vix} above safe threshold {self.VIX_MAX_GATE}.")
            out_metadata["vix_gate"] = "FAILED"
        else:
            out_metadata["vix_gate"] = "PASSED"

        # 2. Weekday Gate — only enforced when ALLOWED_WEEKDAYS is non-empty.
        # The prior Thursday-only restriction was removed 2026-05-20 (see
        # docs/research/2026-05-19-edge-analysis.md: Bonferroni adj_p = 0.190).
        if self.ALLOWED_WEEKDAYS:
            current_weekday = trade_meta.get("weekday", -1)
            if current_weekday not in self.ALLOWED_WEEKDAYS:
                violations.append(
                    f"Weekday {current_weekday} not in allowed list {self.ALLOWED_WEEKDAYS}."
                )
                out_metadata["weekday_gate"] = "FAILED"
            else:
                out_metadata["weekday_gate"] = "PASSED"
        else:
            out_metadata["weekday_gate"] = "DISABLED"

        # 3. DTE Entry Gate (P0 Win Rate Driver - LL-268).
        # FAIL CLOSED on missing dte. The previous `get("dte", 30)` silently
        # passed any caller that omitted the field (refactor, typo, new
        # path) — a deterministic safety gate that defaults a missing
        # required field to a passing value is the exact fail-open pattern
        # this engine exists to prevent.
        dte = trade_meta.get("dte")
        if dte is None:
            violations.append(
                "DTE missing from trade metadata (deterministic gate requires explicit DTE)."
            )
            out_metadata["dte_gate"] = "FAILED"
        elif dte < self.MIN_ENTRY_DTE:
            violations.append(
                f"DTE {dte} too low for entry. Minimum is {self.MIN_ENTRY_DTE} (Gamma Risk protection)."
            )
            out_metadata["dte_gate"] = "FAILED"
        else:
            out_metadata["dte_gate"] = "PASSED"

        # 4. Daily Volume Throttle (P0 failure driver)
        if trades_today >= self.max_trades_per_day:
            violations.append(
                f"Daily trade limit reached ({trades_today}/{self.max_trades_per_day}). "
                "Throttling to prevent over-trading clusters."
            )
            out_metadata["volume_throttle"] = "FAILED"
        else:
            out_metadata["volume_throttle"] = "PASSED"

        # 5. Position Size Safety
        if position_size > 10000:  # $10k per structure limit
            violations.append(f"Position size ${position_size} exceeds safety limit.")
            out_metadata["size_check"] = "FAILED"
        else:
            out_metadata["size_check"] = "PASSED"

        # 6. Iron Condor Width Check
        width = trade_meta.get("wing_width", 0)
        if width < self.MIN_LEG_WIDTH and width > 0:
            violations.append(f"Wing width {width} below minimum {self.MIN_LEG_WIDTH}.")
            out_metadata["width_check"] = "FAILED"
        else:
            out_metadata["width_check"] = "PASSED"

        # 7. Position Count Check
        if current_positions >= self.max_positions:
            violations.append(f"Max positions ({self.max_positions}) reached. Cannot add {symbol}.")
            out_metadata["count_check"] = "FAILED"
        else:
            out_metadata["count_check"] = "PASSED"

        # 8. Underlyings Check (for options)
        underlying = extract_underlying(symbol)
        if underlying not in ALLOWED_TICKERS:
            violations.append(f"Underlying {underlying} not in allowed list.")
            out_metadata["underlying_check"] = "FAILED"
        else:
            out_metadata["underlying_check"] = "PASSED"

        passed = len(violations) == 0
        return GateResult(
            approved=passed,
            reason="; ".join(violations) if not passed else "Approved",
            checks_performed=list(out_metadata.keys()),
        )
