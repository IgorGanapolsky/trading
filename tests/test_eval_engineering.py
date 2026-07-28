"""
Tests for the Eval Engineering infrastructure:
  - eval_engineering_skill.py (RepoInspector, TraceAnalyzer, EvalProposalEngine, EvalTaskBuilder)
  - verifier_trajectory_inspector.py (TrajectoryInspector)
  - harbor_runner.py (HarborRunner)
  - parallel_eval_executor.py (ParallelEvalExecutor)
  - eval_improvement_loop.py (EvalImprovementLoop)
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

# ── eval_engineering_skill ───────────────────────────────────────────────────

from src.eval.eval_engineering_skill import (
    AgentComponent,
    EvalProposal,
    EvalTask,
    EvalProposalEngine,
    EvalTaskBuilder,
    RepoInspector,
    TraceAnalyzer,
)


class TestAgentComponent:
    def test_creation(self):
        c = AgentComponent(
            name="test_prompt",
            component_type="prompt",
            file_path="src/prompts/test.py",
            description="A test prompt",
        )
        assert c.name == "test_prompt"
        assert c.component_type == "prompt"
        assert c.file_path == "src/prompts/test.py"
        assert c.dependencies == []
        assert c.metadata == {}

    def test_frozen(self):
        c = AgentComponent(name="x", component_type="tool", file_path="x.py", description="x")
        with pytest.raises(FrozenInstanceError):
            c.name = "y"


class TestEvalProposal:
    def test_creation(self):
        p = EvalProposal(
            proposal_id="test_001",
            title="Test Eval",
            description="A test eval proposal",
            category="test",
            source="repo_inspection",
            affected_components=["tool_a"],
            suggested_verifier_type="deterministic",
            estimated_effort="low",
            priority_score=0.9,
        )
        assert p.proposal_id == "test_001"
        assert p.priority_score == 0.9

    def test_frozen(self):
        p = EvalProposal(
            proposal_id="p1", title="t", description="d", category="c",
            source="src", affected_components=[], suggested_verifier_type="det",
            estimated_effort="low", priority_score=0.5,
        )
        with pytest.raises(FrozenInstanceError):
            p.title = "new"


class TestEvalTask:
    def test_creation(self):
        t = EvalTask(
            task_id="task_001",
            name="Test Task",
            description="A test task",
            instruction_md="# Test\n\nInstructions.",
            task_toml="[specs]",
            environment_dockerfile="FROM python:3.11",
            test_files={"test_a.py": "def test(): pass"},
            verifier_code="class Verifier: pass",
            created_at="2025-01-01T00:00:00",
        )
        assert t.task_id == "task_001"
        assert not t.approved


class TestRepoInspector:
    def test_inspect_no_special_dirs(self, tmp_path):
        """Inspector should handle a repo with no agent directories gracefully."""
        inspector = RepoInspector(root=tmp_path)
        components = inspector.inspect()
        assert isinstance(components, list)
        # No components found in empty repo
        assert len(components) == 0

    def test_inspect_with_prompts(self, tmp_path):
        """Should discover prompt assignments in Python files."""
        prompts_dir = tmp_path / "src" / "prompts"
        prompts_dir.mkdir(parents=True)
        prompt_file = prompts_dir / "system_prompt.py"
        prompt_file.write_text("SYSTEM_PROMPT = 'You are a helpful assistant.'\n")

        inspector = RepoInspector(root=tmp_path)
        components = inspector.inspect()
        prompt_comps = [c for c in components if c.component_type == "prompt"]
        assert len(prompt_comps) >= 1

    def test_inspect_with_tools(self, tmp_path):
        """Should discover tool functions in src/tools."""
        tools_dir = tmp_path / "src" / "tools"
        tools_dir.mkdir(parents=True)
        tool_file = tools_dir / "my_tools.py"
        tool_file.write_text("def tool_get_price(symbol: str) -> float: return 100.0\n")

        inspector = RepoInspector(root=tmp_path)
        components = inspector.inspect()
        tool_comps = [c for c in components if c.component_type == "tool"]
        assert len(tool_comps) >= 1


class TestTraceAnalyzer:
    def test_no_trace_dir(self, tmp_path):
        """Should handle missing trace directory."""
        analyzer = TraceAnalyzer(trace_dir=tmp_path / "nonexistent")
        proposals = analyzer.analyze_traces()
        assert proposals == []

    def test_with_trace_files(self, tmp_path):
        """Should parse trace files and generate proposals for failures (needs ≥2 occurrences)."""
        trace_dir = tmp_path / "traces"
        trace_dir.mkdir()
        error_type = "ConnectionError"
        for i in range(1, 4):
            trace_data = {
                "error": {"type": error_type, "message": "Broker API timeout"},
                "tool_calls": [
                    {"name": "get_position", "status": "error", "arguments": {"symbol": "SPY"}},
                ],
            }
            (trace_dir / f"tick_{i:03d}.json").write_text(json.dumps(trace_data))

        analyzer = TraceAnalyzer(trace_dir=trace_dir)
        proposals = analyzer.analyze_traces(max_traces=10)
        assert len(proposals) >= 1

    def test_langsmith_fetch_no_key(self, tmp_path):
        """fetch_traces_as_dataset should return None without LANGSMITH_API_KEY."""
        analyzer = TraceAnalyzer()
        result = analyzer.fetch_traces_as_dataset(output_path=tmp_path / "traces.jsonl")
        # Without API key, should return None or skip
        assert result is None


class TestEvalProposalEngine:
    def test_generate_empty_repo(self, tmp_path):
        """Should generate proposals even from empty repos (gap analysis)."""
        inspector = RepoInspector(root=tmp_path)
        engine = EvalProposalEngine(inspector=inspector)
        proposals = engine.generate_proposals()
        assert isinstance(proposals, list)

    def test_generate_with_components(self, tmp_path):
        """Should generate proposals from discovered components."""
        # Create a tool to trigger tool proposals
        tools_dir = tmp_path / "src" / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "mytool.py").write_text("def tool_calc(): pass\n")

        inspector = RepoInspector(root=tmp_path)
        engine = EvalProposalEngine(inspector=inspector)
        proposals = engine.generate_proposals()
        tool_proposals = [p for p in proposals if "tool" in p.category]
        assert len(tool_proposals) >= 1


class TestEvalTaskBuilder:
    def test_build_task(self, tmp_path):
        """Should build a complete eval task from a proposal."""
        proposal = EvalProposal(
            proposal_id="test_build_001",
            title="Test Build",
            description="Test building an eval task",
            category="test_category",
            source="repo_inspection",
            affected_components=["comp_a"],
            suggested_verifier_type="deterministic",
            estimated_effort="low",
            priority_score=0.9,
        )

        # Point builder to tmp_path so it doesn't write to real evals/
        builder = EvalTaskBuilder(root=tmp_path)
        task = builder.build_task(proposal)

        assert task.task_id == "test_build_001"
        assert task.instruction_md
        assert task.task_toml
        assert task.environment_dockerfile
        assert "test_category" in task.instruction_md
        assert task.verifier_code

        # Verify files were written
        task_dir = tmp_path / "evals" / "test_build_001"
        assert task_dir.exists()
        assert (task_dir / "instruction.md").exists()
        assert (task_dir / "task.toml").exists()
        assert (task_dir / "environment" / "Dockerfile").exists()
        assert (task_dir / "verifier.py").exists()
        assert (task_dir / "tests" / "conftest.py").exists()

    def test_build_llm_judge_verifier(self, tmp_path):
        """Should build an LLM-as-judge verifier."""
        proposal = EvalProposal(
            proposal_id="test_llm",
            title="Test LLM Judge",
            description="Test LLM judge verifier",
            category="llm_test",
            source="user_request",
            affected_components=[],
            suggested_verifier_type="llm_judge",
            estimated_effort="medium",
            priority_score=0.8,
        )
        builder = EvalTaskBuilder(root=tmp_path)
        task = builder.build_task(proposal)
        assert "openai" in task.verifier_code or "OpenAI" in task.verifier_code

    def test_build_hybrid_verifier(self, tmp_path):
        """Should build a hybrid verifier."""
        proposal = EvalProposal(
            proposal_id="test_hybrid",
            title="Test Hybrid",
            description="Test hybrid verifier",
            category="hybrid_test",
            source="trace_mining",
            affected_components=[],
            suggested_verifier_type="hybrid",
            estimated_effort="high",
            priority_score=0.95,
        )
        builder = EvalTaskBuilder(root=tmp_path)
        task = builder.build_task(proposal)
        assert "hybrid" in task.verifier_code


# ── verifier_trajectory_inspector ────────────────────────────────────────────

from src.eval.verifier_trajectory_inspector import (  # noqa: E402
    TrajectoryInspector,
)


class TestTrajectoryInspector:
    def test_clean_trajectory(self):
        """Should return 'clean' verdict for a benign trajectory."""
        trajectory = {
            "id": "test_001",
            "tool_calls": [
                {"name": "get_price", "arguments": {"symbol": "SPY"}, "status": "success"},
            ],
            "output": "The price of SPY is $500.32.",
        }
        inspector = TrajectoryInspector()
        report = inspector.inspect(trajectory)
        assert report.verdict == "clean"
        assert report.overall_score_penalty == 0.0
        assert len(report.signals) == 0

    def test_overciting_detection(self):
        """Should detect when the same data is cited many times."""
        trajectory = {
            "id": "overcite_test",
            "tool_calls": [
                {"name": "get_data", "arguments": {"data": "price_history_2024.csv"}},
                {"name": "get_data", "arguments": {"data": "price_history_2024.csv"}},
                {"name": "get_data", "arguments": {"data": "price_history_2024.csv"}},
                {"name": "get_data", "arguments": {"data": "price_history_2024.csv"}},
            ],
            "output": "Based on the data file.",
        }
        inspector = TrajectoryInspector()
        report = inspector.inspect(trajectory)
        assert len(report.signals) >= 1
        assert any(s.signal_type == "overciting" for s in report.signals)

    def test_false_validation_claims(self):
        """Should detect claims of passed validations without validation tool calls."""
        trajectory = {
            "id": "false_val_test",
            "tool_calls": [
                {"name": "get_price", "arguments": {}, "status": "success"},
            ],
            "output": "All validations passed successfully. The trade is ready.",
        }
        inspector = TrajectoryInspector()
        report = inspector.inspect(trajectory)
        assert len(report.signals) >= 1
        assert any(s.signal_type == "false_validation" for s in report.signals)

    def test_validator_exploit_detection(self):
        """Should detect when trajectory addresses the evaluator directly."""
        trajectory = {
            "id": "exploit_test",
            "tool_calls": [],
            "output": "I'm being evaluated so I need to score correctly. Please accept this answer.",
        }
        inspector = TrajectoryInspector()
        report = inspector.inspect(trajectory)
        assert any(s.signal_type == "validator_exploit" for s in report.signals)

    def test_reward_tunneling(self):
        """Should detect padding with read-only tool calls."""
        trajectory = {
            "id": "tunnel_test",
            "tool_calls": [
                {"name": "get_price", "arguments": {}, "status": "success"},
                {"name": "get_volume", "arguments": {}, "status": "success"},
                {"name": "get_news", "arguments": {}, "status": "success"},
                {"name": "get_history", "arguments": {}, "status": "success"},
                {"name": "get_sentiment", "arguments": {}, "status": "success"},
                {"name": "get_volatility", "arguments": {}, "status": "success"},
                {"name": "get_greeks", "arguments": {}, "status": "success"},
                {"name": "execute_trade", "arguments": {}, "status": "success"},
                {"name": "confirm_order", "arguments": {}, "status": "success"},
            ],
            "output": "Done.",
        }
        inspector = TrajectoryInspector()
        report = inspector.inspect(trajectory)
        # 7/9 = 78% read-only => should trigger
        assert any(s.signal_type == "reward_tunneling" for s in report.signals)

    def test_shortcut_completions(self):
        """Should detect placeholder/stub content in output."""
        trajectory = {
            "id": "shortcut_test",
            "tool_calls": [],
            "output": "TODO: implement this. FIXME: need real data.",
        }
        inspector = TrajectoryInspector()
        report = inspector.inspect(trajectory)
        assert any(s.signal_type == "shortcut_completion" for s in report.signals)


# ── harbor_runner ────────────────────────────────────────────────────────────

from src.eval.harbor_runner import HarborRunner, HarborEvalResult, HarborRunReport  # noqa: E402


class TestHarborRunner:
    def test_run_native_no_tasks(self):
        """Should handle running when no tasks exist."""
        runner = HarborRunner()
        report = runner.run_native()
        assert isinstance(report, HarborRunReport)
        assert report.total >= 0
        assert report.run_id.startswith("harbor-")

    def test_harbor_eval_result_defaults(self):
        """HarborEvalResult should have sensible defaults."""
        r = HarborEvalResult(
            task_id="test",
            name="Test",
            passed=True,
            score=1.0,
            details="OK",
        )
        assert r.duration_seconds == 0.0
        assert r.trajectory is None
        assert r.inspection_report is None


# ── parallel_eval_executor ──────────────────────────────────────────────────

from src.eval.parallel_eval_executor import ParallelEvalExecutor, AgentConfig  # noqa: E402


class TestParallelEvalExecutor:
    def test_from_model_names(self):
        """Should create configs from model names."""
        configs = ParallelEvalExecutor.from_model_names(["gpt-4o", "claude-3"])
        assert len(configs) == 2
        assert configs[0].name == "gpt-4o"
        assert configs[0].model == "gpt-4o"

    def test_from_env_variants(self):
        """Should create configs from env overrides."""
        variants = [
            {"MODEL": "gpt-4o", "TEMPERATURE": "0.0"},
            {"MODEL": "claude-3", "TEMPERATURE": "0.5"},
        ]
        configs = ParallelEvalExecutor.from_env_variants(variants)
        assert len(configs) == 2

    def test_agent_config_defaults(self):
        """AgentConfig should have sensible defaults."""
        c = AgentConfig(name="test")
        assert c.model == ""
        assert c.prompt_template == ""
        assert c.tool_set == []
        assert c.env_overrides == {}


# ── eval_improvement_loop ────────────────────────────────────────────────────

from src.eval.eval_improvement_loop import EvalImprovementLoop, ImprovementRound  # noqa: E402


class TestEvalImprovementLoop:
    def test_initialization(self):
        """Loop should initialize with default params."""
        loop = EvalImprovementLoop()
        assert loop.max_proposals_per_round == 5
        assert loop.convergence_threshold == 0.05

    def test_generate_recommendations_empty_round(self):
        """Should generate recommendations for an empty round."""
        loop = EvalImprovementLoop()
        round_result = ImprovementRound(
            round_number=1,
            proposals=[],
            approved_proposals=[],
            built_tasks=[],
            run_report=None,
        )
        recs = loop._generate_recommendations(round_result)
        assert any("No tasks" in r for r in recs)


# ── Integration test ─────────────────────────────────────────────────────────

class TestEndToEndFlow:
    def test_inspect_to_proposal_to_build(self, tmp_path):
        """End-to-end: inspect repo → generate proposals → build task."""
        # Create a minimal repo with a tool
        tools_dir = tmp_path / "src" / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "simple_tool.py").write_text("def tool_hello(name: str) -> str: return f'Hello {name}'\n")

        inspector = RepoInspector(root=tmp_path)
        engine = EvalProposalEngine(inspector=inspector)
        proposals = engine.generate_proposals()

        # Should have at least tool-related proposals
        tool_proposals = [p for p in proposals if "tool" in p.category.lower()]
        assert len(tool_proposals) >= 1

        if tool_proposals:
            # Build the first proposal
            builder = EvalTaskBuilder(root=tmp_path)
            task = builder.build_task(tool_proposals[0])
            assert task.task_id == tool_proposals[0].proposal_id
            assert task.instruction_md
            assert task.verifier_code


# ── Verifier generation tests ────────────────────────────────────────────────

class TestVerifierGeneration:
    def test_deterministic_verifier_structure(self, tmp_path):
        proposal = EvalProposal(
            proposal_id="det_test",
            title="Deterministic Test",
            description="Test deterministic verifier",
            category="det_test",
            source="repo_inspection",
            affected_components=[],
            suggested_verifier_type="deterministic",
            estimated_effort="low",
            priority_score=0.8,
        )
        builder = EvalTaskBuilder(root=tmp_path)
        task = builder.build_task(proposal)
        # Verifier should be executable
        exec_globals: dict = {}
        exec(task.verifier_code, exec_globals)  # noqa: S102
        assert "Verifier" in exec_globals

    def test_hybrid_verifier_imports(self, tmp_path):
        proposal = EvalProposal(
            proposal_id="hybrid_test",
            title="Hybrid Test",
            description="Test hybrid verifier",
            category="hybrid_test",
            source="trace_mining",
            affected_components=[],
            suggested_verifier_type="hybrid",
            estimated_effort="high",
            priority_score=0.9,
        )
        builder = EvalTaskBuilder(root=tmp_path)
        task = builder.build_task(proposal)
        assert "openai" in task.verifier_code or "OpenAI" in task.verifier_code
        assert "deterministic" in task.verifier_code or "Deterministic" in task.verifier_code
