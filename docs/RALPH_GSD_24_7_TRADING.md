# Ralph Loop 24/7 & GSD (Get Shit Done) Autonomous Trading Engine

## Mission & Architecture

The **Ralph + GSD 24/7 Framework** is our continuous autonomous operating loop that unblocks trade execution throughput, expands paper validation capacity from 2 to **5 concurrent slots**, and accelerates progression to the $n=30$ milestone gate with zero manual human intervention.

---

## The 4-Phase Continuous GSD Loop

```mermaid
flowchart TD
    subgraph SENSE["1. SENSE"]
        S1["Market Regime:<br/>VIX, IV Rank, SPY vs 200-DMA"]
        S2["Inventory Capacity:<br/>Occupied Slots (x/5) & Headroom"]
        S3["Mark-to-Market PnL:<br/>Theta Decay & Take-Profit Targets"]
    end

    subgraph DECIDE["2. DECIDE (GSD Priority Matrix)"]
        D1["Priority 1: Lock in Profit<br/>Exit if PnL >= 25% of credit"]
        D2["Priority 2: Protect Capital<br/>Exit if PnL <= -200% stop loss"]
        D3["Priority 3: Harvest Alpha<br/>Enter new weekly structure if headroom > 0"]
        D4["Priority 4: Systematic Hold<br/>Let theta decay on active inventory"]
    end

    subgraph ACT["3. ACT"]
        A1["Execute Paper MLEG Orders"]
        A2["Reconcile Paired Inventory"]
        A3["Update Cohort Scorecard"]
    end

    subgraph VERIFY["4. VERIFY"]
        V1["Emit SHA-256 Audit Receipt in data/audit/ralph_ticks/"]
        V2["Update .claude/ralph/state.json"]
    end

    SENSE --> DECIDE --> ACT --> VERIFY --> SENSE
```

---

## Throughput Acceleration Upgrades

1. **5 Concurrent Position Slots**:
   - Upgraded `PutCreditProfile.max_concurrent_positions` from 2 to **5**.
   - Staggers weekly Friday and mid-week expirations.
   - Increases closed trade turnover from ~1/week to **3–5 closed trades/week**, reducing time to $n=30$ gate from 16 weeks to **2–3 weeks**.

2. **Multi-Asset Universe (SPY + QQQ + IWM + XSP)**:
   - Configured registry to scan 4 ultra-liquid indexes simultaneously.

3. **Autonomous Exit Polling**:
   - Automatically detects positions touching $\ge 25\%$ profit, closing them and instantly freeing slots.

---

## CLI & Makefile Commands

```bash
# Doctor check
uv run scripts/ralph_gsd_trading_runner.py --doctor

# Inspect live Sense & Decide state
uv run scripts/ralph_gsd_trading_runner.py --sense

# Execute a single autonomous GSD tick
uv run scripts/ralph_gsd_trading_runner.py --tick

# Run continuous 24/7 loop (e.g. 10 ticks, 2s interval)
uv run scripts/ralph_gsd_trading_runner.py --loop --max-ticks 10 --sleep-seconds 2.0

# Makefile target
make gsd-tick
```
