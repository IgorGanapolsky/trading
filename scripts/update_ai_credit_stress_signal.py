#!/usr/bin/env python3
"""Update AI credit stress signal from public credit-spread indicators.

Signal source: FRED public CSV endpoints (no API key required)
Series:
- BAMLH0A0HYM2 (ICE BofA US High Yield OAS)
- BAA10Y (Moody's Seasoned Baa - 10Y Treasury spread)

The resulting signal is used by weekly North Star gating to avoid
over-sizing during elevated credit stress regimes.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "market_signals" / "ai_credit_stress_signal.json"
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "system_state.json"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

SERIES_IDS = {
    "high_yield_oas": "BAMLH0A0HYM2",
    "baa_minus_10y": "BAA10Y",
}


@dataclass
class SeriesSummary:
    series_id: str
    latest_value: float | None
    latest_date: str | None
    lookback_change: float | None
    point_count: int


def _safe_read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_fred_csv(csv_text: str) -> list[tuple[date, float]]:
    """Parse FRED CSV into sorted (date, value) points."""
    rows: list[tuple[date, float]] = []
    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        if not isinstance(row, dict):
            continue
        raw_date = str(row.get("DATE", "")).strip()
        if not raw_date:
            continue
        try:
            dt = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue

        value: float | None = None
        for key, raw_value in row.items():
            if key == "DATE":
                continue
            text = str(raw_value).strip()
            if not text or text == ".":
                continue
            try:
                value = float(text)
                break
            except ValueError:
                continue
        if value is None:
            continue
        rows.append((dt, value))

    rows.sort(key=lambda item: item[0])
    return rows


def summarize_series(series_id: str, points: list[tuple[date, float]], lookback_points: int) -> SeriesSummary:
    if not points:
        return SeriesSummary(
            series_id=series_id,
            latest_value=None,
            latest_date=None,
            lookback_change=None,
            point_count=0,
        )

    latest_date, latest_value = points[-1]
    baseline_idx = max(0, len(points) - 1 - max(1, lookback_points))
    _, baseline_value = points[baseline_idx]
    lookback_change = round(latest_value - baseline_value, 4)
    return SeriesSummary(
        series_id=series_id,
        latest_value=round(latest_value, 4),
        latest_date=latest_date.isoformat(),
        lookback_change=lookback_change,
        point_count=len(points),
    )


def evaluate_ai_credit_stress_signal(metrics: dict[str, SeriesSummary]) -> tuple[str, float, list[str]]:
    """Return (status, severity_score, reasons)."""
    score = 0.0
    reasons: list[str] = []

    hy = metrics.get("high_yield_oas")
    baa = metrics.get("baa_minus_10y")
    has_data = any(
        summary.latest_value is not None for summary in metrics.values() if isinstance(summary, SeriesSummary)
    )
    if not has_data:
        return "unknown", 0.0, ["No credit spread data available."]

    if hy and hy.latest_value is not None:
        if hy.latest_value >= 4.5:
            score += 40
            reasons.append(f"HY OAS elevated: {hy.latest_value:.2f}")
        elif hy.latest_value >= 4.0:
            score += 22
            reasons.append(f"HY OAS watch: {hy.latest_value:.2f}")

        if hy.lookback_change is not None:
            if hy.lookback_change >= 0.5:
                score += 30
                reasons.append(f"HY OAS widened +{hy.lookback_change:.2f}")
            elif hy.lookback_change >= 0.3:
                score += 15
                reasons.append(f"HY OAS widening +{hy.lookback_change:.2f}")

    if baa and baa.latest_value is not None:
        if baa.latest_value >= 3.0:
            score += 25
            reasons.append(f"BAA-10Y elevated: {baa.latest_value:.2f}")
        elif baa.latest_value >= 2.5:
            score += 12
            reasons.append(f"BAA-10Y watch: {baa.latest_value:.2f}")

        if baa.lookback_change is not None:
            if baa.lookback_change >= 0.4:
                score += 20
                reasons.append(f"BAA-10Y widened +{baa.lookback_change:.2f}")
            elif baa.lookback_change >= 0.2:
                score += 10
                reasons.append(f"BAA-10Y widening +{baa.lookback_change:.2f}")

    score = round(min(100.0, score), 2)
    if score >= 60:
        return "blocked", score, reasons
    if score >= 30:
        return "watch", score, reasons
    return "pass", score, reasons


def _fetch_fred_series(
    *,
    series_id: str,
    timeout_seconds: float,
) -> list[tuple[date, float]]:
    url = FRED_CSV_URL.format(series_id=series_id)
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    return parse_fred_csv(response.text)


def _build_payload(
    *,
    metrics: dict[str, SeriesSummary],
    status: str,
    severity_score: float,
    reasons: list[str],
    source: str,
    max_stale_days: int,
) -> dict:
    latest_dates = [
        datetime.strptime(summary.latest_date, "%Y-%m-%d").date()
        for summary in metrics.values()
        if summary.latest_date
    ]
    freshest = max(latest_dates) if latest_dates else None
    stale_days = (date.today() - freshest).days if freshest else None
    stale = stale_days is not None and stale_days > max_stale_days

    effective_status = status
    effective_reasons = list(reasons)
    if stale:
        effective_status = "unknown"
        effective_reasons.append(
            f"Credit spread data stale: {stale_days} days old (max {max_stale_days})"
        )

    return {
        "signal": "ai_credit_stress",
        "status": effective_status,
        "severity_score": severity_score,
        "blocked": effective_status == "blocked",
        "watch": effective_status == "watch",
        "reasons": effective_reasons,
        "latest_data_date": freshest.isoformat() if freshest else None,
        "stale_days": stale_days,
        "metrics": {
            name: {
                "series_id": summary.series_id,
                "latest_value": summary.latest_value,
                "latest_date": summary.latest_date,
                "lookback_change": summary.lookback_change,
                "point_count": summary.point_count,
            }
            for name, summary in metrics.items()
        },
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _apply_override(payload: dict, override_status: str, override_reason: str) -> dict:
    status = override_status.strip().lower()
    if status not in {"pass", "watch", "blocked", "unknown"}:
        return payload
    payload = dict(payload)
    reasons = list(payload.get("reasons", []))
    if override_reason.strip():
        reasons.append(override_reason.strip())
    else:
        reasons.append(f"Manual override applied: {status}")
    payload["status"] = status
    payload["blocked"] = status == "blocked"
    payload["watch"] = status == "watch"
    payload["reasons"] = reasons
    payload["source"] = f"{payload.get('source', 'unknown')}+override"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def _sync_to_system_state(state_path: Path, payload: dict) -> None:
    state = _safe_read_json(state_path)
    if not isinstance(state, dict):
        state = {}
    market_signals = state.get("market_signals")
    if not isinstance(market_signals, dict):
        market_signals = {}
    market_signals["ai_credit_stress"] = payload
    state["market_signals"] = market_signals
    _safe_write_json(state_path, state)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update AI credit stress signal from FRED.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_PATH), help="Signal output JSON path.")
    parser.add_argument(
        "--state",
        default=str(DEFAULT_STATE_PATH),
        help="system_state.json path for --sync-state updates.",
    )
    parser.add_argument(
        "--sync-state",
        action="store_true",
        help="Write signal payload into system_state.market_signals.ai_credit_stress.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip network fetch and reuse existing output payload if available.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds for each FRED request.",
    )
    parser.add_argument(
        "--lookback-points",
        type=int,
        default=5,
        help="How many points back to compute widening change.",
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=7,
        help="Mark signal unknown when freshest data exceeds this age.",
    )
    parser.add_argument(
        "--override-status",
        default="",
        help="Optional manual override status: pass/watch/blocked/unknown.",
    )
    parser.add_argument(
        "--override-reason",
        default="",
        help="Optional text appended to reasons when override is used.",
    )
    parser.add_argument("--print-json", action="store_true", help="Print payload JSON to stdout.")
    args = parser.parse_args()

    out_path = Path(args.out).resolve()
    state_path = Path(args.state).resolve()
    existing_payload = _safe_read_json(out_path)

    if args.offline:
        payload = (
            existing_payload
            if existing_payload
            else {
                "signal": "ai_credit_stress",
                "status": "unknown",
                "severity_score": 0.0,
                "blocked": False,
                "watch": False,
                "reasons": ["Offline mode with no prior signal available."],
                "latest_data_date": None,
                "stale_days": None,
                "metrics": {},
                "source": "offline",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    else:
        summaries: dict[str, SeriesSummary] = {}
        fetch_errors: list[str] = []
        for name, series_id in SERIES_IDS.items():
            try:
                points = _fetch_fred_series(
                    series_id=series_id,
                    timeout_seconds=args.timeout_seconds,
                )
                summaries[name] = summarize_series(
                    series_id=series_id,
                    points=points,
                    lookback_points=max(1, args.lookback_points),
                )
            except Exception as exc:  # noqa: BLE001 - network failures handled with fallback
                fetch_errors.append(f"{series_id}: {exc}")
                summaries[name] = SeriesSummary(
                    series_id=series_id,
                    latest_value=None,
                    latest_date=None,
                    lookback_change=None,
                    point_count=0,
                )

        status, score, reasons = evaluate_ai_credit_stress_signal(summaries)
        source = "fred_public"
        payload = _build_payload(
            metrics=summaries,
            status=status,
            severity_score=score,
            reasons=reasons,
            source=source,
            max_stale_days=max(1, args.max_stale_days),
        )

        if fetch_errors:
            payload["reasons"] = list(payload.get("reasons", [])) + fetch_errors
            if not reasons and existing_payload:
                payload = dict(existing_payload)
                payload["source"] = "cached_fallback"
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                payload["reasons"] = list(payload.get("reasons", [])) + fetch_errors

    if args.override_status:
        payload = _apply_override(
            payload,
            override_status=args.override_status,
            override_reason=args.override_reason,
        )

    _safe_write_json(out_path, payload)
    if args.sync_state:
        _sync_to_system_state(state_path, payload)

    print(
        "ok: ai credit stress signal updated",
        f"status={payload.get('status')}",
        f"score={payload.get('severity_score')}",
        f"out={out_path}",
    )
    if args.print_json:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
