"""Tests for DoorDash-Flux FORMAT operator graphs."""

from __future__ import annotations

from pathlib import Path

from src.ops.flux_task_graph import list_graphs, plan_graph, write_receipt


def test_list_graphs():
    names = list_graphs()
    assert "dry_run_readiness" in names
    assert "pr_hygiene" in names


def test_dry_run_graph_order_and_packs():
    plan = plan_graph("dry_run_readiness")
    assert plan.ok is True
    assert plan.order == ("status", "inventory", "dry_run")
    assert plan.packs["dry_run"]["task_class"] == "dry_run"
    assert plan.packs["dry_run"]["paper_only"] is True


def test_unknown_graph_fail_closed():
    plan = plan_graph("not_a_real_graph")
    assert plan.ok is False
    assert "unknown_graph" in plan.failing


def test_receipt_appends(tmp_path: Path):
    plan = plan_graph("pr_hygiene")
    path = tmp_path / "receipts.jsonl"
    payload = write_receipt(plan, path)
    assert payload["receipt_hash"]
    assert path.is_file()
    assert path.read_text(encoding="utf-8").count("\n") == 1
