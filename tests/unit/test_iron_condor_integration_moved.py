from unittest.mock import MagicMock, patch

from src.strategies.iron_condor import IronCondorController


class MockPosition:
    def __init__(self, symbol, qty):
        self.symbol = symbol
        self.qty = qty


@patch("src.strategies.iron_condor.signal.VIXMeanReversionSignal")
@patch("src.safety.mandatory_trade_gate.safe_submit_order")
def test_iron_condor_full_cycle_success(mock_submit, mock_vix):
    # 1. Mock VIX Signal to return GOOD_ENTRY
    mock_vix_inst = mock_vix.return_value
    mock_vix_inst.calculate_signal.return_value = MagicMock(
        signal="GOOD_ENTRY", confidence=0.85, reason="VIX Favorable"
    )

    # 2. Setup Controller
    mock_client = MagicMock()
    controller = IronCondorController(mock_client)

    # 3. Define Inputs (Empty positions = OK to trade)
    market_data = {"symbol": "SPY", "vix": 18.0, "vix_ma": 19.0}
    account_info = {"equity": 100000.0, "positions": []}

    # 4. Run Cycle
    result = controller.run_cycle(market_data, account_info)

    # 5. Assertions
    assert result["status"] == "READY_TO_TRADE"
    assert "GOOD" in result["signal"]


@patch("src.strategies.iron_condor.signal.VIXMeanReversionSignal")
def test_iron_condor_blocked_by_positions(mock_vix):
    # 1. Mock VIX to return GOOD
    mock_vix_inst = mock_vix.return_value
    mock_vix_inst.calculate_signal.return_value = MagicMock(signal="GOOD_ENTRY")

    # 2. Setup Controller with full positions (20 contracts = 5 ICs)
    mock_client = MagicMock()
    controller = IronCondorController(mock_client)

    full_positions = [MockPosition(f"SPY_OPT_{i}", 4) for i in range(5)]
    account_info = {"equity": 100000.0, "positions": full_positions}
    market_data = {"symbol": "SPY"}

    # 3. Run Cycle
    result = controller.run_cycle(market_data, account_info)

    # 4. Assertions
    assert result["status"] == "SKIPPED"
    assert "Max exposure" in result["reason"]
