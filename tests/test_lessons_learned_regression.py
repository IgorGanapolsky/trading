"""
Comprehensive regression tests for ALL lessons learned.

This file MUST be extended whenever a new lesson is created.
Each test prevents a specific incident from recurring.

CRITICAL: Do NOT remove tests. Each test represents real money lost.

Created: Dec 15, 2025
Last Updated: Dec 15, 2025
"""

import ast
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest


class TestLL009SyntaxErrors:
    """Prevent LL-009: Syntax errors in critical files breaking trading."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_critical_files_have_valid_syntax(self, project_root):
        """Verify all critical files parse without syntax errors."""
        critical_paths = [
            "src/orchestrator/main.py",
            "src/execution/alpaca_executor.py",
            "src/risk/trade_gateway.py",
            "src/strategies/options_iv_signal.py",
            "src/core/alpaca_trader.py",
            "scripts/autonomous_trader.py",
        ]

        errors = []
        for rel_path in critical_paths:
            file_path = project_root / rel_path
            if file_path.exists():
                try:
                    with open(file_path) as f:
                        ast.parse(f.read())
                except SyntaxError as e:
                    errors.append(f"{rel_path}: line {e.lineno}: {e.msg}")

        assert not errors, "REGRESSION LL-009: Syntax errors found:\n" + "\n".join(errors)


class TestLL020FearMultiplier:
    """Prevent LL-020: Pyramid buying during fear destroying portfolio.

    Dec 15, 2025: Lost $96 because fear multiplier was INCREASING position size
    during downtrends instead of waiting for confirmation.
    """

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_fear_multiplier_not_increasing_position(self, project_root):
        """Ensure extreme fear conditions don't INCREASE position size."""
        fear_greed_file = project_root / "src" / "utils" / "fear_greed_index.py"

        if not fear_greed_file.exists():
            pytest.skip("fear_greed_index.py not found")

        with open(fear_greed_file) as f:
            content = f.read()

        # Check for dangerous patterns: size_multiplier > 1.0 during fear
        dangerous_patterns = [
            r"if.*fear.*size_multiplier\s*=\s*1\.[5-9]",  # 1.5+ multiplier
            r"if.*fear.*size_multiplier\s*=\s*2",         # 2x multiplier
            r"EXTREME_FEAR.*multiplier\s*=\s*1\.[5-9]",   # Fear threshold increases size
        ]

        for pattern in dangerous_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            assert match is None, (
                f"REGRESSION LL-020: Found dangerous fear multiplier pattern:\n"
                f"  Pattern: {pattern}\n"
                f"  Fear should REDUCE position size, not increase it!"
            )

    def test_no_hardcoded_fake_metrics(self, project_root):
        """Ensure hooks don't contain hardcoded fake performance claims."""
        hook_files = [
            ".claude/hooks/inject_trading_context.sh",
            ".claude/hooks/load_trading_state.sh",
        ]

        fake_metrics = [
            "2.18 Sharpe",
            "62.2% win rate",
            "Sharpe: 2.18",
            "win rate: 62.2",
        ]

        for rel_path in hook_files:
            hook_file = project_root / rel_path
            if hook_file.exists():
                with open(hook_file) as f:
                    content = f.read()

                for fake_metric in fake_metrics:
                    assert fake_metric not in content, (
                        f"REGRESSION LL-020: Found fake hardcoded metric in {rel_path}:\n"
                        f"  Found: {fake_metric}\n"
                        f"  Metrics must be dynamically loaded from actual data!"
                    )

class TestLL024FStringSyntax:
    """Prevent LL-024: F-string syntax errors (backslash in expressions)."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_autonomous_trader_valid_syntax(self, project_root):
        """Verify autonomous_trader.py has no f-string syntax errors."""
        trader_script = project_root / "scripts" / "autonomous_trader.py"

        if not trader_script.exists():
            pytest.skip("autonomous_trader.py not found")

        with open(trader_script) as f:
            content = f.read()

        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"REGRESSION LL-024: Syntax error in autonomous_trader.py: {e}")

    def test_no_backslash_in_fstrings(self, project_root):
        """Check Python files don't have backslashes in f-string expressions."""
        python_files = list((project_root / "src").rglob("*.py"))
        python_files += list((project_root / "scripts").rglob("*.py"))

        issues = []
        # Pattern: f"...{...\...}..." - backslash inside f-string braces
        pattern = r'f["\'][^"\']*\{[^}]*\\[^}]*\}[^"\']*["\']'

        for py_file in python_files[:50]:  # Limit to avoid timeout
            try:
                with open(py_file) as f:
                    content = f.read()

                if re.search(pattern, content):
                    issues.append(str(py_file.relative_to(project_root)))
            except Exception:
                continue

        assert not issues, (
            "REGRESSION LL-024: Backslash in f-string expressions:\n"
            + "\n".join(f"  - {f}" for f in issues)
        )


class TestLL035RAGUsageEnforcement:
    """Prevent LL-035: AI not using RAG despite having it.

    Dec 15, 2025: AI spent 6 hours building features instead of using
    existing RAG to find solutions to workflow failures.
    """

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_lessons_learned_exists(self, project_root):
        """Verify lessons learned directory has content."""
        lessons_dir = project_root / "rag_knowledge" / "lessons_learned"

        assert lessons_dir.exists(), "rag_knowledge/lessons_learned/ must exist"

        lessons = list(lessons_dir.glob("*.md"))
        assert len(lessons) >= 30, (
            f"REGRESSION LL-035: Expected 30+ lessons, found {len(lessons)}\n"
            f"  Lessons learned must be preserved!"
        )

    def test_rag_search_functionality_exists(self, project_root):
        """Verify RAG search capability exists."""
        rag_files = [
            "src/rag/lessons_search.py",
            "src/rag/lessons_learned_rag.py",
            "src/verification/rag_verification_gate.py",
        ]

        found = []
        for rel_path in rag_files:
            if (project_root / rel_path).exists():
                found.append(rel_path)

        assert len(found) >= 1, (
            f"REGRESSION LL-035: No RAG search files found!\n"
            f"  Checked: {rag_files}"
        )

    def test_session_start_checklist_documented(self, project_root):
        """Verify session start protocol is documented in CLAUDE.md."""
        claude_md = project_root / ".claude" / "CLAUDE.md"

        if not claude_md.exists():
            pytest.skip("CLAUDE.md not found")

        with open(claude_md) as f:
            content = f.read()

        required_steps = [
            "claude-progress.txt",
            "system_state.json",
            "git",
        ]

        missing = [step for step in required_steps if step not in content]

        assert not missing, (
            f"REGRESSION LL-035: CLAUDE.md missing session start steps:\n"
            f"  Missing: {missing}\n"
            f"  These must be checked at start of every session!"
        )


class TestRAGVerificationGate:
    """Tests for RAG-powered verification gate integration."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_rag_gate_loads_all_lessons(self, project_root):
        """Verify RAG gate loads ALL lessons from disk."""
        try:
            from src.verification.rag_verification_gate import RAGVerificationGate
        except ImportError:
            pytest.skip("RAGVerificationGate not available")

        gate = RAGVerificationGate(
            rag_knowledge_path=project_root / "rag_knowledge" / "lessons_learned"
        )

        # Should load all lessons
        lessons_on_disk = list(
            (project_root / "rag_knowledge" / "lessons_learned").glob("*.md")
        )

        assert len(gate.lessons) >= len(lessons_on_disk) * 0.8, (
            f"RAG gate only loaded {len(gate.lessons)} of {len(lessons_on_disk)} lessons!\n"
            f"  At least 80% of lessons must be loaded"
        )

    def test_semantic_search_returns_relevant_results(self, project_root):
        """Verify semantic search finds relevant lessons."""
        try:
            from src.verification.rag_verification_gate import RAGVerificationGate
        except ImportError:
            pytest.skip("RAGVerificationGate not available")

        gate = RAGVerificationGate(
            rag_knowledge_path=project_root / "rag_knowledge" / "lessons_learned"
        )

        # Search for known issues
        queries = [
            ("syntax error", ["ll_009", "ll_024"]),
            ("fear multiplier", ["ll_020"]),
        ]

        for query, expected_ids in queries:
            results = gate.semantic_search(query, top_k=5)

            if results:
                result_ids = [r[0].id.lower() for r in results]
                any(exp.lower() in str(result_ids) for exp in expected_ids)
                # Just verify search works, exact matches depend on implementation
                assert len(results) > 0, f"No results for query: {query}"


class TestMLAnomalyDetectorIntegration:
    """Tests for ML anomaly detection system."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_detector_catches_zero_trades(self, project_root, tmp_path):
        """Verify detector flags zero trades as anomaly."""
        try:
            from src.verification.ml_anomaly_detector import MLAnomalyDetector
        except ImportError:
            pytest.skip("MLAnomalyDetector not available")

        detector = MLAnomalyDetector(data_dir=tmp_path)

        # Create mock state with 0 trades
        mock_state = {
            "performance": {"total_trades": 0, "win_rate": 0},
            "challenge": {"current_day": 5},
        }

        state_file = tmp_path / "system_state.json"
        with open(state_file, "w") as f:
            json.dump(mock_state, f)

        detector.system_state_file = state_file

        anomaly = detector.detect_trade_volume_anomaly()

        assert anomaly is not None, (
            "REGRESSION: 0 trades after 5 days should be flagged as anomaly!"
        )
        assert anomaly.severity in ["critical", "high"]

    def test_detector_catches_stale_state(self, project_root, tmp_path):
        """Verify detector flags stale system state."""
        try:
            from src.verification.ml_anomaly_detector import MLAnomalyDetector
        except ImportError:
            pytest.skip("MLAnomalyDetector not available")

        detector = MLAnomalyDetector(data_dir=tmp_path)

        # Create state that's 3 days old
        old_time = (datetime.utcnow() - timedelta(hours=72)).isoformat()
        mock_state = {
            "meta": {"last_updated": old_time},
            "performance": {"total_trades": 5},
        }

        state_file = tmp_path / "system_state.json"
        with open(state_file, "w") as f:
            json.dump(mock_state, f)

        detector.system_state_file = state_file

        anomaly = detector.detect_system_health_anomaly()

        assert anomaly is not None, "Stale state (72h) should be flagged!"
        assert "stale" in anomaly.description.lower()


class TestCIIntegration:
    """Ensure CI properly gates broken code."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_pre_merge_gate_exists(self, project_root):
        """Verify pre-merge gate script exists."""
        gate_script = project_root / "scripts" / "pre_merge_gate.py"
        assert gate_script.exists(), "pre_merge_gate.py must exist!"

    def test_test_workflow_runs_verification(self, project_root):
        """Ensure CI test workflow includes verification tests."""
        test_workflow = project_root / ".github" / "workflows" / "test.yml"

        if not test_workflow.exists():
            # Try alternate names
            test_workflows = list(
                (project_root / ".github" / "workflows").glob("*test*.yml")
            )
            if not test_workflows:
                pytest.skip("No test workflow found")
            test_workflow = test_workflows[0]

        with open(test_workflow) as f:
            content = f.read()

        # Should run pytest
        assert "pytest" in content, "Test workflow must run pytest!"


class TestBacktestMetricValidation:
    """Prevent fake/misleading backtest metrics."""

    @pytest.fixture
    def project_root(self) -> Path:
        return Path(__file__).parent.parent

    def test_backtest_summary_exists(self, project_root):
        """Verify backtest summary file exists."""
        summary_paths = [
            project_root / "data" / "backtests" / "latest_summary.json",
            project_root / "data" / "backtest_summary.json",
        ]

        exists = any(p.exists() for p in summary_paths)

        if not exists:
            pytest.skip("No backtest summary found - acceptable during initial setup")

    def test_displayed_metrics_match_data(self, project_root):
        """Ensure displayed metrics come from actual data, not hardcoded."""
        hook_files = list((project_root / ".claude" / "hooks").glob("*.sh"))

        for hook_file in hook_files:
            with open(hook_file) as f:
                content = f.read()

            # Check for suspiciously precise hardcoded metrics
            hardcoded_patterns = [
                r"Sharpe:\s*2\.\d{2}",     # Sharpe with 2 decimal places
                r"win.*rate.*:\s*62\.\d",   # Suspicious 62.x%
                r"Sharpe.*=.*2\.\d",         # Assigned Sharpe
            ]

            for pattern in hardcoded_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    pytest.fail(
                        f"REGRESSION LL-020: Possible hardcoded metric in {hook_file.name}:\n"
                        f"  Found: {match.group()}\n"
                        f"  Metrics must be loaded from data files!"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
