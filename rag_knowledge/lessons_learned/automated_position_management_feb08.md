# Automated Position Management Requirements (Feb 8, 2026)

## Source: Tastylive best practices, Option Alpha, system gap analysis

### The Gap
Position monitoring code EXISTS (options_risk_monitor.py) but is NOT running on a schedule.
This means 50% profit exits and 200% stop-losses are not being enforced automatically.
This is likely the #1 reason for low win rate.

### Tastylive Best Practices (Confirmed Feb 2026)
1. Open at 45 DTE with 20-delta short strikes
2. Close at 50% of max profit — DO NOT hold to expiration
3. Close at 21 DTE regardless of P/L (we use 7 DTE per LL-268)
4. If challenged: roll untested side closer for additional credit
5. Typical hold time: 2-4 weeks (not full 45 days)

### What Needs to Be Built
1. **Scheduled position monitor** — GitHub Actions workflow OR cron job that runs every market hour
2. **Auto-close at 50% profit** — call options_risk_monitor.run_risk_check() on schedule
3. **Auto-close at 200% stop** — same mechanism
4. **7 DTE forced exit** — close everything within 7 DTE of expiration
5. **Alert system** — notify when positions are closed (Slack, email, or webhook)

### Expected Impact
- Tastylive data shows 50% profit exit boosts win rate from ~70% to 85%+
- Reduces max holding time from 45 days to ~14-21 days average
- Frees up capital for more frequent entries
- At 2-3 cycles per month instead of 1: doubles or triples monthly income

### Implementation Priority
HIGHEST — this is the single biggest lever for reaching North Star
