"""Inception Labs Mercury 2 model adapter.

OpenAI-compatible chat completions at https://api.inceptionlabs.ai/v1
for high-throughput agent loops on the free-tier 100M token pool.

Key resolution order (first hit wins):
1. Explicit ``api_key`` constructor arg
2. Env: ``INCEPTION_API_KEY`` / ``INCEPTION_LABS_API_KEY`` / ``MERCURY_2_API_KEY``
3. Vault: ``~/.resume_secrets/inception.json`` (``INCEPTION_API_KEY``)
4. Optional ``.env`` at repo root (same env names)

NOT Mercury Bank. This is LLM inference only.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
INCEPTION_BASE_URL = "https://api.inceptionlabs.ai/v1"
DEFAULT_MODEL = "mercury-2"
VAULT_PATH = Path.home() / ".resume_secrets" / "inception.json"

# Public list prices (USD / 1M tokens) for ROI math — free tier burns grant first.
# Source: Inception Mercury 2 marketing (2026-07).
PRICE_INPUT_PER_MTOK = 0.25
PRICE_OUTPUT_PER_MTOK = 0.75


@dataclass
class InceptionResponse:
    content: str
    model: str
    tokens_used: int
    success: bool
    status_code: int
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    estimated_cost_usd: float = 0.0
    error: str = ""


@dataclass
class InceptionROIReport:
    """Aggregate proof for high-ROI free-tier usage."""

    n_calls: int = 0
    successes: int = 0
    failures: int = 0
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_latency_ms: float = 0.0
    estimated_paid_cost_usd: float = 0.0
    free_tier_savings_usd: float = 0.0
    tasks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.successes:
            d["avg_latency_ms"] = round(self.total_latency_ms / self.successes, 1)
            d["avg_tokens_per_call"] = round(self.total_tokens / self.successes, 1)
        else:
            d["avg_latency_ms"] = None
            d["avg_tokens_per_call"] = None
        d["success_rate"] = round(self.successes / self.n_calls, 3) if self.n_calls else None
        return d


def resolve_inception_api_key(
    *,
    api_key: str | None = None,
    env_path: Path | None = None,
    vault_path: Path | None = None,
) -> str | None:
    """Resolve API key without printing it."""
    if api_key and str(api_key).strip():
        return str(api_key).strip()

    for env_name in (
        "INCEPTION_API_KEY",
        "INCEPTION_LABS_API_KEY",
        "MERCURY_2_API_KEY",
    ):
        val = (os.environ.get(env_name) or "").strip()
        if val:
            return val

    vault = vault_path or VAULT_PATH
    if vault.exists():
        try:
            data = json.loads(vault.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k in (
                    "INCEPTION_API_KEY",
                    "INCEPTION_LABS_API_KEY",
                    "MERCURY_2_API_KEY",
                    "api_key",
                ):
                    v = data.get(k)
                    if v and str(v).strip():
                        return str(v).strip()
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Failed reading Inception vault: %s", exc)

    path = env_path or (ROOT / ".env")
    if path.exists():
        try:
            from dotenv import dotenv_values

            vals = dotenv_values(path)
            for k in (
                "INCEPTION_API_KEY",
                "INCEPTION_LABS_API_KEY",
                "MERCURY_2_API_KEY",
            ):
                v = (vals.get(k) or "").strip() if vals else ""
                if v:
                    return v
        except Exception as exc:  # pragma: no cover
            logger.debug("dotenv parse skipped: %s", exc)

    return None


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens / 1_000_000.0) * PRICE_INPUT_PER_MTOK + (
        completion_tokens / 1_000_000.0
    ) * PRICE_OUTPUT_PER_MTOK


class InceptionLabsMercuryAdapter:
    """Mercury 2 inference + free-tier ROI accounting."""

    def __init__(
        self,
        api_key: str | None = None,
        env_path: Path | None = None,
        vault_path: Path | None = None,
        model: str = DEFAULT_MODEL,
        timeout_s: float = 45.0,
    ):
        self.env_path = env_path or (ROOT / ".env")
        self.vault_path = vault_path or VAULT_PATH
        self.model = model
        self.timeout_s = timeout_s
        self.api_key = resolve_inception_api_key(
            api_key=api_key,
            env_path=self.env_path,
            vault_path=self.vault_path,
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def completion(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        *,
        model: str | None = None,
    ) -> InceptionResponse:
        if not self.api_key:
            return InceptionResponse(
                content="",
                model=model or self.model,
                tokens_used=0,
                success=False,
                status_code=401,
                error="missing_api_key",
            )

        url = f"{INCEPTION_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        t0 = time.perf_counter()
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            if r.status_code == 200:
                data = r.json()
                content = ((data.get("choices") or [{}])[0].get("message") or {}).get(
                    "content"
                ) or ""
                usage = data.get("usage") or {}
                prompt_tok = int(usage.get("prompt_tokens") or 0)
                completion_tok = int(usage.get("completion_tokens") or 0)
                reasoning_tok = int(usage.get("reasoning_tokens") or 0)
                total = int(
                    usage.get("total_tokens") or (prompt_tok + completion_tok + reasoning_tok)
                )
                cost = _estimate_cost(prompt_tok, completion_tok)
                return InceptionResponse(
                    content=str(content),
                    model=str(data.get("model") or (model or self.model)),
                    tokens_used=total,
                    success=True,
                    status_code=200,
                    latency_ms=round(latency_ms, 1),
                    prompt_tokens=prompt_tok,
                    completion_tokens=completion_tok,
                    reasoning_tokens=reasoning_tok,
                    estimated_cost_usd=round(cost, 8),
                )
            return InceptionResponse(
                content="",
                model=model or self.model,
                tokens_used=0,
                success=False,
                status_code=r.status_code,
                latency_ms=round(latency_ms, 1),
                error=(r.text or "")[:300],
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning("Inception Labs API request error: %s", e)
            return InceptionResponse(
                content="",
                model=model or self.model,
                tokens_used=0,
                success=False,
                status_code=500,
                latency_ms=round(latency_ms, 1),
                error=str(e)[:300],
            )

    def run_roi_suite(
        self,
        tasks: list[dict[str, str]] | None = None,
    ) -> InceptionROIReport:
        """Run high-ROI agent-style tasks and return aggregate metrics.

        Each task: {name, prompt, system?}
        """
        if tasks is None:
            tasks = _default_high_roi_tasks()

        report = InceptionROIReport()
        for task in tasks:
            report.n_calls += 1
            name = task.get("name") or f"task_{report.n_calls}"
            res = self.completion(
                prompt=task["prompt"],
                system_prompt=task.get("system"),
                max_tokens=int(task.get("max_tokens") or 256),
                temperature=float(task.get("temperature") or 0.2),
            )
            entry = {
                "name": name,
                "success": res.success,
                "status_code": res.status_code,
                "latency_ms": res.latency_ms,
                "tokens_used": res.tokens_used,
                "prompt_tokens": res.prompt_tokens,
                "completion_tokens": res.completion_tokens,
                "estimated_cost_usd": res.estimated_cost_usd,
                "content_preview": (res.content or "")[:120],
                "error": res.error[:120] if res.error else "",
            }
            report.tasks.append(entry)
            if res.success:
                report.successes += 1
                report.total_tokens += res.tokens_used
                report.total_prompt_tokens += res.prompt_tokens
                report.total_completion_tokens += res.completion_tokens
                report.total_latency_ms += res.latency_ms
                report.estimated_paid_cost_usd += res.estimated_cost_usd
            else:
                report.failures += 1

        # Free tier: paid cost avoided = estimated list price of tokens used
        report.free_tier_savings_usd = round(report.estimated_paid_cost_usd, 6)
        report.estimated_paid_cost_usd = round(report.estimated_paid_cost_usd, 6)
        return report


def _default_high_roi_tasks() -> list[dict[str, str]]:
    """Tasks that map to real operator loops (summarize, gate, triage)."""
    return [
        {
            "name": "put_credit_cohort_summary",
            "system": "You are a trading risk analyst. Be concise. No invented numbers.",
            "prompt": (
                "Summarize in 3 bullets for an operator: paper SPY put-credit "
                "validation, n_closed=0/30, 2 open 1-lot structures, live blocked, "
                "iron condor killed. What is the single next action?"
            ),
            "max_tokens": "400",
        },
        {
            "name": "ci_failure_triage",
            "system": "You are a senior engineer. Prioritize root causes.",
            "prompt": (
                "Tests fail because ALLOWED_TICKERS was restored to SPY-only but "
                "test_pre_trade_checklist still expects XSP/SPX/QQQ/IWM. "
                "Give a 2-step fix plan."
            ),
            "max_tokens": "400",
        },
        {
            "name": "remittance_truth",
            "system": "Answer only from given facts. No projections.",
            "prompt": (
                "Facts: remitted_to_bank=$0, target=$1000/mo, paper_only=true, "
                "live_blocked=true, put_credit closed_n=0. "
                "Is the $1000/mo after-tax target met? One sentence + one reason."
            ),
            "max_tokens": "200",
        },
        {
            "name": "tool_loop_style",
            "system": "Output valid JSON only.",
            "prompt": (
                'Return JSON: {"action":"hold|exit|enter","reason":"..."} '
                "for a paper SPY put credit with 2/2 concurrent positions filled."
            ),
            "max_tokens": "200",
        },
    ]
