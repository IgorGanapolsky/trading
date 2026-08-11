from __future__ import annotations

from src.observability.llm_observability import build_llm_observability_report


def _clear_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CLAUDE_API_KEY", "")
    for key in [
        "OPENROUTER_API_KEY",
        "LLM_GATEWAY_BASE_URL",
        "LLM_GATEWAY_API_KEY",
        "TETRATE_API_KEY",
        "OPENROUTER_INPUT_OUTPUT_LOGGING_ENABLED",
        "REQUIRE_LLM_GATEWAY",
        "LLM_GATEWAY_STRICT",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_direct_openrouter_route_reports_ok_when_logging_declared(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    monkeypatch.setenv("OPENROUTER_INPUT_OUTPUT_LOGGING_ENABLED", "true")

    report = build_llm_observability_report()

    assert report.status == "ok"
    assert report.primary_route == "direct_openrouter"
    assert report.openrouter_private_logs_cover_primary is True
    assert report.openrouter_private_logs_cover_fallback is False
    assert report.fallback_base_host is None
    assert report.critical_execution_covered_by_openrouter is False
    assert report.anthropic_api_key_present is False
    assert report.local_structured_tracing_available is True


def test_gateway_route_warns_that_openrouter_logs_are_subset_only(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    monkeypatch.setenv("LLM_GATEWAY_BASE_URL", "https://api.router.tetrate.ai/v1")
    monkeypatch.setenv("LLM_GATEWAY_API_KEY", "gw-test")
    monkeypatch.setenv("OPENROUTER_INPUT_OUTPUT_LOGGING_ENABLED", "true")

    report = build_llm_observability_report()

    assert report.status == "warning"
    assert report.primary_route == "gateway"
    assert report.openrouter_private_logs_cover_primary is False
    assert report.openrouter_private_logs_cover_fallback is True
    assert any(
        "OpenRouter private logs do not cover primary gateway traffic" in warning
        for warning in report.warnings
    )


def test_direct_openrouter_without_logging_declaration_warns(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")

    report = build_llm_observability_report()

    assert report.status == "warning"
    assert report.primary_route == "direct_openrouter"
    assert report.openrouter_private_logs_cover_primary is False
    assert any(
        "OPENROUTER_INPUT_OUTPUT_LOGGING_ENABLED is not declared" in warning
        for warning in report.warnings
    )


def test_no_credentials_reports_deterministic_only_without_false_green(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)

    report = build_llm_observability_report()

    assert report.status == "warning"
    assert report.anthropic_api_key_present is False
    assert report.openrouter_api_key_present is False
    assert report.openrouter_private_logs_cover_primary is False
    assert report.primary_route == "unconfigured"
    assert report.primary_base_url is None
    assert report.summary == "No LLM provider route is configured; deterministic paths only."
    assert any(
        "No Anthropic, gateway, or OpenRouter credential" in item for item in report.warnings
    )


def test_claude_credential_alias_is_reported_without_exposing_value(monkeypatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("CLAUDE_API_KEY", "test-value-that-must-not-be-rendered")

    report = build_llm_observability_report()

    assert report.status == "ok"
    assert report.anthropic_api_key_present is True
    assert report.primary_route == "direct_anthropic"
    assert report.primary_base_host == "api.anthropic.com"
    assert (
        report.summary == "Direct Anthropic analysis is configured with local structured tracing."
    )
    assert "test-value" not in str(report.as_dict())
