"""
Eval Engineering Skill for Automated Eval Generation.

Inspects repository structure (prompts, models, tools, skills, hooks, agents),
mines production traces, proposes eval tasks, and iteratively builds Harbor-format
evals with user approval. Based on LangChain's Eval Engineering Skill architecture.
"""

from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AgentComponent:
    """Discovered agent component from repo inspection."""

    name: str
    component_type: str  # "prompt", "tool", "skill", "hook", "agent", "model"
    file_path: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalProposal:
    """Proposed eval task for user review."""

    proposal_id: str
    title: str
    description: str
    category: str
    source: str  # "repo_inspection", "trace_mining", "user_request"
    affected_components: list[str]
    suggested_verifier_type: str  # "deterministic", "llm_judge", "hybrid"
    estimated_effort: str  # "low", "medium", "high"
    priority_score: float  # 0-1


@dataclass(frozen=True)
class EvalTask:
    """Complete Harbor-format eval task ready for execution."""

    task_id: str
    name: str
    description: str
    instruction_md: str
    task_toml: str
    environment_dockerfile: str
    test_files: dict[str, str]  # filename -> content
    verifier_code: str
    created_at: str
    approved: bool = False


class RepoInspector:
    """Inspects repository to map agent surface: prompts, tools, skills, hooks, agents."""

    def __init__(self, root: Path = ROOT):
        self.root = root
        self.src_root = root / "src"

    def inspect(self) -> list[AgentComponent]:
        """Full repo inspection returning discovered components."""
        components: list[AgentComponent] = []

        # Discover prompts
        components.extend(self._discover_prompts())

        # Discover tools
        components.extend(self._discover_tools())

        # Discover skills
        components.extend(self._discover_skills())

        # Discover hooks
        components.extend(self._discover_hooks())

        # Discover agents
        components.extend(self._discover_agents())

        # Discover models/config
        components.extend(self._discover_models())

        logger.info("Discovered %d agent components", len(components))
        return components

    def _discover_prompts(self) -> list[AgentComponent]:
        """Find prompt templates and system prompts."""
        components: list[AgentComponent] = []
        prompt_dirs = [
            self.src_root / "prompts",
            self.src_root / "agents",
            self.src_root / "orchestrator",
        ]

        for prompt_dir in prompt_dirs:
            if not prompt_dir.exists():
                continue
            for prompt_file in prompt_dir.rglob("*.py"):
                components.extend(self._parse_prompt_file(prompt_file))
            for prompt_file in prompt_dir.rglob("*.md"):
                components.extend(self._parse_prompt_md(prompt_file))

        return components

    def _parse_prompt_file(self, file_path: Path) -> list[AgentComponent]:
        """Parse Python file for prompt strings and templates."""
        components: list[AgentComponent] = []
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and "prompt" in target.id.lower():
                            if isinstance(node.value, ast.Constant) and isinstance(
                                node.value.value, str
                            ):
                                components.append(
                                    AgentComponent(
                                        name=target.id,
                                        component_type="prompt",
                                        file_path=str(file_path.relative_to(self.root)),
                                        description=f"Prompt template: {node.value.value[:100]}...",
                                        metadata={"full_prompt": node.value.value},
                                    )
                                )
        except Exception as exc:
            logger.debug("Failed to parse %s: %s", file_path, exc)
        return components

    def _parse_prompt_md(self, file_path: Path) -> list[AgentComponent]:
        """Parse markdown files for prompts."""
        components: list[AgentComponent] = []
        try:
            content = file_path.read_text(encoding="utf-8")
            # Look for prompt sections
            if "prompt" in content.lower() or "system" in content.lower():
                components.append(
                    AgentComponent(
                        name=file_path.stem,
                        component_type="prompt",
                        file_path=str(file_path.relative_to(self.root)),
                        description=f"Prompt document: {file_path.name}",
                        metadata={"content": content[:500]},
                    )
                )
        except Exception as exc:
            logger.debug("Failed to parse %s: %s", file_path, exc)
        return components

    def _discover_tools(self) -> list[AgentComponent]:
        """Discover tool definitions."""
        components: list[AgentComponent] = []
        tools_dir = self.src_root / "tools"
        if tools_dir.exists():
            for tool_file in tools_dir.rglob("*.py"):
                if tool_file.name.startswith("__"):
                    continue
                try:
                    content = tool_file.read_text(encoding="utf-8")
                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if node.name.startswith("tool_") or "tool" in node.name.lower():
                                components.append(
                                    AgentComponent(
                                        name=node.name,
                                        component_type="tool",
                                        file_path=str(tool_file.relative_to(self.root)),
                                        description=f"Tool function: {node.name}",
                                        metadata={"args": [arg.arg for arg in node.args.args]},
                                    )
                                )
                        elif isinstance(node, ast.ClassDef):
                            if "tool" in node.name.lower():
                                components.append(
                                    AgentComponent(
                                        name=node.name,
                                        component_type="tool",
                                        file_path=str(tool_file.relative_to(self.root)),
                                        description=f"Tool class: {node.name}",
                                        metadata={
                                            "methods": [
                                                n.name
                                                for n in node.body
                                                if isinstance(n, ast.FunctionDef)
                                            ]
                                        },
                                    )
                                )
                except Exception as exc:
                    logger.debug("Failed to parse %s: %s", tool_file, exc)
        return components

    def _discover_skills(self) -> list[AgentComponent]:
        """Discover skill definitions."""
        components: list[AgentComponent] = []
        skills_dir = self.src_root / "skills"
        if skills_dir.exists():
            for skill_file in skills_dir.rglob("*.py"):
                if skill_file.name.startswith("__"):
                    continue
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    if "skill" in content.lower() or "class.*Skill" in content:
                        components.append(
                            AgentComponent(
                                name=skill_file.stem,
                                component_type="skill",
                                file_path=str(skill_file.relative_to(self.root)),
                                description=f"Skill module: {skill_file.name}",
                                metadata={},
                            )
                        )
                except Exception as exc:
                    logger.debug("Failed to parse %s: %s", skill_file, exc)
        return components

    def _discover_hooks(self) -> list[AgentComponent]:
        """Discover hook definitions (pre/post tool, pre/post agent)."""
        components: list[AgentComponent] = []
        hooks_dir = self.src_root / "hooks"
        if not hooks_dir.exists():
            # Check common locations
            for loc in [self.src_root / "orchestration", self.src_root / "orchestrator"]:
                if (loc / "hooks.py").exists():
                    hooks_dir = loc
                    break

        if hooks_dir and hooks_dir.exists():
            for hook_file in hooks_dir.rglob("*.py"):
                if hook_file.name.startswith("__"):
                    continue
                try:
                    content = hook_file.read_text(encoding="utf-8")
                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            if "hook" in node.name.lower() or node.name.startswith(
                                ("pre_", "post_", "on_")
                            ):
                                components.append(
                                    AgentComponent(
                                        name=node.name,
                                        component_type="hook",
                                        file_path=str(hook_file.relative_to(self.root)),
                                        description=f"Hook: {node.name}",
                                        metadata={},
                                    )
                                )
                except Exception as exc:
                    logger.debug("Failed to parse %s: %s", hook_file, exc)
        return components

    def _discover_agents(self) -> list[AgentComponent]:
        """Discover agent definitions."""
        components: list[AgentComponent] = []
        agents_dir = self.src_root / "agents"
        if agents_dir.exists():
            for agent_file in agents_dir.rglob("*.py"):
                if agent_file.name.startswith("__"):
                    continue
                try:
                    content = agent_file.read_text(encoding="utf-8")
                    tree = ast.parse(content)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            if "agent" in node.name.lower() or any(
                                base.id == "Agent"
                                for base in node.bases
                                if isinstance(base, ast.Name)
                            ):
                                components.append(
                                    AgentComponent(
                                        name=node.name,
                                        component_type="agent",
                                        file_path=str(agent_file.relative_to(self.root)),
                                        description=f"Agent class: {node.name}",
                                        metadata={
                                            "methods": [
                                                n.name
                                                for n in node.body
                                                if isinstance(n, ast.FunctionDef)
                                            ]
                                        },
                                    )
                                )
                except Exception as exc:
                    logger.debug("Failed to parse %s: %s", agent_file, exc)
        return components

    def _discover_models(self) -> list[AgentComponent]:
        """Discover model configurations."""
        components: list[AgentComponent] = []
        config_files = [
            self.root / "config" / "models.yaml",
            self.root / "config" / "llm.yaml",
            self.root / ".env.example",
            self.root / "pyproject.toml",
        ]

        for config_file in config_files:
            if config_file.exists():
                components.append(
                    AgentComponent(
                        name=config_file.name,
                        component_type="model_config",
                        file_path=str(config_file.relative_to(self.root)),
                        description=f"Model configuration: {config_file.name}",
                        metadata={},
                    )
                )
        return components


class TraceAnalyzer:
    """Analyzes production traces to identify failure patterns and eval opportunities."""

    def __init__(self, trace_dir: Path | None = None):
        self.trace_dir = trace_dir or (ROOT / "data" / "audit" / "ralph_ticks")
        self.langsmith_project = None

    def analyze_traces(self, max_traces: int = 100) -> list[EvalProposal]:
        """Analyze traces and propose evals based on failure patterns."""
        proposals: list[EvalProposal] = []

        # Local trace files
        if self.trace_dir.exists():
            proposals.extend(self._analyze_local_traces(max_traces))

        # LangSmith traces (if configured)
        if self.langsmith_project:
            proposals.extend(self._analyze_langsmith_traces(max_traces))

        return proposals

    def _analyze_local_traces(self, max_traces: int) -> list[EvalProposal]:
        """Analyze local tick/audit JSON files."""
        proposals: list[EvalProposal] = []
        trace_files = sorted(self.trace_dir.glob("tick_*.json"))[-max_traces:]

        failure_patterns: dict[str, int] = {}
        tool_errors: dict[str, int] = {}

        for trace_file in trace_files:
            try:
                data = json.loads(trace_file.read_text(encoding="utf-8"))

                # Check for errors in trace
                if "error" in data and data["error"]:
                    error_type = data["error"].get("type", "unknown")
                    failure_patterns[error_type] = failure_patterns.get(error_type, 0) + 1

                # Check tool call failures
                for tool_call in data.get("tool_calls", []):
                    if tool_call.get("status") == "error":
                        tool_name = tool_call.get("name", "unknown")
                        tool_errors[tool_name] = tool_errors.get(tool_name, 0) + 1

            except Exception as exc:
                logger.debug("Failed to parse trace %s: %s", trace_file, exc)

        # Generate proposals from patterns
        for error_type, count in sorted(failure_patterns.items(), key=lambda x: -x[1]):
            if count >= 2:  # Recurring failure
                proposals.append(
                    EvalProposal(
                        proposal_id=f"trace_failure_{error_type}_{datetime.now().strftime('%Y%m%d')}",
                        title=f"Recurring {error_type} failures ({count} occurrences)",
                        description=f"Production traces show {count} instances of {error_type}. Build eval to prevent regression.",
                        category="regression",
                        source="trace_mining",
                        affected_components=[error_type],
                        suggested_verifier_type="deterministic",
                        estimated_effort="low",
                        priority_score=min(0.9, 0.5 + count * 0.1),
                    )
                )

        for tool_name, count in sorted(tool_errors.items(), key=lambda x: -x[1]):
            if count >= 2:
                proposals.append(
                    EvalProposal(
                        proposal_id=f"tool_failure_{tool_name}_{datetime.now().strftime('%Y%m%d')}",
                        title=f"Tool {tool_name} failures ({count} occurrences)",
                        description=f"Tool {tool_name} failed {count} times in production. Build eval for tool contract.",
                        category="tool_reliability",
                        source="trace_mining",
                        affected_components=[tool_name],
                        suggested_verifier_type="hybrid",
                        estimated_effort="medium",
                        priority_score=min(0.85, 0.4 + count * 0.1),
                    )
                )

        return proposals

    def _analyze_langsmith_traces(self, max_traces: int) -> list[EvalProposal]:
        """Analyze LangSmith traces (placeholder for future integration)."""
        # TODO: Implement LangSmith API integration
        return []


class EvalProposalEngine:
    """Generates eval proposals from repo inspection and trace analysis."""

    def __init__(
        self, inspector: RepoInspector | None = None, analyzer: TraceAnalyzer | None = None
    ):
        self.inspector = inspector or RepoInspector()
        self.analyzer = analyzer or TraceAnalyzer()

    def generate_proposals(self) -> list[EvalProposal]:
        """Generate eval proposals from all sources."""
        proposals: list[EvalProposal] = []

        # 1. From repo inspection - critical components that need testing
        components = self.inspector.inspect()
        proposals.extend(self._propose_from_components(components))

        # 2. From trace analysis - recurring failures
        proposals.extend(self.analyzer.analyze_traces())

        # 3. From existing eval gaps
        proposals.extend(self._propose_from_existing_evals())

        # Sort by priority
        proposals.sort(key=lambda p: -p.priority_score)
        return proposals

    def _propose_from_components(self, components: list[AgentComponent]) -> list[EvalProposal]:
        """Propose evals for critical agent components."""
        proposals: list[EvalProposal] = []

        # Group by type
        by_type: dict[str, list[AgentComponent]] = {}
        for comp in components:
            by_type.setdefault(comp.component_type, []).append(comp)

        # High-priority: agents and tools
        for comp in by_type.get("agent", []):
            proposals.append(
                EvalProposal(
                    proposal_id=f"agent_{comp.name}",
                    title=f"Agent behavior: {comp.name}",
                    description=f"Test {comp.name} agent decision making and tool usage patterns.",
                    category="agent_behavior",
                    source="repo_inspection",
                    affected_components=[comp.name],
                    suggested_verifier_type="hybrid",
                    estimated_effort="high",
                    priority_score=0.9,
                )
            )

        for comp in by_type.get("tool", []):
            proposals.append(
                EvalProposal(
                    proposal_id=f"tool_{comp.name}",
                    title=f"Tool contract: {comp.name}",
                    description=f"Validate {comp.name} tool input/output contract and error handling.",
                    category="tool_contract",
                    source="repo_inspection",
                    affected_components=[comp.name],
                    suggested_verifier_type="deterministic",
                    estimated_effort="low",
                    priority_score=0.8,
                )
            )

        for comp in by_type.get("skill", []):
            proposals.append(
                EvalProposal(
                    proposal_id=f"skill_{comp.name}",
                    title=f"Skill execution: {comp.name}",
                    description=f"Test {comp.name} skill end-to-end with realistic inputs.",
                    category="skill_execution",
                    source="repo_inspection",
                    affected_components=[comp.name],
                    suggested_verifier_type="llm_judge",
                    estimated_effort="medium",
                    priority_score=0.75,
                )
            )

        return proposals

    def _propose_from_existing_evals(self) -> list[EvalProposal]:
        """Identify gaps in existing eval coverage."""
        proposals: list[EvalProposal] = []

        # Check existing eval dataset
        eval_dataset = ROOT / "data" / "eval" / "eval_dataset.jsonl"
        existing_categories: set[str] = set()

        if eval_dataset.exists():
            for line in eval_dataset.read_text(encoding="utf-8").strip().split("\n"):
                if line:
                    try:
                        case = json.loads(line)
                        existing_categories.add(case.get("category", "unknown"))
                    except Exception:
                        pass

        # Propose missing critical categories
        critical_categories = {
            "bank_surplus": "Bank adapter surplus withdrawal logic",
            "risk_gate": "Drawdown circuit breaker behavior",
            "order_idempotency": "Order idempotency key validation",
            "rth_schedule": "Regular trading hours schedule compliance",
            "position_sizing": "Position size limit enforcement",
            "option_greeks": "Option greeks calculation accuracy",
            "trade_execution": "End-to-end trade execution flow",
        }

        for category, description in critical_categories.items():
            if category not in existing_categories:
                proposals.append(
                    EvalProposal(
                        proposal_id=f"missing_{category}",
                        title=f"Missing eval coverage: {category}",
                        description=f"No evals found for {description}. Critical for production safety.",
                        category=category,
                        source="eval_gap",
                        affected_components=[category],
                        suggested_verifier_type="deterministic",
                        estimated_effort="low",
                        priority_score=0.85,
                    )
                )

        return proposals
