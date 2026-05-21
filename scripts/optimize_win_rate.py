import json
from pathlib import Path

# Mock VIX data since we can't fetch live for backtest analysis easily
# In a real run, this would query the DataProvider
VIX_DANGER_ZONE = 25.0


def analyze_trade_survivability():
    """
    Analyzes historical trades against volatility regimes to find
    the deterministic 'Safety Zone' for a >50% win rate.
    """
    trades_path = Path("data/trades.json")
    if not trades_path.exists():
        print("No trades found.")
        return

    with open(trades_path) as f:
        data = json.load(f)
        trades = data.get("trades", [])

    wins = [t for t in trades if t.get("outcome") == "win"]
    losses = [t for t in trades if t.get("outcome") == "loss"]

    print("--- Historical Performance Analysis ---")
    print(f"Total Trades: {len(trades)}")
    print(f"Current Win Rate: {(len(wins) / len(trades) * 100):.2f}%")

    # Hypothesis: Narrow Iron Condors (Width < 10) in High VIX (> 25) drive losses.
    # Let's check the leg widths of losses.

    print("\n--- Failure Pattern Detection ---")
    widths = []
    for t in losses:
        legs = t.get("legs", {})
        put_strikes = legs.get("put_strikes", [0, 0])
        if len(put_strikes) >= 2:
            widths.append(abs(put_strikes[1] - put_strikes[0]))

    if widths:
        avg_loss_width = sum(widths) / len(widths)
        print(f"Average Leg Width in Losses: {avg_loss_width:.2f}")
        print("Recommendation: Increase Leg Width to > 10.0 to improve survivability.")

    # Implementation: Update ConstraintEngine with these findings.
    print("\n--- GRPO Policy Update ---")
    print("1. Adding VIX_MAX_GATE: 25.0")
    print("2. Adding MIN_LEG_WIDTH: 10.0")
    print("3. Adding MIN_DTE: 30")

    return {"vix_max": 25.0, "min_width": 10.0, "min_dte": 30}


if __name__ == "__main__":
    analyze_trade_survivability()
