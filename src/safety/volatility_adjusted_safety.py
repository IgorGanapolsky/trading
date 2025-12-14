"""
Volatility-Adjusted Safety Module

Implements the recommendations from Deep Research analysis (Dec 11, 2025):
1. ATR-based volatility-adjusted limits (replace fixed 10% limits)
2. Drift Detection Test (live entry price vs signal price)
3. Hourly Loss Heartbeat ($50/hour auto-disable)
4. LLM Hallucination Check (regex validation of LLM outputs)

These safety tests allow speed but prevent ruin, as recommended
for achieving $100/day North Star goal.

Author: Trading System (CTO)
Created: 2025-12-11
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# 1. ATR-BASED VOLATILITY-ADJUSTED LIMITS
# =============================================================================


@dataclass
class ATRBasedLimitResult:
    """Result of ATR-based position sizing limit."""

    base_limit_pct: float
    adjusted_limit_pct: float
    atr_value: float
    atr_pct: float  # ATR as % of price
    volatility_regime: str  # "low", "normal", "high", "extreme"
    multiplier: float
    reason: str


class ATRBasedLimits:
    """
    Replace fixed percentage limits with ATR-based volatility-adjusted limits.

    The problem with fixed 10% limits:
    - Too aggressive in quiet markets (wastes capital efficiency)
    - Too loose in volatile markets (excessive risk)

    Solution: Use 2x ATR to dynamically adjust position limits.

    Calculation:
    - Base limit = 5% (comfortable default)
    - If ATR% < 1%: market is calm, can go up to 8%
    - If ATR% > 3%: market is volatile, reduce to 2-3%
    - If ATR% > 5%: extreme volatility, reduce to 1%
    """

    # ATR thresholds for regime detection
    ATR_THRESHOLDS = {
        "calm": 0.01,  # < 1% ATR = calm
        "normal": 0.02,  # 1-2% ATR = normal
        "volatile": 0.03,  # 2-3% ATR = volatile
        "extreme": 0.05,  # > 5% ATR = extreme
    }

    # Limit adjustments by regime
    REGIME_LIMITS = {
        "calm": {"max_position_pct": 0.08, "multiplier": 1.6},
        "normal": {"max_position_pct": 0.05, "multiplier": 1.0},
        "volatile": {"max_position_pct": 0.03, "multiplier": 0.6},
        "extreme": {"max_position_pct": 0.01, "multiplier": 0.2},
    }

    def __init__(
        self,
        base_max_position_pct: float = 0.05,
        atr_multiplier: float = 2.0,  # Use 2x ATR for stops
        lookback_days: int = 14,
    ):
        """
        Initialize ATR-based limit calculator.

        Args:
            base_max_position_pct: Default position limit (5%)
            atr_multiplier: Multiplier for ATR-based stop distance
            lookback_days: Days for ATR calculation
        """
        self.base_max_position_pct = base_max_position_pct
        self.atr_multiplier = atr_multiplier
        self.lookback_days = lookback_days

        # Cache for ATR values (refresh every hour)
        self._atr_cache: dict[str, tuple[float, float]] = {}
        self._cache_ttl = 3600  # 1 hour

    def calculate_position_limit(
        self,
        symbol: str,
        current_price: float,
        atr_value: float | None = None,
        account_equity: float = 100000.0,
    ) -> ATRBasedLimitResult:
        """
        Calculate volatility-adjusted position limit for a symbol.

        Args:
            symbol: Trading symbol
            current_price: Current price of the asset
            atr_value: Pre-calculated ATR (or None to fetch)
            account_equity: Total account equity

        Returns:
            ATRBasedLimitResult with adjusted position limit
        """
        # Get ATR value
        if atr_value is None:
            atr_value = self._get_atr(symbol, current_price)

        # Calculate ATR as percentage of price
        atr_pct = atr_value / current_price if current_price > 0 else 0.02

        # Determine volatility regime
        if atr_pct < self.ATR_THRESHOLDS["calm"]:
            regime = "calm"
        elif atr_pct < self.ATR_THRESHOLDS["normal"]:
            regime = "normal"
        elif atr_pct < self.ATR_THRESHOLDS["volatile"]:
            regime = "volatile"
        else:
            regime = "extreme"

        # Get regime-specific limits
        regime_config = self.REGIME_LIMITS[regime]
        adjusted_limit_pct = regime_config["max_position_pct"]
        multiplier = regime_config["multiplier"]

        # Dynamic adjustment based on actual ATR%
        # Formula: base_limit * (normal_atr / actual_atr)
        normal_atr = 0.015  # 1.5% is "normal" volatility
        dynamic_multiplier = min(2.0, max(0.2, normal_atr / atr_pct))
        adjusted_limit_pct = self.base_max_position_pct * dynamic_multiplier

        # Cap at regime limits
        adjusted_limit_pct = min(adjusted_limit_pct, regime_config["max_position_pct"])
        adjusted_limit_pct = max(adjusted_limit_pct, 0.01)  # Floor at 1%

        reason = (
            f"{regime.upper()} volatility: ATR={atr_pct:.2%} → "
            f"limit adjusted from {self.base_max_position_pct:.1%} to {adjusted_limit_pct:.1%}"
        )

        return ATRBasedLimitResult(
            base_limit_pct=self.base_max_position_pct,
            adjusted_limit_pct=adjusted_limit_pct,
            atr_value=atr_value,
            atr_pct=atr_pct,
            volatility_regime=regime,
            multiplier=dynamic_multiplier,
            reason=reason,
        )

    def _get_atr(self, symbol: str, current_price: float) -> float:
        """Get ATR value for symbol (with caching)."""
        now = time.time()

        # Check cache
        if symbol in self._atr_cache:
            cached_atr, cached_time = self._atr_cache[symbol]
            if now - cached_time < self._cache_ttl:
                return cached_atr

        # Try to fetch live ATR
        try:
            from src.agents.momentum_agent import get_atr_for_symbol

            atr_value = get_atr_for_symbol(symbol, self.lookback_days)
        except Exception as e:
            logger.warning(f"Could not fetch ATR for {symbol}: {e}")
            # Fallback: estimate ATR as 1.5% of price (typical for SPY)
            atr_value = current_price * 0.015

        # Cache result
        self._atr_cache[symbol] = (atr_value, now)
        return atr_value


# =============================================================================
# 2. DRIFT DETECTION TEST
# =============================================================================


@dataclass
class DriftTestResult:
    """Result of price drift detection."""

    signal_price: float
    entry_price: float
    drift_amount: float
    drift_pct: float
    is_excessive: bool  # True if drift > threshold
    recommendation: str
    should_abort: bool


class DriftDetector:
    """
    Detect execution drift (slippage from signal to actual entry).

    The problem: By the time an LLM processes data and makes a decision,
    the market may have moved. If drift > 0.1%, the "alpha" may be gone.

    This detector:
    1. Records signal price at decision time
    2. Compares to actual entry price at execution time
    3. Alerts if drift exceeds threshold
    4. Optionally aborts trade if drift is excessive
    """

    # Thresholds
    WARNING_DRIFT_PCT = 0.001  # 0.1% - warn
    ABORT_DRIFT_PCT = 0.005  # 0.5% - abort trade

    def __init__(
        self,
        warning_threshold: float = WARNING_DRIFT_PCT,
        abort_threshold: float = ABORT_DRIFT_PCT,
        history_file: str = "data/drift_history.json",
    ):
        """
        Initialize drift detector.

        Args:
            warning_threshold: Drift % to trigger warning (default 0.1%)
            abort_threshold: Drift % to abort trade (default 0.5%)
            history_file: File to store drift history for analysis
        """
        self.warning_threshold = warning_threshold
        self.abort_threshold = abort_threshold
        self.history_file = Path(history_file)

        # Pending signals (waiting for execution)
        self._pending_signals: dict[str, dict] = {}

        # Load history
        self._history = self._load_history()

    def record_signal(
        self,
        symbol: str,
        signal_price: float,
        signal_time: datetime | None = None,
    ) -> None:
        """
        Record a trading signal's price at decision time.

        Call this when the trading decision is made, BEFORE execution.
        """
        self._pending_signals[symbol] = {
            "signal_price": signal_price,
            "signal_time": (signal_time or datetime.now()).isoformat(),
        }
        logger.debug(f"Signal recorded for {symbol} at ${signal_price:.2f}")

    def check_drift(
        self,
        symbol: str,
        entry_price: float,
    ) -> DriftTestResult:
        """
        Check price drift at execution time.

        Call this immediately before/after order execution.

        Args:
            symbol: Trading symbol
            entry_price: Actual entry price

        Returns:
            DriftTestResult with drift analysis
        """
        # Get pending signal
        signal = self._pending_signals.pop(symbol, None)

        if signal is None:
            # No signal recorded - can't calculate drift
            logger.warning(f"No signal recorded for {symbol}, cannot calculate drift")
            return DriftTestResult(
                signal_price=entry_price,
                entry_price=entry_price,
                drift_amount=0,
                drift_pct=0,
                is_excessive=False,
                recommendation="Signal price not recorded",
                should_abort=False,
            )

        signal_price = signal["signal_price"]

        # Calculate drift
        drift_amount = entry_price - signal_price
        drift_pct = abs(drift_amount) / signal_price if signal_price > 0 else 0

        # Determine action
        if drift_pct > self.abort_threshold:
            is_excessive = True
            should_abort = True
            recommendation = (
                f"ABORT: Drift {drift_pct:.2%} exceeds {self.abort_threshold:.2%} threshold"
            )
        elif drift_pct > self.warning_threshold:
            is_excessive = True
            should_abort = False
            recommendation = f"WARNING: Drift {drift_pct:.2%} above {self.warning_threshold:.2%}"
        else:
            is_excessive = False
            should_abort = False
            recommendation = f"OK: Drift {drift_pct:.2%} within acceptable range"

        # Record for history
        self._record_drift(symbol, signal_price, entry_price, drift_pct)

        return DriftTestResult(
            signal_price=signal_price,
            entry_price=entry_price,
            drift_amount=drift_amount,
            drift_pct=drift_pct,
            is_excessive=is_excessive,
            recommendation=recommendation,
            should_abort=should_abort,
        )

    def get_average_drift(self, symbol: str | None = None, days: int = 30) -> float:
        """Get average drift over recent trades."""
        cutoff = datetime.now() - timedelta(days=days)

        drifts = []
        for entry in self._history:
            if symbol and entry.get("symbol") != symbol:
                continue
            try:
                entry_time = datetime.fromisoformat(entry["timestamp"])
                if entry_time > cutoff:
                    drifts.append(entry["drift_pct"])
            except Exception:
                pass

        return sum(drifts) / len(drifts) if drifts else 0.0

    def _record_drift(
        self,
        symbol: str,
        signal_price: float,
        entry_price: float,
        drift_pct: float,
    ) -> None:
        """Record drift to history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "signal_price": signal_price,
            "entry_price": entry_price,
            "drift_pct": drift_pct,
        }
        self._history.append(entry)

        # Keep only last 1000 entries
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

        self._save_history()

    def _load_history(self) -> list:
        """Load drift history from file."""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load drift history: {e}")
            return []

    def _save_history(self) -> None:
        """Save drift history to file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w") as f:
                json.dump(self._history, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save drift history: {e}")


# =============================================================================
# 3. HOURLY LOSS HEARTBEAT
# =============================================================================


@dataclass
class HeartbeatStatus:
    """Status of the hourly loss heartbeat."""

    current_hourly_loss: float
    hourly_limit: float
    is_blocked: bool
    time_until_reset: timedelta | None
    trades_this_hour: int
    reason: str


class HourlyLossHeartbeat:
    """
    Auto-disable trading if hourly losses exceed threshold.

    The problem: During market "chop" (sideways volatile movement),
    the bot can spiral into "revenge trading" - making rapid losses.

    Solution: If the bot loses $50 in 1 hour, auto-disable for the
    rest of that hour. This prevents loss spirals.

    This is different from the daily circuit breaker - it's more
    granular and prevents rapid loss accumulation within a single hour.
    """

    DEFAULT_HOURLY_LIMIT = 50.0  # $50 max hourly loss

    def __init__(
        self,
        hourly_loss_limit: float = DEFAULT_HOURLY_LIMIT,
        state_file: str = "data/hourly_heartbeat_state.json",
    ):
        """
        Initialize hourly loss heartbeat.

        Args:
            hourly_loss_limit: Maximum hourly loss before pause (default $50)
            state_file: File to persist state
        """
        self.hourly_loss_limit = hourly_loss_limit
        self.state_file = Path(state_file)

        # State
        self._current_hour: int | None = None
        self._hourly_loss: float = 0.0
        self._hourly_trades: list[dict] = []
        self._is_blocked: bool = False
        self._blocked_until: datetime | None = None

        self._load_state()

    def check_heartbeat(self) -> HeartbeatStatus:
        """
        Check if trading is allowed based on hourly losses.

        Call this BEFORE every trade.

        Returns:
            HeartbeatStatus indicating whether trading is allowed
        """
        current_hour = datetime.now().hour

        # Check if hour changed - reset if so
        if self._current_hour != current_hour:
            self._reset_hour(current_hour)

        # Check if still blocked
        if self._is_blocked:
            if self._blocked_until and datetime.now() >= self._blocked_until:
                self._is_blocked = False
                self._blocked_until = None
                logger.info("Hourly heartbeat block expired, trading resumed")
            else:
                time_remaining = (
                    self._blocked_until - datetime.now()
                    if self._blocked_until
                    else timedelta(hours=1)
                )
                return HeartbeatStatus(
                    current_hourly_loss=self._hourly_loss,
                    hourly_limit=self.hourly_loss_limit,
                    is_blocked=True,
                    time_until_reset=time_remaining,
                    trades_this_hour=len(self._hourly_trades),
                    reason=f"BLOCKED: ${self._hourly_loss:.2f} hourly loss exceeds ${self.hourly_loss_limit:.2f} limit",
                )

        # Calculate time until next hour
        now = datetime.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        time_until_reset = next_hour - now

        return HeartbeatStatus(
            current_hourly_loss=self._hourly_loss,
            hourly_limit=self.hourly_loss_limit,
            is_blocked=False,
            time_until_reset=time_until_reset,
            trades_this_hour=len(self._hourly_trades),
            reason=f"OK: ${self._hourly_loss:.2f} / ${self.hourly_loss_limit:.2f} hourly limit",
        )

    def record_trade_result(
        self,
        symbol: str,
        profit_loss: float,
    ) -> HeartbeatStatus:
        """
        Record a trade result and check if limit exceeded.

        Call this AFTER every trade completes.

        Args:
            symbol: Trading symbol
            profit_loss: Profit (+) or loss (-) from the trade

        Returns:
            Updated HeartbeatStatus
        """
        current_hour = datetime.now().hour

        # Reset if hour changed
        if self._current_hour != current_hour:
            self._reset_hour(current_hour)

        # Record trade
        self._hourly_trades.append(
            {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "profit_loss": profit_loss,
            }
        )

        # Update hourly loss (only count losses, not gains)
        if profit_loss < 0:
            self._hourly_loss += abs(profit_loss)

        # Check if limit exceeded
        if self._hourly_loss >= self.hourly_loss_limit and not self._is_blocked:
            self._trigger_block()

        self._save_state()
        return self.check_heartbeat()

    def _trigger_block(self) -> None:
        """Trigger the hourly block."""
        self._is_blocked = True

        # Block until the next hour
        now = datetime.now()
        self._blocked_until = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        logger.warning(
            f"🚨 HOURLY HEARTBEAT TRIGGERED: ${self._hourly_loss:.2f} loss in 1 hour. "
            f"Trading paused until {self._blocked_until.strftime('%H:%M')}"
        )

        self._save_state()

    def _reset_hour(self, new_hour: int) -> None:
        """Reset hourly counters for new hour."""
        self._current_hour = new_hour
        self._hourly_loss = 0.0
        self._hourly_trades = []
        self._is_blocked = False
        self._blocked_until = None

        logger.info(f"Hourly heartbeat reset for hour {new_hour}")
        self._save_state()

    def force_reset(self) -> None:
        """Force reset the heartbeat (manual intervention)."""
        self._reset_hour(datetime.now().hour)
        logger.warning("Hourly heartbeat manually reset")

    def _load_state(self) -> None:
        """Load state from file."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file) as f:
                state = json.load(f)

            self._current_hour = state.get("current_hour")
            self._hourly_loss = state.get("hourly_loss", 0.0)
            self._hourly_trades = state.get("hourly_trades", [])
            self._is_blocked = state.get("is_blocked", False)

            blocked_until = state.get("blocked_until")
            if blocked_until:
                self._blocked_until = datetime.fromisoformat(blocked_until)
        except Exception as e:
            logger.warning(f"Could not load heartbeat state: {e}")

    def _save_state(self) -> None:
        """Save state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "current_hour": self._current_hour,
                "hourly_loss": self._hourly_loss,
                "hourly_trades": self._hourly_trades,
                "is_blocked": self._is_blocked,
                "blocked_until": self._blocked_until.isoformat() if self._blocked_until else None,
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save heartbeat state: {e}")


# =============================================================================
# 4. LLM HALLUCINATION CHECK
# =============================================================================


@dataclass
class HallucinationCheckResult:
    """Result of LLM output hallucination check."""

    is_valid: bool
    original_output: str
    parsed_data: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]


class LLMHallucinationChecker:
    """
    Validate LLM outputs before acting on them.

    The problem: LLMs can "hallucinate" - generating outputs that look
    plausible but contain invalid data. For trading, this could mean:
    - Invalid ticker symbols ("Buy NaN", "Buy XXXXXXX")
    - Impossible quantities ("Buy 1000000 shares")
    - Malformed JSON responses
    - Sentiment scores outside valid range

    This checker uses regex and validation rules to catch these errors
    BEFORE they reach the broker API.
    """

    # Valid ticker regex: 1-5 uppercase letters, optionally with . for class
    TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$")

    # Valid side values
    VALID_SIDES = {"buy", "sell", "hold", "long", "short"}

    # Valid sentiment range
    SENTIMENT_MIN = -1.0
    SENTIMENT_MAX = 1.0

    # Suspicious values that indicate hallucination
    SUSPICIOUS_VALUES = {
        "nan",
        "null",
        "none",
        "undefined",
        "infinity",
        "inf",
        "-inf",
        "n/a",
        "na",
        "error",
        "unknown",
    }

    # Max reasonable quantity for any single trade
    MAX_QUANTITY = 100000
    MAX_NOTIONAL = 1000000  # $1M absolute max

    def __init__(self):
        """Initialize the hallucination checker."""
        pass

    def validate_trade_signal(
        self,
        llm_output: str | dict,
    ) -> HallucinationCheckResult:
        """
        Validate an LLM-generated trade signal.

        Args:
            llm_output: Raw LLM output (string or parsed dict)

        Returns:
            HallucinationCheckResult with validation status
        """
        errors = []
        warnings = []
        parsed_data = None

        # Handle string input
        if isinstance(llm_output, str):
            original = llm_output
            try:
                # Try to parse as JSON
                parsed_data = json.loads(llm_output)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", llm_output, re.DOTALL)
                if json_match:
                    try:
                        parsed_data = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        errors.append("Could not parse embedded JSON")
                else:
                    errors.append("Could not parse LLM output as JSON")
        else:
            original = json.dumps(llm_output)
            parsed_data = llm_output

        if parsed_data is None:
            return HallucinationCheckResult(
                is_valid=False,
                original_output=original,
                parsed_data=None,
                errors=errors,
                warnings=warnings,
            )

        # Validate ticker
        ticker = parsed_data.get("ticker") or parsed_data.get("symbol")
        if ticker:
            ticker_str = str(ticker).upper().strip()
            if not self.TICKER_PATTERN.match(ticker_str):
                errors.append(f"Invalid ticker format: '{ticker}'")
            if ticker_str.lower() in self.SUSPICIOUS_VALUES:
                errors.append(f"Suspicious ticker value: '{ticker}'")

        # Validate side/action
        side = parsed_data.get("side") or parsed_data.get("action")
        if side:
            side_str = str(side).lower().strip()
            if side_str not in self.VALID_SIDES:
                warnings.append(f"Unusual side value: '{side}'")
            if side_str in self.SUSPICIOUS_VALUES:
                errors.append(f"Suspicious side value: '{side}'")

        # Validate quantity
        qty = parsed_data.get("quantity") or parsed_data.get("qty") or parsed_data.get("shares")
        if qty is not None:
            try:
                qty_float = float(qty)
                if qty_float < 0:
                    errors.append(f"Negative quantity: {qty}")
                if qty_float > self.MAX_QUANTITY:
                    errors.append(f"Quantity {qty} exceeds max {self.MAX_QUANTITY}")
                if qty_float != qty_float:  # NaN check
                    errors.append("Quantity is NaN")
            except (ValueError, TypeError):
                errors.append(f"Invalid quantity format: '{qty}'")

        # Validate notional/amount
        notional = (
            parsed_data.get("notional") or parsed_data.get("amount") or parsed_data.get("value")
        )
        if notional is not None:
            try:
                notional_float = float(notional)
                if notional_float < 0:
                    errors.append(f"Negative notional: {notional}")
                if notional_float > self.MAX_NOTIONAL:
                    errors.append(f"Notional ${notional} exceeds max ${self.MAX_NOTIONAL}")
                if notional_float != notional_float:  # NaN check
                    errors.append("Notional is NaN")
            except (ValueError, TypeError):
                errors.append(f"Invalid notional format: '{notional}'")

        # Validate sentiment score
        sentiment = parsed_data.get("sentiment") or parsed_data.get("score")
        if sentiment is not None:
            try:
                sent_float = float(sentiment)
                if sent_float < self.SENTIMENT_MIN or sent_float > self.SENTIMENT_MAX:
                    warnings.append(
                        f"Sentiment {sent_float} outside range [{self.SENTIMENT_MIN}, {self.SENTIMENT_MAX}]"
                    )
                if sent_float != sent_float:  # NaN check
                    errors.append("Sentiment is NaN")
            except (ValueError, TypeError):
                # Sentiment might be a string like "bullish"
                sent_str = str(sentiment).lower()
                if sent_str in self.SUSPICIOUS_VALUES:
                    errors.append(f"Suspicious sentiment value: '{sentiment}'")

        # Validate confidence
        confidence = parsed_data.get("confidence")
        if confidence is not None:
            try:
                conf_float = float(confidence)
                if conf_float < 0 or conf_float > 1:
                    warnings.append(f"Confidence {conf_float} outside range [0, 1]")
            except (ValueError, TypeError):
                pass  # Confidence might be "high"/"low" string

        # Check for any suspicious values in all fields
        for key, value in parsed_data.items():
            if isinstance(value, str) and value.lower() in self.SUSPICIOUS_VALUES:
                warnings.append(f"Suspicious value in '{key}': '{value}'")

        is_valid = len(errors) == 0

        if not is_valid:
            logger.warning(f"LLM hallucination detected: {errors}")

        return HallucinationCheckResult(
            is_valid=is_valid,
            original_output=original,
            parsed_data=parsed_data,
            errors=errors,
            warnings=warnings,
        )

    def validate_sentiment_analysis(
        self,
        llm_output: str | dict,
    ) -> HallucinationCheckResult:
        """
        Validate LLM-generated sentiment analysis.

        Args:
            llm_output: Raw LLM sentiment output

        Returns:
            HallucinationCheckResult
        """
        result = self.validate_trade_signal(llm_output)

        # Additional sentiment-specific checks
        if result.parsed_data:
            # Ensure required sentiment fields exist
            required_fields = ["score", "sentiment", "confidence"]
            has_any = any(result.parsed_data.get(f) is not None for f in required_fields)
            if not has_any:
                result.warnings.append("Missing sentiment score/confidence fields")

        return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


# Singleton instances
_atr_limits: ATRBasedLimits | None = None
_drift_detector: DriftDetector | None = None
_heartbeat: HourlyLossHeartbeat | None = None
_hallucination_checker: LLMHallucinationChecker | None = None


def get_atr_limits() -> ATRBasedLimits:
    """Get or create ATR-based limits instance."""
    global _atr_limits
    if _atr_limits is None:
        _atr_limits = ATRBasedLimits()
    return _atr_limits


def get_drift_detector() -> DriftDetector:
    """Get or create drift detector instance."""
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = DriftDetector()
    return _drift_detector


def get_hourly_heartbeat() -> HourlyLossHeartbeat:
    """Get or create hourly heartbeat instance."""
    global _heartbeat
    if _heartbeat is None:
        _heartbeat = HourlyLossHeartbeat()
    return _heartbeat


def get_hallucination_checker() -> LLMHallucinationChecker:
    """Get or create hallucination checker instance."""
    global _hallucination_checker
    if _hallucination_checker is None:
        _hallucination_checker = LLMHallucinationChecker()
    return _hallucination_checker


def run_all_safety_checks(
    symbol: str,
    entry_price: float,
    notional: float,
    account_equity: float,
    llm_output: dict | None = None,
) -> dict[str, Any]:
    """
    Run all enhanced safety checks in one call.

    Args:
        symbol: Trading symbol
        entry_price: Current/entry price
        notional: Trade amount in dollars
        account_equity: Total account equity
        llm_output: Optional LLM output to validate

    Returns:
        Dict with all check results and overall approval
    """
    results = {
        "approved": True,
        "checks": {},
        "errors": [],
        "warnings": [],
    }

    # 1. ATR-based position limit
    atr_check = get_atr_limits().calculate_position_limit(
        symbol=symbol,
        current_price=entry_price,
        account_equity=account_equity,
    )
    results["checks"]["atr_limits"] = {
        "passed": True,  # Info only, not blocking
        "adjusted_limit_pct": atr_check.adjusted_limit_pct,
        "volatility_regime": atr_check.volatility_regime,
        "reason": atr_check.reason,
    }

    # Check if notional exceeds adjusted limit
    position_pct = notional / account_equity if account_equity > 0 else 1.0
    if position_pct > atr_check.adjusted_limit_pct:
        results["approved"] = False
        results["errors"].append(
            f"Position {position_pct:.1%} exceeds ATR-adjusted limit {atr_check.adjusted_limit_pct:.1%}"
        )
        results["checks"]["atr_limits"]["passed"] = False

    # 2. Hourly heartbeat
    heartbeat_status = get_hourly_heartbeat().check_heartbeat()
    results["checks"]["hourly_heartbeat"] = {
        "passed": not heartbeat_status.is_blocked,
        "hourly_loss": heartbeat_status.current_hourly_loss,
        "hourly_limit": heartbeat_status.hourly_limit,
        "reason": heartbeat_status.reason,
    }
    if heartbeat_status.is_blocked:
        results["approved"] = False
        results["errors"].append(heartbeat_status.reason)

    # 3. Drift detection (if signal was recorded)
    drift_check = get_drift_detector().check_drift(symbol, entry_price)
    results["checks"]["drift_detection"] = {
        "passed": not drift_check.should_abort,
        "drift_pct": drift_check.drift_pct,
        "is_excessive": drift_check.is_excessive,
        "recommendation": drift_check.recommendation,
    }
    if drift_check.should_abort:
        results["approved"] = False
        results["errors"].append(drift_check.recommendation)
    elif drift_check.is_excessive:
        results["warnings"].append(drift_check.recommendation)

    # 4. LLM hallucination check (if output provided)
    if llm_output:
        hallucination_check = get_hallucination_checker().validate_trade_signal(llm_output)
        results["checks"]["hallucination"] = {
            "passed": hallucination_check.is_valid,
            "errors": hallucination_check.errors,
            "warnings": hallucination_check.warnings,
        }
        if not hallucination_check.is_valid:
            results["approved"] = False
            results["errors"].extend(hallucination_check.errors)
        results["warnings"].extend(hallucination_check.warnings)

    return results


if __name__ == "__main__":
    """Demo the volatility-adjusted safety module."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("VOLATILITY-ADJUSTED SAFETY MODULE DEMO")
    print("=" * 80)

    # Test ATR-based limits
    print("\n1. ATR-BASED POSITION LIMITS")
    print("-" * 40)

    atr = ATRBasedLimits()
    for symbol, price, atr_val in [
        ("SPY", 500, 5),  # 1% ATR - calm
        ("NVDA", 500, 15),  # 3% ATR - volatile
        ("GME", 20, 2),  # 10% ATR - extreme
    ]:
        result = atr.calculate_position_limit(symbol, price, atr_val)
        print(f"  {symbol}: {result.reason}")

    # Test drift detection
    print("\n2. DRIFT DETECTION")
    print("-" * 40)

    drift = DriftDetector()
    drift.record_signal("SPY", 500.00)
    for entry_price in [500.10, 500.50, 502.50]:
        result = drift.check_drift("SPY", entry_price)
        print(f"  Signal $500 → Entry ${entry_price}: {result.recommendation}")
        drift.record_signal("SPY", 500.00)  # Re-record for next test

    # Test hourly heartbeat
    print("\n3. HOURLY LOSS HEARTBEAT")
    print("-" * 40)

    heartbeat = HourlyLossHeartbeat(hourly_loss_limit=50)
    print(f"  Initial: {heartbeat.check_heartbeat().reason}")

    for loss in [-10, -15, -20, -10]:  # $55 total loss
        result = heartbeat.record_trade_result("SPY", loss)
        print(f"  After ${loss} loss: {result.reason}")

    # Test hallucination checker
    print("\n4. LLM HALLUCINATION CHECK")
    print("-" * 40)

    checker = LLMHallucinationChecker()

    test_outputs = [
        {"ticker": "AAPL", "side": "buy", "quantity": 10, "confidence": 0.8},
        {"ticker": "NaN", "side": "buy", "quantity": 10},
        {"ticker": "GOOGL", "side": "buy", "quantity": 999999},
        {"ticker": "MSFT", "side": "yolo", "sentiment": "undefined"},
    ]

    for output in test_outputs:
        result = checker.validate_trade_signal(output)
        status = "✅ VALID" if result.is_valid else "❌ INVALID"
        print(f"  {output.get('ticker', 'N/A')}: {status}")
        if result.errors:
            for err in result.errors:
                print(f"    Error: {err}")
