#!/usr/bin/env python3
"""
Test HyDE Retrieval
"""

import logging
import os
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
from rag_store.retriever import get_retriever

logging.basicConfig(level=logging.INFO)


def main():
    # Explicitly load .env
    load_dotenv()

    print("Initializing HyDE Retriever...")
    try:
        retriever = get_retriever()
    except Exception as e:
        print(f"Error initializing retriever: {e}")
        return

    # Check if agent is properly initialized
    if not retriever.agent.client:
        print("❌ Gemini Agent client still not initialized. Check GOOGLE_API_KEY in .env")
        import os

        key = os.getenv("GOOGLE_API_KEY")
        if key:
            print(f"✅ GOOGLE_API_KEY found in env (length: {len(key)})")
            # Re-init
            retriever.agent.__init__(
                retriever.agent.name, retriever.agent.role, retriever.agent.model
            )
        else:
            print("❌ GOOGLE_API_KEY NOT found in env after explicit load.")
            return

    query = "How do I get the current TVL for a specific protocol using the DeFiLlama API?"
    print(f"\nQuery: {query}")

    print("\n--- Generating Hypothetical Document ---")
    try:
        hypo_doc = retriever.generate_hypothetical_document(query)
        print(f"Hypothetical Document:\n{hypo_doc}")
    except Exception as e:
        print(f"Error generating hypothetical doc: {e}")

    print("\n--- Retrieving Real Documents ---")
    results = retriever.retrieve(query, n_results=3, use_hyde=True)

    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    dists = results.get("distances", [])

    if docs and len(docs) > 0:
        for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
            print(f"\nResult {i + 1} (Score: {1 - dist:.4f}):")
            print(f"Source: {meta.get('source')} - {meta.get('url')}")
            print(f"Content snippet: {doc[:200]}...")
    else:
        print("No documents found.")


if __name__ == "__main__":
    main()
