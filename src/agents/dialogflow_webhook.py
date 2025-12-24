"""
Dialogflow CX Webhook for Trading AI RAG System.

This webhook connects Vertex AI Agent Builder / Dialogflow to our
lessons learned RAG database, enabling the agent to answer questions
about trading strategies, past mistakes, and system behavior.

Deploy with: gcloud run deploy trading-webhook --source .
"""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Import our RAG system
from src.rag.lessons_learned_rag import LessonsLearnedRAG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Trading AI Dialogflow Webhook")

# Initialize RAG on startup
rag = LessonsLearnedRAG()


def format_dialogflow_response(text: str, session_info: dict | None = None) -> dict:
    """Format response for Dialogflow CX webhook."""
    response = {"fulfillment_response": {"messages": [{"text": {"text": [text]}}]}}
    if session_info:
        response["session_info"] = session_info
    return response


def search_rag_knowledge(query: str, top_k: int = 3) -> str:
    """Search RAG knowledge base and format results."""
    results = rag.search(query, top_k=top_k)

    if not results:
        return (
            "I couldn't find specific information about that in my knowledge base. "
            "Could you rephrase your question or ask about trading strategies, "
            "lessons learned, or system behavior?"
        )

    # Format results into a coherent response
    response_parts = []

    for lesson, score in results:
        if score > 0.1:  # Only include relevant results
            # Extract key info from snippet
            snippet = lesson.snippet[:300].strip()
            if snippet:
                response_parts.append(f"**{lesson.id}** ({lesson.severity}): {snippet}")

    if not response_parts:
        return (
            "I found some related information but nothing directly answers your question. "
            "Try asking about specific topics like 'crypto trading', 'risk management', "
            "or 'system failures'."
        )

    intro = "Based on our lessons learned:\n\n"
    return intro + "\n\n".join(response_parts[:3])


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {
        "status": "healthy",
        "lessons_loaded": len(rag.lessons),
        "critical_lessons": len(rag.get_critical_lessons()),
    }


@app.post("/webhook")
async def dialogflow_webhook(request: Request) -> JSONResponse:
    """
    Handle Dialogflow CX webhook requests.

    Dialogflow sends POST requests with the user's query and session info.
    We search our RAG database and return relevant answers.
    """
    try:
        body = await request.json()
        logger.info(
            f"Received webhook request: {body.get('intentInfo', {}).get('displayName', 'unknown')}"
        )

        # Extract the user's query
        # Dialogflow CX uses 'text' in the query input
        text_input = body.get("text", "")

        # Also check fulfillmentInfo for the query
        if not text_input:
            fulfillment_info = body.get("fulfillmentInfo", {})
            text_input = fulfillment_info.get("tag", "")

        # Check transcript for the actual user message
        if not text_input:
            transcript = body.get("transcript", "")
            text_input = transcript

        # Last resort: check messages
        if not text_input:
            messages = body.get("messages", [])
            if messages:
                text_input = messages[-1].get("text", {}).get("text", [""])[0]

        # Get query from session parameters if still not found
        if not text_input:
            session_info = body.get("sessionInfo", {})
            parameters = session_info.get("parameters", {})
            text_input = parameters.get("user_query", parameters.get("query", ""))

        if not text_input:
            # Default to the intent if no text found
            intent_info = body.get("intentInfo", {})
            text_input = intent_info.get("displayName", "general question")

        logger.info(f"Processing query: {text_input}")

        # Search RAG knowledge base
        answer = search_rag_knowledge(text_input)

        # Format and return response
        response = format_dialogflow_response(answer)
        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        error_response = format_dialogflow_response(
            "I encountered an error processing your request. Please try again."
        )
        return JSONResponse(content=error_response, status_code=200)


@app.post("/")
async def root_webhook(request: Request) -> JSONResponse:
    """Alternative endpoint for webhook (some Dialogflow configs use root)."""
    return await dialogflow_webhook(request)


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host=host, port=port)
