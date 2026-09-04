"""Official SuperMemory adapter (optional). Local ledgers remain edge truth."""

from src.rag.supermemory.client import SuperMemoryClient, build_search_body, load_api_key
from src.rag.supermemory.contract import (
    DEFAULT_CONTAINER_TAG,
    DEFAULT_SEARCH_MODE,
    route_query,
    validate_v4_search_body,
)
from src.rag.supermemory.fuse import fuse_local_with_supermemory

__all__ = [
    "DEFAULT_CONTAINER_TAG",
    "DEFAULT_SEARCH_MODE",
    "SuperMemoryClient",
    "build_search_body",
    "fuse_local_with_supermemory",
    "load_api_key",
    "route_query",
    "validate_v4_search_body",
]
