"""
LLM observability route and coverage helpers.

OpenRouter's private Input & Output Logging only covers requests that actually
hit OpenRouter. If an OpenAI-compatible gateway is configured as the primary
route, OpenRouter's private logs only see direct fallback traffic.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

from src.utils.llm_gateway import (
    OPENROUTER_BASE_URL,
    GatewayRequiredError,
    get_llm_gateway_api_key,
    get_llm_gateway_base_url,
    resolve_openrouter_primary_and_fallback_configs,
)


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _host(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or url


def _same_base_url(left: str | None, right: str | None) -> bool:
    return str(left or "").rstrip("/") == str(right or "").rstrip("/")


@dataclass(frozen=True)
class LLMObservabilityReport:
    """Resolved route and logging coverage for LLM traffic."""

    status: str
    summary: str
    primary_route: str
    primary_base_url: str | None
    primary_base_host: str | None
    fallback_base_host: str | None
    openrouter_api_key_present: bool
    gateway_base_url_present: bool
    gateway_base_host: str | None
    gateway_api_key_present: bool
    input_output_logging_declared: bool
    openrouter_private_logs_cover_primary: bool
    openrouter_private_logs_cover_fallback: bool
    critical_execution_provider: str
    critical_execution_covered_by_openrouter: bool
    warnings: tuple[str, ...]
    notes: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def build_llm_observability_report() -> LLMObservabilityReport:
    """Summarize how this process routes OpenRouter-compatible traffic."""
    input_output_logging_declared = _is_truthy(
        os.getenv("OPENROUTER_INPUT_OUTPUT_LOGGING_ENABLED")
    )
    gateway_base_url = get_llm_gateway_base_url()
    gateway_api_key_present = bool(get_llm_gateway_api_key())
    openrouter_api_key_present = bool((os.getenv("OPENROUTER_API_KEY") or "").strip())

    try:
        primary_cfg, fallback_cfg = resolve_openrouter_primary_and_fallback_configs()
    except GatewayRequiredError as exc:
        return LLMObservabilityReport(
            status="broken",
            summary="Gateway routing required but not configured.",
            primary_route="unconfigured",
            primary_base_url=None,
            primary_base_host=None,
            fallback_base_host=None,
            openrouter_api_key_present=openrouter_api_key_present,
            gateway_base_url_present=bool(gateway_base_url),
            gateway_base_host=_host(gateway_base_url),
            gateway_api_key_present=gateway_api_key_present,
            input_output_logging_declared=input_output_logging_declared,
            openrouter_private_logs_cover_primary=False,
            openrouter_private_logs_cover_fallback=False,
            critical_execution_provider="anthropic",
            critical_execution_covered_by_openrouter=False,
            warnings=(str(exc),),
            notes=(),
        )

    primary_base_url = primary_cfg.base_url or OPENROUTER_BASE_URL
    primary_route = (
        "direct_openrouter"
        if _same_base_url(primary_base_url, OPENROUTER_BASE_URL)
        else "gateway"
    )
    fallback_base_host = _host(getattr(fallback_cfg, "base_url", None) if fallback_cfg else None)
    warnings: list[str] = []
    notes = [
        "Critical trade execution still routes via Anthropic and is outside OpenRouter logs."
    ]

    if not primary_cfg.api_key:
        warnings.append("No OpenRouter-compatible API key resolved for the primary route.")

    if primary_route == "direct_openrouter":
        if not input_output_logging_declared:
            warnings.append(
                "Direct OpenRouter routing is active, but OPENROUTER_INPUT_OUTPUT_LOGGING_ENABLED is not declared."
            )
        summary = (
            "Direct OpenRouter routing active; compatible requests can appear in OpenRouter private logs."
        )
    else:
        gateway_host = _host(primary_base_url)
        warnings.append(
            "Primary OpenRouter-compatible traffic routes through "
            f"{gateway_host}; OpenRouter private logs only cover direct fallback requests."
        )
        if not fallback_cfg:
            warnings.append(
                "No direct OpenRouter fallback is configured, so OpenRouter private logs will not capture primary traffic."
            )
        if input_output_logging_declared:
            notes.append(
                "The OpenRouter logging declaration only applies to fallback traffic while the gateway is primary."
            )
        summary = (
            "Gateway routing active; OpenRouter private logs are subset-only and do not cover primary traffic."
        )

    if not openrouter_api_key_present:
        warnings.append("OPENROUTER_API_KEY is absent; direct OpenRouter fallback/logging is unavailable.")

    status = "ok" if not warnings else "warning"
    return LLMObservabilityReport(
        status=status,
        summary=summary,
        primary_route=primary_route,
        primary_base_url=primary_base_url,
        primary_base_host=_host(primary_base_url),
        fallback_base_host=fallback_base_host,
        openrouter_api_key_present=openrouter_api_key_present,
        gateway_base_url_present=bool(gateway_base_url),
        gateway_base_host=_host(gateway_base_url),
        gateway_api_key_present=gateway_api_key_present,
        input_output_logging_declared=input_output_logging_declared,
        openrouter_private_logs_cover_primary=primary_route == "direct_openrouter",
        openrouter_private_logs_cover_fallback=bool(fallback_cfg)
        or primary_route == "direct_openrouter",
        critical_execution_provider="anthropic",
        critical_execution_covered_by_openrouter=False,
        warnings=tuple(warnings),
        notes=tuple(notes),
    )


def render_llm_observability_lines(report: LLMObservabilityReport) -> list[str]:
    """Render report details for CLI and health checks."""
    lines = [
        f"Route: {report.primary_route} ({report.primary_base_host or 'unconfigured'})",
        f"Gateway configured: {'yes' if report.gateway_base_url_present else 'no'}",
        f"Gateway credential present: {'yes' if report.gateway_api_key_present else 'no'}",
        f"OpenRouter key present: {'yes' if report.openrouter_api_key_present else 'no'}",
        "OpenRouter Input & Output Logging declared: "
        f"{'yes' if report.input_output_logging_declared else 'no'}",
        "OpenRouter private logs cover primary traffic: "
        f"{'yes' if report.openrouter_private_logs_cover_primary else 'no'}",
        "OpenRouter private logs cover fallback traffic: "
        f"{'yes' if report.openrouter_private_logs_cover_fallback else 'no'}",
        "Critical Anthropic execution covered by OpenRouter logs: "
        f"{'yes' if report.critical_execution_covered_by_openrouter else 'no'}",
    ]

    if report.fallback_base_host:
        lines.append(f"Fallback route host: {report.fallback_base_host}")

    for warning in report.warnings:
        lines.append(f"⚠️ {warning}")
    for note in report.notes:
        lines.append(f"ℹ️ {note}")
    return lines
