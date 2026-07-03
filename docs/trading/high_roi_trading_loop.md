# High-ROI Exit-Only Trading Loop

This operator protects the paper account while the strategy is halted or in
North Star quarantine. It never opens new positions. It only monitors existing
iron condors and, when explicitly run with `--execute`, can submit eligible exit
orders through the existing MLeg close path.

## Default Dry Run

```bash
PYTHONPATH=. python3 scripts/high_roi_trading_loop.py --dry-run --max-iterations 1
```

The default output files are:

- `data/runtime/high_roi_trading_loop.jsonl`
- `data/runtime/high_roi_trading_loop_latest.json`

Use `/tmp` paths when you want read-only evidence without modifying repo data:

```bash
PYTHONPATH=. python3 scripts/high_roi_trading_loop.py \
  --dry-run \
  --max-iterations 1 \
  --journal-path /tmp/high_roi_trading_loop.jsonl \
  --latest-path /tmp/high_roi_trading_loop_latest.json
```

## Execute Eligible Exits Only

```bash
PYTHONPATH=. python3 scripts/high_roi_trading_loop.py --execute --max-iterations 1
```

`--execute` still does not open new positions. It can only close existing iron
condors that trip the configured exit rules:

- 50% profit target
- 100% credit stop-loss
- 7 DTE exit

If an iron condor is missing `entry_date`, the loop still allows hard risk exits
for stop-loss and 7 DTE. Profit-taking continues to respect the base manager's
minimum-hold safety behavior.

## Scheduled Mode

```bash
PYTHONPATH=. python3 scripts/high_roi_trading_loop.py \
  --dry-run \
  --loop \
  --interval-seconds 900
```

Use `--execute --loop` only for an intentional exit-management session with
operator supervision.
