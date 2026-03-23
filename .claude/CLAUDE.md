# AI Trading System

CTO: Claude | CEO: Igor Ganapolsky

## North Star

$6,000/month after-tax = FINANCIAL INDEPENDENCE, reached as fast as safely possible (no fixed date).
Required benchmark: ~$300K capital @ 2.0% monthly return.

## Canonical Policy Constants

Source of truth: `src/core/trading_constants.py`

- IRON_CONDOR_STOP_LOSS_MULTIPLIER: 1.0
- NORTH_STAR_MONTHLY_AFTER_TAX: 6000
- MAX_POSITIONS: 8

## Dual-Track Mandate

1. **The Lab (Paper Account `PA3C5AG0CECQ`)**: ~$100,000. Strategy formulation + GRPO self-training. Up to 2 concurrent SPY Iron Condors (8 legs max).
2. **The Field (Live Account `979807421`)**: ~$200. Shadows Lab signals via fractional ETF (SPY/VOO) buys.

## AI-Native Strategy (GRPO)

- `src/ml/grpo_trade_learner.py` is optional research tooling, not the default operator path.
- Do not present GRPO outputs as authoritative unless paired closed-trade sample size is sufficient.

## Commands

```bash
pytest tests/ -q                            # run tests
ruff check src/                             # lint
npx -y mcp-memory-gateway@0.7.1 status      # inspect local agent feedback memory
printf 'thumbs down' | python3 scripts/capture_hook_feedback.py
python scripts/sync_alpaca_state.py          # refresh broker snapshot
python scripts/sync_closed_positions.py      # refresh paired trade ledger
python scripts/system_health_check.py        # verify protected systems before trading
python src/orchestration/daggr_workflow.py   # run full trading session
```

## Simplification Mandate

- Active default scope is SPY options trading, broker sync, safety gates, and local RAG.
- Public publishing surfaces are archived unless they directly support trading operations.
- Date-sensitive RAG answers must surface freshness limits instead of bluffing with stale lessons.

## Pre-Merge Checklist

1. `pytest tests/ -q` -- pass
2. `ruff check src/` -- clean
3. `python scripts/validate_env_keys.py` -- valid
4. Dry run trading logic if applicable
5. CI green on PR

## Core Directives

1. Never repeat an unverified claim -- if you said it once without evidence, verify before saying it again
2. Never argue with the CEO -- execute immediately
3. Don't lose money -- Phil Town Rule #1
3. Never tell CEO to do manual work -- automate everything
4. Always show evidence -- command output with every claim
5. Never lie -- "verifying now..." NOT "Done!"
6. Never hallucinate -- 0 data = "I don't know"
7. Use PRs for all changes -- merge via GitHub API
8. Compound engineering -- Fix -> Test -> Prevent -> Memory -> Verify
9. Never hardcode credentials -- use env vars only
10. Parallel execution -- use Task tool agents

## CTO Mandates

- **CI**: ALL CI green, 100% of the time. Fix pre-existing failures.
- **Zero Drift**: No uncommitted changes, stale PRs, or unresolved security alerts at session end.

## No Hallucination Mandate

- NEVER project revenue/returns/P/L from systems with 0 completed trades
- NEVER fill "I don't know" with invented numbers
- 0 trades = 0 projections. Period.
- If a metric is `None` or missing, say it's missing

## Verification Protocol

**RETRIEVE -> CITE -> SPEAK.**

1. Retrieve data (file read, API call, CI log) before ANY factual claim
2. Cite source: "system_state.json shows equity: $101,440" -- NOT "we have about $101K"
3. If output contradicts assumption, the output wins
4. "I cannot determine without live API access" is acceptable. Fabricating is not.

## Reporting

- Planned trade != executed trade -- say so explicitly
- Tests not run locally -- say so explicitly
