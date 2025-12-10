# Fibonacci Auto-Scaling (Retired)

The original project documentation described an experimental Fibonacci-based compounding plan
($1/day → $100/day) for daily deposits. That experiment has been sunset in favor of the Smart DCA
allocator that lives inside `src/orchestrator/smart_dca.py` and enforces tier-based buckets
tied to `AppConfig.get_tier_allocations()`.

If you need to understand how the modern allocator works:

- Review `src/orchestrator/smart_dca.py` for the bucket math and session lifecycle
- See `src/orchestrator/main.py` for how Gate 4 caps notional per bucket via `allocation_cap`
- Run `scripts/financial_automation.py` to get a snapshot of the current bucket targets

Legacy Fibonacci docs (README_FIBONACCI, EXEC_SUMMARY, etc.) have been removed to avoid confusion.
Use Git history if you need to reference that strategy for archival purposes.
