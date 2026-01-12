"""
Dialogflow CX Webhook for Trading AI RAG System.

This webhook receives queries from Vertex AI Dialogue Agent and returns
full, untruncated lessons learned AND trade history from our RAG knowledge base.

Deployed to Cloud Run at: https://trading-dialogflow-webhook-cqlewkvzdq-uc.a.run.app

Updated Jan 2026: Added trade history queries
Security Update Jan 10, 2026: Added SSL verification, rate limiting, webhook auth
"""

import logging
import os
import ssl
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
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

from src.rag.lessons_learned_rag import LessonsLearnedRAG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Webhook authentication token (set in Cloud Run environment)
WEBHOOK_AUTH_TOKEN = os.environ.get("DIALOGFLOW_WEBHOOK_TOKEN", "")

# Initialize FastAPI app
app = FastAPI(
    title="Trading AI RAG Webhook",
    description="Dialogflow CX webhook for lessons AND trade history queries",
    version="2.9.0",  # Security: SSL verification, rate limiting, webhook auth
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


# Initialize RAG system for lessons
rag = LessonsLearnedRAG()
logger.info(f"RAG initialized with {len(rag.lessons)} lessons")

# Trade history is now loaded from local JSON files
# ChromaDB was removed Jan 8, 2026 per CLAUDE.md directive
logger.info("Trade history loaded from local JSON files (ChromaDB removed)")


def get_current_portfolio_status() -> dict:
    """Get current portfolio status from system_state.json (local or GitHub)."""
    import json
    from datetime import datetime, timezone

    state = None

    # Try local file first
    state_path = project_root / "data" / "system_state.json"
    try:
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)
            logger.info("Loaded portfolio from local system_state.json")
    except Exception as e:
        logger.warning(f"Failed to read local system state: {e}")

    # Fallback: Fetch from GitHub if local file unavailable
    if not state:
        try:
            import urllib.request

            github_url = "https://raw.githubusercontent.com/IgorGanapolsky/trading/main/data/system_state.json"
            # Security: Use verified SSL context (fixes MitM vulnerability)
            ssl_context = ssl.create_default_context()
            with urllib.request.urlopen(github_url, timeout=5, context=ssl_context) as response:
                state = json.loads(response.read().decode("utf-8"))
            logger.info("Loaded portfolio from GitHub system_state.json")
        except Exception as e:
            logger.warning(f"Failed to fetch from GitHub: {e}")

    if not state:
        return {}

    # Get actual today's date (US Eastern for market hours)
    try:
        from zoneinfo import ZoneInfo

        today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except ImportError:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Get last trade date and count from state
    last_trade_date = state.get("trades", {}).get("last_trade_date", "unknown")
    stored_trades_today = state.get("trades", {}).get("total_trades_today", 0)

    # CRITICAL FIX: Only show trades_today if the last_trade_date matches actual today
    # Otherwise, 0 trades have occurred today
    if last_trade_date == today_str:
        trades_today = stored_trades_today
    else:
        trades_today = 0  # No trades today - the stored count is from a previous day

    return {
        "live": {
            "equity": state.get("account", {}).get("current_equity", 0),
            "total_pl": state.get("account", {}).get("total_pl", 0),
            "total_pl_pct": state.get("account", {}).get("total_pl_pct", 0),
            "positions_count": state.get("account", {}).get("positions_count", 0),
        },
        "paper": {
            "equity": state.get("paper_account", {}).get("current_equity", 0),
            "total_pl": state.get("paper_account", {}).get("total_pl", 0),
            "total_pl_pct": state.get("paper_account", {}).get("total_pl_pct", 0),
            "positions_count": state.get("paper_account", {}).get("positions_count", 0),
            "win_rate": state.get("paper_account", {}).get("win_rate", 0),
        },
        "last_trade_date": last_trade_date,
        "trades_today": trades_today,
        "actual_today": today_str,
        "challenge_day": state.get("challenge", {}).get("current_day", 0),
    }


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

    # Fallback to GitHub if local not available
    if state is None:
        try:
            import urllib.request

            github_url = "https://raw.githubusercontent.com/IgorGanapolsky/trading/main/data/system_state.json"
            # Security: Use verified SSL context (fixes MitM vulnerability)
            ssl_context = ssl.create_default_context()
            with urllib.request.urlopen(github_url, timeout=5, context=ssl_context) as response:
                state = json.loads(response.read().decode("utf-8"))
            checks.append("System state loaded (GitHub)")
            score += 10
        except Exception as e:
            warnings.append(f"System state not found (local or GitHub): {str(e)[:30]}")

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
            except Exception:
                warnings.append("Could not verify state freshness")

    # 3. CAPITAL CHECK (context-aware: paper vs live)
    max_score += 20
    if state:
        paper_equity = state.get("paper_account", {}).get("current_equity", 0)
        live_equity = state.get("account", {}).get("current_equity", 0)

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
    except Exception:
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

    # 6. TRADING AUTOMATION CHECK (Critical - added Jan 6, 2026)
    max_score += 20
    if state:
        last_trade_date = state.get("trades", {}).get("last_trade_date", "")
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
                    blockers.append(
                        f"🚨 AUTOMATION BROKEN: No trades for {days_since_trade} days! "
                        f"(last trade: {last_trade_date}) Check GitHub Actions secrets!"
                    )
            except Exception:
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
    """Query trade history from local JSON files."""
    import json

    trades = []
    data_dir = project_root / "data"

    try:
        # Get trades from recent JSON files
        for trades_file in sorted(data_dir.glob("trades_*.json"), reverse=True):
            if len(trades) >= limit:
                break

            with open(trades_file) as f:
                file_trades = json.load(f)
                for trade in file_trades:
                    # Build document string like ChromaDB did
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

        return trades[:limit]

    except Exception as e:
        logger.error(f"Trade query failed: {e}")
        return []


def format_trades_response(trades: list, query: str) -> str:
    """Format trade history into a response."""
    if not trades:
        return f"No trades found matching '{query}'. The trade history may be empty or the query didn't match any trades."

    response_parts = [f"📊 **Trade History** (found {len(trades)} trades):\n"]

    for i, trade in enumerate(trades, 1):
        doc = trade.get("document", "")
        meta = trade.get("metadata", {})

        symbol = meta.get("symbol", "UNKNOWN")
        side = meta.get("side", "").upper()
        outcome = meta.get("outcome", "unknown")
        pnl = meta.get("pnl", 0)
        timestamp = meta.get("timestamp", "")[:10]

        outcome_emoji = "✅" if outcome == "profitable" else ("❌" if outcome == "loss" else "➖")

        response_parts.append(
            f"\n{i}. {outcome_emoji} **{symbol}** {side} | P/L: ${pnl:.2f} | {timestamp}\n"
            f"   {doc[:200]}...\n"
        )

    return "\n".join(response_parts)


def create_dialogflow_response(text: str) -> dict:
    """
    Create a Dialogflow CX webhook response.

    IMPORTANT: We set the FULL text here. Dialogflow should not truncate
    this response. If truncation occurs, check:
    1. Cloud Run timeout (should be 60s)
    2. Dialogflow webhook timeout (should be 30s)
    3. Agent response settings in Dialogflow CX console
    """
    return {"fulfillmentResponse": {"messages": [{"text": {"text": [text]}}]}}


def verify_webhook_auth(authorization: str | None = Header(None)) -> bool:
    """
    Verify webhook authentication token.

    Security: Validates bearer token if DIALOGFLOW_WEBHOOK_TOKEN is set.
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
    authorization: str | None = Header(None),
) -> JSONResponse:
    """
    Handle Dialogflow CX webhook requests.

    Security:
    - Rate limited to 100 requests/minute per IP (if slowapi installed)
    - Authenticated via bearer token (if DIALOGFLOW_WEBHOOK_TOKEN configured)

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

        logger.info(f"Processing query: {user_query}")

        # Determine query type and route accordingly
        # Check readiness queries FIRST (highest priority)
        if is_readiness_query(user_query):
            logger.info(f"Detected READINESS query: {user_query}")
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

        elif is_trade_query(user_query):
            # Query trade history from local JSON files
            logger.info(f"Detected TRADE query: {user_query}")
            trades = query_trades(user_query, limit=10)

            if trades:
                response_text = format_trades_response(trades, user_query)
                logger.info(f"Returning {len(trades)} trades")
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
            # Query RAG system for relevant lessons
            results = rag.query(user_query, top_k=3)

            if not results:
                # Try broader search
                results = rag.query("trading operational failure", top_k=3)

            # Format FULL response (no truncation)
            response_text = format_lessons_response(results, user_query)

        logger.info(f"Returning response with {len(response_text)} chars")

        # Create Dialogflow response
        response = create_dialogflow_response(response_text)

        return JSONResponse(content=response)

    except Exception as e:
        # Security: Log full error but don't expose internals to client
        logger.error(f"Webhook error: {e}", exc_info=True)
        error_response = create_dialogflow_response(
            "An error occurred processing your request. Please try again."
        )
        return JSONResponse(content=error_response, status_code=200)


@app.get("/health")
async def health():
    """Health check endpoint."""
    # Count trades from local JSON files
    trade_count = len(query_trades("all", limit=1000))
    return {
        "status": "healthy",
        "lessons_loaded": len(rag.lessons),
        "critical_lessons": len(rag.get_critical_lessons()),
        "trades_loaded": trade_count,
        "trade_history_source": "local_json",
    }


@app.get("/")
async def root():
    """Root endpoint with info."""
    trade_count = len(query_trades("all", limit=1000))
    return {
        "service": "Trading AI RAG Webhook",
        "version": "2.9.0",  # Security: SSL verification, rate limiting, webhook auth
        "lessons_loaded": len(rag.lessons),
        "trades_loaded": trade_count,
        "trade_history_source": "local_json",
        "endpoints": {
            "/webhook": "POST - Dialogflow CX webhook (lessons + trades + readiness)",
            "/health": "GET - Health check",
            "/test": "GET - Test lessons query",
            "/test-trades": "GET - Test trade history query",
            "/test-readiness": "GET - Test trading readiness assessment",
        },
    }


@app.get("/test")
async def test_rag(query: str = "critical lessons"):
    """Test endpoint to verify lessons RAG is working."""
    results = rag.query(query, top_k=3)
    return {
        "query": query,
        "query_type": "lessons",
        "results_count": len(results),
        "results": [
            {
                "id": r["id"],
                "severity": r["severity"],
                "score": r["score"],
                "content_length": len(r.get("content", "")),
                "preview": r.get("snippet", "")[:200],
            }
            for r in results
        ],
    }


@app.get("/test-trades")
async def test_trades(query: str = "recent trades"):
    """Test endpoint to verify trade history is working."""
    trades = query_trades(query, limit=10)
    total_trades = len(query_trades("all", limit=1000))
    return {
        "query": query,
        "query_type": "trades",
        "trade_history_source": "local_json",
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
        "formatted_response": format_readiness_response(assessment),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104 - Required for Cloud Run
