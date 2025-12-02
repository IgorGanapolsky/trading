"""
LangSmith Wrapper for OpenAI Client

Wraps OpenAI client with LangSmith tracing for observability.
Use this wrapper to automatically log all LLM calls to LangSmith.

Usage:
    from src.utils.langsmith_wrapper import get_traced_openai_client

    client = get_traced_openai_client()
    response = client.chat.completions.create(...)
"""

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up LangSmith tracing if API key is available
if os.getenv("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "trading-rl-training")
    LANGSMITH_ENABLED = True
else:
    LANGSMITH_ENABLED = False


def get_traced_openai_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    """
    Get OpenAI client wrapped with LangSmith tracing.

    Args:
        api_key: OpenAI API key (defaults to OPENAI_API_KEY or OPENROUTER_API_KEY)
        base_url: Base URL for API (defaults to OpenAI, or OpenRouter if using OpenRouter key)

    Returns:
        OpenAI client (wrapped if LangSmith enabled, otherwise regular client)
    """
    from openai import OpenAI

    # Determine API key and base URL
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    if not base_url:
        # Use OpenRouter if OPENROUTER_API_KEY is set, otherwise OpenAI
        if os.getenv("OPENROUTER_API_KEY"):
            base_url = "https://openrouter.ai/api/v1"
        else:
            base_url = None  # Default OpenAI URL

    # Create client
    client = OpenAI(api_key=api_key, base_url=base_url)

    # Wrap with LangSmith if enabled
    if LANGSMITH_ENABLED:
        try:
            from langsmith import wrap_openai

            client = wrap_openai(client)
        except ImportError:
            # LangSmith not installed - use regular client
            pass

    return client


def get_traced_async_openai_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    """
    Get async OpenAI client wrapped with LangSmith tracing.

    Args:
        api_key: OpenAI API key (defaults to OPENAI_API_KEY or OPENROUTER_API_KEY)
        base_url: Base URL for API (defaults to OpenAI, or OpenRouter if using OpenRouter key)

    Returns:
        AsyncOpenAI client (wrapped if LangSmith enabled, otherwise regular client)
    """
    from openai import AsyncOpenAI

    # Determine API key and base URL
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    if not base_url:
        # Use OpenRouter if OPENROUTER_API_KEY is set, otherwise OpenAI
        if os.getenv("OPENROUTER_API_KEY"):
            base_url = "https://openrouter.ai/api/v1"
        else:
            base_url = None  # Default OpenAI URL

    # Create client
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # Wrap with LangSmith if enabled
    if LANGSMITH_ENABLED:
        try:
            from langsmith import wrap_openai

            client = wrap_openai(client)
        except ImportError:
            # LangSmith not installed - use regular client
            pass

    return client


def is_langsmith_enabled() -> bool:
    """Check if LangSmith tracing is enabled."""
    return LANGSMITH_ENABLED and os.getenv("LANGCHAIN_API_KEY") is not None
