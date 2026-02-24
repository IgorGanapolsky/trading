import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path

# Statistical profiles for different regimes
# Regime: (VIX_Range, Win_Rate, Avg_Credit, Avg_Loss)
REGIMES = [
    ("CALM", (12, 16), 0.90, 1.00, -200),
    ("NORMAL", (17, 24), 0.85, 1.50, -300),
    ("VOLATILE", (25, 35), 0.70, 2.50, -500),
    ("STRESS", (36, 50), 0.50, 4.00, -800),
]

DATA_DIR = Path("data")
SYSTEM_STATE_PATH = DATA_DIR / "system_state.json"


def generate_regime_aware_trades(count=100):
    """
    Generates realistic regime-aware trade history for ML training.
    """
    synthetic_history = []
    base_date = datetime.now() - timedelta(days=count)

    for i in range(count):
        # Pick a random regime
        regime_name, vix_range, win_rate, avg_credit, avg_loss = random.choice(REGIMES)
        vix = random.uniform(vix_range[0], vix_range[1])

        trade_date = base_date + timedelta(days=i)
        is_win = random.random() < win_rate

        expiry_str = (trade_date + timedelta(days=30)).strftime("%y%m%d")

        if is_win:
            pnl = avg_credit * 100 * random.uniform(0.8, 1.2)
            side = "SELL"
            price = avg_credit
        else:
            pnl = avg_loss * random.uniform(0.8, 1.2)
            side = "BUY"
            price = abs(avg_loss / 100)

        # In a real system, features would be in a separate DB or joined.
        # Here we embed them in the metadata or indicators for the learner.
        trade_entry = {
            "id": f"syn-{regime_name.lower()}-{i}",
            "symbol": f"SPY{expiry_str}P00650000",
            "side": side,
            "qty": 1,
            "price": price,
            "filled_at": trade_date.isoformat(),
            "pnl": pnl,
            "indicators": {"vix": vix, "regime": regime_name},
        }
        synthetic_history.append(trade_entry)

    return synthetic_history


def inject():
    """Main injection routine."""
    logging.basicConfig(level=logging.INFO)
    print("🧪 Injecting 100 Regime-Aware Synthetic Trades...")

    if not SYSTEM_STATE_PATH.exists():
        print("❌ Error: data/system_state.json not found.")
        return

    with open(SYSTEM_STATE_PATH) as f:
        state = json.load(f)

    # Clean existing synthetic trades to avoid duplicates or pollution
    state["trade_history"] = [
        t for t in state.get("trade_history", []) if not str(t.get("id", "")).startswith("syn-")
    ]

    synthetic_trades = generate_regime_aware_trades(100)
    state["trade_history"].extend(synthetic_trades)

    with open(SYSTEM_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    print("✅ Injection Complete.")
    print(f"   Trade History Count: {len(state['trade_history'])}")
    print("\nNext step: Run 'python3 scripts/run_grpo_training.py' to train on REGIME-AWARE data.")


if __name__ == "__main__":
    inject()
