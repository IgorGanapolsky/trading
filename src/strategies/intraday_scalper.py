"""Intraday Scalping Strategy - Multiple trades per day for higher frequency.

This strategy enables 3-5 trades per day during high-volume windows:
- Morning session: 9:35-10:30 AM ET (opening momentum)
- Afternoon session: 3:00-4:00 PM ET (closing momentum)

Uses 5-minute bars with tighter exit thresholds for quick profits.
Target: $2-5 per trade, 10-50 trades/day = $20-100/day
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IntradaySignal:
    """Signal for intraday scalping trade."""

    is_buy: bool
    strength: float  # 0-1 confidence
    entry_price: float
    take_profit: float
    stop_loss: float
    indicators: dict[str, Any]
    window: str  # "morning" or "afternoon"


@dataclass
class IntradayConfig:
    """Configuration for intraday scalping."""

    # Trading windows (Eastern Time)
    morning_start: time = time(9, 35)
    morning_end: time = time(10, 30)
    afternoon_start: time = time(15, 0)
    afternoon_end: time = time(15, 55)

    # Exit thresholds (tighter than swing trading)
    take_profit_pct: float = 0.005  # 0.5% take profit (quick scalp)
    stop_loss_pct: float = 0.003  # 0.3% stop loss (tight risk)
    max_hold_minutes: int = 30  # Max 30 min hold (no overnight)

    # Position sizing
    position_size_usd: float = 20.0  # $20 per scalp trade
    max_daily_trades: int = 10  # Max 10 trades per day
    max_concurrent: int = 2  # Max 2 open scalp positions

    # Indicator thresholds for 5-min bars
    rsi_oversold: float = 35.0  # Buy when RSI < 35
    rsi_overbought: float = 65.0  # Don't buy when RSI > 65
    macd_threshold: float = 0.0  # MACD must be positive/crossing up
    volume_surge: float = 1.5  # Volume must be 1.5x average


class IntradayScalper:
    """
    Intraday scalping strategy for SPY/QQQ.

    Uses 5-minute bars with momentum + mean reversion signals.
    Quick entries and exits for small, frequent profits.
    """

    def __init__(self, config: IntradayConfig | None = None) -> None:
        self.config = config or IntradayConfig()
        self._daily_trade_count = 0
        self._last_trade_date: str | None = None
        self._open_positions: list[dict] = []

        # Load config from environment
        self.config.take_profit_pct = float(
            os.getenv("INTRADAY_TAKE_PROFIT_PCT", str(self.config.take_profit_pct))
        )
        self.config.stop_loss_pct = float(
            os.getenv("INTRADAY_STOP_LOSS_PCT", str(self.config.stop_loss_pct))
        )
        self.config.position_size_usd = float(
            os.getenv("INTRADAY_POSITION_SIZE", str(self.config.position_size_usd))
        )
        self.config.max_daily_trades = int(
            os.getenv("INTRADAY_MAX_TRADES", str(self.config.max_daily_trades))
        )

    def is_trading_window(self) -> tuple[bool, str]:
        """Check if current time is within a trading window."""
        now_utc = datetime.now(timezone.utc)
        # Convert to Eastern Time (approximate - use pytz in production)
        et_offset = -5  # EST (adjust for DST as needed)
        now_et = now_utc.replace(hour=(now_utc.hour + et_offset) % 24)
        current_time = now_et.time()

        if self.config.morning_start <= current_time <= self.config.morning_end:
            return True, "morning"
        if self.config.afternoon_start <= current_time <= self.config.afternoon_end:
            return True, "afternoon"
        return False, "closed"

    def _reset_daily_counter(self) -> None:
        """Reset daily trade counter if new day."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._last_trade_date != today:
            self._daily_trade_count = 0
            self._last_trade_date = today
            logger.info(f"Reset daily trade counter for {today}")

    def can_trade(self) -> tuple[bool, str]:
        """Check if we can place a new trade."""
        self._reset_daily_counter()

        in_window, window = self.is_trading_window()
        if not in_window:
            return False, f"Outside trading window (current: {window})"

        if self._daily_trade_count >= self.config.max_daily_trades:
            return False, f"Daily trade limit reached ({self.config.max_daily_trades})"

        if len(self._open_positions) >= self.config.max_concurrent:
            return False, f"Max concurrent positions ({self.config.max_concurrent})"

        return True, "Ready to trade"

    def evaluate(self, symbol: str, bars_5min: list[dict]) -> IntradaySignal | None:
        """
        Evaluate symbol using 5-minute bars for scalping opportunity.

        Args:
            symbol: Ticker symbol (SPY, QQQ)
            bars_5min: List of 5-minute OHLCV bars (most recent last)

        Returns:
            IntradaySignal if buy opportunity, None otherwise
        """
        can_trade, reason = self.can_trade()
        if not can_trade:
            logger.info(f"{symbol}: Skip scalp - {reason}")
            return None

        if len(bars_5min) < 20:
            logger.warning(f"{symbol}: Insufficient 5-min bars ({len(bars_5min)})")
            return None

        # Calculate indicators on 5-min bars
        indicators = self._calculate_indicators(bars_5min)

        # Scalping signal logic
        is_buy = self._check_buy_signal(indicators)

        if not is_buy:
            logger.debug(f"{symbol}: No scalp signal - {indicators}")
            return None

        current_price = bars_5min[-1]["close"]
        _, window = self.is_trading_window()

        signal = IntradaySignal(
            is_buy=True,
            strength=self._calculate_strength(indicators),
            entry_price=current_price,
            take_profit=current_price * (1 + self.config.take_profit_pct),
            stop_loss=current_price * (1 - self.config.stop_loss_pct),
            indicators=indicators,
            window=window,
        )

        logger.info(
            f"{symbol}: SCALP SIGNAL - Entry ${current_price:.2f}, "
            f"TP ${signal.take_profit:.2f}, SL ${signal.stop_loss:.2f}"
        )

        return signal

    def _calculate_indicators(self, bars: list[dict]) -> dict[str, Any]:
        """Calculate technical indicators from 5-minute bars."""
        closes = [b["close"] for b in bars]
        volumes = [b["volume"] for b in bars]

        # RSI (14-period)
        rsi = self._calculate_rsi(closes, period=14)

        # MACD (12, 26, 9) - standard
        macd, signal_line, histogram = self._calculate_macd(closes)

        # Volume relative to average
        avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
        current_volume = volumes[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        # Price momentum (5-bar)
        price_change = (closes[-1] - closes[-5]) / closes[-5] if len(closes) >= 5 else 0

        return {
            "rsi": rsi,
            "macd": macd,
            "macd_signal": signal_line,
            "macd_histogram": histogram,
            "volume_ratio": volume_ratio,
            "price_change_5bar": price_change,
            "current_price": closes[-1],
        }

    def _calculate_rsi(self, closes: list[float], period: int = 14) -> float:
        """Calculate RSI from closing prices."""
        if len(closes) < period + 1:
            return 50.0  # Neutral default

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, closes: list[float]) -> tuple[float, float, float]:
        """Calculate MACD, Signal, and Histogram."""
        if len(closes) < 26:
            return 0.0, 0.0, 0.0

        # EMA helper
        def ema(data: list[float], period: int) -> list[float]:
            multiplier = 2 / (period + 1)
            ema_values = [data[0]]
            for price in data[1:]:
                ema_values.append((price * multiplier) + (ema_values[-1] * (1 - multiplier)))
            return ema_values

        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)

        macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
        signal_line = ema(macd_line, 9)

        macd = macd_line[-1]
        signal = signal_line[-1]
        histogram = macd - signal

        return macd, signal, histogram

    def _check_buy_signal(self, indicators: dict[str, Any]) -> bool:
        """Check if indicators suggest a buy."""
        rsi = indicators["rsi"]
        macd_hist = indicators["macd_histogram"]
        volume_ratio = indicators["volume_ratio"]

        # Buy conditions:
        # 1. RSI not overbought (room to run)
        # 2. MACD histogram positive or crossing up
        # 3. Volume surge (institutional interest)

        rsi_ok = rsi < self.config.rsi_overbought
        macd_ok = macd_hist > self.config.macd_threshold
        volume_ok = volume_ratio >= self.config.volume_surge

        # Need at least 2 of 3 conditions
        conditions_met = sum([rsi_ok, macd_ok, volume_ok])

        return conditions_met >= 2

    def _calculate_strength(self, indicators: dict[str, Any]) -> float:
        """Calculate signal strength 0-1."""
        rsi = indicators["rsi"]
        macd_hist = indicators["macd_histogram"]
        volume_ratio = indicators["volume_ratio"]

        # RSI component (lower is better for buy)
        rsi_score = max(0, (self.config.rsi_overbought - rsi) / self.config.rsi_overbought)

        # MACD component (positive histogram is better)
        macd_score = min(1.0, max(0, macd_hist * 10))  # Scale histogram

        # Volume component (higher surge is better)
        volume_score = min(1.0, (volume_ratio - 1) / 2) if volume_ratio > 1 else 0

        # Weighted average
        strength = (rsi_score * 0.3) + (macd_score * 0.4) + (volume_score * 0.3)
        return min(1.0, max(0.0, strength))

    def record_trade(self, symbol: str, entry_price: float) -> None:
        """Record a new trade."""
        self._daily_trade_count += 1
        self._open_positions.append(
            {
                "symbol": symbol,
                "entry_price": entry_price,
                "entry_time": datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.info(
            f"Recorded scalp trade #{self._daily_trade_count}: {symbol} @ ${entry_price:.2f}"
        )

    def close_position(self, symbol: str) -> None:
        """Remove position from tracking."""
        self._open_positions = [p for p in self._open_positions if p["symbol"] != symbol]


def get_intraday_scalper() -> IntradayScalper:
    """Factory function to get configured intraday scalper."""
    return IntradayScalper()
