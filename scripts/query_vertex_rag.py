#!/usr/bin/env python3
"""
Query Vertex AI RAG for Pre-Trade Learning.

CEO Directive (Jan 7, 2026): "We are supposed to be LEARNING from Vertex AI RAG,
not just writing to it!"

This script queries the Vertex AI RAG corpus for relevant lessons BEFORE trading,
enabling true bidirectional learning:
- WRITE: Trades sync to RAG after execution (sync_trades_to_rag.py)
- READ: Query RAG for lessons BEFORE trading (this script)

Usage:
    # Query for today's trading context
    python3 scripts/query_vertex_rag.py

    # Query for specific symbol
    python3 scripts/query_vertex_rag.py --symbol AAPL

    # Query for specific topic
    python3 scripts/query_vertex_rag.py --query "stop loss lessons"

    # Output JSON for CI integration
    python3 scripts/query_vertex_rag.py --json --output data/rag_advice.json
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_vertex_rag_client():
    """Initialize Vertex AI RAG client with proper credentials."""
    try:
        # Check for service account key
        sa_key = os.getenv("GCP_SA_KEY")
        if sa_key:
            import json as json_lib
            import tempfile

            # Write SA key to temp file for auth
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                f.write(sa_key)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name

            # Extract project ID from SA key
            sa_data = json_lib.loads(sa_key)
            project_id = sa_data.get("project_id", "igor-trading-2025-v2")
        else:
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "igor-trading-2025-v2")

        from google.cloud import aiplatform

        aiplatform.init(project=project_id, location="us-central1")

        return project_id

    except ImportError as e:
        logger.error(f"Vertex AI SDK not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}")
        return None


def query_rag_corpus(query_text: str, top_k: int = 5) -> list[dict]:
    """
    Query the Vertex AI RAG corpus for relevant documents.

    Args:
        query_text: Natural language query
        top_k: Number of results to return

    Returns:
        List of relevant documents with scores
    """
    try:
        from vertexai.preview import rag
        from vertexai.preview.generative_models import GenerativeModel

        # Get corpus
        corpus_name = None
        corpora = rag.list_corpora()
        for corpus in corpora:
            if corpus.display_name == "trading-system-rag":
                corpus_name = corpus.name
                break

        if not corpus_name:
            logger.info("RAG corpus 'trading-system-rag' not found - creating it...")
            try:
                corpus = rag.create_corpus(
                    display_name="trading-system-rag",
                    description="Trade history, lessons learned, and market insights for Igor's trading system",
                )
                corpus_name = corpus.name
                logger.info(f"Created RAG corpus: {corpus_name}")
            except Exception as e:
                logger.warning(f"Failed to create corpus: {e}")
                return []

        # Create retrieval tool
        rag_retrieval_tool = rag.Retrieval(
            source=rag.VertexRagStore(
                rag_corpora=[corpus_name],
                similarity_top_k=top_k,
            ),
        )

        # Query with Gemini + RAG
        model = GenerativeModel(
            model_name="gemini-1.5-flash",
            tools=[rag_retrieval_tool],
        )

        prompt = f"""Based on the trading lessons and history in the RAG corpus, answer this query:

Query: {query_text}

Provide specific, actionable advice based on past trades and lessons learned.
Include relevant lesson IDs if available."""

        response = model.generate_content(prompt)

        # Extract response
        results = []
        if hasattr(response, "candidates") and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, "content"):
                    for part in candidate.content.parts:
                        if hasattr(part, "text"):
                            results.append(
                                {
                                    "text": part.text,
                                    "query": query_text,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                            )

        return results

    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        return []


def get_pretrade_advice(symbols: list[str] = None) -> dict:
    """
    Get comprehensive pre-trade advice from Vertex AI RAG.

    This is the main entry point for the bidirectional learning system.

    Args:
        symbols: List of symbols being considered for trading

    Returns:
        Dictionary with advice categories
    """
    advice = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbols": symbols or [],
        "general_advice": [],
        "symbol_specific": {},
        "risk_warnings": [],
        "recent_lessons": [],
    }

    # General trading lessons
    general_queries = [
        "What are the most important risk management lessons?",
        "What mistakes should I avoid when trading options?",
        "What are the key Phil Town Rule 1 principles?",
    ]

    for query in general_queries:
        results = query_rag_corpus(query, top_k=3)
        if results:
            advice["general_advice"].extend(results)

    # Symbol-specific advice
    if symbols:
        for symbol in symbols:
            symbol_queries = [
                f"What lessons do we have about trading {symbol}?",
                f"What was our P/L history on {symbol}?",
            ]

            symbol_results = []
            for query in symbol_queries:
                results = query_rag_corpus(query, top_k=2)
                symbol_results.extend(results)

            if symbol_results:
                advice["symbol_specific"][symbol] = symbol_results

    # Risk warnings
    risk_queries = [
        "What critical failures have we had recently?",
        "What trades resulted in losses and why?",
    ]

    for query in risk_queries:
        results = query_rag_corpus(query, top_k=3)
        if results:
            advice["risk_warnings"].extend(results)

    # Recent lessons (last 7 days context)
    recent_query = "What are the most recent lessons learned from trading?"
    recent_results = query_rag_corpus(recent_query, top_k=5)
    if recent_results:
        advice["recent_lessons"] = recent_results

    return advice


def main():
    parser = argparse.ArgumentParser(
        description="Query Vertex AI RAG for pre-trade learning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--symbol",
        "-s",
        action="append",
        dest="symbols",
        help="Symbol to get specific advice for (can be used multiple times)",
    )
    parser.add_argument(
        "--query",
        "-q",
        help="Custom query to run against RAG",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (for CI integration)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("VERTEX AI RAG PRE-TRADE QUERY")
    print("Bidirectional Learning System - READ Phase")
    print("=" * 70)
    print()

    # Initialize Vertex AI
    project_id = get_vertex_rag_client()
    if not project_id:
        print("ERROR: Could not initialize Vertex AI RAG")
        print("Check GCP_SA_KEY or GOOGLE_CLOUD_PROJECT environment variables")
        sys.exit(1)

    print(f"Connected to project: {project_id}")
    print()

    # Run query or get full advice
    if args.query:
        # Single custom query
        print(f"Query: {args.query}")
        print("-" * 50)
        results = query_rag_corpus(args.query, top_k=5)

        if args.json:
            output_data = {"query": args.query, "results": results}
        else:
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result.get('text', 'No response')[:500]}")
            output_data = None
    else:
        # Full pre-trade advice
        print("Getting comprehensive pre-trade advice...")
        advice = get_pretrade_advice(symbols=args.symbols)

        if args.json:
            output_data = advice
        else:
            # Pretty print advice
            print("\n" + "=" * 70)
            print("GENERAL ADVICE")
            print("=" * 70)
            for i, item in enumerate(advice.get("general_advice", [])[:3], 1):
                print(f"\n{i}. {item.get('text', '')[:300]}...")

            if advice.get("symbol_specific"):
                print("\n" + "=" * 70)
                print("SYMBOL-SPECIFIC ADVICE")
                print("=" * 70)
                for symbol, items in advice["symbol_specific"].items():
                    print(f"\n{symbol}:")
                    for item in items[:2]:
                        print(f"  - {item.get('text', '')[:200]}...")

            print("\n" + "=" * 70)
            print("RISK WARNINGS")
            print("=" * 70)
            for i, item in enumerate(advice.get("risk_warnings", [])[:3], 1):
                print(f"\n{i}. {item.get('text', '')[:300]}...")

            output_data = advice

    # Save to file if requested
    if args.output and output_data:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nAdvice saved to: {args.output}")

    print("\n" + "=" * 70)
    print("RAG query complete - Apply these lessons to today's trading!")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
