"""
Dialogflow CX Webhook for Trading AI RAG System.

This webhook receives queries from Vertex AI Dialogue Agent and returns
full, untruncated lessons learned from our RAG knowledge base.

Deployed to Cloud Run at: https://trading-dialogflow-webhook-cqlewkvzdq-uc.a.run.app
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
    description="Dialogflow CX webhook for lessons learned queries",
    version="1.0.0",
)

# Initialize RAG system
rag = LessonsLearnedRAG()
logger.info(f"RAG initialized with {len(rag.lessons)} lessons")


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

        # Query RAG system for relevant lessons
        results = rag.query(user_query, top_k=3)

        if not results:
            # Try broader search
            results = rag.query("trading operational failure", top_k=3)

        # Format FULL response (no truncation)
        response_text = format_lessons_response(results, user_query)

        logger.info(f"Returning response with {len(results)} lessons, {len(response_text)} chars")

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
    return {
        "status": "healthy",
        "lessons_loaded": len(rag.lessons),
        "critical_lessons": len(rag.get_critical_lessons()),
    }


@app.get("/")
async def root():
    """Root endpoint with info."""
    return {
        "service": "Trading AI RAG Webhook",
        "version": "1.0.0",
        "lessons_loaded": len(rag.lessons),
        "endpoints": {
            "/webhook": "POST - Dialogflow CX webhook",
            "/health": "GET - Health check",
            "/test": "GET - Test RAG query",
        },
    }


@app.get("/test")
async def test_rag(query: str = "critical lessons"):
    """Test endpoint to verify RAG is working."""
    results = rag.query(query, top_k=3)
    return {
        "query": query,
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


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104 - Required for Cloud Run
