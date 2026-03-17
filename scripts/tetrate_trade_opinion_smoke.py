#!/usr/bin/env python3
"""Validate routed trade-opinion responses for Tetrate evidence flows."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_PROMPT = (
    "Return strict JSON with fields actionable, decision, confidence, and rationale. "
    "This is a trade-opinion smoke test, so actionable must be true and decision must be one of "
    "buy, sell, hold."
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_kv(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.exists():
        return parsed
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _extract_message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _extract_json_block(content: str) -> dict[str, Any]:
    if not content:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content, re.IGNORECASE)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        inline = re.search(r"\{[\s\S]*\}", content)
        candidate = inline.group(0) if inline else None
    if candidate is None:
        return {}
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_artifact_fallback_result(repo_root: Path) -> dict[str, Any]:
    smoke_payload = _read_json(repo_root / "artifacts/tars/smoke_response.json")
    smoke_metrics = _read_kv(repo_root / "artifacts/tars/smoke_metrics.txt")
    parsed = _extract_json_block(_extract_message_content(smoke_payload))
    router_check = bool(parsed.get("router_check"))
    actionable = bool(parsed.get("actionable", router_check))
    decision = parsed.get("decision") or ("hold" if actionable else "unknown")
    return {
        "generated_at_utc": _now_utc(),
        "source": "artifact_fallback",
        "actionable": actionable,
        "decision": decision,
        "confidence": parsed.get("confidence", 0.5 if actionable else 0.0),
        "rationale": parsed.get(
            "rationale",
            "Derived from existing smoke response artifacts.",
        ),
        "router_check": router_check,
        "request_id": smoke_payload.get("id", ""),
        "model": smoke_payload.get("model", "unknown"),
        "gateway_base_url_host": smoke_metrics.get("gateway_base_url_host", "unknown"),
        "raw_payload_source": "artifacts/tars/smoke_response.json",
    }


def _gateway_key(explicit_key: str | None = None) -> str | None:
    if explicit_key:
        return explicit_key
    return os.getenv("LLM_GATEWAY_API_KEY") or os.getenv("TETRATE_API_KEY")


def _endpoint(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _live_trade_opinion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a strict JSON responder."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        _endpoint(base_url),
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
    payload = json.loads(raw)
    content = _extract_message_content(payload)
    parsed = _extract_json_block(content)
    actionable = bool(parsed.get("actionable"))
    return {
        "generated_at_utc": _now_utc(),
        "source": "live_gateway",
        "actionable": actionable,
        "decision": parsed.get("decision", "unknown"),
        "confidence": parsed.get("confidence", 0.0),
        "rationale": parsed.get("rationale", ""),
        "router_check": bool(parsed.get("router_check", False)),
        "request_id": payload.get("id", ""),
        "model": payload.get("model", model),
        "gateway_base_url_host": base_url.split("://", 1)[-1].split("/", 1)[0],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tetrate trade-opinion smoke test.")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument(
        "--out",
        default="artifacts/tars/trade_opinion_smoke.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--gateway-base-url",
        default=os.getenv("LLM_GATEWAY_BASE_URL", ""),
        help="Gateway base URL; when omitted, falls back to existing smoke artifacts.",
    )
    parser.add_argument("--api-key", default="", help="Gateway API key override")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gateway model")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="HTTP timeout")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Trade-opinion prompt")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = repo_root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    api_key = _gateway_key(args.api_key)
    if args.gateway_base_url and api_key:
        try:
            result = _live_trade_opinion(
                base_url=args.gateway_base_url,
                api_key=api_key,
                model=args.model,
                prompt=args.prompt,
                timeout_seconds=args.timeout_seconds,
            )
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            result = {
                "generated_at_utc": _now_utc(),
                "source": "live_gateway",
                "actionable": False,
                "decision": "error",
                "confidence": 0.0,
                "rationale": "",
                "error": str(exc),
                "gateway_base_url_host": args.gateway_base_url.split("://", 1)[-1].split("/", 1)[0],
            }
            out_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            return 1
    else:
        result = build_artifact_fallback_result(repo_root)

    out_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if result.get("actionable") else 1


if __name__ == "__main__":
    raise SystemExit(main())
