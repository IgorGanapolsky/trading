# LL-640 — Bounded tech-debt audit (2026-09-16)

## Facts

- Hygiene scanner on `origin/main` `043c9b801`: **0 errors, 0 warnings**, 1692 files, 341082 physical lines, 226 lessons, 0 duplicate lesson IDs.
- Ruff: clean (including F401/F841).
- Pytest collect: **3864** tests. Coverage JSON is not a CI artifact; do **not** invent 100% coverage.
- A naive “zero importer” scan flagged 16 `src/` modules; `rg` proved most are live (`yfinance_wrapper`, `sandbox_agent`, `reit_strategy` registry, etc.). LL-225 still holds: grep before claiming dead.
- Deleted only proven-dead surfaces (zero `rg` hits outside the file):
  - `src/eval/eval_engineering_skill.py` (549 lines) — LangChain Harbor eval theater, unused.
  - `scripts/ingest_phil_town_youtube.py` (968 lines) — unused CLI; Phil Town knowledge already lives under `rag_knowledge/`.
- Left in place: `reit_strategy.py` (feature flag + `config/strategy_registry.json`), close/liquidate scripts, AGENT-624/#4703 files.

## Prevention

- `tests/test_repo_hygiene.py::test_proven_dead_modules_stay_deleted` fails if those paths return.
- Whole-repo “line-by-line every file” audits are refused: bound to scanner findings + caller proof (LL-349).

## Coverage honesty

Report collected tests + scanner errors. Do not state “coverage at 100%” without a matching `pytest --cov` totals object for the same source scope.
