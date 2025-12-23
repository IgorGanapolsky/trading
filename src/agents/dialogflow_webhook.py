"""Dialogflow CX Webhook for Trading System RAG Integration.

Handles webhook requests from Dialogflow CX and queries the trading system's
RAG knowledge base (lessons learned, market intelligence, etc.).
"""

import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Import RAG components
try:
    from src.rag.lessons_learned_rag import LessonsLearnedRAG
except ImportError:
    # Handle import for when running in Docker
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.rag.lessons_learned_rag import LessonsLearnedRAG

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Trading System Dialogflow Webhook", version="1.0.0")

# Initialize RAG
rag = LessonsLearnedRAG()

# Log initialization
logger.info(f"Loaded {len(rag.lessons)} lessons into RAG")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "trading-webhook",
        "lessons_loaded": len(rag.lessons),
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "rag": {
            "lessons_loaded": len(rag.lessons),
            "critical_lessons": len(rag.get_critical_lessons()),
        },
    }


@app.post("/webhook")
async def webhook(request: Request):
    """Handle Dialogflow CX webhook requests.

    Expected request format from Dialogflow CX:
    {
        "sessionInfo": {...},
        "fulfillmentInfo": {...},
        "text": "user query text",
        "languageCode": "en",
        ...
    }
    """
    try:
        # Parse request
        body = await request.json()
        logger.info(f"Received webhook request: {body}")

        # Extract query text
        query_text = body.get("text", "")
        if not query_text:
            # Try alternative fields
            query_text = body.get("queryResult", {}).get("queryText", "")

        if not query_text:
            logger.warning("No query text found in request")
            return JSONResponse(
                content={
                    "fulfillmentResponse": {
                        "messages": [
                            {
                                "text": {
                                    "text": [
                                        "I didn't understand that. Could you rephrase your question?"
                                    ]
                                }
                            }
                        ]
                    }
                }
            )

        # Query RAG for relevant lessons
        results = rag.query(query_text, top_k=3)

        # Format response
        if not results:
            response_text = (
                f"I searched my knowledge base for '{query_text}', "
                "but couldn't find directly relevant lessons. "
                "Try asking about specific topics like 'trading strategies', "
                "'risk management', or 'calendar awareness'."
            )
        else:
            # Build response from top results
            response_parts = [f"Based on what I've learned about '{query_text}':\n"]

            for i, result in enumerate(results[:2], 1):
                snippet = result["snippet"][:300]
                severity = result["severity"]
                severity_emoji = "🔴" if severity == "CRITICAL" else "🟡" if severity == "HIGH" else "🟢"

                response_parts.append(
                    f"\n{severity_emoji} Lesson {i} ({severity}):\n{snippet}...\n"
                )

            if len(results) > 2:
                response_parts.append(
                    f"\n(Found {len(results)} total relevant lessons)"
                )

            response_text = "".join(response_parts)

        # Return Dialogflow CX webhook response format
        return JSONResponse(
            content={
                "fulfillmentResponse": {
                    "messages": [{"text": {"text": [response_text]}}]
                }
            }
        )

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "fulfillmentResponse": {
                    "messages": [
                        {
                            "text": {
                                "text": [
                                    f"Sorry, I encountered an error processing your request: {str(e)}"
                                ]
                            }
                        }
                    ]
                }
            },
        )


@app.post("/webhook/test")
async def webhook_test(request: Request):
    """Test endpoint for local development."""
    body = await request.json()
    query = body.get("query", "")

    results = rag.query(query, top_k=5)

    return {
        "query": query,
        "results_count": len(results),
        "results": results,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
