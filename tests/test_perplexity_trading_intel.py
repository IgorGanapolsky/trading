from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from src.analytics.perplexity_trading_intel import (
    PRE_MARKET_QUERIES,
    PerplexityTradingIntelRunner,
    QuerySpec,
    recommendation_for,
    score_text,
)


def test_score_text_blocks_high_impact_event_language() -> None:
    spec = QuerySpec(
        key="test",
        prompt="test",
        recency="day",
        risk_terms=("fomc", "avoid"),
    )

    score = score_text(
        "FOMC and Powell create a volatility spike. Avoid new iron condors today.",
        spec,
    )

    assert score >= 0.70
    assert recommendation_for(score, "ok") == "BLOCK_NEW_IC"


def test_score_text_keeps_calm_language_clear() -> None:
    score = score_text("No major scheduled catalysts. Calm and stable range-bound session.")

    assert score == 0.0
    assert recommendation_for(score, "ok") == "CLEAR"


def test_pre_market_bundle_has_multiple_independent_queries() -> None:
    keys = {query.key for query in PRE_MARKET_QUERIES}

    assert {"macro_calendar", "volatility_regime", "index_event_risk"}.issubset(keys)


def test_dry_run_writes_json_rag_and_ml_artifacts(tmp_path: Path) -> None:
    (tmp_path / "docs" / "data").mkdir(parents=True)
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "docs" / "data" / "public_status.json").write_text(
        json.dumps(
            {
                "paper": {"equity": 93728.02, "total_pnl_today": -97.08, "positions_count": 4},
                "ledger": {"closed_trades_total": 67, "win_rate_pct": 23.88},
                "gate": {"mode": "validation_reset", "scale_allowed": False},
            }
        ),
        encoding="utf-8",
    )

    runner = PerplexityTradingIntelRunner(
        tmp_path,
        dry_run=True,
        now=datetime(2026, 4, 13, 13, 30, tzinfo=timezone.utc),
    )
    payload = asyncio.run(runner.run("pre_market"))
    duplicate_payload = asyncio.run(runner.run("pre_market"))

    latest = tmp_path / "data" / "analysis" / "perplexity" / "pre_market_latest.json"
    trading_latest = tmp_path / "data" / "analysis" / "perplexity" / "trading_intel_latest.json"
    legacy = tmp_path / "data" / "analysis" / "pre_market_2026-04-13.json"
    rag = tmp_path / "rag_knowledge" / "lessons_learned" / "ll_perplexity_pre_market_2026-04-13.md"
    ml = tmp_path / "data" / "feedback" / "perplexity_intel_events.jsonl"

    assert payload["api_status"] == "dry_run"
    assert duplicate_payload["api_status"] == "dry_run"  # nosec B101
    assert latest.exists()
    assert trading_latest.exists()
    assert legacy.exists()
    assert rag.exists()
    assert ml.exists()

    saved = json.loads(latest.read_text(encoding="utf-8"))
    assert saved["trading_context"]["equity"] == 93728.02
    assert saved["gate_contract"]["source"] == "perplexity_trading_intel"

    ml_events = [json.loads(line) for line in ml.read_text(encoding="utf-8").splitlines()]
    assert len(ml_events) == 1  # nosec B101
    assert ml_events[0]["event_id"].startswith("perplexity_trading_intel:")  # nosec B101
    assert ml_events[0]["source"] == "perplexity_trading_intel"  # nosec B101
    assert ml_events[0]["query_count"] == len(PRE_MARKET_QUERIES)  # nosec B101
    assert ml_events[0]["citation_count"] == 0  # nosec B101
    assert ml_events[0]["fresh_for_minutes"] == 240  # nosec B101
    assert ml_events[0]["gate_reason"] == saved["gate_contract"]["reason"]  # nosec B101
    assert ml_events[0]["trading_context_snapshot"]["equity"] == 93728.02  # nosec B101
