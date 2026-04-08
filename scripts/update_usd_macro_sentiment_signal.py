#!/usr/bin/env python3
"""Update USD macro sentiment signal from public macro indicators.

Signal source: FRED public CSV endpoints (no API key required)
Series:
- DTWEXBGS (Trade Weighted U.S. Dollar Index: Broad)
- DEXUSEU (U.S. Dollars to One Euro)

The resulting signal is consumed by the weekly North Star gate as a *soft*
position-size multiplier (never a standalone hard trade block).
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
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "market_signals" / "usd_macro_sentiment_signal.json"
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "system_state.json"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

SERIES_IDS = {
    "broad_usd_index": "DTWEXBGS",
    "usd_per_euro": "DEXUSEU",
}

WATCH_SCORE = 30.0
BLOCK_SCORE = 60.0
WATCH_MULTIPLIER = 0.95
BLOCK_MULTIPLIER = 0.90


@dataclass
class SeriesSummary:
    series_id: str
    latest_value: float | None
    latest_date: str | None
    ma_20: float | None
    ma_50: float | None
    pct_change_5d: float | None
    pct_change_20d: float | None
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
        # Support both 'DATE' and 'observation_date' (FRED recently changed their format)
        raw_date = str(row.get("DATE") or row.get("observation_date") or "").strip()
        if not raw_date:
            continue
        try:
            dt = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue

        value: float | None = None
        for key, raw_value in row.items():
            if key in ("DATE", "observation_date"):
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


def _moving_average(values: list[float], window: int) -> float | None:
    if not values:
        return None
    if len(values) < window:
        return round(sum(values) / len(values), 6)
    segment = values[-window:]
    return round(sum(segment) / window, 6)


def _percent_change(values: list[float], lookback: int) -> float | None:
    if not values or len(values) <= lookback:
        return None
    latest = values[-1]
    baseline = values[-1 - lookback]
    if baseline == 0:
        return None
    return round((latest - baseline) / baseline, 6)


def summarize_series(series_id: str, points: list[tuple[date, float]]) -> SeriesSummary:
    if not points:
        return SeriesSummary(
            series_id=series_id,
            latest_value=None,
            latest_date=None,
            ma_20=None,
            ma_50=None,
            pct_change_5d=None,
            pct_change_20d=None,
            point_count=0,
        )

    latest_date, latest_value = points[-1]
    values = [value for _, value in points]
    return SeriesSummary(
        series_id=series_id,
        latest_value=round(latest_value, 6),
        latest_date=latest_date.isoformat(),
        ma_20=_moving_average(values, 20),
        ma_50=_moving_average(values, 50),
        pct_change_5d=_percent_change(values, 5),
        pct_change_20d=_percent_change(values, 20),
        point_count=len(points),
    )


def _multiplier_for_status(status: str) -> float:
    if status == "blocked":
        return BLOCK_MULTIPLIER
    if status == "watch":
        return WATCH_MULTIPLIER
    return 1.0


def evaluate_usd_macro_sentiment_signal(
    metrics: dict[str, SeriesSummary],
) -> tuple[str, float, float, list[str]]:
    """Return (status, bearish_score, position_size_multiplier, reasons)."""
    score = 0.0
    reasons: list[str] = []

    broad = metrics.get("broad_usd_index")
    eur = metrics.get("usd_per_euro")
    has_data = any(
        summary.latest_value is not None
        for summary in metrics.values()
        if isinstance(summary, SeriesSummary)
    )
    if not has_data:
        return "unknown", 0.0, 1.0, ["No USD macro data available."]

    if broad and broad.latest_value is not None:
        if broad.ma_50 is not None and broad.ma_50 > 0:
            ratio = broad.latest_value / broad.ma_50
            if ratio <= 0.985:
                score += 25
                reasons.append(f"Broad USD index below 50D MA by {((1.0 - ratio) * 100):.2f}%")
            elif ratio <= 0.995:
                score += 12
                reasons.append(
                    f"Broad USD index slightly below 50D MA by {((1.0 - ratio) * 100):.2f}%"
                )

        if broad.pct_change_20d is not None:
            if broad.pct_change_20d <= -0.02:
                score += 30
                reasons.append(f"Broad USD 20D drawdown {broad.pct_change_20d * 100:.2f}%")
            elif broad.pct_change_20d <= -0.01:
                score += 16
                reasons.append(f"Broad USD 20D decline {broad.pct_change_20d * 100:.2f}%")

        if broad.pct_change_5d is not None:
            if broad.pct_change_5d <= -0.008:
                score += 10
                reasons.append(f"Broad USD 5D momentum weak {broad.pct_change_5d * 100:.2f}%")
            elif broad.pct_change_5d <= -0.004:
                score += 5
                reasons.append(
                    f"Broad USD 5D momentum mildly weak {broad.pct_change_5d * 100:.2f}%"
                )

    if eur and eur.latest_value is not None:
        if eur.ma_50 is not None and eur.ma_50 > 0:
            ratio = eur.latest_value / eur.ma_50
            if ratio >= 1.008:
                score += 15
                reasons.append(
                    f"USD per EUR above 50D MA by {((ratio - 1.0) * 100):.2f}% (USD softer)"
                )
            elif ratio >= 1.003:
                score += 8
                reasons.append(f"USD per EUR modestly above 50D MA by {((ratio - 1.0) * 100):.2f}%")

        if eur.pct_change_20d is not None:
            if eur.pct_change_20d >= 0.015:
                score += 20
                reasons.append(f"USD per EUR 20D rise {eur.pct_change_20d * 100:.2f}%")
            elif eur.pct_change_20d >= 0.008:
                score += 10
                reasons.append(f"USD per EUR 20D uptick {eur.pct_change_20d * 100:.2f}%")

    score = round(min(100.0, score), 2)
    if score >= BLOCK_SCORE:
        status = "blocked"
    elif score >= WATCH_SCORE:
        status = "watch"
    else:
        status = "pass"
    multiplier = _multiplier_for_status(status)
    return status, score, multiplier, reasons


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
    bearish_score: float,
    position_size_multiplier: float,
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
    effective_multiplier = position_size_multiplier
    effective_reasons = list(reasons)
    if stale:
        effective_status = "unknown"
        effective_multiplier = 1.0
        effective_reasons.append(
            f"USD macro data stale: {stale_days} days old (max {max_stale_days})"
        )

    return {
        "signal": "usd_macro_sentiment",
        "status": effective_status,
        "bearish_score": bearish_score,
        "position_size_multiplier": round(min(1.0, max(0.1, effective_multiplier)), 4),
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
                "ma_20": summary.ma_20,
                "ma_50": summary.ma_50,
                "pct_change_5d": summary.pct_change_5d,
                "pct_change_20d": summary.pct_change_20d,
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
    payload["position_size_multiplier"] = _multiplier_for_status(status)
    if status == "unknown":
        payload["position_size_multiplier"] = 1.0
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
    market_signals["usd_macro_sentiment"] = payload
    state["market_signals"] = market_signals
    _safe_write_json(state_path, state)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update USD macro sentiment signal from FRED.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_PATH), help="Signal output JSON path.")
    parser.add_argument(
        "--state",
        default=str(DEFAULT_STATE_PATH),
        help="system_state.json path for --sync-state updates.",
    )
    parser.add_argument(
        "--sync-state",
        action="store_true",
        help="Write signal payload into system_state.market_signals.usd_macro_sentiment.",
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
        "--max-stale-days",
        type=int,
        default=14,
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
                "signal": "usd_macro_sentiment",
                "status": "unknown",
                "bearish_score": 0.0,
                "position_size_multiplier": 1.0,
                "blocked": False,
                "watch": False,
                "reasons": ["Offline mode with no prior USD macro signal available."],
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
                summaries[name] = summarize_series(series_id=series_id, points=points)
            except Exception as exc:  # noqa: BLE001 - network failures handled with fallback
                fetch_errors.append(f"{series_id}: {exc}")
                summaries[name] = SeriesSummary(
                    series_id=series_id,
                    latest_value=None,
                    latest_date=None,
                    ma_20=None,
                    ma_50=None,
                    pct_change_5d=None,
                    pct_change_20d=None,
                    point_count=0,
                )

        status, score, multiplier, reasons = evaluate_usd_macro_sentiment_signal(summaries)
        payload = _build_payload(
            metrics=summaries,
            status=status,
            bearish_score=score,
            position_size_multiplier=multiplier,
            reasons=reasons,
            source="fred_public",
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
        "ok: usd macro sentiment signal updated",
        f"status={payload.get('status')}",
        f"score={payload.get('bearish_score')}",
        f"size_multiplier={payload.get('position_size_multiplier')}",
        f"out={out_path}",
    )
    if args.print_json:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
