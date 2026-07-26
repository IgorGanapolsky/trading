# Autonomous Mercury Real-Money Trading & Income System Architecture

## 1. Executive Summary & Tax Strategy Analysis

The objective is to establish an autonomous, state-persistent real-money trading system that regularly interacts with Mercury AI bank, dollar-cost-averages (DCA) into income-producing assets, reserves estimated tax liabilities, and deposits **$1,000/month in net after-tax profit** back into the Mercury AI bank account.

### Day Trading vs. Buy-and-Hold Qualified Dividend Growth

| Feature / Tax Trait | Day Trading / High-Frequency | Buy-and-Hold Qualified Dividend Growth (Selected) |
| :--- | :--- | :--- |
| **Federal Tax Rate** | Ordinary income tax rates (up to 37%) | Preferential qualified dividend rates (0%, 15%, or 20%) |
| **Wash Sale Risk (IRC § 1091)** | High risk (disallows loss deductions if re-entered within 30 days) | Zero risk (continuous DCA buy-and-hold with no frequent sells) |
| **Short-Term Penalties** | Subject to maximum short-term capital gain rates & self-employment friction | Eligible for qualified dividend rate treatment after holding >60 days |
| **Capital Requirements** | $25,000+ Pattern Day Trader (PDT) margin requirement | Flexible fractional share DCA (starts at $1/order) |
| **Recommended Strategy** | ❌ Rejected due to tax inefficiency & high friction | ✅ Selected (`DividendGrowthStrategy` on SCHD, VIG, DGRO) |

---

## 2. Tax Reservation Accounting & $1,000/Month Net Target

To guarantee that **$1,000/month after-tax profit** is deposited back to Mercury bank without underfunding tax obligations:

1. **Tax Reserve Rate ($\tau$)**: Default set to **20.0%** (15% federal qualified dividend rate + 5% state tax buffer).
2. **Gross Income Target**:
   $$\text{Gross Required} = \frac{\text{Net Target}}{1 - \tau} = \frac{\$1,000.00}{1 - 0.20} = \$1,250.00 \text{ / month}$$
3. **Split Accounting**:
   - **Tax Reserve**: $\$1,250.00 \times 20\% = \$250.00$ retained in `tax_reserve_usd` ledger.
   - **Net Payout**: $\$1,250.00 \times 80\% = \$1,000.00$ pushed directly to Mercury AI bank account upon reaching threshold.

---

## 3. System Architecture & Components

```mermaid
flowchart TD
    MB[Mercury AI Bank Account] -->|Surplus > $500 Buffer| BA[BankAdapter / MercuryBankAdapter]
    BA -->|ACH Push Transfer| EA[EquityBrokerAdapter / Alpaca]
    EA -->|DCA Buy Orders| DGS[DividendGrowthStrategy: SCHD/VIG/DGRO]
    DGS -->|Hold & Accumulate| PORT[Broker Portfolio]
    PORT -->|Accrue Qualified Dividends| DIV[Dividend Collector]
    DIV -->|Gross Income| TAX[Tax Reserve Calculator (20% Reserve)]
    TAX -->|80% Net After-Tax Profit| THRESH{After-Tax Profit >= $1,000?}
    THRESH -->|Yes| DEP[Deposit $1,000+ Net to Mercury Bank]
    THRESH -->|No| ACC[Accumulate Net Profit in State]
```

### Components Implemented
1. **`src/adapters/bank_adapter.py`**:
   - `PaperBankAdapter`: In-memory simulated bank adapter.
   - `MercuryBankAdapter`: Live REST client for Mercury API (`https://backend.mercury.com/api/v1`). Hard-gated by `MERCURY_LIVE_TRANSFERS_ENABLED=1` and `MERCURY_API_TOKEN`.
2. **`src/adapters/equity_broker_adapter.py`**:
   - `PaperEquityBrokerAdapter`: Persists position holdings and calculates daily dividend accrual.
   - `AlpacaEquityBrokerAdapter`: Dedicated equity account broker interface.
3. **`src/strategies/dividend_growth_strategy.py`**:
   - Allocates DCA capital into SCHD, VIG, DGRO.
4. **`scripts/mercury_income_loop.py`**:
   - Orchestrates withdrawal -> DCA buy -> dividend collection -> tax reserve split -> net after-tax deposit loop.
   - Persists state to `data/mercury_income_loop_state.json`.

---

## 4. Operational Execution Commands

### Paper Simulation Run (Default)
```bash
python3 scripts/mercury_income_loop.py --mode paper --paper-starting-balance 1500.0 --profit-return-threshold-usd 1000.0
```

### Live Account Execution
Set credentials in environment:
```bash
export MERCURY_API_TOKEN="<mercury-token>"
export MERCURY_ACCOUNT_ID="<mercury-account-id>"
export MERCURY_LIVE_TRANSFERS_ENABLED="1"
export DIVIDEND_GROWTH_ALPACA_API_KEY="<alpaca-key>"
export DIVIDEND_GROWTH_ALPACA_API_SECRET="<alpaca-secret>"
export DIVIDEND_GROWTH_ALPACA_ENABLED="1"

python3 scripts/mercury_income_loop.py --mode live --profit-return-threshold-usd 1000.0
```
