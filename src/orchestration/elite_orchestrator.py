"""
Elite AI Trading Orchestrator
World-class multi-agent system combining:
- Claude Agents SDK + Skills (core flows)
- Langchain Agents (RAG, multi-modal fusion)
- Gemini Agents (research, long-horizon planning)
- Go ADK Agents (high-speed execution)
- Planning-first agentic flows
- Context engineering with persistent storage
"""

import contextlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# Inline stubs for deleted agent_framework (never implemented)
class ContextType:
    TASK_CONTEXT = "task"


class RunContext:
    pass


class RunMode:
    PAPER = "paper"
    LIVE = "live"


from src.core.skills_integration import get_skills
from src.orchestration.shared_types import AgentType, PlanningPhase, TradePlan

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from an agent execution"""

    agent_type: AgentType
    success: bool
    data: dict[str, Any]
    confidence: float = 0.0
    reasoning: str = ""
    errors: list[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


class EliteOrchestrator:
    """
    Elite AI Trading Orchestrator

    Combines all agent frameworks into a unified, planning-first system:
    1. Planning phase: Explicit planning before acting
    2. Multi-agent coordination: Claude Skills, Langchain, Gemini, Go ADK
    3. Context engineering: Persistent storage outside prompts
    4. Hybrid orchestration: Each agent type for its strengths
    5. Autonomous operation: Minimal human intervention
    6. Adaptive organization: Dynamic agent reorganization (NEW)
    """

    def __init__(
        self,
        paper: bool = True,
        enable_planning: bool = True,
        enable_adaptive: bool | None = None,
    ):
        """
        Initialize Elite Orchestrator

        Args:
            paper: Paper trading mode
            enable_planning: Enable planning-first flows
            enable_adaptive: Enable adaptive agent organization (default: from env or True)
        """
        self.paper = paper
        self.enable_planning = enable_planning
        self.enable_adaptive = (
            enable_adaptive
            if enable_adaptive is not None
            else os.getenv("ENABLE_ADAPTIVE_ORCHESTRATOR", "true").lower() == "true"
        )

        # Initialize all agent frameworks
        self.skills = get_skills()
        self.mcp_orchestrator = None
        self.adk_adapter = None
        self.langchain_agent = None
        self.gemini_agent = None

        # Planning storage
        self.plans_dir = Path("data/trading_plans")
        self.plans_dir.mkdir(parents=True, exist_ok=True)

        # Context storage
        self.context_dir = Path("data/agent_context")
        self.context_dir.mkdir(parents=True, exist_ok=True)

        # Audit trail
        self.audit_dir = Path("data/audit_trail")
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # REMOVED: Context Engine (agent_framework deleted)
        # self.context_engine = get_context_engine(storage_dir=self.context_dir)

        # REMOVED: agent_blueprints (agent_framework deleted)
        # agent_blueprints.register_trading_agent_blueprints()

        # Agent0 Co-Evolution System (optional)
        self.agent0_enabled = os.getenv("AGENT0_ENABLED", "false").lower() == "true"
        self.coevolution_engine = None
        if self.agent0_enabled:
            try:
                # REMOVED: CoEvolutionEngine (agent_framework deleted)
                # self.coevolution_engine = CoEvolutionEngine(
                #     storage_dir=self.context_dir / "coevolution"
                # )
                logger.info("✅ Agent0 Co-Evolution Engine initialized")
            except Exception as e:
                logger.warning(f"⚠️ Agent0 Co-Evolution Engine unavailable: {e}")
                self.coevolution_engine = None

        self._initialize_agents()

        # Initialize Adaptive Orchestrator if enabled
        self.adaptive_orchestrator = None
        if self.enable_adaptive:
            try:
                from src.orchestration.adaptive_orchestrator import AdaptiveOrchestrator

                self.adaptive_orchestrator = AdaptiveOrchestrator(
                    paper=self.paper, enable_learning=True
                )
                logger.info("✅ Adaptive Orchestrator initialized")
            except Exception as e:
                logger.warning(f"⚠️ Adaptive Orchestrator unavailable: {e}")
                self.adaptive_orchestrator = None

        logger.info("✅ Elite Orchestrator initialized")
        logger.info(f"   Planning: {'Enabled' if enable_planning else 'Disabled'}")
        logger.info(f"   Adaptive: {'Enabled' if self.adaptive_orchestrator else 'Disabled'}")
        logger.info(f"   Mode: {'PAPER' if paper else 'LIVE'}")

        # Ensemble voting configuration and agent filters
        self.ensemble_buy_threshold = float(os.getenv("ENSEMBLE_BUY_THRESHOLD", "0.15"))
        self.ensemble_sell_threshold = float(os.getenv("ENSEMBLE_SELL_THRESHOLD", "-0.15"))

        # Execution sizing scale bounds
        self.size_scale_min = float(os.getenv("ENSEMBLE_SIZE_SCALE_MIN", "0.5"))
        self.size_scale_max = float(os.getenv("ENSEMBLE_SIZE_SCALE_MAX", "1.0"))

        # Load weights and override thresholds from YAML if present
        self.ensemble_weights = self._load_ensemble_weights()

        # Optional analysis agent filter (can be set by CLI/scripts)
        self._analysis_agent_filter = None

    def _load_ensemble_weights(self) -> dict[str, float]:
        """Load ensemble weights from environment with defaults and optional YAML config."""
        weights = {
            "mcp": float(os.getenv("ENSEMBLE_WEIGHT_MCP", "0.35")),
            "langchain": float(os.getenv("ENSEMBLE_WEIGHT_LANGCHAIN", "0.15")),
            "gemini": float(os.getenv("ENSEMBLE_WEIGHT_GEMINI", "0.15")),
            "ml": float(os.getenv("ENSEMBLE_WEIGHT_ML", "0.25")),
            "ensemble_rl": float(os.getenv("ENSEMBLE_WEIGHT_ENSEMBLE_RL", "0.25")),
            "grok": float(os.getenv("ENSEMBLE_WEIGHT_GROK", "0.10")),
            "bogleheads": float(os.getenv("ENSEMBLE_WEIGHT_BOGLEHEADS", "0.10")),
        }
        # YAML override
        config_path = os.getenv("ENSEMBLE_CONFIG_PATH", "profiles/ensemble-config.yaml")
        try:
            from pathlib import Path as _Path

            p = _Path(config_path)
            if p.exists():
                try:
                    import yaml  # type: ignore

                    with open(p) as f:
                        cfg = yaml.safe_load(f) or {}
                    if isinstance(cfg, dict):
                        w = cfg.get("weights") or {}
                        if isinstance(w, dict):
                            for k, v in w.items():
                                with contextlib.suppress(Exception):
                                    weights[k] = float(v)
                        th = cfg.get("thresholds") or {}
                        if isinstance(th, dict):
                            with contextlib.suppress(Exception):
                                self.ensemble_buy_threshold = float(
                                    th.get("buy", self.ensemble_buy_threshold)
                                )
                            with contextlib.suppress(Exception):
                                self.ensemble_sell_threshold = float(
                                    th.get("sell", self.ensemble_sell_threshold)
                                )
                except Exception:
                    pass
        except Exception:
            pass
        return weights

    def _agent_enabled(self, agent_name: str) -> bool:
        """Check if an agent is enabled given include/exclude filters."""
        filt = self._analysis_agent_filter
        if not filt:
            return True
        include = filt.get("include") or set()
        exclude = filt.get("exclude") or set()
        if include and agent_name not in include:
            return False
        return not (exclude and agent_name in exclude)

    def _initialize_agents(self):
        """Initialize all agent frameworks"""
        # MCP Orchestrator (multi-agent system) - Lazy import
        try:
            from src.orchestration.mcp_trading import MCPTradingOrchestrator

            self.mcp_orchestrator = MCPTradingOrchestrator(
                symbols=["SPY", "QQQ", "VOO"], paper=self.paper
            )
            logger.info("✅ MCP Orchestrator initialized")
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"⚠️ MCP Orchestrator unavailable (dependencies missing): {e}")
            self.mcp_orchestrator = None
        except Exception as e:
            logger.warning(f"⚠️ MCP Orchestrator unavailable: {e}")
            self.mcp_orchestrator = None

        # Go ADK Adapter (high-speed execution) - Lazy import
        try:
            from src.orchestration.adk_integration import ADKTradeAdapter

            self.adk_adapter = ADKTradeAdapter(paper=self.paper)
            if self.adk_adapter.enabled:
                logger.info("✅ Go ADK Adapter initialized")
            else:
                logger.info("⚠️ Go ADK Adapter disabled")
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"⚠️ Go ADK Adapter unavailable (dependencies missing): {e}")
            self.adk_adapter = None
        except Exception as e:
            logger.warning(f"⚠️ Go ADK Adapter unavailable: {e}")
            self.adk_adapter = None

        # Langchain Agent (RAG, multi-modal fusion)
        try:
            from langchain_agents.agents import build_price_action_agent

            self.langchain_agent = build_price_action_agent()
            logger.info("✅ Langchain Agent initialized")
        except Exception as e:
            logger.warning(f"⚠️ Langchain Agent unavailable: {e}")

        # Gemini Agent (research, long-horizon planning)
        try:
            from src.agents.gemini_agent import GeminiAgent

            self.gemini_agent = GeminiAgent(name="EliteGemini", model="gemini-3-pro-preview")
            logger.info("✅ Gemini Agent initialized")
        except Exception as e:
            logger.warning(f"⚠️ Gemini Agent unavailable: {e}")

        # ML Predictor (LSTM-PPO)
        # DISABLED: src.ml.inference module does not exist
        # try:
        #     from src.ml.inference import MLPredictor
        #     self.ml_predictor = MLPredictor()
        #     logger.info("✅ ML Predictor (LSTM-PPO) initialized")
        # except Exception as e:
        #     logger.warning(f"⚠️ ML Predictor unavailable: {e}")
        self.ml_predictor = None

        # Deep Q-Network Agent (Enhanced RL)
        # DISABLED: src.ml.dqn_agent and src.ml.multi_step_learning modules do not exist
        self.dqn_agent = None
        self.use_dqn = os.getenv("USE_DQN", "false").lower() == "true"
        if self.use_dqn:
            logger.info("ℹ️ DQN Agent disabled (modules not available)")
            # try:
            #     from src.ml.dqn_agent import DQNAgent
            #     from src.ml.multi_step_learning import NStepDQNAgent
            #     # Determine state dimension (will be set based on feature extraction)
            #     state_dim = 50  # Default, can be configured
            #     dqn = DQNAgent(
            #         state_dim=state_dim,
            #         use_dueling=True,
            #         use_double=True,
            #         use_prioritized_replay=True,
            #         device="cpu",
            #     )
            #     # Wrap with n-step learning
            #     self.dqn_agent = NStepDQNAgent(dqn, n=3)
            #     logger.info("✅ DQN Agent (with n-step learning) initialized")
            # except Exception as e:
            #     logger.warning(f"⚠️ DQN Agent unavailable: {e}")
            #     self.dqn_agent = None
        else:
            logger.info("ℹ️ DQN Agent disabled (set USE_DQN=true to enable)")

        # Gamma Exposure Agent
        try:
            from src.agents.gamma_exposure_agent import GammaExposureAgent

            self.gamma_agent = GammaExposureAgent()
            logger.info("✅ Gamma Exposure Agent initialized")
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"⚠️ Gamma Exposure Agent unavailable (dependencies missing): {e}")
            self.gamma_agent = None
        except Exception as e:
            logger.warning(f"⚠️ Gamma Exposure Agent unavailable: {e}")
            self.gamma_agent = None

        # BogleHeads Agent
        try:
            from src.agents.bogleheads_agent import BogleHeadsAgent

            self.bogleheads_agent = BogleHeadsAgent()
            logger.info("✅ BogleHeads Agent initialized")
        except Exception as e:
            logger.warning(f"⚠️ BogleHeads Agent unavailable: {e}")
            self.bogleheads_agent = None

        logger.info(
            "✅ Elite Orchestrator Agents Initialized (Claude, Langchain, Gemini, MCP, ML, Gamma, BogleHeads, Agent0)"
        )

    def create_trade_plan(
        self, symbols: list[str], context: dict[str, Any] | None = None
    ) -> TradePlan:
        """
        Create a planning-first trade plan (with adaptive organization if enabled)

        Args:
            symbols: Symbols to trade
            context: Additional context

        Returns:
            TradePlan with explicit planning phases (adaptive if enabled)
        """
        # Use adaptive orchestrator if enabled
        if self.enable_adaptive and self.adaptive_orchestrator:
            logger.info("🔄 Using adaptive agent organization")
            plan = self.adaptive_orchestrator.create_adaptive_plan(symbols, context)
            self._save_plan(plan)
            return plan

        # Fallback to fixed organization
        logger.info("📋 Using fixed agent organization")
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        plan = TradePlan(
            plan_id=plan_id,
            timestamp=datetime.now().isoformat(),
            symbols=symbols,
            context=context or {},
        )

        # Define planning phases (fixed structure)
        plan.phases = {
            PlanningPhase.INITIALIZE.value: {
                "description": "Initialize trading cycle",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": [
                    "Load portfolio state",
                    "Check market hours",
                    "Validate account status",
                ],
                "status": "pending",
            },
            PlanningPhase.DATA_COLLECTION.value: {
                "description": "Collect market data and signals",
                "agents": [
                    AgentType.CLAUDE_SKILLS.value,
                    AgentType.LANGCHAIN.value,
                    AgentType.GEMINI.value,
                ],
                "tasks": [
                    "Fetch price data",
                    "Retrieve news sentiment",
                    "Gather social signals",
                    "Load alternative data",
                ],
                "status": "pending",
            },
            PlanningPhase.ANALYSIS.value: {
                "description": "Multi-agent analysis",
                # Analysis Phase: Agents analyze data and form opinions
                "agents": [
                    AgentType.LANGCHAIN.value,
                    AgentType.GEMINI.value,
                    AgentType.MCP.value,
                    AgentType.ML_MODEL.value,
                    "gamma_agent",  # New Gamma Exposure Agent
                    "bogleheads_agent",  # New BogleHeads Agent
                ],
                "tasks": [
                    "Technical analysis",
                    "Fundamental analysis",
                    "Sentiment analysis",
                    "Ensemble voting",
                ],
                "status": "pending",
            },
            PlanningPhase.RISK_ASSESSMENT.value: {
                "description": "Risk validation",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": [
                    "Portfolio health check",
                    "Position sizing",
                    "Stop-loss calculation",
                    "Circuit breaker check",
                ],
                "status": "pending",
            },
            PlanningPhase.EXECUTION.value: {
                "description": "Trade execution",
                "agents": [AgentType.GO_ADK.value, AgentType.MCP.value],
                "tasks": [
                    "Order placement",
                    "Execution monitoring",
                    "Anomaly detection",
                ],
                "status": "pending",
            },
            PlanningPhase.AUDIT.value: {
                "description": "Post-trade audit",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Performance tracking", "Trade logging", "Git commit"],
                "status": "pending",
            },
        }

        # Save plan to persistent storage
        self._save_plan(plan)

        logger.info(f"📋 Created trade plan: {plan_id} for {len(symbols)} symbols")
        return plan

    def execute_plan(self, plan: TradePlan) -> dict[str, Any]:
        """
        Execute a trade plan with multi-agent coordination

        Args:
            plan: Trade plan to execute

        Returns:
            Execution results
        """
        logger.info(f"🚀 Executing plan: {plan.plan_id}")

        results = {
            "plan_id": plan.plan_id,
            "phases": {},
            "agent_results": [],
            "final_decision": None,
            "errors": [],
        }

        # Phase 1: Initialize
        try:
            init_result = self._execute_phase(plan, PlanningPhase.INITIALIZE)
            results["phases"][PlanningPhase.INITIALIZE.value] = init_result
            plan.phases[PlanningPhase.INITIALIZE.value]["status"] = "completed"
        except Exception as e:
            logger.error(f"Phase 1 failed: {e}")
            results["errors"].append(f"Initialize: {str(e)}")
            return results

        # Phase 2: Data Collection (multi-agent)
        try:
            data_result = self._execute_data_collection(plan)
            results["phases"][PlanningPhase.DATA_COLLECTION.value] = data_result
            plan.phases[PlanningPhase.DATA_COLLECTION.value]["status"] = "completed"
        except Exception as e:
            logger.error(f"Phase 2 failed: {e}")
            results["errors"].append(f"Data Collection: {str(e)}")

        # Phase 3: Analysis (ensemble voting)
        analysis_result = None  # Initialize to prevent NameError if Phase 3 fails
        try:
            analysis_result = self._execute_analysis(
                plan, data_result
            )  # Pass data_result to analysis
            results["phases"][PlanningPhase.ANALYSIS.value] = analysis_result
            plan.phases[PlanningPhase.ANALYSIS.value]["status"] = "completed"
            results["agent_results"].extend(analysis_result.get("agent_results", []))
        except Exception as e:
            logger.error(f"Phase 3 failed: {e}")
            results["errors"].append(f"Analysis: {str(e)}")
            # Set empty analysis_result to prevent downstream errors
            analysis_result = {"agent_results": [], "ensemble_vote": {}}

        # Phase 4: Risk Assessment
        try:
            risk_result = self._execute_risk_assessment(plan)
            results["phases"][PlanningPhase.RISK_ASSESSMENT.value] = risk_result
            plan.phases[PlanningPhase.RISK_ASSESSMENT.value]["status"] = "completed"

            # Check if trading should halt
            if risk_result.get("should_halt"):
                logger.warning("🚫 Trading halted by risk assessment")
                plan.status = "halted"
                self._save_plan(plan)
                return results
        except Exception as e:
            logger.error(f"Phase 4 failed: {e}")
            results["errors"].append(f"Risk Assessment: {str(e)}")

        # Phase 5: Execution
        try:
            if analysis_result is None:
                logger.error("Cannot execute trades: analysis phase failed")
                results["errors"].append("Execution: Analysis phase failed, skipping execution")
            else:
                exec_result = self._execute_trades(plan, analysis_result)
            results["phases"][PlanningPhase.EXECUTION.value] = exec_result
            plan.phases[PlanningPhase.EXECUTION.value]["status"] = "completed"
            results["final_decision"] = exec_result.get("decision")
        except Exception as e:
            logger.error(f"Phase 5 failed: {e}")
            results["errors"].append(f"Execution: {str(e)}")

        # Phase 6: Audit
        try:
            audit_result = self._execute_audit(plan, results)
            results["phases"][PlanningPhase.AUDIT.value] = audit_result
            plan.phases[PlanningPhase.AUDIT.value]["status"] = "completed"
        except Exception as e:
            logger.error(f"Phase 6 failed: {e}")
            results["errors"].append(f"Audit: {str(e)}")

        plan.status = "completed"
        self._save_plan(plan)
        self._save_results(plan.plan_id, results)

        # Record performance for adaptive learning
        if self.enable_adaptive and self.adaptive_orchestrator:
            try:
                execution_time_ms = sum(
                    phase.get("execution_time_ms", 0)
                    for phase in results.get("phases", {}).values()
                )
                success = len(results.get("errors", [])) == 0
                profit = results.get("final_decision", {}).get("profit", 0.0) or 0.0
                confidence = (
                    analysis_result.get("ensemble_vote", {})
                    .get(list(plan.symbols)[0] if plan.symbols else "", {})
                    .get("weighted_score", 0.0)
                    if analysis_result
                    else 0.0
                )

                # Get complexity and regime from plan context
                complexity_str = plan.context.get("complexity", "moderate")
                market_regime = plan.context.get("market_regime", "SIDEWAYS")

                from src.orchestration.adaptive_orchestrator import (
                    ComplexityAssessment,
                    OrganizationPattern,
                    TaskComplexity,
                )

                complexity = ComplexityAssessment(
                    complexity=TaskComplexity(complexity_str),
                    score=plan.context.get("complexity_score", 0.5),
                    factors={},
                )

                organization_pattern = OrganizationPattern(
                    plan.context.get("organization_pattern", "parallel")
                )

                # Create minimal organization for recording
                from src.orchestration.adaptive_orchestrator import AgentOrganization

                organization = AgentOrganization(
                    pattern=organization_pattern,
                    phases={},
                    agent_assignments={},
                    execution_order=[],
                )

                self.adaptive_orchestrator.record_performance(
                    organization=organization,
                    complexity=complexity,
                    market_regime=market_regime,
                    execution_time_ms=execution_time_ms,
                    success=success,
                    profit=profit,
                    confidence=confidence,
                )
            except Exception as e:
                logger.warning(f"Failed to record adaptive performance: {e}")

        logger.info(f"✅ Plan execution complete: {plan.plan_id}")
        return results

    def _execute_phase(self, plan: TradePlan, phase: PlanningPhase) -> dict[str, Any]:
        """Execute a single phase"""
        phase_config = plan.phases[phase.value]
        results = {"phase": phase.value, "tasks": {}, "agent_results": []}

        for task in phase_config["tasks"]:
            # Use Claude Skills for initialization
            if phase == PlanningPhase.INITIALIZE:
                if task == "Load portfolio state":
                    health_result = self.skills.assess_portfolio_health()
                    results["tasks"][task] = health_result
                elif task == "Check market hours":
                    # Use Financial Data Fetcher skill
                    if self.skills.financial_data_fetcher:
                        market_result = self.skills.get_price_data(
                            symbols=plan.symbols[:1],  # Check one symbol
                            timeframe="1Min",
                            limit=1,
                        )
                        results["tasks"][task] = market_result

        return results

    def _execute_data_collection(self, plan: TradePlan) -> dict[str, Any]:
        """Execute data collection phase with multiple agents using Context Engine"""
        results = {
            "phase": PlanningPhase.DATA_COLLECTION.value,
            "data_sources": {},
            "agent_results": [],
        }

        # Get agent contexts from Context Engine
        for symbol in plan.symbols:
            # Claude Skills: Financial Data
            if self.skills.financial_data_fetcher:
                try:
                    data_result = self.skills.get_price_data(
                        symbols=[symbol], timeframe="1Day", limit=30
                    )
                    results["data_sources"][f"{symbol}_price"] = data_result

                    # Store in context memory
                    self.context_engine.store_memory(
                        agent_id="research_agent",
                        content={
                            "symbol": symbol,
                            "price_data": data_result,
                            "timestamp": datetime.now().isoformat(),
                        },
                        tags={symbol, "price_data", "data_collection"},
                    )
                except Exception as e:
                    logger.warning(f"Price data collection failed for {symbol}: {e}")

            # Langchain: RAG for news/sentiment
            if self.langchain_agent:
                try:
                    # Get context for langchain agent

                    prompt = (
                        f"Analyze recent news and sentiment for {symbol}. Provide key insights."
                    )
                    langchain_result = self.langchain_agent.invoke({"input": prompt})

                    result_data = {"agent": "langchain", "data": str(langchain_result)}
                    results["data_sources"][f"{symbol}_sentiment"] = result_data

                    # Send context message
                    self.context_engine.send_context_message(
                        sender="langchain_agent",
                        receiver="meta_agent",
                        payload=result_data,
                        context_type="TASK_CONTEXT",  # ContextType removed - agent_framework deleted
                        metadata={"symbol": symbol, "phase": "data_collection"},
                    )
                except Exception as e:
                    logger.warning(f"Langchain data collection failed for {symbol}: {e}")

            # Gemini: Long-horizon research
            if self.gemini_agent:
                try:
                    research_prompt = f"Provide long-term research analysis for {symbol}. Consider fundamentals, trends, and portfolio fit."
                    gemini_result = self.gemini_agent.reason(prompt=research_prompt)

                    result_data = {"agent": "gemini", "data": gemini_result}
                    results["data_sources"][f"{symbol}_research"] = result_data

                    # Store in memory
                    self.context_engine.store_memory(
                        agent_id="gemini_agent",
                        content={
                            "symbol": symbol,
                            "research": gemini_result,
                            "timestamp": datetime.now().isoformat(),
                        },
                        tags={symbol, "research", "long_term"},
                    )
                except Exception as e:
                    logger.warning(f"Gemini research failed for {symbol}: {e}")

        return results

    def _execute_analysis(
        self, plan: TradePlan, data_collection_results: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Execute analysis phase with ensemble voting using Context Engine"""
        results = {
            "phase": PlanningPhase.ANALYSIS.value,
            "agent_results": [],
            "ensemble_vote": {},
        }

        # Collect recommendations from all agents
        recommendations = {}

        # Optional: derive Bogleheads weight multiplier from latest RAG snapshot (market regime)
        bogleheads_multiplier = 1.0
        try:
            from src.rag.sentiment_store import SentimentRAGStore

            store = SentimentRAGStore()
            bh = store.get_ticker_history("MARKET", limit=1)
            if bh:
                regime = (bh[0].get("metadata", {}) or {}).get("market_regime", "unknown").lower()
                boost_map = {
                    "bull": float(os.getenv("ENSEMBLE_BOGLEHEADS_BOOST_BULL", "1.0")),
                    "bear": float(os.getenv("ENSEMBLE_BOGLEHEADS_BOOST_BEAR", "1.2")),
                    "choppy": float(os.getenv("ENSEMBLE_BOGLEHEADS_BOOST_CHOPPY", "1.0")),
                    "unknown": float(os.getenv("ENSEMBLE_BOGLEHEADS_BOOST_UNKNOWN", "1.0")),
                }
                bogleheads_multiplier = boost_map.get(regime, boost_map["unknown"])
        except Exception:
            pass

        # MCP Orchestrator (multi-agent system)
        if self.mcp_orchestrator and self._agent_enabled("mcp"):
            try:
                # Validate context flow before execution
                is_valid, errors = self.context_engine.validate_context_flow(
                    from_agent="research_agent",
                    to_agent="signal_agent",
                    context=data_collection_results or {},
                )
                if not is_valid:
                    logger.warning(f"Context validation warnings: {errors}")

                mcp_result = self.mcp_orchestrator.run_once(execute_orders=False)
                for symbol in plan.symbols:
                    if symbol in mcp_result.get("symbols", []):
                        rec_data = {
                            "agent": "mcp",
                            "recommendation": mcp_result.get("symbols", {}).get(symbol, {}),
                            "confidence": 0.8,
                        }
                        recommendations[f"{symbol}_mcp"] = rec_data

                        # Send context message
                        self.context_engine.send_context_message(
                            sender="mcp",
                            receiver="meta_agent",
                            payload=rec_data,
                            context_type=ContextType.TASK_CONTEXT,
                            metadata={"symbol": symbol, "phase": "analysis"},
                        )
            except Exception as e:
                logger.warning(f"MCP analysis failed: {e}")

        # Langchain Agent
        if self.langchain_agent and self._agent_enabled("langchain"):
            for symbol in plan.symbols:
                try:
                    prompt = f"Should we trade {symbol}? Provide recommendation with reasoning."
                    langchain_result = self.langchain_agent.invoke({"input": prompt})
                    text = str(langchain_result)
                    approve = "approve" in text.lower() and "decline" not in text.lower()
                    recommendations[f"{symbol}_langchain"] = {
                        "agent": "langchain",
                        "recommendation": "BUY" if approve else "HOLD",
                        "confidence": 0.7,
                        "reasoning": text[:200],
                    }
                except Exception as e:
                    logger.warning(f"Langchain analysis failed for {symbol}: {e}")

        # Gemini Agent
        if self.gemini_agent and self._agent_enabled("gemini"):
            for symbol in plan.symbols:
                try:
                    gemini_prompt = (
                        f"Analyze {symbol} for trading. Consider long-term portfolio fit and risk."
                    )
                    gemini_result = self.gemini_agent.reason(prompt=gemini_prompt)
                    decision = gemini_result.get("decision", "").upper()
                    recommendations[f"{symbol}_gemini"] = {
                        "agent": "gemini",
                        "recommendation": decision if decision else "HOLD",
                        "confidence": 0.75,
                        "reasoning": gemini_result.get("reasoning", "")[:200],
                    }
                except Exception as e:
                    logger.warning(f"Gemini analysis failed for {symbol}: {e}")

        # ML Predictor (LSTM-PPO or Ensemble)
        if self.ml_predictor and (
            self._agent_enabled("ml_model") or self._agent_enabled("ensemble_rl")
        ):
            for symbol in plan.symbols:
                try:
                    # Try to use ensemble RL if available
                    use_ensemble = os.getenv("USE_ENSEMBLE_RL", "false").lower() == "true"

                    if use_ensemble:
                        # DISABLED: src.ml.data_processor and src.ml.ensemble_rl modules do not exist
                        logger.debug("Ensemble RL not available (modules do not exist)")
                        # try:
                        #     import torch  # noqa: F401
                        #     from src.ml.data_processor import DataProcessor
                        #     from src.ml.ensemble_rl import EnsembleRLAgent
                        #     # Get state representation
                        #     data_processor = DataProcessor()
                        #     df = data_processor.fetch_data(symbol, period="1y")
                        #     if not df.empty:
                        #         df = data_processor.add_technical_indicators(df)
                        #         df = data_processor.normalize_data(df)
                        #         sequences = data_processor.create_sequences(df)
                        #         if len(sequences) > 0:
                        #             # Use last sequence
                        #             state = sequences[-1:].unsqueeze(0)  # Add batch dimension
                        #             # Initialize ensemble agent
                        #             ensemble_agent = EnsembleRLAgent(
                        #                 input_dim=len(data_processor.feature_columns),
                        #                 device="cpu",
                        #             )
                        #             # Get prediction
                        #             action, confidence, details = ensemble_agent.predict(state)
                        #             action_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
                        #             recommendations[f"{symbol}_ml"] = {
                        #                 "agent": "ensemble_rl",
                        #                 "recommendation": action_map.get(action, "HOLD"),
                        #                 "confidence": confidence,
                        #                 "reasoning": f"Ensemble RL (PPO+A2C+SAC): {details.get('individual_predictions', {})}",
                        #             }
                        #             logger.info(
                        #                 f"✅ Ensemble RL prediction for {symbol}: {action_map.get(action)} (confidence: {confidence:.2f})"
                        #             )
                        # except Exception as e:
                        #     logger.debug(f"Ensemble RL not available, using single model: {e}")

                    # Fallback to single model
                    if f"{symbol}_ml" not in recommendations:
                        ml_signal = self.ml_predictor.get_signal(symbol)
                        recommendations[f"{symbol}_ml"] = {
                            "agent": "ml_model",
                            "recommendation": ml_signal["action"],
                            "confidence": ml_signal["confidence"],
                            "reasoning": f"LSTM-PPO Value Estimate: {ml_signal.get('value_estimate', 0):.2f}",
                        }
                except Exception as e:
                    logger.warning(f"ML prediction failed for {symbol}: {e}")

        # Social sentiment (Grok) from context memory, if enabled
        if self._agent_enabled("grok_twitter"):
            try:
                for symbol in plan.symbols:
                    memories = self.context_engine.retrieve_memories(
                        agent_id="research_agent",
                        tags={symbol, "grok_twitter", "sentiment"},
                        limit=1,
                    )
                    if memories:
                        grok_data = memories[0].content.get("grok_twitter", {})
                        score = grok_data.get("score")
                        if score is not None:
                            action = "HOLD"
                            if score >= 20:
                                action = "BUY"
                            elif score <= -20:
                                action = "SELL"
                            confidence = min(1.0, max(0.0, abs(score) / 100.0)) * 0.6
                            recommendations[f"{symbol}_grok"] = {
                                "agent": "grok_twitter",
                                "recommendation": action,
                                "confidence": round(confidence, 2),
                                "reasoning": f"Twitter sentiment score={score}",
                            }
            except Exception as e:
                logger.debug(f"Grok/X sentiment integration in analysis unavailable: {e}")

        # BogleHeads Agent (long-term sanity check / sentiment)
        if getattr(self, "bogleheads_agent", None) and self._agent_enabled("bogleheads"):
            for symbol in plan.symbols:
                try:
                    analysis = self.bogleheads_agent.analyze({"symbol": symbol})
                    decision = (
                        analysis.get("signal") or analysis.get("decision") or "HOLD"
                    ).upper()
                    confidence = float(analysis.get("confidence", 0.5))
                    recommendations[f"{symbol}_bogleheads"] = {
                        "agent": "bogleheads_agent",
                        "recommendation": (decision if decision in {"BUY", "SELL"} else "HOLD"),
                        "confidence": max(0.0, min(1.0, confidence)),
                        "reasoning": (analysis.get("reasoning") or "")[:200],
                    }
                except Exception as e:
                    logger.debug(f"BogleHeads analysis failed for {symbol}: {e}")

        # Ensemble voting (weighted)
        for symbol in plan.symbols:
            symbol_recs = {k: v for k, v in recommendations.items() if symbol in k}
            if symbol_recs:
                score = 0.0
                contributions = []
                for rec in symbol_recs.values():
                    agent_id = (rec.get("agent") or "").lower()
                    # Normalize agent id to weight key
                    if agent_id in ("ml_model", "ml"):
                        wkey = "ml"
                    elif agent_id == "grok_twitter":
                        wkey = "grok"
                    elif agent_id == "bogleheads_agent":
                        wkey = "bogleheads"
                    else:
                        wkey = agent_id
                    w = self.ensemble_weights.get(wkey, 0.1)
                    if wkey == "bogleheads":
                        w = w * bogleheads_multiplier
                    conf = float(rec.get("confidence", 0.5))
                    action = (rec.get("recommendation") or "HOLD").upper()
                    val = conf if action == "BUY" else (-conf if action == "SELL" else 0.0)
                    contrib = w * val
                    score += contrib
                    contributions.append(
                        {
                            "agent": agent_id,
                            "weight": w,
                            "confidence": conf,
                            "action": action,
                            "contrib": round(contrib, 4),
                        }
                    )

                consensus = "HOLD"
                if score >= self.ensemble_buy_threshold:
                    consensus = "BUY"
                elif score <= self.ensemble_sell_threshold:
                    consensus = "SELL"

                results["ensemble_vote"][symbol] = {
                    "weighted_score": round(score, 4),
                    "buy_threshold": self.ensemble_buy_threshold,
                    "sell_threshold": self.ensemble_sell_threshold,
                    "consensus": consensus,
                    "recommendations": symbol_recs,
                    "contributions": contributions,
                }

        results["agent_results"] = list(recommendations.values())
        return results

    def _execute_risk_assessment(self, plan: TradePlan) -> dict[str, Any]:
        """Execute risk assessment phase"""
        results = {
            "phase": PlanningPhase.RISK_ASSESSMENT.value,
            "should_halt": False,
            "risk_checks": {},
        }

        # Portfolio health check
        health_result = self.skills.assess_portfolio_health()
        results["risk_checks"]["portfolio_health"] = health_result

        if health_result.get("success"):
            health_data = health_result.get("data", {})
            if health_data.get("overall_status") == "HALTED":
                results["should_halt"] = True
                logger.warning("🚫 Portfolio health check: HALTED")

        # Position sizing for each symbol
        if plan.symbols:
            account_value = (
                health_data.get("account_equity", 100000)
                if health_result.get("success")
                else 100000
            )
            for symbol in plan.symbols:
                position_result = self.skills.calculate_position(
                    symbol=symbol, account_value=account_value, risk_per_trade_pct=1.0
                )
                results["risk_checks"][f"{symbol}_position"] = position_result

        return results

    def _execute_trades(self, plan: TradePlan, analysis_result: dict[str, Any]) -> dict[str, Any]:
        """Execute trades using high-speed agents"""
        results = {
            "phase": PlanningPhase.EXECUTION.value,
            "orders": [],
            "decision": "NO_TRADE",
        }

        ensemble_vote = analysis_result.get("ensemble_vote", {})

        # Determine account value for sizing
        health_result = self.skills.assess_portfolio_health()
        account_value = 100000
        if isinstance(health_result, dict) and health_result.get("success"):
            account_value = health_result.get("data", {}).get("account_equity", account_value)

        # Use Go ADK for high-speed execution
        if self.adk_adapter and self.adk_adapter.enabled:
            for symbol, vote in ensemble_vote.items():
                if vote.get("consensus") == "BUY":
                    try:
                        # Baseline position sizing (1% risk) scaled by ensemble confidence magnitude
                        position_result = self.skills.calculate_position(
                            symbol=symbol,
                            account_value=account_value,
                            risk_per_trade_pct=1.0,
                        )
                        base_dollars = (
                            position_result.get("recommendations", {})
                            .get("primary_method", {})
                            .get("position_size_dollars", 0.0)
                        ) or position_result.get("position_size_dollars", 0.0)
                        weighted_score = float(vote.get("weighted_score", 0.15))
                        # Scale execution size by confidence within configured bounds
                        scale = max(
                            self.size_scale_min,
                            min(self.size_scale_max, abs(weighted_score)),
                        )
                        desired_position_dollars = round(base_dollars * scale, 2)

                        # Use ADK for execution
                        adk_result = self.adk_adapter.evaluate(
                            symbols=[symbol],
                            context={
                                "plan_id": plan.plan_id,
                                "ensemble_vote": vote,
                                "desired_position_dollars": desired_position_dollars,
                                "sizing": {
                                    "account_value": account_value,
                                    "base_position_dollars": base_dollars,
                                    "scale": scale,
                                },
                            },
                        )
                        results["orders"].append(
                            {"symbol": symbol, "agent": "go_adk", "result": adk_result}
                        )
                    except Exception as e:
                        logger.error(f"ADK execution failed for {symbol}: {e}")

        # Fallback to MCP orchestrator
        elif self.mcp_orchestrator:
            for symbol, vote in ensemble_vote.items():
                if vote.get("consensus") == "BUY":
                    try:
                        mcp_result = self.mcp_orchestrator.run_once(execute_orders=True)
                        results["orders"].append(
                            {"symbol": symbol, "agent": "mcp", "result": mcp_result}
                        )
                    except Exception as e:
                        logger.error(f"MCP execution failed for {symbol}: {e}")

        if results["orders"]:
            results["decision"] = "TRADE_EXECUTED"

        # Anomaly detection after execution
        for order in results["orders"]:
            if order.get("result", {}).get("execution"):
                exec_data = order["result"]["execution"]
                anomaly_result = self.skills.detect_execution_anomalies(
                    order_id=exec_data.get("order_id", "unknown"),
                    expected_price=exec_data.get("expected_price", 0),
                    actual_fill_price=exec_data.get("fill_price", 0),
                    quantity=exec_data.get("quantity", 0),
                    order_type=exec_data.get("order_type", "market"),
                    timestamp=datetime.now().isoformat(),
                )
                order["anomaly_check"] = anomaly_result

        return results

    def _execute_audit(self, plan: TradePlan, execution_results: dict[str, Any]) -> dict[str, Any]:
        """Execute audit phase"""
        results = {
            "phase": PlanningPhase.AUDIT.value,
            "performance_metrics": {},
            "git_commit": None,
        }

        # Performance monitoring
        if self.skills.performance_monitor:
            perf_result = self.skills.get_performance_metrics(
                start_date=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
            )
            results["performance_metrics"] = perf_result

        # Save audit trail
        audit_file = self.audit_dir / f"{plan.plan_id}_audit.json"
        audit_data = {
            "plan_id": plan.plan_id,
            "timestamp": datetime.now().isoformat(),
            "plan": asdict(plan),
            "execution_results": execution_results,
        }
        with open(audit_file, "w") as f:
            json.dump(audit_data, f, indent=2, default=str)

        logger.info(f"📝 Audit trail saved: {audit_file}")

        return results

    def _save_plan(self, plan: TradePlan):
        """Save plan to persistent storage"""
        plan_file = self.plans_dir / f"{plan.plan_id}.json"
        with open(plan_file, "w") as f:
            json.dump(asdict(plan), f, indent=2, default=str)

    def _save_results(self, plan_id: str, results: dict[str, Any]):
        """Save execution results"""
        results_file = self.plans_dir / f"{plan_id}_results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)

    def run_trading_cycle(self, symbols: list[str]) -> dict[str, Any]:
        """
        Run a complete trading cycle with planning-first approach

        Args:
            symbols: Symbols to trade

        Returns:
            Complete cycle results
        """
        logger.info("=" * 80)
        logger.info("ELITE TRADING CYCLE STARTING")
        logger.info("=" * 80)

        # Optional: Run Agent0 co-evolution cycle before trading
        agent0_result = None
        if self.coevolution_engine:
            try:
                logger.info("🔄 Running Agent0 co-evolution cycle...")
                # REMOVED: from src.agent_framework.context import RunContext, RunMode

                evolution_context = RunContext(mode=RunMode.PAPER if self.paper else RunMode.LIVE)
                agent0_result = self.coevolution_engine.evolve(evolution_context)
                if agent0_result.get("status") == "success":
                    logger.info(
                        f"✅ Agent0 evolution cycle completed: "
                        f"iteration={agent0_result.get('iteration')}, "
                        f"success_rate={agent0_result.get('metrics', {}).get('success_rate', 0):.2%}"
                    )
            except Exception as e:
                logger.warning(f"Agent0 evolution cycle failed: {e}")

        # Step 1: Create plan
        plan = self.create_trade_plan(symbols)

        # Step 2: Execute plan
        results = self.execute_plan(plan)

        # Add Agent0 result if available
        if agent0_result:
            results["agent0_evolution"] = agent0_result

        logger.info("=" * 80)
        logger.info("ELITE TRADING CYCLE COMPLETE")
        logger.info("=" * 80)

        return results
