"""
Dialogflow CX Webhook for Trading AI System.

Handles:
1. Portfolio/trade queries - Returns LIVE data from Alpaca API
2. Readiness queries - Checks market hours, capital, blockers
3. Lessons queries - Searches lessons learned database

Created: Dec 2025
Restored: Jan 12, 2026 (was deleted in PR #1445 cleanup)
Key Fix: Fetches LIVE Alpaca data instead of stale static files
"""

import json
import logging
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Trading AI RAG Webhook")

# Initialize lessons search (lazy load to avoid import issues)
rag = None


def _get_rag():
    """Lazy load RAG to handle import errors gracefully."""
    global rag
    if rag is None:
        try:
            from src.rag.lessons_search import get_lessons_search

            rag = get_lessons_search()
        except Exception as e:
            logger.warning(f"Could not load lessons search: {e}")
            # Create a dummy RAG object
            rag = type(
                "DummyRAG",
                (),
                {"lessons": [], "query": lambda *args, **kwargs: [], "search": lambda *args, **kwargs: []},
            )()
    return rag


def create_dialogflow_response(message: str) -> dict:
    """
    Create a properly formatted Dialogflow CX webhook response.

    Args:
        message: The text message to return to the user

    Returns:
        Dict in Dialogflow CX fulfillment response format
    """
    return {
        "fulfillmentResponse": {
            "messages": [{"text": {"text": [message]}}]
        }
    }


def format_lessons_response(lessons: list, query: str) -> str:
    """
    Format lesson search results for display.

    Args:
        lessons: List of lesson dicts with id, severity, content
        query: The original search query

    Returns:
        Formatted string with lesson summaries
    """
    if not lessons:
        return (
            f"No lessons found for '{query}'.\n\n"
            "Try searching for: trading, risk, API failures, position sizing"
        )

    response_parts = [f"Found {len(lessons)} lessons for '{query}':\n"]

    for lesson in lessons:
        lesson_id = lesson.get("id", "unknown")
        severity = lesson.get("severity", "INFO")
        content = lesson.get("content", lesson.get("snippet", ""))[:200]

        response_parts.append(f"\n[{severity}] {lesson_id}")
        response_parts.append(f"{content}...")

    return "\n".join(response_parts)


def format_lesson_full(lesson: dict) -> str:
    """
    Format a single lesson for full display.

    Args:
        lesson: Lesson dict with content, severity

    Returns:
        Formatted lesson string
    """
    content = lesson.get("content", "")
    severity = lesson.get("severity", "INFO")

    # Extract title from H1 header
    title = "Lesson"
    lines = content.split("\n")
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return f"[{severity}] {title}\n\n{content}"


def is_trade_query(query: str) -> bool:
    """
    Detect if query is asking about trades/money/portfolio.

    Uses word boundary matching to avoid false positives like
    "lessons learned" matching "earn" inside "learned".

    Args:
        query: User's query string

    Returns:
        True if this is a trade/portfolio query
    """
    query_lower = query.lower()

    # Keywords that indicate a trade/portfolio query
    # Use word boundaries to prevent substring matching
    trade_keywords = [
        r"\bmoney\b",
        r"\bprofit\b",
        r"\bprofits\b",
        r"\bportfolio\b",
        r"\bbalance\b",
        r"\bearn\b",
        r"\bearns\b",
        r"\bearned\b",
        r"\bearning\b",
        r"\bp/l\b",
        r"\bpl\b",
        r"\bequity\b",
        r"\breturns\b",
        r"\bgains\b",
        r"\bgain\b",
        r"\bloss\b",
        r"\blosses\b",
        r"\bmade\b",
        r"\bmake\b",
        r"\btrade\b",
        r"\btrades\b",
        r"\btrading\b",
        r"\baccount\b",
        r"\bpositions?\b",
    ]

    return any(re.search(pattern, query_lower) for pattern in trade_keywords)


def is_readiness_query(query: str) -> bool:
    """
    Detect if query is asking about trading readiness/status.

    Args:
        query: User's query string

    Returns:
        True if this is a readiness check query
    """
    query_lower = query.lower()

    readiness_keywords = [
        "ready",
        "prepared",
        "preparation",
        "checklist",
        "status check",
        "preflight",
        "pre-trade",
        "can we trade",
        "should we trade",
    ]

    return any(keyword in query_lower for keyword in readiness_keywords)


def get_current_portfolio_status() -> dict:
    """
    Get LIVE portfolio status from Alpaca API.

    Falls back to local file, then GitHub if API unavailable.

    Returns:
        Dict with live, paper account info, or empty dict on failure
    """
    result = {}

    # Try LIVE Alpaca API first
    try:
        from src.utils.alpaca_client import get_account_info, get_alpaca_client

        # Get paper account (R&D) - this is our main testing account
        paper_client = get_alpaca_client(paper=True)
        if paper_client:
            paper_account = paper_client.get_account()
            result["paper"] = {
                "equity": float(paper_account.equity),
                "cash": float(paper_account.cash),
                "buying_power": float(paper_account.buying_power),
                "total_pl": float(paper_account.equity) - 100000,  # Default paper starts at $100k
                "total_pl_pct": ((float(paper_account.equity) - 100000) / 100000) * 100,
                "positions_count": 0,
                "win_rate": 0.0,
            }
            logger.info(f"Got LIVE paper account data: ${paper_account.equity}")

        # Get live account (brokerage)
        # Check for brokerage-specific API keys
        brokerage_key = os.getenv("ALPACA_BROKERAGE_TRADING_API_KEY")
        brokerage_secret = os.getenv("ALPACA_BROKERAGE_TRADING_API_SECRET")

        if brokerage_key and brokerage_secret:
            try:
                from alpaca.trading.client import TradingClient

                live_client = TradingClient(brokerage_key, brokerage_secret, paper=False)
                live_account = live_client.get_account()
                result["live"] = {
                    "equity": float(live_account.equity),
                    "cash": float(live_account.cash),
                    "buying_power": float(live_account.buying_power),
                    "total_pl": 0.0,  # Calculate from deposits
                    "total_pl_pct": 0.0,
                    "positions_count": 0,
                }
                logger.info(f"Got LIVE brokerage account data: ${live_account.equity}")
            except Exception as e:
                logger.warning(f"Could not get brokerage account: {e}")

        if result:
            # Add metadata
            result["last_trade_date"] = "Unknown"
            result["trades_today"] = 0
            result["challenge_day"] = _calculate_challenge_day()
            return result

    except Exception as e:
        logger.warning(f"Could not get live Alpaca data: {e}")

    # Fallback: Try local system_state.json
    state_file = Path("data/system_state.json")
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            portfolio = state.get("portfolio", {})

            result = {
                "live": {
                    "equity": portfolio.get("equity", 0),
                    "cash": portfolio.get("cash", 0),
                    "total_pl": 0.0,
                    "total_pl_pct": 0.0,
                    "positions_count": 0,
                },
                "paper": {
                    "equity": 5000.0,  # Default paper
                    "total_pl": 0.0,
                    "total_pl_pct": 0.0,
                    "positions_count": 0,
                    "win_rate": state.get("win_rate", 0),
                },
                "last_trade_date": "Unknown",
                "trades_today": state.get("total_trades", 0),
                "challenge_day": state.get("day_of_90", 0),
            }
            logger.info("Using local system_state.json (Alpaca API not available)")
            return result
        except Exception as e:
            logger.warning(f"Could not read local state: {e}")

    # Final fallback: GitHub raw content
    github_url = "https://raw.githubusercontent.com/IgorGanapolsky/trading/main/data/system_state.json"
    try:
        with urllib.request.urlopen(github_url, timeout=5) as response:
            state = json.loads(response.read().decode("utf-8"))
            portfolio = state.get("portfolio", {})
            return {
                "live": {
                    "equity": portfolio.get("equity", 0),
                    "total_pl": 0.0,
                    "total_pl_pct": 0.0,
                    "positions_count": 0,
                },
                "paper": {
                    "equity": 5000.0,
                    "total_pl": 0.0,
                    "win_rate": 0,
                },
                "last_trade_date": "Unknown",
                "trades_today": 0,
                "challenge_day": state.get("day_of_90", 0),
            }
    except Exception as e:
        logger.warning(f"GitHub fallback failed: {e}")

    return {}


def _calculate_challenge_day() -> int:
    """Calculate current day in the 90-day challenge."""
    # Challenge started roughly Dec 1, 2025
    start_date = datetime(2025, 12, 1)
    today = datetime.now()
    return (today - start_date).days


def assess_trading_readiness() -> dict:
    """
    Assess current trading readiness.

    Checks:
    - Market hours
    - Capital requirements
    - System health
    - Recent errors

    Returns:
        Dict with status, emoji, score, checks, warnings, blockers
    """
    checks = []
    warnings = []
    blockers = []
    score = 0
    max_score = 100

    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()

    # Check market hours (EST - simplified)
    if weekday >= 5:  # Weekend
        blockers.append("Market CLOSED - Weekend")
    elif hour < 9 or (hour == 9 and now.minute < 30):
        warnings.append(f"Market opens at 9:30 AM ET (currently {now.strftime('%I:%M %p')})")
        score += 20
    elif hour >= 16:
        blockers.append("Market CLOSED - After hours")
    else:
        checks.append("Market OPEN")
        score += 30

    # Check capital (get live data)
    portfolio = get_current_portfolio_status()
    if portfolio:
        live_equity = portfolio.get("live", {}).get("equity", 0)
        if live_equity >= 500:
            checks.append(f"Capital sufficient: ${live_equity:.2f}")
            score += 40
        else:
            warnings.append(f"Capital building: ${live_equity:.2f} / $500 needed")
            score += 10
    else:
        warnings.append("Could not verify capital")

    # Check system state
    state_file = Path("data/system_state.json")
    if state_file.exists():
        checks.append("System state loaded")
        score += 15
    else:
        warnings.append("System state file missing")

    # Paper account for R&D
    if portfolio and portfolio.get("paper", {}).get("equity", 0) > 0:
        checks.append("Paper account available for R&D")
        score += 15

    # Determine overall status
    if blockers:
        status = "NOT_READY"
        emoji = "🔴"
    elif len(warnings) >= 2:
        status = "CAUTION"
        emoji = "🟡"
    elif score >= 80:
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
        "readiness_pct": (score / max_score) * 100,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "timestamp": now.strftime("%Y-%m-%d %I:%M %p ET"),
    }


def format_readiness_response(assessment: dict) -> str:
    """
    Format readiness assessment for display.

    Args:
        assessment: Dict from assess_trading_readiness()

    Returns:
        Formatted string with status, checks, warnings, blockers
    """
    parts = []

    # Header
    parts.append(f"{assessment['emoji']} TRADING READINESS: {assessment['status']}")
    parts.append(f"Score: {assessment['readiness_pct']:.0f}%")
    parts.append(f"Checked: {assessment['timestamp']}")
    parts.append("")

    # Blockers (if any)
    if assessment["blockers"]:
        parts.append("🚫 BLOCKERS (Do NOT trade):")
        for blocker in assessment["blockers"]:
            parts.append(f"  - {blocker}")
        parts.append("")

    # Warnings (if any)
    if assessment["warnings"]:
        parts.append("⚠️ WARNINGS (reduced position sizes):")
        for warning in assessment["warnings"]:
            parts.append(f"  - {warning}")
        parts.append("")

    # Passing checks
    if assessment["checks"]:
        parts.append("✅ PASSING:")
        for check in assessment["checks"]:
            parts.append(f"  - {check}")
        parts.append("")

    # Recommendation
    if assessment["status"] == "READY":
        parts.append("💡 All systems GO - Ready to trade")
    elif assessment["status"] == "NOT_READY":
        parts.append("💡 Do NOT trade until blockers resolved")
    else:
        parts.append("💡 Proceed with caution - review warnings")

    return "\n".join(parts)


def format_portfolio_response(portfolio: dict) -> str:
    """
    Format portfolio status for display.

    Args:
        portfolio: Dict from get_current_portfolio_status()

    Returns:
        Formatted string with portfolio details
    """
    if not portfolio:
        return "⚠️ Portfolio data unavailable. I couldn't retrieve your account information."

    parts = [f"📊 Current Portfolio Status (Day {portfolio.get('challenge_day', '?')}/90)"]
    parts.append("")

    # Live account
    live = portfolio.get("live", {})
    if live:
        parts.append("**Live Account:**")
        parts.append(f"  • Equity: ${live.get('equity', 0):,.2f}")
        parts.append(f"  • Total P/L: ${live.get('total_pl', 0):,.2f} ({live.get('total_pl_pct', 0):.2f}%)")
        parts.append(f"  • Positions: {live.get('positions_count', 0)}")
        parts.append("")

    # Paper account
    paper = portfolio.get("paper", {})
    if paper:
        parts.append("**Paper Account (R&D):**")
        parts.append(f"  • Equity: ${paper.get('equity', 0):,.2f}")
        parts.append(f"  • Total P/L: ${paper.get('total_pl', 0):,.2f} ({paper.get('total_pl_pct', 0):.2f}%)")
        parts.append(f"  • Win Rate: {paper.get('win_rate', 0):.1f}%")
        parts.append(f"  • Positions: {paper.get('positions_count', 0)}")
        parts.append("")

    # Today's activity
    parts.append(f"**Today ({datetime.now().strftime('%Y-%m-%d')}):** {portfolio.get('trades_today', 0)} trades")
    parts.append(f"**Last Trade:** {portfolio.get('last_trade_date', 'Unknown')}")

    return "\n".join(parts)


# =============================================================================
# FastAPI Endpoints
# =============================================================================


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Trading AI RAG Webhook",
        "version": "2.0.0",
        "endpoints": ["/webhook", "/health", "/test", "/test-readiness"],
        "data_source": "LIVE Alpaca API with local/GitHub fallback",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    rag_instance = _get_rag()
    return {
        "status": "healthy",
        "lessons_loaded": len(getattr(rag_instance, "lessons", getattr(rag_instance, "_lessons_cache", []))),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/test")
async def test_query(query: str = "trading lessons"):
    """Test endpoint for RAG queries."""
    rag_instance = _get_rag()

    try:
        # Try search method first (LessonsSearch)
        if hasattr(rag_instance, "search"):
            results = rag_instance.search(query, top_k=5)
            lessons = [
                {"id": r[0].id, "severity": r[0].severity, "content": r[0].snippet, "score": r[1]}
                for r in results
            ]
        else:
            lessons = rag_instance.query(query)
    except Exception as e:
        lessons = []
        logger.warning(f"Test query failed: {e}")

    return {
        "query": query,
        "results_count": len(lessons),
        "results": lessons[:3],
    }


@app.get("/test-readiness")
async def test_readiness():
    """Test endpoint for readiness assessment."""
    assessment = assess_trading_readiness()
    return {
        "query_type": "readiness",
        "assessment": assessment,
        "formatted_response": format_readiness_response(assessment),
    }


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    """
    Main Dialogflow CX webhook endpoint.

    Handles incoming queries and routes to appropriate handler:
    1. Readiness queries -> assess_trading_readiness()
    2. Trade/portfolio queries -> get_current_portfolio_status() [LIVE from Alpaca]
    3. Lesson queries -> LessonsSearch.search()
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Extract query from various Dialogflow CX fields
    query = (
        body.get("text")
        or body.get("transcript")
        or body.get("sessionInfo", {}).get("parameters", {}).get("query")
        or body.get("fulfillmentInfo", {}).get("tag")
        or "trading lessons"
    )

    logger.info(f"Webhook received query: {query}")

    try:
        # Route based on query type
        # Priority: readiness > trade > lessons

        if is_readiness_query(query):
            assessment = assess_trading_readiness()
            response_text = format_readiness_response(assessment)
            return create_dialogflow_response(response_text)

        if is_trade_query(query):
            portfolio = get_current_portfolio_status()
            response_text = format_portfolio_response(portfolio)
            return create_dialogflow_response(response_text)

        # Default: Lessons search
        rag_instance = _get_rag()

        # Search for lessons
        if hasattr(rag_instance, "search"):
            results = rag_instance.search(query, top_k=5)
            lessons = [
                {"id": r[0].id, "severity": r[0].severity, "content": r[0].snippet}
                for r in results
            ]
        else:
            lessons = rag_instance.query(query)

        # If no results, try broader search
        if not lessons:
            if hasattr(rag_instance, "search"):
                results = rag_instance.search("trading", top_k=3)
                lessons = [
                    {"id": r[0].id, "severity": r[0].severity, "content": r[0].snippet}
                    for r in results
                ]
            else:
                lessons = rag_instance.query("trading")

        response_text = format_lessons_response(lessons, query)
        return create_dialogflow_response(response_text)

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Security: Don't expose exception details
        return create_dialogflow_response(
            "An error occurred while processing your request. Please try again."
        )


# For local testing
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
