"""Build the temporal trade graph from canonical repo data.

Sources, all already in the repo -- no external feeds, no new infrastructure:

* `data/trades.json`             -> paired closed structures (the outcome ledger)
* `data/put_credit_entries.json` -> active strategy lifecycle journal
* `src/core/trading_constants.py` git history -> policy validity windows
* `rag_knowledge/lessons_learned/` -> lessons, linked to what they warn about

The policy windows are the reason this is a *temporal* graph rather than a static one.
`git log` on the constants file tells us exactly when each risk parameter changed, so a
trade opened in March 2026 is joined to the stop-loss multiplier that was in force in
March 2026 -- not to today's value. That join is what makes "did the policy change help"
answerable instead of guessable.
"""

from __future__ import annotations

import ast
import json
import logging
import re
import subprocess  # nosec B404 - used only to read local git history, never user input
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.rag.graph.temporal_graph import Edge, Node, TemporalGraph

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRADES_PATH = PROJECT_ROOT / "data" / "trades.json"
JOURNAL_PATH = PROJECT_ROOT / "data" / "put_credit_entries.json"
CONSTANTS_REL = "src/core/trading_constants.py"
LESSONS_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"

# Risk parameters worth tracking through time. Deliberately narrow: every extra key
# multiplies GOVERNED_BY edges by the trade count without adding explanatory power.
TRACKED_POLICIES = (
    "IRON_CONDOR_STOP_LOSS_MULTIPLIER",
    "IC_PROFIT_TARGET_PCT",
    "IRON_CONDOR_EXIT_DTE",
    "IRON_CONDOR_TARGET_DELTA",
    "IRON_CONDOR_WING_WIDTH",
    "MAX_POSITIONS",
    "MAX_CONCURRENT_IRON_CONDORS",
    "MAX_DAILY_STRUCTURES",
    "MAX_CONTRACTS_PER_TRADE",
    "MAX_POSITION_PCT",
    "MAX_DAILY_LOSS_PCT",
    "MIN_DTE",
    "MAX_DTE",
)

_ASSIGN_RE = re.compile(
    r"^(?P<name>[A-Z][A-Z0-9_]*)\s*(?::\s*[^=]+?)?\s*=\s*(?P<value>.+?)\s*(?:#.*)?$"
)


# --------------------------------------------------------------------- policies


@dataclass(frozen=True)
class PolicyWindow:
    """A risk parameter holding one value over a half-open time interval."""

    name: str
    value: Any
    valid_from: str
    valid_to: str | None
    commit: str

    @property
    def node_id(self) -> str:
        return f"policy:{self.name}@{self.valid_from[:10]}"


@dataclass(frozen=True)
class IndeterminateSpan:
    """A period where a tracked policy exists but its value is not statically knowable.

    Constants that delegate to a runtime profile (`= ACTIVE_IRON_CONDOR_PROFILE.x`) cannot
    be resolved from the file alone. Trades in such a span get no GOVERNED_BY edge, so
    they are excluded from cohort attribution instead of being silently bucketed under
    the last literal that happened to be readable.
    """

    name: str
    since: str
    commit: str
    reason: str


@dataclass
class PolicyHistory:
    """Resolved policy windows plus the spans we deliberately refused to guess."""

    windows: list[PolicyWindow]
    indeterminate: list[IndeterminateSpan]


def _git(args: list[str], cwd: Path) -> str:
    # nosec B603 B607 - fixed argv (no shell), `git` resolved from PATH by design so the
    # caller's toolchain is used; `args` are module constants and commit SHAs from
    # `git log`, never user input.
    result = subprocess.run(  # nosec B603 B607
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        logger.warning("git %s failed: %s", " ".join(args), result.stderr.strip())
        return ""
    return result.stdout


def _parse_literal(raw: str) -> Any | None:
    """Return the literal value of an assignment RHS, or None if it is not a literal.

    Many constants delegate to `ACTIVE_IRON_CONDOR_PROFILE.<field>`. Those are recorded
    as unresolved rather than guessed -- an invented policy value would silently
    corrupt every cohort attribution built on top of it.
    """
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None


def extract_policy_history(repo_root: Path | None = None) -> PolicyHistory:
    """Reconstruct policy validity windows from the git history of the constants file.

    A window closes when the value changes, when the constant is deleted, or when it
    stops being a readable literal. That last case matters: on 2026-04-08 the constants
    file was refactored to delegate to a runtime profile, and treating the pre-refactor
    literal as still-in-force would misattribute every subsequent trade.
    """
    root = repo_root or PROJECT_ROOT
    log = _git(["log", "--format=%H|%aI", "--reverse", "--", CONSTANTS_REL], root)
    commits = [line.split("|", 1) for line in log.splitlines() if "|" in line]
    if not commits:
        return PolicyHistory(windows=[], indeterminate=[])

    # name -> (value, valid_from, commit) for the currently-open window
    open_windows: dict[str, tuple[Any, str, str]] = {}
    closed: list[PolicyWindow] = []
    indeterminate: dict[str, IndeterminateSpan] = {}

    def close(name: str, at: str) -> None:
        prior = open_windows.pop(name, None)
        if prior is not None:
            closed.append(
                PolicyWindow(
                    name=name, value=prior[0], valid_from=prior[1], valid_to=at, commit=prior[2]
                )
            )

    for sha, iso_date in commits:
        blob = _git(["show", f"{sha}:{CONSTANTS_REL}"], root)
        if not blob:
            continue
        values, unresolved = _parse_constants(blob)

        for name, value in values.items():
            indeterminate.pop(name, None)
            prior = open_windows.get(name)
            if prior is None:
                open_windows[name] = (value, iso_date, sha)
            elif prior[0] != value:
                close(name, iso_date)
                open_windows[name] = (value, iso_date, sha)

        # Present but not statically readable -> stop attributing, and say why.
        for name in unresolved:
            close(name, iso_date)
            indeterminate.setdefault(
                name,
                IndeterminateSpan(
                    name=name,
                    since=iso_date,
                    commit=sha,
                    reason="value delegates to a runtime profile; not resolvable from source",
                ),
            )

        # Removed from the file entirely.
        for name in set(open_windows) - set(values) - unresolved:
            close(name, iso_date)

    for name, (value, valid_from, sha) in open_windows.items():
        closed.append(
            PolicyWindow(name=name, value=value, valid_from=valid_from, valid_to=None, commit=sha)
        )

    return PolicyHistory(
        windows=sorted(closed, key=lambda w: (w.name, w.valid_from)),
        indeterminate=sorted(indeterminate.values(), key=lambda s: s.name),
    )


def _parse_constants(source: str) -> tuple[dict[str, Any], set[str]]:
    """Return (resolved literals, names present but not resolvable) for one revision."""
    found: dict[str, Any] = {}
    unresolved: set[str] = set()
    for line in source.splitlines():
        match = _ASSIGN_RE.match(line.strip())
        if not match:
            continue
        name = match.group("name")
        if name not in TRACKED_POLICIES:
            continue
        value = _parse_literal(match.group("value"))
        if value is None:
            unresolved.add(name)
            found.pop(name, None)
        else:
            found[name] = value
            unresolved.discard(name)
    return found, unresolved


# ----------------------------------------------------------------------- trades


def _entry_ts(trade: dict) -> str | None:
    return trade.get("entry_time") or trade.get("entry_date")


def _load_json(path: Path) -> Any:
    if not path.exists():
        logger.warning("missing data source: %s", path)
        return {}
    with path.open() as handle:
        return json.load(handle)


def _trade_nodes_and_edges(
    trades: list[dict],
    windows: list[PolicyWindow],
    evidence_tier: str = "paired_ledger",
) -> tuple[list[Node], list[Edge]]:
    """Build trade nodes. `evidence_tier` decides whether a row may score.

    `paired_ledger` rows come from `data/trades.json` and are broker-reconciled closed
    structures. `journal` rows come from the entry lifecycle file: they may still be
    open, they carry no `realized_pnl`, and per data-integrity.md they are never trades.
    Both are stored -- only the former is allowed into any metric.
    """
    nodes: list[Node] = []
    edges: list[Edge] = []
    seen_kinds: set[str] = set()

    by_policy: dict[str, list[PolicyWindow]] = {}
    for window in windows:
        by_policy.setdefault(window.name, []).append(window)

    for trade in trades:
        trade_id = trade.get("id")
        if not trade_id:
            continue
        node_id = f"trade:{trade_id}"
        entry = _entry_ts(trade)
        exit_ts = trade.get("exit_time") or trade.get("exit_date")
        pnl = float(trade.get("realized_pnl") or 0.0)
        strategy = trade.get("strategy") or trade.get("strategy_family") or "unknown"
        outcome = trade.get("outcome") or "unknown"
        exit_reason = trade.get("exit_reason")

        nodes.append(
            Node(
                id=node_id,
                kind="trade",
                label=f"{trade.get('symbol', '?')} {strategy} {pnl:+.2f}",
                attrs={
                    "symbol": trade.get("symbol"),
                    "strategy": strategy,
                    "realized_pnl": pnl,
                    "outcome": outcome,
                    "entry_credit": trade.get("entry_credit"),
                    "exit_debit": trade.get("exit_debit"),
                    "signature": trade.get("signature"),
                    "quantity": trade.get("quantity"),
                    "exit_reason": exit_reason,
                    "evidence_tier": evidence_tier,
                    "status": trade.get("status"),
                },
                valid_from=entry,
                valid_to=exit_ts,
            )
        )

        for kind, key in (("strategy", strategy), ("outcome", outcome)):
            target = f"{kind}:{key}"
            if target not in seen_kinds:
                seen_kinds.add(target)
                nodes.append(Node(id=target, kind=kind, label=str(key)))

        edges.append(
            Edge(node_id, "BELONGS_TO", f"strategy:{strategy}", valid_from=entry, valid_to=exit_ts)
        )
        edges.append(
            Edge(
                node_id,
                "RESULTED_IN",
                f"outcome:{outcome}",
                weight=abs(pnl),
                attrs={"realized_pnl": pnl},
                valid_from=exit_ts,
            )
        )

        # exit_reason is present on only a fraction of the ledger. Absent is recorded
        # as `unrecorded`, never inferred from the P/L sign -- a guessed exit reason
        # would fabricate the very attribution this graph exists to provide.
        reason_key = exit_reason or "unrecorded"
        reason_node = f"exit_reason:{reason_key}"
        if reason_node not in seen_kinds:
            seen_kinds.add(reason_node)
            nodes.append(
                Node(
                    id=reason_node,
                    kind="exit_reason",
                    label=reason_key,
                    attrs={"inferred": False, "recorded": exit_reason is not None},
                )
            )
        edges.append(Edge(node_id, "EXITED_VIA", reason_node, valid_from=exit_ts))

        signature = trade.get("signature") or ""
        expiry_match = re.search(r"(\d{4}-\d{2}-\d{2})", signature)
        if expiry_match:
            expiry_node = f"expiry:{expiry_match.group(1)}"
            if expiry_node not in seen_kinds:
                seen_kinds.add(expiry_node)
                nodes.append(Node(id=expiry_node, kind="expiry", label=expiry_match.group(1)))
            edges.append(Edge(node_id, "CONCENTRATED_IN", expiry_node, valid_from=entry))

        # The temporal join: which policy value was actually in force at entry.
        if entry:
            for name, name_windows in by_policy.items():
                window = _window_at(name_windows, entry)
                if window is None:
                    continue
                edges.append(
                    Edge(
                        node_id,
                        "GOVERNED_BY",
                        window.node_id,
                        attrs={"policy": name, "value": window.value},
                        valid_from=entry,
                        valid_to=exit_ts,
                    )
                )

    return nodes, edges


def _window_at(windows: list[PolicyWindow], timestamp: str) -> PolicyWindow | None:
    for window in windows:
        if window.valid_from <= timestamp and (
            window.valid_to is None or timestamp < window.valid_to
        ):
            return window
    return None


# ---------------------------------------------------------------------- lessons


def _lesson_nodes_and_edges(strategies: set[str]) -> tuple[list[Node], list[Edge]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    if not LESSONS_DIR.exists():
        return nodes, edges

    for path in sorted(LESSONS_DIR.glob("*.md")):
        text = path.read_text(errors="replace")
        lesson_id = f"lesson:{path.stem}"
        title = next(
            (ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("#")),
            path.stem,
        )
        severity = "HIGH" if re.search(r"severity[:\s]*(HIGH|CRITICAL)", text, re.I) else "MEDIUM"
        nodes.append(
            Node(
                id=lesson_id,
                kind="lesson",
                label=title[:120],
                attrs={"path": str(path.relative_to(PROJECT_ROOT)), "severity": severity},
            )
        )

        upper = text.upper()
        for strategy in strategies:
            token = strategy.upper().replace("_", " ")
            if strategy.upper() in upper or token in upper:
                edges.append(Edge(lesson_id, "WARNED_ABOUT", f"strategy:{strategy}"))
        for policy in TRACKED_POLICIES:
            if policy in text:
                edges.append(
                    Edge(lesson_id, "WARNED_ABOUT", f"policy_name:{policy}", attrs={"exact": True})
                )

    return nodes, edges


# ------------------------------------------------------------------------ build


def build_graph(db_path: str | Path | None = None, rebuild: bool = True) -> dict[str, Any]:
    """Build (or rebuild) the trade graph. Returns ingestion stats."""
    graph = TemporalGraph(db_path)
    if rebuild:
        graph.clear()

    history = extract_policy_history()
    windows = history.windows
    policy_nodes: list[Node] = []
    policy_edges: list[Edge] = []
    by_name: dict[str, list[PolicyWindow]] = {}

    for window in windows:
        by_name.setdefault(window.name, []).append(window)
        policy_nodes.append(
            Node(
                id=window.node_id,
                kind="policy",
                label=f"{window.name}={window.value}",
                attrs={"name": window.name, "value": window.value, "commit": window.commit},
                valid_from=window.valid_from,
                valid_to=window.valid_to,
            )
        )

    # A stable per-parameter node so lessons can point at the parameter itself, and
    # SUPERSEDED_BY chains so "what did this value replace" is one hop.
    for name, name_windows in by_name.items():
        policy_nodes.append(Node(id=f"policy_name:{name}", kind="policy_name", label=name))
        for window in name_windows:
            policy_edges.append(Edge(window.node_id, "INSTANCE_OF", f"policy_name:{name}"))
        for earlier, later in zip(name_windows, name_windows[1:], strict=False):
            policy_edges.append(
                Edge(
                    earlier.node_id,
                    "SUPERSEDED_BY",
                    later.node_id,
                    attrs={"from": earlier.value, "to": later.value},
                    valid_from=later.valid_from,
                )
            )

    ledger = _load_json(TRADES_PATH)
    trades = ledger.get("trades", []) if isinstance(ledger, dict) else []
    trade_nodes, trade_edges = _trade_nodes_and_edges(trades, windows)

    journal = _load_json(JOURNAL_PATH)
    journal_trades = [
        {**entry, "id": key, "symbol": "SPY", "strategy": entry.get("strategy_family", "unknown")}
        for key, entry in (journal.items() if isinstance(journal, dict) else [])
    ]
    journal_nodes, journal_edges = _trade_nodes_and_edges(
        journal_trades, windows, evidence_tier="journal"
    )

    strategies = {
        n.attrs.get("strategy", "unknown") for n in trade_nodes + journal_nodes if n.kind == "trade"
    }
    lesson_nodes, lesson_edges = _lesson_nodes_and_edges(strategies)

    graph.add_many(
        nodes=[*policy_nodes, *trade_nodes, *journal_nodes, *lesson_nodes],
        edges=[*policy_edges, *trade_edges, *journal_edges, *lesson_edges],
    )

    stats = graph.stats()
    stats["policy_windows"] = len(windows)
    stats["never_resolved_policies"] = sorted(
        set(TRACKED_POLICIES) - set(by_name) - {s.name for s in history.indeterminate}
    )
    # Surfaced, not swallowed: these parameters have no attributable cohort after the
    # listed date, so any cohort table for them is knowingly incomplete.
    stats["indeterminate_since"] = [
        {"policy": s.name, "since": s.since[:10], "reason": s.reason} for s in history.indeterminate
    ]
    stats["ledger_trades"] = len(trades)
    stats["journal_entries"] = len(journal_trades)
    graph.close()
    return stats
