"""Unit tests for Dagster-Style Software-Defined Assets (SDA) & Asset Checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from src.ops.dagster_asset_engine import (
    AssetCheck,
    AssetCheckResult,
    AssetGraph,
    AssetKey,
    AssetMaterializationEngine,
    CheckSeverity,
    SoftwareDefinedAsset,
    diagnose_dagster_engine,
    get_default_trading_asset_graph,
)

REPO = Path(__file__).resolve().parents[1]


def test_asset_key_parsing_and_equality():
    k1 = AssetKey("market", "regime")
    k2 = AssetKey.parse("market/regime")
    k3 = AssetKey.parse("market.regime")
    assert k1 == k2 == k3
    assert k1.to_string() == "market/regime"
    assert str(k1) == "market/regime"
    assert repr(k1) == "AssetKey('market/regime')"


def test_asset_graph_topological_sort():
    a1 = SoftwareDefinedAsset(
        key=AssetKey("raw", "prices"),
        deps=(),
        compute_fn=lambda inputs: ({"SPY": 596.0}, {"rows": 1}),
    )
    a2 = SoftwareDefinedAsset(
        key=AssetKey("derived", "moving_avg"),
        deps=(AssetKey("raw", "prices"),),
        compute_fn=lambda inputs: ({"SPY_200": 540.0}, {"window": 200}),
    )
    a3 = SoftwareDefinedAsset(
        key=AssetKey("signals", "trend"),
        deps=(AssetKey("derived", "moving_avg"),),
        compute_fn=lambda inputs: ({"bullish": True}, {}),
    )

    graph = AssetGraph([a3, a1, a2])
    order = graph.get_topological_order()
    assert order == [
        AssetKey("raw", "prices"),
        AssetKey("derived", "moving_avg"),
        AssetKey("signals", "trend"),
    ]


def test_asset_graph_missing_dependency_fails():
    a1 = SoftwareDefinedAsset(
        key=AssetKey("derived", "signal"),
        deps=(AssetKey("missing", "upstream"),),
        compute_fn=lambda inputs: ({}, {}),
    )
    with pytest.raises(ValueError, match="depends on missing upstream"):
        AssetGraph([a1])


def test_asset_graph_cycle_detection_fails():
    a1 = SoftwareDefinedAsset(
        key=AssetKey("loop", "a"),
        deps=(AssetKey("loop", "b"),),
        compute_fn=lambda inputs: ({}, {}),
    )
    a2 = SoftwareDefinedAsset(
        key=AssetKey("loop", "b"),
        deps=(AssetKey("loop", "a"),),
        compute_fn=lambda inputs: ({}, {}),
    )
    graph = AssetGraph.__new__(AssetGraph)
    graph.assets = {a1.key: a1, a2.key: a2}
    with pytest.raises(ValueError, match="Cycle detected"):
        graph.get_topological_order()


def test_materialization_engine_success_run():
    a1 = SoftwareDefinedAsset(
        key=AssetKey("a"),
        deps=(),
        compute_fn=lambda inputs: (10, {"count": 10}),
        checks=(
            AssetCheck(
                name="check_positive",
                description="Must be positive",
                check_fn=lambda val, up: AssetCheckResult(
                    check_name="check_positive", passed=val > 0
                ),
                blocking=True,
            ),
        ),
    )
    a2 = SoftwareDefinedAsset(
        key=AssetKey("b"),
        deps=(AssetKey("a"),),
        compute_fn=lambda inputs: (inputs[AssetKey("a")] * 2, {"doubled": True}),
    )
    graph = AssetGraph([a1, a2])
    engine = AssetMaterializationEngine(graph)
    results = engine.materialize()

    assert results["a"].success is True
    assert len(results["a"].check_results) == 1
    assert results["a"].check_results[0]["passed"] is True
    assert results["b"].success is True
    assert engine.asset_values[AssetKey("b")] == 20


def test_blocking_check_diode_stops_downstream():
    # When an upstream check fails, downstream assets must be blocked fail-closed
    downstream_executed = False

    def downstream_compute(inputs: dict) -> tuple[Any, dict]:
        nonlocal downstream_executed
        downstream_executed = True
        return 42, {}

    a_bad = SoftwareDefinedAsset(
        key=AssetKey("bad_upstream"),
        deps=(),
        compute_fn=lambda inputs: (-5, {}),
        checks=(
            AssetCheck(
                name="check_must_be_positive",
                description="Value must be > 0",
                check_fn=lambda val, up: AssetCheckResult(
                    check_name="check_must_be_positive",
                    passed=val > 0,
                    severity=CheckSeverity.ERROR,
                    description="Negative value encountered",
                ),
                blocking=True,
            ),
        ),
    )
    a_downstream = SoftwareDefinedAsset(
        key=AssetKey("safe_downstream"),
        deps=(AssetKey("bad_upstream"),),
        compute_fn=downstream_compute,
    )

    graph = AssetGraph([a_bad, a_downstream])
    engine = AssetMaterializationEngine(graph)
    results = engine.materialize()

    assert results["bad_upstream"].success is False
    assert results["bad_upstream"].blocked_by == "check_must_be_positive"
    # Downstream was blocked fail-closed without executing its compute_fn
    assert results["safe_downstream"].success is False
    assert results["safe_downstream"].blocked_by == "bad_upstream"
    assert downstream_executed is False


def test_non_blocking_check_warns_without_halting():
    a_warn = SoftwareDefinedAsset(
        key=AssetKey("warn_upstream"),
        deps=(),
        compute_fn=lambda inputs: (100, {}),
        checks=(
            AssetCheck(
                name="check_high_threshold",
                description="Warn if value is high",
                check_fn=lambda val, up: AssetCheckResult(
                    check_name="check_high_threshold",
                    passed=False,
                    severity=CheckSeverity.WARN,
                    description="Value is high",
                ),
                blocking=False,
            ),
        ),
    )
    a_downstream = SoftwareDefinedAsset(
        key=AssetKey("downstream"),
        deps=(AssetKey("warn_upstream"),),
        compute_fn=lambda inputs: (inputs[AssetKey("warn_upstream")] + 1, {}),
    )
    graph = AssetGraph([a_warn, a_downstream])
    engine = AssetMaterializationEngine(graph)
    results = engine.materialize()

    assert results["warn_upstream"].success is True
    assert results["warn_upstream"].check_results[0]["passed"] is False
    assert results["downstream"].success is True
    assert engine.asset_values[AssetKey("downstream")] == 101


def test_default_trading_asset_graph():
    graph = get_default_trading_asset_graph()
    assert len(graph.assets) == 4
    engine = AssetMaterializationEngine(graph)

    # Materialize target single asset (will pull its upstream lineage)
    results = engine.materialize([AssetKey("options", "put_credit_candidates")])
    assert "market/regime" in results
    assert "inventory/open_positions" in results
    assert "options/put_credit_candidates" in results
    assert all(r.success for r in results.values())


def test_diagnose_dagster_engine_green():
    report = diagnose_dagster_engine(REPO)
    assert report.ok is True
    assert report.score == report.max_score == 4
    assert len(report.failing) == 0
    assert report.checks["agents_directive"] is True
    assert report.checks["asset_graph_lineage"] is True
    assert report.checks["asset_materialization_and_checks"] is True
    assert report.checks["blocking_check_diode"] is True


def test_cli_script_execution(capsys):
    import importlib.util

    cli_path = REPO / "scripts" / "dagster_asset_engine.py"
    spec = importlib.util.spec_from_file_location("dagster_asset_engine", cli_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Doctor
    rc = mod.main(["--doctor", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["score"] == 4

    # List assets
    rc = mod.main(["--list-assets", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "market/regime" in out
    assert "options/put_credit_candidates" in out

    # Materialize all
    rc = mod.main(["--materialize-all", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 4
    assert all(m["success"] for m in out.values())
