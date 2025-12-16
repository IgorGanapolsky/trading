"""
LangSmith Wrapper for OpenAI Client with Helicone Observability

Wraps OpenAI client with LangSmith tracing and optional Helicone gateway
for comprehensive LLM observability (traces, costs, latency, token usage).

Observability Stack:
- Helicone Gateway: Server-side observability via OpenRouter proxy (zero latency overhead)
- LangSmith: Client-side tracing (additional instrumentation)

When HELICONE_API_KEY is set, all OpenRouter requests automatically:
- Route through Helicone gateway for observability
- Track costs, tokens, latency per request
- Enable dashboard analytics at helicone.ai

Usage:
    from src.utils.langsmith_wrapper import get_traced_openai_client

    client = get_traced_openai_client()
    response = client.chat.completions.create(...)
"""

import logging
import os

from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Set up LangSmith tracing if API key is available
# Support BOTH naming conventions: LANGSMITH_* and LANGCHAIN_*
# LangChain SDK uses LANGCHAIN_* but users may set LANGSMITH_* (more intuitive)
_langsmith_api_key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
_langsmith_project = (
    os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT") or "trading-system"
)

if _langsmith_api_key:
    # Set the official LangChain env vars that the SDK expects
    os.environ["LANGCHAIN_API_KEY"] = _langsmith_api_key
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = _langsmith_project
    LANGSMITH_ENABLED = True
    logger.info(f"LangSmith tracing enabled for project: {_langsmith_project}")
else:
    LANGSMITH_ENABLED = False
    logger.debug("LangSmith tracing disabled - no API key found")

# Helicone configuration
HELICONE_API_KEY = os.getenv("HELICONE_API_KEY")
HELICONE_ENABLED = bool(HELICONE_API_KEY)

# OpenRouter URLs
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
HELICONE_OPENROUTER_URL = "https://openrouter.helicone.ai/api/v1"


def _get_openrouter_config(
    api_key: str | None = None, base_url: str | None = None
) -> tuple[str | None, str | None, dict[str, str]]:
    """
    Get OpenRouter configuration with optional Helicone gateway.

    Returns:
        Tuple of (api_key, base_url, default_headers)
    """
    # Determine API key
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    default_headers = {}

    # Determine base URL and headers
    if not base_url:
        if os.getenv("OPENROUTER_API_KEY"):
            # Check if Helicone is enabled for enhanced observability
            if HELICONE_ENABLED:
                base_url = HELICONE_OPENROUTER_URL
                default_headers["Helicone-Auth"] = f"Bearer {HELICONE_API_KEY}"
                logger.debug("Using Helicone gateway for OpenRouter observability")
            else:
                base_url = OPENROUTER_BASE_URL
        else:
            base_url = None  # Default OpenAI URL

    # Add OpenRouter identification headers
    if base_url and "openrouter" in base_url:
        default_headers["HTTP-Referer"] = os.getenv(
            "OPENROUTER_REFERER", "https://github.com/trading-system"
        )
        default_headers["X-Title"] = os.getenv("OPENROUTER_TITLE", "AI Trading System")

    return api_key, base_url, default_headers


def get_traced_openai_client(api_key: str | None = None, base_url: str | None = None):
    """
    Get OpenAI client with Helicone gateway and LangSmith tracing.

    Observability features (when configured):
    - Helicone: Server-side traces, cost tracking, latency metrics
    - LangSmith: Client-side tracing with detailed spans

    Args:
        api_key: OpenAI API key (defaults to OPENAI_API_KEY or OPENROUTER_API_KEY)
        base_url: Base URL for API (defaults to Helicone gateway if HELICONE_API_KEY set)

    Returns:
        OpenAI client with observability enabled
    """
    from openai import OpenAI

    resolved_key, resolved_url, default_headers = _get_openrouter_config(api_key, base_url)

    # Create client with headers for Helicone
    client = OpenAI(
        api_key=resolved_key,
        base_url=resolved_url,
        default_headers=default_headers if default_headers else None,
    )

    # Wrap with LangSmith if enabled (additional client-side tracing)
    if LANGSMITH_ENABLED:
        try:
            from langsmith import wrap_openai

            client = wrap_openai(client)
        except ImportError:
            # LangSmith not installed - use regular client
            pass

    return client


def get_traced_async_openai_client(api_key: str | None = None, base_url: str | None = None):
    """
    Get async OpenAI client with Helicone gateway and LangSmith tracing.

    Observability features (when configured):
    - Helicone: Server-side traces, cost tracking, latency metrics
    - LangSmith: Client-side tracing with detailed spans

    Args:
        api_key: OpenAI API key (defaults to OPENAI_API_KEY or OPENROUTER_API_KEY)
        base_url: Base URL for API (defaults to Helicone gateway if HELICONE_API_KEY set)

    Returns:
        AsyncOpenAI client with observability enabled
    """
    from openai import AsyncOpenAI

    resolved_key, resolved_url, default_headers = _get_openrouter_config(api_key, base_url)

    # Create async client with headers for Helicone
    client = AsyncOpenAI(
        api_key=resolved_key,
        base_url=resolved_url,
        default_headers=default_headers if default_headers else None,
    )

    # Wrap with LangSmith if enabled (additional client-side tracing)
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
    return LANGSMITH_ENABLED and (
        os.getenv("LANGCHAIN_API_KEY") is not None or os.getenv("LANGSMITH_API_KEY") is not None
    )


def is_helicone_enabled() -> bool:
    """Check if Helicone observability is enabled."""
    return HELICONE_ENABLED


def get_observability_status() -> dict:
    """
    Get current observability configuration status.

    Returns:
        Dictionary with status of all observability integrations
    """
    return {
        "helicone": {
            "enabled": HELICONE_ENABLED,
            "gateway_url": HELICONE_OPENROUTER_URL if HELICONE_ENABLED else None,
            "dashboard": "https://helicone.ai/dashboard" if HELICONE_ENABLED else None,
        },
        "langsmith": {
            "enabled": LANGSMITH_ENABLED,
            "project": os.getenv("LANGCHAIN_PROJECT", "trading-rl-training")
            if LANGSMITH_ENABLED
            else None,
            "dashboard": "https://smith.langchain.com" if LANGSMITH_ENABLED else None,
        },
        "openrouter": {
            "configured": bool(os.getenv("OPENROUTER_API_KEY")),
            "base_url": HELICONE_OPENROUTER_URL if HELICONE_ENABLED else OPENROUTER_BASE_URL,
        },
    }
