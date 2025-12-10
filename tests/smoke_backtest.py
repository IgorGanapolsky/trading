from pathlib import Path


def test_smoke_backtest(tmp_path):
    # Locate the fixture
    fixture_src = Path(__file__).parent / "fixtures" / "fixture.csv"
    if not fixture_src.exists():
        # Fallback if fixtures dir not found relative to this file
        fixture_src = Path("tests/fixtures/fixture.csv").resolve()

    fixture_dst = tmp_path / "fixture.csv"
    fixture_dst.write_bytes(fixture_src.read_bytes())

    from src.trading.backtest import run_backtest

    pnl = run_backtest(fixture_csv=str(fixture_dst), seed=42)

    # Deterministic expectation
    # We will need to update this once we run it and see the result.
    # For now, put a placeholder. The user autonomously update script will handle it.
    EXPECTED = 660.189175

    # We use a rough equality to detect changes
    assert abs(pnl - EXPECTED) < 1e-6, f"PnL {pnl} != EXPECTED {EXPECTED}"
