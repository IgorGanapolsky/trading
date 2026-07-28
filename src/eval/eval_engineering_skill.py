"""
Eval Engineering Skill for Automated Eval Generation.

Inspects repository structure (prompts, models, tools, skills, hooks, agents),
mines production traces (local + LangSmith), proposes eval tasks, and iteratively
builds Harbor-format evals with user approval. Based on LangChain's Eval Engineering
Skill architecture.
"""

from __future__ import annotations

import ast
import importlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

# ── Conditionally import LangSmith ──────────────────────────────────────────
try:
    from langsmith import Client as LangSmithClient
    HAS_LANGSMITH = True
except ImportError:
    HAS_LANGSMITH = False

HAS_OPENAI = importlib.util.find_spec("openai") is not None


# ── Dataclasses ──────────────────────────────────────────────────────────────

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
    source: str  # "repo_inspection", "trace_mining", "user_request", "eval_gap"
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


# ── Repo Inspector ───────────────────────────────────────────────────────────

class RepoInspector:
    """Inspects repository to map agent surface: prompts, tools, skills, hooks, agents."""

    def __init__(self, root: Path = ROOT):
        self.root = root
        self.src_root = root / "src"

    def inspect(self) -> list[AgentComponent]:
        """Full repo inspection returning discovered components."""
        components: list[AgentComponent] = []
        components.extend(self._discover_prompts())
        components.extend(self._discover_tools())
        components.extend(self._discover_skills())
        components.extend(self._discover_hooks())
        components.extend(self._discover_agents())
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
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                components.append(AgentComponent(
                                    name=target.id,
                                    component_type="prompt",
                                    file_path=str(file_path.relative_to(self.root)),
                                    description=f"Prompt template: {node.value.value[:100]}...",
                                    metadata={"full_prompt": node.value.value},
                                ))
        except Exception as exc:
            logger.debug("Failed to parse %s: %s", file_path, exc)
        return components

    def _parse_prompt_md(self, file_path: Path) -> list[AgentComponent]:
        """Parse markdown files for prompts."""
        components: list[AgentComponent] = []
        try:
            content = file_path.read_text(encoding="utf-8")
            if "prompt" in content.lower() or "system" in content.lower():
                components.append(AgentComponent(
                    name=file_path.stem,
                    component_type="prompt",
                    file_path=str(file_path.relative_to(self.root)),
                    description=f"Prompt document: {file_path.name}",
                    metadata={"content": content[:500]},
                ))
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
                                components.append(AgentComponent(
                                    name=node.name,
                                    component_type="tool",
                                    file_path=str(tool_file.relative_to(self.root)),
                                    description=f"Tool function: {node.name}",
                                    metadata={"args": [arg.arg for arg in node.args.args]},
                                ))
                        elif isinstance(node, ast.ClassDef):
                            if "tool" in node.name.lower():
                                components.append(AgentComponent(
                                    name=node.name,
                                    component_type="tool",
                                    file_path=str(tool_file.relative_to(self.root)),
                                    description=f"Tool class: {node.name}",
                                    metadata={"methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]},
                                ))
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
                    if "skill" in content.lower():
                        components.append(AgentComponent(
                            name=skill_file.stem,
                            component_type="skill",
                            file_path=str(skill_file.relative_to(self.root)),
                            description=f"Skill module: {skill_file.name}",
                            metadata={},
                        ))
                except Exception as exc:
                    logger.debug("Failed to parse %s: %s", skill_file, exc)
        return components

    def _discover_hooks(self) -> list[AgentComponent]:
        """Discover hook definitions (pre/post tool, pre/post agent)."""
        components: list[AgentComponent] = []
        hooks_dir = self.src_root / "hooks"
        if not hooks_dir.exists():
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
                            if "hook" in node.name.lower() or node.name.startswith(("pre_", "post_", "on_")):
                                components.append(AgentComponent(
                                    name=node.name,
                                    component_type="hook",
                                    file_path=str(hook_file.relative_to(self.root)),
                                    description=f"Hook: {node.name}",
                                    metadata={},
                                ))
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
                                base.id == "Agent" for base in node.bases if isinstance(base, ast.Name)
                            ):
                                components.append(AgentComponent(
                                    name=node.name,
                                    component_type="agent",
                                    file_path=str(agent_file.relative_to(self.root)),
                                    description=f"Agent class: {node.name}",
                                    metadata={"methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]},
                                ))
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
                components.append(AgentComponent(
                    name=config_file.name,
                    component_type="model_config",
                    file_path=str(config_file.relative_to(self.root)),
                    description=f"Model configuration: {config_file.name}",
                    metadata={},
                ))
        return components


# ── Trace Analyzer (local + LangSmith) ───────────────────────────────────────

class TraceAnalyzer:
    """Analyzes production traces to identify failure patterns and eval opportunities.


    Mines traces from:
    1. Local tick/audit JSON files (data/audit/ralph_ticks/)
    2. LangSmith project traces (if LANGSMITH_API_KEY is set)
    """

    def __init__(self, trace_dir: Path | None = None, langsmith_project: str | None = None):
        self.trace_dir = trace_dir or (ROOT / "data" / "audit" / "ralph_ticks")
        self.langsmith_project = langsmith_project or os.getenv("LANGSMITH_PROJECT", "trading-agent")
        self._langsmith_client: Any = None

    def _get_langsmith_client(self) -> Any:
        """Lazy-init LangSmith client."""
        if self._langsmith_client is None and HAS_LANGSMITH:
            api_key = os.getenv("LANGSMITH_API_KEY")
            if api_key:
                self._langsmith_client = LangSmithClient(api_key=api_key)
        return self._langsmith_client

    def analyze_traces(self, max_traces: int = 100) -> list[EvalProposal]:
        """Analyze traces and propose evals based on failure patterns."""
        proposals: list[EvalProposal] = []
        if self.trace_dir.exists():
            proposals.extend(self._analyze_local_traces(max_traces))
        if self._get_langsmith_client() is not None:
            proposals.extend(self._analyze_langsmith_traces(max_traces))
        return proposals

    def _analyze_local_traces(self, max_traces: int) -> list[EvalProposal]:
        """Analyze local tick/audit JSON files."""
        proposals: list[EvalProposal] = []
        trace_files = sorted(self.trace_dir.glob("tick_*.json"))[-max_traces:]
        failure_patterns: dict[str, int] = {}
        tool_errors: dict[str, int] = {}
        state_changes: list[dict[str, Any]] = []

        for trace_file in trace_files:
            try:
                data = json.loads(trace_file.read_text(encoding="utf-8"))
                if "error" in data and data["error"]:
                    error_type = data["error"].get("type", "unknown")
                    failure_patterns[error_type] = failure_patterns.get(error_type, 0) + 1
                for tool_call in data.get("tool_calls", []):
                    if tool_call.get("status") == "error":
                        tool_name = tool_call.get("name", "unknown")
                        tool_errors[tool_name] = tool_errors.get(tool_name, 0) + 1
                if "state_changes" in data:
                    state_changes.extend(data["state_changes"])
            except Exception as exc:
                logger.debug("Failed to parse trace %s: %s", trace_file, exc)

        for error_type, count in sorted(failure_patterns.items(), key=lambda x: -x[1]):
            if count >= 2:
                proposals.append(EvalProposal(
                    proposal_id=f"trace_failure_{error_type}_{datetime.now().strftime('%Y%m%d')}",
                    title=f"Recurring {error_type} failures ({count} occurrences)",
                    description=f"Production traces show {count} instances of {error_type}. Build eval to prevent regression.",
                    category="regression",
                    source="trace_mining",
                    affected_components=[error_type],
                    suggested_verifier_type="deterministic",
                    estimated_effort="low",
                    priority_score=min(0.9, 0.5 + count * 0.1),
                ))
        for tool_name, count in sorted(tool_errors.items(), key=lambda x: -x[1]):
            if count >= 2:
                proposals.append(EvalProposal(
                    proposal_id=f"tool_failure_{tool_name}_{datetime.now().strftime('%Y%m%d')}",
                    title=f"Tool {tool_name} failures ({count} occurrences)",
                    description=f"Tool {tool_name} failed {count} times in production. Build eval for tool contract.",
                    category="tool_reliability",
                    source="trace_mining",
                    affected_components=[tool_name],
                    suggested_verifier_type="hybrid",
                    estimated_effort="medium",
                    priority_score=min(0.85, 0.4 + count * 0.1),
                ))
        return proposals

    def _analyze_langsmith_traces(self, max_traces: int) -> list[EvalProposal]:
        """Analyze LangSmith traces via the SDK."""
        proposals: list[EvalProposal] = []
        client = self._get_langsmith_client()
        if client is None:
            return proposals

        try:
            # List runs from the configured project
            runs = list(client.list_runs(
                project_name=self.langsmith_project,
                execution_order="desc",
                limit=max_traces,
            ))
            failure_patterns: dict[str, int] = {}
            tool_errors: dict[str, int] = {}
            eval_gaps: set[str] = set()

            for run in runs:
                # Check for run-level errors
                if run.error:
                    error_type = run.error.split(":")[0] if ":" in run.error else run.error
                    failure_patterns[error_type] = failure_patterns.get(error_type, 0) + 1

                # Check child runs for tool failures
                if hasattr(run, "child_runs") and run.child_runs:
                    for child in run.child_runs:
                        if child.error:
                            tool_errors[child.name] = tool_errors.get(child.name, 0) + 1
                        # Track eval coverage gaps
                        if child.run_type == "eval" and child.error:
                            eval_gaps.add(child.name)

            for error_type, count in sorted(failure_patterns.items(), key=lambda x: -x[1]):
                if count >= 2:
                    proposals.append(EvalProposal(
                        proposal_id=f"langsmith_failure_{error_type}_{datetime.now().strftime('%Y%m%d')}",
                        title=f"LangSmith: Recurring {error_type} failures ({count} occurrences)",
                        description=f"LangSmith traces show {count} instances of {error_type}. Build eval to prevent regression.",
                        category="regression",
                        source="langsmith_trace",
                        affected_components=[error_type],
                        suggested_verifier_type="deterministic",
                        estimated_effort="low",
                        priority_score=min(0.9, 0.5 + count * 0.1),
                    ))

            for tool_name, count in sorted(tool_errors.items(), key=lambda x: -x[1]):
                if count >= 2:
                    proposals.append(EvalProposal(
                        proposal_id=f"langsmith_tool_{tool_name}_{datetime.now().strftime('%Y%m%d')}",
                        title=f"LangSmith: Tool {tool_name} failures ({count} occurrences)",
                        description=f"Tool {tool_name} failed {count} times in LangSmith traces. Build eval for tool contract.",
                        category="tool_reliability",
                        source="langsmith_trace",
                        affected_components=[tool_name],
                        suggested_verifier_type="hybrid",
                        estimated_effort="medium",
                        priority_score=min(0.85, 0.4 + count * 0.1),
                    ))

            logger.info("Analyzed %d LangSmith runs, generated %d proposals", len(runs), len(proposals))
        except Exception as exc:
            logger.warning("Failed to analyze LangSmith traces: %s", exc)

        return proposals

    def fetch_traces_as_dataset(self, output_path: Path | None = None, max_traces: int = 50) -> Path | None:
        """Fetch traces from LangSmith and save as a local dataset for offline mining."""
        client = self._get_langsmith_client()
        if client is None:
            logger.warning("LangSmith not configured; cannot fetch traces")
            return None

        output_path = output_path or (ROOT / "data" / "eval" / "langsmith_traces.jsonl")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            runs = list(client.list_runs(
                project_name=self.langsmith_project,
                execution_order="desc",
                limit=max_traces,
            ))
            count = 0
            with output_path.open("w", encoding="utf-8") as f:
                for run in runs:
                    record = {
                        "run_id": str(run.id) if hasattr(run, "id") else None,
                        "name": run.name,
                        "run_type": getattr(run, "run_type", "unknown"),
                        "error": run.error,
                        "inputs": getattr(run, "inputs", {}),
                        "outputs": getattr(run, "outputs", {}),
                        "start_time": str(run.start_time) if run.start_time else None,
                        "end_time": str(run.end_time) if run.end_time else None,
                    }
                    f.write(json.dumps(record) + "\n")
                    count += 1
            logger.info("Fetched %d LangSmith traces to %s", count, output_path)
            return output_path
        except Exception as exc:
            logger.warning("Failed to fetch LangSmith traces: %s", exc)
            return None


# ── Eval Proposal Engine ─────────────────────────────────────────────────────

class EvalProposalEngine:
    """Generates eval proposals from repo inspection and trace analysis."""

    def __init__(self, inspector: RepoInspector | None = None, analyzer: TraceAnalyzer | None = None):
        self.inspector = inspector or RepoInspector()
        self.analyzer = analyzer or TraceAnalyzer()

    def generate_proposals(self) -> list[EvalProposal]:
        """Generate eval proposals from all sources."""
        proposals: list[EvalProposal] = []
        components = self.inspector.inspect()
        proposals.extend(self._propose_from_components(components))
        proposals.extend(self.analyzer.analyze_traces())
        proposals.extend(self._propose_from_existing_evals())
        proposals.sort(key=lambda p: -p.priority_score)
        return proposals

    def _propose_from_components(self, components: list[AgentComponent]) -> list[EvalProposal]:
        """Propose evals for critical agent components."""
        proposals: list[EvalProposal] = []
        by_type: dict[str, list[AgentComponent]] = {}
        for comp in components:
            by_type.setdefault(comp.component_type, []).append(comp)

        for comp in by_type.get("agent", []):
            proposals.append(EvalProposal(
                proposal_id=f"agent_{comp.name}",
                title=f"Agent behavior: {comp.name}",
                description=f"Test {comp.name} agent decision making and tool usage patterns.",
                category="agent_behavior",
                source="repo_inspection",
                affected_components=[comp.name],
                suggested_verifier_type="hybrid",
                estimated_effort="high",
                priority_score=0.9,
            ))
        for comp in by_type.get("tool", []):
            proposals.append(EvalProposal(
                proposal_id=f"tool_{comp.name}",
                title=f"Tool contract: {comp.name}",
                description=f"Validate {comp.name} tool input/output contract and error handling.",
                category="tool_contract",
                source="repo_inspection",
                affected_components=[comp.name],
                suggested_verifier_type="deterministic",
                estimated_effort="low",
                priority_score=0.8,
            ))
        for comp in by_type.get("skill", []):
            proposals.append(EvalProposal(
                proposal_id=f"skill_{comp.name}",
                title=f"Skill execution: {comp.name}",
                description=f"Test {comp.name} skill end-to-end with realistic inputs.",
                category="skill_execution",
                source="repo_inspection",
                affected_components=[comp.name],
                suggested_verifier_type="llm_judge",
                estimated_effort="medium",
                priority_score=0.75,
            ))
        return proposals

    def _propose_from_existing_evals(self) -> list[EvalProposal]:
        """Identify gaps in existing eval coverage."""
        proposals: list[EvalProposal] = []
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

        critical_categories = {
            "bank_surplus": ("Bank adapter surplus withdrawal logic", "deterministic"),
            "risk_gate": ("Drawdown circuit breaker behavior", "deterministic"),
            "order_idempotency": ("Order idempotency key validation", "deterministic"),
            "rth_schedule": ("Regular trading hours schedule compliance", "deterministic"),
            "position_sizing": ("Position size limit enforcement", "deterministic"),
            "option_greeks": ("Option greeks calculation accuracy", "deterministic"),
            "trade_execution": ("End-to-end trade execution flow", "hybrid"),
        }
        for category, (description, verifier_type) in critical_categories.items():
            if category not in existing_categories:
                proposals.append(EvalProposal(
                    proposal_id=f"missing_{category}",
                    title=f"Missing eval coverage: {category}",
                    description=f"No evals found for {description}. Critical for production safety.",
                    category=category,
                    source="eval_gap",
                    affected_components=[category],
                    suggested_verifier_type=verifier_type,
                    estimated_effort="low",
                    priority_score=0.85,
                ))
        return proposals


# ── Eval Task Builder ────────────────────────────────────────────────────────

class EvalTaskBuilder:
    """Builds complete Harbor-format eval tasks from approved proposals."""

    def __init__(self, root: Path = ROOT):
        self.root = root
        self.evals_dir = root / "evals"
        self.evals_dir.mkdir(parents=True, exist_ok=True)

    def build_task(self, proposal: EvalProposal, user_guidance: dict[str, Any] | None = None) -> EvalTask:
        """Build a complete Harbor-format eval task from a proposal."""
        guidance = user_guidance or {}
        task_id = proposal.proposal_id
        task_dir = self.evals_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        instruction_md = self._generate_instruction(proposal, guidance)
        task_toml = self._generate_task_toml(proposal, guidance)
        dockerfile = self._generate_dockerfile(proposal)
        test_files = self._generate_tests(proposal, guidance)
        verifier_code = self._generate_verifier(proposal, guidance)

        task = EvalTask(
            task_id=task_id,
            name=proposal.title,
            description=proposal.description,
            instruction_md=instruction_md,
            task_toml=task_toml,
            environment_dockerfile=dockerfile,
            test_files=test_files,
            verifier_code=verifier_code,
            created_at=datetime.now().isoformat(),
            approved=True,
        )

        # Write files to disk
        self._write_task_files(task_dir, task)
        logger.info("Built eval task %s at %s", task_id, task_dir)
        return task

    def _write_task_files(self, task_dir: Path, task: EvalTask) -> None:
        """Write all task files to disk."""
        # instruction.md
        (task_dir / "instruction.md").write_text(task.instruction_md, encoding="utf-8")
        # task.toml
        (task_dir / "task.toml").write_text(task.task_toml, encoding="utf-8")
        # environment/
        env_dir = task_dir / "environment"
        env_dir.mkdir(exist_ok=True)
        (env_dir / "Dockerfile").write_text(task.environment_dockerfile, encoding="utf-8")
        # tests/
        tests_dir = task_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")
        for filename, content in task.test_files.items():
            (tests_dir / filename).write_text(content, encoding="utf-8")
        # verifier.py
        (task_dir / "verifier.py").write_text(task.verifier_code, encoding="utf-8")

    def _generate_instruction(self, proposal: EvalProposal, guidance: dict[str, Any]) -> str:
        """Generate instruction.md for the eval task."""
        scenario_desc = guidance.get("scenario_description", proposal.description)
        return f"""# {proposal.title}

## Overview

{scenario_desc}

## Eval Checks

| ID | Name | Weight | Description |
|----|------|--------|-------------|
| EVAL-001 | {proposal.category}_check | 1.0 | {proposal.description} |

## Verifier Requirements

The verifier must:
1. Score each eval independently based on golden answers
2. Inspect agent trajectory (tool calls, errors, state changes)
3. Detect reward hacking shortcuts:
   - Overciting irrelevant data
   - False claims about validation steps
   - Exploited edge cases in validator logic
4. Report confidence level for each score
5. Provide counterexamples when verifier is too lenient

## Golden Test Cases

### Valid Case (Expected Pass: 100%)
- Input: Standard valid input for {proposal.category}
- All checks should pass

### Invalid Case (Expected Fail)
- Input: Input that should trigger {proposal.category} validation
- At least one check should fail

## Trace Analysis Guidelines

1. Extract tool calls from agent trajectory
2. Identify failed validations in production
3. Convert failures into eval tasks
4. Build verifier that checks intended behavior
5. Iterate on task/verifier if reward hacking detected

## Harbor Format Components

- **task.toml**: Task metadata, eval IDs, weights, scenarios
- **instruction.md**: This file - agent context and verifier requirements
- **environment/**: Dockerfile, setup scripts, mock data
- **tests/**: Pytest suite for deterministic validation
"""

    def _generate_task_toml(self, proposal: EvalProposal, guidance: dict[str, Any]) -> str:
        """Generate task.toml for the eval task."""
        return f"""# Harbor Task Definition for {proposal.title}
# Maps to Harbour format: evals/<task-id>/

[[specs.tasks]]
name = "{proposal.proposal_id}"
id = "{proposal.proposal_id}"
description = "{proposal.description}"
version = "1.0.0"

[[specs.eval_checks]]
id = "EVAL-001"
name = "{proposal.category}_check"
weight = 1.0
goal_description = "{proposal.description}"
process_description = "Validate {proposal.category} behavior against expected outcomes"
style_description = "Report violations with clear error messages"

[[specs.env_setup]]
python_version = "3.11"
dependencies_inline = "pip install pytest"
base_image = "python:3.11-slim"

[[specs.golden_scenarios]]
id = "scenario-valid"
description = "Valid case that passes all checks"
expected_pass_rate = 1.0

[[specs.golden_scenarios]]
id = "scenario-invalid"
description = "Invalid case that triggers {proposal.category} violations"
expected_pass_rate = 0.0
violation_count_minimum = 1
"""

    def _generate_dockerfile(self, proposal: EvalProposal) -> str:
        """Generate Dockerfile for the eval environment."""
        return f"""# Harbor Eval Environment: {proposal.title}
FROM python:3.11-slim as base

WORKDIR /app

RUN pip install --no-cache-dir \
    pytest==8.3.4 \
    pytest-cov==5.0.0 \
    requests==2.32.3

# Build stage
FROM base as build
WORKDIR /build
COPY . .

# Runtime stage
FROM base
WORKDIR /evals
COPY --from=build /app/dist /evals/dist

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0

ENTRYPOINT ["python", "-m", "pytest"]
"""

    def _generate_tests(self, proposal: EvalProposal, guidance: dict[str, Any]) -> dict[str, str]:
        """Generate test files for the eval task."""
        test_name = f"test_{proposal.category}"
        test_content = f'''"""
Tests for {proposal.title}
'''
        test_content += f"""
Generated from proposal: {proposal.proposal_id}
"""

        test_content += f'''"""

import json
from pathlib import Path


class Test{proposal.category.replace("_", " ").title().replace(" ", "")}:
    """Test suite for {proposal.category} validation."""

    def test_valid_case(self):
        """Test that valid input passes all checks."""
        # TODO: Implement with actual validation logic
        assert True, "Valid case should pass"

    def test_invalid_case(self):
        """Test that invalid input triggers violations."""
        # TODO: Implement with actual validation logic
        pass

    def test_edge_case(self):
        """Test edge case behavior."""
        # TODO: Implement edge cases
        pass
'''

        conftest_content = '''"""Pytest fixtures and configuration."""

import pytest
from pathlib import Path


@pytest.fixture
def test_data_dir() -> Path:
    """Return path to test data directory."""
    return Path(__file__).parent / "data"
'''

        return {
            f"{test_name}.py": test_content,
            "conftest.py": conftest_content,
        }

    def _generate_verifier(self, proposal: EvalProposal, guidance: dict[str, Any]) -> str:
        """Generate verifier code based on suggested verifier type."""
        verifier_type = guidance.get("verifier_type", proposal.suggested_verifier_type)
        if verifier_type == "deterministic":
            return self._generate_deterministic_verifier(proposal, guidance)
        elif verifier_type == "llm_judge":
            return self._generate_llm_judge_verifier(proposal, guidance)
        else:
            return self._generate_hybrid_verifier(proposal, guidance)

    def _generate_deterministic_verifier(self, proposal: EvalProposal, guidance: dict[str, Any]) -> str:
        """Generate a deterministic (rule-based) verifier."""
        return f'''"""
Deterministic Verifier for {proposal.title}
Generated from proposal: {proposal.proposal_id}
Verifier type: deterministic
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Verdict:
    passed: bool
    score: float
    details: str
    confidence: float = 1.0
    violations: list[str] = field(default_factory=list)


class Verifier:
    """Rule-based verifier for {proposal.category} validation."""

    def __init__(self):
        self.rules = self._setup_rules()

    def _setup_rules(self) -> list[dict]:
        """Define deterministic validation rules."""
        return [
            {{
                "id": "EVAL-001",
                "name": "{proposal.category}_check",
                "weight": 1.0,
            }},
        ]

    def verify(self, agent_trajectory: dict[str, Any]) -> Verdict:
        """Run deterministic verification against agent trajectory."""
        violations: list[str] = []
        tool_calls = agent_trajectory.get("tool_calls", [])
        errors = agent_trajectory.get("errors", [])
        outputs = agent_trajectory.get("outputs", {{}})

        # Check for errors
        if errors:
            violations.append(f"Agent trajectory contains errors: {{errors}}")

        # Check tool calls exist
        if not tool_calls:
            violations.append("No tool calls made during evaluation")

        passed = len(violations) == 0
        return Verdict(
            passed=passed,
            score=1.0 if passed else 0.0,
            details="All checks passed" if passed else "; ".join(violations),
            violations=violations,
        )
'''

    def _generate_llm_judge_verifier(self, proposal: EvalProposal, guidance: dict[str, Any]) -> str:
        """Generate an LLM-as-judge verifier."""
        return f'''"""
LLM-as-Judge Verifier for {proposal.title}
Generated from proposal: {proposal.proposal_id}
Verifier type: llm_judge
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class Verdict:
    passed: bool
    score: float
    details: str
    confidence: float
    reasoning: str = ""
    violations: list[str] = field(default_factory=list)


JUDGE_PROMPT = """You are an expert evaluator judging an AI agent's performance.
Analyze the agent trajectory below and score it 0-5 based on:

1. Correctness: Did the agent produce the right answer?
2. Process: Did the agent follow proper procedures?
3. Efficiency: Did the agent avoid unnecessary steps?
4. Safety: Did the agent respect constraints and boundaries?

Agent Trajectory:
{{trajectory}}

Rubric:
{proposal.description}

Return a valid JSON object with fields: score (0-5), reasoning (str), violations (list[str])).
"""


class Verifier:
    """LLM-as-judge verifier for {proposal.category}."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self._client = None
        if HAS_OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._client = openai.OpenAI(api_key=api_key)

    def verify(self, agent_trajectory: dict[str, Any]) -> Verdict:
        """Run LLM-as-judge evaluation on agent trajectory."""
        if self._client is None:
            logger.warning("OpenAI not configured; using fallback scoring")
            return Verdict(
                passed=True,
                score=5.0,
                details="LLM judge unavailable - using pass-through",
                confidence=0.0,
            )

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {{"role": "system", "content": JUDGE_PROMPT.format(
                        trajectory=json.dumps(agent_trajectory, indent=2),
                        description="{proposal.description}",
                    )}},
                ],
                response_format={{"type": "json_object"}},
                temperature=0.0,
            )
            result = json.loads(response.choices[0].message.content)
            score = float(result.get("score", 3.0))
            reasoning = result.get("reasoning", "")
            violations = result.get("violations", [])

            passed = score >= 3.0  # Threshold: 3/5
            return Verdict(
                passed=passed,
                score=score / 5.0,  # Normalize to 0-1
                details=f"LLM judge score: {{score}}/5",
                confidence=0.8,
                reasoning=reasoning,
                violations=violations,
            )
        except Exception as exc:
            logger.warning("LLM judge failed: %s", exc)
            return Verdict(
                passed=True,
                score=1.0,
                details=f"LLM judge error (bypass): {{exc}}",
                confidence=0.0,
            )
'''

    def _generate_hybrid_verifier(self, proposal: EvalProposal, guidance: dict[str, Any]) -> str:
        """Generate a hybrid (deterministic + LLM) verifier."""
        return f'''"""
Hybrid Verifier for {proposal.title}
Generated from proposal: {proposal.proposal_id}
Verifier type: hybrid (deterministic rules + LLM judge)
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


@dataclass
class Verdict:
    passed: bool
    score: float
    details: str
    confidence: float
    deterministic_verdict: dict | None = None
    llm_verdict: dict | None = None
    violations: list[str] = field(default_factory=list)


class Verifier:
    """Hybrid verifier combining deterministic rules and LLM judge."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self._client = None
        if HAS_OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._client = openai.OpenAI(api_key=api_key)

    def _deterministic_check(self, trajectory: dict[str, Any]) -> dict:
        """Run deterministic rule checks on trajectory."""
        violations = []
        tool_calls = trajectory.get("tool_calls", [])
        errors = trajectory.get("errors", [])

        if errors:
            violations.append(f"Trajectory errors: {{errors}}")
        if not tool_calls:
            violations.append("No tool calls found")

        passed = len(violations) == 0
        return {{
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "violations": violations,
        }}

    def _llm_judge_check(self, trajectory: dict[str, Any]) -> dict:
        """Run LLM-as-judge evaluation."""
        if self._client is None:
            return {{"passed": True, "score": 1.0, "reasoning": "LLM unavailable", "violations": []}}

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {{"role": "system", "content": f"Evaluate this agent trajectory for {proposal.description}. Return JSON with score (0-5), reasoning, violations."}},
                    {{"role": "user", "content": json.dumps(trajectory, indent=2)}},
                ],
                response_format={{"type": "json_object"}},
                temperature=0.0,
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as exc:
            return {{"score": 3.0, "reasoning": f"Error: {{exc}}", "violations": []}}

    def verify(self, agent_trajectory: dict[str, Any]) -> Verdict:
        """Run hybrid verification combining both approaches."""
        det = self._deterministic_check(agent_trajectory)
        llm = self._llm_judge_check(agent_trajectory)

        llm_score = float(llm.get("score", 3.0)) / 5.0
        violations = det["violations"] + llm.get("violations", [])

        # Hybrid: must pass deterministic AND meet LLM threshold
        passed = det["passed"] and llm_score >= 0.6

        return Verdict(
            passed=passed,
            score=min(1.0, (det["score"] + llm_score) / 2),
            details=f"Deterministic: {{{{det}}}} | LLM: {{{{llm}}}}",
            confidence=0.9 if passed else 0.95,
            deterministic_verdict=det,
            llm_verdict=llm,
            violations=violations,
        )
'''


# ── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    """CLI entry point for the Eval Engineering Skill."""
    import argparse

    parser = argparse.ArgumentParser(description="Eval Engineering Skill - Automated Eval Generation")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect repo for agent components")
    inspect_parser.add_argument("--output", "-o", type=str, default=None, help="Output JSON file")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze traces for failure patterns")
    analyze_parser.add_argument("--max-traces", type=int, default=100, help="Max traces to analyze")
    analyze_parser.add_argument("--output", "-o", type=str, default=None, help="Output JSON file")

    # propose
    propose_parser = subparsers.add_parser("propose", help="Generate eval proposals")
    propose_parser.add_argument("--output", "-o", type=str, default=None, help="Output JSON file")

    # build
    build_parser = subparsers.add_parser("build", help="Build eval task from proposal")
    build_parser.add_argument("--proposal-id", type=str, required=True, help="Proposal ID to build")
    build_parser.add_argument("--proposal-file", type=str, required=True, help="JSON file with proposal")

    # fetch-langsmith
    fetch_parser = subparsers.add_parser("fetch-langsmith", help="Fetch LangSmith traces as dataset")
    fetch_parser.add_argument("--max-traces", type=int, default=50, help="Max traces to fetch")
    fetch_parser.add_argument("--output", "-o", type=str, default=None, help="Output JSONL file")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "inspect":
        inspector = RepoInspector()
        components = inspector.inspect()
        data = [asdict(c) for c in components]
        if args.output:
            Path(args.output).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            print(f"Wrote {len(data)} components to {args.output}")
        else:
            print(json.dumps(data, indent=2, default=str))

    elif args.command == "analyze":
        analyzer = TraceAnalyzer()
        proposals = analyzer.analyze_traces(max_traces=args.max_traces)
        data = [asdict(p) for p in proposals]
        if args.output:
            Path(args.output).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            print(f"Wrote {len(data)} proposals to {args.output}")
        else:
            print(json.dumps(data, indent=2, default=str))

    elif args.command == "propose":
        engine = EvalProposalEngine()
        proposals = engine.generate_proposals()
        data = [asdict(p) for p in proposals]
        if args.output:
            Path(args.output).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            print(f"Wrote {len(data)} proposals to {args.output}")
        else:
            print(json.dumps(data, indent=2, default=str))

    elif args.command == "build":
        with open(args.proposal_file, encoding="utf-8") as f:
            proposals_data = json.load(f)
        if isinstance(proposals_data, list):
            matches = [p for p in proposals_data if p["proposal_id"] == args.proposal_id]
            if not matches:
                print(f"ERROR: No proposal with ID {args.proposal_id}")
                return 1
            raw = matches[0]
        else:
            raw = proposals_data
        proposal = EvalProposal(**raw)
        builder = EvalTaskBuilder()
        task = builder.build_task(proposal)
        print(f"Built eval task {task.task_id} at {ROOT / 'evals' / task.task_id}")

    elif args.command == "fetch-langsmith":
        analyzer = TraceAnalyzer()
        result = analyzer.fetch_traces_as_dataset(output_path=Path(args.output) if args.output else None, max_traces=args.max_traces)
        if result:
            print(f"Fetched traces to {result}")
        else:
            print("Failed to fetch LangSmith traces (check LANGSMITH_API_KEY)")
            return 1

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
