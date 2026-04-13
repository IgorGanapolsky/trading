"""Perplexity-backed trading intelligence loop.

The goal is not to let web research place trades. The goal is to keep current
market/event context flowing into artifacts that the trading gates, RAG, and ML
feedback loop can inspect before the next entry decision.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "sonar-pro"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

MODE_FRESHNESS_MINUTES = {
    "pre_market": 240,
    "post_market": 1440,
    "weekend": 10080,
}


@dataclass(frozen=True)
class QuerySpec:
    """A single Perplexity query with scoring metadata."""

    key: str
    prompt: str
    recency: str
    risk_terms: tuple[str, ...]
    priority: int = 1


@dataclass(frozen=True)
class IntelPaths:
    """Output paths produced by the intelligence loop."""

    latest_json: Path
    stamped_json: Path
    rag_lesson: Path
    ml_jsonl: Path
    legacy_pre_market_json: Path | None = None


PRE_MARKET_QUERIES = (
    QuerySpec(
        key="macro_calendar",
        prompt=(
            "For today, list US economic releases, FOMC/Fed speaker events, Treasury "
            "events, and market-moving policy headlines that could affect SPY/SPX "
            "options premium selling. Identify exact times when available."
        ),
        recency="day",
        risk_terms=("fomc", "powell", "cpi", "jobs", "nonfarm", "gdp", "auction", "fed"),
    ),
    QuerySpec(
        key="volatility_regime",
        prompt=(
            "Summarize the current SPY/SPX volatility regime, including VIX drivers, "
            "overnight futures context, and whether short premium entries face event "
            "gap risk today."
        ),
        recency="day",
        risk_terms=("vix", "volatility", "gap", "selloff", "risk-off", "tariff", "war"),
    ),
    QuerySpec(
        key="index_event_risk",
        prompt=(
            "Are there broad index-level events today that should block or caution a "
            "new SPY iron condor entry? Focus on scheduled catalysts, unscheduled "
            "policy shocks, liquidity, and expected intraday volatility."
        ),
        recency="day",
        risk_terms=("block", "avoid", "caution", "shock", "crisis", "halt", "uncertain"),
    ),
)

POST_MARKET_QUERIES = (
    QuerySpec(
        key="market_move_autopsy",
        prompt=(
            "Explain today's SPY/SPX move and volatility shift. Identify the top "
            "drivers, whether the move was event-driven or trend/regime-driven, and "
            "what an iron condor system should learn for tomorrow."
        ),
        recency="day",
        risk_terms=("trend", "breakout", "gap", "selloff", "volatility", "event"),
    ),
    QuerySpec(
        key="options_premium_context",
        prompt=(
            "Summarize today's SPY/SPX options premium environment. Did implied "
            "volatility, skew, or realized volatility favor selling defined-risk "
            "premium, or should the system have waited?"
        ),
        recency="day",
        risk_terms=("realized volatility", "skew", "waited", "unfavorable", "tail"),
    ),
)

WEEKEND_QUERIES = (
    QuerySpec(
        key="iron_condor_research",
        prompt=(
            "Research recent evidence on SPY/SPX iron condor rules: 10-20 delta, "
            "30-45 DTE, 50 percent profit exits, 2x credit stop, event avoidance, "
            "and VIX regime filters. Return actionable rules with citations and "
            "state which rules need backtesting before live use."
        ),
        recency="month",
        risk_terms=("needs backtesting", "avoid", "underperforms", "drawdown", "tail risk"),
    ),
    QuerySpec(
        key="strategy_failure_patterns",
        prompt=(
            "Find failure patterns for short premium index option strategies during "
            "high-volatility regime shifts. Focus on what a 100k paper account should "
            "block before entering new SPY/SPX iron condors."
        ),
        recency="month",
        risk_terms=("regime shift", "tail risk", "loss", "drawdown", "block"),
    ),
)

QUERY_BUNDLES = {
    "pre_market": PRE_MARKET_QUERIES,
    "post_market": POST_MARKET_QUERIES,
    "weekend": WEEKEND_QUERIES,
}

HIGH_RISK_WEIGHTS = {
    "fomc": 0.22,
    "powell": 0.18,
    "cpi": 0.18,
    "nonfarm": 0.18,
    "jobs report": 0.16,
    "tariff": 0.16,
    "war": 0.20,
    "geopolitical": 0.16,
    "selloff": 0.18,
    "gap": 0.14,
    "risk-off": 0.18,
    "volatility spike": 0.22,
    "vix spike": 0.22,
    "avoid": 0.20,
    "block": 0.24,
    "halt": 0.24,
    "crisis": 0.24,
    "uncertain": 0.10,
}

LOW_RISK_WEIGHTS = {
    "no major": -0.14,
    "low volatility": -0.12,
    "calm": -0.12,
    "stable": -0.10,
    "range-bound": -0.08,
    "no scheduled": -0.10,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def compact_trading_context(repo_root: Path) -> dict[str, Any]:
    """Load the minimum account/ledger context needed for market research prompts."""

    public_status = _read_json(repo_root / "docs" / "data" / "public_status.json") or {}
    system_state = _read_json(repo_root / "data" / "system_state.json") or {}
    trades = _read_json(repo_root / "data" / "trades.json") or {}

    paper = public_status.get("paper", {}) if isinstance(public_status, dict) else {}
    ledger = public_status.get("ledger", {}) if isinstance(public_status, dict) else {}
    gate = public_status.get("gate", {}) if isinstance(public_status, dict) else {}

    if not paper and isinstance(system_state, dict):
        paper = system_state.get("paper_account", {})
    if not ledger and isinstance(trades, dict):
        ledger = trades.get("stats", {})

    return {
        "equity": paper.get("equity"),
        "total_pnl_today": paper.get("total_pnl_today") or paper.get("daily_change"),
        "positions_count": paper.get("positions_count")
        or len(system_state.get("positions", []) if isinstance(system_state, dict) else []),
        "closed_trades_total": ledger.get("closed_trades")
        or ledger.get("closed_trades_total")
        or ledger.get("total_trades"),
        "win_rate_pct": ledger.get("win_rate_pct"),
        "profit_factor": ledger.get("profit_factor"),
        "expectancy_per_trade": ledger.get("expectancy_per_trade"),
        "gate_mode": gate.get("mode") if isinstance(gate, dict) else None,
        "scale_allowed": gate.get("scale_allowed") if isinstance(gate, dict) else None,
        "verified_edge_available": gate.get("verified_edge_available")
        if isinstance(gate, dict)
        else None,
    }


def score_text(text: str, spec: QuerySpec | None = None) -> float:
    """Score market/event risk from a Perplexity answer using transparent weights."""

    normalized = re.sub(r"\s+", " ", text.lower())
    score = 0.0

    for term, weight in HIGH_RISK_WEIGHTS.items():
        if term in normalized:
            score += weight

    for term, weight in LOW_RISK_WEIGHTS.items():
        if term in normalized:
            score += weight

    if spec:
        for term in spec.risk_terms:
            if term.lower() in normalized:
                score += 0.05

    return round(_clamp(score), 3)


def recommendation_for(risk_score: float, api_status: str) -> str:
    """Translate risk into a gate-readable recommendation."""

    if risk_score >= 0.70:
        return "BLOCK_NEW_IC"
    if risk_score >= 0.40:
        return "CAUTION"
    if api_status != "ok":
        return "CAUTION_API_UNAVAILABLE"
    return "CLEAR"


def confidence_for(results: list[dict[str, Any]], api_status: str) -> float:
    """Confidence rises with successful answers and citations, falls offline."""

    if not results:
        return 0.0

    answered = sum(1 for item in results if item.get("answer"))
    cited = sum(1 for item in results if item.get("citations"))
    base = 0.35 if api_status == "ok" else 0.15
    return round(_clamp(base + answered * 0.12 + cited * 0.08), 3)


def _iso_slug(value: datetime) -> str:
    return value.strftime("%Y%m%d_%H%M%S")


def _date_slug(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def build_paths(repo_root: Path, mode: str, now: datetime) -> IntelPaths:
    base = repo_root / "data" / "analysis" / "perplexity"
    date_slug = _date_slug(now)
    stamp = _iso_slug(now)
    legacy = repo_root / "data" / "analysis" / f"pre_market_{date_slug}.json"
    return IntelPaths(
        latest_json=base / f"{mode}_latest.json",
        stamped_json=base / f"{mode}_{stamp}.json",
        rag_lesson=repo_root
        / "rag_knowledge"
        / "lessons_learned"
        / f"ll_perplexity_{mode}_{date_slug}.md",
        ml_jsonl=repo_root / "data" / "feedback" / "perplexity_intel_events.jsonl",
        legacy_pre_market_json=legacy if mode == "pre_market" else None,
    )


class PerplexityTradingIntelRunner:
    """Run Perplexity trading research and persist gate/RAG/ML artifacts."""

    def __init__(
        self,
        repo_root: Path,
        *,
        api_key: str | None = None,
        model: str | None = None,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.api_key = api_key if api_key is not None else os.getenv("PERPLEXITY_API_KEY", "")
        self.model = model or os.getenv("PERPLEXITY_TRADING_MODEL", DEFAULT_MODEL)
        self.dry_run = dry_run
        self.now = now or utc_now()

    async def run(self, mode: str, *, write: bool = True) -> dict[str, Any]:
        if mode == "all":
            combined: dict[str, Any] = {
                "generated_at_utc": self.now.isoformat(),
                "mode": "all",
                "runs": {},
            }
            for child_mode in ("pre_market", "post_market", "weekend"):
                combined["runs"][child_mode] = await self.run(child_mode, write=write)
            return combined

        if mode not in QUERY_BUNDLES:
            raise ValueError(f"Unsupported Perplexity intel mode: {mode}")

        context = compact_trading_context(self.repo_root)
        results: list[dict[str, Any]] = []
        api_status = "dry_run" if self.dry_run else ("ok" if self.api_key else "missing_api_key")

        for spec in QUERY_BUNDLES[mode]:
            results.append(await self._ask(spec, mode, context))

        if any(item.get("api_status") == "error" for item in results):
            api_status = "partial_error"
        elif all(item.get("api_status") == "missing_api_key" for item in results):
            api_status = "missing_api_key"
        elif all(item.get("api_status") == "dry_run" for item in results):
            api_status = "dry_run"

        risk_score = round(
            _clamp(sum(_safe_float(item.get("risk_score")) for item in results) / max(len(results), 1)),
            3,
        )
        recommendation = recommendation_for(risk_score, api_status)
        confidence = confidence_for(results, api_status)

        payload = {
            "generated_at_utc": self.now.isoformat(),
            "mode": mode,
            "model": self.model,
            "api_status": api_status,
            "fresh_for_minutes": MODE_FRESHNESS_MINUTES[mode],
            "risk_score": risk_score,
            "recommendation": recommendation,
            "confidence": confidence,
            "trading_context": context,
            "queries": results,
            "gate_contract": {
                "blocks_new_iron_condors": recommendation == "BLOCK_NEW_IC",
                "reason": self._decision_reason(recommendation, risk_score, api_status),
                "source": "perplexity_trading_intel",
            },
        }

        if write:
            self.write_artifacts(mode, payload)

        return payload

    async def _ask(
        self, spec: QuerySpec, mode: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        if self.dry_run:
            answer = (
                "Dry run: Perplexity API was not called. Local context was packaged for "
                "research and scoring; live citations require PERPLEXITY_API_KEY."
            )
            return self._format_result(spec, answer, [], "dry_run")

        if not self.api_key:
            answer = (
                "Perplexity API key is not configured in this runtime. The trading loop "
                "should treat web intelligence as degraded until GitHub Actions or the "
                "local agent provides PERPLEXITY_API_KEY."
            )
            return self._format_result(spec, answer, [], "missing_api_key")

        system_prompt = (
            "You are a trading risk analyst for a paper SPY/SPX iron condor system. "
            "Be concise, cite current sources, and distinguish hard blockers from "
            "context. Do not recommend trades. Output factual event/regime intelligence."
        )
        user_prompt = (
            f"Mode: {mode}\n"
            f"Current trading context JSON: {json.dumps(context, sort_keys=True)}\n\n"
            f"Research task: {spec.prompt}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "search_recency_filter": spec.recency,
            "return_citations": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            import httpx

            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(PERPLEXITY_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            return self._format_result(spec, f"Perplexity API error: {exc}", [], "error")

        answer = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        citations = data.get("citations", [])
        return self._format_result(spec, answer, citations, "ok")

    def _format_result(
        self,
        spec: QuerySpec,
        answer: str,
        citations: list[str],
        api_status: str,
    ) -> dict[str, Any]:
        return {
            "key": spec.key,
            "priority": spec.priority,
            "prompt": spec.prompt,
            "api_status": api_status,
            "risk_score": score_text(answer, spec),
            "answer": answer,
            "citations": citations[:8],
        }

    def _decision_reason(self, recommendation: str, risk_score: float, api_status: str) -> str:
        if recommendation == "BLOCK_NEW_IC":
            return f"Fresh Perplexity event/regime risk score {risk_score:.2f} blocks new IC entries."
        if recommendation == "CAUTION":
            return f"Perplexity event/regime risk score {risk_score:.2f} requires caution."
        if recommendation == "CAUTION_API_UNAVAILABLE":
            return f"Perplexity intelligence degraded ({api_status}); do not increase risk based on stale context."
        return "Fresh Perplexity intelligence found no major event/regime blocker."

    def write_artifacts(self, mode: str, payload: dict[str, Any]) -> IntelPaths:
        paths = build_paths(self.repo_root, mode, self.now)
        for path in (
            paths.latest_json,
            paths.stamped_json,
            paths.rag_lesson,
            paths.ml_jsonl,
            paths.legacy_pre_market_json,
        ):
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)

        json_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        paths.latest_json.write_text(json_text, encoding="utf-8")
        paths.stamped_json.write_text(json_text, encoding="utf-8")

        if mode == "pre_market":
            trading_latest = paths.latest_json.parent / "trading_intel_latest.json"
            trading_latest.write_text(json_text, encoding="utf-8")

        if paths.legacy_pre_market_json:
            legacy = {
                "date": _date_slug(self.now),
                "time": self.now.strftime("%H:%M UTC"),
                "risk_score": payload["risk_score"],
                "recommendation": payload["recommendation"],
                "reason": payload["gate_contract"]["reason"],
                "intel": {item["key"]: item["answer"] for item in payload["queries"]},
                "source": "perplexity_trading_intel",
            }
            paths.legacy_pre_market_json.write_text(
                json.dumps(legacy, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        paths.rag_lesson.write_text(render_rag_lesson(payload), encoding="utf-8")
        with paths.ml_jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(render_ml_event(payload), sort_keys=True) + "\n")

        return paths


def render_rag_lesson(payload: dict[str, Any]) -> str:
    """Render a compact RAG lesson from a Perplexity intel run."""

    citations = []
    for item in payload.get("queries", []):
        citations.extend(item.get("citations", [])[:3])
    unique_citations = list(dict.fromkeys(citations))[:8]

    lines = [
        f"# Perplexity Trading Intel: {payload.get('mode')}",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Recommendation: `{payload.get('recommendation')}`",
        f"- Risk score: `{payload.get('risk_score')}`",
        f"- Confidence: `{payload.get('confidence')}`",
        f"- API status: `{payload.get('api_status')}`",
        f"- Gate reason: {payload.get('gate_contract', {}).get('reason')}",
        "",
        "## Query Findings",
    ]
    for item in payload.get("queries", []):
        answer = str(item.get("answer", "")).replace("\n", " ").strip()
        if len(answer) > 700:
            answer = answer[:700].rstrip() + "..."
        lines.extend(
            [
                "",
                f"### {item.get('key')}",
                f"- Risk score: `{item.get('risk_score')}`",
                f"- Summary: {answer}",
            ]
        )

    if unique_citations:
        lines.append("")
        lines.append("## Citations")
        lines.extend(f"- {url}" for url in unique_citations)

    lines.append("")
    return "\n".join(lines)


def render_ml_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Return one JSONL event for downstream ML/RAG pipelines."""

    context = payload.get("trading_context", {})
    return {
        "event_type": "perplexity_trading_intel",
        "generated_at_utc": payload.get("generated_at_utc"),
        "mode": payload.get("mode"),
        "model": payload.get("model"),
        "api_status": payload.get("api_status"),
        "risk_score": payload.get("risk_score"),
        "recommendation": payload.get("recommendation"),
        "confidence": payload.get("confidence"),
        "blocks_new_iron_condors": payload.get("gate_contract", {}).get(
            "blocks_new_iron_condors"
        ),
        "equity": context.get("equity"),
        "win_rate_pct": context.get("win_rate_pct"),
        "profit_factor": context.get("profit_factor"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Perplexity trading intelligence loop")
    parser.add_argument(
        "--mode",
        choices=["pre_market", "post_market", "weekend", "all"],
        default="pre_market",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


async def async_main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    runner = PerplexityTradingIntelRunner(
        args.repo_root.resolve(),
        dry_run=args.dry_run,
    )
    payload = await runner.run(args.mode, write=not args.no_write)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main(argv: list[str] | None = None) -> None:
    asyncio.run(async_main(argv))


if __name__ == "__main__":
    main()
