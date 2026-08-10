"""Build / refresh the financial knowledge graph from local ledgers.

Sources (authoritative for this lab):
- Seed ontology (strategies, rules, tickers)
- ``data/runtime/strategy_kill_switch.json``
- ``rag_knowledge/lessons_learned/*.md``
- ``data/trades.json`` paired closed structures
- Optional macro signal JSON under ``data/runtime/``
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.rag.graph.schema import (
    SEED_CONCEPTS,
    SEED_RULES,
    SEED_STRATEGIES,
    SEED_TICKERS,
    TICKER_PATTERN_SOURCES,
    EdgeRel,
    NodeType,
)
from src.rag.graph.store import FinancialGraphStore

logger = logging.getLogger(__name__)

_LESSON_ID_RE = re.compile(r"\b(LL[-_]?\d+)\b", re.IGNORECASE)
_TICKER_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in TICKER_PATTERN_SOURCES) + r")\b",
    re.IGNORECASE,
)

_STRATEGY_ALIASES: dict[str, str] = {
    "spy put credit": "spy_put_credit",
    "put credit": "spy_put_credit",
    "bull put": "spy_put_credit",
    "put credit spread": "spy_put_credit",
    "iron condor": "iron_condor",
    "ic simple": "ic_simple",
    "ic_simple": "ic_simple",
    "residual ic": "residual_ic",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


NODE_SPY = "ticker:SPY"
NODE_SPY_PUT_CREDIT = "strategy:spy_put_credit"
NODE_IRON_CONDOR = "strategy:iron_condor"
NODE_IC_SIMPLE = "strategy:ic_simple"


def _trade_outcome(raw: Any, pnl: float) -> str:
    if raw:
        return str(raw)
    if pnl > 0:
        return "win"
    if pnl < 0:
        return "loss"
    return "flat"


def _strategy_node_id(strategy: str) -> str:
    """Map a trade strategy string to a canonical strategy node id."""
    s = (strategy or "unknown").lower().strip()
    if s == "ic_simple":
        return NODE_IC_SIMPLE
    if s in {"iron_condor", "ic"}:
        return NODE_IRON_CONDOR
    if "put" in s and "credit" in s:
        return NODE_SPY_PUT_CREDIT
    if s in SEED_STRATEGIES:
        return f"strategy:{s}"
    return f"strategy:{s or 'unknown'}"


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None


def _normalize_lesson_id(raw: str) -> str:
    m = re.search(r"ll[-_]?(\d+)", raw.lower())
    if m:
        return f"lesson:LL-{m.group(1)}"
    return f"lesson:{raw}"


def _extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines()[:30]:
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()[:200]
    return fallback


def _extract_severity(content: str) -> str:
    m = re.search(
        r"\*\*severity\*\*:\s*\*?(critical|high|medium|low|p0|p1|p2|p3)\*?",
        content,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).upper()
    m2 = re.search(r"severity\s*[:=]\s*(critical|high|medium|low)", content, re.IGNORECASE)
    if m2:
        return m2.group(1).upper()
    return "MEDIUM"


class FinancialGraphBuilder:
    """Incremental builder that can full-rebuild or soft-refresh the graph."""

    def __init__(
        self,
        store: FinancialGraphStore,
        repo_root: str | Path | None = None,
    ):
        self.store = store
        self.repo_root = Path(repo_root or Path.cwd())

    def rebuild(self, *, clear: bool = True) -> dict[str, Any]:
        if clear:
            self.store.clear()
        counts: Counter[str] = Counter()
        counts.update(self.seed_ontology())
        counts.update(self.ingest_kill_switch())
        counts.update(self.ingest_lessons())
        counts.update(self.ingest_arxiv_papers())
        counts.update(self.ingest_trades())
        counts.update(self.ingest_runtime_signals())
        stats = self.store.stats()
        return {
            "built_at": _utc_now(),
            "ingest_counts": dict(counts),
            "stats": stats,
        }

    # ------------------------------------------------------------------
    # Seeds
    # ------------------------------------------------------------------

    def seed_ontology(self) -> Counter[str]:
        c: Counter[str] = Counter()
        for ticker in SEED_TICKERS:
            self.store.upsert_node(
                f"ticker:{ticker}",
                NodeType.TICKER,
                label=ticker,
                properties={"symbol": ticker},
            )
            c["nodes"] += 1

        for sid, meta in SEED_STRATEGIES.items():
            self.store.upsert_node(
                f"strategy:{sid}",
                NodeType.STRATEGY,
                label=meta["label"],
                properties=dict(meta),
            )
            c["nodes"] += 1
            # Active strategies trade SPY
            if sid in {"spy_put_credit", "iron_condor", "ic_simple", "residual_ic"}:
                self.store.upsert_edge(
                    f"strategy:{sid}",
                    NODE_SPY,
                    EdgeRel.TRADES,
                    weight=1.0,
                    properties={"underlying": "SPY"},
                    edge_id=f"e:strategy:{sid}:TRADES:ticker:SPY",
                )
                c["edges"] += 1

        for rid, label in SEED_RULES.items():
            self.store.upsert_node(rid, NodeType.RULE, label=label, properties={"rule": True})
            c["nodes"] += 1
            # Put-credit rules govern active strategy
            self.store.upsert_edge(
                rid,
                NODE_SPY_PUT_CREDIT,
                EdgeRel.GOVERNS,
                weight=1.2,
                edge_id=f"e:{rid}:GOVERNS:strategy:spy_put_credit",
            )
            c["edges"] += 1

        # IC kill rule
        self.store.upsert_edge(
            "rule:no_new_ic_entries",
            NODE_IRON_CONDOR,
            EdgeRel.BLOCKS,
            weight=2.0,
            edge_id="e:rule:no_new_ic_entries:BLOCKS:strategy:iron_condor",
        )
        c["edges"] += 1

        for cid, label in SEED_CONCEPTS.items():
            self.store.upsert_node(cid, NodeType.CONCEPT, label=label)
            c["nodes"] += 1

        # Macro concepts impact SPY / sector proxies
        self.store.upsert_edge(
            "concept:fed_policy",
            NODE_SPY,
            EdgeRel.IMPACTS,
            weight=1.1,
            edge_id="e:concept:fed_policy:IMPACTS:ticker:SPY",
        )
        self.store.upsert_edge(
            "concept:vix_spike",
            NODE_SPY_PUT_CREDIT,
            EdgeRel.IMPACTS,
            weight=1.3,
            edge_id="e:concept:vix_spike:IMPACTS:strategy:spy_put_credit",
        )
        self.store.upsert_edge(
            "concept:inventory_hygiene",
            NODE_SPY_PUT_CREDIT,
            EdgeRel.BLOCKS,
            weight=1.5,
            properties={"gate": "UNCLEAN_INVENTORY"},
            edge_id="e:concept:inventory_hygiene:BLOCKS:strategy:spy_put_credit",
        )
        self.store.upsert_edge(
            NODE_SPY_PUT_CREDIT,
            NODE_IRON_CONDOR,
            EdgeRel.SUCCEEDS,
            weight=1.0,
            properties={"note": "put-credit is successor after IC kill"},
            edge_id="e:strategy:spy_put_credit:SUCCEEDS:strategy:iron_condor",
        )
        c["edges"] += 4

        # Cross-ticker correlations (lab-relevant ETFs only)
        for a, b, w in (
            ("SPY", "QQQ", 0.9),
            ("SPY", "IWM", 0.75),
            ("SPY", "VIX", -0.7),
            ("SPY", "XSP", 0.99),
        ):
            self.store.upsert_edge(
                f"ticker:{a}",
                f"ticker:{b}",
                EdgeRel.CORRELATES_WITH,
                weight=abs(w),
                properties={"approx_corr": w},
                edge_id=f"e:ticker:{a}:CORRELATES_WITH:ticker:{b}",
            )
            c["edges"] += 1
        return c

    # ------------------------------------------------------------------
    # Kill switch
    # ------------------------------------------------------------------

    def ingest_kill_switch(self) -> Counter[str]:
        c: Counter[str] = Counter()
        path = self.repo_root / "data/runtime/strategy_kill_switch.json"
        data = _read_json(path)
        if not isinstance(data, dict):
            return c

        updated = str(data.get("updated_at") or _utc_now())
        active = data.get("active_family") or "spy_put_credit"
        killed = data.get("killed_families") or []
        live_blocked = bool(data.get("live_blocked", True))
        paper_only = bool(data.get("paper_only", True))
        reason = str(data.get("reason") or "")[:500]

        event_id = "macro:strategy_kill_2026_07_22"
        self.store.upsert_node(
            event_id,
            NodeType.MACRO_EVENT,
            label="IC Simple killed; spy_put_credit successor",
            properties={
                "active_family": active,
                "killed_families": killed,
                "live_blocked": live_blocked,
                "paper_only": paper_only,
                "reason": reason,
                "evidence": data.get("evidence"),
            },
        )
        c["nodes"] += 1

        for fam in killed:
            sid = f"strategy:{fam}"
            self.store.upsert_node(
                sid,
                NodeType.STRATEGY,
                label=SEED_STRATEGIES.get(fam, {}).get("label", fam),
                properties={"status": "killed", **(SEED_STRATEGIES.get(fam) or {})},
            )
            self.store.upsert_edge(
                event_id,
                sid,
                EdgeRel.KILLED,
                weight=2.0,
                valid_from=updated,
                properties={"source": "strategy_kill_switch.json"},
                edge_id=f"e:{event_id}:KILLED:{sid}",
            )
            c["edges"] += 1

        self.store.upsert_edge(
            event_id,
            f"strategy:{active}",
            EdgeRel.SUCCEEDS,
            weight=1.5,
            valid_from=updated,
            edge_id=f"e:{event_id}:SUCCEEDS:strategy:{active}",
        )
        c["edges"] += 1

        if live_blocked:
            self.store.upsert_edge(
                "rule:live_gate_n30",
                f"strategy:{active}",
                EdgeRel.BLOCKS,
                weight=2.0,
                valid_from=updated,
                properties={"live_blocked": True},
                edge_id=f"e:rule:live_gate_n30:BLOCKS:strategy:{active}",
            )
            c["edges"] += 1
        return c

    # ------------------------------------------------------------------
    # Lessons
    # ------------------------------------------------------------------

    def ingest_lessons(self, limit: int | None = None) -> Counter[str]:
        c: Counter[str] = Counter()
        lessons_dir = self.repo_root / "rag_knowledge/lessons_learned"
        if not lessons_dir.is_dir():
            return c

        files = sorted(lessons_dir.glob("*.md"))
        if limit is not None:
            files = files[:limit]

        for path in files:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.warning("Skip lesson %s: %s", path, exc)
                continue

            stem = path.stem
            lid_match = _LESSON_ID_RE.search(stem) or _LESSON_ID_RE.search(content[:500])
            if lid_match:
                node_id = _normalize_lesson_id(lid_match.group(1))
            else:
                node_id = f"lesson:{stem[:80]}"

            title = _extract_title(content, stem)
            severity = _extract_severity(content)
            snippet = content[:1200]
            self.store.upsert_node(
                node_id,
                NodeType.LESSON,
                label=title,
                properties={
                    "file": str(path.relative_to(self.repo_root))
                    if path.is_relative_to(self.repo_root)
                    else str(path),
                    "severity": severity,
                    "snippet": snippet,
                    "hybrid_leaf": True,  # vector/chunk leaf attach point
                },
            )
            c["nodes"] += 1

            # Tickers mentioned
            for t in sorted({m.group(1).upper() for m in _TICKER_RE.finditer(content)}):
                tid = f"ticker:{t}"
                self.store.upsert_node(tid, NodeType.TICKER, label=t, properties={"symbol": t})
                self.store.upsert_edge(
                    node_id,
                    tid,
                    EdgeRel.MENTIONS,
                    weight=1.0,
                    edge_id=f"e:{node_id}:MENTIONS:{tid}",
                )
                c["edges"] += 1

            # Strategy links
            lower = content.lower()
            linked_strategies: set[str] = set()
            for phrase, sid in _STRATEGY_ALIASES.items():
                if phrase in lower:
                    linked_strategies.add(sid)
            if "kill" in lower and ("iron condor" in lower or "ic simple" in lower):
                linked_strategies.add("iron_condor")
            for sid in linked_strategies:
                self.store.upsert_edge(
                    node_id,
                    f"strategy:{sid}",
                    EdgeRel.RELATED_TO,
                    weight=1.1,
                    edge_id=f"e:{node_id}:RELATED_TO:strategy:{sid}",
                )
                c["edges"] += 1

            # Prevention edges for critical lessons
            if severity in {"CRITICAL", "HIGH", "P0", "P1"}:
                self.store.upsert_edge(
                    node_id,
                    NODE_SPY_PUT_CREDIT,
                    EdgeRel.PREVENTS,
                    weight=1.4 if severity in {"CRITICAL", "P0"} else 1.2,
                    properties={"severity": severity},
                    edge_id=f"e:{node_id}:PREVENTS:strategy:spy_put_credit",
                )
                c["edges"] += 1

            # Concept hooks
            if "inventory" in lower or "orphan" in lower or "lot mismatch" in lower:
                self.store.upsert_edge(
                    node_id,
                    "concept:inventory_hygiene",
                    EdgeRel.RELATED_TO,
                    edge_id=f"e:{node_id}:RELATED_TO:concept:inventory_hygiene",
                )
                c["edges"] += 1
            if "vix" in lower or "volatility" in lower:
                self.store.upsert_edge(
                    node_id,
                    "concept:vix_spike",
                    EdgeRel.RELATED_TO,
                    edge_id=f"e:{node_id}:RELATED_TO:concept:vix_spike",
                )
                c["edges"] += 1
            if "north star" in lower or "6000" in lower or "$6,000" in lower:
                self.store.upsert_edge(
                    node_id,
                    "concept:north_star",
                    EdgeRel.RELATED_TO,
                    edge_id=f"e:{node_id}:RELATED_TO:concept:north_star",
                )
                c["edges"] += 1

        return c

    # ------------------------------------------------------------------
    # arXiv research papers (Agentic RAG continuous ingest)
    # ------------------------------------------------------------------

    def ingest_arxiv_papers(self, limit: int | None = 200) -> Counter[str]:
        """Ingest rag_knowledge/arxiv/*.md as LESSON nodes (research context)."""
        c: Counter[str] = Counter()
        arxiv_dir = self.repo_root / "rag_knowledge/arxiv"
        if not arxiv_dir.is_dir():
            return c

        files = sorted(arxiv_dir.glob("*.md"))
        if limit is not None:
            files = files[:limit]

        for path in files:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.warning("Skip arXiv paper %s: %s", path, exc)
                continue

            stem = path.stem
            node_id = f"arxiv:{stem[:100]}"
            title = _extract_title(content, stem)
            snippet = content[:1200]
            self.store.upsert_node(
                node_id,
                NodeType.LESSON,
                label=title,
                properties={
                    "file": str(path.relative_to(self.repo_root))
                    if path.is_relative_to(self.repo_root)
                    else str(path),
                    "source": "arxiv",
                    "snippet": snippet,
                    "hybrid_leaf": True,
                },
            )
            c["nodes"] += 1

            lower = content.lower()
            if "option" in lower or "put credit" in lower or "volatility" in lower:
                sid = "strategy:spy_put_credit"
                self.store.upsert_node(
                    sid, NodeType.STRATEGY, label="spy_put_credit", properties={}
                )
                self.store.upsert_edge(
                    node_id,
                    sid,
                    EdgeRel.RELATED_TO,
                    edge_id=f"e:{node_id}:RELATED_TO:{sid}",
                )
                c["edges"] += 1
            if "rag" in lower or "retrieval" in lower:
                cid = "concept:agentic_rag"
                self.store.upsert_node(
                    cid, NodeType.CONCEPT, label="agentic_rag", properties={}
                )
                self.store.upsert_edge(
                    node_id,
                    cid,
                    EdgeRel.RELATED_TO,
                    edge_id=f"e:{node_id}:RELATED_TO:{cid}",
                )
                c["edges"] += 1

        return c

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    def ingest_trades(self, max_trades: int = 500) -> Counter[str]:
        c: Counter[str] = Counter()
        path = self.repo_root / "data/trades.json"
        data = _read_json(path)
        if not isinstance(data, dict):
            return c
        trades = data.get("trades") or []
        if not isinstance(trades, list):
            return c

        # Prefer most recent by exit_date
        def _sort_key(t: dict) -> str:
            return str(t.get("exit_date") or t.get("entry_date") or "")

        selected = sorted(
            [t for t in trades if isinstance(t, dict)],
            key=_sort_key,
            reverse=True,
        )[:max_trades]

        strategy_pnl: Counter[str] = Counter()
        strategy_n: Counter[str] = Counter()

        for t in selected:
            tid = str(t.get("id") or t.get("signature") or "")
            if not tid:
                continue
            node_id = f"trade:{tid[:120]}"
            strategy = str(t.get("strategy") or "unknown").lower()
            symbol = str(t.get("symbol") or "SPY").upper()
            pnl = float(t.get("realized_pnl") or 0.0)
            outcome = _trade_outcome(t.get("outcome"), pnl)
            self.store.upsert_node(
                node_id,
                NodeType.TRADE,
                label=f"{strategy} {symbol} {outcome} ${pnl:.0f}",
                properties={
                    "strategy": strategy,
                    "symbol": symbol,
                    "realized_pnl": pnl,
                    "outcome": outcome,
                    "entry_date": t.get("entry_date"),
                    "exit_date": t.get("exit_date"),
                    "quantity": t.get("quantity"),
                    "signature": t.get("signature"),
                },
            )
            c["nodes"] += 1

            sid = _strategy_node_id(strategy)

            self.store.upsert_edge(
                node_id,
                sid,
                EdgeRel.OUTCOME_OF,
                weight=1.0 + min(abs(pnl) / 500.0, 1.0),
                valid_from=str(t.get("exit_date") or t.get("entry_date") or ""),
                properties={"realized_pnl": pnl, "outcome": outcome},
                edge_id=f"e:{node_id}:OUTCOME_OF:{sid}",
            )
            c["edges"] += 1

            self.store.upsert_edge(
                node_id,
                f"ticker:{symbol}",
                EdgeRel.MENTIONS,
                edge_id=f"e:{node_id}:MENTIONS:ticker:{symbol}",
            )
            c["edges"] += 1

            strategy_pnl[sid] += pnl
            strategy_n[sid] += 1

        # Aggregate strategy nodes with realized summary (evidence, not projection)
        for sid, n in strategy_n.items():
            total = strategy_pnl[sid]
            node = self.store.get_node(sid)
            props = dict(node.properties) if node else {}
            props.update(
                {
                    "paired_closed_sample_n": n,
                    "paired_realized_pnl_sum": round(total, 2),
                    "note": "from trades.json sample in graph build; not a profitability claim",
                }
            )
            self.store.upsert_node(
                sid,
                NodeType.STRATEGY,
                label=(node.label if node else sid),
                properties=props,
            )
        return c

    # ------------------------------------------------------------------
    # Runtime signals
    # ------------------------------------------------------------------

    def ingest_runtime_signals(self) -> Counter[str]:
        c: Counter[str] = Counter()
        runtime = self.repo_root / "data/runtime"
        if not runtime.is_dir():
            return c

        signal_globs = (
            "*macro*.json",
            "*sentiment*.json",
            "*regime*.json",
            "*ai_cycle*.json",
            "*credit_stress*.json",
        )
        seen: set[Path] = set()
        for pattern in signal_globs:
            for path in runtime.glob(pattern):
                if path in seen or path.name == "strategy_kill_switch.json":
                    continue
                seen.add(path)
                data = _read_json(path)
                if data is None:
                    continue
                sid = f"signal:{path.stem}"
                self.store.upsert_node(
                    sid,
                    NodeType.SIGNAL,
                    label=path.stem,
                    properties={
                        "file": str(path.relative_to(self.repo_root)),
                        "payload_keys": list(data.keys())[:20] if isinstance(data, dict) else [],
                        "summary": json.dumps(data, default=str)[:800],
                    },
                )
                c["nodes"] += 1
                self.store.upsert_edge(
                    sid,
                    NODE_SPY,
                    EdgeRel.IMPACTS,
                    weight=0.8,
                    edge_id=f"e:{sid}:IMPACTS:ticker:SPY",
                )
                self.store.upsert_edge(
                    sid,
                    NODE_SPY_PUT_CREDIT,
                    EdgeRel.IMPACTS,
                    weight=0.9,
                    edge_id=f"e:{sid}:IMPACTS:strategy:spy_put_credit",
                )
                c["edges"] += 2
        return c


def build_financial_graph(
    repo_root: str | Path | None = None,
    db_path: str | Path | None = None,
    *,
    clear: bool = True,
) -> dict[str, Any]:
    """Convenience entry: build graph and return stats."""
    root = Path(repo_root or Path.cwd())
    store = FinancialGraphStore(db_path=db_path or root / "data/rag/financial_graph.sqlite")
    builder = FinancialGraphBuilder(store, repo_root=root)
    result = builder.rebuild(clear=clear)
    store.close()
    return result
