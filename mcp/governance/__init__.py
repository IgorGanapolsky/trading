"""
MCP Governance Middleware

Architecture pattern from "Architecting for the Agent Age" (Medium, Jan 2026):
1. Input Validation (Pydantic) - Validates all incoming requests
2. Output Sanitization (Anti-Injection) - Sanitizes all responses

This middleware layer protects against:
- Prompt injection attacks
- Malformed trading requests
- Unauthorized symbol access
- Resource exhaustion
"""

from mcp.governance.input_validation import (
    OrderRequest,
    PositionSizeRequest,
    StockAnalysisRequest,
    validate_request,
)
from mcp.governance.output_sanitization import sanitize_response

__all__ = [
    "OrderRequest",
    "PositionSizeRequest",
    "StockAnalysisRequest",
    "validate_request",
    "sanitize_response",
]
