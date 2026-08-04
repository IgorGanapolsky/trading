"""Tests for the temporal trade knowledge graph."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from src.rag.graph.build import _parse_constants, extract_policy_history
from src.rag.graph.queries import (
    MIN_COHORT_FOR_RATIOS,
    Cohort,
    graph_context,
    loss_attribution,
    policy_cohorts,
)
from src.rag.graph.temporal_graph import Edge, Node, TemporalGraph

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def graph(tmp_path: Path) -> TemporalGraph:
    g = TemporalGraph(tmp_path / "graph.sqlite")
    yield g
    g.close()


# ------------------------------------------------------------------ temporality


def test_edge_invisible_outside_validity_window(graph: TemporalGraph) -> None:
    """A fact must not be visible before it was true or after it stopped being true."""
    graph.add_many(
        nodes=[Node("a", "trade", "A"), Node("b", "policy", "B")],
        edges=[Edge("a", "GOVERNED_BY", "b", valid_from="2026-03-01", valid_to="2026-04-01")],
    )

    assert list(graph.neighbors("a", as_of="2026-03-15")), "edge should be live mid-window"
    assert not list(graph.neighbors("a", as_of="2026-02-01")), "edge must not exist before"
    assert not list(graph.neighbors("a", as_of="2026-05-01")), "edge must not exist after"
    assert list(graph.neighbors("a", as_of=None)), "as_of=None ignores time"


def test_open_ended_edge_is_live_after_start(graph: TemporalGraph) -> None:
    graph.add_many(
        nodes=[Node("a", "trade", "A"), Node("b", "policy", "B")],
        edges=[Edge("a", "GOVERNED_BY", "b", valid_from="2026-03-01", valid_to=None)],
    )
    assert list(graph.neighbors("a", as_of="2030-01-01"))
    assert not list(graph.neighbors("a", as_of="2026-01-01"))


# --------------------------------------------------------------------- budgets


def test_expansion_respects_node_budget(graph: TemporalGraph) -> None:
    """Dense hubs must not blow the context budget; truncation must be reported."""
    nodes = [Node("hub", "outcome", "loss")]
    edges = []
    for i in range(100):
        nodes.append(Node(f"t{i}", "trade", f"trade {i}"))
        edges.append(Edge(f"t{i}", "RESULTED_IN", "hub"))
    graph.add_many(nodes=nodes, edges=edges)

    sub = graph.expand(["hub"], hops=2, node_budget=10)
    assert len(sub.nodes) <= 10
    assert sub.truncated is True, "a budget-capped subgraph must announce it is partial"

    full = graph.expand(["hub"], hops=2, node_budget=500)
    assert full.truncated is False
    assert len(full.nodes) == 101


def test_graph_context_states_truncation(graph: TemporalGraph) -> None:
    nodes = [Node("hub", "outcome", "loss")]
    edges = []
    for i in range(50):
        nodes.append(Node(f"t{i}", "trade", f"trade {i}"))
        edges.append(Edge(f"t{i}", "RESULTED_IN", "hub"))
    graph.add_many(nodes=nodes, edges=edges)

    text = graph_context(graph, ["hub"], hops=2, node_budget=5)
    assert "TRUNCATED" in text, "partial context must never read as complete"


# ------------------------------------------------------------------- multi-hop


def test_paths_finds_policy_to_outcome_chain(graph: TemporalGraph) -> None:
    """The join vector search cannot make: policy -> trade -> outcome."""
    graph.add_many(
        nodes=[
            Node("policy:SL@2026-03-01", "policy", "SL=1.0"),
            Node("trade:X", "trade", "X"),
            Node("outcome:loss", "outcome", "loss"),
        ],
        edges=[
            Edge("trade:X", "GOVERNED_BY", "policy:SL@2026-03-01"),
            Edge("trade:X", "RESULTED_IN", "outcome:loss"),
        ],
    )
    found = graph.paths("policy:SL@2026-03-01", "outcome:loss", max_hops=3)
    assert found, "expected a policy->trade->outcome path"
    assert len(found[0]) == 2


# --------------------------------------------------------------- sample honesty


def test_ratios_withheld_below_minimum_sample() -> None:
    """Small-sample win rate / profit factor must be withheld, not rounded into truth."""
    cohort = Cohort(key="k", label="k", valid_from=None, valid_to=None)
    for i in range(5):
        cohort.trade_ids.append(f"t{i}")
        cohort.wins += 1
        cohort.gross_profit += 10.0

    metrics = cohort.metrics()
    assert metrics["n"] == 5
    assert metrics["win_rate"] is None
    assert metrics["profit_factor"] is None
    assert metrics["sufficient_sample"] is False
    assert metrics["expectancy"] == 10.0, "expectancy is a mean and is always reportable"


def test_ratios_reported_at_sufficient_sample() -> None:
    cohort = Cohort(key="k", label="k", valid_from=None, valid_to=None)
    for i in range(MIN_COHORT_FOR_RATIOS):
        cohort.trade_ids.append(f"t{i}")
        if i % 2 == 0:
            cohort.wins += 1
            cohort.gross_profit += 10.0
        else:
            cohort.losses += 1
            cohort.gross_loss += 5.0

    metrics = cohort.metrics()
    assert metrics["sufficient_sample"] is True
    assert metrics["win_rate"] == pytest.approx(0.5, abs=0.02)
    assert metrics["profit_factor"] == pytest.approx(2.0, abs=0.01)


def test_exit_reason_is_never_inferred(graph: TemporalGraph) -> None:
    """A missing exit reason stays `unrecorded` -- it is not guessed from the P/L sign."""
    graph.add_many(
        nodes=[
            Node(
                "trade:A",
                "trade",
                "A",
                attrs={"realized_pnl": -300.0, "outcome": "loss", "exit_reason": None},
            ),
            Node(
                "trade:B",
                "trade",
                "B",
                attrs={"realized_pnl": 50.0, "outcome": "win", "exit_reason": "profit_target"},
            ),
        ]
    )
    report = loss_attribution(graph)
    reasons = {row["exit_reason"]: row for row in report["by_exit_reason"]}

    assert "unrecorded" in reasons
    assert reasons["unrecorded"]["n"] == 1
    assert "stop_loss" not in reasons, "a loss must not be relabelled as a stop-loss exit"
    assert report["exit_reason_coverage"] == pytest.approx(0.5)


# ------------------------------------------------- policy history (regression)


def _init_repo(root: Path, revisions: list[str]) -> None:
    """Create a throwaway git repo whose constants file changes across commits."""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    target = root / "src" / "core" / "trading_constants.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    for i, body in enumerate(revisions):
        target.write_text(body)
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", f"rev{i}", f"--date=2026-0{i + 1}-01T12:00:00"],
            cwd=root,
            check=True,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                "GIT_COMMITTER_DATE": f"2026-0{i + 1}-01T12:00:00",
                "HOME": str(root),
            },
        )


def test_policy_window_closes_when_value_stops_being_a_literal(tmp_path: Path) -> None:
    """Regression: a constant that starts delegating must END its window, not coast.

    Before this was fixed, the refactor that replaced a literal with a profile lookup
    left the last-known literal open forever, silently attributing every later trade to
    a value that was no longer in force.
    """
    _init_repo(
        tmp_path,
        [
            "IRON_CONDOR_STOP_LOSS_MULTIPLIER: float = 1.0\n",
            "IRON_CONDOR_STOP_LOSS_MULTIPLIER: float = 2.0\n",
            "IRON_CONDOR_STOP_LOSS_MULTIPLIER: float = PROFILE.stop_loss_pct\n",
        ],
    )

    history = extract_policy_history(tmp_path)
    windows = [w for w in history.windows if w.name == "IRON_CONDOR_STOP_LOSS_MULTIPLIER"]

    assert [w.value for w in windows] == [1.0, 2.0]
    assert all(w.valid_to is not None for w in windows), (
        "no window may stay open once the value stops being resolvable"
    )
    assert [s.name for s in history.indeterminate] == ["IRON_CONDOR_STOP_LOSS_MULTIPLIER"]


def test_parse_constants_separates_literals_from_delegations() -> None:
    resolved, unresolved = _parse_constants(
        "MAX_POSITIONS: int = 8\n"
        "MAX_DAILY_STRUCTURES: int = PROFILE.max_daily_structures\n"
        "UNRELATED_NAME: int = 3\n"
    )
    assert resolved == {"MAX_POSITIONS": 8}
    assert unresolved == {"MAX_DAILY_STRUCTURES"}


def test_journal_rows_never_enter_metrics(graph: TemporalGraph) -> None:
    """Regression: entry-journal rows were counted as closed trades.

    They can still be open, they carry no `realized_pnl`, and data-integrity.md is
    explicit that unmatched orders are never trades. Counting them inflated
    `spy_put_credit` to n=3 when the paired ledger held n=1 -- overstating progress
    toward the n>=30 live-capital gate, the one direction this must never fail.
    """
    graph.add_many(
        nodes=[
            Node(
                "trade:LEDGER",
                "trade",
                "paired close",
                attrs={
                    "realized_pnl": 17.0,
                    "outcome": "win",
                    "strategy": "spy_put_credit",
                    "evidence_tier": "paired_ledger",
                },
            ),
            Node(
                "trade:JOURNAL_OPEN",
                "trade",
                "still open",
                attrs={
                    "realized_pnl": 0.0,
                    "outcome": "unknown",
                    "strategy": "spy_put_credit",
                    "evidence_tier": "journal",
                    "status": "exit_pending",
                },
            ),
        ]
    )
    report = loss_attribution(graph)

    assert report["total_trades"] == 1, "journal row must not be counted as a trade"
    assert report["excluded_non_scorable"] == {"journal": 1}, "exclusions must be reported"
    by_strategy = {r["strategy"]: r for r in report["by_strategy"]}
    assert by_strategy["spy_put_credit"]["n"] == 1
    assert by_strategy["spy_put_credit"]["expectancy"] == 17.0


def test_policy_cohorts_exclude_journal_rows(graph: TemporalGraph) -> None:
    graph.add_many(
        nodes=[
            Node(
                "policy:P@2026-03-01",
                "policy",
                "P=1.0",
                attrs={"name": "P", "value": 1.0},
            ),
            Node(
                "trade:J",
                "trade",
                "journal",
                attrs={
                    "realized_pnl": 0.0,
                    "outcome": "unknown",
                    "strategy": "spy_put_credit",
                    "evidence_tier": "journal",
                },
            ),
        ],
        edges=[Edge("trade:J", "GOVERNED_BY", "policy:P@2026-03-01")],
    )
    assert policy_cohorts(graph, "P") == [], "a journal row cannot form a cohort"


def test_stale_sources_detects_newer_ledger(tmp_path: Path) -> None:
    """A graph older than its source ledger must be reported, never answered silently."""
    import importlib.util

    script = PROJECT_ROOT / "scripts" / "trade_graph.py"
    spec = importlib.util.spec_from_file_location("trade_graph_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    db = tmp_path / "graph.sqlite"
    db.write_text("")
    ledger = tmp_path / "trades.json"
    ledger.write_text("{}")

    # Ledger written after the graph -> stale.
    os.utime(db, (1_700_000_000, 1_700_000_000))
    os.utime(ledger, (1_700_000_500, 1_700_000_500))
    assert module.stale_sources(db, [ledger]) == [str(ledger)]

    # Graph rebuilt after the ledger -> fresh.
    os.utime(db, (1_700_001_000, 1_700_001_000))
    assert module.stale_sources(db, [ledger]) == []

    # A source that does not exist cannot make the graph stale.
    assert module.stale_sources(db, [tmp_path / "absent.json"]) == []


def test_policy_cohorts_excludes_indeterminate_period(graph: TemporalGraph) -> None:
    """Trades with no GOVERNED_BY edge must not land in any cohort."""
    graph.add_many(
        nodes=[
            Node(
                "policy:SL@2026-03-01",
                "policy",
                "SL=1.0",
                attrs={"name": "SL", "value": 1.0},
                valid_from="2026-03-01",
                valid_to="2026-04-08",
            ),
            Node(
                "trade:attributed",
                "trade",
                "in window",
                attrs={"realized_pnl": -100.0, "outcome": "loss", "strategy": "iron_condor"},
            ),
            Node(
                "trade:orphan",
                "trade",
                "after refactor",
                attrs={"realized_pnl": -999.0, "outcome": "loss", "strategy": "iron_condor"},
            ),
        ],
        edges=[Edge("trade:attributed", "GOVERNED_BY", "policy:SL@2026-03-01")],
    )

    cohorts = policy_cohorts(graph, "SL")
    assert len(cohorts) == 1
    assert cohorts[0]["n"] == 1
    assert cohorts[0]["realized_pnl"] == -100.0, "unattributable trade must be excluded"
