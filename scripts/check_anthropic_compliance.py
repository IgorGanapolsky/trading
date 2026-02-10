#!/usr/bin/env python3
"""
CI guardrail: verify Anthropic usage policy compliance anchors are present.

This is intentionally lightweight and dependency-free.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "compliance" / "anthropic_usage_policy.json"
DISCLOSURE_TEXT = (
    "AI Disclosure: This interface uses AI to search and summarize internal lessons. "
    "Not financial advice. Human review required for any trading decisions."
)


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _fail(errors: list[str]) -> int:
    print("Anthropic compliance check failed:")
    for error in errors:
        print(f"- {error}")
    return 1


def main() -> int:
    errors: list[str] = []

    if not CONFIG_PATH.exists():
        errors.append(f"Missing compliance config: {CONFIG_PATH}")
        return _fail(errors)

    try:
        config = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in compliance config: {exc}")
        return _fail(errors)

    if config.get("version") != "2025-09-15":
        errors.append("Compliance config version must be 2025-09-15")

    high_risk_domains = config.get("high_risk_domains", [])
    if "finance" not in high_risk_domains:
        errors.append("Compliance config must declare finance as high-risk")

    requirements = config.get("requirements", {})
    ai_disclosure = requirements.get("ai_disclosure", {})
    if not ai_disclosure.get("required", False):
        errors.append("AI disclosure requirement must be enabled")

    human_review = requirements.get("human_review", {})
    if not human_review.get("required", False):
        errors.append("Human review requirement must be enabled")

    rag_ui = PROJECT_ROOT / "docs" / "rag-query.html"
    if not rag_ui.exists():
        errors.append("docs/rag-query.html missing")
    else:
        rag_text = _normalize(rag_ui.read_text())
        if DISCLOSURE_TEXT not in rag_text:
            errors.append("RAG UI missing AI disclosure text")

    webhook = PROJECT_ROOT / "src" / "agents" / "rag_webhook.py"
    if not webhook.exists():
        errors.append("src/agents/rag_webhook.py missing")
    else:
        webhook_text = webhook.read_text()
        if "AI_DISCLOSURE_TEXT" not in webhook_text:
            errors.append("Webhook missing AI disclosure constant")
        if DISCLOSURE_TEXT not in _normalize(webhook_text):
            errors.append("Webhook missing AI disclosure text")
        if "ai_disclosure" not in webhook_text:
            errors.append("Webhook missing ai_disclosure field in response")

    guardrails = PROJECT_ROOT / "src" / "orchestration" / "agentic_guardrails.py"
    if not guardrails.exists():
        errors.append("src/orchestration/agentic_guardrails.py missing")
    else:
        guardrails_text = guardrails.read_text().lower()
        if "human review" not in guardrails_text:
            errors.append("Guardrails missing human review requirement")

    if errors:
        return _fail(errors)

    print("Anthropic compliance check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
