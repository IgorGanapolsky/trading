# IV & McMillan Quick Reference

## Quick Decision Matrix

### Should I Sell This Covered Call?

| Check | Metric | Threshold | Action if Failed |
|-------|--------|-----------|------------------|
| 1. IV Rank | `iv_analyzer.get_recommendation()` | **> 30%** | ❌ SKIP - Premium too cheap |
| 2. Delta | Option delta | **0.20 - 0.30** | ❌ SKIP - Too risky or too safe |
| 3. DTE | Days to expiration | **30 - 45 days** | ⚠️ WARNING - Suboptimal timing |
| 4. Expected Move | `calculate_expected_move()` | Strike **OUTSIDE** range | ⚠️ WARNING - High assignment risk |
| 5. McMillan Rules | `_validate_against_mcmillan_rules()` | No violations | ❌ SKIP - Rule violation |

---

## One-Liner Checks

```python
# 1. Check IV Rank
iv_data = iv_analyzer.get_recommendation(symbol)
if iv_data.iv_rank < 30: SKIP

# 2. Check Expected Move
expected = iv_analyzer.calculate_expected_move(symbol, dte=30)
if strike < expected.range_high: WARNING

# 3. Check for 2σ opportunity
if iv_analyzer.is_premium_expensive(symbol): AGGRESSIVE_SELL

# 4. Validate against McMillan
validation = _validate_against_mcmillan_rules(...)
if not validation["passed"]: SKIP
```

---

## IV Rank Interpretation

| IV Rank | Interpretation | Action |
|---------|----------------|--------|
| 0-20 | **Very Low** - Volatility compressed | ❌ Don't sell premium |
| 21-40 | **Low** - Below average | ⚠️ Marginal for selling |
| 41-60 | **Medium** - Average volatility | ✅ Decent for selling |
| 61-80 | **High** - Above average | ✅✅ Great for selling |
| 81-100 | **Very High** - Extreme volatility | ✅✅✅ Excellent for selling |

---

## Expected Move Examples

### Example 1: Safe Strike
- **Stock Price**: $100
- **IV**: 25% (0.25)
- **DTE**: 30 days
- **Expected Move**: ±$7.20
- **Expected Range**: $92.80 - $107.20
- **Your Strike**: $110 ✅ (Outside range - safe)

### Example 2: Risky Strike
- **Stock Price**: $100
- **IV**: 40% (0.40)
- **DTE**: 30 days
- **Expected Move**: ±$11.52
- **Expected Range**: $88.48 - $111.52
- **Your Strike**: $110 ⚠️ (Within range - risky!)

**Formula**: `Expected Move = Price × IV × sqrt(DTE/365)`

---

## McMillan's Golden Rules

1. **Never Sell Premium When IV Rank < 30%**
   - Options are cheap, you get minimal premium
   - Wait for IV to expand

2. **Target 0.20-0.30 Delta**
   - 0.20 delta = ~20% assignment chance
   - 0.30 delta = ~30% assignment chance
   - Sweet spot: Safe enough but good premium

3. **Optimal DTE is 30-45 Days**
   - Too short (<25): Gamma risk (price moves quickly)
   - Too long (>60): Theta too slow (time decay minimal)
   - 30-45: Theta accelerates, manageable gamma

4. **Strikes Outside Expected Move**
   - 1σ move = 68% probability
   - If strike INSIDE 1σ range → High assignment risk
   - If strike OUTSIDE 1σ range → Safer

5. **Never Sell Before Earnings**
   - Earnings = 10-20%+ overnight moves
   - Premium collected rarely justifies risk
   - Wait until AFTER earnings

---

## Auto-Trigger: 2 Std Dev Rule

**When**: IV < (Mean - 2×Std Dev)

**Example**:
- 52-week Mean IV: 30%
- 52-week Std Dev: 5%
- Threshold: 30% - (2 × 5%) = **20%**
- Current IV: **18%** → **AUTO-TRIGGER! 🎯**

**Why**: ~2.5% probability event. IV is statistically cheap and will likely mean-revert higher. Sell aggressively.

**McMillan**: *"When volatility compresses to 2 std devs below average, the options market is mispriced. This is a rare gift - sell premium aggressively."*

---

## Code Snippets

### Get IV Analysis
```python
from src.utils.iv_analyzer import IVAnalyzer

analyzer = IVAnalyzer()
iv_data = analyzer.get_recommendation("AAPL")

print(f"IV Rank: {iv_data.iv_rank}%")
print(f"Recommendation: {iv_data.recommendation}")
print(f"Strategies: {iv_data.suggested_strategies}")
```

### Calculate Expected Move
```python
expected = analyzer.calculate_expected_move(
    symbol="AAPL",
    dte=30,
    iv=0.28  # 28% IV
)

print(f"Range: ${expected.range_low} - ${expected.range_high}")
print(f"Move: ±${expected.move_dollars} ({expected.move_percent*100}%)")
```

### Check McMillan Rules
```python
from src.rag.collectors.mcmillan_options_collector import McMillanKnowledge

kb = McMillanKnowledge()

# Get IV recommendation
iv_rec = kb.get_iv_recommendation(iv_rank=65, iv_percentile=68)
print(iv_rec['recommendation'])  # "STRONGLY SELL PREMIUM"

# Get strategy rules
cc_rules = kb.get_strategy_rules("covered_call")
print(cc_rules['description'])
print(cc_rules['setup_rules'])
```

---

## Trade Checklist

Before executing ANY covered call:

- [ ] ✅ IV Rank > 30%
- [ ] ✅ Delta 0.20-0.30
- [ ] ✅ DTE 30-45 days
- [ ] ✅ Strike outside expected move
- [ ] ✅ No earnings within 14 days
- [ ] ✅ McMillan validation passed
- [ ] ✅ Position size < 5% of portfolio
- [ ] ✅ Willing to sell stock at strike price

**If all checked → EXECUTE**
**If ANY failed → SKIP or ADJUST**

---

## Red Flags (Never Ignore)

🚨 **CRITICAL - BLOCK TRADE**:
- IV Rank < 20%
- Delta > 0.40
- Earnings in < 14 days
- McMillan rule VIOLATION

⚠️ **WARNING - PROCEED WITH CAUTION**:
- IV Rank 20-30%
- Delta < 0.15 or 0.30-0.35
- DTE < 25 or > 60 days
- Strike within expected move
- McMillan rule WARNING

---

## Learning Resources

### Books
1. **"Options as a Strategic Investment"** - Lawrence G. McMillan (Bible of options)
2. **"Option Volatility and Pricing"** - Sheldon Natenberg (Deep dive on IV)
3. **"The Option Trader's Hedge Fund"** - Mark Sebastian (Practical strategies)

### Key Concepts
- **IV Rank**: Where current IV sits in 52-week range (0-100%)
- **IV Percentile**: % of days IV was lower than today
- **Expected Move**: 1σ price move implied by current IV
- **Delta**: Probability of option being ITM at expiration
- **Theta**: Daily time decay (how much option loses per day)

---

## FAQ

**Q: Why IV Rank > 30%?**
A: Below 30%, premium is historically too cheap. You're selling insurance for less than it's worth.

**Q: Can I sell weeklies instead of monthlies?**
A: Only on 2σ auto-trigger events. Otherwise, gamma risk too high.

**Q: What if strike is within expected move?**
A: Not an automatic fail, but WARNING. Higher assignment risk. Consider wider strike.

**Q: What if McMillan says SKIP but I want to trade?**
A: McMillan rules are conservative for a reason. Violating them increases risk significantly. Only override if you have strong conviction AND are willing to accept higher risk.

**Q: How often should IV be 2σ below mean?**
A: Statistically, ~2.5% of the time (rare). When it happens, it's a gift. Sell premium aggressively.

---

**Quick Start**: Run `python3 test_options_iv_integration.py` to verify everything works!
