"""
Shared Alpaca API Client Utility

This module provides a centralized way to create Alpaca trading clients,
avoiding code duplication across scripts.

Created: Jan 8, 2026
Reason: DRY violation - get_alpaca_client() was duplicated in 5+ scripts

Updated: Jan 12, 2026
- Added get_alpaca_credentials() to prioritize $5K paper account
- All code must use get_alpaca_credentials() for API key access
"""

import logging
import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import find_dotenv, load_dotenv
except ImportError:  # pragma: no cover - dotenv is present in runtime dependencies
    find_dotenv = None
    load_dotenv = None

logger = logging.getLogger(__name__)
_ENV_BOOTSTRAPPED = False


def _iter_local_env_files(repo_root: Path) -> list[Path]:
    """Return candidate local dotenv files, including the primary repo from a worktree."""
    candidates: list[Path] = []

    for filename in (".env", ".env.local"):
        env_path = find_dotenv(filename=filename, usecwd=True) if find_dotenv else ""
        if env_path:
            candidates.append(Path(env_path))

    for filename in (".env", ".env.local"):
        candidates.append(repo_root / filename)

    if repo_root.parent.name == ".worktrees":
        primary_repo_root = repo_root.parent.parent
        for filename in (".env", ".env.local"):
            candidates.append(primary_repo_root / filename)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.exists():
            continue
        deduped.append(candidate)
        seen.add(candidate)
    return deduped


def _bootstrap_env_from_dotenv() -> None:
    """
    Load local dotenv files once so credential lookup works in local shells too.

    This keeps CI behavior unchanged because repository/workflow env vars already
    exist and `override=False` never replaces an existing exported value.
    """
    global _ENV_BOOTSTRAPPED
    if _ENV_BOOTSTRAPPED:
        return
    _ENV_BOOTSTRAPPED = True

    if load_dotenv is None or find_dotenv is None:
        return

    repo_root = Path(__file__).resolve().parents[2]
    loaded_any = False
    for env_file in _iter_local_env_files(repo_root):
        loaded_any = load_dotenv(env_file, override=False) or loaded_any

    if loaded_any:
        logger.info("Loaded local dotenv file(s) for Alpaca credential discovery")


def get_alpaca_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Get Alpaca API credentials with proper priority (paper trading).

    Priority order (first found wins) - UPDATED Jan 30, 2026:
    1. ALPACA_PAPER_TRADING_API_KEY / SECRET ($100K account - PRIMARY)
    2. ALPACA_API_KEY / ALPACA_SECRET_KEY (workflow fallback)

    NOTE: The $5K/$30K accounts are deprecated. Use $100K account only.
    $100K account = No PDT restrictions, faster path to North Star.

    Returns:
        Tuple of (api_key, secret_key) or (None, None) if not found.
    """
    _bootstrap_env_from_dotenv()

    env_vars_checked = [
        ("ALPACA_PAPER_TRADING_API_KEY", os.getenv("ALPACA_PAPER_TRADING_API_KEY")),
        ("ALPACA_API_KEY", os.getenv("ALPACA_API_KEY")),
    ]

    logger.info("Credential lookup (checking env vars):")
    for var_name, var_val in env_vars_checked:
        if var_val:
            logger.info(f"  ✅ {var_name}: SET (length={len(var_val)})")
        else:
            logger.info(f"  ❌ {var_name}: NOT SET")

    # $100K account is PRIMARY (Jan 30, 2026 decision)
    api_key = os.getenv("ALPACA_PAPER_TRADING_API_KEY") or os.getenv(  # $100K account - PRIMARY
        "ALPACA_API_KEY"
    )  # Workflow fallback
    secret_key = os.getenv(
        "ALPACA_PAPER_TRADING_API_SECRET"
    ) or os.getenv(  # $100K account - PRIMARY
        "ALPACA_SECRET_KEY"
    )  # Workflow fallback

    if api_key:
        if os.getenv("ALPACA_PAPER_TRADING_API_KEY"):
            logger.info("Selected: ALPACA_PAPER_TRADING_API_KEY ($100K account)")
        elif os.getenv("ALPACA_API_KEY"):
            logger.info("Selected: ALPACA_API_KEY fallback")
    else:
        logger.error("NO API KEY FOUND - all env vars are empty!")

    if not secret_key:
        logger.error("NO SECRET KEY FOUND - all secret env vars are empty!")

    return api_key, secret_key


def get_brokerage_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Get Alpaca BROKERAGE (live) API credentials.

    Uses ALPACA_BROKERAGE_TRADING_API_KEY/SECRET for real money trading.

    Returns:
        Tuple of (api_key, secret_key) or (None, None) if not found.
    """
    _bootstrap_env_from_dotenv()

    api_key = os.getenv("ALPACA_BROKERAGE_TRADING_API_KEY")
    secret_key = os.getenv("ALPACA_BROKERAGE_TRADING_API_SECRET")

    if api_key:
        logger.info("Using BROKERAGE (live) trading credentials")
    else:
        logger.warning("Brokerage credentials not found - set ALPACA_BROKERAGE_TRADING_API_KEY")

    return api_key, secret_key


def get_brokerage_client():
    """
    Get Alpaca BROKERAGE (live money) trading client.

    WARNING: This uses real money! Only for actual trading.

    Returns:
        TradingClient instance for live trading or None if creation fails.
    """
    try:
        from alpaca.trading.client import TradingClient

        api_key, secret_key = get_brokerage_credentials()

        if not api_key or not secret_key:
            logger.error("Brokerage credentials not found. Set ALPACA_BROKERAGE_TRADING_API_KEY")
            return None

        return TradingClient(api_key, secret_key, paper=False)
    except ImportError:
        logger.error("alpaca-py not installed. Add to requirements.txt")
        return None
    except Exception as e:
        logger.error(f"Failed to create brokerage client: {e}")
        return None


def get_alpaca_client(paper: bool = True):
    """
    Get Alpaca trading client.

    Args:
        paper: If True (default), use paper trading. Set to False for live trading.
               Note: Live trading requires explicit confirmation and is dangerous.

    Returns:
        TradingClient instance or None if creation fails.

    Environment variables required:
        - ALPACA_API_KEY: Your Alpaca API key
        - ALPACA_SECRET_KEY: Your Alpaca secret key
    """
    try:
        from alpaca.trading.client import TradingClient

        api_key, secret_key = get_alpaca_credentials()

        if not api_key or not secret_key:
            logger.error(
                "Alpaca credentials not found. Set ALPACA_PAPER_TRADING_5K_API_KEY or ALPACA_API_KEY"
            )
            return None

        return TradingClient(api_key, secret_key, paper=paper)
    except ImportError:
        logger.error("alpaca-py not installed. Add to requirements.txt")
        return None
    except Exception as e:
        logger.error(f"Failed to create Alpaca client: {e}")
        return None


# Private alias. External callers must use ``get_guarded_trading_client``;
# the unsafe factory is preserved only for use inside this module and the
# safety layer (which performs its own gate enforcement).
_get_alpaca_client_unsafe = get_alpaca_client


def get_guarded_trading_client(paper: bool = True):
    """
    Get an Alpaca TradingClient whose ``submit_order`` is forced through
    ``safe_submit_order`` → ``validate_trade_mandatory``.

    This is the ONLY supported way for scripts and workflows to acquire a
    TradingClient. The raw ``submit_order`` from alpaca-py bypasses every
    risk gate (position sizing, max-concurrent-IC, ticker whitelist, daily
    loss cap, etc.). On May 19, 2026 a 50-lot SPY 2026-06-18 iron condor
    was opened by direct ``client.submit_order(...)`` calls in three GitHub
    workflows — far above the 5%-per-trade cap. This factory closes that gap
    at the runtime level: even if a script calls ``submit_order`` directly,
    the patched method routes through the mandatory trade gate first.

    Args:
        paper: If True (default), use paper trading. Live trading requires
            explicit confirmation upstream.

    Returns:
        TradingClient with monkey-patched ``submit_order`` or None if
        creation fails.

    Raises (on a later submit_order call):
        ValueError / TradeBlockedError if the gate rejects the order.
    """
    client = _get_alpaca_client_unsafe(paper=paper)
    if client is None:
        return None

    # Late import to avoid a circular import at module load time.
    from src.safety.mandatory_trade_gate import safe_submit_order

    original_submit_order = client.submit_order

    def _guarded_submit_order(order_request, *args, strategy: str | None = None, **kwargs):
        """Patched submit_order: routes every call through the mandatory gate.

        Positional/keyword args after ``order_request`` are not forwarded to
        ``safe_submit_order`` (it does not accept them); they are kept in the
        signature only so callers that incorrectly pass extras get a clear
        TypeError instead of a silent bypass.
        """
        if args or kwargs:
            raise TypeError(
                "guarded submit_order only accepts (order_request, strategy=...); "
                f"received extra args={args!r} kwargs={kwargs!r}. Refusing to bypass the gate."
            )
        # Temporarily restore the original so safe_submit_order's internal
        # call to client.submit_order() does not recurse into the guard.
        client.submit_order = original_submit_order
        try:
            return safe_submit_order(client, order_request, strategy=strategy)
        finally:
            client.submit_order = _guarded_submit_order

    client.submit_order = _guarded_submit_order
    return client


def get_options_client(paper: bool = True):
    """
    Get Alpaca options client.

    Note: Options trading uses the same TradingClient as equities in alpaca-py.
    This function is provided for semantic clarity.

    Args:
        paper: If True (default), use paper trading.

    Returns:
        TradingClient instance or None if creation fails.
    """
    return get_alpaca_client(paper=paper)


def get_options_data_client():
    """
    Get Alpaca options historical data client.

    Used for fetching options chain data, IV, greeks, etc.

    Returns:
        OptionHistoricalDataClient instance or None if creation fails.
    """
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient

        api_key, secret_key = get_alpaca_credentials()

        if not api_key or not secret_key:
            logger.error("Alpaca credentials not found for options data client")
            return None

        return OptionHistoricalDataClient(api_key, secret_key)
    except ImportError:
        logger.error("alpaca-py not installed. Add to requirements.txt")
        return None
    except Exception as e:
        logger.error(f"Failed to create options data client: {e}")
        return None


def get_account_info(client) -> Optional[dict]:
    """
    Get account information from Alpaca.

    Args:
        client: TradingClient instance from get_alpaca_client()

    Returns:
        Dictionary with equity, cash, buying_power or None on failure.
    """
    if client is None:
        return None

    try:
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
        }
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        return None
