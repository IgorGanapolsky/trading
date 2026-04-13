from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from src.orchestration.daggr_workflow import (
    create_trading_workflow,
    load_latest_perplexity_trading_intel,
)


def test_load_latest_perplexity_trading_intel_requires_fresh_artifact(tmp_path: Path) -> None:
    path = tmp_path / "trading_intel_latest.json"
    path.write_text(
        json.dumps(
            {
                "generated_at_utc": datetime(2026, 4, 13, 14, 0, tzinfo=timezone.utc).isoformat(),
                "recommendation": "BLOCK_NEW_IC",
                "risk_score": 0.8,
            }
        ),
        encoding="utf-8",
    )

    fresh = load_latest_perplexity_trading_intel(
        path,
        now=datetime(2026, 4, 13, 15, 0, tzinfo=timezone.utc),
    )
    stale = load_latest_perplexity_trading_intel(
        path,
        max_age_minutes=30,
        now=datetime(2026, 4, 13, 15, 0, tzinfo=timezone.utc),
    )

    assert fresh is not None
    assert stale is None


def test_trade_decision_holds_when_perplexity_blocks_new_ic() -> None:
    workflow = create_trading_workflow()
    node = workflow.nodes["trade_decision"]

    result = asyncio.run(
        node.execute(
            {
                "options_chain": {
                    "signal": 0.8,
                    "confidence": 0.9,
                    "data": {"ticker": "SPY"},
                },
                "perplexity_intel": {
                    "confidence": 0.9,
                    "data": {
                        "recommendation": "BLOCK_NEW_IC",
                        "gate_contract": {
                            "blocks_new_iron_condors": True,
                            "reason": "FOMC risk",
                        },
                    },
                },
            },
            {},
        )
    )

    assert result.success is True
    assert result.output["decision"] == "HOLD"
    assert result.output["trade_params"] is None
    assert result.output["reason"] == "FOMC risk"
