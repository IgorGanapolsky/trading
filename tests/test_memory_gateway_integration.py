from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_mcp_config_pins_memory_gateway_server() -> None:
    config = json.loads((PROJECT_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["rlhf"]
    assert server["command"] == "npx"
    assert server["args"] == ["-y", "mcp-memory-gateway@0.7.1", "serve"]

    settings = json.loads((PROJECT_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    claude_server = settings["mcpServers"]["rlhf"]
    assert claude_server["command"] == "npx"
    assert claude_server["args"] == ["-y", "mcp-memory-gateway@0.7.1", "serve"]


def test_gsd_pipeline_uses_gateway_backed_hooks_only() -> None:
    content = (PROJECT_ROOT / ".claude" / "hooks" / "gsd-pipeline.sh").read_text(encoding="utf-8")
    assert 'run_hook "session-start.sh"' in content
    assert 'run_hook "user-prompt-submit.sh"' in content
    assert 'run_hook "inject_trading_context.sh"' in content
    assert 'run_hook "memory-gateway-pretool.sh"' in content
    assert "force_rag_learning.sh" not in content
    assert "session-start-memalign.sh" not in content


def test_gateway_hook_scripts_have_valid_bash_syntax() -> None:
    for relative_path in (
        ".claude/hooks/gsd-pipeline.sh",
        ".claude/hooks/session-start.sh",
        ".claude/hooks/user-prompt-submit.sh",
        ".claude/hooks/memory-gateway-pretool.sh",
    ):
        result = subprocess.run(
            ["bash", "-n", str(PROJECT_ROOT / relative_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


def test_auto_record_lesson_workflow_uses_gateway_and_no_main_push() -> None:
    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "auto-record-lesson.yml").read_text(
            encoding="utf-8"
        )
    )
    record_job = workflow["jobs"]["record-lesson"]
    step_commands = "\n".join(step.get("run", "") for step in record_job["steps"])
    assert "mcp-memory-gateway@0.7.1 capture" in step_commands
    assert "git push origin main" not in step_commands


def test_gateway_pretool_hook_has_repo_local_gate_config() -> None:
    hook_path = PROJECT_ROOT / ".claude" / "hooks" / "memory-gateway-pretool.sh"
    gates_path = PROJECT_ROOT / "config" / "memory-gateway" / "gates.json"
    assert hook_path.exists()
    assert gates_path.exists()
