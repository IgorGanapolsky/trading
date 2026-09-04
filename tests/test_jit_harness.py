"""Tests for deterministic JIT task→harness selection."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from src.ops.jit_harness import (
    TaskClass,
    classify_task,
    estimate_savings_vs_full_context,
    list_task_classes,
    select_harness,
)


def test_classify_status():
    assert classify_task("what is account status?") == TaskClass.STATUS
    assert classify_task("show kill switch health") == TaskClass.STATUS


def test_classify_dry_run():
    assert classify_task("run put credit dry-run") == TaskClass.DRY_RUN
    assert classify_task("make dry-run for today") == TaskClass.DRY_RUN


def test_classify_inventory_before_generic_search():
    assert classify_task("audit open inventory unclean") == TaskClass.INVENTORY


def test_classify_pr_hygiene():
    assert classify_task("merge ready PRs and fix CI") == TaskClass.PR_HYGIENE


def test_classify_rag_search():
    assert classify_task("zg_search put credit stop lessons") == TaskClass.RAG_SEARCH


def test_classify_residual_ic():
    assert classify_task("residual IC exit plan") == TaskClass.RESIDUAL_IC


def test_unknown_fail_closed():
    pack = select_harness("teleport the moon")
    assert pack.task_class == TaskClass.UNKNOWN
    assert pack.paper_only is True
    assert any("live" in f.lower() or "submit" in f.lower() for f in pack.forbid)


def test_four_modules_present():
    pack = select_harness("spy put credit dry-run plan")
    assert pack.task_class == TaskClass.DRY_RUN
    assert pack.memory and pack.plan and pack.actions and pack.skills
    assert "--dry-run" in " ".join(pack.actions)
    assert any("live" in f.lower() for f in pack.forbid)


def test_dry_run_forbids_claiming_fill():
    pack = select_harness("plan trade with spy_put_credit")
    assert any("filled" in f or "executed" in f or "claim" in f for f in pack.forbid)


def test_savings_hint_positive():
    pack = select_harness("status")
    hint = estimate_savings_vs_full_context(pack, full_budget=12000)
    assert hint["pack_budget"] < hint["full_budget"]
    assert hint["saved_pct_hint"] > 0


def test_list_task_classes_includes_unknown():
    rows = list_task_classes()
    ids = {r["task_class"] for r in rows}
    assert TaskClass.STATUS.value in ids
    assert TaskClass.UNKNOWN.value in ids


def test_cli_json_and_ready():
    path = Path(__file__).resolve().parents[1] / "scripts" / "jit_harness.py"
    spec = importlib.util.spec_from_file_location("jit_harness_cli", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.main(["--check-ready"]) == 0
    assert mod.main(["--json", "account status"]) == 0
