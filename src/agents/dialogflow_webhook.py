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
    version="2.2.0",  # Fixed money/today query detection + system_state.json fallback
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
    """Get current portfolio status from system_state.json."""
    import json

    state_path = project_root / "data" / "system_state.json"
    try:
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)
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
                "last_trade_date": state.get("trades", {}).get("last_trade_date", "unknown"),
                "trades_today": state.get("trades", {}).get("total_trades_today", 0),
                "challenge_day": state.get("challenge", {}).get("current_day", 0),
            }
    except Exception as e:
        logger.error(f"Failed to read system state: {e}")
    return {}


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
        if is_trade_query(user_query):
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

**Today:** {portfolio.get("trades_today", 0)} trades executed
**Last Trade:** {portfolio.get("last_trade_date", "unknown")}

No new trades today. Markets are open - next execution at scheduled time."""
                    logger.info("Returning portfolio status from system_state.json")
                else:
                    # Final fallback: lessons
                    results = rag.query(user_query, top_k=3)
                    response_text = format_lessons_response(results, user_query)
                    response_text = (
                        f"No trade history found. Here are related lessons:\n\n{response_text}"
                    )
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
        "version": "2.0.0",
        "lessons_loaded": len(rag.lessons),
        "trades_loaded": trade_count,
        "endpoints": {
            "/webhook": "POST - Dialogflow CX webhook (lessons + trades)",
            "/health": "GET - Health check",
            "/test": "GET - Test lessons query",
            "/test-trades": "GET - Test trade history query",
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


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104 - Required for Cloud Run
