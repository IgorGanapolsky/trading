"""
RAG System Configuration

Centralized configuration for vector database and embedding settings.
"""

from pathlib import Path
from typing import Any

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Data directories
DATA_DIR = PROJECT_ROOT / "data" / "rag"
NORMALIZED_DIR = DATA_DIR / "normalized"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"

# Ensure directories exist
NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

# Embedding configuration
EMBEDDING_CONFIG = {
    "model_name": "all-MiniLM-L6-v2",  # Fast, efficient, 384 dimensions
    "device": "cpu",  # Use CPU for compatibility (GPU optional)
    "max_seq_length": 512,  # Maximum token length for chunks
    "batch_size": 50,  # Process 50 articles at a time
}

# ChromaDB configuration
CHROMA_CONFIG = {
    "persist_directory": str(CHROMA_DB_DIR),
    "collection_name": "market_news",
    "distance_metric": "cosine",  # Best for sentence embeddings
}

# Chunking configuration
CHUNK_CONFIG = {
    "max_tokens": 512,  # Match model max_seq_length
    "overlap": 50,  # Token overlap between chunks
    "combine_title_content": True,  # Include title in chunk
}

# Retrieval configuration
RETRIEVAL_CONFIG = {
    "default_k": 5,  # Default number of results
    "max_k": 20,  # Maximum results allowed
    "min_score": 0.3,  # Minimum similarity score (0-1)
}

# Metadata schema
METADATA_SCHEMA = {
    "ticker": str,  # Stock ticker symbol
    "source": str,  # News source (Alpha Vantage, Reddit, etc.)
    "published_date": str,  # ISO format date
    "sentiment_score": float,  # -1 to 1
    "title": str,  # Article title
    "url": str,  # Source URL
}


def get_config() -> dict[str, Any]:
    """
    Get complete RAG configuration.

    Returns:
        Dictionary containing all configuration settings
    """
    return {
        "paths": {
            "data_dir": str(DATA_DIR),
            "normalized_dir": str(NORMALIZED_DIR),
            "chroma_db_dir": str(CHROMA_DB_DIR),
        },
        "embedding": EMBEDDING_CONFIG,
        "chroma": CHROMA_CONFIG,
        "chunking": CHUNK_CONFIG,
        "retrieval": RETRIEVAL_CONFIG,
        "metadata_schema": METADATA_SCHEMA,
    }


def validate_config() -> bool:
    """
    Validate configuration and directory setup.

    Returns:
        True if configuration is valid, raises exception otherwise
    """
    # Check directories exist
    assert DATA_DIR.exists(), f"Data directory not found: {DATA_DIR}"
    assert NORMALIZED_DIR.exists(), f"Normalized directory not found: {NORMALIZED_DIR}"
    assert CHROMA_DB_DIR.exists(), f"ChromaDB directory not found: {CHROMA_DB_DIR}"

    # Check embedding model name is valid
    assert isinstance(EMBEDDING_CONFIG["model_name"], str), "Model name must be string"
    assert EMBEDDING_CONFIG["batch_size"] > 0, "Batch size must be positive"

    # Check retrieval parameters
    assert RETRIEVAL_CONFIG["default_k"] <= RETRIEVAL_CONFIG["max_k"], "default_k must be <= max_k"
    assert 0 <= RETRIEVAL_CONFIG["min_score"] <= 1, "min_score must be between 0 and 1"

    return True
