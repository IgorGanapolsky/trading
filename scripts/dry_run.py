#!/usr/bin/env python3
"""
Dry Run CLI: Execute planning, data collection, and analysis without placing trades.

Usage:
  python3 scripts/dry_run.py --symbols SPY QQQ VOO

Notes:
  - Loads .env if present.
  - Skips execution phase entirely (no ADK/MCP orders).
  - Prints ensemble vote and top agent recommendations per symbol.
"""

import argparse
import json
import os  # noqa: F401

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

import sys
from pathlib import Path

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestration.elite_orchestrator import EliteOrchestrator
from src.rag.sentiment_store import SentimentRAGStore


def dry_run(symbols: list[str], args) -> int:
    eo = EliteOrchestrator(paper=True, enable_planning=True)
    # Optional agent filters
    include = set(getattr(args, "include_agents", []) or [])
    exclude = set(getattr(args, "exclude_agents", []) or [])
    if include or exclude:
        eo._analysis_agent_filter = {"include": include, "exclude": exclude}

    # Optional weights/thresholds
    if getattr(args, "weight_mcp", None) is not None:
        eo.ensemble_weights["mcp"] = args.weight_mcp
    if getattr(args, "weight_langchain", None) is not None:
        eo.ensemble_weights["langchain"] = args.weight_langchain
    if getattr(args, "weight_gemini", None) is not None:
        eo.ensemble_weights["gemini"] = args.weight_gemini
    if getattr(args, "weight_ml", None) is not None:
        eo.ensemble_weights["ml"] = args.weight_ml
        eo.ensemble_weights["ensemble_rl"] = args.weight_ml
    if getattr(args, "weight_grok", None) is not None:
        eo.ensemble_weights["grok"] = args.weight_grok
    if getattr(args, "buy_threshold", None) is not None:
        eo.ensemble_buy_threshold = args.buy_threshold
    if getattr(args, "sell_threshold", None) is not None:
        eo.ensemble_sell_threshold = args.sell_threshold
    plan = eo.create_trade_plan(symbols)

    # Phase 2: Data collection
    data = eo._execute_data_collection(plan)

    # Phase 3: Analysis (ensemble voting)
    analysis = eo._execute_analysis(plan, data)

    print("\n=== Ensemble Vote ===")
    for sym, vote in analysis.get("ensemble_vote", {}).items():
        if "weighted_score" in vote:
            print(
                f"{sym}: consensus={vote.get('consensus')} score={vote.get('weighted_score')} thresholds=({vote.get('sell_threshold')}, {vote.get('buy_threshold')})"
            )
        else:
            print(f"{sym}: consensus={vote.get('consensus')}")

    print("\n=== Agent Recommendations (top 5) ===")
    agent_results = analysis.get("agent_results", [])
    for rec in agent_results[:5]:
        print(json.dumps(rec, indent=2))

    # Phase 4: Risk assessment (informational only)
    risk = eo._execute_risk_assessment(plan)
    print("\n=== Risk Assessment ===")
    print(json.dumps(risk, indent=2, default=str))

    exec_result = None
    if getattr(args, "execute", False):
        exec_result = eo._execute_trades(plan, analysis)
        print("\n=== Execution (paper) ===")
        print(json.dumps(exec_result, indent=2, default=str))

    # Optional export
    export_path = getattr(args, "export_json", None)
    if export_path:
        payload = {
            "plan_id": plan.plan_id,
            "symbols": symbols,
            "ensemble_vote": analysis.get("ensemble_vote", {}),
            "agent_results": analysis.get("agent_results", [])[:20],
            "risk": risk,
            "execution": exec_result,
        }
        with open(export_path, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(f"\nExported report to: {export_path}")

    # Optional Markdown export
    export_md = getattr(args, "export_md", None)
    if export_md:
        lines = []
        lines.append(f"# Dry Run Report: {', '.join(symbols)}")
        lines.append("")
        # Optional: include latest Bogleheads snapshot summary from RAG
        try:
            store = SentimentRAGStore()
            bh = store.get_ticker_history("MARKET", limit=1)
            if bh:
                lines.append("## Bogleheads Snapshot (Latest)")
                md = bh[0]
                meta = md.get("metadata", {})
                # Try to parse TL;DR from document JSON if available
                tldr = None
                try:
                    import json as _J

                    doc = md.get("document", "")
                    parsed = _J.loads(doc) if doc and doc.strip().startswith("{") else {}
                    tldr = parsed.get("tl_dr")
                except Exception:
                    tldr = None
                lines.append(
                    f"- Date: `{meta.get('snapshot_date', 'n/a')}` | Regime: `{meta.get('market_regime', 'unknown')}` | Confidence: `{meta.get('confidence', 'n/a')}`"
                )
                if tldr:
                    lines.append(f"- TL;DR: {tldr}")
                lines.append("")
            else:
                # Fallback: query agent directly if store empty
                try:
                    from src.agents.bogleheads_agent import BogleHeadsAgent

                    agent = BogleHeadsAgent()
                    res = agent.analyze({"symbol": None})
                    lines.append("## Bogleheads Snapshot (Agent Fallback)")
                    lines.append(
                        f"- Decision: `{(res.get('signal') or 'HOLD')}` | Confidence: `{res.get('confidence', 0.5)}`"
                    )
                    # Short TL;DR from agent
                    r = (res.get("reasoning") or "").strip()
                    if r:
                        lines.append(f"- TL;DR: {r[:160]}...")
                    lines.append("")
                except Exception:
                    pass
        except Exception:
            # Last-resort: read JSON fallback if present
            try:
                import json as _J
                from pathlib import Path as _P

                fp = _P("data/rag/bogleheads_latest.json")
                if fp.exists():
                    data = _J.loads(fp.read_text(encoding="utf-8"))
                    meta = data.get("metadata", {})
                    snap = data.get("snapshot", {})
                    tldr = snap.get("tl_dr")
                    lines.append("## Bogleheads Snapshot (Latest, JSON Fallback)")
                    lines.append(
                        f"- Date: `{meta.get('published_date', 'n/a')}` | Regime: `{meta.get('market_regime', 'unknown')}` | Confidence: `{meta.get('confidence', 'n/a')}`"
                    )
                    if tldr:
                        lines.append(f"- TL;DR: {tldr}")
                    lines.append("")
            except Exception:
                pass
        lines.append(f"Plan ID: `{plan.plan_id}`")
        lines.append("")
        lines.append("## Ensemble Consensus")
        for sym, vote in (analysis.get("ensemble_vote", {}) or {}).items():
            if "weighted_score" in vote:
                lines.append(
                    f"- **{sym}**: consensus: `{vote.get('consensus')}`, score: `{vote.get('weighted_score')}`, thresholds: `({vote.get('sell_threshold')}, {vote.get('buy_threshold')})`"
                )
                contribs = sorted(
                    vote.get("contributions", []),
                    key=lambda x: abs(x.get("contrib", 0)),
                    reverse=True,
                )[:3]
                for c in contribs:
                    lines.append(
                        f"  - {c.get('agent')}: action `{c.get('action')}`, conf `{c.get('confidence')}`, weight `{c.get('weight')}`, contrib `{c.get('contrib')}`"
                    )
            else:
                lines.append(f"- **{sym}**: consensus: `{vote.get('consensus')}`")
        lines.append("")
        lines.append("## Risk Summary")
        status = risk.get("risk_checks", {}).get("portfolio_health", {})
        lines.append(f"- Portfolio health success: `{status.get('success', False)}`")
        for sym in symbols:
            pos = risk.get("risk_checks", {}).get(f"{sym}_position", {})
            if pos:
                primary = (
                    pos.get("recommendations", {})
                    .get("primary_method", {})
                    .get("position_size_dollars", 0)
                )
                lines.append(f"- {sym} position (primary): `${primary}`")
        if exec_result:
            lines.append("")
            lines.append("## Execution (Paper)")
            for o in exec_result.get("orders", []):
                lines.append(f"- {o.get('symbol')}: agent `{o.get('agent')}`")
        with open(export_md, "w") as f:
            f.write("\n".join(lines))
        print(f"Exported markdown to: {export_md}")

    print("\nDry run complete.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry run trading analysis without execution")
    parser.add_argument("--symbols", nargs="*", default=["SPY", "QQQ"], help="Symbols to analyze")
    parser.add_argument(
        "--include-agents",
        nargs="*",
        default=None,
        help="Only include these agents (mcp langchain gemini ml_model ensemble_rl grok_twitter)",
    )
    parser.add_argument(
        "--exclude-agents",
        nargs="*",
        default=None,
        help="Exclude these agents from analysis",
    )
    parser.add_argument("--weight-mcp", type=float, default=None, help="Ensemble weight for MCP")
    parser.add_argument(
        "--weight-langchain",
        type=float,
        default=None,
        help="Ensemble weight for LangChain",
    )
    parser.add_argument(
        "--weight-gemini", type=float, default=None, help="Ensemble weight for Gemini"
    )
    parser.add_argument(
        "--weight-ml", type=float, default=None, help="Ensemble weight for ML model(s)"
    )
    parser.add_argument(
        "--weight-grok",
        type=float,
        default=None,
        help="Ensemble weight for Grok/X Twitter sentiment",
    )
    parser.add_argument(
        "--buy-threshold",
        type=float,
        default=None,
        help="Weighted BUY threshold (default 0.15)",
    )
    parser.add_argument(
        "--sell-threshold",
        type=float,
        default=None,
        help="Weighted SELL threshold (default -0.15)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute trades if consensus BUY (paper mode)",
    )
    parser.add_argument(
        "--export-json",
        default=None,
        help="Export analysis/risk/execution report to JSON file",
    )
    parser.add_argument("--export-md", default=None, help="Export markdown summary report")
    args = parser.parse_args()
    return dry_run(args.symbols, args)


if __name__ == "__main__":
    raise SystemExit(main())
