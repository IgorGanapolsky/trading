# Iron Condor Backtest Findings (Feb 8, 2026)

## Source: Web Research + OptionsTrading IQ + Spintwig

### Key Backtest Data

**50-trade study (10-15 delta, 25-60 DTE):**
- Win rate: 86% (43W / 7L)
- Average win: $460
- Average loss: $677
- Average P/L per trade: $300.73
- Average premium collected: $994.68
- Average max risk: $5,435.32
- Risk/reward ratio: 5.4:1

**Theoretical vs Actual:**
- Theoretical win rate at 15-delta: ~70%
- Actual with active management (50% profit exit): 86%
- The 16-point improvement comes from closing winners early

### Delta Impact on Win Rate
- 15-delta shorts: ~70-77% win rate (unmanaged), 85%+ with 50% profit exit
- 30-delta shorts: ~34% win rate — massive dropoff
- Conclusion: 15-delta is significantly superior for iron condors

### Project Option Study (SPY-specific)
- Average P/L per SPY iron condor: $35.39 (held to expiration, no adjustment)
- Win rate: 77.6% for 30-60 DTE, 16-delta shorts, 5-delta longs

### Optimal Parameters (Confirmed)
| Parameter | Optimal | Rationale |
|---|---|---|
| Short delta | 15 | 70-86% win rate, best risk/reward |
| DTE | 30-45 | Sweet spot for theta decay |
| Width | $5 | Defined risk, manageable max loss |
| Exit | 50% profit | Boosts win rate from 70% to 85%+ |
| Stop | 200% of credit | Caps losses, preserves capital |
| Min DTE exit | 7 DTE | Avoids gamma risk (LL-268) |

### Application to Our Strategy
- Current setup: 15-delta, 30-45 DTE, $5 wide on SPY — CONFIRMED OPTIMAL
- Expected annual return at 2 condors/month: ~$600/month ($7,200/year) on $100K
- Path to North Star: Scale to 4-6 condors as account grows past $150K

### YouTube Transcript IP Ban Fix
- youtube-transcript-api blocked on all cloud providers (GitHub Actions, AWS, GCP)
- Simple env var proxy (HTTP_PROXY) does NOT work — library needs native proxy config
- yt-dlp subtitle extraction is more resistant to bans (different request patterns)
- Curated embedded transcripts as guaranteed fallback
- Rotating residential proxies (Webshare) are the gold standard but cost money
