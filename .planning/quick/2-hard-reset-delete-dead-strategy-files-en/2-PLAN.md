---
phase: quick-2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/strategies/core_strategy.py
  - src/strategies/momentum_strategy.py
  - src/strategies/vix_mean_reversion.py
  - src/agents/momentum_agent.py
  - src/safety/milestone_controller.py
  - src/orchestration/harness/strategy_harness.py
  - scripts/autonomous_trader.py
  - tests/test_core_strategy.py
  - tests/test_momentum_strategy.py
  - tests/test_momentum_agent.py
  - tests/test_vix_mean_reversion_signal.py
  - tests/test_sync_trades_to_rag.py
  - tests/test_decision_trace.py
  - .github/workflows/ci.yml
autonomous: true
requirements: [CLEANUP-01]

must_haves:
  truths:
    - "pytest tests/ -q passes with no ImportError for deleted modules"
    - "ruff check src/ reports no errors"
    - "No file in src/ or tests/ imports core_strategy, momentum_strategy, or vix_mean_reversion"
    - "ci.yml contains no references to run_core_strategy_reference_backtest.py or CoreStrategy import check"
  artifacts:
    - path: "src/strategies/iron_condor/"
      provides: "Only remaining strategy implementation"
    - path: "src/strategies/__init__.py"
      provides: "Strategy registry without dead entries"
  key_links:
    - from: "tests/"
      to: "src/strategies/"
      via: "pytest collection"
      pattern: "no ImportError on collection"
---

<objective>
Hard-delete all dead strategy files (core_strategy, momentum_strategy, vix_mean_reversion, autonomous_trader) and repair every file that imported them so CI stays green.

Purpose: The codebase has one strategy (SPY iron condors via iron_condor_trader.py). These dead files add noise, fail silently, and mislead future AI sessions about what the system does.
Output: Deleted files gone from git, zero broken imports, pytest passing.
</objective>

<execution_context>
@/Users/ganapolsky_i/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ganapolsky_i/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@/Users/ganapolsky_i/workspace/git/igor/trading/.planning/STATE.md
@/Users/ganapolsky_i/workspace/git/igor/trading/.claude/rules/MANDATORY_RULES.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Delete dead test files and dead strategy source files</name>
  <files>
    tests/test_core_strategy.py
    tests/test_momentum_strategy.py
    src/strategies/core_strategy.py
    src/strategies/momentum_strategy.py
    src/strategies/vix_mean_reversion.py
    scripts/autonomous_trader.py
  </files>
  <action>
NOTE: scripts/pre_cleanup_check.py does not exist in this repo. Skip it. Proceed directly.

Step 1 — Delete test files first (they import src files, removing them prevents collection errors during later pytest runs):
  git rm tests/test_core_strategy.py
  git rm tests/test_momentum_strategy.py

Step 2 — Delete dead strategy source files:
  git rm src/strategies/core_strategy.py
  git rm src/strategies/momentum_strategy.py
  git rm src/strategies/vix_mean_reversion.py

Step 3 — Delete autonomous_trader.py (uses SmartDCA stock-buying strategy, disabled in daily-trading.yml with comment "SKIPPING autonomous_trader.py - uses SmartDCA (stock buying)"):
  git rm scripts/autonomous_trader.py

Do NOT delete:
  - src/signals/vix_mean_reversion_signal.py (separate module, only imports from itself)
  - src/strategies/registry.py (check if it references deleted files before touching)
  - src/strategies/reit_strategy.py or rule_one_options.py (not in scope)
  </action>
  <verify>
    git status --short | grep -E "^D " to confirm 6 files staged for deletion.
    python3 -c "import ast; ast.parse(open('src/strategies/__init__.py').read())" to confirm init still parses.
  </verify>
  <done>Six files deleted from git index. No __pycache__ references remain in git-tracked files.</done>
</task>

<task type="auto">
  <name>Task 2: Repair broken imports in surviving src files</name>
  <files>
    src/agents/momentum_agent.py
    src/safety/milestone_controller.py
    src/orchestration/harness/strategy_harness.py
  </files>
  <action>
For each file, remove the import line for deleted modules and fix any code that used those imports. Specific actions:

src/agents/momentum_agent.py — line 10: `from src.strategies.momentum_strategy import MomentumStrategy`
  - Remove that import line.
  - Scan the rest of the file for any use of MomentumStrategy. If the class is only used in type hints or instantiation, replace with a NotImplementedError stub or remove the dependent method entirely. The goal is zero broken references, not preserving dead functionality.

src/safety/milestone_controller.py — contains a string reference "Inherit from 'BaseStrategy' in 'src.strategies.core_strategy'" inside a docstring or comment (line ~50). This is a comment, not a live import — simply update or delete the comment. Verify with: grep -n "import.*core_strategy" src/safety/milestone_controller.py (should return nothing).

src/orchestration/harness/strategy_harness.py — also contains the comment reference. Same fix: remove or reword the comment. Verify with: grep -n "import.*core_strategy" src/orchestration/harness/strategy_harness.py (should return nothing).

src/strategies/registry.py — read it first. If it contains references to CoreStrategy, MomentumStrategy, or VixMeanReversion, remove those entries. Leave IronCondorStrategy entry intact.

After edits, run: ruff check src/ --select E,F to confirm no import errors.
  </action>
  <verify>
    grep -rn "from src.strategies.core_strategy\|from src.strategies.momentum_strategy\|from src.strategies.vix_mean_reversion" src/ should return 0 lines.
    python3 -c "import src.agents.momentum_agent" should not raise ImportError (may raise other errors if env vars missing — that is acceptable).
  </verify>
  <done>Zero Python import statements for deleted modules remain in src/. ruff check src/ exits 0.</done>
</task>

<task type="auto">
  <name>Task 3: Update CI workflow and surviving test files, then verify</name>
  <files>
    .github/workflows/ci.yml
    tests/test_sync_trades_to_rag.py
    tests/test_momentum_agent.py
    tests/test_decision_trace.py
  </files>
  <action>
.github/workflows/ci.yml — four references to remove:
  - Line 551-552: Already commented out (lines start with #) — leave as-is or remove the dead comment block.
  - Line 574: `python scripts/run_core_strategy_reference_backtest.py || {` — remove this entire step or comment it out. Check if run_core_strategy_reference_backtest.py exists; if not, just delete the step block entirely.
  - Line 709: `("CoreStrategy", "from src.strategies.core_strategy import CoreStrategy"),` — this is inside a CI import-validation check list. Remove just this tuple entry from the list.

tests/test_sync_trades_to_rag.py — lines 63-74 contain `"strategy": "core_strategy"` and `assert "core_strategy" in doc`. These are testing a trade document structure. Change "core_strategy" to "iron_condor" in both the mock fixture and the assertion to reflect the actual current strategy.

tests/test_momentum_agent.py — contains `assert agent._strategy.name == "momentum_strategy"`. This test is testing the momentum agent which no longer exists in a meaningful way. Delete this test file entirely with `git rm tests/test_momentum_agent.py`.

tests/test_decision_trace.py — lines 24 and 130 reference `"src.signals.vix_mean_reversion_signal"` as a string key in a dictionary (not a live import). Read the test context: if vix_mean_reversion_signal still exists as a module (src/signals/vix_mean_reversion_signal.py does exist per grep), the reference may still be valid. Only remove if the module itself is being deleted — it is NOT in scope for deletion. Leave test_decision_trace.py unchanged.

After all edits, run verification:
  cd /Users/ganapolsky_i/workspace/git/igor/trading
  pytest tests/ -x --timeout=30 --ignore=tests/integration -q 2>&1 | tail -20
  ruff check src/ 2>&1
  </action>
  <verify>
    pytest tests/ -x --timeout=30 --ignore=tests/integration -q exits 0 (or fails only on pre-existing unrelated failures — confirm no new ImportError failures).
    grep -rn "core_strategy\|momentum_strategy\|vix_mean_reversion" .github/workflows/ci.yml tests/ src/ --include="*.py" --include="*.yml" should return 0 results from non-comment, non-deleted-module lines in src/ and active CI steps.
  </verify>
  <done>
    - pytest passes (no new failures introduced by this cleanup).
    - ruff check src/ exits clean.
    - CI yml has no runnable steps referencing deleted scripts.
    - All changes committed to a branch and pushed via PR.
  </done>
</task>

</tasks>

<verification>
After all three tasks:

1. No Python file in src/ or tests/ imports core_strategy, momentum_strategy, or vix_mean_reversion:
   grep -rn "from src.strategies.core_strategy\|from src.strategies.momentum_strategy\|from src.strategies.vix_mean_reversion" src/ tests/ --include="*.py"
   Expected: 0 results

2. Deleted files are gone:
   ls src/strategies/core_strategy.py src/strategies/momentum_strategy.py src/strategies/vix_mean_reversion.py scripts/autonomous_trader.py
   Expected: all "No such file"

3. Test suite passes:
   pytest tests/ -x --timeout=30 --ignore=tests/integration -q
   Expected: exit 0 (or same pre-existing failures as before this change)

4. Linter clean:
   ruff check src/
   Expected: exit 0
</verification>

<success_criteria>
- Six files deleted from git: test_core_strategy.py, test_momentum_strategy.py, core_strategy.py, momentum_strategy.py, vix_mean_reversion.py, autonomous_trader.py
- Zero import statements referencing deleted modules in any remaining file
- pytest exits 0 with no new failures
- ruff check src/ exits 0
- PR merged with green CI
</success_criteria>

<output>
After completion, create `/Users/ganapolsky_i/workspace/git/igor/trading/.planning/quick/2-hard-reset-delete-dead-strategy-files-en/2-SUMMARY.md`
</output>
