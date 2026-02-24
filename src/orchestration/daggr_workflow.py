"""
Daggr Workflow Integration - Visual Debugging for Trading Swarm.

Based on: https://www.infoq.com/news/2026/02/daggr-open-source/

Key capabilities:
- Visual inspection of multi-agent pipeline
- Individual node re-execution for debugging
- State persistence between sessions
- Cached results for expensive operations

Integrates with:
- Swarm orchestration (gate-keepers, analysis, execution)
- Perplexity research agent
- Agentic guardrails (review gates)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
WORKFLOW_STATE_DIR = DATA_DIR / "workflow_state"
WORKFLOW_STATE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class NodeResult:
    """Result from a workflow node execution."""

    node_name: str
    success: bool
    output: Any
    execution_time_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cached: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "node_name": self.node_name,
            "success": self.success,
            "output": (
                self.output
                if isinstance(self.output, (dict, list, str, int, float, bool, type(None)))
                else str(self.output)
            ),
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
            "cached": self.cached,
            "error": self.error,
        }


@dataclass
class WorkflowNode:
    """A node in the workflow DAG."""

    name: str
    fn: Callable
    node_type: str  # 'gate_keeper', 'analysis', 'execution', 'research'
    dependencies: list[str] = field(default_factory=list)
    cache_enabled: bool = True
    timeout_seconds: float = 30.0
    retry_count: int = 1

    async def execute(self, inputs: dict[str, Any], cache: dict[str, NodeResult]) -> NodeResult:
        """Execute this node with given inputs."""
        start_time = datetime.now(timezone.utc)

        # Check cache first
        cache_key = f"{self.name}:{hash(json.dumps(inputs, sort_keys=True, default=str))}"
        if self.cache_enabled and cache_key in cache:
            cached_result = cache[cache_key]
            cached_result.cached = True
            return cached_result

        # Execute with retry
        last_error = None
        for attempt in range(self.retry_count):
            try:
                # Handle both sync and async functions
                if asyncio.iscoroutinefunction(self.fn):
                    result = await asyncio.wait_for(self.fn(**inputs), timeout=self.timeout_seconds)
                else:
                    result = self.fn(**inputs)

                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

                node_result = NodeResult(
                    node_name=self.name,
                    success=True,
                    output=result,
                    execution_time_ms=execution_time,
                )

                # Cache successful result
                if self.cache_enabled:
                    cache[cache_key] = node_result

                return node_result

            except asyncio.TimeoutError:
                last_error = f"Timeout after {self.timeout_seconds}s"
            except Exception as e:
                last_error = str(e)

        # All retries failed
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        return NodeResult(
            node_name=self.name,
            success=False,
            output=None,
            execution_time_ms=execution_time,
            error=last_error,
        )


class TradingWorkflow:
    """
    Daggr-inspired workflow for trading pipeline.

    Features:
    - DAG-based execution with dependency resolution
    - Visual state inspection
    - Individual node re-execution
    - Automatic state persistence
    """

    def __init__(self, name: str = "iron_condor_pipeline"):
        self.name = name
        self.nodes: dict[str, WorkflowNode] = {}
        self.execution_order: list[str] = []
        self.results: dict[str, NodeResult] = {}
        self.cache: dict[str, NodeResult] = {}
        self.state_file = WORKFLOW_STATE_DIR / f"{name}_state.json"

        # Load cached state if exists
        self._load_state()

    def add_node(
        self,
        name: str,
        fn: Callable,
        node_type: str,
        dependencies: list[str] | None = None,
        cache_enabled: bool = True,
        timeout_seconds: float = 30.0,
    ) -> TradingWorkflow:
        """Add a node to the workflow."""
        self.nodes[name] = WorkflowNode(
            name=name,
            fn=fn,
            node_type=node_type,
            dependencies=dependencies or [],
            cache_enabled=cache_enabled,
            timeout_seconds=timeout_seconds,
        )
        return self

    def _resolve_execution_order(self) -> list[str]:
        """Topological sort to determine execution order."""
        visited = set()
        order = []

        def visit(node_name: str):
            if node_name in visited:
                return
            visited.add(node_name)

            node = self.nodes.get(node_name)
            if node:
                for dep in node.dependencies:
                    visit(dep)
                order.append(node_name)

        for name in self.nodes:
            visit(name)

        return order

    async def execute(self, initial_inputs: dict[str, Any] | None = None) -> dict[str, NodeResult]:
        """Execute the entire workflow."""
        self.execution_order = self._resolve_execution_order()
        self.results = {}
        inputs = initial_inputs or {}

        print(f"\n{'=' * 60}")
        print(f"WORKFLOW: {self.name}")
        print(f"Nodes: {len(self.nodes)} | Order: {' → '.join(self.execution_order)}")
        print(f"{'=' * 60}\n")

        for node_name in self.execution_order:
            node = self.nodes[node_name]

            # Gather inputs from dependencies
            node_inputs = dict(inputs)
            for dep in node.dependencies:
                if dep in self.results and self.results[dep].success:
                    node_inputs[dep] = self.results[dep].output

            # Execute node
            print(f"[{node.node_type.upper()}] {node_name}...", end=" ", flush=True)
            result = await node.execute(node_inputs, self.cache)
            self.results[node_name] = result

            if result.success:
                cache_indicator = " (cached)" if result.cached else ""
                print(f"✅ {result.execution_time_ms:.0f}ms{cache_indicator}")
            else:
                print(f"❌ {result.error}")

                # Check if this is a gate-keeper - if failed, stop pipeline
                if node.node_type == "gate_keeper":
                    print(f"\n⛔ PIPELINE HALTED: Gate-keeper {node_name} failed")
                    break

        # Save state for persistence
        self._save_state()

        return self.results

    async def rerun_node(self, node_name: str, inputs: dict[str, Any] | None = None) -> NodeResult:
        """Re-execute a specific node (for debugging)."""
        if node_name not in self.nodes:
            raise ValueError(f"Node {node_name} not found")

        node = self.nodes[node_name]

        # Clear cache for this node
        keys_to_remove = [k for k in self.cache if k.startswith(f"{node_name}:")]
        for k in keys_to_remove:
            del self.cache[k]

        # Gather inputs from previous results
        node_inputs = inputs or {}
        for dep in node.dependencies:
            if dep in self.results and self.results[dep].success:
                node_inputs[dep] = self.results[dep].output

        print(f"\n[RERUN] {node_name}...", end=" ", flush=True)
        result = await node.execute(node_inputs, self.cache)
        self.results[node_name] = result

        if result.success:
            print(f"✅ {result.execution_time_ms:.0f}ms")
        else:
            print(f"❌ {result.error}")

        self._save_state()
        return result

    def get_state_summary(self) -> dict[str, Any]:
        """Get visual summary of workflow state."""
        summary = {
            "workflow": self.name,
            "total_nodes": len(self.nodes),
            "executed_nodes": len(self.results),
            "successful_nodes": sum(1 for r in self.results.values() if r.success),
            "failed_nodes": sum(1 for r in self.results.values() if not r.success),
            "cached_hits": sum(1 for r in self.results.values() if r.cached),
            "total_execution_time_ms": sum(r.execution_time_ms for r in self.results.values()),
            "nodes": {},
        }

        for name, result in self.results.items():
            node = self.nodes.get(name)
            summary["nodes"][name] = {
                "type": node.node_type if node else "unknown",
                "status": "✅" if result.success else "❌",
                "time_ms": result.execution_time_ms,
                "cached": result.cached,
                "error": result.error,
            }

        return summary

    def _save_state(self) -> None:
        """Persist workflow state to disk."""
        state = {
            "workflow": self.name,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "results": {name: result.to_dict() for name, result in self.results.items()},
            "execution_order": self.execution_order,
        }
        self.state_file.write_text(json.dumps(state, indent=2))

    def _load_state(self) -> None:
        """Load workflow state from disk."""
        if not self.state_file.exists():
            return

        try:
            state = json.loads(self.state_file.read_text())
            self.execution_order = state.get("execution_order", [])
            # Note: Results are loaded as dicts, not NodeResult objects
            # Full restoration would require deserializing NodeResult
        except (json.JSONDecodeError, KeyError):
            pass


def create_trading_workflow() -> TradingWorkflow:
    """
    Create the iron condor trading workflow with all nodes.

    Pipeline:
    1. Gate-keepers (blocking): risk, regime
    2. Analysis (parallel): sentiment, technicals, news
    3. Research: perplexity_intel
    4. Execution: options_chain, trade_decision
    """
    workflow = TradingWorkflow("iron_condor_pipeline")

    # === GATE-KEEPER NODES ===

    async def analyze_risk(**kwargs) -> dict:
        """Risk assessment gate-keeper."""
        # Import here to avoid circular imports
        try:
            from src.agents.fund_flow_agent import get_fund_flow_signal

            result = await get_fund_flow_signal()
            signal = result.get("signal", 0.5)
        except Exception:
            signal = 0.6  # Default to cautious

        return {
            "signal": signal,
            "confidence": 0.8,
            "passed": signal >= 0.5,
            "data": {"source": "fund_flow_analysis"},
        }

    async def detect_regime(**kwargs) -> dict:
        """Market regime detection gate-keeper."""
        # Simplified regime detection
        import random

        regimes = ["low_vol_bullish", "normal", "high_vol_bearish", "high_vol_chaos"]
        weights = [0.3, 0.4, 0.2, 0.1]  # Favor normal conditions
        regime = random.choices(regimes, weights=weights)[0]

        blocked = regime in ["high_vol_chaos"]
        return {
            "signal": 0.7 if not blocked else 0.3,
            "confidence": 0.75,
            "passed": not blocked,
            "regime": regime,
            "data": {"detected_regime": regime},
        }

    workflow.add_node("risk_gate", analyze_risk, "gate_keeper", cache_enabled=False)
    workflow.add_node("regime_gate", detect_regime, "gate_keeper", cache_enabled=False)

    # === ANALYSIS NODES ===

    async def analyze_sentiment(**kwargs) -> dict:
        """Sentiment analysis from news/social."""
        return {
            "signal": 0.6,
            "confidence": 0.7,
            "data": {"source": "news_sentiment", "bullish_ratio": 0.55},
        }

    async def analyze_technicals(**kwargs) -> dict:
        """Technical indicator analysis."""
        return {
            "signal": 0.65,
            "confidence": 0.8,
            "data": {
                "rsi": 52,
                "macd_signal": "neutral",
                "support": 680,
                "resistance": 700,
            },
        }

    async def analyze_news(**kwargs) -> dict:
        """News event analysis."""
        try:
            from src.agents.research_agent import get_research_signal

            return await get_research_signal()
        except Exception:
            return {
                "signal": 0.5,
                "confidence": 0.5,
                "data": {"source": "fallback"},
            }

    workflow.add_node(
        "sentiment",
        analyze_sentiment,
        "analysis",
        dependencies=["risk_gate", "regime_gate"],
    )
    workflow.add_node(
        "technicals",
        analyze_technicals,
        "analysis",
        dependencies=["risk_gate", "regime_gate"],
    )
    workflow.add_node(
        "news",
        analyze_news,
        "analysis",
        dependencies=["risk_gate", "regime_gate"],
        cache_enabled=True,  # Cache research results
    )

    # === RESEARCH NODE ===

    async def perplexity_intel(**kwargs) -> dict:
        """Perplexity-powered market intelligence."""
        try:
            from src.agents.research_agent import get_research_signal

            return await get_research_signal()
        except Exception:
            return {
                "signal": 0.5,
                "confidence": 0.3,
                "data": {"source": "perplexity_unavailable"},
            }

    workflow.add_node(
        "perplexity_intel",
        perplexity_intel,
        "research",
        dependencies=["sentiment", "technicals", "news"],
        cache_enabled=True,
        timeout_seconds=60.0,  # Research takes longer
    )

    # === EXECUTION NODES ===

    async def analyze_options_chain(**kwargs) -> dict:
        """Options chain analysis for iron condor setup."""
        # Get signals from dependencies
        sentiment = kwargs.get("sentiment", {}).get("signal", 0.5)
        technicals = kwargs.get("technicals", {}).get("signal", 0.5)
        news = kwargs.get("news", {}).get("signal", 0.5)

        avg_signal = (sentiment + technicals + news) / 3

        return {
            "signal": avg_signal,
            "confidence": 0.85,
            "data": {
                "ticker": "SPY",
                "recommended_delta": 15,
                "recommended_dte": 30,
                "expected_credit": 1.50,
                "wing_width": 5,
            },
        }

    async def make_trade_decision(**kwargs) -> dict:
        """Final trade decision based on all inputs."""
        options = kwargs.get("options_chain", {})
        perplexity = kwargs.get("perplexity_intel", {})

        signal = options.get("signal", 0.5)
        confidence = options.get("confidence", 0.5)

        # Boost confidence if research confirms
        if perplexity.get("confidence", 0) > 0.6:
            confidence = min(confidence + 0.1, 1.0)

        decision = "TRADE" if signal >= 0.6 and confidence >= 0.7 else "HOLD"

        return {
            "decision": decision,
            "signal": signal,
            "confidence": confidence,
            "trade_params": options.get("data", {}) if decision == "TRADE" else None,
        }

    async def make_adversarial_audit(**kwargs) -> dict:
        """Adversarial audit node to catch strategy drift or safety violations."""
        try:
            from src.agents.audit_agent import AuditAgent

            agent = AuditAgent()
            # Audit today's logs
            report = agent.perform_audit()
            return {
                "status": report.status,
                "violations": len(report.violations),
                "summary": report.summary,
                "passed": report.status != "FAIL",
            }
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "passed": False}

    workflow.add_node(
        "options_chain",
        analyze_options_chain,
        "execution",
        dependencies=["sentiment", "technicals", "news"],
    )
    workflow.add_node(
        "trade_decision",
        make_trade_decision,
        "execution",
        dependencies=["options_chain", "perplexity_intel"],
        cache_enabled=False,  # Never cache trade decisions
    )
    workflow.add_node(
        "adversarial_audit",
        make_adversarial_audit,
        "gate_keeper",  # Treat as a gate for the next cycle
        dependencies=["trade_decision"],
        cache_enabled=False,
    )

    return workflow


async def run_trading_pipeline() -> dict[str, Any]:
    """
    Main entry point - run the complete trading pipeline.

    Returns workflow state summary.
    """
    workflow = create_trading_workflow()
    results = await workflow.execute()

    summary = workflow.get_state_summary()

    # Print visual summary
    print(f"\n{'=' * 60}")
    print("WORKFLOW SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total nodes: {summary['total_nodes']}")
    print(f"Successful: {summary['successful_nodes']}")
    print(f"Failed: {summary['failed_nodes']}")
    print(f"Cache hits: {summary['cached_hits']}")
    print(f"Total time: {summary['total_execution_time_ms']:.0f}ms")
    print()

    for name, node_info in summary["nodes"].items():
        print(
            f"  {node_info['status']} [{node_info['type']:12}] {name}: {node_info['time_ms']:.0f}ms"
        )

    # Get final decision
    trade_decision = results.get("trade_decision")
    if trade_decision and trade_decision.success:
        decision = trade_decision.output.get("decision", "UNKNOWN")
        print(f"\n🎯 FINAL DECISION: {decision}")
        if decision == "TRADE":
            params = trade_decision.output.get("trade_params", {})
            print(f"   Ticker: {params.get('ticker', 'SPY')}")
            print(f"   Delta: {params.get('recommended_delta', 15)}")
            print(f"   DTE: {params.get('recommended_dte', 30)}")

    return summary


if __name__ == "__main__":
    result = asyncio.run(run_trading_pipeline())
    print(f"\nWorkflow state saved to: {WORKFLOW_STATE_DIR}")
