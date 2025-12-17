"""
Market data utilities with resilient fetching across multiple sources.

Priority order (RELIABLE FIRST):
1. Alpaca API (if credentials available - MOST RELIABLE, use FIRST)
2. Polygon.io API (if available - PAID SERVICE, reliable)
3. Cache (use cached data aggressively - faster than API calls)
4. Yahoo Finance via yfinance (unreliable free source - last resort)
5. Alpha Vantage Daily Adjusted (free tier, throttled - avoid if possible)

CRITICAL: System should NEVER fail completely - skip trades gracefully if data unavailable.
"""

from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

import pandas as pd
import requests

# Optional import - yfinance may not be installed in all environments
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    yf = None  # type: ignore
    YFINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """Data source enumeration for tracking which provider was used."""

    ALPACA = "alpaca"  # Most reliable - use FIRST
    POLYGON = "polygon"  # Paid service - reliable
    CACHE = "cache"  # Fast and reliable if recent
    YFINANCE = "yfinance"  # Unreliable free source
    ALPHA_VANTAGE = "alpha_vantage"  # Slow, rate-limited
    UNKNOWN = "unknown"


@dataclass
class FetchAttempt:
    """Record of a single data fetch attempt."""

    source: DataSource
    timestamp: float
    success: bool
    error_message: str | None = None
    rows_fetched: int = 0
    latency_ms: float = 0.0


@dataclass
class PerformanceMetrics:
    """Performance metrics for data source usage."""

    source: DataSource
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0

    def update(self, success: bool, latency_ms: float):
        """Update metrics with a new request."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        self.total_latency_ms += latency_ms
        self.avg_latency_ms = self.total_latency_ms / self.total_requests
        self.success_rate = (
            self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0
        )


@dataclass
class MarketDataResult:
    """Enhanced result with metadata about data source and fetch attempts."""

    data: pd.DataFrame
    source: DataSource
    attempts: list[FetchAttempt] = field(default_factory=list)
    total_attempts: int = 0
    total_latency_ms: float = 0.0
    cache_age_hours: float | None = None

    def add_attempt(self, attempt: FetchAttempt) -> None:
        """Track a fetch attempt."""
        self.attempts.append(attempt)
        self.total_attempts += 1
        self.total_latency_ms += attempt.latency_ms

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/reporting."""
        return {
            "source": self.source.value,
            "rows": len(self.data),
            "total_attempts": self.total_attempts,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "cache_age_hours": (round(self.cache_age_hours, 2) if self.cache_age_hours else None),
            "attempts": [
                {
                    "source": a.source.value,
                    "success": a.success,
                    "error": a.error_message,
                    "rows": a.rows_fetched,
                    "latency_ms": round(a.latency_ms, 2),
                }
                for a in self.attempts
            ],
        }


class MarketDataProvider:
    """Fetch daily OHLCV data with retries and multi-source fallbacks."""

    def __init__(
        self,
        alpha_vantage_key: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        # Configuration (loaded from env vars at instance creation)
        self.YFINANCE_LOOKBACK_BUFFER_DAYS = int(os.getenv("YFINANCE_LOOKBACK_BUFFER_DAYS", "35"))
        self.YFINANCE_SECONDARY_LOOKBACK_DAYS = int(
            os.getenv("YFINANCE_SECONDARY_LOOKBACK_DAYS", "150")
        )
        # Polygon-specific lookback buffer (can be larger for free tier with delayed data)
        self.POLYGON_LOOKBACK_BUFFER_DAYS = int(
            os.getenv("POLYGON_LOOKBACK_BUFFER_DAYS", "45")
        )  # Increased for free tier
        self.YFINANCE_MAX_RETRIES = int(os.getenv("YFINANCE_MAX_RETRIES", "3"))
        self.YFINANCE_INITIAL_BACKOFF_SECONDS = float(
            os.getenv("YFINANCE_INITIAL_BACKOFF_SECONDS", "1.0")
        )

        self.ALPACA_MAX_RETRIES = int(os.getenv("ALPACA_MAX_RETRIES", "3"))
        self.ALPACA_INITIAL_BACKOFF_SECONDS = float(
            os.getenv("ALPACA_INITIAL_BACKOFF_SECONDS", "2.0")
        )

        self.ALPHAVANTAGE_MIN_INTERVAL_SECONDS = float(
            os.getenv("ALPHAVANTAGE_MIN_INTERVAL_SECONDS", "15")
        )
        self.ALPHAVANTAGE_BACKOFF_SECONDS = float(os.getenv("ALPHAVANTAGE_BACKOFF_SECONDS", "60"))
        self.ALPHAVANTAGE_MAX_RETRIES = int(os.getenv("ALPHAVANTAGE_MAX_RETRIES", "4"))
        # CRITICAL: Max total time to spend on Alpha Vantage (fail fast to avoid workflow timeouts)
        self.ALPHAVANTAGE_MAX_TOTAL_SECONDS = float(
            os.getenv("ALPHAVANTAGE_MAX_TOTAL_SECONDS", "90")
        )  # 90s max

        self.CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", str(6 * 60 * 60)))  # 6 hours
        self.CACHE_MAX_AGE_DAYS = int(
            os.getenv("CACHE_MAX_AGE_DAYS", "7")
        )  # Use cached data up to 7 days old
        self.MAX_DATA_AGE_HOURS = int(
            os.getenv("MAX_DATA_AGE_HOURS", "48")
        )  # Allow data up to 48h old for free Polygon tier
        self.POLYGON_MAX_RETRIES = int(
            os.getenv("POLYGON_MAX_RETRIES", "3")
        )  # Max retries for Polygon API
        self.POLYGON_INITIAL_BACKOFF_SECONDS = float(
            os.getenv("POLYGON_INITIAL_BACKOFF_SECONDS", "30.0")
        )  # Initial backoff: 30s
        self.session = session or requests.Session()
        # Harden yfinance requests to reduce 403/429 responses
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/119.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            }
        )
        self.alpha_vantage_key = alpha_vantage_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        self._last_alpha_call_ts: float = 0.0
        self._cache: dict[tuple[str, int, date], pd.DataFrame] = {}
        cache_root = os.getenv("MARKET_DATA_CACHE_DIR", "data/cache/alpha_vantage")
        self.cache_dir = Path(cache_root)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Health tracking
        self._health_log_file = self.cache_dir / "health_log.jsonl"

        # Performance metrics tracking
        self._metrics: dict[DataSource, PerformanceMetrics] = {
            source: PerformanceMetrics(source=source) for source in DataSource
        }

        # Initialize Alpaca API if credentials available (PRIMARY SOURCE - MOST RELIABLE)
        self._alpaca_api = None
        alpaca_key = os.getenv("ALPACA_API_KEY")
        alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
        if alpaca_key and alpaca_secret:
            try:
                from alpaca.data.historical import StockHistoricalDataClient

                self._alpaca_api = StockHistoricalDataClient(
                    api_key=alpaca_key, secret_key=alpaca_secret
                )
                logger.info(
                    "✅ Alpaca API initialized as PRIMARY market data source (most reliable)"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Alpaca API for market data: {e}")
                self._alpaca_api = None

        # Initialize Polygon.io API if available (SECONDARY RELIABLE SOURCE)
        self.polygon_api_key = os.getenv("POLYGON_API_KEY")
        if self.polygon_api_key:
            logger.info("✅ Polygon.io API available as secondary market data source")
        else:
            logger.debug("Polygon.io API not configured (optional)")

        # Log configuration at startup
        self._log_configuration()

    def get_performance_metrics(self) -> dict[str, dict[str, float]]:
        """Get performance metrics for all data sources."""
        return {
            source.value: {
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "success_rate": metrics.success_rate,
                "avg_latency_ms": metrics.avg_latency_ms,
            }
            for source, metrics in self._metrics.items()
            if metrics.total_requests > 0
        }

    def get_daily_bars(
        self,
        symbol: str,
        lookback_days: int,
        end_datetime: datetime | None = None,
    ) -> MarketDataResult:
        """
        Retrieve daily OHLCV candles for a symbol with comprehensive fallback tracking.

        Args:
            symbol: Equity ticker symbol.
            lookback_days: Number of trading days required (excludes buffer).
            end_datetime: Optional custom end date (defaults to now).

        Returns:
            MarketDataResult with data and metadata about fetch attempts.

        Raises:
            ValueError: if data cannot be fetched from any source.
        """
        end_dt = end_datetime or datetime.now()
        start_dt = end_dt - timedelta(days=lookback_days + self.YFINANCE_LOOKBACK_BUFFER_DAYS)
        cache_key = (symbol.upper(), lookback_days, end_dt.date())
        result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)

        # PRIORITY 1: Check in-memory cache first (fastest, most reliable if recent)
        cached = self._cache.get(cache_key)
        if cached is not None and not cached.empty:
            logger.debug("%s: Serving from in-memory cache", symbol)
            result.data = cached.copy()
            result.source = DataSource.CACHE
            return result

        # PRIORITY 2: Try Polygon.io API (reliable paid source) - MOVED UP
        if self.polygon_api_key:
            logger.info("%s: Fetching from Polygon.io API (primary reliable source)", symbol)
            data = self._fetch_polygon_with_retries(symbol, lookback_days, result)
            if self._is_valid(data, lookback_days):
                prepared = self._prepare(data, lookback_days)
                self._cache[cache_key] = prepared
                result.data = prepared.copy()
                result.source = DataSource.POLYGON
                self._log_health(symbol, result)
                # Update performance metrics
                self._metrics[DataSource.POLYGON].update(True, result.total_latency_ms)
                # Cache successful response to disk for full CACHE_TTL_SECONDS
                self._cache_polygon_response(symbol, prepared)
                logger.info(
                    "%s: ✅ Successfully fetched from Polygon.io (%d rows, %d attempts, %.2fms)",
                    symbol,
                    len(prepared),
                    result.total_attempts,
                    result.total_latency_ms,
                )
                return result
            else:
                logger.warning("%s: Polygon.io returned insufficient data, trying Alpaca", symbol)

        # PRIORITY 3: Try Alpaca API (reliable paid source) - MOVED DOWN
        if self._alpaca_api:
            logger.info("%s: Fetching from Alpaca API (secondary reliable source)", symbol)
            data = self._fetch_alpaca_with_retries(symbol, lookback_days, result)
            if self._is_valid(data, lookback_days):
                prepared = self._prepare(data, lookback_days)
                self._cache[cache_key] = prepared
                result.data = prepared.copy()
                result.source = DataSource.ALPACA
                self._log_health(symbol, result)
                # Update performance metrics
                self._metrics[DataSource.ALPACA].update(True, result.total_latency_ms)
                logger.info(
                    "%s: ✅ Successfully fetched from Alpaca API (%d rows, %d attempts, %.2fms)",
                    symbol,
                    len(prepared),
                    result.total_attempts,
                    result.total_latency_ms,
                )
                return result
            else:
                logger.info(
                    "%s: Alpaca API returned insufficient data, trying cache/yfinance",
                    symbol,
                )

        # PRIORITY 4: Check disk cache (may be stale but better than nothing)
        cached_data, cache_age_hours = self._load_cached_data_with_age(symbol, lookback_days)
        if (
            cached_data is not None
            and cache_age_hours is not None
            and cache_age_hours <= self.MAX_DATA_AGE_HOURS
        ):
            logger.info(
                "%s: Using cached data (%.1f hours old, max allowed: %d hours) - reliable fallback",
                symbol,
                cache_age_hours,
                self.MAX_DATA_AGE_HOURS,
            )
            result.data = cached_data
            result.source = DataSource.CACHE
            result.cache_age_hours = cache_age_hours
            self._log_health(symbol, result)
            return result

        # PRIORITY 5: Try yfinance (unreliable free source - only if no paid sources available)
        logger.warning(
            "%s: Paid sources unavailable/unreliable. Trying yfinance (unreliable free source).",
            symbol,
        )
        data = self._fetch_yfinance_with_retries(symbol, start_dt, end_dt, result)
        if self._is_valid(data, lookback_days):
            prepared = self._prepare(data, lookback_days)
            self._cache[cache_key] = prepared
            result.data = prepared.copy()
            result.source = DataSource.YFINANCE
            self._log_health(symbol, result)
            logger.info(
                "%s: Successfully fetched from yfinance (%d rows, %d attempts, %.2fms)",
                symbol,
                len(prepared),
                result.total_attempts,
                result.total_latency_ms,
            )
            return result

        # Try Alpha Vantage (last resort live source) - BUT CHECK CACHE FIRST
        # Skip Alpha Vantage if we have cached data (faster and avoids rate limits)
        cached_data, cache_age_hours = self._load_cached_data_with_age(symbol, lookback_days)
        if (
            cached_data is not None
            and cache_age_hours is not None
            and cache_age_hours <= self.MAX_DATA_AGE_HOURS
        ):
            logger.info(
                "%s: Using cached data (%.1f hours old, max allowed: %d hours) before trying Alpha Vantage",
                symbol,
                cache_age_hours,
                self.MAX_DATA_AGE_HOURS,
            )
            result.data = cached_data
            result.source = DataSource.CACHE
            result.cache_age_hours = cache_age_hours
            self._log_health(symbol, result)
            return result

        # Only try Alpha Vantage if no recent cache available
        if not self.alpha_vantage_key:
            logger.warning(
                "%s: Alpha Vantage fallback unavailable (ALPHA_VANTAGE_API_KEY not configured).",
                symbol,
            )
        else:
            logger.warning(
                "%s: Alpaca API failed. Trying Alpha Vantage (will fail fast if rate-limited).",
                symbol,
            )
            data = self._fetch_alpha_vantage_with_retries(symbol, result)
            if self._is_valid(data, lookback_days):
                prepared = self._prepare(data, lookback_days)
                self._cache[cache_key] = prepared
                result.data = prepared.copy()
                result.source = DataSource.ALPHA_VANTAGE
                self._log_health(symbol, result)
                logger.info(
                    "%s: Successfully fetched from Alpha Vantage (%d rows, %d attempts, %.2fms)",
                    symbol,
                    len(prepared),
                    result.total_attempts,
                    result.total_latency_ms,
                )
                return result

        # Final fallback: Use cached data if available (stale but better than nothing)
        logger.warning(
            "%s: All live data sources failed. Attempting to use cached data.",
            symbol,
        )
        cached_data, cache_age_hours = self._load_cached_data_with_age(symbol, lookback_days)
        if cached_data is not None:
            result.data = cached_data
            result.source = DataSource.CACHE
            result.cache_age_hours = cache_age_hours
            self._log_health(symbol, result)
            logger.warning(
                "%s: Using cached data (%.1f hours old). Trading will proceed with caution.",
                symbol,
                cache_age_hours,
            )
            return result

        # Complete failure - log and raise
        self._log_health(symbol, result)
        error_summary = "\n".join(
            [f"  - {a.source.value}: {a.error_message}" for a in result.attempts if not a.success]
        )
        raise ValueError(
            f"Failed to fetch {lookback_days} days of data for {symbol} from all sources:\n{error_summary}"
        )

    # ------------------------------------------------------------------
    # Configuration and Health Tracking
    # ------------------------------------------------------------------
    def _log_configuration(self) -> None:
        """Log configuration at startup for debugging."""
        logger.info("MarketDataProvider configuration (RELIABLE FIRST):")
        logger.info(
            "  - Alpaca API: %s (PRIMARY - most reliable)",
            "✅ enabled" if self._alpaca_api else "❌ disabled",
        )
        logger.info(
            "  - Polygon.io: %s (SECONDARY - reliable paid)",
            "✅ enabled" if self.polygon_api_key else "❌ disabled",
        )
        if self.polygon_api_key:
            logger.info(
                "    * Polygon retries: %d, backoff: %.0fs (exponential), max_data_age: %dh",
                self.POLYGON_MAX_RETRIES,
                self.POLYGON_INITIAL_BACKOFF_SECONDS,
                self.MAX_DATA_AGE_HOURS,
            )
        logger.info(
            "  - Cache: dir=%s, ttl=%ds, max_age=%dd (FAST FALLBACK)",
            self.cache_dir,
            self.CACHE_TTL_SECONDS,
            self.CACHE_MAX_AGE_DAYS,
        )
        logger.info(
            "  - yfinance: max_retries=%d (UNRELIABLE FREE - last resort)",
            self.YFINANCE_MAX_RETRIES,
        )
        logger.info(
            "  - Alpha Vantage: %s (SLOW RATE-LIMITED - avoid)",
            "enabled" if self.alpha_vantage_key else "disabled",
        )

    def _log_health(self, symbol: str, result: MarketDataResult) -> None:
        """Log fetch result to health log for monitoring."""
        try:
            import json
            from datetime import timezone

            health_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                **result.to_dict(),
            }
            with open(self._health_log_file, "a") as f:
                f.write(json.dumps(health_entry) + "\n")
        except Exception as exc:
            logger.debug("Failed to write health log: %s", exc)

    # ------------------------------------------------------------------
    # Retry Wrappers with Exponential Backoff
    # ------------------------------------------------------------------
    def _fetch_yfinance_with_retries(
        self,
        symbol: str,
        start_dt: datetime,
        end_dt: datetime,
        result: MarketDataResult,
    ) -> pd.DataFrame | None:
        """Fetch from yfinance with exponential backoff retries."""
        for attempt in range(1, self.YFINANCE_MAX_RETRIES + 1):
            start_time = time.time()
            try:
                data = self._fetch_yfinance(symbol, start_dt, end_dt)
                latency_ms = (time.time() - start_time) * 1000
                if data is not None and not data.empty:
                    result.add_attempt(
                        FetchAttempt(
                            source=DataSource.YFINANCE,
                            timestamp=time.time(),
                            success=True,
                            rows_fetched=len(data),
                            latency_ms=latency_ms,
                        )
                    )
                    return data
                else:
                    result.add_attempt(
                        FetchAttempt(
                            source=DataSource.YFINANCE,
                            timestamp=time.time(),
                            success=False,
                            error_message="Empty DataFrame returned",
                            latency_ms=latency_ms,
                        )
                    )
            except Exception as exc:
                latency_ms = (time.time() - start_time) * 1000
                result.add_attempt(
                    FetchAttempt(
                        source=DataSource.YFINANCE,
                        timestamp=time.time(),
                        success=False,
                        error_message=str(exc),
                        latency_ms=latency_ms,
                    )
                )
                logger.debug(
                    "%s: yfinance attempt %d/%d failed: %s",
                    symbol,
                    attempt,
                    self.YFINANCE_MAX_RETRIES,
                    exc,
                )

            # Exponential backoff before retry
            if attempt < self.YFINANCE_MAX_RETRIES:
                backoff = self.YFINANCE_INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.debug("%s: Retrying yfinance in %.1fs...", symbol, backoff)
                time.sleep(backoff)

        return None

    def _fetch_alpaca_with_retries(
        self, symbol: str, lookback_days: int, result: MarketDataResult
    ) -> pd.DataFrame | None:
        """Fetch from Alpaca API with exponential backoff retries."""
        if not self._alpaca_api:
            result.add_attempt(
                FetchAttempt(
                    source=DataSource.ALPACA,
                    timestamp=time.time(),
                    success=False,
                    error_message="Alpaca API not initialized (missing credentials)",
                )
            )
            return None

        for attempt in range(1, self.ALPACA_MAX_RETRIES + 1):
            start_time = time.time()
            try:
                data = self._fetch_alpaca(symbol, lookback_days)
                latency_ms = (time.time() - start_time) * 1000
                if data is not None and not data.empty:
                    result.add_attempt(
                        FetchAttempt(
                            source=DataSource.ALPACA,
                            timestamp=time.time(),
                            success=True,
                            rows_fetched=len(data),
                            latency_ms=latency_ms,
                        )
                    )
                    return data
                else:
                    result.add_attempt(
                        FetchAttempt(
                            source=DataSource.ALPACA,
                            timestamp=time.time(),
                            success=False,
                            error_message="No bars returned",
                            latency_ms=latency_ms,
                        )
                    )
            except Exception as exc:
                latency_ms = (time.time() - start_time) * 1000
                result.add_attempt(
                    FetchAttempt(
                        source=DataSource.ALPACA,
                        timestamp=time.time(),
                        success=False,
                        error_message=str(exc),
                        latency_ms=latency_ms,
                    )
                )
                logger.debug(
                    "%s: Alpaca attempt %d/%d failed: %s",
                    symbol,
                    attempt,
                    self.ALPACA_MAX_RETRIES,
                    exc,
                )

            # Exponential backoff before retry
            if attempt < self.ALPACA_MAX_RETRIES:
                backoff = self.ALPACA_INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.debug("%s: Retrying Alpaca API in %.1fs...", symbol, backoff)
                time.sleep(backoff)

        return None

    def _fetch_alpha_vantage_with_retries(
        self, symbol: str, result: MarketDataResult
    ) -> pd.DataFrame | None:
        """
        Fetch from Alpha Vantage with FAIL-FAST logic to avoid workflow timeouts.

        CRITICAL: If rate-limited, we FAIL IMMEDIATELY instead of waiting 10+ minutes
        for exponential backoff. This prevents GitHub Actions workflow timeouts.
        """
        start_time = time.time()
        max_total_time = self.ALPHAVANTAGE_MAX_TOTAL_SECONDS

        try:
            data = self._fetch_alpha_vantage(
                symbol, max_total_time=max_total_time, start_time=start_time
            )
            latency_ms = (time.time() - start_time) * 1000
            if data is not None and not data.empty:
                result.add_attempt(
                    FetchAttempt(
                        source=DataSource.ALPHA_VANTAGE,
                        timestamp=time.time(),
                        success=True,
                        rows_fetched=len(data),
                        latency_ms=latency_ms,
                    )
                )
                return data
            else:
                result.add_attempt(
                    FetchAttempt(
                        source=DataSource.ALPHA_VANTAGE,
                        timestamp=time.time(),
                        success=False,
                        error_message="No time series data returned",
                        latency_ms=latency_ms,
                    )
                )
        except TimeoutError as exc:
            latency_ms = (time.time() - start_time) * 1000
            result.add_attempt(
                FetchAttempt(
                    source=DataSource.ALPHA_VANTAGE,
                    timestamp=time.time(),
                    success=False,
                    error_message=f"Timeout after {latency_ms / 1000:.1f}s (max {max_total_time}s): {exc}",
                    latency_ms=latency_ms,
                )
            )
            logger.warning(
                "%s: Alpha Vantage timed out after %.1fs (rate-limited). Using cached data instead.",
                symbol,
                latency_ms / 1000,
            )
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000
            result.add_attempt(
                FetchAttempt(
                    source=DataSource.ALPHA_VANTAGE,
                    timestamp=time.time(),
                    success=False,
                    error_message=str(exc),
                    latency_ms=latency_ms,
                )
            )
            logger.debug("%s: Alpha Vantage failed: %s", symbol, exc)

        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fetch_yfinance(
        self, symbol: str, start_dt: datetime, end_dt: datetime
    ) -> pd.DataFrame | None:
        sleep_seconds = random.uniform(0.3, 1.2)
        time.sleep(sleep_seconds)
        try:
            data = yf.download(
                symbol,
                start=start_dt,
                end=end_dt,
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if isinstance(data, pd.DataFrame) and not data.empty:
                return data
            logger.debug("%s: yfinance primary download returned empty frame.", symbol)
        except Exception as exc:
            logger.warning("yfinance fetch failed for %s: %s", symbol, exc)
            # Track data source failures for monitoring
            try:
                from src.utils.error_monitoring import capture_data_source_failure

                capture_data_source_failure("yfinance", symbol, str(exc))
            except Exception:
                pass  # Error monitoring is optional

        # Secondary attempt using Ticker.history (sometimes succeeds when download fails)
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(
                start=start_dt.strftime("%Y-%m-%d"),
                end=end_dt.strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=False,
            )
            if isinstance(history, pd.DataFrame) and not history.empty:
                return history
        except Exception as exc:
            logger.debug("%s: yfinance ticker.history failed: %s", symbol, exc)

        # Final attempt: broader lookback to mitigate sparse weekends/holidays
        try:
            extended_start = end_dt - timedelta(days=self.YFINANCE_SECONDARY_LOOKBACK_DAYS)
            extended = yf.download(
                symbol,
                start=extended_start,
                end=end_dt,
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if isinstance(extended, pd.DataFrame) and not extended.empty:
                return extended
        except Exception as exc:
            logger.debug("%s: yfinance extended download failed: %s", symbol, exc)

        return None

    def _fetch_alpaca(self, symbol: str, lookback_days: int) -> pd.DataFrame | None:
        """Fetch market data from Alpaca API (preferred fallback)."""
        if not self._alpaca_api:
            logger.debug("%s: Alpaca API not available (missing credentials)", symbol)
            return None

        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            # Alpaca API: get_stock_bars returns BarSet
            end_dt = datetime.now(timezone.utc)
            # Request a generous window to ensure sufficient bars
            start_dt = end_dt - timedelta(days=lookback_days + self.YFINANCE_LOOKBACK_BUFFER_DAYS)
            feed = os.getenv("ALPACA_DATA_FEED", "iex")

            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_dt,
                end=end_dt,
                limit=min(lookback_days + self.YFINANCE_LOOKBACK_BUFFER_DAYS, 5000),
                feed=feed,
                adjustment="raw",
            )

            barset = self._alpaca_api.get_stock_bars(req)

            if not barset.data or symbol not in barset.data or len(barset.data[symbol]) == 0:
                logger.warning("%s: Alpaca API returned no bars", symbol)
                return None

            # Convert Alpaca bars to pandas DataFrame
            records = []
            bars = barset.data[symbol]

            for bar in bars:
                records.append(
                    {
                        "Open": float(bar.open),
                        "High": float(bar.high),
                        "Low": float(bar.low),
                        "Close": float(bar.close),
                        "Volume": int(bar.volume),
                    }
                )

            if not records:
                return None

            # Create DataFrame with datetime index
            df = pd.DataFrame(records, index=[bar.timestamp for bar in bars])
            df.index.name = "Date"
            df = df.sort_index()

            logger.info("%s: Successfully fetched %d bars from Alpaca API", symbol, len(df))
            return df

        except Exception as exc:
            logger.warning("%s: Alpaca API fetch failed: %s", symbol, exc)
            return None

    def _fetch_polygon_with_retries(
        self, symbol: str, lookback_days: int, result: MarketDataResult
    ) -> pd.DataFrame | None:
        """Fetch from Polygon.io API with exponential backoff retries and cache fallback."""
        if not self.polygon_api_key:
            result.add_attempt(
                FetchAttempt(
                    source=DataSource.POLYGON,
                    timestamp=time.time(),
                    success=False,
                    error_message="Polygon.io API not configured (missing POLYGON_API_KEY)",
                )
            )
            return None

        for attempt in range(1, self.POLYGON_MAX_RETRIES + 1):
            start_time = time.time()
            try:
                data = self._fetch_polygon(symbol, lookback_days)
                latency_ms = (time.time() - start_time) * 1000
                if data is not None and not data.empty:
                    result.add_attempt(
                        FetchAttempt(
                            source=DataSource.POLYGON,
                            timestamp=time.time(),
                            success=True,
                            rows_fetched=len(data),
                            latency_ms=latency_ms,
                        )
                    )
                    # Cache successful response for full CACHE_TTL_SECONDS
                    self._cache_polygon_response(symbol, data)
                    return data
                else:
                    result.add_attempt(
                        FetchAttempt(
                            source=DataSource.POLYGON,
                            timestamp=time.time(),
                            success=False,
                            error_message="No bars returned",
                            latency_ms=latency_ms,
                        )
                    )
            except requests.exceptions.HTTPError as exc:
                latency_ms = (time.time() - start_time) * 1000
                # Check if it's a 429 rate limit error
                response = getattr(exc, "response", None)
                if response is not None and response.status_code == 429:
                    logger.warning(
                        "%s: Polygon.io rate limit hit (429) on attempt %d/%d",
                        symbol,
                        attempt,
                        self.POLYGON_MAX_RETRIES,
                    )
                    result.add_attempt(
                        FetchAttempt(
                            source=DataSource.POLYGON,
                            timestamp=time.time(),
                            success=False,
                            error_message=f"Rate limit (429) on attempt {attempt}",
                            latency_ms=latency_ms,
                        )
                    )
                    # Check cache before retrying
                    if attempt < self.POLYGON_MAX_RETRIES:
                        cached_data, cache_age_hours = self._load_cached_data_with_age(
                            symbol, lookback_days
                        )
                        if cached_data is not None and cache_age_hours is not None:
                            max_age_hours = self.MAX_DATA_AGE_HOURS
                            if cache_age_hours <= max_age_hours:
                                logger.info(
                                    "%s: Using cached Polygon data (%.1f hours old) after 429",
                                    symbol,
                                    cache_age_hours,
                                )
                                result.add_attempt(
                                    FetchAttempt(
                                        source=DataSource.CACHE,
                                        timestamp=time.time(),
                                        success=True,
                                        rows_fetched=len(cached_data),
                                        latency_ms=0.0,
                                    )
                                )
                                return cached_data
                    # Exponential backoff: 30s → 60s → 120s
                    backoff = self.POLYGON_INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.info(
                        "%s: Waiting %.0fs before retry (exponential backoff)",
                        symbol,
                        backoff,
                    )
                    time.sleep(backoff)
                else:
                    # Other HTTP errors - log and continue
                    result.add_attempt(
                        FetchAttempt(
                            source=DataSource.POLYGON,
                            timestamp=time.time(),
                            success=False,
                            error_message=str(exc),
                            latency_ms=latency_ms,
                        )
                    )
                    logger.debug(
                        "%s: Polygon.io attempt %d/%d failed: %s",
                        symbol,
                        attempt,
                        self.POLYGON_MAX_RETRIES,
                        exc,
                    )
                    if attempt < self.POLYGON_MAX_RETRIES:
                        time.sleep(1)  # Brief backoff for non-rate-limit errors
            except Exception as exc:
                latency_ms = (time.time() - start_time) * 1000
                result.add_attempt(
                    FetchAttempt(
                        source=DataSource.POLYGON,
                        timestamp=time.time(),
                        success=False,
                        error_message=str(exc),
                        latency_ms=latency_ms,
                    )
                )
                logger.debug(
                    "%s: Polygon.io attempt %d/%d failed: %s",
                    symbol,
                    attempt,
                    self.POLYGON_MAX_RETRIES,
                    exc,
                )
                if attempt < self.POLYGON_MAX_RETRIES:
                    time.sleep(1)  # Brief backoff

        # Final fallback: check cache one more time
        cached_data, cache_age_hours = self._load_cached_data_with_age(symbol, lookback_days)
        if cached_data is not None and cache_age_hours is not None:
            max_age_hours = self.MAX_DATA_AGE_HOURS
            if cache_age_hours <= max_age_hours:
                logger.info(
                    "%s: Using cached Polygon data (%.1f hours old) after all retries failed",
                    symbol,
                    cache_age_hours,
                )
                result.add_attempt(
                    FetchAttempt(
                        source=DataSource.CACHE,
                        timestamp=time.time(),
                        success=True,
                        rows_fetched=len(cached_data),
                        latency_ms=0.0,
                    )
                )
                return cached_data

        return None

    def _fetch_polygon(self, symbol: str, lookback_days: int) -> pd.DataFrame | None:
        """Fetch market data from Polygon.io API."""
        if not self.polygon_api_key:
            return None

        try:
            # Polygon.io v2 aggregates endpoint
            end_date = datetime.now().date()
            start_date = end_date - timedelta(
                days=lookback_days + self.POLYGON_LOOKBACK_BUFFER_DAYS
            )  # Buffer for weekends/holidays

            # Ensure dates are strings in YYYY-MM-DD format
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}/range/1/day/{start_str}/{end_str}"
            params = {
                "adjusted": "true",
                "sort": "asc",
                "limit": 120,  # Reduced limit to avoid rate limits
                "apiKey": self.polygon_api_key,
            }

            response = self.session.get(url, params=params, timeout=10)
            # Don't handle 429 here - let _fetch_polygon_with_retries handle it with exponential backoff
            response.raise_for_status()

            payload = response.json()

            # Polygon v2 response handling
            status = payload.get("status")
            if status not in ("OK", "DELAYED"):
                if "error" in payload:
                    raise ValueError(f"Polygon.io API error: {payload['error']}")
                elif "results" not in payload:
                    logger.warning(
                        "%s: Polygon.io returned no results (status: %s)",
                        symbol,
                        status,
                    )
                    return None

            results = payload.get("results", [])
            if not results:
                logger.warning(
                    "%s: Polygon.io returned no bars (count: %s)",
                    symbol,
                    payload.get("resultsCount", 0),
                )
                return None

            # Convert Polygon.io format to DataFrame
            records = []
            timestamps = []
            for bar in results:
                # Polygon.io returns: t (timestamp ms), o, h, l, c, v
                dt = datetime.fromtimestamp(bar["t"] / 1000)
                timestamps.append(dt)
                records.append(
                    {
                        "Open": float(bar["o"]),
                        "High": float(bar["h"]),
                        "Low": float(bar["l"]),
                        "Close": float(bar["c"]),
                        "Volume": float(bar.get("v", 0)),
                    }
                )

            if not records:
                return None

            df = pd.DataFrame(records, index=timestamps)
            df.index.name = "Date"
            df = df.sort_index()

            logger.info("%s: Successfully fetched %d bars from Polygon.io", symbol, len(df))
            return df

        except Exception as exc:
            logger.warning("%s: Polygon.io fetch failed: %s", symbol, exc)
            return None

    def _cache_polygon_response(self, symbol: str, data: pd.DataFrame) -> None:
        """Cache successful Polygon response to disk for reuse."""
        try:
            cache_file = self.cache_dir / f"{symbol.upper()}_{datetime.now().date()}.csv"
            data.to_csv(cache_file, index=True)
            logger.debug("%s: Cached Polygon response to %s", symbol, cache_file)
        except Exception as exc:
            logger.debug("%s: Failed to cache Polygon response: %s", symbol, exc)

    def _fetch_alpha_vantage(
        self,
        symbol: str,
        max_total_time: float = 90.0,
        start_time: float | None = None,
    ) -> pd.DataFrame | None:
        """
        Fetch from Alpha Vantage with FAIL-FAST timeout logic.

        CRITICAL FIX: If rate-limited, we FAIL IMMEDIATELY instead of waiting 10+ minutes.
        This prevents GitHub Actions workflow timeouts (20 minute limit).

        Args:
            symbol: Stock symbol to fetch
            max_total_time: Maximum total time to spend (default 90s)
            start_time: Start time for timeout calculation (defaults to now)
        """
        if not self.alpha_vantage_key:
            logger.warning("%s: Alpha Vantage fallback unavailable (missing API key).", symbol)
            return None

        if start_time is None:
            start_time = time.time()

        cache_file = self.cache_dir / f"{symbol.upper()}_{datetime.utcnow().date()}.csv"
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age <= self.CACHE_TTL_SECONDS:
                try:
                    cached_df = pd.read_csv(cache_file, parse_dates=["Date"], index_col="Date")
                    if not cached_df.empty:
                        logger.debug(
                            "%s: Using cached Alpha Vantage data (%.1f hours old)",
                            symbol,
                            age / 3600,
                        )
                        return cached_df
                except Exception as exc:
                    logger.debug("%s: Failed to load cached Alpha Vantage data: %s", symbol, exc)

        # Throttle to respect free-tier rate limits
        def respect_rate_limit(min_interval: float) -> None:
            elapsed = time.time() - self._last_alpha_call_ts
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                # CHECK TIMEOUT BEFORE SLEEPING
                elapsed_total = time.time() - start_time
                if elapsed_total + sleep_time > max_total_time:
                    raise TimeoutError(
                        f"Would exceed max_total_time ({max_total_time}s) waiting for rate limit"
                    )
                logger.debug("Sleeping %.2fs to respect Alpha Vantage rate limit", sleep_time)
                time.sleep(sleep_time)

        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "compact",
            "datatype": "json",
            "apikey": self.alpha_vantage_key,
        }

        for attempt in range(1, self.ALPHAVANTAGE_MAX_RETRIES + 1):
            # CHECK TIMEOUT BEFORE EACH ATTEMPT
            elapsed_total = time.time() - start_time
            if elapsed_total >= max_total_time:
                raise TimeoutError(
                    f"Exceeded max_total_time ({max_total_time}s) after {attempt - 1} attempts"
                )

            respect_rate_limit(self.ALPHAVANTAGE_MIN_INTERVAL_SECONDS)

            try:
                response = self.session.get(
                    "https://www.alphavantage.co/query", params=params, timeout=30
                )
                self._last_alpha_call_ts = time.time()
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.warning(
                    "Alpha Vantage request failed for %s (attempt %s): %s",
                    symbol,
                    attempt,
                    exc,
                )
                continue

            time_series = payload.get("Time Series (Daily)")
            if time_series:
                records = []
                for date_str, values in time_series.items():
                    try:
                        records.append(
                            {
                                "Date": datetime.strptime(date_str, "%Y-%m-%d"),
                                "Open": float(values["1. open"]),
                                "High": float(values["2. high"]),
                                "Low": float(values["3. low"]),
                                "Close": float(values["4. close"]),
                                "Volume": float(values["6. volume"]),
                            }
                        )
                    except Exception as exc:
                        logger.debug(
                            "%s: Skipping Alpha Vantage row %s (%s)",
                            symbol,
                            date_str,
                            exc,
                        )

                if records:
                    df = pd.DataFrame(records).set_index("Date").sort_index()
                    try:
                        df.to_csv(cache_file, index=True)
                    except Exception as exc:
                        logger.debug("%s: Unable to cache Alpha Vantage data: %s", symbol, exc)
                    return df

            # Handle throttling notices - FAIL FAST INSTEAD OF WAITING
            info_message = payload.get("Information") or payload.get("Note")
            if info_message:
                # CRITICAL FIX: If rate-limited, FAIL IMMEDIATELY instead of waiting
                elapsed_total = time.time() - start_time
                if elapsed_total >= max_total_time * 0.8:  # Fail if we've used 80% of time
                    raise TimeoutError(
                        f"Alpha Vantage rate-limited after {elapsed_total:.1f}s. "
                        f"Message: {info_message}. Using cached data instead."
                    )

                # Only wait if we have time remaining (max 30s wait)
                max_wait = min(30.0, max_total_time - elapsed_total - 5)  # Leave 5s buffer
                if max_wait > 0:
                    logger.warning(
                        "%s: Alpha Vantage rate limit hit (attempt %s). Waiting %ss (max %ss). Message: %s",
                        symbol,
                        attempt,
                        max_wait,
                        max_total_time,
                        info_message,
                    )
                    time.sleep(max_wait)
                else:
                    raise TimeoutError(
                        f"Alpha Vantage rate-limited. No time remaining (used {elapsed_total:.1f}s of {max_total_time}s)"
                    )
                continue

            logger.warning(
                "%s: Alpha Vantage response missing time series (keys: %s)",
                symbol,
                list(payload.keys()),
            )
            # Don't sleep on last attempt
            if attempt < self.ALPHAVANTAGE_MAX_RETRIES:
                elapsed_total = time.time() - start_time
                max_wait = min(10.0, max_total_time - elapsed_total - 5)
                if max_wait > 0:
                    time.sleep(max_wait)
                else:
                    raise TimeoutError(f"No time remaining for retry (used {elapsed_total:.1f}s)")

        return None

    def _load_cached_data(self, symbol: str, lookback_days: int) -> pd.DataFrame | None:
        """Load cached data from disk as last resort fallback (legacy method)."""
        data, _ = self._load_cached_data_with_age(symbol, lookback_days)
        return data

    def _load_cached_data_with_age(
        self, symbol: str, lookback_days: int
    ) -> tuple[pd.DataFrame | None, float | None]:
        """Load cached data from disk with age information."""
        try:
            # Check cache directory for any recent data
            cache_pattern = self.cache_dir / f"{symbol.upper()}_*.csv"
            import glob

            cache_files = glob.glob(str(cache_pattern))

            if not cache_files:
                return None, None

            # Get most recent cache file
            cache_files.sort(key=lambda f: Path(f).stat().st_mtime, reverse=True)
            latest_cache = Path(cache_files[0])

            # Check age (use if < configured max age)
            age_hours = (time.time() - latest_cache.stat().st_mtime) / 3600
            max_age_hours = self.CACHE_MAX_AGE_DAYS * 24
            if age_hours > max_age_hours:
                logger.debug(
                    "%s: Cached data too old (%.1f hours > %d hours)",
                    symbol,
                    age_hours,
                    max_age_hours,
                )
                return None, None

            # Load cached data
            cached_df = pd.read_csv(latest_cache, parse_dates=["Date"], index_col="Date")
            if not cached_df.empty and len(cached_df) >= lookback_days * 0.5:
                logger.info(
                    "%s: Loaded %d rows from cache (%.1f hours old)",
                    symbol,
                    len(cached_df),
                    age_hours,
                )
                return cached_df.tail(lookback_days), age_hours

        except Exception as exc:
            logger.debug("%s: Failed to load cached data: %s", symbol, exc)

        return None, None

    @staticmethod
    def _is_valid(data: pd.DataFrame | None, lookback_days: int) -> bool:
        if data is None or data.empty:
            return False
        # Relaxed validation: Accept if we have substantial data (at least 20 rows)
        # This allows partial data from free-tier APIs (e.g. Polygon 120 days limit)
        # while still rejecting empty/broken responses.
        return len(data.index.unique()) >= min(lookback_days, 20)

    @staticmethod
    def _prepare(data: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
        df = data.copy().rename(
            columns={
                "Adj Close": "Adj Close",
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Volume": "Volume",
            }
        )
        # Ensure index is datetime and unique
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df = df[~df.index.duplicated(keep="last")].sort_index()
        return df.tail(lookback_days)


def get_market_data_provider() -> MarketDataProvider:
    """Convenience singleton-style accessor."""
    if not hasattr(get_market_data_provider, "_instance"):
        get_market_data_provider._instance = MarketDataProvider()  # type: ignore[attr-defined]
    return get_market_data_provider._instance  # type: ignore[attr-defined]
