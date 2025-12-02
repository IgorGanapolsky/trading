#!/usr/bin/env python3
"""
IMMEDIATE BACKTEST - Prove Strategy Profitability
Tests momentum system (MACD + RSI + Volume) on 60 days of historical data
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.backtesting.backtest_engine import BacktestEngine
from src.strategies.core_strategy import CoreStrategy

print("=" * 80)
print("🔬 RUNNING 60-DAY BACKTEST - MOMENTUM STRATEGY")
print("=" * 80)
print()

# Configure strategy (same as production)
strategy = CoreStrategy(
    daily_allocation=2000.0,  # Match current 2% of $100k portfolio
    use_sentiment=False,  # Pure technical (MACD + RSI + Volume)
    etf_universe=["SPY", "QQQ", "VOO"],
    stop_loss_pct=0.05,
)

print("📊 Strategy Configuration:")
print(f"  - Daily Allocation: ${strategy.daily_allocation}")
print(f"  - ETF Universe: {strategy.etf_universe}")
print(f"  - Stop Loss: {strategy.stop_loss_pct * 100}%")
print("  - Indicators: MACD, RSI, Volume Ratio")
print()

# Define backtest period (Sept 1 - Oct 31, 2025 = 60 days)
start_date = "2025-09-01"
end_date = "2025-10-31"

print(f"📅 Backtest Period: {start_date} to {end_date}")
print("💰 Initial Capital: $100,000")
print()

# Create and run backtest
print("🚀 Running backtest... (this may take 2-3 minutes)")
print()

engine = BacktestEngine(
    strategy=strategy,
    start_date=start_date,
    end_date=end_date,
    initial_capital=100000.0,
)

results = engine.run()

# Display results
print(results.generate_report())

# Save results
results_file = Path("backtest_results_60day.json")
results.save_to_json(str(results_file))
print(f"\n📁 Full results saved to: {results_file}")

# Decision logic
print("\n" + "=" * 80)
print("🎯 GO/NO-GO DECISION FOR SCALING")
print("=" * 80)

criteria_met = []
criteria_failed = []

if results.win_rate >= 55:
    criteria_met.append(f"✅ Win Rate: {results.win_rate:.1f}% (target: >55%)")
else:
    criteria_failed.append(f"❌ Win Rate: {results.win_rate:.1f}% (target: >55%)")

if results.sharpe_ratio >= 1.0:
    criteria_met.append(f"✅ Sharpe Ratio: {results.sharpe_ratio:.2f} (target: >1.0)")
else:
    criteria_failed.append(f"❌ Sharpe Ratio: {results.sharpe_ratio:.2f} (target: >1.0)")

if results.max_drawdown <= 10:
    criteria_met.append(f"✅ Max Drawdown: {results.max_drawdown:.1f}% (target: <10%)")
else:
    criteria_failed.append(f"❌ Max Drawdown: {results.max_drawdown:.1f}% (target: <10%)")

if results.total_return > 0:
    criteria_met.append(f"✅ Total Return: {results.total_return:.2f}% (target: >0%)")
else:
    criteria_failed.append(f"❌ Total Return: {results.total_return:.2f}% (target: >0%)")

print("\n📊 Criteria Met:")
for item in criteria_met:
    print(f"  {item}")

if criteria_failed:
    print("\n⚠️ Criteria Failed:")
    for item in criteria_failed:
        print(f"  {item}")

# Final decision
print("\n" + "=" * 80)
if len(criteria_met) >= 3:
    print("✅ **DECISION: SCALE AGGRESSIVELY**")
    print("Strategy is profitable. Ready for production deployment.")
    print("Recommendation: Increase position sizes, continue live trading.")
else:
    print("❌ **DECISION: BUILD RL AGENTS**")
    print("Strategy needs improvement. Proceed with Month 2 RL system.")
    print("Recommendation: Research + Signal + Risk + Execution agents.")
print("=" * 80)
