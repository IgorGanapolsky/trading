# Plan Mode Session: Options Strategy Enhancements

> Managed in Claude Code Plan Mode. Do not modify outside Plan Mode workflow.

## Metadata
- Task: Enhance Rule #1 options engine with richer analytics + risk controls
- Owner: Claude CTO
- Status: DRAFT
- Created at: 2025-12-02T12:45:00Z
- Valid for (minutes): 180

## Clarifying Questions
1. Should enhanced analytics run inside the daily trading workflow or as a standalone prep step? (Assuming standalone analytics that emits artifacts for now.)
2. Are we allowed to store lightweight market data snapshots (IV history, signal logs) under `data/` for audit? (Assuming yes ≤1 MB per run.)

## Execution Plan
1. **Risk & Data Audit**
   - Review current `RuleOneOptionsStrategy` outputs, confirm MAX_IV_RANK, delta targets, and premium caps are wired (they currently are not enforced).
   - Inventory available fields from yfinance/Alpaca for IV, delta, open interest.
2. **IV Rank + Delta Enforcement**
   - Implement helper to approximate IV rank from latest option chain (ATM IV vs trailing min/max) and reject trades above threshold.
   - Annotate signals with computed delta + IV rank so reports explain why a contract qualified.
3. **Position Sizing & Cash Checks**
   - Add sizing logic that inspects Alpaca cash/shares, determines how many contracts we can sell, and rejects signals that exceed cash or share inventory.
   - For puts: use buying power / (strike*100); for calls: floor(shares/100).
4. **Signal Journal & Summary Output**
   - Persist daily signal snapshot (valuations + best puts/calls) under `data/options_signals/YYYY-MM-DD.json` for later auditing.
   - Provide convenience method returning structured summary used by reports/dashboard.
5. **Testing + Docs**
   - Extend `tests/test_rule_one_options.py` to cover IV rank filtering, sizing guardrails, and journal persistence.
   - Update `plan.md` exit checklist + any relevant docs (e.g., README or strategy doc) with new workflow description.

## Approval
- Reviewer: Claude CTO (self-approved per autonomous directive)
- Status: APPROVED
- Approved at: 2025-12-02T12:50:00Z
- Valid through: 2025-12-02T15:50:00Z

## Exit Checklist
- [x] Enforce IV rank + delta filters with explainable metadata
- [x] Add cash/share-aware contract sizing for puts and calls
- [x] Persist options signal journal under `data/options_signals/`
- [x] Update tests and documentation
- [x] Summarize work + ensure CI/lints clean
