#!/usr/bin/env python3
"""
Ingest Options Trading Books into RAG Vector Store

This script ingests options trading books (PDF format) into the RAG system
for semantic search and knowledge retrieval during trading decisions.

Primary Books:
1. "Options as a Strategic Investment" by Lawrence McMillan (5th Edition)
2. "Option Volatility and Pricing" by Sheldon Natenberg
3. "Volatility Trading" by Euan Sinclair

Usage:
    # Ingest a single book
    python scripts/ingest_options_books.py --pdf /path/to/mcmillan.pdf --book-id mcmillan_options

    # Ingest McMillan knowledge base (no PDF needed - uses built-in KB)
    python scripts/ingest_options_books.py --ingest-kb

    # Ingest all PDFs from a directory
    python scripts/ingest_options_books.py --dir /path/to/books/

    # Re-ingest (force refresh)
    python scripts/ingest_options_books.py --pdf /path/to/book.pdf --force

Author: AI Trading System
Date: December 2, 2025
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.collectors.mcmillan_options_collector import McMillanOptionsKnowledgeBase
from src.rag.collectors.options_book_collector import OptionsBookCollector
from src.rag.options_book_retriever import get_options_book_retriever
from src.rag.vector_db.chroma_client import get_rag_db
from src.rag.vector_db.embedder import get_embedder

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def ingest_pdf_book(pdf_path: str, book_id: str, force: bool = False) -> dict:
    """
    Ingest a single PDF book.

    Args:
        pdf_path: Path to PDF file
        book_id: Identifier for the book (e.g., 'mcmillan_options')
        force: Force re-ingestion even if already processed

    Returns:
        Dict with ingestion status and stats
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"INGESTING: {book_id}")
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"{'=' * 60}")

    collector = OptionsBookCollector()

    # Step 1: Ingest PDF
    result = collector.ingest_pdf(pdf_path=pdf_path, book_id=book_id, force_refresh=force)

    if result["status"] == "success":
        logger.info(f"PDF ingested: {result['chunks']} chunks from {result['pages']} pages")

        # Step 2: Add to vector store
        retriever = get_options_book_retriever()
        vector_result = retriever.ingest_options_books_to_vector_store()

        logger.info(f"Vector store: {vector_result['status']}")

        return {
            "status": "success",
            "book_id": book_id,
            "chunks": result["chunks"],
            "pages": result["pages"],
            "vector_store": vector_result["status"],
        }

    elif result["status"] == "already_ingested":
        logger.info("Book already ingested. Use --force to re-ingest.")
        return result

    else:
        logger.error(f"Ingestion failed: {result.get('message')}")
        return result


def ingest_mcmillan_knowledge_base() -> dict:
    """
    Ingest the built-in McMillan knowledge base into the vector store.

    This doesn't require a PDF - it uses the structured knowledge already
    coded in mcmillan_options_collector.py.

    Returns:
        Dict with ingestion status
    """
    logger.info("\n" + "=" * 60)
    logger.info("INGESTING: McMillan Knowledge Base (Built-in)")
    logger.info("=" * 60)

    kb = McMillanOptionsKnowledgeBase()
    db = get_rag_db()
    get_embedder()

    # Get all knowledge
    all_knowledge = kb.get_all_knowledge()

    documents = []
    metadatas = []
    ids = []

    # Process Greeks
    logger.info("Processing Greeks...")
    for greek_name, greek_data in all_knowledge["greeks"].items():
        content = (
            f"Greek: {greek_data['name']}\n"
            f"Definition: {greek_data['definition']}\n"
            f"Range: {greek_data['range']}\n"
            f"Interpretation: {greek_data['interpretation']}\n"
            f"Trading Implications: {greek_data['trading_implications']}\n"
            f"Peak Conditions: {greek_data['peak_conditions']}"
        )
        documents.append(content)
        metadatas.append(
            {
                "source": "mcmillan_kb",
                "content_type": "greek",
                "topic": greek_name,
                "book_title": "Options as a Strategic Investment",
            }
        )
        ids.append(f"mcmillan_greek_{greek_name}")

    # Process Strategies
    logger.info("Processing Strategies...")
    for strategy_name, strategy_data in all_knowledge["strategies"].items():
        content = (
            f"Strategy: {strategy_data['strategy_name']}\n"
            f"Description: {strategy_data['description']}\n"
            f"Market Outlook: {strategy_data['market_outlook']}\n"
            f"Setup Rules:\n- " + "\n- ".join(strategy_data["setup_rules"]) + "\n"
            "Entry Criteria:\n- " + "\n- ".join(strategy_data["entry_criteria"]) + "\n"
            "Exit Rules:\n- " + "\n- ".join(strategy_data["exit_rules"]) + "\n"
            "Risk Management:\n- " + "\n- ".join(strategy_data["risk_management"]) + "\n"
            "Common Mistakes:\n- " + "\n- ".join(strategy_data["common_mistakes"])
        )
        documents.append(content)
        metadatas.append(
            {
                "source": "mcmillan_kb",
                "content_type": "strategy",
                "topic": strategy_name,
                "book_title": "Options as a Strategic Investment",
            }
        )
        ids.append(f"mcmillan_strategy_{strategy_name}")

    # Process Volatility Guidance
    logger.info("Processing Volatility Guidance...")
    for i, guidance in enumerate(all_knowledge["volatility_guidance"]):
        content = (
            f"IV Range: {guidance['iv_rank_min']:.0f}-{guidance['iv_rank_max']:.0f}\n"
            f"Recommendation: {guidance['recommendation']}\n"
            f"Reasoning: {guidance['reasoning']}\n"
            f"Suggested Strategies: {', '.join(guidance['strategies'])}"
        )
        documents.append(content)
        metadatas.append(
            {
                "source": "mcmillan_kb",
                "content_type": "volatility_guidance",
                "topic": f"iv_range_{i}",
                "book_title": "Options as a Strategic Investment",
            }
        )
        ids.append(f"mcmillan_iv_guidance_{i}")

    # Process Risk Rules
    logger.info("Processing Risk Rules...")
    for category, rules in all_knowledge["risk_rules"].items():
        content = f"Risk Category: {category}\n"
        if isinstance(rules, dict):
            for key, value in rules.items():
                if isinstance(value, dict):
                    content += f"\n{key}:\n"
                    for k, v in value.items():
                        content += f"  - {k}: {v}\n"
                else:
                    content += f"- {key}: {value}\n"
        documents.append(content)
        metadatas.append(
            {
                "source": "mcmillan_kb",
                "content_type": "risk_rule",
                "topic": category,
                "book_title": "Options as a Strategic Investment",
            }
        )
        ids.append(f"mcmillan_risk_{category}")

    # Add to vector store
    logger.info(f"Adding {len(documents)} documents to vector store...")
    result = db.add_documents(documents=documents, metadatas=metadatas, ids=ids)

    if result["status"] == "success":
        logger.info(f"Successfully ingested {result['count']} knowledge chunks")

        # Get stats
        stats = db.get_stats()
        logger.info(f"Vector store now has {stats.get('total_documents', 0)} total documents")

        return {
            "status": "success",
            "chunks": len(documents),
            "categories": ["greeks", "strategies", "volatility_guidance", "risk_rules"],
        }
    else:
        logger.error(f"Failed to ingest: {result.get('message')}")
        return result


def ingest_directory(dir_path: str, force: bool = False) -> dict:
    """
    Ingest all PDF books from a directory.

    Args:
        dir_path: Path to directory containing PDFs
        force: Force re-ingestion

    Returns:
        Dict with results for each book
    """
    dir_path = Path(dir_path)
    if not dir_path.exists():
        return {"status": "error", "message": f"Directory not found: {dir_path}"}

    pdf_files = list(dir_path.glob("*.pdf"))
    if not pdf_files:
        return {"status": "error", "message": f"No PDF files found in {dir_path}"}

    logger.info(f"Found {len(pdf_files)} PDF files")

    results = {}
    for pdf_file in pdf_files:
        # Generate book_id from filename
        book_id = pdf_file.stem.lower().replace(" ", "_").replace("-", "_")
        result = ingest_pdf_book(str(pdf_file), book_id, force)
        results[book_id] = result

    return {"status": "success", "books_processed": len(results), "results": results}


def main():
    parser = argparse.ArgumentParser(
        description="Ingest options trading books into RAG vector store",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest McMillan knowledge base (no PDF needed)
  python scripts/ingest_options_books.py --ingest-kb

  # Ingest a specific PDF book
  python scripts/ingest_options_books.py --pdf ~/Books/mcmillan.pdf --book-id mcmillan_options

  # Ingest all PDFs from a directory
  python scripts/ingest_options_books.py --dir ~/Books/Options/

  # Force re-ingest
  python scripts/ingest_options_books.py --pdf book.pdf --book-id my_book --force
        """,
    )

    parser.add_argument("--pdf", type=str, help="Path to PDF file to ingest")
    parser.add_argument("--book-id", type=str, help="Book identifier (e.g., 'mcmillan_options')")
    parser.add_argument("--dir", type=str, help="Directory containing PDF books to ingest")
    parser.add_argument(
        "--ingest-kb", action="store_true", help="Ingest the built-in McMillan knowledge base"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force re-ingestion even if already processed"
    )
    parser.add_argument("--test", action="store_true", help="Run a test search after ingestion")

    args = parser.parse_args()

    # Validate arguments
    if not args.pdf and not args.dir and not args.ingest_kb:
        parser.print_help()
        print("\nError: Must specify --pdf, --dir, or --ingest-kb")
        sys.exit(1)

    if args.pdf and not args.book_id:
        # Try to infer book_id from filename
        args.book_id = Path(args.pdf).stem.lower().replace(" ", "_")
        logger.info(f"Inferred book_id: {args.book_id}")

    # Run ingestion
    start_time = datetime.now()

    if args.ingest_kb:
        result = ingest_mcmillan_knowledge_base()
    elif args.pdf:
        result = ingest_pdf_book(args.pdf, args.book_id, args.force)
    elif args.dir:
        result = ingest_directory(args.dir, args.force)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Print summary
    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    print(f"Status: {result['status']}")
    print(f"Time: {elapsed:.1f} seconds")

    if result["status"] == "success":
        if "chunks" in result:
            print(f"Chunks ingested: {result['chunks']}")
        if "pages" in result:
            print(f"Pages processed: {result['pages']}")

    # Optional test search
    if args.test and result["status"] == "success":
        print("\n" + "=" * 60)
        print("TEST SEARCH")
        print("=" * 60)

        retriever = get_options_book_retriever()
        test_query = "iron condor setup when IV is high"

        search_result = retriever.search_options_knowledge(test_query)
        print(f"Query: '{test_query}'")
        print(f"Book results: {len(search_result.get('book_results', []))}")
        print(f"Structured results: {len(search_result.get('structured_results', []))}")

        if search_result.get("combined_answer"):
            print(f"\nAnswer preview:\n{search_result['combined_answer'][:300]}...")


if __name__ == "__main__":
    main()
