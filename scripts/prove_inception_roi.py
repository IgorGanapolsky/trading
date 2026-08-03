#!/usr/bin/env python3
"""Prove Inception Mercury 2 free-tier high-ROI improvements.

Runs a live ROI suite against the vaulted key (or env), writes
data/audit/inception_roi_latest.json, prints a summary (no secrets).

Exit 0 if configured + all suite tasks succeed.
Exit 2 if key missing.
Exit 1 if any task fails.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.observability.inception_labs_adapter import (  # noqa: E402
    InceptionLabsMercuryAdapter,
)


def main() -> int:
    adapter = InceptionLabsMercuryAdapter()
    out = {
        "generated_at": datetime.now(UTC).isoformat(),
        "configured": adapter.configured,
        "model": adapter.model,
        "api_base": "https://api.inceptionlabs.ai/v1",
        "free_tier_tokens": 100_000_000,
        "note": "LLM free compute only — not Mercury Bank remittance",
    }

    if not adapter.configured:
        out["error"] = "missing_api_key"
        _write(out)
        print(json.dumps(out, indent=2))
        return 2

    # ping
    ping = adapter.completion("Reply with exactly: OK", max_tokens=16)
    out["ping"] = {
        "success": ping.success,
        "status_code": ping.status_code,
        "latency_ms": ping.latency_ms,
        "tokens_used": ping.tokens_used,
        "content_preview": (ping.content or "")[:40],
        "error": ping.error[:120] if ping.error else "",
    }

    report = adapter.run_roi_suite()
    out["roi"] = report.to_dict()

    # High-ROI verdict
    out["verdict"] = {
        "api_live": bool(ping.success),
        "suite_all_passed": report.failures == 0 and report.successes == report.n_calls,
        "avg_latency_ms": report.to_dict().get("avg_latency_ms"),
        "free_tier_savings_usd_this_run": report.free_tier_savings_usd,
        "claim": (
            "Mercury 2 free tier is usable for agent loops; savings are list-price "
            "avoided under free grant, not cash P/L."
        ),
    }

    path = _write(out)
    print(json.dumps(out, indent=2))
    print(f"\nwrote {path}", file=sys.stderr)

    if not ping.success or report.failures:
        return 1
    return 0


def _write(payload: dict) -> Path:
    path = ROOT / "data" / "audit" / "inception_roi_latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
