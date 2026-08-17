"""Tests for put-credit research protocol (handbook high-ROI layer)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research.put_credit_research_protocol import (
    ProtocolVariant,
    ExperimentRegistry,
    compare_challenger,
    freeze_champion,
    metrics_from_pnls,
    run_baseline_snapshot,
    select_champion,
    split_dev_val_holdout,
    unlock_holdout_once,
    SliceMetrics,
)


def test_metrics_from_pnls_basic():
    m = metrics_from_pnls([10.0, -5.0, 0.0, 20.0])
    assert m.n == 4
    assert m.wins == 2
    assert m.losses == 1
    assert m.expectancy == pytest.approx(6.25)
    assert m.total_realized_pnl == pytest.approx(25.0)
    assert m.profit_factor == pytest.approx(6.0)


def test_split_holdout_locked_sizes():
    timed = [(f"t{i}", float(i)) for i in range(15)]
    splits = split_dev_val_holdout(timed)
    assert sum(len(v) for v in splits.values()) == 15
    assert len(splits["holdout"]) >= 3
    assert len(splits["development"]) >= 1
    assert len(splits["validation"]) >= 1


def test_select_champion_fixed_gates():
    inc = SliceMetrics(5, 3, 2, 1.0, 1.2, 5.0, 60.0)
    better = SliceMetrics(5, 4, 1, 2.0, 1.5, 10.0, 80.0)
    worse = SliceMetrics(5, 2, 3, 0.5, 0.8, 1.0, 40.0)
    name, rationale, failed = select_champion(
        better, inc, challenger_name="v2", incumbent_name="v1"
    )
    assert name == "v2"
    assert not failed
    name2, _, failed2 = select_champion(worse, inc, challenger_name="v2", incumbent_name="v1")
    assert name2 == "v1"
    assert failed2


def test_registry_append_only(tmp_path: Path):
    reg = ExperimentRegistry(tmp_path / "registry.jsonl")
    reg.append({"event": "experiment", "version": "v1", "status": "ok"})
    reg.append({"event": "experiment", "version": "v2", "status": "fail"})
    rows = reg.read_all()
    assert len(rows) == 2
    assert rows[0]["version"] == "v1"
    assert rows[1]["status"] == "fail"


def test_baseline_snapshot_records_insufficient_sample(tmp_path: Path):
    out = run_baseline_snapshot({"trades": []}, tmp_path)
    assert out["status"] == "insufficient_sample"
    assert (tmp_path / "SELECTION_RULE.md").is_file()
    assert (tmp_path / "registry.jsonl").is_file()
    assert (tmp_path / "latest_snapshot.json").is_file()


def test_baseline_with_closed_pcs_trades(tmp_path: Path):
    trades = {
        "trades": [
            {
                "strategy": "spy_put_credit",
                "status": "closed",
                "exit_time": f"2026-07-{10+i:02d}T15:00:00+00:00",
                "realized_pnl": 10.0 if i % 2 == 0 else -8.0,
            }
            for i in range(6)
        ]
    }
    out = run_baseline_snapshot(trades, tmp_path)
    assert out["status"] == "ok"
    assert out["evaluation"]["n_closed"] == 6
    assert out["evaluation"]["holdout"]["locked"] is True


def test_freeze_then_holdout_once(tmp_path: Path):
    timed = [(f"2026-07-{i:02d}", 1.0) for i in range(1, 16)]
    val = metrics_from_pnls(split_dev_val_holdout(timed)["validation"])
    freeze_champion(
        tmp_path,
        champion=ProtocolVariant("v1", "baseline", {"family": "spy_put_credit"}),
        validation=val,
        rationale="test freeze",
    )
    report = unlock_holdout_once(tmp_path, timed)
    assert "holdout" in report
    with pytest.raises(RuntimeError, match="already evaluated"):
        unlock_holdout_once(tmp_path, timed)


def test_research_critic_flags_holdout_selection():
    from src.research.put_credit_research_protocol import research_critic_audit

    trades = {"trades": []}
    bad = research_critic_audit(
        trades_payload=trades,
        decision={"event": "decision", "used_holdout_for_selection": True},
    )
    assert bad["pass"] is False
    assert any(f["code"] == "holdout_used_for_selection" for f in bad["findings"])

    good = research_critic_audit(
        trades_payload=trades,
        decision={"event": "decision", "used_holdout_for_selection": False},
    )
    assert good["pass"] is True


def test_scorecard_includes_research_protocol(tmp_path: Path, monkeypatch):
    from scripts import put_credit_cohort_scorecard as sc

    trades_path = tmp_path / "trades.json"
    trades_path.write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "strategy": "spy_put_credit",
                        "status": "closed",
                        "exit_time": "2026-07-10T15:00:00+00:00",
                        "realized_pnl": 17.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    entries_path = tmp_path / "entries.json"
    entries_path.write_text("{}", encoding="utf-8")
    kill_path = tmp_path / "kill.json"
    kill_path.write_text(
        json.dumps({"active_family": "spy_put_credit", "paper_only": True, "live_blocked": True}),
        encoding="utf-8",
    )
    card = sc.build_scorecard(
        trades_path=trades_path, entries_path=entries_path, kill_path=kill_path
    )
    assert card["schema_version"] == "put-credit-cohort-scorecard/2"
    rp = card["research_protocol"]
    assert rp.get("langchain_adopted") is False
    assert "validation" in rp
    assert rp.get("critic", {}).get("pass") is True


def test_compare_preferred_ivr_records_decision(tmp_path: Path):
    trades = {
        "trades": [
            {
                "strategy": "spy_put_credit",
                "status": "closed",
                "exit_time": "2026-07-10T15:00:00+00:00",
                "realized_pnl": 17.0,
                "regime": {"iv_rank_proxy": 40.0},
            },
            {
                "strategy": "spy_put_credit",
                "status": "closed",
                "exit_time": "2026-07-20T15:00:00+00:00",
                "realized_pnl": -10.0,
                "regime": {"iv_rank_proxy": 8.0},
            },
        ]
    }
    decision = compare_challenger(
        trades,
        challenger=ProtocolVariant(
            "v2",
            "preferred",
            {"min_ivr_for_edge_claim": 30.0},
        ),
        incumbent=ProtocolVariant("v1", "baseline", {}),
        research_dir=tmp_path,
    )
    assert decision["event"] == "decision"
    assert "champion" in decision
    rows = ExperimentRegistry(tmp_path / "registry.jsonl").read_all()
    assert any(r.get("event") == "decision" for r in rows)
