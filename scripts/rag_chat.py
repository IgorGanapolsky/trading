#!/usr/bin/env python3
"""
RAG Chat Interface - Chat with your Phil Town knowledge base

Interactive chat that retrieves relevant context from ChromaDB
and uses Gemini to answer questions.

Usage:
    python3 scripts/rag_chat.py                    # Interactive chat
    python3 scripts/rag_chat.py --query "question" # Single query
    python3 scripts/rag_chat.py --stats            # Show database stats
    python3 scripts/rag_chat.py --list             # List all documents

Requires: GOOGLE_API_KEY environment variable
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

VECTOR_DB_PATH = Path("data/vector_db")


def get_chroma_collection():
    """Get ChromaDB collection."""
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        print("❌ ChromaDB not installed. Run: pip install chromadb")
        return None

    if not VECTOR_DB_PATH.exists():
        print("❌ Vector DB not found. Run: python3 scripts/vectorize_rag_knowledge.py --rebuild")
        return None

    client = chromadb.PersistentClient(
        path=str(VECTOR_DB_PATH), settings=Settings(anonymized_telemetry=False)
    )

    try:
        collection = client.get_collection("phil_town_rag")
        return collection
    except Exception as e:
        print(f"❌ Collection not found: {e}")
        return None


def search_rag(query: str, n_results: int = 5) -> list[dict]:
    """Search the RAG for relevant content."""
    collection = get_chroma_collection()
    if not collection:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    formatted = []
    for i, doc in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i]
        formatted.append(
            {
                "content": doc,
                "source": metadata.get("source", "unknown"),
                "type": metadata.get("content_type", "unknown"),
                "concepts": metadata.get("concepts", "none"),
                "relevance": round(1 - results["distances"][0][i], 3),
            }
        )

    return formatted


def ask_gemini(question: str, context: list[dict]) -> str:
    """Use Gemini to answer based on retrieved context."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "❌ GOOGLE_API_KEY not set. Set it to use Gemini for answers."

    try:
        import google.generativeai as genai
    except ImportError:
        return "❌ google-generativeai not installed. Run: pip install google-generativeai"

    genai.configure(api_key=api_key)

    # Build context string
    context_str = "\n\n---\n\n".join(
        [
            f"[{c['type']}] {c['source']} (relevance: {c['relevance']})\n{c['content'][:1500]}"
            for c in context[:3]  # Top 3 results
        ]
    )

    prompt = f"""You are a Phil Town Rule #1 Investing expert assistant.
Answer the user's question based on the following context from the knowledge base.
Be specific and cite which source you're drawing from.
If the context doesn't contain relevant information, say so.

CONTEXT:
{context_str}

USER QUESTION: {question}

ANSWER:"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Gemini error: {e}"


def show_stats():
    """Show database statistics."""
    collection = get_chroma_collection()
    if not collection:
        return

    count = collection.count()

    # Get sample of metadata
    sample = collection.peek(limit=10)

    types = {}
    concepts = {}
    for meta in sample.get("metadatas", []):
        t = meta.get("content_type", "unknown")
        types[t] = types.get(t, 0) + 1
        for c in meta.get("concepts", "").split(", "):
            if c and c != "none":
                concepts[c] = concepts.get(c, 0) + 1

    print("\n📊 RAG Database Statistics")
    print("=" * 50)
    print(f"   Total chunks: {count}")
    print("\n   Content types (sample):")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"     - {t}: {c}")
    print("\n   Top concepts (sample):")
    for c, n in sorted(concepts.items(), key=lambda x: -x[1])[:10]:
        print(f"     - {c}: {n}")


def list_documents():
    """List all unique documents in the database."""
    collection = get_chroma_collection()
    if not collection:
        return

    # Get all metadata
    all_data = collection.get(include=["metadatas"])

    sources = {}
    for meta in all_data.get("metadatas", []):
        source = meta.get("source", "unknown")
        content_type = meta.get("content_type", "unknown")
        if source not in sources:
            sources[source] = {"type": content_type, "chunks": 0}
        sources[source]["chunks"] += 1

    print("\n📚 Documents in RAG Database")
    print("=" * 50)

    by_type = {}
    for source, info in sources.items():
        t = info["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append((source, info["chunks"]))

    for content_type, docs in sorted(by_type.items()):
        print(f"\n   [{content_type}]")
        for source, chunks in sorted(docs):
            print(f"     - {source} ({chunks} chunks)")


def interactive_chat():
    """Run interactive chat session."""
    print("\n" + "=" * 60)
    print("   🤖 Phil Town RAG Chat")
    print("   Ask questions about Rule #1 Investing")
    print("=" * 60)
    print("\nCommands:")
    print("  /stats  - Show database statistics")
    print("  /list   - List all documents")
    print("  /raw    - Show raw context (no Gemini)")
    print("  /quit   - Exit chat")
    print()

    raw_mode = False

    while True:
        try:
            query = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye! 👋")
            break

        if not query:
            continue

        if query.lower() == "/quit":
            print("\nGoodbye! 👋")
            break
        elif query.lower() == "/stats":
            show_stats()
            continue
        elif query.lower() == "/list":
            list_documents()
            continue
        elif query.lower() == "/raw":
            raw_mode = not raw_mode
            print(f"Raw mode: {'ON' if raw_mode else 'OFF'}")
            continue

        # Search RAG
        print("\n🔍 Searching knowledge base...")
        results = search_rag(query, n_results=5)

        if not results:
            print("❌ No results found.")
            continue

        if raw_mode:
            # Show raw results
            print(f"\n📄 Found {len(results)} relevant chunks:\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. [{r['type']}] {r['source']} (relevance: {r['relevance']})")
                print(f"   Concepts: {r['concepts']}")
                print(f"   {r['content'][:300]}...")
                print()
        else:
            # Use Gemini to answer
            print("\n💭 Thinking...")
            answer = ask_gemini(query, results)
            print(f"\n🤖 Assistant:\n{answer}")

            # Show sources
            print("\n📚 Sources:")
            for r in results[:3]:
                print(f"   - {r['source']} ({r['type']}, relevance: {r['relevance']})")

        print()


def main():
    parser = argparse.ArgumentParser(description="Chat with Phil Town RAG")
    parser.add_argument("--query", "-q", type=str, help="Single query (non-interactive)")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--list", action="store_true", help="List all documents")
    parser.add_argument("--raw", action="store_true", help="Show raw results without Gemini")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if args.list:
        list_documents()
        return

    if args.query:
        results = search_rag(args.query)
        if not results:
            print("❌ No results found.")
            return

        if args.raw:
            for i, r in enumerate(results, 1):
                print(f"\n{i}. [{r['type']}] {r['source']} (relevance: {r['relevance']})")
                print(f"   {r['content'][:500]}...")
        else:
            answer = ask_gemini(args.query, results)
            print(f"\n🤖 {answer}")
            print("\n📚 Sources:")
            for r in results[:3]:
                print(f"   - {r['source']} (relevance: {r['relevance']})")
        return

    # Interactive mode
    interactive_chat()


if __name__ == "__main__":
    main()
