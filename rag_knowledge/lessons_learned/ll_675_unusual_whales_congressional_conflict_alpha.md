# LL-675: Unusual Whales Congressional Committee Conflict & Options Flow Alpha

**ID**: LL-675
**Date**: 2026-09-29
**Severity**: LOW
**Category**: Alpha Signals, Microstructure, Strategic Intelligence
**Status**: ACTIVE

## Context

Reverse-engineered and institutionalized retail intelligence models inspired by Unusual Whales and Congress trading tracking:
1. Disclosed trades under the STOCK Act suffer statutory 30-45 day reporting lags.
2. Raw politician trade copies without committee jurisdiction alignment produce noisy, unhedged signals.
3. Combining Congressional committee jurisdiction conflicts with real-time institutional Unusual Options Activity (sweeps/blocks: $Vol/OI \ge 1.5$, premium $\ge \$250\text{k}$) and dealer Gamma Exposure (GEX) regimes produces high-conviction directional and credit alpha.

## Key Principles Codified

1. **Committee Jurisdiction Mapping** (`src/analytics/congressional_flow_tracker.py`):
   - Mapped high-impact Congressional committees (Armed Services, Energy and Commerce, Financial Services, Intelligence, Banking, Agriculture, Transportation) to their regulated sectors and ticker universes.
   - Profiled key Congressional committee members (Nancy Pelosi, Tommy Tuberville, Dan Crenshaw, Michael McCaul, Ro Khanna, Josh Gottheimer) with empirical conflict weighting.
2. **Exponential Disclosure Decay**:
   - Implemented half-life decay modeling ($2^{-\Delta t / 30}$) bounded between $[0.05, 1.0]$ to discount dated disclosures while heavily weighting fresh filings.
3. **Multi-Venue Flow & GEX Regime Fusion**:
   - Institutional sweeps at ask side confirm politician directional positioning with a $1.35\times$ conviction boost.
   - In positive gamma regimes, bullish politician flow converts into high-probability credit spreads (`SELL_PUT_CREDIT`).
   - In negative gamma regimes (breakout/trend acceleration), flow triggers directional debit spreads (`BUY_CALL_SPREAD` / `BUY_PUT_SPREAD`).
4. **Complete Unit Test Coverage**:
   - 12 comprehensive unit tests in `tests/test_congressional_flow_tracker.py` achieving 100% line and branch test coverage.
