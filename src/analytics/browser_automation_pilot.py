"""A/B pilot runner for browser automation reliability and cost tracking.

This module compares local automation against AnchorBrowser for the same URL-level
tasks and records objective metrics:
- success rate
- retries
- latency
- total cost
- cost per success
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

ANCHOR_DEFAULT_BASE_URL = "https://api.anchorbrowser.io"
ANCHOR_DEFAULT_TASK_PATH = "/api/v1/ai-tools/perform-web-task"


@dataclass(frozen=True)
class BrowserPilotTask:
    """Single browser automation task used for pilot comparisons."""

    task_id: str
    url: str
    prompt: str
    expected_text: str | None = None
    tags: list[str] | None = None


@dataclass(frozen=True)
class BrowserPilotRunResult:
    """Immutable result for one provider-task execution attempt."""

    provider: str
    task_id: str
    run_index: int
    status: str  # success | failed | skipped
    detail: str
    started_at_utc: str
    latency_ms: float
    retries: int
    http_status: int | None = None
    cost_usd: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_tasks(config_path: Path) -> list[BrowserPilotTask]:
    """Load pilot tasks from JSON config.

    Accepted JSON shapes:
    - {"tasks": [{...}, {...}]}
    - [{...}, {...}]
    """
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    raw_tasks = payload.get("tasks", []) if isinstance(payload, dict) else payload

    if not isinstance(raw_tasks, list):
        raise ValueError("Task config must contain a list of tasks.")

    tasks: list[BrowserPilotTask] = []
    seen_ids: set[str] = set()
    for idx, row in enumerate(raw_tasks, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Task #{idx} must be an object.")
        task_id = str(row.get("task_id", "")).strip()
        url = str(row.get("url", "")).strip()
        prompt = str(row.get("prompt", "")).strip()
        if not task_id:
            raise ValueError(f"Task #{idx} missing task_id.")
        if task_id in seen_ids:
            raise ValueError(f"Duplicate task_id: {task_id}")
        if not url:
            raise ValueError(f"Task {task_id} missing url.")
        if not prompt:
            prompt = f"Open {url} and confirm the page is accessible."

        expected_text = row.get("expected_text")
        tags = row.get("tags")
        tag_list = [str(tag) for tag in tags] if isinstance(tags, list) else None
        tasks.append(
            BrowserPilotTask(
                task_id=task_id,
                url=url,
                prompt=prompt,
                expected_text=str(expected_text) if expected_text else None,
                tags=tag_list,
            )
        )
        seen_ids.add(task_id)
    return tasks


class LocalHTTPProvider:
    """Local baseline provider using direct HTTP fetch checks."""

    name = "local"

    def execute(
        self,
        task: BrowserPilotTask,
        *,
        run_index: int,
        timeout_seconds: int,
    ) -> BrowserPilotRunResult:
        started_at = _utc_now_iso()
        t0 = time.perf_counter()
        try:
            response = requests.get(
                task.url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; trading-browser-pilot/1.0; +https://github.com/"
                        "IgorGanapolsky/trading)"
                    )
                },
                timeout=timeout_seconds,
            )
            body_text = response.text or ""
            if response.status_code >= 400:
                status = "failed"
                detail = f"HTTP {response.status_code}"
            elif task.expected_text and task.expected_text not in body_text:
                status = "failed"
                detail = "Expected text not found."
            else:
                status = "success"
                detail = "HTTP fetch check passed."
            return BrowserPilotRunResult(
                provider=self.name,
                task_id=task.task_id,
                run_index=run_index,
                status=status,
                detail=detail,
                started_at_utc=started_at,
                latency_ms=_latency_ms(t0),
                retries=0,
                http_status=response.status_code,
            )
        except Exception as exc:  # pragma: no cover - defensive
            return BrowserPilotRunResult(
                provider=self.name,
                task_id=task.task_id,
                run_index=run_index,
                status="failed",
                detail=f"Local HTTP exception: {exc}",
                started_at_utc=started_at,
                latency_ms=_latency_ms(t0),
                retries=0,
            )


class AnchorBrowserProvider:
    """AnchorBrowser provider using its remote browser task endpoint."""

    name = "anchor"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = ANCHOR_DEFAULT_BASE_URL,
        task_path: str = ANCHOR_DEFAULT_TASK_PATH,
        max_retries: int = 1,
        dry_run: bool = False,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.task_path = task_path
        self.max_retries = max(0, int(max_retries))
        self.dry_run = dry_run

    def execute(
        self,
        task: BrowserPilotTask,
        *,
        run_index: int,
        timeout_seconds: int,
    ) -> BrowserPilotRunResult:
        started_at = _utc_now_iso()
        t0 = time.perf_counter()
        if not self.api_key:
            return BrowserPilotRunResult(
                provider=self.name,
                task_id=task.task_id,
                run_index=run_index,
                status="skipped",
                detail="ANCHOR_API_KEY missing.",
                started_at_utc=started_at,
                latency_ms=_latency_ms(t0),
                retries=0,
            )

        if self.dry_run:
            return BrowserPilotRunResult(
                provider=self.name,
                task_id=task.task_id,
                run_index=run_index,
                status="skipped",
                detail="Dry-run enabled; Anchor call skipped.",
                started_at_utc=started_at,
                latency_ms=_latency_ms(t0),
                retries=0,
            )

        endpoint = f"{self.base_url}{self.task_path}"
        payload = {
            "task": task.prompt,
            "url": task.url,
            "metadata": {
                "task_id": task.task_id,
                "tags": task.tags or [],
                "source": "trading-browser-pilot",
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = "Unknown Anchor error."
        last_http_status: int | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=timeout_seconds,
                )
                last_http_status = response.status_code
                body = _safe_json(response)
                response_cost = _extract_anchor_cost(body)
                status = _derive_anchor_status(response.status_code, body)
                detail = _derive_anchor_detail(response.status_code, body)
                if status == "success":
                    return BrowserPilotRunResult(
                        provider=self.name,
                        task_id=task.task_id,
                        run_index=run_index,
                        status="success",
                        detail=detail,
                        started_at_utc=started_at,
                        latency_ms=_latency_ms(t0),
                        retries=attempt,
                        http_status=response.status_code,
                        cost_usd=response_cost,
                    )
                last_error = detail
            except Exception as exc:  # pragma: no cover - defensive
                last_error = f"Anchor request exception: {exc}"

            if attempt < self.max_retries:
                time.sleep(0.5)

        return BrowserPilotRunResult(
            provider=self.name,
            task_id=task.task_id,
            run_index=run_index,
            status="failed",
            detail=last_error,
            started_at_utc=started_at,
            latency_ms=_latency_ms(t0),
            retries=self.max_retries,
            http_status=last_http_status,
            cost_usd=0.0,
        )


def run_browser_ab_pilot(
    *,
    tasks: list[BrowserPilotTask],
    providers: list[Any],
    runs_per_task: int,
    timeout_seconds: int,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run A/B pilot and return detailed + aggregated metrics."""
    if runs_per_task < 1:
        raise ValueError("runs_per_task must be >= 1")

    pilot_run_id = run_id or datetime.now(UTC).strftime("pilot-%Y%m%dT%H%M%SZ")
    results: list[BrowserPilotRunResult] = []

    for task in tasks:
        for run_index in range(1, runs_per_task + 1):
            for provider in providers:
                result = provider.execute(
                    task,
                    run_index=run_index,
                    timeout_seconds=timeout_seconds,
                )
                results.append(result)

    provider_summary = summarize_provider_results(results)
    return {
        "run_id": pilot_run_id,
        "generated_at_utc": _utc_now_iso(),
        "tasks": [asdict(task) for task in tasks],
        "providers": list(provider_summary.keys()),
        "runs_per_task": runs_per_task,
        "results": [result.as_dict() for result in results],
        "summary": provider_summary,
    }


def summarize_provider_results(results: list[BrowserPilotRunResult]) -> dict[str, dict[str, Any]]:
    """Aggregate pilot results per provider."""
    buckets: dict[str, dict[str, Any]] = {}
    for result in results:
        bucket = buckets.setdefault(
            result.provider,
            {
                "runs_total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "latency_ms_total": 0.0,
                "retries_total": 0,
                "cost_usd_total": 0.0,
            },
        )
        bucket["runs_total"] += 1
        bucket["latency_ms_total"] += float(result.latency_ms)
        bucket["retries_total"] += int(result.retries)
        bucket["cost_usd_total"] += float(result.cost_usd)
        if result.status not in {"success", "failed", "skipped"}:
            bucket["failed"] += 1
        else:
            bucket[result.status] += 1

    summary: dict[str, dict[str, Any]] = {}
    for provider, bucket in buckets.items():
        attempted = bucket["success"] + bucket["failed"]
        success_rate = float(bucket["success"] / attempted) if attempted else None
        avg_latency_ms = float(bucket["latency_ms_total"] / bucket["runs_total"])
        avg_retries = float(bucket["retries_total"] / bucket["runs_total"])
        cost_per_success = (
            float(bucket["cost_usd_total"] / bucket["success"]) if bucket["success"] else None
        )
        summary[provider] = {
            "runs_total": bucket["runs_total"],
            "attempted": attempted,
            "success": bucket["success"],
            "failed": bucket["failed"],
            "skipped": bucket["skipped"],
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency_ms,
            "avg_retries": avg_retries,
            "cost_usd_total": float(bucket["cost_usd_total"]),
            "cost_per_success_usd": cost_per_success,
        }
    return summary


def append_results_jsonl(path: Path, results: list[dict[str, Any]]) -> None:
    """Append result rows to JSONL history."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row) + "\n")


def write_summary_json(path: Path, payload: dict[str, Any]) -> None:
    """Write summary payload as pretty JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
        return payload if isinstance(payload, dict) else {"raw": payload}
    except Exception:
        return {"raw_text": response.text[:500]}


def _extract_anchor_cost(payload: dict[str, Any]) -> float:
    for key in ("cost_usd", "estimated_cost_usd", "cost", "price"):
        value = payload.get(key)
        parsed = _to_float(value)
        if parsed is not None:
            return parsed

    usage = payload.get("usage")
    if isinstance(usage, dict):
        for key in ("cost_usd", "estimated_cost_usd", "cost"):
            parsed = _to_float(usage.get(key))
            if parsed is not None:
                return parsed
    return 0.0


def _derive_anchor_status(http_status: int, payload: dict[str, Any]) -> str:
    status_field = str(payload.get("status", "")).strip().lower()
    if status_field in {"ok", "success", "completed"}:
        return "success"
    if status_field in {"failed", "error", "denied"}:
        return "failed"

    if "success" in payload:
        return "success" if bool(payload.get("success")) else "failed"

    return "success" if http_status < 400 else "failed"


def _derive_anchor_detail(http_status: int, payload: dict[str, Any]) -> str:
    for key in ("detail", "message", "error"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    status_field = str(payload.get("status", "")).strip()
    if status_field:
        return f"Anchor status={status_field}"
    return f"HTTP {http_status}"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _latency_ms(start_time: float) -> float:
    return round((time.perf_counter() - start_time) * 1000.0, 3)
