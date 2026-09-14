# Dagster-Style Software-Defined Assets (SDA) & Asset Checks

## Source & Architecture Reference

- **Documentation**: [Dagster Docs](https://docs.dagster.io/)
- **Core Paradigm**: The shift from **task-based imperative workflow scripts** to **declarative, asset-centric state management**.

---

## Core Stolen Mechanics

### 1. Software-Defined Assets (SDAs)

Instead of defining procedural jobs ("run step 1, then step 2"), you declare **what data assets exist** and their **upstream dependencies**:

$$\text{Asset}_i = f(\text{Upstream Asset}_1, \dots, \text{Upstream Asset}_k)$$

In trading & financial operations:

- `AssetKey("market", "regime")`: Snapshot of VIX, IV Rank proxy, SPY vs 200-DMA.
- `AssetKey("inventory", "open_positions")`: Active paired options positions.
- `AssetKey("options", "put_credit_candidates")`: Screened SPY put credit spread candidate structures (depends on `market/regime` and `inventory/open_positions`).
- `AssetKey("scorecard", "cohort_progress")`: Cohort performance scorecard, expectancy, and milestone progression.

### 2. First-Class Asset Checks

Data quality and safety invariants are defined directly alongside the asset:

- `check_vix_ivr_regime_bounds`: Asserts $\text{VIX} \le 30$ and $\text{IVR} \ge 30$.
- `check_inventory_capacity`: Asserts concurrent positions do not exceed maximum capacity (2).
- `check_paper_only_invariant`: Enforces `paper_only` and blocks live order execution.

### 3. Blocking Check Diodes (Fail-Closed Execution)

If an asset check marked `blocking=True` fails:

- The asset's materialization status is marked `success=False`.
- **All downstream assets in the dependency graph are immediately blocked** (`blocked_by="upstream_asset"`), preventing bad data or unverified state from propagating downstream.

### 4. Immutable Materialization Receipts

Every asset materialization event captures:

- `asset_key`: Identifier
- `materialized_at`: UTC timestamp
- `duration_ms`: Computation latency (sub-millisecond)
- `metadata`: Structured payload
- `check_results`: Evaluation of all attached checks
- `content_hash`: SHA-256 fingerprint

---

## CLI & Makefile Usage

```bash
# Run Dagster SDA Engine Doctor
uv run scripts/dagster_asset_engine.py --doctor

# List all declared Software-Defined Assets & Checks
uv run scripts/dagster_asset_engine.py --list-assets

# Materialize a target asset (automatically resolves upstream dependencies)
uv run scripts/dagster_asset_engine.py --materialize options/put_credit_candidates

# Materialize the entire asset graph
uv run scripts/dagster_asset_engine.py --materialize-all

# Makefile Target
make dagster-roi
```
