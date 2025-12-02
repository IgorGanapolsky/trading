# McMillan Options - Quick Reference Card

## 🎯 Core Formulas

### Expected Move
```
1σ Move = Stock Price × IV × √(DTE/365)
2σ Move = 1σ Move × 2

Probabilities:
- 1σ = 68% probability
- 2σ = 95% probability
```

### Position Sizing
```
Max Risk = Portfolio Value × 2%
Max Contracts = Max Risk / (Premium × 100)
```

### IV Rank
```
IV Rank = (Current IV - 52wk Low) / (52wk High - 52wk Low) × 100
```

---

## 📊 The Greeks - One-Liner Summary

| Greek | What It Measures | Range | Key Insight |
|-------|------------------|-------|-------------|
| **Delta** | $ change per $1 stock move | 0-1 (calls), -1-0 (puts) | Also = probability of ITM |
| **Gamma** | How fast delta changes | Highest ATM near expiry | High gamma = high risk/reward |
| **Theta** | Daily time decay | Negative (long) | Accelerates last 30 days |
| **Vega** | Sensitivity to 1% IV change | Positive (long) | Buy low IV, sell high IV |
| **Rho** | Sensitivity to 1% rate change | Minor except LEAPS | Usually ignore <90 DTE |

---

## 📈 IV Decision Matrix

| IV Rank | Action | Best Strategies |
|---------|--------|-----------------|
| **0-20%** | **BUY PREMIUM** | Long calls, Long puts, Straddles |
| **20-40%** | **NEUTRAL** | Case by case analysis |
| **40-60%** | **FAVOR SELLING** | Iron condor, Covered call |
| **60-100%** | **STRONGLY SELL** | Iron condor, Credit spreads |

**Rule**: Sell when IV Rank > 50%, Buy when IV Rank < 30%

---

## 🎲 Strategy Quick Reference

### Iron Condor (Neutral - Sell Premium)
```
Setup: Sell OTM put + call spreads
Entry: IV Rank > 50%, 30-45 DTE
Strikes: 1σ from current price (16 delta)
Wings: 5-10 strikes wide
Target: 1/3 width as credit
Exit: 50% profit or tested side
```

### Covered Call (Neutral to Bullish - Income)
```
Setup: Own 100 shares, sell 1 call
Entry: IV Rank > 30%, no earnings
Strike: 20 delta (5% OTM)
DTE: 30-45 days
Exit: Roll at 21 DTE if profitable
```

### Cash-Secured Put (Bullish - Want to Own Stock)
```
Setup: Sell put at desired entry price
Entry: IV Rank > 30%, at support
Strike: 20 delta (5% OTM)
DTE: 30-45 days
Exit: 50-80% profit or assignment
Cash: Keep strike × 100 available
```

### Long Call (Bullish - Directional)
```
Setup: Buy ATM/slightly OTM call
Entry: IV Rank < 50%, strong catalyst
Strike: 55 delta (2% OTM)
DTE: 60-90 days minimum
Exit: 100% profit or 50% loss
```

### Protective Put (Bullish + Insurance)
```
Setup: Own 100 shares, buy put
Entry: Before volatility event
Strike: 15 delta (5-10% OTM)
DTE: Match protection period
Exit: When protection not needed
```

---

## ⚠️ Risk Management Rules

### Position Sizing
- ✓ Max 2% risk per trade
- ✓ Max 10% in single position
- ✓ Max 30% in options total
- ✓ Scale in: 50% → 25% → 25%

### Stop Losses
- Long options: **50% of premium** or 25% trailing
- Short options: **2x credit received**
- Stock: **8% below entry**

### Exit Rules
- Credit spreads: **Close at 50% profit** (best risk/reward)
- Debit spreads: **Close at 100% profit** or 50% loss
- Don't hold past **21 DTE** unless deep ITM

### Assignment Risk
- ⚠️ Avoid deep ITM short options (>0.95 delta)
- ⚠️ Close or roll before ex-dividend
- ⚠️ Close positions by 3:00 PM ET on expiration day

---

## 🎓 Delta Interpretation

| Delta | Meaning | Use Case |
|-------|---------|----------|
| **0.90+** | Acts like stock | Deep ITM, little time value |
| **0.70-0.90** | Strong directional | Good for trend following |
| **0.50** | ATM | Balanced risk/reward |
| **0.30-0.50** | Moderate OTM | Good for swing trades |
| **0.20** | Typical sell strike | Income generation |
| **0.10-0.20** | Far OTM | Insurance, protection |
| **<0.10** | Lottery ticket | Usually avoid |

---

## 📅 Optimal DTE (Days to Expiration)

### For Selling Premium
- **Sweet Spot**: 30-45 DTE
- **Why**: Theta acceleration starts, gamma still manageable
- **Roll When**: 21 DTE if profitable

### For Buying Premium
- **Minimum**: 60-90 DTE
- **Why**: Avoid rapid theta decay
- **Don't Buy**: <30 DTE unless quick move expected

---

## 💰 Premium Targeting

### Credit Spreads (Iron Condor, etc.)
```
Target Credit = Spread Width × 33%

Example: $5 wide spread
Target: $1.65-$1.75 credit
Max Risk: $5.00 - $1.70 = $3.30
Return: 51% if held to expiration
```

### Covered Calls
```
Target: 1-2% of stock value per month
Annual: 12-24% if consistent

Example: $100 stock
Monthly Premium: $1.00-$2.00
Strike: $105 (5% OTM, ~20 delta)
```

---

## 🚫 Common Mistakes to Avoid

### 1. Theta Traps
- ❌ Buying options <30 DTE
- ❌ Holding long options to expiration
- ✓ Buy 60-90 DTE, exit at 30 DTE

### 2. IV Mistakes
- ❌ Buying when IV Rank > 70% (expensive)
- ❌ Selling when IV Rank < 30% (low premium)
- ✓ Match strategy to IV environment

### 3. Position Sizing Errors
- ❌ Risking >2% per trade
- ❌ Going "all in" on one trade
- ✓ Size positions mathematically

### 4. Assignment Failures
- ❌ Holding short calls through ex-dividend
- ❌ Letting deep ITM options expire
- ✓ Close/roll before events

### 5. Exit Discipline
- ❌ Letting winners turn to losers
- ❌ Holding past 50% profit (credit spreads)
- ✓ Take profit at target, cut losses at stop

---

## 📱 Quick Decision Tree

### Should I Trade Options on This Stock?

```
1. Check IV Rank
   ├─ > 50% → Favor selling premium
   ├─ < 30% → Favor buying premium
   └─ 30-50% → Neutral, case by case

2. Select Strategy
   ├─ High IV → Iron Condor, Covered Call
   ├─ Low IV → Long Call/Put
   └─ Neutral → Cash-Secured Put

3. Calculate Expected Move
   ├─ Place strikes at 1σ (16 delta)
   └─ Wings 5-10 strikes wide

4. Size Position
   ├─ Max risk = 2% of portfolio
   └─ Calculate max contracts

5. Check Risk Rules
   ├─ DTE in optimal range?
   ├─ No earnings in window?
   ├─ Position size within limits?
   └─ All checks pass → Execute
```

---

## 🔢 Example Calculations

### Example 1: Expected Move
```
Stock: $150
IV: 25% (0.25)
DTE: 30 days

1σ Move = 150 × 0.25 × √(30/365)
        = 150 × 0.25 × 0.287
        = $10.76

Range: $139.24 - $160.76 (68% probability)
```

### Example 2: Position Sizing
```
Portfolio: $10,000
Max Risk: 2% = $200
Option Premium: $3.50 ($350/contract)

Max Contracts = $200 / $350 = 0.57
→ Can't trade (need smaller premium or bigger portfolio)

Need premium ≤ $2.00 to trade 1 contract
```

### Example 3: Iron Condor Credit
```
Spread Width: $5
Target Credit: $5 × 0.33 = $1.65

If credit = $1.50:
- Max Profit: $150/contract
- Max Risk: $500 - $150 = $350/contract
- Return: 43% if expires worthless
```

---

## 💡 McMillan's Top 10 Rules

1. **Match strategy to IV environment** - Don't fight volatility
2. **30-45 DTE is optimal for selling** - Balance theta vs gamma
3. **60-90 DTE minimum for buying** - Avoid rapid decay
4. **Close at 50% profit (credit spreads)** - Best risk/reward
5. **Never risk >2% per trade** - Survival first
6. **Roll at 21 DTE if profitable** - Avoid gamma risk
7. **Avoid earnings (unless intentional)** - IV crush hurts
8. **Use delta to estimate probability** - 20 delta = ~20% ITM
9. **Place strikes at 1σ (16 delta)** - Proper risk/reward
10. **Have an exit plan before entry** - Know when to fold

---

## 📚 Python Quick Start

```python
from src.rag.collectors.mcmillan_options_collector import McMillanOptionsKnowledgeBase

kb = McMillanOptionsKnowledgeBase()

# Get IV recommendation
rec = kb.get_iv_recommendation(iv_rank=65, iv_percentile=70)
print(rec['recommendation'])  # "STRONGLY SELL PREMIUM"

# Calculate expected move
move = kb.calculate_expected_move(
    stock_price=150,
    implied_volatility=0.25,
    days_to_expiration=30
)
print(f"Range: ${move['lower_bound']} - ${move['upper_bound']}")

# Get strategy rules
rules = kb.get_strategy_rules("iron_condor")
print(rules['setup_rules'])

# Size position
size = kb.get_position_size(
    portfolio_value=10000,
    option_premium=2.50
)
print(f"Max contracts: {size['max_contracts']}")
```

---

## 🎯 One-Page Cheat Sheet

```
┌─────────────────────────────────────────────────────────────┐
│ MCMILLAN OPTIONS QUICK REFERENCE                            │
├─────────────────────────────────────────────────────────────┤
│ IV RANK    | ACTION                                         │
│ 60-100%    | STRONGLY SELL (Iron Condor, Credit Spreads)   │
│ 40-60%     | FAVOR SELLING (Covered Call, CSP)             │
│ 20-40%     | NEUTRAL (Case by case)                        │
│ 0-20%      | BUY PREMIUM (Long Call/Put)                   │
├─────────────────────────────────────────────────────────────┤
│ DTE        | STRATEGY                                       │
│ 30-45      | SELL PREMIUM (optimal theta/gamma balance)    │
│ 60-90      | BUY PREMIUM (minimum to avoid rapid decay)    │
│ <21        | ROLL OR CLOSE (gamma risk too high)           │
├─────────────────────────────────────────────────────────────┤
│ POSITION SIZING                                             │
│ Max Risk:     2% of portfolio per trade                     │
│ Max Position: 10% in single stock                           │
│ Max Options:  30% of portfolio                              │
├─────────────────────────────────────────────────────────────┤
│ EXIT RULES                                                  │
│ Credit Spreads:  50% profit (optimal risk/reward)           │
│ Debit Spreads:   100% profit or 50% loss                    │
│ Long Options:    50% loss or 25% trailing stop              │
│ Short Options:   2x credit received                         │
├─────────────────────────────────────────────────────────────┤
│ FORMULAS                                                    │
│ Expected Move = Price × IV × √(DTE/365)                     │
│ Max Contracts = (Portfolio × 0.02) / (Premium × 100)        │
│ IV Rank = (Current - Low) / (High - Low) × 100              │
├─────────────────────────────────────────────────────────────┤
│ STRIKE SELECTION                                            │
│ Income:      20 delta (~5% OTM)                             │
│ Iron Condor: 16 delta (~1 std dev)                          │
│ Long Call:   55 delta (~2% OTM)                             │
│ Protection:  15 delta (~5-10% OTM)                          │
└─────────────────────────────────────────────────────────────┘
```

---

**Keep this reference handy for quick decisions!**

**Last Updated**: December 2, 2025
