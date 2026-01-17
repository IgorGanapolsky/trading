# Trading System Data Architecture

> **Last Updated**: Jan 17, 2026  
> **Owner**: Claude (CTO)

## Single Source of Truth

```
┌─────────────────────────────────────────────────────────────────┐
│                        ALPACA API                                │
│                   (Authoritative Source)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              sync-system-state.yml (GitHub Actions)              │
│                                                                  │
│  Schedule: Every hour during market (14:00-21:00 UTC Mon-Fri)   │
│  Fetches: Account, Positions, Orders (last 100 filled)          │
│  Writes to: data/system_state.json                              │
│  Commits via: Auto-merge PR                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    data/system_state.json                        │
│                                                                  │
│  {                                                               │
│    "last_updated": "2026-01-17T00:00:00Z",                      │
│    "portfolio": { "equity": "4986.71", "cash": "4761.71" },     │
│    "paper_account": { "positions": [...] },                     │
│    "trade_history": [                    ◀── ALL TRADES HERE    │
│      { "symbol": "SPY", "side": "BUY", "price": "692.08", ... } │
│    ],                                                            │
│    "trades_loaded": 38                                           │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   Webhook     │    │  Dashboards   │    │ Local Scripts │
│  (Cloud Run)  │    │ (GH Pages)    │    │  (Dev/Debug)  │
│               │    │               │    │               │
│ Reads via:    │    │ Reads via:    │    │ Reads via:    │
│ GitHub API    │    │ fetch()       │    │ file read     │
└───────────────┘    └───────────────┘    └───────────────┘
```

## Data Flow Rules

### ✅ DO
- Read trade data from `system_state.json` → `trade_history[]`
- Query Alpaca API directly for real-time data (webhook does this)
- Trust `sync-system-state.yml` as the sync mechanism

### ❌ DON'T
- Write trade data to `trades_*.json` files (deprecated)
- Create alternative trade storage locations
- Bypass the single source of truth

## Staleness Protection

The system includes staleness guards:

1. **Webhook**: Checks `last_updated` timestamp, warns if >4 hours old
2. **Integration Test**: CI verifies `trades_loaded > 0` on every deploy
3. **Workflow**: Runs hourly during market hours

## File Locations

| File | Purpose | Writer | Readers |
|------|---------|--------|---------|
| `data/system_state.json` | Portfolio + Trades | sync-system-state.yml | Webhook, Dashboards, Scripts |
| `data/trades_*.json` | **DEPRECATED** | ~~trade_sync.py~~ | None (remove) |

## Why This Architecture?

1. **Alpaca is truth**: Our broker has the real data. Period.
2. **Single sync point**: One workflow, one file, no confusion.
3. **Cloud Run compatible**: GitHub API works everywhere, local files don't.
4. **Debuggable**: Check `system_state.json` in GitHub to see exactly what data exists.

## Monitoring

- **Webhook Health**: `GET /health` returns `trades_loaded` count
- **CI Integration Test**: Fails if `trades_loaded == 0`
- **Staleness Alert**: Webhook logs warning if data >4 hours old

---

*Architecture defined after LL-230 incident (Jan 17, 2026)*
