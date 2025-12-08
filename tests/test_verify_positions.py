#!/usr/bin/env python3
"""
Unit tests for verify_positions.py script

Tests the position comparison logic without requiring live API access.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_compare_positions_exact_match():
    """Test when positions match exactly."""
    from verify_positions import Position, compare_positions

    local = {
        "SPY": Position(
            symbol="SPY",
            quantity=10.0,
            market_value=5000.0,
            avg_entry_price=500.0,
            current_price=500.0,
            unrealized_pl=0.0,
        )
    }

    alpaca = {
        "SPY": Position(
            symbol="SPY",
            quantity=10.0,
            market_value=5000.0,
            avg_entry_price=500.0,
            current_price=500.0,
            unrealized_pl=0.0,
        )
    }

    discrepancies = compare_positions(local, alpaca)
    assert len(discrepancies) == 0, "Expected no discrepancies for exact match"


def test_compare_positions_quantity_mismatch():
    """Test when quantities don't match."""
    from verify_positions import Position, compare_positions

    local = {
        "SPY": Position(
            symbol="SPY",
            quantity=10.0,
            market_value=5000.0,
            avg_entry_price=500.0,
            current_price=500.0,
            unrealized_pl=0.0,
        )
    }

    alpaca = {
        "SPY": Position(
            symbol="SPY",
            quantity=11.0,  # Different quantity
            market_value=5500.0,
            avg_entry_price=500.0,
            current_price=500.0,
            unrealized_pl=0.0,
        )
    }

    discrepancies = compare_positions(local, alpaca)
    assert len(discrepancies) >= 1, "Expected discrepancy for quantity mismatch"
    assert any("Quantity" in d.issue for d in discrepancies)


def test_compare_positions_missing_in_alpaca():
    """Test when position exists locally but not in Alpaca (phantom)."""
    from verify_positions import Position, compare_positions

    local = {
        "SPY": Position(
            symbol="SPY",
            quantity=10.0,
            market_value=5000.0,
            avg_entry_price=500.0,
            current_price=500.0,
            unrealized_pl=0.0,
        )
    }

    alpaca = {}  # Empty - position missing in Alpaca

    discrepancies = compare_positions(local, alpaca)
    assert len(discrepancies) == 1, "Expected discrepancy for phantom position"
    assert "phantom" in discrepancies[0].issue.lower()


def test_compare_positions_missing_in_local():
    """Test when position exists in Alpaca but not locally."""
    from verify_positions import Position, compare_positions

    local = {}  # Empty - position missing locally

    alpaca = {
        "SPY": Position(
            symbol="SPY",
            quantity=10.0,
            market_value=5000.0,
            avg_entry_price=500.0,
            current_price=500.0,
            unrealized_pl=0.0,
        )
    }

    discrepancies = compare_positions(local, alpaca)
    assert len(discrepancies) == 1, "Expected discrepancy for missing local position"
    assert "NOT in local" in discrepancies[0].issue


def test_compare_positions_value_mismatch():
    """Test when values differ by more than tolerance."""
    from verify_positions import Position, compare_positions

    local = {
        "SPY": Position(
            symbol="SPY",
            quantity=10.0,
            market_value=5000.0,
            avg_entry_price=500.0,
            current_price=500.0,
            unrealized_pl=0.0,
        )
    }

    alpaca = {
        "SPY": Position(
            symbol="SPY",
            quantity=10.0,
            market_value=5100.0,  # 2% higher (>1% tolerance)
            avg_entry_price=500.0,
            current_price=510.0,
            unrealized_pl=100.0,
        )
    }

    discrepancies = compare_positions(local, alpaca)
    # Should have value mismatch
    assert any("Value" in d.issue for d in discrepancies)


def test_compare_positions_small_value_diff_ok():
    """Test that small value differences within tolerance are OK."""
    from verify_positions import Position, compare_positions

    local = {
        "SPY": Position(
            symbol="SPY",
            quantity=10.0,
            market_value=5000.0,
            avg_entry_price=500.0,
            current_price=500.0,
            unrealized_pl=0.0,
        )
    }

    alpaca = {
        "SPY": Position(
            symbol="SPY",
            quantity=10.0,
            market_value=5004.0,  # 0.08% difference (within 1% tolerance)
            avg_entry_price=500.0,
            current_price=500.40,
            unrealized_pl=4.0,
        )
    }

    discrepancies = compare_positions(local, alpaca)
    # Should have no value mismatch (within tolerance)
    assert not any("Value" in d.issue for d in discrepancies)


def test_load_local_positions():
    """Test loading positions from system_state.json."""
    from verify_positions import load_local_positions

    # Create temporary state file
    state_data = {
        "performance": {
            "open_positions": [
                {
                    "symbol": "SPY",
                    "quantity": 10.5,
                    "amount": 5250.0,
                    "entry_price": 500.0,
                    "current_price": 500.0,
                    "unrealized_pl": 0.0,
                },
                {
                    "symbol": "QQQ",
                    "quantity": 5.2,
                    "amount": 2080.0,
                    "entry_price": 400.0,
                    "current_price": 400.0,
                    "unrealized_pl": 0.0,
                },
            ]
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(state_data, f)
        temp_path = f.name

    try:
        # Mock the STATE_FILE path
        import verify_positions

        original_state_file = verify_positions.STATE_FILE
        verify_positions.STATE_FILE = Path(temp_path)

        positions = load_local_positions()

        assert len(positions) == 2
        assert "SPY" in positions
        assert "QQQ" in positions
        assert positions["SPY"].quantity == 10.5
        assert positions["QQQ"].market_value == 2080.0

    finally:
        # Restore original
        verify_positions.STATE_FILE = original_state_file
        Path(temp_path).unlink()


def test_write_github_output(tmp_path):
    """Test writing to GITHUB_OUTPUT file."""
    from verify_positions import write_github_output

    output_file = tmp_path / "github_output.txt"

    # Mock GITHUB_OUTPUT environment variable
    import verify_positions

    original_output = verify_positions.GITHUB_OUTPUT
    verify_positions.GITHUB_OUTPUT = str(output_file)

    try:
        write_github_output(positions_match=True, discrepancy_count=0)

        # Verify file contents
        assert output_file.exists()
        contents = output_file.read_text()
        assert "positions_match=true" in contents
        assert "discrepancy_count=0" in contents

    finally:
        verify_positions.GITHUB_OUTPUT = original_output


def test_main_missing_credentials():
    """Test main() when credentials are missing."""
    from verify_positions import main

    # Mock missing credentials
    import verify_positions

    original_key = verify_positions.ALPACA_API_KEY
    original_secret = verify_positions.ALPACA_SECRET_KEY

    verify_positions.ALPACA_API_KEY = None
    verify_positions.ALPACA_SECRET_KEY = None

    try:
        exit_code = main()
        assert exit_code == 1, "Expected exit code 1 for missing credentials"
    finally:
        verify_positions.ALPACA_API_KEY = original_key
        verify_positions.ALPACA_SECRET_KEY = original_secret


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
