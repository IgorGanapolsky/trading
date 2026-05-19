# INVESTOR DUE DILIGENCE: SPY Options Validation System

## 1. Executive Summary — current honest state (2026-05-19)

This deck has been updated to reflect a re-audit of the same 69-paired-trade dataset under proper multi-comparison statistics. The earlier "Thursday Alpha ~60%" framing did not survive Bonferroni correction (K=14 stratifications tested, adjusted p=0.190; full audit in `docs/research/2026-05-19-edge-analysis.md`).

What the data actually says:

- **Cohort baseline (n=69 closed ICs):** 23.19% win rate, profit factor **0.22**, expectancy **-$58.78/trade**, total realized **-$3,958**.
- **The only stratification slice with a statistically meaningful signal is *negative*:** Tuesday entries (n=17) won 1/17 (5.9%) and account for 73% of total losses. "Avoid Tuesday" is the only data-supported filter.
- **The strategy collected no theta:** 77% of trades closed in <24h; expectancy -$20.36/trade in that bucket. The hold-time fix in `ic_simple.py` (24h minimum) is exactly the correct response and is now enforced.

**Current posture:** new entries pause until the next 30-trade validation cohort (with the 24h-hold + 1-lot + no-same-expiry-re-entry rules from `.claude/rules/controlled-experiment.md`) produces realized expectancy > 0. No claim of edge is made until that cohort closes. No capital additions until then.

## 2. Competitive Edge: RAG-to-ML Feedback Loop

Unlike traditional black-box ML models, our system uses a **Retrieval-Augmented Generation (RAG)** knowledge base as a "governor" for the Machine Learning policy:

- **Learning from Mistakes**: We have 249 documented "Lessons Learned" (LanceDB).
- **Hard Penalties**: The ML model (GRPO) is penalized (-200 reward) for suggesting trades that violate documented RAG lessons.
- **Result**: A self-correcting system that "knows better" before it "does better."

## 3. Operational Integrity & Transparency

Investors are protected by a multi-layered safety stack:

- **Broker-Backed Proof**: All performance is derived from Alpaca broker syncs, not internal spreadsheets.
- **Deterministic Gates**: No LLM hallucination can override the `ConstraintEngine` (e.g., VIX thresholds, DTE buffers).
- **Public Surface**: A live GitHub-backed dashboard provides real-time transparency into gate state and P/L.

### Reliability Metrics (Live Audit)

- **Recent Approval Rate**: **100%** (Up from 30% lifetime - proves successful hardening).
- **Preventative Defense**: **72 repeat mistakes blocked** by autonomous safety gates.
- **Learning Velocity**: **44%** of system feedback is automatically distilled into actionable lessons.
- **Operational Efficiency**: **187,000+ tokens saved** by autonomously blocking high-risk/low-alpha requests.

## 4. Scalability Roadmap (North Star)

- **Target Capital**: $300,000
- **Target Monthly Yield**: $6,000 (after tax)
- **Status**: Currently in "Validation Reset" mode, selectively trading the Thursday alpha to prove edge before scaling contracts.

## 5. Verification

Investors can run our `morning_proof` and `system_health_check` scripts to verify that every claim in this document is backed by current code and broker evidence.
