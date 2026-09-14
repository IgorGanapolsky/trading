---
name: quant-trading-core
description: Lean quantitative options trading engine with verified 10-year statistical edge, Black-Scholes delta targeting, IV Rank filtering, and fixed-fractional risk management.
---

# Quant Trading Core Skill

## 1. Overview & Directive

The **Quant Trading Core** operates a lean, deterministic, mathematically verified options trading strategy focused exclusively on SPY Bull Put Credit Spreads.

All fantasy infrastructure (mock bank remittance, arXiv scrapers, YouTube bots, dead Iron Condors) is eliminated. The engine focuses on **statistical edge, execution speed, and capital growth**.

---

## 2. Proven 10-Year Mathematical Edge (2015–2026 Receipts)

From empirical historical options simulation across 11.6 years and all market regimes (2018 Volmageddon, 2020 COVID, 2022 Bear Market, 2023–2026 Bull Market):

| Metric                 | Selective High-IVR (Recommended) | Conservative Standard        | Unmanaged / No Stop Loss   |
| :--------------------- | :------------------------------- | :--------------------------- | :------------------------- |
| **Win Rate**           | **89.0%**                        | **84.4%**                    | 84.7%                      |
| **Profit Factor**      | **2.25**                         | **1.65**                     | 0.76 (Fails / Loses Money) |
| **Expectancy / Trade** | **+$75.59**                      | **+$52.01**                  | -$33.78                    |
| **Max Drawdown**       | **4.5%**                         | **5.5%**                     | 28.6%                      |
| **10-Year Net PnL**    | **+$19,199.44** (254 trades)     | **+$24,962.74** (480 trades) | -$15,844.98                |

### Key Mathematical Lessons

1. **50% Take-Profit is King**: Taking profit at 50% max credit generates **7.4x more total net PnL** than 25% micro-scalping ($24,962 vs $3,436).
2. **200% Stop Loss is Non-Negotiable**: Without a 200% stop loss, rare tail moves destroy the account (PF drops from 1.65 to 0.76).
3. **Elevated IV Rank (IVR >= 25–30)**: Entering when implied volatility is rich boosts Profit Factor from 1.65 to **2.25** and Win Rate to **89.0%**.
4. **21 DTE Time Exit**: Exiting or rolling at 21 DTE cuts gamma risk and eliminates late-cycle assignment risk.

---

## 3. The 5 Deterministic Execution Rules

### Rule 1: Market Regime Filter

- **Trend**: SPY price must be above the 200-day Simple Moving Average (`SPY > SMA200`).
- **Volatility**: 252-day IV Rank must be **>= 25%** (prevents selling cheap premium during low-vol complacency).

### Rule 2: Strike & Expiration Selection

- **Short Put Strike**: Target **15 Delta (~0.15Δ)**, approximately 85% probability of expiring OTM.
- **Long Put Strike**: Exactly **$5.00 below** the short strike (defined risk).
- **Expiration (DTE)**: **30 to 45 Days to Expiration (DTE)** (optimal theta decay slope).

### Rule 3: Position Sizing & Margin Allocation

- **Risk Per Trade**: Fixed fractional risk of **1.5% to 2.0%** of total portfolio equity.
- **Max Concurrent Spreads**: **4 positions maximum** (ensures cash cushion).

### Rule 4: Exit & Risk Management (Automated)

- **Take Profit**: Place limit order to close at **50% of initial credit received**.
- **Stop Loss**: Trigger market close if spread debit reaches **200% of initial credit** (loss = 2x credit).
- **Time Exit**: Force close at **21 DTE** regardless of P&L to avoid high gamma acceleration.

---

## 4. North Star Capital Roadmap ($6,000/Month Target)

To generate $6,000/month after-tax (~$8,000/month pre-tax) with verified conservative returns (~1.5% to 2.5% monthly return on deployed capital):

| Account Size            | Risk / Trade (2%) | Contracts / Spread | Exp. Monthly Net PnL                           |
| :---------------------- | :---------------- | :----------------- | :--------------------------------------------- |
| **$10,000** (Seed Live) | $200              | 1 contract         | **$150 – $250 / mo**                           |
| **$50,000** (Scaling)   | $1,000            | 2–3 contracts      | **$750 – $1,250 / mo**                         |
| **$150,000** (Growth)   | $3,000            | 6–8 contracts      | **$2,250 – $3,750 / mo**                       |
| **$350,000 – $400,000** | $7,000            | 15–20 contracts    | **$5,500 – $8,500 / mo (Hits $6k North Star)** |

---

## 5. Execution CLI & Runbooks

```bash
# 1. Check live market regime and entry eligibility
.venv/bin/python scripts/quant_core_engine.py --status

# 2. Run full 10-year historical backtest (2015-2026)
.venv/bin/python scripts/historical_options_backtest.py

# 3. Run multi-scenario parameter tournament
.venv/bin/python scripts/historical_options_backtest.py --tournament

# 4. Run automated test suite
.venv/bin/pytest tests/test_quant_core_engine.py
```
