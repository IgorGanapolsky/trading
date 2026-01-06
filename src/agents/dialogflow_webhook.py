"""
Dialogflow CX Webhook for Trading AI RAG System.

This webhook receives queries from Vertex AI Dialogue Agent and returns
full, untruncated lessons learned AND trade history from our RAG knowledge base.

Deployed to Cloud Run at: https://trading-dialogflow-webhook-cqlewkvzdq-uc.a.run.app

Updated Jan 2026: Added trade history queries
"""

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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

# Initialize FastAPI app
app = FastAPI(
    title="Trading AI RAG Webhook",
    description="Dialogflow CX webhook for lessons AND trade history queries",
    version="2.5.0",  # Added: Trading readiness assessment for "How ready are we?" queries
)

# Initialize RAG system for lessons
rag = LessonsLearnedRAG()
logger.info(f"RAG initialized with {len(rag.lessons)} lessons")

# Initialize trade history ChromaDB
trade_collection = None
try:
    import chromadb
    from chromadb.config import Settings

    db_path = Path("data/vector_db")
    if db_path.exists():
        client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False),
        )
        trade_collection = client.get_or_create_collection(name="trade_history")
        logger.info(f"Trade history initialized: {trade_collection.count()} trades")
except Exception as e:
    logger.warning(f"Trade history not available: {e}")


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
            with urllib.request.urlopen(github_url, timeout=5) as response:  # noqa: S310 - trusted URL
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


def is_trade_query(query: str) -> bool:
    """Detect if query is about trades vs lessons."""
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
    return any(keyword in query_lower for keyword in trade_keywords)


def assess_trading_readiness() -> dict:
    """
    Assess trading readiness based on multiple factors.
    Returns a comprehensive readiness report with actionable insights.
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
        blockers.append("Market CLOSED - Weekend (Mon-Fri only)")
    elif current_time < market_open:
        minutes_to_open = market_open - current_time
        warnings.append(f"Market opens in {minutes_to_open} minutes ({now_et.strftime('%I:%M %p')} ET)")
        score += 10  # Partial credit - we're prepared
    elif current_time >= market_close:
        blockers.append(f"Market CLOSED - After hours ({now_et.strftime('%I:%M %p')} ET)")
    else:
        checks.append(f"Market OPEN ({now_et.strftime('%I:%M %p')} ET)")
        score += 20

    # 2. SYSTEM STATE CHECK
    max_score += 20
    state_path = project_root / "data" / "system_state.json"
    state = None
    try:
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)
            checks.append("System state loaded")
            score += 10
        else:
            warnings.append("System state file not found")
    except Exception as e:
        warnings.append(f"System state error: {str(e)[:50]}")

    # Check state freshness
    if state:
        last_updated = state.get("meta", {}).get("last_updated", "")
        if last_updated:
            try:
                update_time = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                hours_old = (datetime.now(update_time.tzinfo or None) - update_time).total_seconds() / 3600
                if hours_old < 4:
                    checks.append(f"State fresh ({hours_old:.1f}h old)")
                    score += 10
                else:
                    warnings.append(f"State stale ({hours_old:.1f}h old)")
            except Exception:
                warnings.append("Could not verify state freshness")

    # 3. CAPITAL CHECK
    max_score += 20
    if state:
        paper_equity = state.get("paper_account", {}).get("current_equity", 0)
        live_equity = state.get("account", {}).get("current_equity", 0)

        if paper_equity > 100000:
            checks.append(f"Paper equity healthy: ${paper_equity:,.2f}")
            score += 10
        elif paper_equity > 95000:
            warnings.append(f"Paper equity warning: ${paper_equity:,.2f}")
            score += 5
        else:
            blockers.append(f"Paper equity critical: ${paper_equity:,.2f}")

        if live_equity >= 200:
            checks.append(f"Live capital sufficient: ${live_equity:.2f}")
            score += 10
        else:
            target = state.get("account", {}).get("deposit_strategy", {}).get("target_for_first_trade", 200)
            remaining = target - live_equity
            warnings.append(f"Live capital building: ${live_equity:.2f} (need ${remaining:.0f} more for first trade)")

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

    # 5. WIN RATE CHECK
    max_score += 20
    if state:
        win_rate = state.get("paper_account", {}).get("win_rate", 0)
        if win_rate >= 60:
            checks.append(f"Win rate strong: {win_rate:.0f}%")
            score += 20
        elif win_rate >= 50:
            warnings.append(f"Win rate marginal: {win_rate:.0f}%")
            score += 10
        else:
            blockers.append(f"Win rate poor: {win_rate:.0f}%")

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
    }


def format_readiness_response(assessment: dict) -> str:
    """Format readiness assessment into a user-friendly response."""
    status = assessment["status"]
    emoji = assessment["emoji"]
    score = assessment["score"]
    max_score = assessment["max_score"]
    readiness_pct = assessment["readiness_pct"]

    response_parts = [
        f"{emoji} **TRADING READINESS: {status}** ({readiness_pct:.0f}%)",
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
        response_parts.append("📌 **Recommendation:** Proceed with reduced position sizes. Monitor closely.")
    elif status == "READY":
        response_parts.append("📌 **Recommendation:** All systems GO. Execute per strategy guidelines.")
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
    """Query trade history from ChromaDB."""
    if not trade_collection:
        return []

    try:
        results = trade_collection.query(
            query_texts=[query],
            n_results=limit,
            where={"type": "trade"},
        )

        trades = []
        if results["documents"] and results["metadatas"]:
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                trades.append(
                    {
                        "document": doc,
                        "metadata": meta,
                    }
                )
        return trades
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


@app.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
    """
    Handle Dialogflow CX webhook requests.

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
    try:
        body = await request.json()
        logger.info(f"Received webhook request: {body}")

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
            assessment = assess_trading_readiness()
            response_text = format_readiness_response(assessment)
            logger.info(f"Readiness assessment: {assessment['status']} ({assessment['readiness_pct']:.0f}%)")

        elif is_trade_query(user_query):
            # Query trade history from ChromaDB
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
        logger.error(f"Webhook error: {e}", exc_info=True)
        error_response = create_dialogflow_response(
            f"Error processing request: {str(e)}. Please try again."
        )
        return JSONResponse(content=error_response, status_code=200)


@app.get("/health")
async def health():
    """Health check endpoint."""
    trade_count = trade_collection.count() if trade_collection else 0
    return {
        "status": "healthy",
        "lessons_loaded": len(rag.lessons),
        "critical_lessons": len(rag.get_critical_lessons()),
        "trades_loaded": trade_count,
        "trade_history_available": trade_collection is not None,
    }


@app.get("/")
async def root():
    """Root endpoint with info."""
    trade_count = trade_collection.count() if trade_collection else 0
    return {
        "service": "Trading AI RAG Webhook",
        "version": "2.5.0",
        "lessons_loaded": len(rag.lessons),
        "trades_loaded": trade_count,
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
    return {
        "query": query,
        "query_type": "trades",
        "trade_collection_available": trade_collection is not None,
        "trade_count": trade_collection.count() if trade_collection else 0,
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
async def test_readiness():
    """Test endpoint to verify trading readiness assessment."""
    assessment = assess_trading_readiness()
    return {
        "query_type": "readiness",
        "assessment": assessment,
        "formatted_response": format_readiness_response(assessment),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104 - Required for Cloud Run
