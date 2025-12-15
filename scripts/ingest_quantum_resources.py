#!/usr/bin/env python3
"""
Ingest quantum physics and quantum trading resources into RAG system.

This script:
1. Reads quantum resources from config/quantum_physics_trading_resources.yaml
2. Reads markdown files from rag_knowledge/quantum/
3. Embeds and stores in ChromaDB vector database
4. Makes resources searchable via RAG queries

Usage:
    python3 scripts/ingest_quantum_resources.py
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.vector_db.chroma_client import get_rag_db
from src.rag.vector_db.embedder import get_embedder

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_yaml_resources() -> dict[str, Any]:
    """Load quantum resources from YAML config file."""
    yaml_path = Path("config/quantum_physics_trading_resources.yaml")

    if not yaml_path.exists():
        raise FileNotFoundError(f"Resources file not found: {yaml_path}")

    with open(yaml_path) as f:
        resources = yaml.safe_load(f)

    logger.info(f"✅ Loaded quantum resources from {yaml_path}")
    return resources


def load_markdown_files() -> list[dict[str, str]]:
    """Load markdown files from rag_knowledge/quantum/ directory."""
    quantum_dir = Path("rag_knowledge/quantum")

    if not quantum_dir.exists():
        logger.warning(f"Quantum directory not found: {quantum_dir}")
        return []

    markdown_files = []
    for md_file in quantum_dir.glob("*.md"):
        with open(md_file, encoding="utf-8") as f:
            content = f.read()

        markdown_files.append({"filename": md_file.name, "content": content})

    logger.info(f"✅ Loaded {len(markdown_files)} markdown files")
    return markdown_files


def format_book_entry(book: dict[str, Any]) -> str:
    """Format book entry as text for embedding."""
    text = f"# Book: {book['title']}\n\n"
    text += f"**Author**: {book['author']}\n"
    text += f"**Difficulty**: {book['difficulty']}\n"
    text += f"**Focus**: {', '.join(book.get('focus_tags', []))}\n\n"

    if "isbn" in book:
        text += f"**ISBN**: {book['isbn']}\n"
    if "year" in book:
        text += f"**Year**: {book['year']}\n"

    text += f"\n{book.get('summary', '')}\n\n"

    if "lessons" in book:
        text += "## Key Lessons\n\n"
        for lesson in book["lessons"]:
            text += f"### {lesson['title']}\n"
            text += f"**Trigger**: {lesson['trigger']}\n"
            text += "**Actions**:\n"
            for action in lesson.get("actions", []):
                text += f"- {action}\n"
            text += "\n"

    if "reading_plan" in book:
        text += "## Reading Plan\n\n"
        for plan in book["reading_plan"]:
            text += f"- {plan['label']}: {plan['goal']} ({plan['minutes']} min, {plan['difficulty']})\n"

    return text


def format_paper_entry(paper: dict[str, Any]) -> str:
    """Format paper entry as text for embedding."""
    authors_str = ", ".join(paper.get("authors", []))
    text = f"# Research Paper: {paper['title']}\n\n"
    text += f"**Authors**: {authors_str}\n"
    text += f"**Journal**: {paper.get('journal', 'N/A')}\n"
    text += f"**Year**: {paper.get('year', 'N/A')}\n"
    text += f"**Focus**: {', '.join(paper.get('focus_tags', []))}\n"

    if "url" in paper:
        text += f"**URL**: {paper['url']}\n"

    text += f"\n{paper.get('summary', '')}\n\n"

    if "key_findings" in paper:
        text += "## Key Findings\n\n"
        for finding in paper["key_findings"]:
            text += f"- {finding}\n"

    return text


def format_youtube_entry(channel: dict[str, Any]) -> str:
    """Format YouTube channel entry as text for embedding."""
    text = f"# YouTube Channel: {channel['name']}\n\n"
    text += f"**URL**: {channel['url']}\n"
    text += f"**Focus**: {', '.join(channel.get('focus', []))}\n"
    text += f"**Quality**: {channel.get('quality', 'N/A')}\n\n"

    if "recommended_videos" in channel:
        text += "## Recommended Videos\n\n"
        for video in channel["recommended_videos"]:
            text += f"### {video['title']}\n"
            if "video_id" in video:
                text += f"**Video ID**: {video['video_id']}\n"
            if "duration_minutes" in video:
                text += f"**Duration**: {video['duration_minutes']} minutes\n"
            text += f"**Difficulty**: {video.get('difficulty', 'N/A')}\n"
            text += f"**Topics**: {', '.join(video.get('key_topics', []))}\n\n"

    return text


def format_blog_entry(blog: dict[str, Any]) -> str:
    """Format blog entry as text for embedding."""
    text = f"# Blog/Website: {blog['name']}\n\n"
    text += f"**URL**: {blog['url']}\n"
    text += f"**Focus**: {', '.join(blog.get('focus', []))}\n"
    text += f"**Update Frequency**: {blog.get('update_frequency', 'N/A')}\n"
    text += f"**Quality**: {blog.get('quality', 'N/A')}\n\n"

    if "notes" in blog:
        text += f"{blog['notes']}\n\n"

    if "key_articles" in blog:
        text += "## Key Articles\n\n"
        for article in blog["key_articles"]:
            text += f"- [{article['title']}]({article['url']})\n"
            text += f"  Tags: {', '.join(article.get('tags', []))}\n"

    return text


def format_concept_entry(concept: dict[str, Any]) -> str:
    """Format quantum concept entry as text for embedding."""
    text = f"# Quantum Concept: {concept['concept']}\n\n"
    text += f"{concept.get('description', '')}\n\n"
    text += f"**Practical Use**: {concept.get('practical_use', 'N/A')}\n"
    text += f"**Tools**: {', '.join(concept.get('tools', []))}\n"

    return text


def ingest_resources():
    """Main ingestion function."""
    logger.info("=" * 60)
    logger.info("🚀 Starting Quantum Resources Ingestion")
    logger.info("=" * 60)

    # Initialize RAG database
    db = get_rag_db()
    get_embedder()

    # Load resources
    resources = load_yaml_resources()
    markdown_files = load_markdown_files()

    documents = []
    metadatas = []
    ids = []
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Process books
    logger.info("\n📚 Processing quantum physics books...")
    for i, book in enumerate(resources.get("quantum_physics_books", [])):
        text = format_book_entry(book)
        documents.append(text)
        metadatas.append(
            {
                "ticker": "QUANTUM",
                "source": "book",
                "category": "quantum_physics",
                "title": book["title"],
                "author": book["author"],
                "difficulty": book["difficulty"],
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        ids.append(f"QUANTUM_book_{timestamp}_{i}")

    logger.info(f"✅ Processed {len(resources.get('quantum_physics_books', []))} books")

    # Process papers
    logger.info("\n📄 Processing quantum trading papers...")
    for i, paper in enumerate(resources.get("quantum_trading_papers", [])):
        text = format_paper_entry(paper)
        documents.append(text)
        metadatas.append(
            {
                "ticker": "QUANTUM",
                "source": "paper",
                "category": "research",
                "title": paper["title"],
                "year": str(paper.get("year", "")),
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        ids.append(f"QUANTUM_paper_{timestamp}_{i}")

    logger.info(f"✅ Processed {len(resources.get('quantum_trading_papers', []))} papers")

    # Process YouTube channels
    logger.info("\n📺 Processing YouTube channels...")
    for i, channel in enumerate(resources.get("youtube_channels", [])):
        text = format_youtube_entry(channel)
        documents.append(text)
        metadatas.append(
            {
                "ticker": "QUANTUM",
                "source": "youtube",
                "category": "education",
                "name": channel["name"],
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        ids.append(f"QUANTUM_youtube_{timestamp}_{i}")

    logger.info(f"✅ Processed {len(resources.get('youtube_channels', []))} YouTube channels")

    # Process blogs
    logger.info("\n📝 Processing blogs and websites...")
    for i, blog in enumerate(resources.get("blogs_and_websites", [])):
        text = format_blog_entry(blog)
        documents.append(text)
        metadatas.append(
            {
                "ticker": "QUANTUM",
                "source": "blog",
                "category": "online_resource",
                "name": blog["name"],
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        ids.append(f"QUANTUM_blog_{timestamp}_{i}")

    logger.info(
        f"✅ Processed {len(resources.get('blogs_and_websites', []))} blogs/websites"
    )

    # Process quantum concepts
    logger.info("\n🔬 Processing quantum finance concepts...")
    for i, concept in enumerate(resources.get("key_quantum_finance_concepts", [])):
        text = format_concept_entry(concept)
        documents.append(text)
        metadatas.append(
            {
                "ticker": "QUANTUM",
                "source": "concept",
                "category": "knowledge",
                "concept": concept["concept"],
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        ids.append(f"QUANTUM_concept_{timestamp}_{i}")

    logger.info(
        f"✅ Processed {len(resources.get('key_quantum_finance_concepts', []))} concepts"
    )

    # Process markdown files
    logger.info("\n📄 Processing markdown documentation...")
    for i, md_file in enumerate(markdown_files):
        documents.append(md_file["content"])
        metadatas.append(
            {
                "ticker": "QUANTUM",
                "source": "documentation",
                "category": "knowledge_base",
                "filename": md_file["filename"],
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
        )
        ids.append(f"QUANTUM_doc_{timestamp}_{i}")

    logger.info(f"✅ Processed {len(markdown_files)} markdown files")

    # Store in vector database
    logger.info(f"\n💾 Storing {len(documents)} documents in ChromaDB...")

    try:
        result = db.add_documents(documents=documents, metadatas=metadatas, ids=ids)

        if result["status"] == "success":
            logger.info(f"✅ Successfully stored {result['count']} quantum resources")

            # Get updated stats
            stats = db.get_stats()
            logger.info("\n📊 Updated Database Stats:")
            logger.info(f"   Total documents: {stats.get('total_documents', 0)}")
            logger.info(f"   Unique tickers: {stats.get('unique_tickers', 0)}")
            logger.info(f"   Sources: {', '.join(stats.get('sources', []))}")

            # Save summary
            summary_path = Path("rag_knowledge/quantum/ingestion_summary.json")
            summary = {
                "timestamp": datetime.now().isoformat(),
                "total_documents": result["count"],
                "categories": {
                    "books": len(resources.get("quantum_physics_books", [])),
                    "papers": len(resources.get("quantum_trading_papers", [])),
                    "youtube_channels": len(resources.get("youtube_channels", [])),
                    "blogs": len(resources.get("blogs_and_websites", [])),
                    "concepts": len(resources.get("key_quantum_finance_concepts", [])),
                    "markdown_docs": len(markdown_files),
                },
                "status": "success",
            }

            summary_path.parent.mkdir(exist_ok=True)
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2)

            logger.info(f"\n✅ Ingestion summary saved to {summary_path}")

            return {"status": "success", "count": result["count"], "stats": stats}

        else:
            logger.error(f"❌ Failed to store documents: {result.get('message')}")
            return {"status": "error", "message": result.get("message")}

    except Exception as e:
        logger.error(f"❌ Error during ingestion: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def test_query():
    """Test RAG query on ingested quantum resources."""
    logger.info("\n" + "=" * 60)
    logger.info("🔍 Testing RAG Query on Quantum Resources")
    logger.info("=" * 60)

    db = get_rag_db()

    test_queries = [
        "quantum portfolio optimization",
        "QAOA algorithm for finance",
        "quantum machine learning trading",
        "books on quantum finance",
        "YouTube channels for quantum computing",
    ]

    for query in test_queries:
        logger.info(f"\n📝 Query: {query}")
        results = db.query(query_texts=[query], n_results=3)

        if results and results.get("documents"):
            for i, (doc, metadata) in enumerate(
                zip(results["documents"][0], results["metadatas"][0])
            ):
                logger.info(f"\n  Result {i+1}:")
                logger.info(f"    Source: {metadata.get('source', 'N/A')}")
                logger.info(f"    Category: {metadata.get('category', 'N/A')}")
                logger.info(f"    Preview: {doc[:150]}...")
        else:
            logger.info("  No results found")


if __name__ == "__main__":
    try:
        result = ingest_resources()

        if result["status"] == "success":
            logger.info("\n" + "=" * 60)
            logger.info("✅ INGESTION COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)

            # Test queries
            test_query()

        else:
            logger.error("\n❌ INGESTION FAILED")
            sys.exit(1)

    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
