"""
Teammate Swarm Orchestration - Multi-Agent Trading with Claude Code TeammateTool Pattern.

Implements specialized agents for trading decisions using the Pipeline pattern:
    MarketAnalysis -> RiskGate -> TradeDecision -> Execution

Agent Roles:
- Analyst: Market analysis (sentiment, technicals, news)
- RiskManager: Risk assessment gate-keeper (Phil Town Rule #1)
- Executor: Trade execution with timing optimization
- Monitor: Position monitoring and health checks
- Researcher: Perplexity-powered deep research
- Fixer: Self-healing watchdog (spawned on errors)

Patterns:
- Pipeline: Sequential processing with gate-keepers
- Parallel: Run independent agents simultaneously
- Watchdog: Self-healing via Fixer agent on errors

Integrates with:
- daggr_workflow.py for visual debugging
- agentic_guardrails.py for CEO approval gates
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
SWARM_STATE_DIR = DATA_DIR / "swarm_state"
SWARM_STATE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Specialized agent roles in the trading swarm."""

    ANALYST = "analyst"
    RISK_MANAGER = "risk_manager"
    EXECUTOR = "executor"
    MONITOR = "monitor"
    RESEARCHER = "researcher"
    FIXER = "fixer"  # Watchdog pattern - spawned on errors


class AgentStatus(Enum):
    """Agent execution status."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # Waiting on dependency


@dataclass
class AgentMessage:
    """Message passed between agents in the swarm."""

    sender: str
    receiver: str
    content: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    message_type: str = "data"  # 'data', 'signal', 'error', 'control'

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type,
        }


@dataclass
class AgentResult:
    """Result from agent execution."""

    agent_name: str
    role: AgentRole
    success: bool
    output: dict[str, Any]
    execution_time_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "role": self.role.value,
            "success": self.success,
            "output": self.output,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
        }


@dataclass
class SwarmAgent:
    """
    A specialized agent in the trading swarm.

    Each agent has:
    - Role-specific analysis function
    - Input/output message handling
    - Status tracking
    - Error recovery via Fixer pattern
    """

    name: str
    role: AgentRole
    fn: Callable
    dependencies: list[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    timeout_seconds: float = 30.0
    retry_count: int = 2
    is_gate_keeper: bool = False  # Gate-keepers can halt pipeline

    async def execute(self, inputs: dict[str, Any], messages: list[AgentMessage]) -> AgentResult:
        """Execute agent with inputs and accumulated messages."""
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        # Gather relevant messages for this agent
        agent_messages = [m for m in messages if m.receiver == self.name or m.receiver == "*"]

        # Merge message content into inputs
        for msg in agent_messages:
            inputs[f"msg_{msg.sender}"] = msg.content

        last_error = None
        for attempt in range(self.retry_count):
            try:
                # Execute agent function (sync or async)
                if asyncio.iscoroutinefunction(self.fn):
                    result = await asyncio.wait_for(self.fn(**inputs), timeout=self.timeout_seconds)
                else:
                    result = self.fn(**inputs)

                execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
                self.status = AgentStatus.COMPLETED

                return AgentResult(
                    agent_name=self.name,
                    role=self.role,
                    success=True,
                    output=result,
                    execution_time_ms=execution_time,
                )

            except TimeoutError:
                last_error = f"Timeout after {self.timeout_seconds}s"
            except Exception as e:
                last_error = str(e)
                logger.warning(f"{self.name} attempt {attempt + 1} failed: {e}")

        # All retries failed
        execution_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
        self.status = AgentStatus.FAILED

        return AgentResult(
            agent_name=self.name,
            role=self.role,
            success=False,
            output={},
            execution_time_ms=execution_time,
            error=last_error,
        )


class TradingSwarm:
    """
    Multi-agent swarm orchestrator for trading decisions.

    Implements:
    - Pipeline pattern: MarketAnalysis -> RiskGate -> TradeDecision -> Execution
    - Parallel execution: Independent agents run simultaneously
    - Message passing: Agents communicate via typed messages
    - Watchdog pattern: Fixer agent spawned on errors
    - State persistence: Swarm state saved to data/swarm_state/
    """

    def __init__(self, name: str = "iron_condor_swarm"):
        self.name = name
        self.agents: dict[str, SwarmAgent] = {}
        self.messages: list[AgentMessage] = []
        self.results: dict[str, AgentResult] = {}
        self.execution_order: list[str] = []
        self.state_file = SWARM_STATE_DIR / f"{name}_state.json"
        self.fixer_spawned = False

        # Initialize with core agents
        self._register_core_agents()
        self._load_state()

    def _register_core_agents(self) -> None:
        """Register the 5 core specialized agents + Fixer."""

        # === ANALYST: Market Analysis ===
        async def analyst_fn(**kwargs) -> dict[str, Any]:
            """Analyze market conditions from multiple sources."""
            sentiment = kwargs.get("sentiment", 0.5)
            technicals = kwargs.get("technicals", 0.5)
            news = kwargs.get("news", 0.5)

            # Weighted signal aggregation
            signal = (sentiment * 0.3) + (technicals * 0.4) + (news * 0.3)

            return {
                "signal": round(signal, 3),
                "confidence": 0.75,
                "analysis": {
                    "sentiment_weight": 0.3,
                    "technicals_weight": 0.4,
                    "news_weight": 0.3,
                    "inputs": {
                        "sentiment": sentiment,
                        "technicals": technicals,
                        "news": news,
                    },
                },
                "recommendation": (
                    "BULLISH" if signal > 0.6 else "NEUTRAL" if signal > 0.4 else "BEARISH"
                ),
            }

        self.add_agent(
            SwarmAgent(
                name="Analyst",
                role=AgentRole.ANALYST,
                fn=analyst_fn,
                dependencies=[],
            )
        )

        # === RISK_MANAGER: Risk Gate-Keeper ===
        async def risk_manager_fn(**kwargs) -> dict[str, Any]:
            """
            Risk assessment gate-keeper.

            Phil Town Rule #1: Don't lose money.
            Blocks trades that exceed risk limits.
            """
            position_size = kwargs.get("position_size", 0)
            portfolio_value = kwargs.get("portfolio_value", 100000)
            vix = kwargs.get("vix", 20)

            # 5% max position rule
            max_position = portfolio_value * 0.05
            position_approved = position_size <= max_position

            # VIX-based regime filter
            if vix > 30:
                regime_approved = False
                regime_note = "VIX > 30: High volatility regime - avoid trading"
            elif vix > 25:
                regime_approved = True
                regime_note = "VIX 25-30: Elevated volatility - reduce position size"
            else:
                regime_approved = True
                regime_note = "VIX < 25: Normal volatility"

            passed = position_approved and regime_approved

            return {
                "signal": 0.8 if passed else 0.2,
                "confidence": 0.9,
                "passed": passed,
                "risk_checks": {
                    "position_size_check": {
                        "passed": position_approved,
                        "max_allowed": max_position,
                        "requested": position_size,
                    },
                    "regime_check": {
                        "passed": regime_approved,
                        "vix": vix,
                        "note": regime_note,
                    },
                },
                "phil_town_rule_1": "COMPLIANT" if passed else "VIOLATION",
            }

        self.add_agent(
            SwarmAgent(
                name="RiskManager",
                role=AgentRole.RISK_MANAGER,
                fn=risk_manager_fn,
                dependencies=["Analyst"],
                is_gate_keeper=True,
            )
        )

        # === EXECUTOR: Trade Execution ===
        async def executor_fn(**kwargs) -> dict[str, Any]:
            """
            Execute trades with timing optimization.

            Only executes if RiskManager approves.
            """
            risk_passed = kwargs.get("msg_RiskManager", {}).get("passed", False)
            analyst_signal = kwargs.get("msg_Analyst", {}).get("signal", 0.5)

            if not risk_passed:
                return {
                    "action": "BLOCKED",
                    "reason": "Risk gate failed",
                    "signal": 0.0,
                    "confidence": 1.0,
                }

            # Trade decision based on analyst signal
            if analyst_signal >= 0.65:
                action = "OPEN_IRON_CONDOR"
                confidence = 0.85
            elif analyst_signal <= 0.35:
                action = "CLOSE_POSITIONS"
                confidence = 0.8
            else:
                action = "HOLD"
                confidence = 0.7

            return {
                "action": action,
                "signal": analyst_signal,
                "confidence": confidence,
                "timing": "IMMEDIATE" if action != "HOLD" else "N/A",
                "trade_params": (
                    {
                        "ticker": "SPY",
                        "delta": 15,
                        "dte": 30,
                        "width": 5,
                    }
                    if action == "OPEN_IRON_CONDOR"
                    else None
                ),
            }

        self.add_agent(
            SwarmAgent(
                name="Executor",
                role=AgentRole.EXECUTOR,
                fn=executor_fn,
                dependencies=["Analyst", "RiskManager"],
            )
        )

        # === MONITOR: Position Monitoring ===
        async def monitor_fn(**kwargs) -> dict[str, Any]:
            """Monitor open positions and portfolio health."""
            positions = kwargs.get("positions", [])
            portfolio_value = kwargs.get("portfolio_value", 100000)

            # Check position health
            unhealthy_positions = []
            for pos in positions:
                pnl_pct = pos.get("pnl_pct", 0)
                # Flag positions at stop-loss level (100% of credit)
                if pnl_pct <= -100:  # Lost more than credit received
                    unhealthy_positions.append(pos)

            health_score = 1.0 - (len(unhealthy_positions) / max(len(positions), 1))

            return {
                "signal": health_score,
                "confidence": 0.85,
                "positions_count": len(positions),
                "unhealthy_count": len(unhealthy_positions),
                "portfolio_value": portfolio_value,
                "alerts": [
                    f"Position {p.get('symbol', 'UNKNOWN')} at stop-loss"
                    for p in unhealthy_positions
                ],
                "recommendation": ("HEALTHY" if health_score >= 0.8 else "ATTENTION_NEEDED"),
            }

        self.add_agent(
            SwarmAgent(
                name="Monitor",
                role=AgentRole.MONITOR,
                fn=monitor_fn,
                dependencies=[],  # Independent - can run in parallel
            )
        )

        # === RESEARCHER: Deep Research ===
        async def researcher_fn(**kwargs) -> dict[str, Any]:
            """Perplexity-powered deep research for strategy optimization."""
            try:
                from src.agents.research_agent import get_research_signal

                return await get_research_signal()
            except Exception as e:
                logger.warning(f"Research agent fallback: {e}")
                return {
                    "signal": 0.5,
                    "confidence": 0.3,
                    "data": {"source": "fallback", "error": str(e)},
                }

        self.add_agent(
            SwarmAgent(
                name="Researcher",
                role=AgentRole.RESEARCHER,
                fn=researcher_fn,
                dependencies=[],  # Independent - can run in parallel
                timeout_seconds=60.0,  # Research takes longer
            )
        )

        # === FIXER: Self-Healing Watchdog ===
        async def fixer_fn(**kwargs) -> dict[str, Any]:
            """
            Watchdog agent - spawned when other agents fail.

            Attempts to diagnose and recover from errors.
            """
            failed_agent = kwargs.get("failed_agent", "unknown")
            error = kwargs.get("error", "unknown error")

            # Diagnostic checks
            diagnostics = {
                "api_connectivity": True,  # Would check actual APIs
                "data_freshness": True,  # Would check data timestamps
                "system_resources": True,  # Would check memory/CPU
            }

            # Recovery actions
            recovery_actions = []
            if "timeout" in error.lower():
                recovery_actions.append("increase_timeout")
            if "api" in error.lower() or "connection" in error.lower():
                recovery_actions.append("retry_with_backoff")
            if not recovery_actions:
                recovery_actions.append("log_and_alert")

            return {
                "signal": 0.5,
                "confidence": 0.6,
                "diagnosis": {
                    "failed_agent": failed_agent,
                    "error": error,
                    "diagnostics": diagnostics,
                },
                "recovery": {
                    "actions": recovery_actions,
                    "can_recover": len(recovery_actions) > 0,
                },
                "recommendation": "RETRY" if diagnostics.values() else "ALERT_CEO",
            }

        self.add_agent(
            SwarmAgent(
                name="Fixer",
                role=AgentRole.FIXER,
                fn=fixer_fn,
                dependencies=[],
            )
        )

    def add_agent(self, agent: SwarmAgent) -> TradingSwarm:
        """Add an agent to the swarm."""
        self.agents[agent.name] = agent
        return self

    def send_message(
        self,
        sender: str,
        receiver: str,
        content: dict[str, Any],
        message_type: str = "data",
    ) -> None:
        """Send a message between agents."""
        msg = AgentMessage(
            sender=sender,
            receiver=receiver,
            content=content,
            message_type=message_type,
        )
        self.messages.append(msg)
        logger.debug(f"Message: {sender} -> {receiver}: {message_type}")

    def _resolve_execution_order(self) -> list[list[str]]:
        """
        Resolve execution order with parallel groups.

        Returns list of groups - agents in same group can run in parallel.
        """
        groups: list[list[str]] = []

        # Build dependency levels
        def get_level(agent_name: str, memo: dict[str, int]) -> int:
            if agent_name in memo:
                return memo[agent_name]

            agent = self.agents.get(agent_name)
            if not agent or not agent.dependencies:
                memo[agent_name] = 0
                return 0

            max_dep_level = max(
                get_level(dep, memo) for dep in agent.dependencies if dep in self.agents
            )
            memo[agent_name] = max_dep_level + 1
            return memo[agent_name]

        levels: dict[str, int] = {}
        for name in self.agents:
            get_level(name, levels)

        # Group agents by level (same level = can run in parallel)
        max_level = max(levels.values()) if levels else 0
        for level in range(max_level + 1):
            group = [name for name, lvl in levels.items() if lvl == level]
            if group:
                # Exclude Fixer from normal execution (watchdog pattern)
                group = [n for n in group if n != "Fixer"]
                if group:
                    groups.append(group)

        return groups

    async def execute_pipeline(
        self, initial_inputs: dict[str, Any] | None = None
    ) -> dict[str, AgentResult]:
        """
        Execute the swarm pipeline.

        Pattern: MarketAnalysis -> RiskGate -> TradeDecision -> Execution

        Supports parallel execution of independent agents.
        """
        self.results = {}
        self.messages = []
        inputs = initial_inputs or {}

        execution_groups = self._resolve_execution_order()
        self.execution_order = [name for group in execution_groups for name in group]

        print(f"\n{'=' * 60}")
        print(f"SWARM: {self.name}")
        print(f"Agents: {len(self.agents)} | Groups: {len(execution_groups)}")
        print(f"{'=' * 60}\n")

        for group_idx, group in enumerate(execution_groups):
            print(f"[Group {group_idx + 1}] {' + '.join(group)}")

            # Run agents in parallel within group
            tasks = []
            for agent_name in group:
                agent = self.agents[agent_name]

                # Check dependencies
                deps_met = all(
                    dep in self.results and self.results[dep].success for dep in agent.dependencies
                )

                if not deps_met:
                    agent.status = AgentStatus.BLOCKED
                    print(f"  [{agent.role.value.upper()}] {agent_name}: BLOCKED (dependencies)")
                    continue

                # Pass outputs from dependencies as messages
                for dep in agent.dependencies:
                    if dep in self.results:
                        self.send_message(
                            sender=dep,
                            receiver=agent_name,
                            content=self.results[dep].output,
                        )

                tasks.append(self._execute_agent(agent, inputs))

            # Wait for all agents in group
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Agent execution error: {result}")
                        continue

                    self.results[result.agent_name] = result

                    # Print status
                    status = "OK" if result.success else "FAIL"
                    print(
                        f"  [{result.role.value.upper()}] {result.agent_name}: "
                        f"{status} ({result.execution_time_ms:.0f}ms)"
                    )

                    # Gate-keeper logic
                    if not result.success:
                        agent = self.agents.get(result.agent_name)
                        if agent and agent.is_gate_keeper:
                            print(f"\n  PIPELINE HALTED: Gate-keeper {result.agent_name} failed")
                            await self._spawn_fixer(result.agent_name, result.error)
                            break

                    # Check gate-keeper pass/fail
                    if result.success and result.output.get("passed") is False:
                        agent = self.agents.get(result.agent_name)
                        if agent and agent.is_gate_keeper:
                            print(
                                f"\n  PIPELINE HALTED: Gate-keeper {result.agent_name} "
                                f"blocked (risk check failed)"
                            )
                            break

            print()

        # Save state
        self._save_state()

        return self.results

    async def _execute_agent(self, agent: SwarmAgent, inputs: dict[str, Any]) -> AgentResult:
        """Execute a single agent."""
        try:
            return await agent.execute(inputs, self.messages)
        except Exception as e:
            logger.error(f"Agent {agent.name} execution error: {e}")
            return AgentResult(
                agent_name=agent.name,
                role=agent.role,
                success=False,
                output={},
                execution_time_ms=0,
                error=str(e),
            )

    async def _spawn_fixer(self, failed_agent: str, error: str | None) -> AgentResult | None:
        """
        Watchdog pattern: Spawn Fixer agent on errors.

        Attempts to diagnose and recover from failures.
        """
        if self.fixer_spawned:
            logger.warning("Fixer already spawned - avoiding infinite loop")
            return None

        self.fixer_spawned = True
        fixer = self.agents.get("Fixer")

        if not fixer:
            logger.error("Fixer agent not registered")
            return None

        print(f"\n[WATCHDOG] Spawning Fixer for {failed_agent}")

        inputs = {"failed_agent": failed_agent, "error": error or "unknown"}
        result = await fixer.execute(inputs, [])

        self.results["Fixer"] = result
        print(f"  [FIXER] Diagnosis: {result.output.get('diagnosis', {})}")
        print(f"  [FIXER] Recovery: {result.output.get('recovery', {})}")

        return result

    def get_consensus(self) -> dict[str, Any]:
        """Get swarm consensus from all agent signals."""
        signals = []
        confidences = []

        for result in self.results.values():
            if result.success and "signal" in result.output:
                signals.append(result.output["signal"])
                confidences.append(result.output.get("confidence", 0.5))

        if not signals:
            return {
                "consensus_signal": 0.5,
                "avg_confidence": 0.0,
                "decision": "NO_DATA",
                "agents_contributing": 0,
            }

        # Weighted average by confidence
        total_weight = sum(confidences)
        if total_weight > 0:
            consensus_signal = (
                sum(s * c for s, c in zip(signals, confidences, strict=False)) / total_weight
            )
        else:
            consensus_signal = sum(signals) / len(signals)

        avg_confidence = sum(confidences) / len(confidences)

        # Decision thresholds
        if consensus_signal >= 0.65 and avg_confidence >= 0.7:
            decision = "TRADE"
        elif consensus_signal <= 0.35:
            decision = "CLOSE"
        else:
            decision = "HOLD"

        return {
            "consensus_signal": round(consensus_signal, 3),
            "avg_confidence": round(avg_confidence, 3),
            "decision": decision,
            "agents_contributing": len(signals),
        }

    def get_state_summary(self) -> dict[str, Any]:
        """Get summary of swarm state."""
        return {
            "swarm": self.name,
            "total_agents": len(self.agents),
            "executed": len(self.results),
            "successful": sum(1 for r in self.results.values() if r.success),
            "failed": sum(1 for r in self.results.values() if not r.success),
            "fixer_spawned": self.fixer_spawned,
            "total_execution_time_ms": sum(r.execution_time_ms for r in self.results.values()),
            "consensus": self.get_consensus(),
            "agent_results": {name: r.to_dict() for name, r in self.results.items()},
        }

    def _save_state(self) -> None:
        """Persist swarm state to disk."""
        state = {
            "swarm": self.name,
            "last_updated": datetime.now(UTC).isoformat(),
            "execution_order": self.execution_order,
            "results": {name: r.to_dict() for name, r in self.results.items()},
            "messages": [m.to_dict() for m in self.messages],
            "consensus": self.get_consensus(),
        }
        self.state_file.write_text(json.dumps(state, indent=2))
        logger.info(f"Swarm state saved to {self.state_file}")

    def _load_state(self) -> None:
        """Load swarm state from disk."""
        if not self.state_file.exists():
            return

        try:
            state = json.loads(self.state_file.read_text())
            self.execution_order = state.get("execution_order", [])
            # Note: Full restoration would require deserializing AgentResult objects
            logger.info(f"Loaded swarm state from {self.state_file}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load swarm state: {e}")


async def run_trading_swarm(
    sentiment: float = 0.6,
    technicals: float = 0.65,
    news: float = 0.55,
    vix: float = 18,
    portfolio_value: float = 100000,
    position_size: float = 3000,
) -> dict[str, Any]:
    """
    Run the trading swarm pipeline.

    Args:
        sentiment: Sentiment signal (0-1)
        technicals: Technical analysis signal (0-1)
        news: News signal (0-1)
        vix: Current VIX level
        portfolio_value: Portfolio value for risk calculations
        position_size: Proposed position size

    Returns:
        Swarm execution summary with consensus decision
    """
    swarm = TradingSwarm()

    inputs = {
        "sentiment": sentiment,
        "technicals": technicals,
        "news": news,
        "vix": vix,
        "portfolio_value": portfolio_value,
        "position_size": position_size,
        "positions": [],  # Current positions for Monitor
    }

    results = await swarm.execute_pipeline(inputs)
    summary = swarm.get_state_summary()

    # Print summary
    print(f"{'=' * 60}")
    print("SWARM SUMMARY")
    print(f"{'=' * 60}")
    print(f"Agents: {summary['total_agents']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Total time: {summary['total_execution_time_ms']:.0f}ms")
    print()

    consensus = summary["consensus"]
    print(f"CONSENSUS SIGNAL: {consensus['consensus_signal']}")
    print(f"AVG CONFIDENCE: {consensus['avg_confidence']}")
    print(f"DECISION: {consensus['decision']}")

    # Get trade params if decision is TRADE
    if consensus["decision"] == "TRADE":
        executor_result = results.get("Executor")
        if executor_result and executor_result.success:
            params = executor_result.output.get("trade_params")
            if params:
                print("\nTRADE PARAMETERS:")
                print(f"  Ticker: {params.get('ticker')}")
                print(f"  Delta: {params.get('delta')}")
                print(f"  DTE: {params.get('dte')}")
                print(f"  Width: ${params.get('width')}")

    return summary


async def integrate_with_daggr() -> dict[str, Any]:
    """
    Integrate swarm with Daggr workflow for visual debugging.

    Creates a TradingWorkflow that uses swarm agents as nodes.
    """
    from src.orchestration.daggr_workflow import TradingWorkflow

    workflow = TradingWorkflow("swarm_integrated_pipeline")
    swarm = TradingSwarm()

    # Create workflow nodes from swarm agents
    async def swarm_market_analysis(**kwargs) -> dict:
        """Swarm-based market analysis."""
        analyst = swarm.agents.get("Analyst")
        if analyst:
            result = await analyst.execute(kwargs, [])
            return result.output
        return {"signal": 0.5, "confidence": 0.5}

    async def swarm_risk_gate(**kwargs) -> dict:
        """Swarm-based risk assessment."""
        risk_mgr = swarm.agents.get("RiskManager")
        if risk_mgr:
            # Pass analyst output as message
            analyst_output = kwargs.get("market_analysis", {})
            swarm.send_message("Analyst", "RiskManager", analyst_output)
            result = await risk_mgr.execute(kwargs, swarm.messages)
            return result.output
        return {"signal": 0.5, "passed": True}

    async def swarm_execution(**kwargs) -> dict:
        """Swarm-based execution decision."""
        executor = swarm.agents.get("Executor")
        if executor:
            result = await executor.execute(kwargs, swarm.messages)
            return result.output
        return {"action": "HOLD", "signal": 0.5}

    # Add nodes to workflow
    workflow.add_node("market_analysis", swarm_market_analysis, "analysis")
    workflow.add_node(
        "risk_gate",
        swarm_risk_gate,
        "gate_keeper",
        dependencies=["market_analysis"],
    )
    workflow.add_node(
        "execution",
        swarm_execution,
        "execution",
        dependencies=["market_analysis", "risk_gate"],
    )

    # Execute workflow
    await workflow.execute({"sentiment": 0.6, "technicals": 0.65, "news": 0.55, "vix": 18})

    return workflow.get_state_summary()


if __name__ == "__main__":
    # Demo execution
    result = asyncio.run(run_trading_swarm())
    print(f"\nSwarm state saved to: {SWARM_STATE_DIR}")
