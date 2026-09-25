---
name: options-vol-gex
description: Quantitative options volatility, dealer gamma exposure (GEX), term structure backwardation, and market tide flow analysis engine.
---

# Options Volatility, GEX, & Market Tide Analysis

## 1. Overview & Zero-Cost Architecture

This skill reproduces institutional-grade options volatility, dealer positioning, and flow analytics in-house at **$0 cost**, completely replacing expensive external subscriptions ($750/mo for Unusual Whales API, $3,000/mo for Kafka feeds).

Using free Alpaca options chains and local Black-Scholes math, this engine computes:
1. **Dealer Gamma Exposure (GEX)**: Strike-by-strike dealer hedging positioning, Call/Put Walls, Gamma Magnet, and Zero-Gamma Flip levels.
2. **Volatility Regimes**: Differentiates between Positive Gamma (mean-reverting, volatility-dampening) and Negative Gamma (cascading momentum, volatility-amplifying).
3. **Expiration Max Pain**: Strike where total option buyer value expires worthless, creating dealer gravitational price pins.
4. **Term Structure Backwardation**: Linear IV slope gating ($\text{slope} \le -0.00406$ per day) and Variance Risk Premium richness ($IV30 / RV30 \ge 1.25$).
5. **Market Tide Flow Aggressiveness**: Net Call vs. Net Put dollar premium delta and $>70\%$ ask-side order flow urgency.

```
                                 OPTIONS VOLATILITY & GEX PIPELINE
                                 
  [Free Alpaca Option Chain] ───► [Black-Scholes Gamma Engine] ───► [GEX Levels & Regimes]
  (Strikes, OI, Bid/Ask, IV)       d1 = [ln(S/K) + (r+s^2/2)T] / s√T  • Call Wall / Put Wall
                                   Γ = exp(-qT) * φ(d1) / (S*s*√T)    • Gamma Magnet & Flip ($GEX=0$)
                                                                      • Positive vs Negative Vol Regime

  [Open Interest Matrix]     ───► [Cash-Loss Payoff Model]     ───► [Max Pain Strike Pin]
  (Sum of Call + Put Loss)         min_K Σ (Buyer Payout)              Dealer Pin for Expiration

  [Term Structure IV Curve]  ───► [VRP / Backwardation Slope]  ───► [Credit Spread Entry Filter]
  (Front IV vs 45 DTE IV)          Slope = (IV_back - IV_front)/ΔDTE   Gate: Slope <= -0.00406 / day
                                   IV30 / RV30 >= 1.25 Richness        Capture front IV crush safely

  [Intraday Tape / Quotes]   ───► [Market Tide & Flow Ratio]   ───► [Aggressive Flow Detector]
  (Ask vs Bid executions)          Net Prem = Σ(Ask Prem) - Σ(Bid)     Gate: Ask Volume Ratio >= 70%
```

---

## 2. Core Quantitative Formulations

### A. Dealer Gamma Exposure (GEX)
Market makers typically assume the opposite side of retail order flow:
*   Retail buys calls $\implies$ Market Makers sell calls $\implies$ Dealers are short calls.
*   Retail buys puts $\implies$ Market Makers sell puts $\implies$ Dealers are short puts.

Dollar Gamma per 1-point move in underlying $S$:
$$\text{Spot GEX}_{\text{call}, K} = \Gamma_{\text{call}, K} \times \text{OI}_{\text{call}, K} \times S^2 \times 100$$
$$\text{Spot GEX}_{\text{put}, K} = -\Gamma_{\text{put}, K} \times \text{OI}_{\text{put}, K} \times S^2 \times 100$$
$$\text{Net GEX}_K = \text{Spot GEX}_{\text{call}, K} + \text{Spot GEX}_{\text{put}, K}$$

#### Key Levels
*   **Call Wall**: $\arg\max_{K > S} (\text{Net GEX}_K)$ — Strike above spot with largest positive net gamma (overhead dealer resistance).
*   **Put Wall**: $\arg\max_{K < S} (\text{Net GEX}_K)$ — Strike below spot with largest positive net gamma (downside dealer support).
*   **Gamma Magnet**: $\arg\max_{K} (|\text{Net GEX}_K|)$ — Strike with largest magnitude net gamma (strongest pin).
*   **Gamma Flip**: Linear zero-crossing price where net gamma flips from positive to negative:
    $$\text{Flip} = K_1 + \frac{0 - \text{GEX}_1}{\text{GEX}_2 - \text{GEX}_1} \cdot (K_2 - K_1)$$

#### Regime Decision Rail
*   $\sum \text{Net GEX} \ge 0$ (**Positive Gamma**): Dealers buy dips and sell rallies $\implies$ volatility is dampened and mean-reverting. **Optimal regime to sell SPY put credit spreads.**
*   $\sum \text{Net GEX} < 0$ (**Negative Gamma**): Dealers sell dips and buy rallies $\implies$ volatility expands, cascading selloffs occur. **Put credit spread hazard gate.**

---

### B. Expiration Max Pain
At options expiration, underlying prices tend to gravitate toward the strike where option holders suffer maximum cumulative dollar loss:
$$\text{Buyer Payout}(K_{\text{eval}}) = \sum_{j} \text{OI}_{\text{call}, j} \cdot \max(0, K_{\text{eval}} - K_j) \cdot 100 + \sum_{j} \text{OI}_{\text{put}, j} \cdot \max(0, K_j - K_{\text{eval}}) \cdot 100$$
$$\text{Max Pain Strike} = \arg\min_{K_{\text{eval}}} \text{Buyer Payout}(K_{\text{eval}})$$

---

### C. Term Structure Backwardation & VRP Richness
When near-term implied volatility is abnormally elevated relative to deferred expirations, the options term structure is in **backwardation**:
$$\text{Slope} = \frac{IV_{\text{back}} - IV_{\text{front}}}{\text{DTE}_{\text{back}} - \text{DTE}_{\text{front}}}$$
*   **Backwardation Gate**: $\text{Slope} \le -0.00406 \text{ per day}$ (front-month IV sharply inverted).
*   **Richness Ratio**: $\frac{IV_{30}}{RV_{30}} \ge 1.25$ (front IV trades at $\ge 25\%$ premium over 30-day realized volatility).
*   **Trade Action**: When both criteria are met, selling front-month credit spreads captures rich volatility premium with statistical tailwind.

---

### D. Market Tide & Flow Aggressiveness
*   **Net Call Premium**: $\sum \text{Call Premium}_{\text{ask}} - \sum \text{Call Premium}_{\text{bid}}$
*   **Net Put Premium**: $\sum \text{Put Premium}_{\text{ask}} - \sum \text{Put Premium}_{\text{bid}}$
*   **Market Tide Delta**: $\text{Net Call Premium} - \text{Net Put Premium}$
*   **Ask-Side Aggressiveness**:
    $$\text{Ask Ratio} = \frac{\text{Volume}_{\text{ask}}}{\text{Volume}_{\text{ask}} + \text{Volume}_{\text{bid}}} \ge 0.70$$
    Identifies institutional buyer urgency over 5-minute rolling windows.

---

## 3. Usage & Execution Recipe

```python
from src.analytics.options_vol_gex import (
    black_scholes_gamma,
    calculate_gex_levels,
    calculate_max_pain,
    calculate_iv_term_structure,
    calculate_market_tide,
)

# 1. Compute GEX Levels and Regime from Option Chain
gex = calculate_gex_levels(
    spot_price=505.20,
    strikes=[490.0, 495.0, 500.0, 505.0, 510.0, 515.0],
    call_gammas=[0.01, 0.02, 0.03, 0.04, 0.03, 0.01],
    put_gammas=[0.01, 0.02, 0.03, 0.04, 0.03, 0.01],
    call_ois=[500, 1200, 3000, 5000, 2500, 1000],
    put_ois=[2000, 3500, 1500, 800, 400, 200],
)

print(f"Regime: {gex.gamma_regime}")  # 'positive_gamma' or 'negative_gamma'
print(f"Call Wall (Resistance): {gex.call_wall}")
print(f"Put Wall (Support): {gex.put_wall}")
print(f"Gamma Magnet (Pin): {gex.gamma_magnet}")
print(f"Gamma Flip (Zero Crossing): {gex.gamma_flip}")

# 2. Check Expiration Max Pain Pin
max_pain = calculate_max_pain(
    strikes=[490.0, 495.0, 500.0, 505.0, 510.0, 515.0],
    call_ois=[500, 1200, 3000, 5000, 2500, 1000],
    put_ois=[2000, 3500, 1500, 800, 400, 200],
)
print(f"Max Pain Strike: {max_pain}")

# 3. Gating Filter for Credit Spread Entry
term_struct = calculate_iv_term_structure(
    front_dte=7.0,
    front_iv=0.28,
    back_dte=45.0,
    back_iv=0.18,
    rv30=0.19,
)
if term_struct.credit_spread_favorable and gex.gamma_regime == "positive_gamma":
    print("[+] Optimal Put Credit Spread Regime: Backwardated + Rich + Positive Gamma")

# 4. Unusual Whales Periscope: Dealer Hedging Flow & Defended Levels
from src.analytics.options_vol_gex import (
    calculate_expected_hedging_flow,
    evaluate_dealer_defense_levels,
    detect_zero_dte_risk_pockets,
)

flow = calculate_expected_hedging_flow(spot_price=505.20, net_gamma=gex.net_gamma, spot_move_pct=-0.01)
print(f"Hedging Pressure: {flow.hedging_pressure} ({flow.description})")

defense = evaluate_dealer_defense_levels(
    spot_price=505.20, put_wall=gex.put_wall, call_wall=gex.call_wall, gamma_flip=gex.gamma_flip
)
print(f"Safety: {defense.regime_safety} - {defense.summary}")

pockets = detect_zero_dte_risk_pockets(
    spot_price=505.20,
    strikes=[500.0, 505.0, 510.0],
    zero_dte_put_ois=[500, 3000, 200],
    zero_dte_call_ois=[200, 4000, 100],
    total_put_ois=[1500, 5000, 1000],
    total_call_ois=[1000, 8000, 2000],
)
for p in pockets:
    print(f"0DTE Risk Pocket: Strike {p.strike} -> {p.risk_level}: {p.hazard_description}")
```

