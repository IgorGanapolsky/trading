#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from src.utils.llm_gateway import resolve_openrouter_primary_and_fallback_configs
from src.utils.model_selector import get_model_selector, to_tars_model_id

SYSTEM_PROMPT = """You are a quantitative options trading research agent.
Return strict JSON with keys:
should_trade (bool), confidence (0..1), regime (string),
suggested_short_delta (0.05..0.30), suggested_dte (14..60),
reasoning (string), risk_flags (array of strings).
"""

USER_PROMPT = """Context:
- Symbol: SPY
- VIX: 18.2
- Regime: range-bound
- Thompson: wins=18 losses=11 posterior=0.621
- Recent lessons: avoid high-IV events and avoid low-liquidity entries

Produce one actionable trade opinion JSON object only.
"""

# For hackathon evidence we prefer a known-working OpenAI-family model on the
# gateway. This avoids "non-actionable" failures when the BATS selector picks a
# model that isn't enabled on the current gateway profile.
PREFERRED_GATEWAY_MODEL = (
    os.environ.get("TARS_TRADE_OPINION_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
)


def is_actionable(payload: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload_not_object"
    if not isinstance(payload.get("should_trade"), bool):
        return False, "missing_should_trade_bool"
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
        return False, "invalid_confidence"
    if not isinstance(payload.get("regime"), str) or not payload["regime"].strip():
        return False, "missing_regime"
    delta = payload.get("suggested_short_delta")
    if not isinstance(delta, (int, float)) or not (0.05 <= float(delta) <= 0.30):
        return False, "invalid_delta"
    dte = payload.get("suggested_dte")
    if not isinstance(dte, int) or not (14 <= dte <= 60):
        return False, "invalid_dte"
    reasoning = payload.get("reasoning")
    if not isinstance(reasoning, str) or len(reasoning.strip()) < 12:
        return False, "reasoning_too_short"
    risk_flags = payload.get("risk_flags")
    if not isinstance(risk_flags, list):
        return False, "risk_flags_not_list"
    return True, "ok"


def call_model(
    client: Any, model: str, *, system_prompt: str, user_prompt: str
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started = time.time()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    latency_ms = int((time.time() - started) * 1000)
    usage = {
        "prompt_tokens": int(getattr(resp.usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(resp.usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(resp.usage, "total_tokens", 0) or 0),
    }
    content = (resp.choices[0].message.content if resp.choices else "") or ""
    parsed = json.loads(content) if content else None
    return parsed, {"latency_ms": latency_ms, "usage": usage, "raw_len": len(content)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tetrate trade-opinion smoke with fallback verification."
    )
    parser.add_argument(
        "--out", default="artifacts/tars/trade_opinion_smoke.json", help="Artifact output path"
    )
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    primary_cfg, fallback_cfg = resolve_openrouter_primary_and_fallback_configs()
    if not primary_cfg.api_key:
        payload = {
            "ok": False,
            "error": "missing_api_key",
            "actionable": False,
            "actionable_reason": "missing_api_key",
        }
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"error: missing key -> {out}")
        return 2

    from openai import OpenAI

    selector = get_model_selector()
    canonical_model = selector.select_model("pre_trade_research")
    gateway_model = to_tars_model_id(canonical_model)
    using_gateway = bool(primary_cfg.base_url and "openrouter.ai" not in primary_cfg.base_url)

    attempts: list[dict[str, Any]] = []
    actionable = False
    actionable_reason = "no_attempt"
    final_payload: dict[str, Any] | None = None
    chosen_model = ""

    primary_client = OpenAI(api_key=primary_cfg.api_key, base_url=primary_cfg.base_url)
    preferred = (
        to_tars_model_id(PREFERRED_GATEWAY_MODEL) if using_gateway else PREFERRED_GATEWAY_MODEL
    )
    model_order = [preferred]
    # Keep the selector-chosen model in the attempt set for evidence of routing logic,
    # but don't let it block a valid gateway smoke.
    if (gateway_model if using_gateway else canonical_model) not in model_order:
        model_order.append(gateway_model if using_gateway else canonical_model)
    if using_gateway:
        model_order.extend(
            [
                to_tars_model_id("mistralai/mistral-medium-3"),
                to_tars_model_id("deepseek/deepseek-r1"),
            ]
        )
    else:
        model_order.extend(["mistralai/mistral-medium-3", "deepseek/deepseek-r1"])

    for model in model_order:
        try:
            parsed, meta = call_model(
                primary_client, model, system_prompt=SYSTEM_PROMPT, user_prompt=USER_PROMPT
            )
            ok, reason = is_actionable(parsed or {})
            attempts.append(
                {
                    "model": model,
                    "via": "gateway_or_primary",
                    "ok": ok,
                    "reason": reason,
                    **meta,
                }
            )
            if ok and parsed is not None:
                final_payload = parsed
                chosen_model = model
                actionable = True
                actionable_reason = "ok"
                break
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {"model": model, "via": "gateway_or_primary", "ok": False, "reason": str(exc)}
            )

    if not actionable and fallback_cfg:
        try:
            fallback_client = OpenAI(api_key=fallback_cfg.api_key, base_url=fallback_cfg.base_url)
            parsed, meta = call_model(
                fallback_client,
                canonical_model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=USER_PROMPT,
            )
            ok, reason = is_actionable(parsed or {})
            attempts.append(
                {
                    "model": canonical_model,
                    "via": "openrouter_fallback",
                    "ok": ok,
                    "reason": reason,
                    **meta,
                }
            )
            if ok and parsed is not None:
                final_payload = parsed
                chosen_model = canonical_model
                actionable = True
                actionable_reason = "ok"
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                {
                    "model": canonical_model,
                    "via": "openrouter_fallback",
                    "ok": False,
                    "reason": str(exc),
                }
            )

    fallback_probe_ok = False
    if fallback_cfg:
        try:
            fallback_client = OpenAI(api_key=fallback_cfg.api_key, base_url=fallback_cfg.base_url)
            _ = fallback_client.chat.completions.create(
                model="model-does-not-exist-xyz",
                messages=[{"role": "user", "content": "ping"}],
                temperature=0,
            )
        except Exception:
            try:
                parsed, _meta = call_model(
                    fallback_client,
                    canonical_model,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=USER_PROMPT,
                )
                fallback_probe_ok, _ = is_actionable(parsed or {})
            except Exception:
                fallback_probe_ok = False

    result = {
        "ok": actionable,
        "actionable": actionable,
        "actionable_reason": actionable_reason,
        "chosen_model": chosen_model,
        "canonical_model": canonical_model,
        "gateway_model": gateway_model,
        "using_gateway": using_gateway,
        "fallback_available": bool(fallback_cfg),
        "fallback_probe_ok": fallback_probe_ok,
        "attempts": attempts,
        "trade_opinion": final_payload,
    }
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"ok: trade opinion smoke -> {out}")
    if not actionable:
        print("error: non-actionable output")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
