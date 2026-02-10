"""
Perplexity Research Agent - Autonomous Weekend Backtesting & Strategy Optimization.

Based on: Perplexity Deep Research (Jan 2026) + GPU Acceleration (Feb 2026)
- Natural language → automated backtesting
- GPU-accelerated parameter grid search (Numba/CUDA)
- CSV export for RAG integration
- Parameter optimization for iron condors

Runs autonomously on weekends via GitHub Actions to:
1. Test iron condor parameters (delta, DTE, width) via GPU grid search
2. Validate with Perplexity research for market context
3. Analyze event-based performance (FOMC, earnings, VIX)
4. Feed results to RAG for continuous learning
5. Update optimal parameters in system_state.json
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
RESEARCH_DIR = DATA_DIR / "research"
BACKTEST_DIR = RESEARCH_DIR / "backtests"
RAG_DIR = PROJECT_DIR / "rag_knowledge" / "backtests"

# Ensure directories exist
RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
RAG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BacktestQuery:
    """A backtest research query for Perplexity."""

    query: str
    parameter_type: str  # 'delta', 'dte', 'width', 'event', 'vix'
    expected_metrics: list[str] = field(
        default_factory=lambda: [
            "win_rate",
            "avg_profit",
            "max_drawdown",
            "profit_factor",
        ]
    )
    priority: int = 1  # 1=high, 2=medium, 3=low


@dataclass
class BacktestResult:
    """Result from a Perplexity backtest research query."""

    query: str
    parameter_type: str
    findings: str
    metrics: dict[str, float]
    optimal_value: str | None
    confidence: float
    sources: list[str]
    timestamp: datetime
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "parameter_type": self.parameter_type,
            "findings": self.findings,
            "metrics": self.metrics,
            "optimal_value": self.optimal_value,
            "confidence": self.confidence,
            "sources": self.sources,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_rag_lesson(self) -> str:
        """Convert to RAG-compatible lesson format."""
        return f"""# Backtest Research: {self.parameter_type.upper()}

**Query**: {self.query}

**Findings**: {self.findings}

**Optimal Value**: {self.optimal_value or "N/A"}

**Metrics**:
{chr(10).join(f"- {k}: {v}" for k, v in self.metrics.items())}

**Confidence**: {self.confidence:.0%}

**Sources**: {", ".join(self.sources[:3]) if self.sources else "Perplexity Deep Research"}

**Date**: {self.timestamp.strftime("%Y-%m-%d")}
"""


class PerplexityResearchAgent:
    """
    Autonomous research agent using Perplexity Deep Research.

    Capabilities:
    - Natural language backtesting queries
    - Parameter optimization research
    - Event-based performance analysis
    - CSV export for data analysis
    - RAG integration for continuous learning
    """

    # Standard backtest queries for iron condors
    IRON_CONDOR_QUERIES: list[BacktestQuery] = [
        # Delta optimization
        BacktestQuery(
            query="Historical backtest of SPY iron condors: compare 10-delta vs 15-delta vs 20-delta short strikes. What win rate and profit factor does each achieve over the past 5 years?",
            parameter_type="delta",
            priority=1,
        ),
        # DTE optimization
        BacktestQuery(
            query="SPY iron condor backtest: compare 30 DTE vs 45 DTE vs 60 DTE expiration. Which DTE has the best risk-adjusted returns and win rate?",
            parameter_type="dte",
            priority=1,
        ),
        # Width optimization
        BacktestQuery(
            query="SPY iron condor wing width analysis: $5 wide vs $10 wide spreads. How does wing width affect win rate and maximum drawdown?",
            parameter_type="width",
            priority=2,
        ),
        # FOMC event analysis
        BacktestQuery(
            query="Iron condor performance around FOMC meetings: should you avoid trading 3 days before Fed announcements? Historical win rate comparison.",
            parameter_type="event",
            priority=1,
        ),
        # Earnings event analysis
        BacktestQuery(
            query="SPY iron condor performance during earnings season vs non-earnings periods. Is there a statistically significant difference in win rates?",
            parameter_type="event",
            priority=2,
        ),
        # VIX regime analysis
        BacktestQuery(
            query="Iron condor performance by VIX level: VIX under 15 vs 15-20 vs 20-25 vs above 25. Which VIX regime has the best iron condor win rate?",
            parameter_type="vix",
            priority=1,
        ),
        # Exit timing
        BacktestQuery(
            query="Iron condor exit strategy backtest: close at 50% profit vs 75% profit vs hold to expiration. Which exit strategy maximizes risk-adjusted returns?",
            parameter_type="exit",
            priority=1,
        ),
        # Management rules
        BacktestQuery(
            query="Iron condor adjustment strategies: when one side is tested, does rolling the untested side closer improve overall profitability?",
            parameter_type="management",
            priority=2,
        ),
    ]

    def __init__(self):
        self.api_key = os.environ.get("PERPLEXITY_API_KEY", "")
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.model = "sonar-pro"  # Deep research model
        self.results: list[BacktestResult] = []
        self.cache_file = RESEARCH_DIR / "perplexity_cache.json"
        self.cache_ttl_days = int(os.getenv("PERPLEXITY_CACHE_TTL_DAYS", "14"))

    def _load_cache(self) -> dict[str, Any]:
        if not self.cache_file.exists():
            return {}
        try:
            return json.loads(self.cache_file.read_text())
        except json.JSONDecodeError:
            return {}

    def _save_cache(self, cache: dict[str, Any]) -> None:
        self.cache_file.write_text(json.dumps(cache, indent=2))

    def _cache_key(self, query: str) -> str:
        payload = f"{self.model}:{query}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _get_cached_response(self, query: str) -> dict[str, Any] | None:
        cache = self._load_cache()
        key = self._cache_key(query)
        entry = cache.get(key)
        if not entry:
            return None

        try:
            timestamp = datetime.fromisoformat(entry["timestamp"])
        except (KeyError, ValueError):
            return None

        if datetime.now(timezone.utc) - timestamp > timedelta(days=self.cache_ttl_days):
            return None

        response = entry.get("response")
        if not response:
            return None
        response = dict(response)
        response["cached"] = True
        response["cache_timestamp"] = entry["timestamp"]
        return response

    def _store_cache(self, query: str, response: dict[str, Any]) -> None:
        cache = self._load_cache()
        key = self._cache_key(query)
        cache[key] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response": response,
        }
        self._save_cache(cache)

    async def research(self, query: str, extract_metrics: bool = True) -> dict[str, Any]:
        """
        Execute a deep research query via Perplexity.

        Returns structured research results with metrics extraction.
        """
        cached = self._get_cached_response(query)
        if cached:
            if extract_metrics and "metrics" not in cached:
                cached["metrics"] = self._extract_metrics(cached.get("answer", ""))
            return cached

        if not self.api_key:
            return {"error": "PERPLEXITY_API_KEY not configured", "results": None}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # System prompt for structured backtest analysis
        system_prompt = """You are a quantitative options research analyst specializing in iron condor strategies on SPY.

When analyzing backtests, ALWAYS provide:
1. Win rate (as percentage)
2. Average profit per trade (as dollar amount or percentage)
3. Maximum drawdown (as percentage)
4. Profit factor (ratio of gross profits to gross losses)
5. Sample size (number of trades analyzed)

Format numbers clearly. Cite specific studies, papers, or data sources when available.
If exact numbers aren't available, provide reasonable estimates with confidence levels."""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            "search_recency_filter": "year",  # Recent data preferred
            "return_citations": True,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=60.0,  # Deep research takes longer
                )
                response.raise_for_status()
                data = response.json()

                answer = data["choices"][0]["message"]["content"]
                citations = data.get("citations", [])

                result = {
                    "answer": answer,
                    "citations": citations,
                    "model": data.get("model", self.model),
                }

                # Extract metrics if requested
                if extract_metrics:
                    result["metrics"] = self._extract_metrics(answer)

                self._store_cache(query, result)
                return result

        except httpx.HTTPError as e:
            return {"error": str(e), "results": None}

    def _extract_metrics(self, text: str) -> dict[str, float | None]:
        """Extract quantitative metrics from research response."""
        import re

        metrics = {
            "win_rate": None,
            "avg_profit": None,
            "max_drawdown": None,
            "profit_factor": None,
            "sample_size": None,
        }

        # Win rate patterns (e.g., "85% win rate", "win rate of 80%")
        win_patterns = [
            r"(\d{1,2}(?:\.\d+)?)\s*%\s*win\s*rate",
            r"win\s*rate\s*(?:of\s*)?(\d{1,2}(?:\.\d+)?)\s*%",
            r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:probability|success)",
        ]
        for pattern in win_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metrics["win_rate"] = float(match.group(1))
                break

        # Profit factor patterns (e.g., "profit factor of 1.5", "1.8 profit factor")
        pf_patterns = [
            r"profit\s*factor\s*(?:of\s*)?(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*profit\s*factor",
        ]
        for pattern in pf_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metrics["profit_factor"] = float(match.group(1))
                break

        # Max drawdown patterns
        dd_patterns = [
            r"(?:max(?:imum)?\s*)?drawdown\s*(?:of\s*)?(\d{1,2}(?:\.\d+)?)\s*%",
            r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:max(?:imum)?\s*)?drawdown",
        ]
        for pattern in dd_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metrics["max_drawdown"] = float(match.group(1))
                break

        # Sample size patterns
        sample_patterns = [
            r"(\d{2,5})\s*trades",
            r"sample\s*(?:size\s*)?(?:of\s*)?(\d{2,5})",
            r"(\d{2,5})\s*(?:iron\s*)?condors",
        ]
        for pattern in sample_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metrics["sample_size"] = int(match.group(1))
                break

        return metrics

    async def run_backtest_suite(
        self,
        queries: list[BacktestQuery] | None = None,
        priority_filter: int | None = None,
    ) -> list[BacktestResult]:
        """
        Run a suite of backtest queries.

        Args:
            queries: Custom queries or use default IRON_CONDOR_QUERIES
            priority_filter: Only run queries with priority <= this value

        Returns:
            List of BacktestResult objects
        """
        if queries is None:
            queries = self.IRON_CONDOR_QUERIES

        if priority_filter is not None:
            queries = [q for q in queries if q.priority <= priority_filter]

        results = []
        for query in queries:
            print(f"Researching: {query.parameter_type}...")

            response = await self.research(query.query)

            if response.get("error"):
                print(f"  Error: {response['error']}")
                continue

            # Parse response into BacktestResult
            result = BacktestResult(
                query=query.query,
                parameter_type=query.parameter_type,
                findings=response.get("answer", "")[:500],  # Truncate for summary
                metrics=response.get("metrics", {}),
                optimal_value=self._extract_optimal_value(
                    response.get("answer", ""), query.parameter_type
                ),
                confidence=self._calculate_confidence(response),
                sources=response.get("citations", [])[:5],
                timestamp=datetime.now(timezone.utc),
                raw_response=response.get("answer", ""),
            )

            results.append(result)
            self.results.append(result)

            # Rate limit - don't hammer API
            await asyncio.sleep(2)

        return results

    def _extract_optimal_value(self, text: str, param_type: str) -> str | None:
        """Extract the recommended optimal value from research."""
        import re

        text_lower = text.lower()

        if param_type == "delta":
            # Look for delta recommendations
            patterns = [
                r"(\d{1,2})\s*(?:-)?delta\s*(?:is\s*)?(?:optimal|best|recommended)",
                r"(?:optimal|best|recommended)\s*(?:is\s*)?(\d{1,2})\s*(?:-)?delta",
            ]
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return f"{match.group(1)}-delta"

        elif param_type == "dte":
            patterns = [
                r"(\d{2,3})\s*(?:dte|days?\s*to\s*expir)",
                r"(?:optimal|best)\s*(?:is\s*)?(\d{2,3})\s*(?:dte|days)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return f"{match.group(1)} DTE"

        elif param_type == "width":
            patterns = [
                r"\$(\d{1,2})\s*(?:wide|width)",
                r"(\d{1,2})\s*(?:point|dollar)\s*(?:wide|width)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return f"${match.group(1)} wide"

        elif param_type == "vix":
            if "under 15" in text_lower or "below 15" in text_lower:
                return "VIX < 15"
            elif "15-20" in text_lower or "15 to 20" in text_lower:
                return "VIX 15-20"
            elif "20-25" in text_lower:
                return "VIX 20-25"

        elif param_type == "exit":
            if "50%" in text_lower and ("profit" in text_lower or "max" in text_lower):
                return "50% of max profit"
            elif "75%" in text_lower:
                return "75% of max profit"

        return None

    def _calculate_confidence(self, response: dict) -> float:
        """Calculate confidence score based on response quality."""
        confidence = 0.5  # Base confidence

        # More citations = higher confidence
        citations = response.get("citations", [])
        if len(citations) >= 3:
            confidence += 0.2
        elif len(citations) >= 1:
            confidence += 0.1

        # Metrics extracted = higher confidence
        metrics = response.get("metrics", {})
        non_null_metrics = sum(1 for v in metrics.values() if v is not None)
        confidence += non_null_metrics * 0.05

        # Cap at 0.95
        return min(confidence, 0.95)

    def export_to_csv(self, results: list[BacktestResult] | None = None) -> Path:
        """Export results to CSV for analysis."""
        if results is None:
            results = self.results

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = BACKTEST_DIR / f"backtest_results_{timestamp}.csv"

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "parameter_type",
                    "query",
                    "optimal_value",
                    "win_rate",
                    "profit_factor",
                    "max_drawdown",
                    "sample_size",
                    "confidence",
                    "findings",
                ],
            )
            writer.writeheader()

            for result in results:
                writer.writerow(
                    {
                        "timestamp": result.timestamp.isoformat(),
                        "parameter_type": result.parameter_type,
                        "query": result.query[:100],
                        "optimal_value": result.optimal_value or "",
                        "win_rate": result.metrics.get("win_rate", ""),
                        "profit_factor": result.metrics.get("profit_factor", ""),
                        "max_drawdown": result.metrics.get("max_drawdown", ""),
                        "sample_size": result.metrics.get("sample_size", ""),
                        "confidence": result.confidence,
                        "findings": result.findings[:200],
                    }
                )

        print(f"Exported {len(results)} results to {csv_path}")
        return csv_path

    def export_to_rag(self, results: list[BacktestResult] | None = None) -> list[Path]:
        """Export results as RAG lessons for continuous learning."""
        if results is None:
            results = self.results

        paths = []
        timestamp = datetime.now().strftime("%Y%m%d")

        for result in results:
            if result.confidence < 0.5:
                continue  # Skip low-confidence results

            filename = f"backtest_{result.parameter_type}_{timestamp}.md"
            rag_path = RAG_DIR / filename

            rag_path.write_text(result.to_rag_lesson())
            paths.append(rag_path)
            print(f"Created RAG lesson: {rag_path.name}")

        return paths

    def update_system_state(self, results: list[BacktestResult] | None = None) -> None:
        """Update system_state.json with optimal parameters."""
        if results is None:
            results = self.results

        state_file = DATA_DIR / "system_state.json"
        if not state_file.exists():
            print("system_state.json not found")
            return

        state = json.loads(state_file.read_text())

        # Initialize research section
        if "research_insights" not in state:
            state["research_insights"] = {}

        insights = state["research_insights"]
        insights["last_updated"] = datetime.now(timezone.utc).isoformat()
        insights["parameters"] = insights.get("parameters", {})

        # Update parameters from high-confidence results
        for result in results:
            if result.confidence >= 0.6 and result.optimal_value:
                insights["parameters"][result.parameter_type] = {
                    "optimal_value": result.optimal_value,
                    "confidence": result.confidence,
                    "win_rate": result.metrics.get("win_rate"),
                    "profit_factor": result.metrics.get("profit_factor"),
                    "updated_at": result.timestamp.isoformat(),
                }

        state_file.write_text(json.dumps(state, indent=2))
        print(f"Updated system_state.json with {len(results)} research insights")


async def run_gpu_backtest() -> dict[str, Any]:
    """
    Run GPU-accelerated parameter grid search.

    Uses Numba/CUDA for parallel backtesting across 360+ parameter combinations.
    Falls back to NumPy if CUDA unavailable.
    """
    try:
        from src.compute.gpu_backtest import GPUBacktestEngine

        print("=== Starting GPU-Accelerated Backtest ===")
        engine = GPUBacktestEngine()

        # Load historical SPY data for backtesting
        engine.load_price_data(ticker="SPY", years=5)

        # Run grid search across all parameter combinations
        print("Running parameter grid search...")
        grid_result = engine.grid_search(n_trades_per_sim=252)

        # Get best parameters from result
        best_params = grid_result.best_params

        # Run Monte Carlo VaR on best params
        print("Running Monte Carlo VaR simulation...")
        var_result = engine.monte_carlo_var(best_params, n_scenarios=1000, confidence=[0.95, 0.99])

        return {
            "status": "completed",
            "compute": "GPU" if grid_result.gpu_accelerated else "CPU",
            "parameters_tested": grid_result.total_combinations,
            "best_params": {
                "delta": best_params.delta,
                "dte": best_params.dte,
                "width": best_params.width,
                "exit_pct": best_params.exit_profit_pct,
                "stop_pct": best_params.stop_loss_pct,
            },
            "best_win_rate": grid_result.best_win_rate * 100,  # Convert to percentage
            "best_sharpe": grid_result.best_sharpe,
            "var_95": var_result.get("var_95"),
            "var_99": var_result.get("var_99"),
            "execution_time_ms": grid_result.execution_time_ms,
        }

    except ImportError as e:
        print(f"GPU backtest not available: {e}")
        return {"status": "skipped", "reason": str(e)}
    except Exception as e:
        import traceback

        print(f"GPU backtest error: {e}")
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


async def run_weekend_research() -> dict[str, Any]:
    """
    Autonomous weekend research job.

    Called by GitHub Actions on Saturday mornings.
    Combines GPU-accelerated backtesting with Perplexity research.
    """
    print("=" * 60)
    print("AUTONOMOUS WEEKEND RESEARCH")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    results_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gpu_backtest": None,
        "perplexity_research": None,
        "combined_insights": [],
    }

    # Phase 1: GPU-accelerated parameter optimization
    print("\n[Phase 1] GPU-Accelerated Backtesting")
    print("-" * 40)
    gpu_results = await run_gpu_backtest()
    results_summary["gpu_backtest"] = gpu_results

    if gpu_results.get("status") == "completed":
        best = gpu_results.get("best_params", {})
        print(f"✅ GPU Backtest Complete ({gpu_results.get('compute', 'CPU')} mode)")
        print(
            f"   Best: {best.get('delta')}-delta, {best.get('dte')} DTE, ${best.get('width')} wide"
        )
        print(f"   Win Rate: {gpu_results.get('best_win_rate', 0):.1f}%")
        print(f"   VaR 95%: ${gpu_results.get('var_95', 0):.2f}")

        # Add GPU findings to insights
        results_summary["combined_insights"].append(
            {
                "source": "gpu_backtest",
                "parameter": "optimal_setup",
                "value": f"{best.get('delta')}-delta, {best.get('dte')} DTE, ${best.get('width')} wide",
                "confidence": 0.85,  # High confidence from actual simulation
                "win_rate": gpu_results.get("best_win_rate"),
            }
        )

    # Phase 2: Perplexity research for market context
    print("\n[Phase 2] Perplexity Deep Research")
    print("-" * 40)

    agent = PerplexityResearchAgent()

    if not agent.api_key:
        print("⚠️  PERPLEXITY_API_KEY not configured - skipping research phase")
        results_summary["perplexity_research"] = {
            "status": "skipped",
            "reason": "API key not configured",
        }
    else:
        # Run high-priority queries
        results = await agent.run_backtest_suite(priority_filter=1)

        # Export results
        csv_path = agent.export_to_csv(results)
        rag_paths = agent.export_to_rag(results)

        results_summary["perplexity_research"] = {
            "status": "completed",
            "queries_run": len(results),
            "high_confidence_results": sum(1 for r in results if r.confidence >= 0.7),
            "csv_export": str(csv_path),
            "rag_lessons_created": len(rag_paths),
        }

        # Add Perplexity findings to insights
        for r in results:
            if r.optimal_value and r.confidence >= 0.6:
                results_summary["combined_insights"].append(
                    {
                        "source": "perplexity",
                        "parameter": r.parameter_type,
                        "value": r.optimal_value,
                        "confidence": r.confidence,
                        "win_rate": r.metrics.get("win_rate"),
                    }
                )

    # Phase 3: Update system state with combined insights
    print("\n[Phase 3] Updating System State")
    print("-" * 40)

    state_file = DATA_DIR / "system_state.json"
    if state_file.exists():
        state = json.loads(state_file.read_text())

        # Initialize research section
        if "research_insights" not in state:
            state["research_insights"] = {}

        insights = state["research_insights"]
        insights["last_updated"] = datetime.now(timezone.utc).isoformat()
        insights["gpu_backtest"] = gpu_results if gpu_results.get("status") == "completed" else None
        insights["combined_insights"] = results_summary["combined_insights"]

        # Update optimal parameters from GPU results (highest confidence)
        if gpu_results.get("status") == "completed":
            best = gpu_results.get("best_params", {})
            insights["recommended_params"] = {
                "delta": best.get("delta", 15),
                "dte": best.get("dte", 30),
                "width": best.get("width", 5),
                "exit_pct": best.get("exit_pct", 50),
                "stop_pct": best.get("stop_pct", 200),
                "source": "gpu_grid_search",
                "win_rate": gpu_results.get("best_win_rate"),
                "var_95": gpu_results.get("var_95"),
            }

        state_file.write_text(json.dumps(state, indent=2))
        print("✅ system_state.json updated")

    # Save full summary
    summary_file = RESEARCH_DIR / "latest_research_summary.json"
    summary_file.write_text(json.dumps(results_summary, indent=2))
    print(f"✅ Summary saved to {summary_file.name}")

    # Final report
    print("\n" + "=" * 60)
    print("RESEARCH COMPLETE")
    print("=" * 60)
    print(f"GPU Backtest: {gpu_results.get('status', 'N/A')}")
    print(
        f"Perplexity: {results_summary['perplexity_research'].get('status', 'N/A') if results_summary['perplexity_research'] else 'N/A'}"
    )
    print(f"Combined Insights: {len(results_summary['combined_insights'])}")

    if gpu_results.get("status") == "completed":
        best = gpu_results.get("best_params", {})
        print("\n🎯 RECOMMENDED SETUP:")
        print(f"   Delta: {best.get('delta')}")
        print(f"   DTE: {best.get('dte')} days")
        print(f"   Width: ${best.get('width')}")
        print(f"   Exit: {best.get('exit_pct')}% profit")
        print(f"   Stop: {best.get('stop_pct')}% loss")
        print(f"   Expected Win Rate: {gpu_results.get('best_win_rate', 0):.1f}%")

    return results_summary


async def get_research_signal() -> dict[str, Any]:
    """
    Get trading signal based on latest research insights.

    For swarm integration.
    """
    state_file = DATA_DIR / "system_state.json"

    if not state_file.exists():
        return {
            "signal": 0.5,
            "confidence": 0.3,
            "data": {"error": "No research data available"},
        }

    state = json.loads(state_file.read_text())
    insights = state.get("research_insights", {})
    params = insights.get("parameters", {})

    if not params:
        return {
            "signal": 0.5,
            "confidence": 0.3,
            "data": {"error": "No parameter insights available"},
        }

    # Calculate signal based on research confidence
    avg_confidence = sum(p.get("confidence", 0.5) for p in params.values()) / max(len(params), 1)

    # Higher confidence in research = more favorable signal
    signal = 0.5 + (avg_confidence - 0.5) * 0.4

    return {
        "signal": round(signal, 3),
        "confidence": round(avg_confidence, 3),
        "data": {
            "source": "perplexity_deep_research",
            "parameters_optimized": list(params.keys()),
            "last_updated": insights.get("last_updated", "unknown"),
            "recommendation": "FAVORABLE" if avg_confidence >= 0.7 else "NEUTRAL",
        },
    }


if __name__ == "__main__":

    async def demo():
        agent = PerplexityResearchAgent()

        if not agent.api_key:
            print("PERPLEXITY_API_KEY not set - demo mode")
            print("\nTo enable research, set PERPLEXITY_API_KEY environment variable")
            return

        # Run a single test query
        result = await agent.research(
            "What is the historical win rate for SPY iron condors with 15-delta short strikes?"
        )

        print("=== Research Result ===")
        print(f"Answer: {result.get('answer', 'N/A')[:300]}...")
        print(f"Metrics: {result.get('metrics', {})}")
        print(f"Citations: {len(result.get('citations', []))}")

    asyncio.run(demo())
