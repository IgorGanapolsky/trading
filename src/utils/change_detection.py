"""Shared git diff and CI change classification utilities."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

DEPENDENCY_PATTERNS = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "mypy.ini",
    "pytest.ini",
    "requirements*.txt",
)

DOCS_TOOLING_PATHS = {
    "scripts/check_ai_discoverability.py",
    "scripts/check_anthropic_compliance.py",
    "scripts/generate_dashboard_snapshot.py",
    "scripts/generate_llms_manifest.py",
    "scripts/lint_blog_posts.py",
    "scripts/validate_github_pages_links.py",
}

WORKFLOW_TOOLING_PATHS = {
    "scripts/agent_handoff_gate.py",
    "scripts/collect_agent_handoff_ab_metrics.py",
}

WORKFLOW_META_TESTS = (
    "tests/test_agent_handoff_gate.py",
    "tests/test_ci_runner_wiring.py",
    "tests/test_workflow_contracts.py",
    "tests/test_workflow_dependencies.py",
    "tests/test_workflow_health_monitor.py",
    "tests/test_workflow_integrity.py",
    "tests/test_workflow_ml_integration.py",
    "tests/test_workflow_visualizer.py",
)

DOCS_META_TESTS = (
    "tests/test_check_ai_discoverability.py",
    "tests/test_dashboard_none_handling.py",
    "tests/test_generate_dashboard_snapshot.py",
    "tests/test_generate_world_class_dashboard_booleans.py",
    "tests/test_generate_world_class_dashboard_snapshots.py",
)


@dataclass(frozen=True)
class ChangeClassification:
    """Boolean routing hints for CI jobs."""

    changed_paths: list[str]
    docs_only: bool
    run_lint_python: bool
    run_lint_docs: bool
    run_agent_handoff: bool
    run_workflow_checks: bool
    run_full_tests: bool
    run_smoke: bool
    run_integration: bool
    run_core_test_suite: bool
    run_safety_jobs: bool
    run_security: bool
    run_type_check: bool
    run_core_strategy_validation: bool
    run_syntax_imports: bool
    run_dead_code_detection: bool
    run_skill_validation: bool
    run_pages_validation: bool
    run_safe_wrapper_scan: bool

    def to_output_map(self) -> dict[str, str]:
        """Convert booleans to GitHub Actions output strings."""
        output: dict[str, str] = {}
        for key, value in asdict(self).items():
            if isinstance(value, bool):
                output[key] = str(value).lower()
            elif isinstance(value, list):
                output[key] = json.dumps(value)
            else:
                output[key] = str(value)
        return output


def parse_changed_paths(raw_text: str) -> list[str]:
    """Parse git diff --name-only output into normalized repo-relative paths."""
    parsed: list[str] = []
    for line in raw_text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        normalized = PurePosixPath(candidate).as_posix()
        if normalized not in parsed:
            parsed.append(normalized)
    return parsed


def _run_git_diff(repo_root: Path, base_ref: str, head_ref: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            f"{base_ref}...{head_ref}",
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def get_changed_paths(repo_root: Path, base_ref: str, head_ref: str = "HEAD") -> list[str]:
    """Get changed file paths against a base ref, with a shallow-clone fallback."""
    code, stdout, _stderr = _run_git_diff(repo_root=repo_root, base_ref=base_ref, head_ref=head_ref)
    if code == 0:
        return parse_changed_paths(stdout)

    fallback_base = f"{head_ref}~1"
    code, stdout, _stderr = _run_git_diff(
        repo_root=repo_root,
        base_ref=fallback_base,
        head_ref=head_ref,
    )
    if code == 0:
        return parse_changed_paths(stdout)

    return []


def _matches(path: str, *patterns: str) -> bool:
    posix = PurePosixPath(path)
    return any(posix.match(pattern) for pattern in patterns)


def _is_dependency_path(path: str) -> bool:
    return _matches(path, *DEPENDENCY_PATTERNS)


def _is_docs_path(path: str) -> bool:
    return (
        path in DOCS_TOOLING_PATHS
        or path in {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "_config.yml"}
        or path.endswith(".md")
        or path.startswith(("docs/", "wiki/", "rag_knowledge/", ".claude/"))
    )


def _is_pages_path(path: str) -> bool:
    return (
        path == "_config.yml"
        or path.startswith("docs/")
        or path == "scripts/validate_github_pages_links.py"
    )


def _is_workflow_path(path: str) -> bool:
    return (
        path.startswith(".github/workflows/")
        or path.startswith("scripts/ci/")
        or path in WORKFLOW_TOOLING_PATHS
        or path in WORKFLOW_META_TESTS
    )


def _is_skill_path(path: str) -> bool:
    return (
        path == "scripts/validate_skills.py"
        or "/skills/" in f"/{path}"
        or path.endswith("/SKILL.md")
        or path.startswith((".agents/skills/", ".codex/skills/"))
    )


def _is_meta_test(path: str) -> bool:
    return path in WORKFLOW_META_TESTS or path in DOCS_META_TESTS


def _is_runtime_script(path: str) -> bool:
    return (
        path.startswith("scripts/")
        and path.endswith(".py")
        and path not in DOCS_TOOLING_PATHS
        and path not in WORKFLOW_TOOLING_PATHS
        and path != "scripts/validate_skills.py"
    )


def _is_runtime_source(path: str) -> bool:
    return path.startswith("src/")


def _is_runtime_test(path: str) -> bool:
    return path.startswith("tests/") and path.endswith(".py") and not _is_meta_test(path)


def _is_gate_test_path(path: str) -> bool:
    return (
        _matches(
            path,
            "src/risk/**",
            "src/safety/**",
            "src/execution/**",
            "src/orchestrator/**",
        )
        or path
        in {
            "scripts/enforce_promotion_gate.py",
            "tests/test_promotion_gate.py",
            "tests/test_trade_gateway.py",
        }
        or _is_dependency_path(path)
    )


def _is_safety_path(path: str) -> bool:
    return (
        _matches(
            path,
            "src/risk/**",
            "src/safety/**",
            "src/execution/**",
            "src/orchestrator/**",
            "tests/evals/**",
        )
        or path
        in {
            "scripts/compliance_audit.py",
            "scripts/enforce_promotion_gate.py",
            "scripts/rollback_test.py",
            "tests/test_mandatory_trade_gate.py",
            "tests/test_orchestrator_gates.py",
            "tests/test_safety_gates.py",
        }
        or _is_dependency_path(path)
    )


def _is_core_strategy_path(path: str) -> bool:
    return (
        _matches(
            path,
            "src/backtest/**",
            "src/strategies/core_strategy*.py",
            "src/strategies/core_strategy*/**",
            "tests/fixtures/**",
        )
        or path == "scripts/run_core_strategy_reference_backtest.py"
        or _is_dependency_path(path)
    )


def _is_smoke_path(path: str) -> bool:
    return (
        _is_runtime_source(path)
        or path == "scripts/run_smoke.sh"
        or _matches(path, "tests/fixtures/**", "tests/integration/**")
        or _is_dependency_path(path)
    )


def _is_integration_path(path: str) -> bool:
    return (
        _is_runtime_source(path)
        or _is_runtime_script(path)
        or _matches(path, "tests/integration/**")
        or _is_dependency_path(path)
    )


def _is_safe_wrapper_path(path: str) -> bool:
    return _is_runtime_source(path) or _is_runtime_script(path) or _is_dependency_path(path)


def classify_changed_paths(changed_paths: Iterable[str]) -> ChangeClassification:
    """Classify changed paths into CI routing buckets."""
    normalized = parse_changed_paths("\n".join(changed_paths))

    runtime_source = any(_is_runtime_source(path) for path in normalized)
    runtime_script = any(_is_runtime_script(path) for path in normalized)
    runtime_test = any(_is_runtime_test(path) for path in normalized)
    workflow_related = any(_is_workflow_path(path) for path in normalized)
    docs_related = any(_is_docs_path(path) for path in normalized)
    pages_related = any(_is_pages_path(path) for path in normalized)
    skill_related = any(_is_skill_path(path) for path in normalized)
    dependency_related = any(_is_dependency_path(path) for path in normalized)

    runtime_related = runtime_source or runtime_script
    full_test_related = runtime_related or runtime_test or dependency_related

    docs_only = bool(normalized) and all(
        _is_docs_path(path) or _is_pages_path(path) or _is_skill_path(path) for path in normalized
    )

    return ChangeClassification(
        changed_paths=normalized,
        docs_only=docs_only,
        run_lint_python=runtime_related or runtime_test or dependency_related,
        run_lint_docs=docs_related or pages_related,
        run_agent_handoff=full_test_related or workflow_related,
        run_workflow_checks=workflow_related,
        run_full_tests=full_test_related,
        run_smoke=any(_is_smoke_path(path) for path in normalized),
        run_integration=any(_is_integration_path(path) for path in normalized),
        run_core_test_suite=any(_is_gate_test_path(path) for path in normalized),
        run_safety_jobs=any(_is_safety_path(path) for path in normalized),
        run_security=full_test_related or workflow_related or ".secrets.baseline" in normalized,
        run_type_check=runtime_related or dependency_related,
        run_core_strategy_validation=any(_is_core_strategy_path(path) for path in normalized),
        run_syntax_imports=runtime_related or dependency_related,
        run_dead_code_detection=runtime_related,
        run_skill_validation=skill_related,
        run_pages_validation=pages_related,
        run_safe_wrapper_scan=any(_is_safe_wrapper_path(path) for path in normalized),
    )
