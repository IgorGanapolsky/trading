# Trading

**SPY put-credit validation and real-money control plane** with broker-backed
ledgers, deterministic risk gates, reconciliation, hybrid RAG, and explicit
proof of the **$1,000/month after-tax** objective.

[Docs](docs/README.md) · [Operator guide](docs/operator-guide.md) ·
[RAG architecture](docs/RAG_PIPELINE_DEEP_DIVE.md) ·
[Agent skill](skills/trading-ops/SKILL.md) ·
[Bogleheads research](skills/bogleheads-research/SKILL.md) ·
[Coordination](docs/AGENT_COORDINATION.md)

> **Current verified state (2026-08-03): not live-profit ready.** The active
> strategy has 1 closed paper outcome, live execution is blocked, confirmed
> broker-to-bank remittance is $0, and the latest provider-backed live Alpaca
> sync returned `unauthorized`. Real-money capability, a funded account, an
> order, a fill, profitable performance, and banked after-tax profit are
> separate proof surfaces. The active strategy's edge is **not proven**.

## Objective and evidence contract

The operating objective is $1,000/month after tax. With the system's
conservative 37% tax reserve, that requires approximately **$1,587/month of
realized pre-tax profit**. This is a requirement, not a projection.

The goal is proved only by a confirmed brokerage-to-bank remittance ledger.
Backtests, paper gains, account funding, submitted orders, fills, model scores,
and healthy CI do not prove after-tax income.

| Proof surface               | Current verified evidence                                                          |
| --------------------------- | ---------------------------------------------------------------------------------- |
| Active strategy             | `spy_put_credit`: 1-lot, $5-wide SPY bull put credit spread                        |
| Closed active-family sample | 1 of 100 desk-grade minimum; +$17 is not statistically sufficient                  |
| Retired strategy            | Iron-condor entry families killed after PF 0.16 and negative expectancy            |
| Inventory                   | One protected two-leg paper SPY put spread; broker/journal audit clean             |
| Live Alpaca                 | Credentials configured in GitHub, but latest provider sync returned `unauthorized` |
| Mercury funding proof       | Not available in the confirmed transfer ledger in this checkout                    |
| Banked monthly profit       | $0 confirmed for August 2026                                                       |

Provider evidence: [North Star broker sync run 30817404104](https://github.com/IgorGanapolsky/trading/actions/runs/30817404104).

## System architecture

```text
market data + broker orders/fills + Mercury transfer events
                         │
                         ▼
              normalize and reconcile
                         │
           ┌─────────────┴─────────────┐
           ▼                           ▼
 paired trade ledger            broker inventory audit
           │                           │
           └─────────────┬─────────────┘
                         ▼
        statistical edge + freshness + risk gates
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        paper validation      live order gateway
                              (currently blocked)
                                     │
                                     ▼
                        fill → realized P&L → tax reserve
                                     │
                                     ▼
                         confirmed bank remittance
```

Every new-risk order must cross the mandatory policy layer and `TradeGateway`.
The system fails closed on stale broker state, unclean inventory, missing paired
outcomes, insufficient edge, negative confidence bounds, strategy-family
drift, or an active kill switch.

### Strategy promotion policy

Thirty closed paper trades are only an interim experiment checkpoint. Live
capital requires all of the following:

- at least 100 paired, closed active-family outcomes across multiple regimes;
- positive 95% lower confidence bound for expectancy;
- profit factor at least 1.2 and positive total realized P&L;
- stable rolling-20 performance;
- fresh provider state and clean broker-to-journal inventory;
- the reviewed live switch, strategy kill switch, and bank gate all open.

Position sizing uses realized outcomes, observed trade cadence, a 1% per-trade
risk ceiling, and a half-Kelly cap. It never assumes an 85% win rate and never
forces one contract when the risk budget cannot afford it.

## Lessons and retrieval gate

Operational feedback follows one governed path:

```text
👎 feedback → normalize/redact → quality gate → versioned SQLite FTS5
  → BM25 + bigram/unigram + vector retrieval with metadata filters
  → up to three queries only when lexical confidence < 0.6
  → cross-encoder or validated LLM rerank; heuristic fallback is degraded
  → bounded cited context → deterministic tool-call decision
```

The default offline fallback remains available for recovery, but production
readiness requires the semantic embedding backend, strict-quality indexing
(legacy failures are quarantined), retrieval regression gates, and observable
latency/error/degradation metrics. See
[docs/RAG_PIPELINE_DEEP_DIVE.md](docs/RAG_PIPELINE_DEEP_DIVE.md).

External forum research is a separate trust domain. The Bogleheads path makes
one bounded public-feed request, normalizes and quality-gates documents, assigns
stable hashes, creates overlapping chunks, and transactionally upserts them into
an isolated SQLite FTS5 index. Those documents are labeled
`untrusted_research` with `gate_effect: none`; they cannot authorize a trade or
silently become operational lessons. Authenticated Chrome is used only for
needed public-thread context. Forum posting is never an ingestion side effect.

## Operator commands

Requires Python 3.11.

```bash
git clone https://github.com/IgorGanapolsky/trading
cd trading
make setup

# Read-only evidence and health
.venv/bin/python scripts/spy_put_credit.py --status
.venv/bin/python scripts/audit_open_inventory.py
.venv/bin/python scripts/put_credit_cohort_scorecard.py
.venv/bin/python scripts/world_class_trading_readiness.py --allow-not-ready
make health

# Plans only; no order submission
make dry-run

# Engineering verification
make check
```

The readiness command returns non-zero until the complete system contract is
satisfied. `--allow-not-ready` is for inspection only and never opens a gate.

## Repository map

| Path             | Purpose                                                           |
| ---------------- | ----------------------------------------------------------------- |
| `src/`           | Product, execution, analytics, bank, safety, and RAG code         |
| `scripts/`       | Explicit operator, evidence, and maintenance entry points         |
| `tests/`         | Unit, integration, contract, concurrency, service, and eval tests |
| `skills/`        | Reviewed operator procedures                                      |
| `config/`        | Static configuration                                              |
| `data/`          | Canonical ledgers and compact evidence snapshots                  |
| `rag_knowledge/` | Curated immutable lesson sources, not runtime indexes             |
| `docs/`          | Architecture and operating documentation                          |

Start with [CONTRIBUTING.md](CONTRIBUTING.md),
[data/README.md](data/README.md), and [docs/EXTENSIONS.md](docs/EXTENSIONS.md).

## Evidence boundary

- A configured secret is not an authenticated provider session.
- Mercury cash is not brokerage capital until transfer settlement is confirmed.
- A submitted order is not a fill; a fill is not a paired closed outcome.
- Paper performance is not live performance.
- Realized brokerage P&L is not after-tax banked profit.
- An A+ control plane cannot manufacture strategy edge.

MIT licensed. Nothing in this repository is financial advice.
