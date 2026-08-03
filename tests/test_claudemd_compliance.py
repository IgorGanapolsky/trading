import json
import re
from pathlib import Path

WORKFLOW = Path(".github/workflows/put-credit-validation.yml")
KILL_SWITCH = Path("data/runtime/strategy_kill_switch.json")


def test_documented_active_path_is_put_credit() -> None:
    directives = Path("CLAUDE.md").read_text() + Path(".claude/CLAUDE.md").read_text()
    assert "spy_put_credit.py" in directives
    assert "paper" in directives.lower()


def test_killed_entry_scripts_are_absent() -> None:
    for path in (
        "scripts/ic_simple.py",
        "scripts/iron_condor_trader.py",
        "scripts/iron_condor_guardian.py",
        "scripts/iron_condor_scanner.py",
    ):
        assert not Path(path).exists()


def test_workflow_only_executes_current_entry_path() -> None:
    text = WORKFLOW.read_text()
    assert "python3 scripts/spy_put_credit.py" in text and "--execute-paper" in text
    assert (
        "--live" not in text and "iron_condor_trader.py" not in text and "ic_simple.py" not in text
    )


def test_workflows_do_not_default_to_forbidden_tickers() -> None:
    forbidden = re.compile(r"default:\s*['\"]?(SOFI|AMD|NVDA|INTC)['\"]?", re.IGNORECASE)
    for workflow in Path(".github/workflows").glob("*.yml"):
        assert forbidden.search(workflow.read_text()) is None, workflow


def test_kill_switch_blocks_live() -> None:
    state = json.loads(KILL_SWITCH.read_text())
    assert state["live_blocked"] is True
    assert {"ic_simple", "iron_condor"} <= set(state["killed_families"])
    assert state["active_family"] == "spy_put_credit"
