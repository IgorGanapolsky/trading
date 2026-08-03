# World-class path to $1,000/mo after-tax (real money)

**CEO near-term cash goal:** $1,000/month after-tax profit.  
**North Star (canonical):** $6,000/month after-tax on ~$300K capital path.  
**This document is process truth, not a revenue forecast.**

## Brutal current state (evidence)

| Fact                     | Value                                                        |
| ------------------------ | ------------------------------------------------------------ |
| Paper equity             | ~$94,150 (−5.8% from $100k)                                  |
| Live equity              | **$0** (prior live $20 → −100%)                              |
| Active family            | `spy_put_credit` paper only                                  |
| IC / iron condor         | **KILLED** (PF ~0.17, expectancy ~−$47, large realized loss) |
| Put-credit closed cohort | **n=1 / 30** (~3% to gate), +$17 total                       |
| Live blocked             | **true** until EDGE_CANDIDATE                                |
| Inventory                | clean (2-leg SPY put vertical open)                          |

A system that is mostly paper validation with n=1 on the successor strategy is **not** yet a production cash engine. Calling RAG/infra “production-grade trading” without edge is marketing.

## What “world-class” means here

World-class is **not** more frameworks. It is:

1. **One strategy**, fixed profile, no mid-cohort parameter thrash
2. **Paired-ledger truth** (unpaired fills quarantined)
3. **Kill criteria in code** (n≥30, expectancy>0, PF>1, total PnL>0)
4. **Inventory hygiene** before new risk
5. **Live capital only after edge**
6. **Boring repetition** at 1-lot, then scale size — never scale a PF&lt;1 process
7. **LLM/RAG production plane A+** (latency/cost, observability, fail-closed modes,
   structured validation, operator document ACL, no heavy frameworks) — process only;
   it does **not** print dollars

### LLM/RAG A+ control plane (process)

```bash
python3 -c "from src.observability.llm_production_control_plane import evaluate_llm_production_control_plane; \
r=evaluate_llm_production_control_plane(); print(r.overall_grade, r.overall_score_0_10, r.a_plus_ready)"
python3 scripts/world_class_production_scorecard.py
```

| Dimension            | Contract                                                                 |
| -------------------- | ------------------------------------------------------------------------ |
| latency_cost_control | ModelSelector tiers, RAG LRU cache wired, deterministic order path       |
| observability        | route report, token monitor, retrieval JSONL scores, eval module         |
| failure_modes        | empty_index fail-closed, gate modes, CRITICAL lesson blocks, kill switch |
| structured_outputs   | Pydantic decisions, PreToolValidator fail-closed for money tools         |
| multi_tenancy_acl    | single-operator + document sensitivity + secret scrub                    |
| framework_discipline | no LangChain/LangGraph/LlamaIndex on money path                          |

**Hard truth:** LLM plane A+ + ops A+ with put-credit n&lt;30 still means **overall cash engine is not A+**.
`$1,000/mo after-tax` requires EDGE_CANDIDATE then funded live. Do not confuse planes.

## Math for $1,000/mo after-tax (requirements, not forecasts)

Assume ~30% effective tax on SPY equity options short-term gains:

| Quantity                     | Approx.                      |
| ---------------------------- | ---------------------------- |
| After-tax goal               | $1,000/mo                    |
| Pre-tax needed               | **~$1,430/mo**               |
| On $94k paper equity         | **~1.5% / month** pre-tax    |
| On 10 clean closes/mo        | **~$143 expectancy / trade** |
| Capital for ~1%/mo pre-tax   | **~$143k**                   |
| Capital for ~1.5%/mo pre-tax | **~$95k**                    |

With **1-lot** $5-wide put credits, credits are often tens of dollars — so **$143/trade expectancy is not free**. Options:

- **Prove edge first**, then **raise lots** under hard risk caps, and/or
- **Add capital** only after EDGE_CANDIDATE, and/or
- Accept that **$1k/mo is multi-phase** (edge → small live → scale).

With **n=1**, any monthly income projection is **undefined**. World-class desks do not deposit to “create” a number.

## Phased production path

### Phase 0 — Honesty (now)

- [x] Kill IC new entries
- [x] Paper-only put credit
- [x] Live blocked in kill switch + `spy_put_credit --live`
- [x] Cohort scorecard + this production scorecard
- [ ] Operator runs scorecards **every trading day**

### Phase 1 — Validation factory (until n≥30)

Goal: **30 clean** put-credit structures, same profile:

- SPY only, 1-lot, $5 wide, 15Δ-ish short, 30–45 DTE
- Max 3/day, max 2 concurrent
- Stop 200% credit, TP 25%, exit by 7 DTE
- Regime gate: IVR/VIX rules as coded
- No same-expiry re-entry after loss
- Inventory must stay clean

**Exit Phase 1 only if:**

- `kill_criteria.verdict == EDGE_CANDIDATE`
- else **NO_EDGE_KILL** → redesign written hypothesis (do not revive IC by default)

### Phase 2 — Micro live (only if EDGE_CANDIDATE)

- Fund live with **small** capital (start 1-lot, not 50-lot history)
- Same risk constants; no “live special cases”
- Parallel paper continues for regression

### Phase 3 — Scale toward $1k/mo after-tax

- Increase lot size only under max risk % of equity
- Track after-tax set-aside (SPY = STCG unless XSP/1256 later)
- Only then treat system as a **cash engine**

### Phase 4 — North Star ($6k/mo)

- Capital path ~$300k @ ~2%/mo is the long-horizon map
- Do not skip Phase 1–3 with leverage or undefined risk

## Daily operator command (desk ritual)

```bash
# One command (recommended):
python3 scripts/production_desk_session.py
# or: make production-desk

# Manual equivalent:
python3 scripts/sync_alpaca_state.py
python3 scripts/audit_open_inventory.py
python3 scripts/put_credit_cohort_scorecard.py
python3 scripts/world_class_production_scorecard.py
python3 scripts/spy_put_credit.py --production-gate
python3 scripts/spy_put_credit.py --status
# if RTH + production gate allow_new_risk + regime ok:
python3 scripts/spy_put_credit.py --dry-run
# paper execute only when dry-run valid (never --live until EDGE_CANDIDATE)
```

### Two grades (do not confuse them)

| Grade                                      | Meaning                                                    | Can be A+ today?                          |
| ------------------------------------------ | ---------------------------------------------------------- | ----------------------------------------- |
| **process_ops / production_control_plane** | Halt, family, inventory, freshness, kill switch, live lock | **Yes** — when desk ritual green          |
| **overall (cash engine)**                  | Edge sample + live capital + readiness                     | **No** until EDGE_CANDIDATE + funded live |

## Anti-goals (explicit)

- Scaling live to “make $1k this month” with n&lt;30
- Counting unpaired cash as edge
- Reviving iron condors because recent legs “looked fine”
- Confusing RAG/CI green with profitability
- Changing profile mid-cohort to chase a better headline win rate

## Scorecard

```bash
python3 scripts/world_class_production_scorecard.py
# JSON: data/audit/world_class_production_latest.json
```

Overall grade will stay low until **edge + live capital** exist. That is correct.

## Bottom line

**World-class trading systems make money after they have edge, then scale.**  
Today we are in **Phase 1 validation** with **$0 live**. The production path to $1k/mo is:

**finish clean n=30 put-credit → EDGE_CANDIDATE → micro live → scale lots/capital under hard risk.**

Anything else is theater.
