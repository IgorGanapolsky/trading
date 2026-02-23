#!/usr/bin/env python3
"""Run local-vs-anchor browser automation pilot and persist metrics."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.browser_automation_pilot import (
    ANCHOR_DEFAULT_BASE_URL,
    AnchorBrowserProvider,
    LocalHTTPProvider,
    append_results_jsonl,
    load_tasks,
    run_browser_ab_pilot,
    write_summary_json,
)
from src.analytics.browser_provider_promotion import (
    load_policy,
    load_previous_provider,
    recommend_provider,
    write_promotion_report,
    write_provider_state,
)


def _provider_list(
    names: list[str],
    *,
    anchor_api_key: str | None,
    anchor_base_url: str,
    anchor_task_path: str,
    anchor_retries: int,
    anchor_dry_run: bool,
) -> list[Any]:
    out: list[Any] = []
    for raw in names:
        name = raw.strip().lower()
        if name == "local":
            out.append(LocalHTTPProvider())
        elif name == "anchor":
            out.append(
                AnchorBrowserProvider(
                    api_key=anchor_api_key,
                    base_url=anchor_base_url,
                    task_path=anchor_task_path,
                    max_retries=anchor_retries,
                    dry_run=anchor_dry_run,
                )
            )
        else:
            raise ValueError(f"Unsupported provider: {raw}")
    return out


def _print_summary(summary: dict[str, Any]) -> None:
    print("\nBrowser Automation Pilot Summary")
    print("=" * 80)
    for provider, row in summary.items():
        success_rate = row.get("success_rate")
        success_rate_fmt = "N/A" if success_rate is None else f"{success_rate * 100:.2f}%"
        cps = row.get("cost_per_success_usd")
        cps_fmt = "N/A" if cps is None else f"${cps:.6f}"
        print(
            " | ".join(
                [
                    f"provider={provider}",
                    f"runs={row.get('runs_total')}",
                    f"attempted={row.get('attempted')}",
                    f"success={row.get('success')}",
                    f"failed={row.get('failed')}",
                    f"skipped={row.get('skipped')}",
                    f"success_rate={success_rate_fmt}",
                    f"avg_latency_ms={row.get('avg_latency_ms'):.3f}",
                    f"avg_retries={row.get('avg_retries'):.3f}",
                    f"cost_total=${row.get('cost_usd_total'):.6f}",
                    f"cost_per_success={cps_fmt}",
                ]
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run browser automation A/B pilot.")
    parser.add_argument(
        "--tasks",
        default="config/browser_automation_pilot_tasks.json",
        help="Path to JSON task config.",
    )
    parser.add_argument(
        "--providers",
        default="local,anchor",
        help="Comma-separated providers: local,anchor",
    )
    parser.add_argument("--runs-per-task", type=int, default=1, help="Runs per task per provider.")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="HTTP request timeout.")
    parser.add_argument(
        "--jsonl-out",
        default="data/analytics/browser_automation_pilot_history.jsonl",
        help="JSONL history output path.",
    )
    parser.add_argument(
        "--summary-out",
        default="data/analytics/browser_automation_pilot_latest.json",
        help="Summary JSON output path.",
    )
    parser.add_argument(
        "--provider-state-out",
        default="config/browser_automation_provider.json",
        help="Provider state JSON path for downstream workflows.",
    )
    parser.add_argument(
        "--promotion-report-out",
        default="data/analytics/browser_provider_promotion_latest.json",
        help="Detailed provider promotion report output path.",
    )
    parser.add_argument(
        "--promotion-policy",
        default="config/browser_provider_promotion_policy.json",
        help="Promotion policy JSON (optional; defaults applied if missing).",
    )
    parser.add_argument(
        "--anchor-base-url",
        default=os.getenv("ANCHOR_API_BASE_URL", ANCHOR_DEFAULT_BASE_URL),
        help="Anchor API base URL.",
    )
    parser.add_argument(
        "--anchor-task-path",
        default=os.getenv("ANCHOR_TASK_PATH", "/api/v1/ai-tools/perform-web-task"),
        help="Anchor task endpoint path.",
    )
    parser.add_argument(
        "--anchor-retries", type=int, default=1, help="Retries for Anchor task calls."
    )
    parser.add_argument(
        "--anchor-dry-run",
        action="store_true",
        help="Skip live Anchor calls (records skipped runs).",
    )
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=0.0,
        help="Fail run if any provider attempted runs with success_rate below threshold.",
    )
    args = parser.parse_args()

    task_path = PROJECT_ROOT / args.tasks
    tasks = load_tasks(task_path)
    provider_names = [name.strip() for name in args.providers.split(",") if name.strip()]
    anchor_api_key = os.getenv("ANCHOR_API_KEY")

    providers = _provider_list(
        provider_names,
        anchor_api_key=anchor_api_key,
        anchor_base_url=args.anchor_base_url,
        anchor_task_path=args.anchor_task_path,
        anchor_retries=args.anchor_retries,
        anchor_dry_run=args.anchor_dry_run,
    )

    payload = run_browser_ab_pilot(
        tasks=tasks,
        providers=providers,
        runs_per_task=args.runs_per_task,
        timeout_seconds=args.timeout_seconds,
    )

    jsonl_out = PROJECT_ROOT / args.jsonl_out
    summary_out = PROJECT_ROOT / args.summary_out
    provider_state_out = PROJECT_ROOT / args.provider_state_out
    promotion_report_out = PROJECT_ROOT / args.promotion_report_out
    policy_path = PROJECT_ROOT / args.promotion_policy
    append_results_jsonl(jsonl_out, payload["results"])
    write_summary_json(summary_out, payload)

    previous_provider = load_previous_provider(provider_state_out)
    promotion_policy = load_policy(policy_path)
    recommendation = recommend_provider(
        payload["summary"],
        policy=promotion_policy,
        previous_provider=previous_provider,
    )
    write_provider_state(
        provider_state_out,
        recommendation=recommendation,
        run_id=str(payload["run_id"]),
        generated_at_utc=str(payload["generated_at_utc"]),
    )
    write_promotion_report(
        promotion_report_out,
        recommendation=recommendation,
        payload=payload,
    )

    print(json.dumps(payload, indent=2))
    print(f"Wrote JSONL history: {jsonl_out}")
    print(f"Wrote summary JSON: {summary_out}")
    print(f"Wrote provider state: {provider_state_out}")
    print(f"Wrote promotion report: {promotion_report_out}")
    _print_summary(payload["summary"])
    print(
        "Provider recommendation: "
        f"{recommendation['recommended_provider']} "
        f"(confidence={recommendation['confidence']}, reason={recommendation['reason']})"
    )

    if args.min_success_rate <= 0:
        return 0

    below_threshold: list[str] = []
    for provider, row in payload["summary"].items():
        attempted = int(row.get("attempted", 0))
        success_rate = row.get("success_rate")
        if attempted <= 0 or success_rate is None:
            continue
        if float(success_rate) < args.min_success_rate:
            below_threshold.append(provider)

    if below_threshold:
        print(
            "Pilot failed minimum success-rate gate. "
            f"providers={below_threshold}, threshold={args.min_success_rate:.3f}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
