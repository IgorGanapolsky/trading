"""ML Module - Gemini/GenAI Integration.

Provides GENAI_AVAILABLE flag for health checks.
"""

try:
    import google.generativeai  # noqa: F401 - import used for availability check

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

__all__ = ["GENAI_AVAILABLE"]
