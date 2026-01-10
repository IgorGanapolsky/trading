"""
Adaptive Agent Organization Orchestrator

Implements dynamic agent organization that adapts to:
- Task complexity
- Market regime
- Historical performance
- Real-time conditions

Based on research: Multi-agent systems with adaptive organization outperform
fixed chains/trees/graphs by reorganizing agents as tasks evolve.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.core.skills_integration import get_skills
from src.orchestration.context_engine import get_context_engine
from src.orchestration.shared_types import AgentType, PlanningPhase, TradePlan

# Market regime detector (not yet implemented)
MarketRegimeDetector = None


logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    """Task complexity levels"""

    SIMPLE = "simple"  # Low uncertainty, clear signals
    MODERATE = "moderate"  # Standard trading decision
    COMPLEX = "complex"  # High uncertainty, multiple factors
    CRITICAL = "critical"  # High-value or high-risk decision


class OrganizationPattern(Enum):
    """Agent organization patterns"""

    LINEAR = "linear"  # Sequential chain: A → B → C
    PARALLEL = "parallel"  # Parallel execution: A, B, C simultaneously
    HIERARCHICAL = "hierarchical"  # Tree: Root → Branch1, Branch2
    MESH = "mesh"  # Graph: Agents connect dynamically
    FAST_TRACK = "fast_track"  # Minimal agents, fast path


@dataclass
class AgentOrganization:
    """Dynamic agent organization configuration"""

    pattern: OrganizationPattern
    phases: dict[str, dict[str, Any]]
    agent_assignments: dict[str, list[str]]
    execution_order: list[str]
    parallel_groups: list[list[str]] = field(default_factory=list)
    rationale: str = ""


@dataclass
class ComplexityAssessment:
    """Task complexity assessment result"""

    complexity: TaskComplexity
    score: float  # 0.0 (simple) to 1.0 (critical)
    factors: dict[str, float]
    rationale: str = ""


@dataclass
class OrganizationPerformance:
    """Performance metrics for agent organization"""

    organization_id: str
    pattern: OrganizationPattern
    complexity: TaskComplexity
    market_regime: str
    execution_time_ms: float
    success: bool
    profit: float = 0.0
    confidence: float = 0.0
    timestamp: str = ""


class AdaptiveOrchestrator:
    """
    Adaptive Agent Organization Orchestrator

    Dynamically reorganizes agents based on:
    1. Task complexity assessment
    2. Market regime detection
    3. Historical performance learning
    4. Real-time conditions
    """

    def __init__(self, paper: bool = True, enable_learning: bool = True):
        """
        Initialize Adaptive Orchestrator

        Args:
            paper: Paper trading mode
            enable_learning: Enable performance-based learning
        """
        self.paper = paper
        self.enable_learning = enable_learning

        # Core components
        self.skills = get_skills()
        self.regime_detector = MarketRegimeDetector() if MarketRegimeDetector else None
        self.context_engine = get_context_engine()

        # Performance learning storage
        self.performance_dir = Path("data/adaptive_organization")
        self.performance_dir.mkdir(parents=True, exist_ok=True)
        self.performance_file = self.performance_dir / "organization_performance.jsonl"

        # Load historical performance
        self.performance_history: list[OrganizationPerformance] = []
        self._load_performance_history()

        # Organization templates for different scenarios
        self._initialize_organization_templates()

        logger.info("✅ Adaptive Orchestrator initialized")
        logger.info(f"   Learning: {'Enabled' if enable_learning else 'Disabled'}")
        logger.info(f"   Historical patterns: {len(self.performance_history)}")

    def _initialize_organization_templates(self):
        """Initialize organization templates for different scenarios"""
        self.templates = {
            # Simple task templates
            (TaskComplexity.SIMPLE, "BULL"): self._create_fast_track_plan,
            (TaskComplexity.SIMPLE, "BEAR"): self._create_fast_track_plan,
            (TaskComplexity.SIMPLE, "SIDEWAYS"): self._create_linear_plan,
            # Moderate task templates
            (TaskComplexity.MODERATE, "BULL"): self._create_parallel_plan,
            (TaskComplexity.MODERATE, "BEAR"): self._create_hierarchical_plan,
            (TaskComplexity.MODERATE, "SIDEWAYS"): self._create_parallel_plan,
            # Complex task templates
            (TaskComplexity.COMPLEX, "BULL"): self._create_mesh_plan,
            (TaskComplexity.COMPLEX, "BEAR"): self._create_hierarchical_plan,
            (TaskComplexity.COMPLEX, "SIDEWAYS"): self._create_mesh_plan,
            # Critical task templates
            (TaskComplexity.CRITICAL, "BULL"): self._create_mesh_plan,
            (TaskComplexity.CRITICAL, "BEAR"): self._create_hierarchical_plan,
            (TaskComplexity.CRITICAL, "SIDEWAYS"): self._create_mesh_plan,
        }

    def create_adaptive_plan(
        self, symbols: list[str], context: dict[str, Any] | None = None
    ) -> TradePlan:
        """
        Create an adaptive trade plan with dynamic agent organization

        Args:
            symbols: Symbols to trade
            context: Additional context

        Returns:
            TradePlan with adaptive agent organization
        """
        # Step 1: Assess task complexity
        complexity = self.assess_complexity(symbols, context or {})

        # Step 2: Detect market regime
        market_regime = self._detect_market_regime(symbols)

        # Step 3: Select optimal organization based on complexity + regime
        organization = self._select_organization(complexity, market_regime, symbols, context or {})

        # Step 4: Create trade plan with adaptive organization
        plan_id = f"adaptive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        plan = TradePlan(
            plan_id=plan_id,
            timestamp=datetime.now().isoformat(),
            symbols=symbols,
            context={
                **(context or {}),
                "complexity": complexity.complexity.value,
                "complexity_score": complexity.score,
                "market_regime": market_regime,
                "organization_pattern": organization.pattern.value,
                "organization_rationale": organization.rationale,
            },
        )

        # Apply adaptive organization to phases
        plan.phases = organization.phases

        logger.info(f"📋 Created adaptive plan: {plan_id}")
        logger.info(f"   Complexity: {complexity.complexity.value} (score: {complexity.score:.2f})")
        logger.info(f"   Market Regime: {market_regime}")
        logger.info(f"   Organization: {organization.pattern.value}")
        logger.info(f"   Rationale: {organization.rationale}")

        return plan

    def assess_complexity(
        self, symbols: list[str], context: dict[str, Any]
    ) -> ComplexityAssessment:
        """
        Assess task complexity based on multiple factors

        Args:
            symbols: Trading symbols
            context: Task context

        Returns:
            ComplexityAssessment with score and rationale
        """
        factors = {}

        # Factor 1: Number of symbols (more symbols = more complex)
        num_symbols = len(symbols)
        factors["symbol_count"] = min(1.0, num_symbols / 5.0)  # Normalize to 0-1

        # Factor 2: Market volatility (higher volatility = more complex)
        volatility = context.get("volatility", 0.0)
        factors["volatility"] = min(1.0, volatility / 0.3)  # Normalize to 0-1

        # Factor 3: Position size (larger positions = more complex)
        position_size = context.get("position_size", 0.0)
        account_value = context.get("account_value", 100000.0)
        position_pct = position_size / account_value if account_value > 0 else 0.0
        factors["position_size"] = min(1.0, position_pct / 0.1)  # 10% = max complexity

        # Factor 4: Uncertainty (from context or calculated)
        uncertainty = context.get("uncertainty", 0.5)
        factors["uncertainty"] = uncertainty

        # Factor 5: Historical performance (poor performance = more complex)
        recent_performance = self._get_recent_performance(symbols)
        factors["recent_performance"] = 1.0 - recent_performance  # Inverse

        # Calculate weighted complexity score
        weights = {
            "symbol_count": 0.15,
            "volatility": 0.25,
            "position_size": 0.20,
            "uncertainty": 0.25,
            "recent_performance": 0.15,
        }

        complexity_score = sum(weights[k] * factors[k] for k in weights)

        # Determine complexity level
        if complexity_score < 0.3:
            complexity = TaskComplexity.SIMPLE
        elif complexity_score < 0.5:
            complexity = TaskComplexity.MODERATE
        elif complexity_score < 0.7:
            complexity = TaskComplexity.COMPLEX
        else:
            complexity = TaskComplexity.CRITICAL

        rationale = (
            f"Complexity assessed as {complexity.value} (score: {complexity_score:.2f}). "
            f"Factors: volatility={factors['volatility']:.2f}, "
            f"position_size={factors['position_size']:.2f}, "
            f"uncertainty={factors['uncertainty']:.2f}"
        )

        return ComplexityAssessment(
            complexity=complexity,
            score=complexity_score,
            factors=factors,
            rationale=rationale,
        )

    def _detect_market_regime(self, symbols: list[str]) -> str:
        """
        Detect current market regime

        Args:
            symbols: Trading symbols

        Returns:
            Market regime string (BULL, BEAR, SIDEWAYS)
        """
        try:
            # Use first symbol for regime detection
            if symbols and self.skills.financial_data_fetcher:
                price_data = self.skills.get_price_data(
                    symbols=symbols[:1], timeframe="1Day", limit=30
                )

                if price_data and "data" in price_data:
                    prices = [bar.get("close", 0) for bar in price_data["data"]]
                    if prices and self.regime_detector:
                        try:
                            import numpy as np

                            prices_array = np.array(prices)
                            regime_result = self.regime_detector.detect(prices_array)
                            return regime_result.get("regime", "SIDEWAYS")
                        except Exception:
                            pass

        except Exception as e:
            logger.warning(f"Regime detection failed: {e}")

        return "SIDEWAYS"  # Default

    def _select_organization(
        self,
        complexity: ComplexityAssessment,
        market_regime: str,
        symbols: list[str],
        context: dict[str, Any],
    ) -> AgentOrganization:
        """
        Select optimal agent organization based on complexity and regime

        Args:
            complexity: Task complexity assessment
            market_regime: Market regime string
            symbols: Trading symbols
            context: Task context

        Returns:
            AgentOrganization with dynamic structure
        """
        # Check if we have learned a better organization
        learned_org = self._get_learned_organization(complexity, market_regime)
        if learned_org:
            logger.info("📚 Using learned organization pattern")
            return learned_org

        # Use template-based organization
        template_key = (complexity.complexity, market_regime)
        template_func = self.templates.get(template_key, self._create_parallel_plan)

        organization = template_func(complexity, market_regime, symbols, context)

        return organization

    def _create_fast_track_plan(
        self,
        complexity: ComplexityAssessment,
        market_regime: str,
        symbols: list[str],
        context: dict[str, Any],
    ) -> AgentOrganization:
        """Create fast-track plan for simple tasks"""
        phases = {
            PlanningPhase.INITIALIZE.value: {
                "description": "Quick initialization",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Load portfolio state", "Check market hours"],
                "status": "pending",
            },
            PlanningPhase.ANALYSIS.value: {
                "description": "Streamlined analysis",
                "agents": [AgentType.ML_MODEL.value, AgentType.MCP.value],
                "tasks": ["ML signal", "Quick validation"],
                "status": "pending",
            },
            PlanningPhase.RISK_ASSESSMENT.value: {
                "description": "Basic risk check",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Position sizing"],
                "status": "pending",
            },
            PlanningPhase.EXECUTION.value: {
                "description": "Fast execution",
                "agents": [AgentType.GO_ADK.value],
                "tasks": ["Order placement"],
                "status": "pending",
            },
        }

        return AgentOrganization(
            pattern=OrganizationPattern.FAST_TRACK,
            phases=phases,
            agent_assignments={
                "initialize": [AgentType.CLAUDE_SKILLS.value],
                "analysis": [AgentType.ML_MODEL.value, AgentType.MCP.value],
                "risk": [AgentType.CLAUDE_SKILLS.value],
                "execution": [AgentType.GO_ADK.value],
            },
            execution_order=["initialize", "analysis", "risk", "execution"],
            rationale="Fast-track plan: Simple task, minimal agents for speed",
        )

    def _create_linear_plan(
        self,
        complexity: ComplexityAssessment,
        market_regime: str,
        symbols: list[str],
        context: dict[str, Any],
    ) -> AgentOrganization:
        """Create linear sequential plan"""
        phases = {
            PlanningPhase.INITIALIZE.value: {
                "description": "Initialize",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Load portfolio state", "Check market hours"],
                "status": "pending",
            },
            PlanningPhase.DATA_COLLECTION.value: {
                "description": "Collect data",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Fetch price data"],
                "status": "pending",
            },
            PlanningPhase.ANALYSIS.value: {
                "description": "Analyze",
                "agents": [AgentType.ML_MODEL.value],
                "tasks": ["Generate signal"],
                "status": "pending",
            },
            PlanningPhase.RISK_ASSESSMENT.value: {
                "description": "Assess risk",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Position sizing", "Stop-loss"],
                "status": "pending",
            },
            PlanningPhase.EXECUTION.value: {
                "description": "Execute",
                "agents": [AgentType.MCP.value],
                "tasks": ["Order placement"],
                "status": "pending",
            },
        }

        return AgentOrganization(
            pattern=OrganizationPattern.LINEAR,
            phases=phases,
            agent_assignments={
                "initialize": [AgentType.CLAUDE_SKILLS.value],
                "data_collection": [AgentType.CLAUDE_SKILLS.value],
                "analysis": [AgentType.ML_MODEL.value],
                "risk": [AgentType.CLAUDE_SKILLS.value],
                "execution": [AgentType.MCP.value],
            },
            execution_order=["initialize", "data_collection", "analysis", "risk", "execution"],
            rationale="Linear plan: Sequential execution for moderate complexity",
        )

    def _create_parallel_plan(
        self,
        complexity: ComplexityAssessment,
        market_regime: str,
        symbols: list[str],
        context: dict[str, Any],
    ) -> AgentOrganization:
        """Create parallel execution plan"""
        phases = {
            PlanningPhase.INITIALIZE.value: {
                "description": "Initialize",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Load portfolio state", "Check market hours"],
                "status": "pending",
            },
            PlanningPhase.DATA_COLLECTION.value: {
                "description": "Parallel data collection",
                "agents": [
                    AgentType.CLAUDE_SKILLS.value,
                    AgentType.GEMINI.value,
                ],
                "tasks": ["Fetch price data", "Retrieve sentiment", "Gather research"],
                "status": "pending",
                "parallel": True,
            },
            PlanningPhase.ANALYSIS.value: {
                "description": "Parallel analysis",
                "agents": [
                    AgentType.ML_MODEL.value,
                    AgentType.MCP.value,
                    AgentType.GEMINI.value,
                ],
                "tasks": ["ML signal", "MCP analysis", "Gemini research"],
                "status": "pending",
                "parallel": True,
            },
            PlanningPhase.RISK_ASSESSMENT.value: {
                "description": "Risk validation",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Position sizing", "Stop-loss", "Circuit breaker"],
                "status": "pending",
            },
            PlanningPhase.EXECUTION.value: {
                "description": "Execute",
                "agents": [AgentType.GO_ADK.value, AgentType.MCP.value],
                "tasks": ["Order placement", "Monitoring"],
                "status": "pending",
            },
        }

        return AgentOrganization(
            pattern=OrganizationPattern.PARALLEL,
            phases=phases,
            agent_assignments={
                "initialize": [AgentType.CLAUDE_SKILLS.value],
                "data_collection": [
                    AgentType.CLAUDE_SKILLS.value,
                    AgentType.GEMINI.value,
                ],
                "analysis": [
                    AgentType.ML_MODEL.value,
                    AgentType.MCP.value,
                    AgentType.GEMINI.value,
                ],
                "risk": [AgentType.CLAUDE_SKILLS.value],
                "execution": [AgentType.GO_ADK.value, AgentType.MCP.value],
            },
            execution_order=["initialize", "data_collection", "analysis", "risk", "execution"],
            parallel_groups=[
                ["data_collection"],
                ["analysis"],
            ],
            rationale="Parallel plan: Concurrent agents for moderate complexity",
        )

    def _create_hierarchical_plan(
        self,
        complexity: ComplexityAssessment,
        market_regime: str,
        symbols: list[str],
        context: dict[str, Any],
    ) -> AgentOrganization:
        """Create hierarchical tree plan"""
        phases = {
            PlanningPhase.INITIALIZE.value: {
                "description": "Initialize",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Load portfolio state", "Check market hours", "Validate account"],
                "status": "pending",
            },
            PlanningPhase.DATA_COLLECTION.value: {
                "description": "Hierarchical data collection",
                "agents": [AgentType.CLAUDE_SKILLS.value],  # Coordinator
                "tasks": ["Coordinate data collection"],
                "status": "pending",
                "sub_agents": {
                    "price_data": [AgentType.CLAUDE_SKILLS.value],
                    "research": [AgentType.GEMINI.value],
                },
            },
            PlanningPhase.ANALYSIS.value: {
                "description": "Hierarchical analysis",
                "agents": [AgentType.CLAUDE_SKILLS.value],  # Meta-coordinator
                "tasks": ["Coordinate analysis"],
                "status": "pending",
                "sub_agents": {
                    "technical": [AgentType.ML_MODEL.value, AgentType.MCP.value],
                    "fundamental": [AgentType.GEMINI.value],
                },
            },
            PlanningPhase.RISK_ASSESSMENT.value: {
                "description": "Enhanced risk assessment",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": [
                    "Portfolio health check",
                    "Position sizing",
                    "Stop-loss calculation",
                    "Circuit breaker check",
                    "Drawdown monitoring",
                ],
                "status": "pending",
            },
            PlanningPhase.EXECUTION.value: {
                "description": "Supervised execution",
                "agents": [AgentType.CLAUDE_SKILLS.value],  # Supervisor
                "tasks": ["Supervise execution"],
                "status": "pending",
                "sub_agents": {
                    "execution": [AgentType.GO_ADK.value, AgentType.MCP.value],
                    "monitoring": [AgentType.CLAUDE_SKILLS.value],
                },
            },
        }

        return AgentOrganization(
            pattern=OrganizationPattern.HIERARCHICAL,
            phases=phases,
            agent_assignments={
                "initialize": [AgentType.CLAUDE_SKILLS.value],
                "data_collection": [
                    AgentType.CLAUDE_SKILLS.value,
                    AgentType.GEMINI.value,
                ],
                "analysis": [
                    AgentType.CLAUDE_SKILLS.value,
                    AgentType.ML_MODEL.value,
                    AgentType.MCP.value,
                    AgentType.GEMINI.value,
                ],
                "risk": [AgentType.CLAUDE_SKILLS.value],
                "execution": [
                    AgentType.CLAUDE_SKILLS.value,
                    AgentType.GO_ADK.value,
                    AgentType.MCP.value,
                ],
            },
            execution_order=["initialize", "data_collection", "analysis", "risk", "execution"],
            rationale="Hierarchical plan: Tree structure for complex/critical tasks",
        )

    def _create_mesh_plan(
        self,
        complexity: ComplexityAssessment,
        market_regime: str,
        symbols: list[str],
        context: dict[str, Any],
    ) -> AgentOrganization:
        """Create mesh/graph plan with dynamic connections"""
        phases = {
            PlanningPhase.INITIALIZE.value: {
                "description": "Initialize",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": ["Load portfolio state", "Check market hours", "Validate account"],
                "status": "pending",
            },
            PlanningPhase.DATA_COLLECTION.value: {
                "description": "Mesh data collection",
                "agents": [
                    AgentType.CLAUDE_SKILLS.value,
                    AgentType.GEMINI.value,
                ],
                "tasks": ["Fetch price data", "Retrieve sentiment", "Gather research"],
                "status": "pending",
                "mesh": True,  # Agents can communicate with each other
            },
            PlanningPhase.ANALYSIS.value: {
                "description": "Mesh analysis with consensus",
                "agents": [
                    AgentType.ML_MODEL.value,
                    AgentType.MCP.value,
                    AgentType.GEMINI.value,
                    "gamma_agent",
                    "bogleheads_agent",
                ],
                "tasks": [
                    "Technical analysis",
                    "Fundamental analysis",
                    "Sentiment analysis",
                    "Gamma exposure",
                    "Bogleheads validation",
                    "Ensemble consensus",
                ],
                "status": "pending",
                "mesh": True,  # Full agent-to-agent communication
                "consensus_required": True,
            },
            PlanningPhase.RISK_ASSESSMENT.value: {
                "description": "Comprehensive risk assessment",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": [
                    "Portfolio health check",
                    "Position sizing",
                    "Stop-loss calculation",
                    "Circuit breaker check",
                    "Drawdown monitoring",
                    "Correlation analysis",
                ],
                "status": "pending",
            },
            PlanningPhase.EXECUTION.value: {
                "description": "Supervised execution with monitoring",
                "agents": [AgentType.GO_ADK.value, AgentType.MCP.value],
                "tasks": ["Order placement", "Real-time monitoring", "Anomaly detection"],
                "status": "pending",
            },
            PlanningPhase.AUDIT.value: {
                "description": "Comprehensive audit",
                "agents": [AgentType.CLAUDE_SKILLS.value],
                "tasks": [
                    "Performance tracking",
                    "Trade logging",
                    "Organization learning",
                    "Git commit",
                ],
                "status": "pending",
            },
        }

        return AgentOrganization(
            pattern=OrganizationPattern.MESH,
            phases=phases,
            agent_assignments={
                "initialize": [AgentType.CLAUDE_SKILLS.value],
                "data_collection": [
                    AgentType.CLAUDE_SKILLS.value,
                    AgentType.GEMINI.value,
                ],
                "analysis": [
                    AgentType.ML_MODEL.value,
                    AgentType.MCP.value,
                    AgentType.GEMINI.value,
                    "gamma_agent",
                    "bogleheads_agent",
                ],
                "risk": [AgentType.CLAUDE_SKILLS.value],
                "execution": [AgentType.GO_ADK.value, AgentType.MCP.value],
                "audit": [AgentType.CLAUDE_SKILLS.value],
            },
            execution_order=[
                "initialize",
                "data_collection",
                "analysis",
                "risk",
                "execution",
                "audit",
            ],
            rationale="Mesh plan: Full agent connectivity for complex/critical tasks",
        )

    def _get_recent_performance(self, symbols: list[str]) -> float:
        """Get recent performance score for symbols (0.0 = poor, 1.0 = excellent)"""
        if not self.performance_history:
            return 0.5  # Neutral

        # Filter recent performance for these symbols
        recent = [
            p
            for p in self.performance_history
            if p.timestamp and (datetime.now() - datetime.fromisoformat(p.timestamp)).days < 7
        ]

        if not recent:
            return 0.5

        # Calculate average success rate
        success_rate = sum(1 for p in recent if p.success) / len(recent)
        return success_rate

    def _get_learned_organization(
        self, complexity: ComplexityAssessment, market_regime: str
    ) -> AgentOrganization | None:
        """Get learned optimal organization from historical performance"""
        if not self.enable_learning or not self.performance_history:
            return None

        # Find best performing organization for this complexity + regime
        matching = [
            p
            for p in self.performance_history
            if p.complexity == complexity.complexity and p.market_regime == market_regime
        ]

        if not matching:
            return None

        # Sort by performance (success + profit)
        matching.sort(
            key=lambda p: (1 if p.success else 0) * 0.7 + min(1.0, p.profit / 1000.0) * 0.3,
            reverse=True,
        )

        best = matching[0]
        logger.info(f"📚 Learned pattern: {best.pattern.value} (success: {best.success})")

        # Reconstruct organization from best pattern
        # (In production, we'd store full organization config)
        if best.pattern == OrganizationPattern.FAST_TRACK:
            return self._create_fast_track_plan(complexity, market_regime, [], {})
        elif best.pattern == OrganizationPattern.LINEAR:
            return self._create_linear_plan(complexity, market_regime, [], {})
        elif best.pattern == OrganizationPattern.PARALLEL:
            return self._create_parallel_plan(complexity, market_regime, [], {})
        elif best.pattern == OrganizationPattern.HIERARCHICAL:
            return self._create_hierarchical_plan(complexity, market_regime, [], {})
        elif best.pattern == OrganizationPattern.MESH:
            return self._create_mesh_plan(complexity, market_regime, [], {})

        return None

    def record_performance(
        self,
        organization: AgentOrganization,
        complexity: ComplexityAssessment,
        market_regime: str,
        execution_time_ms: float,
        success: bool,
        profit: float = 0.0,
        confidence: float = 0.0,
    ):
        """
        Record organization performance for learning

        Args:
            organization: Agent organization used
            complexity: Task complexity
            market_regime: Market regime
            execution_time_ms: Execution time
            success: Whether execution was successful
            profit: Profit/loss from trade
            confidence: Confidence in decision
        """
        if not self.enable_learning:
            return

        org_id = f"{organization.pattern.value}_{complexity.complexity.value}_{market_regime}"

        performance = OrganizationPerformance(
            organization_id=org_id,
            pattern=organization.pattern,
            complexity=complexity.complexity,
            market_regime=market_regime,
            execution_time_ms=execution_time_ms,
            success=success,
            profit=profit,
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
        )

        # Save to file
        with open(self.performance_file, "a") as f:
            f.write(json.dumps(asdict(performance), default=str) + "\n")

        # Add to memory
        self.performance_history.append(performance)

        # Keep only recent history (last 1000 entries)
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]

        logger.info(
            f"📊 Recorded performance: {org_id} (success: {success}, profit: ${profit:.2f})"
        )

    def _load_performance_history(self):
        """Load historical performance data"""
        if not self.performance_file.exists():
            return

        try:
            with open(self.performance_file) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        # Convert enum strings back to enums
                        data["pattern"] = OrganizationPattern(data["pattern"])
                        data["complexity"] = TaskComplexity(data["complexity"])
                        self.performance_history.append(OrganizationPerformance(**data))

            logger.info(f"📚 Loaded {len(self.performance_history)} performance records")
        except Exception as e:
            logger.warning(f"Failed to load performance history: {e}")
