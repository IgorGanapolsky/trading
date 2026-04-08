"""
RAG Webhook for Trading RAG System.

This webhook serves RAG search and trade history queries for internal clients.
Returns full, untruncated lessons learned AND trade history from our RAG knowledge base.

Version History:
- v2.9.0 Jan 10, 2026: Security - SSL verification, rate limiting, webhook auth
- v3.0.0 Jan 12, 2026: LanceDB RAG integration - semantic search with fallback
- v3.1.0 Jan 13, 2026: Fix analytical queries - WHY questions route to RAG not status
- v3.2.0 Jan 13, 2026: Add CI status check to readiness assessment (CEO directive)
- v3.3.0 Jan 13, 2026: Fix direct P/L queries - conversational "How much money" answers
- v3.4.0 Jan 14, 2026: Fix stale P/L data - use GitHub API instead of raw URL (bypass CDN cache)
- v3.5.0 Jan 15, 2026: Query Alpaca API DIRECTLY for real-time P/L (fixes stale data issue)
- v3.5.1 Jan 16, 2026: Force redeployment to ensure Alpaca credentials are loaded
- v3.5.2 Jan 16, 2026: Fix LanceDB RAG init
- v3.7.0 Jan 16, 2026: Fix trades_loaded=0 - check system_state.json for trade_history
- v3.9.0 Jan 16, 2026: Fix trade data source priority - system_state.json FIRST (Alpaca source of truth)

Architecture (v3.0.0):
- Primary: LanceDB local semantic search
- Fallback: Keyword-based search

CEO Directive: "I want to be able to ask about my trades and get accurate information"
requires semantic search.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import ssl
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Rate limiting (optional - graceful degradation if not installed)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    RATE_LIMITING_ENABLED = True
except ImportError:
    RATE_LIMITING_ENABLED = False

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.sync_alpaca_state import _derive_trade_summary_from_fills  # noqa: E402
from src.rag.lessons_learned_rag import LessonsLearnedRAG  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# AI disclosure required for high-risk (finance) domain usage.
AI_DISCLOSURE_TEXT = "AI Disclosure: This interface uses AI to search and summarize internal lessons. Not financial advice. Human review required for any trading decisions."

# Webhook authentication token (set in Cloud Run environment)
WEBHOOK_AUTH_TOKEN = os.environ.get("RAG_WEBHOOK_TOKEN", "")

# Initialize FastAPI app
app = FastAPI(
    title="Trading AI RAG Webhook",
    description="RAG Webhook for lessons AND trade history queries",
    version="3.9.0",  # Fix trade data source priority - system_state.json first
)

# Allow browser clients (GitHub Pages / local dev) to call /rag-search directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize rate limiter if available
if RATE_LIMITING_ENABLED:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting ENABLED (slowapi)")

    def rate_limit(limit_string: str):
        """Apply rate limit decorator when slowapi is available."""
        return limiter.limit(limit_string)

else:
    limiter = None
    logger.warning("Rate limiting DISABLED (slowapi not installed)")

    def rate_limit(limit_string: str):
        """No-op decorator when slowapi is not available."""

        def decorator(func):
            return func

        return decorator


local_rag: Optional[LessonsLearnedRAG] = None


def get_local_rag() -> LessonsLearnedRAG:
    """Lazy-init RAG to avoid import-time side effects in CI/tests."""
    global local_rag
    if local_rag is None:
        local_rag = LessonsLearnedRAG()
        logger.info(
            "RAG initialized with %s lessons (LanceDB-first, keyword fallback)",
            len(local_rag.lessons),
        )
    return local_rag


def query_rag_hybrid(query: str, top_k: int = 5) -> tuple[list, str]:
    """
    Query RAG using LanceDB-first retrieval with keyword fallback.

    Returns:
        Tuple of (results_list, source_name)
    """
    rag = get_local_rag()
    results = rag.query(query, top_k=top_k)
    source = rag.last_source or "keyword"
    logger.info(f"RAG returned {len(results)} results (source={source})")
    return results, source


def format_rag_response(results: list, query: str, source: str) -> str:
    """Format RAG results into response text."""
    if not results:
        return (
            f"No lessons found matching '{query}'. "
            "Try searching for: trading, risk, CI, RAG, verification, or operational."
        )

    response_parts = []
    header = (
        "Based on our semantic index (LanceDB):\n"
        if source == "lancedb"
        else "Based on our keyword index:\n"
    )
    response_parts.append(header)

    for lesson in results:
        lesson_id = lesson.get("id", "unknown")
        severity = lesson.get("severity", "UNKNOWN")
        content = lesson.get("content", lesson.get("snippet", ""))
        response_parts.append(f"\n**{lesson_id}** ({severity}): {content}\n")
        response_parts.append("-" * 50)

    return "\n".join(response_parts)


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return default


def _format_signed_dollars(amount: float) -> str:
    if amount > 0:
        return f"+${amount:,.2f}"
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return "$0.00"


def _format_no_trade_today_pl(paper: dict, actual_today: str) -> str:
    """Format a 'no trades today' P/L line that still explains mark-to-market drift."""
    daily_change = _coerce_float(paper.get("daily_change", 0.0))
    positions_count = int(paper.get("positions_count", 0) or 0)

    if abs(daily_change) < 0.005:
        return f"**Today ({actual_today}):** No trades executed; mark-to-market is flat so far"

    drift_label = "mark-to-market" if positions_count > 0 else "equity drift"
    positions_hint = f" across {positions_count} open position(s)" if positions_count > 0 else ""
    return (
        f"**Today ({actual_today}):** No trades executed; "
        f"{drift_label} {_format_signed_dollars(daily_change)}{positions_hint}"
    )


@app.post("/rag-search")
async def rag_search(request: Request):
    """Lightweight RAG search endpoint for UI/worker use."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    query = (payload.get("query") or payload.get("message") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query required")

    try:
        top_k = int(payload.get("top_k", 5))
    except Exception:
        top_k = 5
    top_k = max(1, min(top_k, 10))

    results, source = query_rag_hybrid(query, top_k=top_k)
    trimmed = []
    for r in results:
        content = r.get("content") or r.get("snippet") or ""
        trimmed.append(
            {
                "id": r.get("id"),
                "title": r.get("title") or r.get("id"),
                "severity": r.get("severity", "MEDIUM"),
                "summary": content[:300],
                "content": content[:2000],
                "context_score": r.get("context_score"),
                "file": r.get("file"),
            }
        )

    return {
        "query": query,
        "source": source,
        "ai_disclosure": AI_DISCLOSURE_TEXT,
        "results": trimmed,
    }


def query_alpaca_api_direct() -> Optional[dict]:
    """
    Query Alpaca API directly for REAL-TIME portfolio data.

    FIX Jan 15, 2026: RAG Webhook was showing stale data from cached files.
    This function queries Alpaca directly for accurate, real-time data.

    Returns:
        dict with account data or None if API unavailable
    """
    import json
    import urllib.request

    # Get Alpaca credentials using the standard priority chain.
    try:
        from src.utils.alpaca_client import get_alpaca_credentials

        api_key, api_secret = get_alpaca_credentials()
    except ImportError:
        # Fallback if import fails - try the current paper-trading env vars.
        api_key = os.environ.get("ALPACA_PAPER_TRADING_API_KEY", "") or os.environ.get(
            "ALPACA_API_KEY", ""
        )
        api_secret = os.environ.get("ALPACA_PAPER_TRADING_API_SECRET", "") or os.environ.get(
            "ALPACA_SECRET_KEY", ""
        )

    if not api_key or not api_secret:
        logger.warning(
            f"Alpaca API credentials not available in environment. "
            f"API_KEY present: {bool(api_key)}, API_SECRET present: {bool(api_secret)}. "
            f"Env vars: {[k for k in os.environ if 'ALPACA' in k]}"
        )
        return None

    try:
        # Query Alpaca account endpoint
        account_url = "https://paper-api.alpaca.markets/v2/account"
        req = urllib.request.Request(
            account_url,
            headers={
                "accept": "application/json",
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            },
        )
        ssl_context = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            account = json.loads(response.read().decode("utf-8"))

        # Query positions
        positions_url = "https://paper-api.alpaca.markets/v2/positions"
        req = urllib.request.Request(
            positions_url,
            headers={
                "accept": "application/json",
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            },
        )
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            positions = json.loads(response.read().decode("utf-8"))

        # Query today's fills
        from datetime import datetime

        try:
            from zoneinfo import ZoneInfo

            today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        except ImportError:
            from datetime import timezone

            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        activities_url = (
            f"https://paper-api.alpaca.markets/v2/account/activities/FILL?date={today_str}"
        )
        req = urllib.request.Request(
            activities_url,
            headers={
                "accept": "application/json",
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            },
        )
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            activities = json.loads(response.read().decode("utf-8"))

        equity = float(account.get("equity", 0))
        last_equity = float(account.get("last_equity", 0))
        daily_change = equity - last_equity

        logger.info(
            f"✅ Alpaca API: equity=${equity:.2f}, daily_change=${daily_change:.2f}, fills={len(activities)}"
        )

        return {
            "equity": equity,
            "cash": float(account.get("cash", 0)),
            "buying_power": float(account.get("buying_power", 0)),
            "last_equity": last_equity,
            "daily_change": daily_change,
            "positions_count": len(positions),
            "positions": positions,
            "trades_today": len(activities),
            "activities": activities,
            "queried_at": datetime.now().astimezone().isoformat(),
            "source": "alpaca_api_direct",
        }

    except Exception as e:
        logger.warning(f"Alpaca API query failed: {e}")
        return None


def _load_cached_system_state() -> dict:
    """Load the canonical cached state from disk, then GitHub as fallback."""
    import base64
    import json
    import urllib.request

    state = None
    state_path = project_root / "data" / "system_state.json"

    try:
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)
            logger.info("Loaded portfolio from local system_state.json")
    except Exception as e:
        logger.warning(f"Failed to read local system state: {e}")

    if state:
        return state

    try:
        github_url = (
            "https://api.github.com/repos/IgorGanapolsky/trading/contents/data/system_state.json"
        )
        req = urllib.request.Request(
            github_url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "TradingBot/1.0",
            },
        )
        ssl_context = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
            api_response = json.loads(response.read().decode("utf-8"))
            content_b64 = api_response.get("content", "")
            content = base64.b64decode(content_b64).decode("utf-8")
            state = json.loads(content)
        logger.info("Loaded portfolio from GitHub API fallback")
    except Exception as e:
        logger.warning(f"Failed to fetch cached system state from GitHub API: {e}")

    return state or {}


def _map_alpaca_positions_to_state_shapes(
    raw_positions: list[dict],
) -> tuple[list[dict], list[dict], float]:
    """Normalize Alpaca REST position payloads into dashboard/state shapes."""
    top_level_positions: list[dict] = []
    performance_positions: list[dict] = []
    total_unrealized = 0.0

    for position in raw_positions:
        if not isinstance(position, dict):
            continue

        qty = _coerce_float(position.get("qty"), 0.0)
        entry_price = _coerce_float(position.get("avg_entry_price"), 0.0) * 100.0
        current_price = _coerce_float(position.get("current_price"), 0.0) * 100.0
        market_value = _coerce_float(position.get("market_value"), 0.0)
        unrealized_pl = _coerce_float(position.get("unrealized_pl"), 0.0)
        unrealized_pl_pct = _coerce_float(position.get("unrealized_plpc"), 0.0)
        side_raw = str(position.get("side") or "")
        side = "short" if qty < 0 or side_raw.upper().endswith("SHORT") else "long"
        symbol = str(position.get("symbol") or "")

        total_unrealized += unrealized_pl
        top_level_positions.append(
            {
                "symbol": symbol,
                "qty": qty,
                "price": current_price,
                "value": market_value,
                "pnl": unrealized_pl,
                "type": "option",
            }
        )
        performance_positions.append(
            {
                "symbol": symbol,
                "quantity": qty,
                "entry_price": entry_price,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pl": unrealized_pl,
                "unrealized_pl_pct": unrealized_pl_pct,
                "side": side,
            }
        )

    return top_level_positions, performance_positions, round(total_unrealized, 2)


def _calculate_challenge_day(start_date_raw: str | None = None) -> int:
    """Calculate the current challenge day from start date.

    Defaults to the current paper-trading start date when available.
    Only counts trading days (Mon-Fri, excluding holidays).
    """
    from datetime import date

    try:
        start_date = (
            date.fromisoformat(str(start_date_raw)) if start_date_raw else date(2026, 1, 30)
        )
    except ValueError:
        start_date = date(2026, 1, 30)
    today = date.today()

    # Count trading days (simplified - just weekdays)
    trading_days = 0
    current = start_date
    while current <= today:
        if current.weekday() < 5:  # Mon-Fri
            trading_days += 1
        current = current + __import__("datetime").timedelta(days=1)

    return min(trading_days, 90)  # Cap at 90-day challenge


def build_live_system_state_snapshot() -> dict:
    """Return a system-state-shaped snapshot with live Alpaca paper data overlaid when available."""
    from datetime import datetime, timezone

    try:
        from zoneinfo import ZoneInfo

        today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except ImportError:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cached_state = _load_cached_system_state()
    has_cached_state = bool(cached_state)
    if not cached_state:
        cached_state = {}

    state = copy.deepcopy(cached_state)
    state.setdefault("portfolio", {})
    state.setdefault("paper_account", {})
    state.setdefault("live_account", {})
    state.setdefault("account", {})
    state.setdefault("meta", {})
    state.setdefault("risk", {})
    state.setdefault("performance", {})
    state.setdefault("trades", {})
    state.setdefault("paper_trading", {})
    state.setdefault("positions", [])

    alpaca_data = query_alpaca_api_direct()
    if not alpaca_data:
        if not has_cached_state:
            return {}
        state["actual_today"] = today_str
        state["status_source"] = "cached_system_state"
        state["meta"]["portfolio_status_source"] = "cached_system_state"
        return state

    paper = state["paper_account"]
    portfolio = state["portfolio"]
    account = state["account"]
    live = state["live_account"]
    meta = state["meta"]
    risk = state["risk"]
    performance = state["performance"]
    trades = state["trades"]
    paper_trading = state["paper_trading"]

    starting_balance = _coerce_float(paper.get("starting_balance"), 100000.0) or 100000.0
    top_positions, performance_positions, total_unrealized = _map_alpaca_positions_to_state_shapes(
        alpaca_data.get("positions") or []
    )

    equity = _coerce_float(alpaca_data.get("equity"))
    cash = _coerce_float(alpaca_data.get("cash"))
    buying_power = _coerce_float(alpaca_data.get("buying_power"))
    last_equity = _coerce_float(alpaca_data.get("last_equity"))
    daily_change = _coerce_float(alpaca_data.get("daily_change"))
    queried_at = str(alpaca_data.get("queried_at") or datetime.now(timezone.utc).isoformat())
    total_pl = equity - starting_balance
    total_pl_pct = (total_pl / starting_balance * 100.0) if starting_balance > 0 else 0.0

    portfolio["equity"] = equity
    portfolio["cash"] = cash

    paper["equity"] = equity
    paper["current_equity"] = equity
    paper["cash"] = cash
    paper["buying_power"] = buying_power
    paper["last_equity"] = last_equity
    paper["daily_change"] = round(daily_change, 2)
    paper["starting_balance"] = starting_balance
    paper["total_pl"] = total_pl
    paper["total_pl_pct"] = total_pl_pct
    paper["positions_count"] = len(top_positions)
    paper["synced_at"] = queried_at

    account["current_equity"] = equity
    account["equity"] = equity
    account["cash"] = cash
    account["buying_power"] = buying_power
    account["positions_count"] = len(top_positions)
    account["total_pl"] = total_pl
    account["total_pl_pct"] = total_pl_pct

    state["positions"] = top_positions
    performance["open_positions"] = performance_positions
    risk["unrealized_pl"] = total_unrealized
    risk["total_pl"] = total_pl

    trades["today_trades"] = int(alpaca_data.get("trades_today") or 0)
    trades["total_trades_today"] = int(alpaca_data.get("trades_today") or 0)
    if trades["today_trades"] > 0:
        trades["last_trade_date"] = today_str

    live.setdefault("equity", _coerce_float(live.get("equity")))
    live.setdefault("current_equity", _coerce_float(live.get("current_equity")))

    paper_trading["current_day"] = _calculate_challenge_day(paper_trading.get("start_date"))

    state["last_updated"] = queried_at
    meta["last_updated"] = queried_at
    meta["last_sync"] = queried_at
    meta["portfolio_status_source"] = "alpaca_api_direct"
    meta["live_query_at"] = queried_at
    state["actual_today"] = today_str
    state["status_source"] = "alpaca_api_direct"
    return state


def get_current_portfolio_status() -> dict:
    """Get current portfolio status - PREFER Alpaca API, fallback to cached files."""
    from datetime import datetime, timezone

    state = build_live_system_state_snapshot()
    if not state:
        return {}

    # Get actual today's date (US Eastern for market hours)
    try:
        from zoneinfo import ZoneInfo

        today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except ImportError:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build canonical activity from fills, not state["trades"] summary fields.
    # state["trades"] can become stale while trade_history is newer.
    canonical_activity = []
    seen_fill_keys = set()

    def _add_fill_activity(trade: dict) -> None:
        filled_at = trade.get("filled_at") or trade.get("timestamp")
        if not filled_at:
            return
        fill_key = (
            str(trade.get("id") or trade.get("order_id") or ""),
            str(filled_at),
            str(trade.get("symbol") or ""),
            str(trade.get("side") or ""),
            str(trade.get("qty") or ""),
            str(trade.get("price") or ""),
        )
        if fill_key in seen_fill_keys:
            return
        seen_fill_keys.add(fill_key)
        canonical_activity.append({"filled_at": str(filled_at), **trade})

    trade_history = state.get("trade_history", [])
    if isinstance(trade_history, list):
        for trade in trade_history:
            if not isinstance(trade, dict):
                continue
            _add_fill_activity(trade)

    # Include legacy/local trade file activity as fallback evidence.
    data_dir = project_root / "data"
    for trades_file in sorted(data_dir.glob("trades_*.json"), reverse=True):
        try:
            with open(trades_file) as f:
                file_trades = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read {trades_file}: {e}")
            continue
        if not isinstance(file_trades, list):
            continue
        for trade in file_trades:
            if not isinstance(trade, dict):
                continue
            _add_fill_activity(trade)

    trade_summary = _derive_trade_summary_from_fills(canonical_activity)
    last_trade_date = trade_summary.get("last_trade_date") or "unknown"
    trades_today = int(trade_summary.get("today_trades") or 0)

    return {
        "live": {
            # FIX Jan 16, 2026: system_state.json uses "current_equity" not "equity"
            # Schema: account.current_equity, account.total_pl, account.total_pl_pct
            "equity": state.get("account", {}).get("current_equity", 0)
            or state.get("account", {}).get("equity", 0)
            or state.get("portfolio", {}).get("equity", 0),
            "total_pl": state.get("account", {}).get("total_pl", 0),
            "total_pl_pct": state.get("account", {}).get("total_pl_pct", 0),
            "positions_count": state.get("account", {}).get("positions_count", 0),
        },
        "paper": {
            # FIX Jan 12, 2026: system_state.json uses "equity" not "current_equity"
            "equity": state.get("paper_account", {}).get("equity", 0)
            or state.get("paper_account", {}).get("cash", 0),
            "total_pl": state.get("paper_account", {}).get("total_pl", 0),
            "total_pl_pct": state.get("paper_account", {}).get("total_pl_pct", 0),
            "positions_count": state.get("paper_account", {}).get("positions_count", 0),
            "win_rate": state.get("paper_account", {}).get("win_rate", 0),
            # FIX Jan 13, 2026: Add daily_change for "today" questions
            "daily_change": state.get("paper_account", {}).get("daily_change", 0),
        },
        "last_trade_date": last_trade_date,
        "trades_today": trades_today,
        "actual_today": today_str,
        # FIX: state.challenge.current_day doesn't exist - calculate dynamically
        "challenge_day": _calculate_challenge_day(state.get("paper_trading", {}).get("start_date")),
        "source": state.get("status_source", "cached_system_state"),
    }


def check_ci_status() -> dict:
    """
    Check GitHub Actions CI status for the main branch.

    Returns:
        dict with:
        - is_passing: True if CI is passing
        - failed_workflows: List of failed workflow names
        - running_workflows: List of running workflow names
        - error: Error message if API call failed
    """
    import json
    import urllib.request

    result = {
        "is_passing": True,
        "failed_workflows": [],
        "running_workflows": [],
        "error": None,
    }

    try:
        # Use GitHub API to check workflow runs (no auth needed for public repos)
        url = "https://api.github.com/repos/IgorGanapolsky/trading/actions/runs?branch=main&per_page=10"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "TradingBot/1.0",
            },
        )
        ssl_context = ssl.create_default_context()

        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Check recent workflow runs
        seen_workflows = set()
        for run in data.get("workflow_runs", []):
            workflow_name = run.get("name", "unknown")

            # Only check each workflow once (most recent run)
            if workflow_name in seen_workflows:
                continue
            seen_workflows.add(workflow_name)

            conclusion = run.get("conclusion")
            status = run.get("status")

            if status == "in_progress" or status == "queued":
                result["running_workflows"].append(workflow_name)
            elif conclusion == "failure":
                result["is_passing"] = False
                result["failed_workflows"].append(workflow_name)

        logger.info(
            f"CI check: passing={result['is_passing']}, failed={result['failed_workflows']}"
        )

    except Exception as e:
        logger.warning(f"CI status check failed: {e}")
        result["error"] = "CI status temporarily unavailable"

    return result


def is_readiness_query(query: str) -> bool:
    """Detect if query is asking about trading readiness assessment."""
    readiness_keywords = [
        "ready",
        "readiness",
        "prepared",
        "preparation",
        "should we trade",
        "can we trade",
        "safe to trade",
        "good to trade",
        "green light",
        "go ahead",
        "status check",
        "pre-trade",
        "preflight",
        "checklist",
    ]
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in readiness_keywords)


def parse_readiness_context(query: str) -> dict:
    """
    Parse the query to understand context for readiness assessment.

    Returns dict with:
    - is_future: True if asking about tomorrow/future trading
    - is_paper: True if asking about paper trading specifically
    - is_live: True if asking about live trading specifically
    """
    query_lower = query.lower()

    # Detect future-oriented queries
    future_keywords = ["tomorrow", "next", "upcoming", "future", "will we", "later"]
    is_future = any(kw in query_lower for kw in future_keywords)

    # Detect paper trading context
    paper_keywords = ["paper", "simulation", "simulated", "test", "demo", "practice"]
    is_paper = any(kw in query_lower for kw in paper_keywords)

    # Detect live trading context
    live_keywords = ["live", "real", "actual", "production", "real money"]
    is_live = any(kw in query_lower for kw in live_keywords)

    # If neither specified, default based on current capital strategy
    # (We're in paper trading phase with $30 live capital)
    if not is_paper and not is_live:
        is_paper = True  # Default to paper since that's our current mode

    return {
        "is_future": is_future,
        "is_paper": is_paper,
        "is_live": is_live,
    }


def is_analytical_query(query: str) -> bool:
    """
    Detect if query is asking for analysis/explanation (WHY questions).

    These should be routed to RAG for semantic understanding, not simple
    status lookups. Examples:
    - "Why did we not make money yesterday?"
    - "How come we lost on that trade?"
    - "Explain what went wrong with paper trades"
    - "What happened to our profits?"
    """
    import re

    analytical_keywords = [
        r"\bwhy\b",
        r"\bhow come\b",
        r"\bexplain\b",
        r"\bwhat happened\b",
        r"\bwhat went wrong\b",
        r"\breason\b",
        r"\bcause\b",
        r"\banalyze\b",
        r"\banalysis\b",
        r"\bunderstand\b",
        r"\bin detail\b",
        r"\btell me about\b",
    ]
    query_lower = query.lower()
    return any(re.search(pattern, query_lower) for pattern in analytical_keywords)


def is_direct_pl_query(query: str) -> bool:
    """
    Detect if query is asking for a DIRECT P/L answer (not a full status dump).

    These questions expect a conversational answer like "You made $X today"
    instead of a portfolio status dump.

    Examples:
    - "How much money we made today?"
    - "How much did we make?"
    - "What's our profit today?"
    - "Did we make money?"
    - "How are we doing today?"
    """
    import re

    # Patterns for direct P/L questions
    direct_pl_patterns = [
        r"\bhow much.{0,20}(money|profit|made|make|earn)",
        r"\bhow much did we (make|earn|profit|lose)",
        r"\bwhat('s| is| did).{0,15}(our|the|my).{0,10}(profit|loss|p/?l|pnl)",
        r"\bdid we (make|lose|earn).{0,10}(money|profit)?",
        r"\bhow are we doing",
        r"\bwhat did we (make|earn|lose)",
        r"\bany (profit|money|gains)",
    ]
    query_lower = query.lower()
    return any(re.search(pattern, query_lower) for pattern in direct_pl_patterns)


def is_compound_pl_analytical_query(query: str) -> bool:
    """
    Detect if query asks BOTH for P/L data AND explanation/analysis.

    Examples that are compound queries:
    - "How much money did we make today and why?"
    - "What's our profit and explain why?"
    - "Did we make money? Why or why not?"

    These need BOTH:
    1. Direct P/L answer (conversational, not dump)
    2. RAG analysis for the "why" part
    """
    return is_direct_pl_query(query) and is_analytical_query(query)


def extract_ticker_from_query(query: str) -> str | None:
    """Extract a potential ticker symbol from a trade query.

    Returns the ticker if found, or None if the query is generic
    (e.g., "show all trades", "recent trades").
    """
    import re

    # Known valid tickers in our system
    known_tickers = {"SPY", "XSP", "SPX", "VOO", "QQQ"}
    # Common English words that should never be treated as tickers
    _stop_words = {
        "a",
        "an",
        "am",
        "as",
        "at",
        "be",
        "by",
        "do",
        "go",
        "he",
        "hi",
        "if",
        "in",
        "is",
        "it",
        "me",
        "my",
        "no",
        "of",
        "oh",
        "ok",
        "on",
        "or",
        "so",
        "to",
        "up",
        "us",
        "we",
        "did",
        "has",
        "had",
        "his",
        "her",
        "its",
        "let",
        "may",
        "not",
        "now",
        "old",
        "one",
        "our",
        "out",
        "own",
        "put",
        "run",
        "say",
        "see",
        "set",
        "she",
        "the",
        "too",
        "try",
        "use",
        "way",
        "who",
        "why",
        "win",
        "yes",
        "yet",
        "you",
        "all",
        "and",
        "are",
        "but",
        "buy",
        "can",
        "for",
        "got",
        "how",
        "new",
        "per",
        "via",
        "was",
        "any",
        "big",
        "day",
        "end",
        "far",
        "few",
        "get",
        "lot",
        "man",
        "net",
        "off",
        "pay",
        "red",
        "tax",
        "top",
        "two",
        "ago",
        "ask",
        "bad",
        "bet",
        "bit",
        "cut",
        "due",
        "fit",
        "hit",
        "hot",
        "key",
        "low",
        "max",
        "min",
        "mix",
        "ran",
        "raw",
        "risk",
        "rule",
        "safe",
        "sell",
        "side",
        "size",
        "stop",
        "take",
        "tell",
        "than",
        "that",
        "them",
        "then",
        "they",
        "this",
        "time",
        "told",
        "took",
        "turn",
        "used",
        "very",
        "want",
        "week",
        "well",
        "went",
        "what",
        "when",
        "will",
        "with",
        "work",
        "year",
        "your",
        "also",
        "back",
        "been",
        "best",
        "both",
        "call",
        "came",
        "come",
        "data",
        "does",
        "done",
        "down",
        "each",
        "even",
        "fact",
        "feel",
        "give",
        "good",
        "half",
        "hand",
        "have",
        "help",
        "here",
        "high",
        "hold",
        "home",
        "into",
        "just",
        "keep",
        "kind",
        "know",
        "last",
        "left",
        "less",
        "life",
        "like",
        "line",
        "long",
        "look",
        "lose",
        "lost",
        "make",
        "more",
        "most",
        "move",
        "much",
        "must",
        "name",
        "need",
        "next",
        "only",
        "over",
        "part",
        "plan",
        "play",
        "real",
        "rest",
        "same",
        "seem",
        "show",
        "some",
        "such",
        "sure",
        "test",
        "true",
        "type",
        "upon",
        "view",
        "from",
        "about",
        "after",
        "could",
        "every",
        "first",
        "found",
        "great",
        "never",
        "other",
        "right",
        "shall",
        "since",
        "still",
        "their",
        "there",
        "these",
        "thing",
        "think",
        "those",
        "three",
        "under",
        "until",
        "using",
        "where",
        "which",
        "while",
        "would",
        # Trading-specific words
        "trade",
        "trades",
        "trading",
        "bought",
        "sold",
        "position",
        "positions",
        "pnl",
        "profit",
        "loss",
        "money",
        "made",
        "earn",
        "earned",
        "today",
        "gains",
        "returns",
        "equity",
        "balance",
        "account",
        "stock",
        "option",
        "entry",
        "exit",
        "filled",
        "executed",
        "order",
        "recent",
        "iron",
        "condor",
        "condors",
        "spread",
        "spreads",
        "performance",
        "portfolio",
        "symbol",
        "current",
        "close",
        "open",
        "list",
        "find",
        "many",
    }
    words = re.findall(r"\b[a-zA-Z]+\b", query)
    for word in words:
        upper = word.upper()
        lower = word.lower()
        if lower in _stop_words:
            continue
        if upper in known_tickers:
            return upper
        # Only treat as unknown ticker if: 3-6 chars and either ALL CAPS in
        # original query or not a recognizable English word
        if 3 <= len(word) <= 6 and word.isalpha() and word.isupper():
            return upper
    # Second pass: look for 3-6 char words that aren't stop words
    # (handles lowercase ticker mentions like "kurast")
    for word in words:
        upper = word.upper()
        lower = word.lower()
        if lower in _stop_words:
            continue
        if 3 <= len(word) <= 6 and word.isalpha():
            return upper
    return None


def is_trade_query(query: str) -> bool:
    """
    Detect if query is about trades vs lessons.

    Uses word boundary matching to avoid false positives like
    "learned" matching "earn" or "earned".
    """
    import re

    trade_keywords = [
        "trade",
        "trades",
        "trading",
        "bought",
        "sold",
        "position",
        "pnl",
        "p/l",
        "profit",
        "loss",
        "performance",
        "portfolio",
        "spy",
        "money",
        "made",
        "earn",
        "earned",
        "today",
        "gains",
        "returns",
        "equity",
        "balance",
        "account",
        "aapl",
        "msft",
        "nvda",
        "symbol",
        "stock",
        "option",
        "entry",
        "exit",
        "filled",
        "executed",
        "order",
    ]
    query_lower = query.lower()
    # Use word boundary matching to avoid "learned" matching "earn"
    return any(re.search(rf"\b{re.escape(keyword)}\b", query_lower) for keyword in trade_keywords)


def assess_trading_readiness(
    is_future: bool = False,
    is_paper: bool = True,
    is_live: bool = False,
) -> dict:
    """
    Assess trading readiness based on multiple factors.
    Returns a comprehensive readiness report with actionable insights.

    Args:
        is_future: If True, evaluating readiness for future trading (e.g., tomorrow)
        is_paper: If True, evaluating paper trading readiness
        is_live: If True, evaluating live trading readiness
    """
    import json
    from datetime import datetime

    try:
        from zoneinfo import ZoneInfo

        et_tz = ZoneInfo("America/New_York")
        now_et = datetime.now(et_tz)
    except ImportError:
        from datetime import timezone

        now_et = datetime.now(timezone.utc)

    checks = []
    warnings = []
    blockers = []
    score = 0
    max_score = 0

    # 1. MARKET STATUS CHECK
    max_score += 20
    weekday = now_et.weekday()
    hour = now_et.hour
    minute = now_et.minute
    current_time = hour * 60 + minute
    market_open = 9 * 60 + 30  # 9:30 AM
    market_close = 16 * 60  # 4:00 PM

    if weekday >= 5:  # Weekend
        if is_future:
            # Weekend but asking about future - check if next trading day is accessible
            days_until_monday = (7 - weekday) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            warnings.append(f"Weekend - next trading day in {days_until_monday} days")
            score += 10  # Partial credit for future planning
        else:
            blockers.append("Market CLOSED - Weekend (Mon-Fri only)")
    elif current_time < market_open:
        minutes_to_open = market_open - current_time
        if is_future:
            # Before open but asking about future - this is fine
            checks.append(f"Market opens at 9:30 AM ET (in {minutes_to_open} min)")
            score += 20
        else:
            warnings.append(
                f"Market opens in {minutes_to_open} minutes ({now_et.strftime('%I:%M %p')} ET)"
            )
            score += 10  # Partial credit - we're prepared
    elif current_time >= market_close:
        if is_future:
            # After hours but asking about tomorrow - NOT a blocker
            checks.append("Market opens tomorrow at 9:30 AM ET")
            score += 20
        else:
            blockers.append(f"Market CLOSED - After hours ({now_et.strftime('%I:%M %p')} ET)")
    else:
        checks.append(f"Market OPEN ({now_et.strftime('%I:%M %p')} ET)")
        score += 20

    # 2. SYSTEM STATE CHECK
    max_score += 20
    state_path = project_root / "data" / "system_state.json"
    state = None
    # Try local file first
    try:
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)
            checks.append("System state loaded (local)")
            score += 10
    except Exception as e:
        logger.warning(f"Failed to read local system state: {e}")

    # Fallback to GitHub API if local not available
    # Use GitHub API v3 instead of raw URL to bypass CDN caching (fixes stale data issue)
    if state is None:
        try:
            import base64
            import urllib.request

            # GitHub API v3 endpoint - provides fresh data, no CDN caching
            github_url = "https://api.github.com/repos/IgorGanapolsky/trading/contents/data/system_state.json"
            req = urllib.request.Request(
                github_url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "TradingBot/1.0",
                },
            )
            # Security: Use verified SSL context (fixes MitM vulnerability)
            ssl_context = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=5, context=ssl_context) as response:
                api_response = json.loads(response.read().decode("utf-8"))
                # GitHub API returns base64-encoded content
                content_b64 = api_response.get("content", "")
                content = base64.b64decode(content_b64).decode("utf-8")
                state = json.loads(content)
            checks.append("System state loaded (GitHub API)")
            score += 10
        except Exception as e:
            logger.debug(f"System state fallback read failed: {e}")
            warnings.append("System state not found (local or GitHub API)")

    # Check state freshness
    if state:
        last_updated = state.get("meta", {}).get("last_updated", "")
        if last_updated:
            try:
                update_time = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                hours_old = (
                    datetime.now(update_time.tzinfo or None) - update_time
                ).total_seconds() / 3600
                if hours_old < 2:
                    checks.append(f"State fresh ({hours_old:.1f}h old)")
                    score += 10
                elif hours_old < 4:
                    warnings.append(f"State aging ({hours_old:.1f}h old) - consider refreshing")
                    score += 5
                else:
                    warnings.append(f"State STALE ({hours_old:.1f}h old) - data may be outdated")
            except Exception as e:
                logger.debug(f"State freshness check failed: {e}")
                warnings.append("Could not verify state freshness")

    # 3. CAPITAL CHECK (context-aware: paper vs live)
    max_score += 20
    if state:
        # FIX Jan 12, 2026: Use "equity" or "cash" as fallback (system_state.json schema)
        paper_equity = state.get("paper_account", {}).get("equity", 0) or state.get(
            "paper_account", {}
        ).get("cash", 0)
        live_equity = state.get("account", {}).get("equity", 0) or state.get("account", {}).get(
            "cash", 0
        )

        if is_paper:
            # Paper trading mode - realistic thresholds for $5K paper account (CEO reset Jan 7, 2026)
            # $5K is our 6-month milestone target, not $100K
            if paper_equity >= 5000:
                checks.append(f"Paper equity healthy: ${paper_equity:,.2f}")
                score += 20
            elif paper_equity >= 2000:
                warnings.append(f"Paper equity moderate: ${paper_equity:,.2f}")
                score += 10
            elif paper_equity > 0:
                warnings.append(f"Paper equity low: ${paper_equity:,.2f} (building track record)")
                score += 5
            else:
                blockers.append(f"Paper equity zero: ${paper_equity:,.2f}")
            # Note about live capital (informational, not blocking for paper)
            if live_equity < 200:
                target = 500  # First CSP target
                remaining = target - live_equity
                warnings.append(
                    f"FYI: Live capital ${live_equity:.2f} (need ${remaining:.0f} more for live trading)"
                )
        else:
            # Live trading mode - evaluate live equity (full 20 points)
            if live_equity >= 500:
                checks.append(f"Live capital sufficient: ${live_equity:.2f}")
                score += 20
            elif live_equity >= 200:
                warnings.append(f"Live capital minimal: ${live_equity:.2f}")
                score += 10
            else:
                target = 500  # First CSP target
                remaining = target - live_equity
                blockers.append(
                    f"Live capital insufficient: ${live_equity:.2f} (need ${remaining:.0f} more)"
                )

    # 4. BACKTEST VALIDATION
    max_score += 20
    backtest_path = project_root / "data" / "backtests" / "latest_summary.json"
    try:
        if backtest_path.exists():
            with open(backtest_path) as f:
                backtest = json.load(f)
            passes = backtest.get("aggregate_metrics", {}).get("passes", 0)
            total = backtest.get("scenario_count", 0)
            if passes == total and total > 0:
                checks.append(f"Backtests: {passes}/{total} scenarios PASS")
                score += 20
            elif passes > total * 0.8:
                warnings.append(f"Backtests: {passes}/{total} scenarios pass")
                score += 10
            else:
                blockers.append(f"Backtests FAILING: only {passes}/{total} pass")
    except Exception as e:
        logger.debug(f"Backtest status check failed: {e}")
        warnings.append("Could not verify backtest status")

    # 5. WIN RATE CHECK (handles fresh starts with 0 trades)
    max_score += 20
    if state:
        win_rate = state.get("paper_account", {}).get("win_rate", 0)
        sample_size = state.get("paper_account", {}).get("win_rate_sample_size", 0)

        # Fresh start (0 trades) - not a blocker, just needs trades
        if sample_size == 0:
            warnings.append("No trades yet - building track record (not a blocker)")
            score += 10  # Give partial credit for fresh starts
        elif win_rate >= 60:
            checks.append(f"Win rate strong: {win_rate:.0f}% ({sample_size} trades)")
            score += 20
        elif win_rate >= 50:
            warnings.append(f"Win rate marginal: {win_rate:.0f}% ({sample_size} trades)")
            score += 10
        else:
            # Only block if we have enough trades to be meaningful
            if sample_size >= 10:
                blockers.append(f"Win rate poor: {win_rate:.0f}% ({sample_size} trades)")
            else:
                warnings.append(
                    f"Win rate {win_rate:.0f}% (only {sample_size} trades - need more data)"
                )

    # 6. CI/CD STATUS CHECK (Critical - added Jan 13, 2026)
    # CEO Directive: "CI is failing" should lower readiness score
    max_score += 20
    ci_status = check_ci_status()
    if ci_status["error"]:
        warnings.append("Could not verify CI status")
        score += 10  # Partial credit - we tried
    elif ci_status["is_passing"]:
        if ci_status["running_workflows"]:
            checks.append(f"CI passing ({len(ci_status['running_workflows'])} workflows running)")
        else:
            checks.append("CI passing (all workflows green)")
        score += 20
    else:
        # CI is failing - this is a WARNING, not blocker (code still runs)
        failed_list = ", ".join(ci_status["failed_workflows"][:3])
        warnings.append(f"CI FAILING: {failed_list}")
        score += 5  # Some credit for having CI

    # 7. TRADING AUTOMATION CHECK (Critical - added Jan 6, 2026)
    max_score += 20
    if state:
        last_trade_date = state.get("trades", {}).get("last_trade_date", "")
        automation_fix_date = state.get("meta", {}).get("automation_fix_date", "")
        if last_trade_date:
            try:
                last_trade = datetime.strptime(last_trade_date, "%Y-%m-%d")
                days_since_trade = (now_et.replace(tzinfo=None) - last_trade).days
                # Weekend adjustment: subtract 2 days if Mon/Tue
                weekday = now_et.weekday()
                if weekday in [0, 1]:  # Monday or Tuesday
                    days_since_trade -= 2
                if days_since_trade <= 1:
                    checks.append(f"Automation active (last trade: {last_trade_date})")
                    score += 20
                elif days_since_trade <= 3:
                    warnings.append(
                        f"Automation possibly stale ({days_since_trade} days since last trade)"
                    )
                    score += 10
                else:
                    # Check if a fix was applied today
                    today_str = now_et.strftime("%Y-%m-%d")
                    if automation_fix_date == today_str:
                        # Fix applied but no trade yet - show warning not blocker
                        warnings.append(
                            f"Fix applied today - awaiting 9:35 AM ET trade run "
                            f"(last trade: {last_trade_date})"
                        )
                        score += 10
                    else:
                        # Provide detailed diagnosis for automation failure
                        diagnosis = []
                        diagnosis.append(
                            f"🚨 AUTOMATION BROKEN: No trades for {days_since_trade} days! (last trade: {last_trade_date})"
                        )

                        # Check for known issues in lessons
                        try:
                            from src.rag.lessons_learned_rag import LessonsLearnedRAG

                            rag = LessonsLearnedRAG()
                            recent_issues = rag.search(
                                "trading failed blocked automation bug", top_k=2
                            )
                            if recent_issues:
                                diagnosis.append("**Recent Issues Found:**")
                                for lesson, score_val in recent_issues[:2]:
                                    if hasattr(lesson, "title"):
                                        diagnosis.append(f"  • {lesson.title}")
                        except Exception as e:
                            logger.debug(f"RAG lessons query failed: {e}")

                        # Add actionable diagnostics
                        diagnosis.append("**Likely Causes:**")
                        diagnosis.append(
                            "  • Market hours: Trades only execute 9:35 AM ET on trading days"
                        )
                        diagnosis.append("  • Bug in trading logic: Check simple_daily_trader.py")
                        diagnosis.append("  • Alpaca API: Check GitHub Actions logs for API errors")
                        diagnosis.append("**Action:** Monitor next 9:35 AM ET workflow run")

                        blockers.append("\n".join(diagnosis))
            except Exception as e:
                logger.debug(f"Last trade date check failed: {e}")
                warnings.append("Could not verify last trade date")
        else:
            blockers.append("No trade history found - automation may not be running")

    # Calculate overall readiness
    readiness_pct = (score / max_score * 100) if max_score > 0 else 0

    if blockers:
        status = "NOT_READY"
        emoji = "🔴"
    elif len(warnings) > 2:
        status = "CAUTION"
        emoji = "🟡"
    elif readiness_pct >= 80:
        status = "READY"
        emoji = "🟢"
    else:
        status = "PARTIAL"
        emoji = "🟡"

    return {
        "status": status,
        "emoji": emoji,
        "score": score,
        "max_score": max_score,
        "readiness_pct": readiness_pct,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "timestamp": now_et.strftime("%Y-%m-%d %I:%M %p ET"),
        # Include context for response formatting
        "is_future": is_future,
        "is_paper": is_paper,
        "is_live": is_live,
    }


def format_readiness_response(assessment: dict) -> str:
    """Format readiness assessment into a user-friendly response."""
    status = assessment["status"]
    emoji = assessment["emoji"]
    score = assessment["score"]
    max_score = assessment["max_score"]
    readiness_pct = assessment["readiness_pct"]

    # Show context if available
    context_parts = []
    if assessment.get("is_paper"):
        context_parts.append("PAPER")
    elif assessment.get("is_live"):
        context_parts.append("LIVE")
    if assessment.get("is_future"):
        context_parts.append("TOMORROW")
    context_str = f" [{'/'.join(context_parts)}]" if context_parts else ""

    response_parts = [
        f"{emoji} **TRADING READINESS: {status}** ({readiness_pct:.0f}%){context_str}",
        f"Score: {score}/{max_score}",
        f"Assessed: {assessment['timestamp']}",
        "",
    ]

    if assessment["blockers"]:
        response_parts.append("🚫 **BLOCKERS:**")
        for b in assessment["blockers"]:
            response_parts.append(f"  • {b}")
        response_parts.append("")

    if assessment["warnings"]:
        response_parts.append("⚠️ **WARNINGS:**")
        for w in assessment["warnings"]:
            response_parts.append(f"  • {w}")
        response_parts.append("")

    if assessment["checks"]:
        response_parts.append("✅ **PASSING:**")
        for c in assessment["checks"]:
            response_parts.append(f"  • {c}")
        response_parts.append("")

    # Add actionable recommendation
    if status == "NOT_READY":
        response_parts.append("📌 **Recommendation:** Do NOT trade until blockers are resolved.")
    elif status == "CAUTION":
        response_parts.append(
            "📌 **Recommendation:** Proceed with reduced position sizes. Monitor closely."
        )
    elif status == "READY":
        response_parts.append(
            "📌 **Recommendation:** All systems GO. Execute per strategy guidelines."
        )
    else:
        response_parts.append("📌 **Recommendation:** Review warnings before trading.")

    return "\n".join(response_parts)


def format_lesson_full(lesson: dict) -> str:
    """Format a lesson with FULL content - no truncation."""
    content = lesson.get("content", "")

    # Extract key sections from markdown
    lines = content.split("\n")
    title = ""
    severity = lesson.get("severity", "UNKNOWN")

    # Get title from first H1
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    # Return full formatted content
    formatted = f"""**{title}** ({severity})

{content}
"""
    return formatted


def format_lessons_response(lessons: list, query: str) -> str:
    """Format multiple lessons into a complete response."""
    if not lessons:
        return f"No lessons found matching '{query}'. Try searching for: trading, risk, CI, RAG, verification, or operational."

    response_parts = ["Based on our lessons learned:\n"]

    for i, lesson in enumerate(lessons, 1):
        lesson_id = lesson.get("id", "unknown")
        severity = lesson.get("severity", "UNKNOWN")
        content = lesson.get("content", lesson.get("snippet", ""))

        # Format full lesson content
        response_parts.append(f"\n**{lesson_id}** ({severity}): {content}\n")
        response_parts.append("-" * 50)

    return "\n".join(response_parts)


def query_trades(query: str, limit: int = 10) -> list[dict]:
    """Query trade history from system_state.json (Alpaca source of truth).

    FIX Jan 16 2026: Reversed priority order.
    - OLD: trades_*.json first, system_state.json fallback
    - NEW: system_state.json FIRST (synced from Alpaca), trades_*.json fallback

    The bug: On Cloud Run, trades_*.json files don't exist. The webhook was
    checking them first and finding nothing. system_state.json has the real
    trade_history synced directly from Alpaca API.
    """
    import json

    import requests

    trades = []
    data_dir = project_root / "data"

    try:
        # PRIORITY 1: system_state.json - source of truth from Alpaca
        # Try local first, then GitHub API
        state = None
        state_path = data_dir / "system_state.json"

        # Try local system_state.json
        if state_path.exists():
            try:
                with open(state_path) as f:
                    state = json.load(f)
                logger.info("Loaded system_state.json from local file")
            except Exception as e:
                logger.warning(f"Failed to read local system_state.json: {e}")

        # Fallback to GitHub API if local not available
        if not state:
            try:
                github_url = "https://api.github.com/repos/IgorGanapolsky/trading/contents/data/system_state.json"
                resp = requests.get(github_url, timeout=10)
                if resp.status_code == 200:
                    import base64

                    content = base64.b64decode(resp.json()["content"]).decode("utf-8")
                    state = json.loads(content)
                    logger.info("Loaded system_state.json from GitHub API")
            except Exception as e:
                logger.warning(f"GitHub API system_state.json fetch failed: {e}")

        # Extract trade_history from system_state.json
        if state:
            trade_history = state.get("trade_history", [])
            for trade in trade_history[:limit]:
                # Clean up side string (remove "OrderSide." prefix)
                side_raw = str(trade.get("side", ""))
                side_clean = side_raw.replace("OrderSide.", "").upper()

                document = (
                    f"Trade: {side_clean} {trade.get('qty', 0)} "
                    f"{trade.get('symbol', '')} at ${float(trade.get('price', 0)):.2f}. "
                    f"Filled: {str(trade.get('filled_at', ''))[:10] if trade.get('filled_at') else 'N/A'}"
                )
                # FIX Jan 22, 2026: Add timestamp and source fields
                # Note: system_state.json trades are order FILLS, not matched trades
                # They don't have P/L data - that would require matching buy/sell pairs
                filled_at = str(trade.get("filled_at", ""))[:10] if trade.get("filled_at") else ""
                trades.append(
                    {
                        "document": document,
                        "metadata": {
                            "symbol": trade.get("symbol", "UNKNOWN"),
                            "side": side_clean,
                            "qty": trade.get("qty", 0),
                            "price": trade.get("price", 0),
                            "filled_at": trade.get("filled_at", ""),
                            "timestamp": filled_at,  # For formatter compatibility
                            "source": "alpaca_fills",  # Indicates these are order fills
                        },
                    }
                )
            if trades:
                logger.info(f"Loaded {len(trades)} trades from system_state.json (Alpaca fills)")

        # PRIORITY 2: Fallback to trades_*.json files (legacy/local sync)
        if not trades:
            logger.info("No trades in system_state.json, trying trades_*.json files")
            for trades_file in sorted(data_dir.glob("trades_*.json"), reverse=True):
                if len(trades) >= limit:
                    break

                with open(trades_file) as f:
                    file_trades = json.load(f)
                    for trade in file_trades:
                        pnl = trade.get("pnl") or 0
                        outcome = "profitable" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")
                        document = (
                            f"Trade: {trade.get('side', '').upper()} {trade.get('qty', 0)} "
                            f"{trade.get('symbol', '')} at ${trade.get('price', 0):.2f} "
                            f"using {trade.get('strategy', '')} strategy. "
                            f"Outcome: {outcome} with P/L ${pnl:.2f}. "
                            f"Date: {trade.get('timestamp', '')[:10]}"
                        )
                        trades.append(
                            {
                                "document": document,
                                "metadata": {
                                    "symbol": trade.get("symbol", "UNKNOWN"),
                                    "side": trade.get("side", ""),
                                    "strategy": trade.get("strategy", ""),
                                    "pnl": pnl,
                                    "outcome": outcome,
                                    "timestamp": trade.get("timestamp", ""),
                                },
                            }
                        )
                        if len(trades) >= limit:
                            break
            if trades:
                logger.info(f"Loaded {len(trades)} trades from trades_*.json files (fallback)")

        return trades[:limit]

    except Exception as e:
        logger.error(f"Trade query failed: {e}")
        return []


def format_trades_response(trades: list, query: str) -> str:
    """Format trade history into a response.

    FIX Jan 22, 2026: Handle different trade sources properly.
    - alpaca_fills: Order fills from system_state.json - no P/L data
    - matched_trades: From trades_*.json - have P/L data
    """
    if not trades:
        return f"No trades found matching '{query}'. The trade history may be empty or the query didn't match any trades."

    response_parts = [f"📊 **Trade History** (found {len(trades)} trades):\n"]

    for i, trade in enumerate(trades, 1):
        doc = trade.get("document", "")
        meta = trade.get("metadata", {})

        symbol = meta.get("symbol", "UNKNOWN")
        side = meta.get("side", "").upper()
        timestamp = meta.get("timestamp", "")[:10]
        source = meta.get("source", "")

        # FIX: Only show P/L for sources that have real P/L data
        if source == "alpaca_fills":
            # Order fills don't have P/L - just show the fill info
            price = float(meta.get("price", 0))
            qty = meta.get("qty", 0)
            response_parts.append(
                f"\n{i}. **{symbol}** {side} | Qty: {qty} @ ${price:.2f} | {timestamp}\n"
                f"   {doc[:150]}\n"
            )
        else:
            # Matched trades have P/L data
            outcome = meta.get("outcome", "unknown")
            pnl = meta.get("pnl", 0)
            outcome_emoji = (
                "✅" if outcome == "profitable" else ("❌" if outcome == "loss" else "➖")
            )
            response_parts.append(
                f"\n{i}. {outcome_emoji} **{symbol}** {side} | P/L: ${pnl:.2f} | {timestamp}\n"
                f"   {doc[:150]}\n"
            )

    return "\n".join(response_parts)


def create_webhook_response(text: str) -> dict:
    """
    Create a webhook response payload.

    IMPORTANT: We set the FULL text here. Clients should not truncate
    this response. If truncation occurs, check:
    1. Cloud Run timeout (should be 60s)
    2. Client timeout (should be 30s)
    3. Client response settings
    """
    return {"fulfillmentResponse": {"messages": [{"text": {"text": [text]}}]}}


def sanitize_public_response_text(text: str) -> str:
    """Prevent exception stack traces from being returned to API clients."""
    if "Traceback (most recent call last)" in text or 'File "' in text:
        return "An internal error occurred processing your request. Please try again."
    return text


def verify_webhook_auth(authorization: Optional[str] = Header(None)) -> bool:
    """
    Verify webhook authentication token.

    Security: Validates bearer token if RAG_WEBHOOK_TOKEN is set.
    If no token is configured, allows requests (for backward compatibility).
    """
    if not WEBHOOK_AUTH_TOKEN:
        # No auth configured - allow (backward compatibility)
        return True

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Support both "Bearer <token>" and plain "<token>" formats
    token = authorization.replace("Bearer ", "").strip()
    if token != WEBHOOK_AUTH_TOKEN:
        logger.warning("Webhook authentication failed - invalid token")
        raise HTTPException(status_code=403, detail="Invalid authentication token")

    return True


@app.post("/webhook")
@rate_limit("100/minute")  # Security: Rate limit webhook to 100 requests/minute per IP
async def webhook(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    """
    Handle RAG Webhook requests.

    Security:
    - Rate limited to 100 requests/minute per IP (if slowapi installed)
    - Authenticated via bearer token (if RAG_WEBHOOK_TOKEN configured)

    Request format:
    {
        "detectIntentResponseId": "...",
        "intentInfo": {...},
        "pageInfo": {...},
        "sessionInfo": {...},
        "fulfillmentInfo": {...},
        "text": "user query here"
    }
    """
    # Verify authentication (if configured)
    verify_webhook_auth(authorization)

    try:
        body = await request.json()
        # Security: Don't log full request body (may contain sensitive data)
        logger.info(f"Webhook request received, text field present: {'text' in body}")

        # Extract user query from different possible locations
        user_query = ""

        # Try text field first (most common)
        if "text" in body:
            user_query = body["text"]
        # Try transcript field
        elif "transcript" in body:
            user_query = body["transcript"]
        # Try sessionInfo parameters
        elif "sessionInfo" in body and "parameters" in body["sessionInfo"]:
            params = body["sessionInfo"]["parameters"]
            if "query" in params:
                user_query = params["query"]
        # Try fulfillmentInfo tag
        elif "fulfillmentInfo" in body and "tag" in body["fulfillmentInfo"]:
            # Use tag as context hint
            tag = body["fulfillmentInfo"]["tag"]
            user_query = f"lessons about {tag}"

        if not user_query:
            # Default query for testing
            user_query = "critical lessons learned"
            logger.warning(f"No query found in request, using default: {user_query}")

        # Sanitize user input for safe logging (prevent log injection)
        safe_query = user_query.replace("\n", " ").replace("\r", " ")[:200]
        logger.info(f"Processing query: {safe_query}")

        # Determine query type and route accordingly
        # Check readiness queries FIRST (highest priority)
        if is_readiness_query(user_query):
            logger.info(f"Detected READINESS query: {safe_query}")
            # Parse context from query (tomorrow? paper? live?)
            context = parse_readiness_context(user_query)
            logger.info(f"Readiness context: {context}")
            assessment = assess_trading_readiness(
                is_future=context["is_future"],
                is_paper=context["is_paper"],
                is_live=context["is_live"],
            )
            response_text = format_readiness_response(assessment)
            logger.info(
                f"Readiness assessment: {assessment['status']} ({assessment['readiness_pct']:.0f}%) "
                f"[future={context['is_future']}, paper={context['is_paper']}]"
            )

        elif is_compound_pl_analytical_query(user_query):
            # FIX Jan 21, 2026: Handle compound P/L + analytical queries
            # E.g., "How much money did we make today and why?"
            # 1. Answer the P/L question directly (conversational)
            # 2. Query RAG for the "why" explanation
            logger.info(f"Detected COMPOUND P/L + ANALYTICAL query: {safe_query}")

            # Part 1: Get direct P/L answer
            portfolio = get_current_portfolio_status()
            pl_response = ""
            trades_today = 0  # Initialize for use in Part 2
            if portfolio:
                paper = portfolio.get("paper", {})
                trades_today = portfolio.get("trades_today", 0)
                actual_today = portfolio.get("actual_today", "today")

                if trades_today > 0:
                    daily_change = _coerce_float(paper.get("daily_change", 0))
                    if daily_change > 0:
                        pl_response = (
                            f"**Today's P/L:** +${daily_change:,.2f} from {trades_today} trade(s)"
                        )
                    elif daily_change < 0:
                        pl_response = f"**Today's P/L:** -${abs(daily_change):,.2f} from {trades_today} trade(s)"
                    else:
                        pl_response = f"**Today's P/L:** Flat from {trades_today} trade(s)"
                else:
                    pl_response = _format_no_trade_today_pl(paper, actual_today)
            else:
                pl_response = "**P/L Status:** Unable to retrieve portfolio data"

            # Part 2: Query RAG for analytical explanation
            # FIX Jan 23, 2026: When no trades, use relevant query instead of user query
            # User query "How much money did we make" was matching random failure lessons
            if trades_today == 0:
                # Query for reasons why no trades (more relevant than user query)
                rag_query = "trading signals market conditions iron condor entry criteria"
            else:
                rag_query = user_query
            results, source = query_rag_hybrid(rag_query, top_k=3)

            rag_explanation = ""
            if results:
                # Extract key insights from RAG results
                insights = []
                for r in results[:3]:
                    lesson_id = r.get("id", "Insight")
                    content = r.get("content", r.get("snippet", ""))[:150]
                    if content:
                        insights.append(f"- **{lesson_id}**: {content}")

                if insights:
                    rag_explanation = "\n**Analysis from lessons learned:**\n" + "\n".join(insights)

            # If no insights extracted, provide default explanation
            if not rag_explanation:
                rag_explanation = """
**Common reasons for P/L results:**
- Market closed (weekends/holidays) - no trading possible
- Entry signals not triggered - waiting for setup
- Strategy parameters - iron condor requires specific conditions
- Position sizing - staying within 5% risk limit"""

            response_text = f"""📊 **{user_query}**

{pl_response}
{rag_explanation}

💡 *Ask "are we ready to trade?" for full status*"""
            logger.info(f"Returning compound P/L + analytical response (RAG source: {source})")

        elif is_trade_query(user_query):
            # Query trade history from local JSON files
            logger.info(f"Detected TRADE query: {safe_query}")

            # Check if user is asking about a specific unknown ticker
            mentioned_ticker = extract_ticker_from_query(user_query)
            known_tickers = {"SPY", "XSP", "SPX", "VOO", "QQQ"}
            _unknown_ticker = mentioned_ticker and mentioned_ticker not in known_tickers

            if _unknown_ticker:
                response_text = (
                    f"I don't recognize '{mentioned_ticker}' as a ticker in our system. "
                    f"We only trade **SPY** iron condors. "
                    f"Try asking about SPY trades, current P/L, or exit rules."
                )
                # Avoid logging user-controlled ticker values to prevent log injection vectors.
                logger.info("Unknown ticker query received; returning SPY-only guidance")

            if not _unknown_ticker:
                trades = query_trades(user_query, limit=10)

                # Filter by mentioned ticker if specified
                if mentioned_ticker and trades:
                    trades = [
                        t
                        for t in trades
                        if (t.get("metadata", {}).get("symbol") or "").upper() == mentioned_ticker
                        or mentioned_ticker == "SPY"  # SPY options have OCC symbols
                    ]

                if trades:
                    response_text = format_trades_response(trades, user_query)
                    logger.info(f"Returning {len(trades)} trades")
                elif is_analytical_query(user_query):
                    # FIX Jan 13, 2026: Analytical questions (WHY, explain, etc.)
                    # should go to RAG for semantic understanding, not portfolio status
                    logger.info(f"Detected ANALYTICAL trade query: {safe_query} - routing to RAG")
                    results, source = query_rag_hybrid(user_query, top_k=5)

                    # Get portfolio context to include in response
                    portfolio = get_current_portfolio_status()
                    portfolio_context = ""
                    if portfolio:
                        live = portfolio.get("live", {})
                        paper = portfolio.get("paper", {})
                        last_trade = portfolio.get("last_trade_date", "unknown")
                        portfolio_context = f"""
**Current Status:**
- Paper Equity: ${paper.get("equity", 0):,.2f} | P/L: ${paper.get("total_pl", 0):,.2f}
- Live Equity: ${live.get("equity", 0):.2f}
- Last Trade: {last_trade}

"""

                    if results:
                        rag_response = format_rag_response(results, user_query, source)
                        response_text = f"""📊 **Analysis: {user_query}**

{portfolio_context}{rag_response}"""
                    else:
                        # No RAG results - provide helpful analysis
                        response_text = f"""📊 **Analysis: {user_query}**

{portfolio_context}**Possible reasons for no profit:**
1. **No trades executed** - Check if automation is running
2. **Market conditions** - Weekend/after hours means no trading
3. **Strategy parameters** - Entry signals may not have triggered
4. **Capital constraints** - Insufficient buying power for options

**To investigate further:**
- Check GitHub Actions for trading workflow status
- Review paper account positions in Alpaca dashboard
- Ask: "Are we ready to trade?" for full readiness assessment"""
                    logger.info(f"Returning analytical response with RAG from {source}")
                elif is_direct_pl_query(user_query):
                    # FIX Jan 13, 2026: Direct P/L questions get conversational answers
                    # Not a full portfolio dump - just answer the question directly
                    logger.info(f"Detected DIRECT P/L query: {safe_query}")
                    portfolio = get_current_portfolio_status()
                    if portfolio:
                        paper = portfolio.get("paper", {})
                        live = portfolio.get("live", {})
                        trades_today = portfolio.get("trades_today", 0)
                        # FIX: today_pl doesn't exist - use daily_change from paper account
                        today_pl = paper.get("daily_change", 0)
                        actual_today = portfolio.get("actual_today", "today")

                        if trades_today > 0 and today_pl != 0:
                            # Trades executed with P/L
                            if today_pl > 0:
                                response_text = (
                                    f"You made **${today_pl:,.2f}** today "
                                    f"from {trades_today} trade(s). Nice work!"
                                )
                            else:
                                response_text = (
                                    f"You lost **${abs(today_pl):,.2f}** today "
                                    f"from {trades_today} trade(s). Let's review."
                                )
                        elif trades_today > 0:
                            # Trades executed - show TODAY's change, not total P/L
                            daily_change = paper.get("daily_change", 0)
                            total_pl = paper.get("total_pl", 0)
                            if daily_change > 0:
                                response_text = (
                                    f"You executed {trades_today} trade(s) today. "
                                    f"**Today's gain: +${daily_change:,.2f}** "
                                    f"(Overall P/L: ${total_pl:,.2f})"
                                )
                            elif daily_change < 0:
                                response_text = (
                                    f"You executed {trades_today} trade(s) today. "
                                    f"**Today's loss: -${abs(daily_change):,.2f}** "
                                    f"(Overall P/L: ${total_pl:,.2f})"
                                )
                            else:
                                response_text = (
                                    f"You executed {trades_today} trade(s) today. "
                                    f"**Flat today** (Overall P/L: ${total_pl:,.2f})"
                                )
                        else:
                            # No trades today
                            paper_pl = _coerce_float(paper.get("total_pl", 0))
                            pct = _coerce_float(paper.get("total_pl_pct", 0))
                            daily_change = _coerce_float(paper.get("daily_change", 0))
                            positions_count = int(paper.get("positions_count", 0) or 0)

                            drift_label = (
                                "mark-to-market" if positions_count > 0 else "equity drift"
                            )
                            drift_line = (
                                f"Today's {drift_label}: **{_format_signed_dollars(daily_change)}** "
                                f"(no trades)."
                                if abs(daily_change) >= 0.005
                                else "Today's mark-to-market: **$0.00** (no trades)."
                            )
                            response_text = (
                                f"No trades executed **today** ({actual_today}).\n\n"
                                f"{drift_line}\n\n"
                                f"Overall paper P/L: **${paper_pl:,.2f}** ({pct:.2f}%)"
                            )
                        logger.info("Returning conversational P/L response")
                    else:
                        response_text = (
                            "I couldn't retrieve your P/L data right now. "
                            "Try asking 'Are we ready to trade?' for status."
                        )
                        logger.warning("Direct P/L query but no portfolio data")
                else:
                    # Fallback: Get current portfolio status from system_state.json
                    portfolio = get_current_portfolio_status()
                    if portfolio:
                        live = portfolio.get("live", {})
                        paper = portfolio.get("paper", {})
                        trades_today = portfolio.get("trades_today", 0)
                        last_trade = portfolio.get("last_trade_date", "unknown")
                        actual_today = portfolio.get("actual_today", "unknown")

                        # Build trading activity message based on whether trades happened today
                        if trades_today > 0:
                            activity_msg = (
                                f"**Today ({actual_today}):** {trades_today} trades executed ✅"
                            )
                        else:
                            activity_msg = f"**Today ({actual_today}):** No trades yet\n**Last Trade:** {last_trade}"

                        response_text = f"""📊 Current Portfolio Status (Day {portfolio.get("challenge_day", "?")}/90)

**Live Account:**
- Equity: ${live.get("equity", 0):.2f}
- Total P/L: ${live.get("total_pl", 0):.2f} ({live.get("total_pl_pct", 0):.2f}%)
- Positions: {live.get("positions_count", 0)}

**Paper Account (R&D):**
- Equity: ${paper.get("equity", 0):,.2f}
- Total P/L: ${paper.get("total_pl", 0):,.2f} ({paper.get("total_pl_pct", 0):.2f}%)
- Win Rate: {paper.get("win_rate", 0):.1f}%
- Positions: {paper.get("positions_count", 0)}

{activity_msg}"""
                        logger.info("Returning portfolio status from system_state.json")
                    else:
                        # Final fallback: Clear message (don't dump lessons for P/L questions)
                        response_text = """📊 **Portfolio Status Unavailable**

I couldn't retrieve the current portfolio data. This may be because:
- The system state file is not accessible
- The GitHub repository data is unavailable

Please check directly:
- **Dashboard**: View your Alpaca paper/live account dashboard
- **Local System**: Run `cat data/system_state.json` for latest state

Or ask me about **lessons learned** instead (e.g., "What lessons did we learn about risk management?")"""
                        logger.warning("Trade query but no portfolio data available")
        else:
            # Query RAG system for relevant lessons (LanceDB-first)
            results, source = query_rag_hybrid(user_query, top_k=5)

            if not results:
                # Try broader search
                results, source = query_rag_hybrid("trading operational failure", top_k=3)

            # Format response based on source
            response_text = format_rag_response(results, user_query, source)

        logger.info(f"Returning response with {len(response_text)} chars")

        # Create RAG Webhook response
        response = create_webhook_response(sanitize_public_response_text(response_text))

        return JSONResponse(content=response)

    except Exception as e:
        # Security: Log full error but don't expose internals to client
        logger.error(f"Webhook error: {e}", exc_info=True)
        error_response = create_webhook_response(
            "An error occurred processing your request. Please try again."
        )
        return JSONResponse(content=error_response, status_code=200)


@app.get("/health")
async def health():
    """Health check endpoint."""
    rag = get_local_rag()
    # Count trades from local JSON files
    trade_count = len(query_trades("all", limit=1000))
    return {
        "status": "healthy",
        "local_lessons_loaded": len(rag.lessons),
        "critical_lessons": len(rag.get_critical_lessons()),
        "trades_loaded": trade_count,
        "trade_history_source": "system_state.json (Alpaca)",
        "rag_mode": "lancedb_first",
        "rag_last_source": rag.last_source,
    }


@app.get("/diagnostics")
async def diagnostics():
    """Detailed diagnostic information for RAG status."""
    import os

    rag = get_local_rag()
    return {
        "local_rag": {
            "lessons_loaded": len(rag.lessons),
            "critical_lessons": len(rag.get_critical_lessons()),
            "last_source": rag.last_source,
        },
        "system": {
            "python_path": os.getenv("PYTHONPATH", "NOT SET"),
            "working_dir": os.getcwd(),
            "lancedb_offline": os.getenv("LANCEDB_OFFLINE", "NOT SET"),
        },
    }


@app.get("/portfolio-status")
async def portfolio_status():
    """Return the freshest broker-backed portfolio snapshot available."""
    return build_live_system_state_snapshot()


@app.get("/")
async def root():
    """Root endpoint with info."""
    rag = get_local_rag()
    trade_count = len(query_trades("all", limit=1000))
    return {
        "service": "Trading AI RAG Webhook",
        "version": "3.9.0",  # Fix trade data source priority - system_state.json first
        "local_lessons_loaded": len(rag.lessons),
        "trades_loaded": trade_count,
        "trade_history_source": "system_state.json (Alpaca)",
        "rag_mode": "lancedb_first",
        "rag_last_source": rag.last_source,
        "endpoints": {
            "/webhook": "POST - RAG Webhook (lessons + trades + readiness)",
            "/rag-search": "POST - RAG search (LanceDB-first, JSON response)",
            "/portfolio-status": "GET - Broker-backed portfolio snapshot for dashboard/status surfaces",
            "/health": "GET - Health check",
            "/diagnostics": "GET - Detailed diagnostic info for debugging",
            "/test": "GET - Test lessons query",
            "/test-trades": "GET - Test trade history query",
            "/test-readiness": "GET - Test trading readiness assessment",
        },
    }


@app.get("/test")
async def test_rag(query: str = "critical lessons"):
    """Test endpoint to verify lessons RAG is working."""
    results, source = query_rag_hybrid(query, top_k=3)

    formatted_results = [
        {
            "id": r.get("id", ""),
            "severity": r.get("severity", ""),
            "score": r.get("score", 0),
            "content_length": len(r.get("content", "")),
            "preview": r.get("snippet", "")[:200],
        }
        for r in results
    ]

    return {
        "query": query,
        "query_type": "lessons",
        "rag_source": source,
        "results_count": len(results),
        "results": formatted_results,
    }


@app.get("/test-trades")
async def test_trades(query: str = "recent trades"):
    """Test endpoint to verify trade history is working."""
    trades = query_trades(query, limit=10)
    total_trades = len(query_trades("all", limit=1000))
    return {
        "query": query,
        "query_type": "trades",
        "trade_history_source": "system_state.json (Alpaca)",
        "total_trade_count": total_trades,
        "results_count": len(trades),
        "results": [
            {
                "symbol": t.get("metadata", {}).get("symbol", "UNKNOWN"),
                "side": t.get("metadata", {}).get("side", ""),
                "outcome": t.get("metadata", {}).get("outcome", ""),
                "pnl": t.get("metadata", {}).get("pnl", 0),
                "preview": t.get("document", "")[:200],
            }
            for t in trades
        ],
    }


@app.get("/test-readiness")
async def test_readiness(
    query: str = "How ready are we for paper trading?",
    is_future: bool = False,
    is_paper: bool = True,
    is_live: bool = False,
):
    """
    Test endpoint to verify trading readiness assessment.

    Args:
        query: Optional query to parse context from (overrides explicit params)
        is_future: If True, evaluate for tomorrow/future trading
        is_paper: If True, evaluate paper trading mode
        is_live: If True, evaluate live trading mode
    """
    # Parse context from query if provided
    if query:
        context = parse_readiness_context(query)
        is_future = context["is_future"]
        is_paper = context["is_paper"]
        is_live = context["is_live"]

    try:
        assessment = assess_trading_readiness(
            is_future=is_future,
            is_paper=is_paper,
            is_live=is_live,
        )
        return {
            "query_type": "readiness",
            "query": query,
            "context": {
                "is_future": is_future,
                "is_paper": is_paper,
                "is_live": is_live,
            },
            "assessment": assessment,
            "formatted_response": sanitize_public_response_text(
                format_readiness_response(assessment)
            ),
        }
    except Exception as e:
        logger.error(f"test-readiness endpoint failed: {e}", exc_info=True)
        return {
            "query_type": "readiness",
            "query": query,
            "error": "Readiness assessment is temporarily unavailable.",
        }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104 - Required for Cloud Run
