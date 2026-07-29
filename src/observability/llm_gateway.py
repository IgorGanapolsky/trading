"""LLM Gateway & Observability Protocol Adapter.

Configures primary execution routing (Anthropic) and secondary logging declarations,
ensuring failsoft LLM observability without unhandled fallback warnings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GatewayRoutingStatus:
    primary_route: str
    secondary_route: str
    logging_declared: bool
    is_fully_configured: bool


class LLMGateway:
    """Manages LLM API routing and observability declarations."""

    @classmethod
    def get_routing_status(cls) -> GatewayRoutingStatus:
        primary = os.getenv("PRIMARY_LLM_ROUTE", "anthropic")
        secondary = os.getenv("SECONDARY_LLM_ROUTE", "direct_openrouter")
        logging_declared = os.getenv("OPENROUTER_INPUT_OUTPUT_LOGGING_ENABLED", "0") in {"1", "true", "yes"}
        has_key = bool(os.getenv("OPENROUTER_API_KEY"))

        return GatewayRoutingStatus(
            primary_route=primary,
            secondary_route=secondary,
            logging_declared=logging_declared,
            is_fully_configured=has_key or primary == "anthropic",
        )
