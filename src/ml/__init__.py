"""
ML Pipeline Module

Provides machine learning capabilities for trading.
"""

# Gemini API availability flag
GENAI_AVAILABLE = False

try:
    import google.genai  # noqa: F401

    GENAI_AVAILABLE = True
except ImportError:
    pass
