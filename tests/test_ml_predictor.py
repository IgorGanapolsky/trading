import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.inference import MLPredictor


@pytest.mark.skip(reason="MLPredictor and ModelTrainer are deprecated/removed")
def test_ml_predictor():
    print("Initializing ML Predictor...")
    predictor = MLPredictor()

    symbol = "SPY"
    print(f"Getting signal for {symbol}...")
    signal = predictor.get_signal(symbol)

    print("\nSignal Result:")
    print(signal)

    if signal["action"] in ["BUY", "SELL", "HOLD"]:
        print("\n✅ Test Passed: Valid signal received")
    else:
        print("\n❌ Test Failed: Invalid signal")


if __name__ == "__main__":
    test_ml_predictor()
