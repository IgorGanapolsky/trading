"""
100% Test Coverage for update_blog_positions.py

Tests the blog update functionality that displays paper trading positions.

Created: Jan 4, 2026
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from update_blog_positions import (
    generate_positions_table,
    load_paper_account,
    load_positions,
    update_dashboard_md,
    update_index_md,
)


class TestLoadPositions:
    """Test loading positions from system_state.json."""

    def test_load_positions_success(self, tmp_path):
        """Test loading valid positions."""
        state_file = tmp_path / "data" / "system_state.json"
        state_file.parent.mkdir(parents=True)
        state = {
            "performance": {
                "open_positions": [
                    {
                        "symbol": "SPY",
                        "quantity": 10,
                        "entry_price": 590,
                        "current_price": 595,
                        "market_value": 5950,
                        "unrealized_pl": 50,
                        "side": "long",
                    },
                    {
                        "symbol": "AAPL",
                        "quantity": 5,
                        "entry_price": 180,
                        "current_price": 185,
                        "market_value": 925,
                        "unrealized_pl": 25,
                        "side": "long",
                    },
                ]
            }
        }
        state_file.write_text(json.dumps(state))

        with patch("update_blog_positions.SYSTEM_STATE", state_file):
            positions = load_positions()

        assert len(positions) == 2
        assert positions[0]["symbol"] == "SPY"
        assert positions[1]["symbol"] == "AAPL"

    def test_load_positions_empty(self, tmp_path):
        """Test loading when no positions exist."""
        state_file = tmp_path / "data" / "system_state.json"
        state_file.parent.mkdir(parents=True)
        state = {"performance": {"open_positions": []}}
        state_file.write_text(json.dumps(state))

        with patch("update_blog_positions.SYSTEM_STATE", state_file):
            positions = load_positions()

        assert positions == []

    def test_load_positions_missing_file(self, tmp_path):
        """Test loading when state file doesn't exist."""
        with patch("update_blog_positions.SYSTEM_STATE", tmp_path / "nonexistent.json"):
            positions = load_positions()

        assert positions == []

    def test_load_positions_missing_performance_key(self, tmp_path):
        """Test loading when performance key is missing."""
        state_file = tmp_path / "data" / "system_state.json"
        state_file.parent.mkdir(parents=True)
        state = {"account": {"equity": 100000}}
        state_file.write_text(json.dumps(state))

        with patch("update_blog_positions.SYSTEM_STATE", state_file):
            positions = load_positions()

        assert positions == []


class TestLoadPaperAccount:
    """Test loading paper account data."""

    def test_load_paper_account_success(self, tmp_path):
        """Test loading valid paper account data."""
        state_file = tmp_path / "data" / "system_state.json"
        state_file.parent.mkdir(parents=True)
        state = {
            "paper_account": {
                "current_equity": 100942.23,
                "total_pl_pct": 0.94,
                "win_rate": 80.0,
            }
        }
        state_file.write_text(json.dumps(state))

        with patch("update_blog_positions.SYSTEM_STATE", state_file):
            account = load_paper_account()

        assert account["current_equity"] == 100942.23
        assert account["total_pl_pct"] == 0.94
        assert account["win_rate"] == 80.0

    def test_load_paper_account_missing_file(self, tmp_path):
        """Test loading when state file doesn't exist."""
        with patch("update_blog_positions.SYSTEM_STATE", tmp_path / "nonexistent.json"):
            account = load_paper_account()

        assert account == {}


class TestGeneratePositionsTable:
    """Test markdown table generation."""

    def test_generate_table_with_positions(self):
        """Test generating table with positions."""
        positions = [
            {
                "symbol": "SPY",
                "side": "long",
                "entry_price": 590.00,
                "current_price": 595.00,
                "unrealized_pl": 50.00,
                "unrealized_pl_pct": 0.85,
                "market_value": 5950.00,
            },
            {
                "symbol": "AAPL",
                "side": "long",
                "entry_price": 180.00,
                "current_price": 185.00,
                "unrealized_pl": 25.00,
                "unrealized_pl_pct": 2.78,
                "market_value": 925.00,
            },
        ]

        table = generate_positions_table(positions)

        assert "SPY" in table
        assert "AAPL" in table
        assert "Long" in table
        assert "$590.00" in table
        assert "$595.00" in table
        assert "+$50.00" in table

    def test_generate_table_empty(self):
        """Test generating table with no positions."""
        table = generate_positions_table([])

        assert "*No open positions*" in table

    def test_generate_table_negative_pl(self):
        """Test generating table with negative P/L."""
        positions = [
            {
                "symbol": "TSLA",
                "side": "long",
                "entry_price": 250.00,
                "current_price": 240.00,
                "unrealized_pl": -100.00,
                "unrealized_pl_pct": -4.0,
                "market_value": 2400.00,
            },
        ]

        table = generate_positions_table(positions)

        assert "TSLA" in table
        assert "-$100.00" in table or "$-100.00" in table

    def test_generate_table_sorted_by_value(self):
        """Test that positions are sorted by market value descending."""
        positions = [
            {
                "symbol": "SMALL",
                "side": "long",
                "entry_price": 10,
                "current_price": 11,
                "unrealized_pl": 1,
                "unrealized_pl_pct": 10,
                "market_value": 100,
            },
            {
                "symbol": "LARGE",
                "side": "long",
                "entry_price": 100,
                "current_price": 110,
                "unrealized_pl": 100,
                "unrealized_pl_pct": 10,
                "market_value": 10000,
            },
            {
                "symbol": "MEDIUM",
                "side": "long",
                "entry_price": 50,
                "current_price": 55,
                "unrealized_pl": 50,
                "unrealized_pl_pct": 10,
                "market_value": 1000,
            },
        ]

        table = generate_positions_table(positions)
        lines = table.strip().split("\n")

        # LARGE should come first (highest market value)
        assert "LARGE" in lines[0]


class TestUpdateIndexMd:
    """Test updating index.md with positions."""

    @pytest.fixture
    def sample_index(self, tmp_path):
        """Create sample index.md."""
        index_path = tmp_path / "docs" / "index.md"
        index_path.parent.mkdir(parents=True)
        content = """---
layout: home
---

## Daily Transparency Report

### Paper Trading (R&D)

| Metric | Value | Trend |
|--------|-------|-------|
| **Day** | 50/90 | R&D Phase |
| **Portfolio** | $100,000.00 | +0.00% |
| **Win Rate** | 50% | Stable |
| **Lessons** | 50+ | Growing |

> **Strategy**: Backtest and analyze during off-hours. Apply proven strategies to real account.

---

## What's Working
"""
        index_path.write_text(content)
        return index_path

    def test_update_index_with_positions(self, sample_index):
        """Test updating index.md with positions."""
        positions = [
            {
                "symbol": "SPY",
                "side": "long",
                "entry_price": 590,
                "current_price": 595,
                "unrealized_pl": 50,
                "unrealized_pl_pct": 0.85,
                "market_value": 5950,
            },
        ]
        paper_account = {"current_equity": 100942.23, "total_pl_pct": 0.94, "win_rate": 80.0}

        with patch("update_blog_positions.INDEX_MD", sample_index):
            result = update_index_md(positions, paper_account)

        assert result is True

        content = sample_index.read_text()
        assert "Open Positions (1)" in content
        assert "SPY" in content
        assert "$100,942.23" in content

    def test_update_index_empty_positions(self, sample_index):
        """Test updating index.md with no positions."""
        positions = []
        paper_account = {"current_equity": 100000, "total_pl_pct": 0, "win_rate": 50}

        with patch("update_blog_positions.INDEX_MD", sample_index):
            result = update_index_md(positions, paper_account)

        assert result is True

        content = sample_index.read_text()
        assert "Open Positions (0)" in content
        assert "*No open positions*" in content

    def test_update_index_missing_file(self, tmp_path):
        """Test updating non-existent index.md."""
        with patch("update_blog_positions.INDEX_MD", tmp_path / "nonexistent.md"):
            result = update_index_md([], {})

        assert result is False


class TestUpdateDashboardMd:
    """Test updating progress_dashboard.md with positions."""

    @pytest.fixture
    def sample_dashboard(self, tmp_path):
        """Create sample progress_dashboard.md."""
        dashboard_path = tmp_path / "docs" / "progress_dashboard.md"
        dashboard_path.parent.mkdir(parents=True)
        content = """# Trading System Progress Dashboard

## Current Positions

### Live Account

| Symbol | Type | Strike | Expiry | Entry | Current | P/L |
|--------|------|--------|--------|-------|---------|-----|
| *No positions yet* | - | - | - | - | - | - |

---

## Recent Trades
"""
        dashboard_path.write_text(content)
        return dashboard_path

    def test_update_dashboard_with_positions(self, sample_dashboard):
        """Test updating dashboard.md with positions."""
        positions = [
            {
                "symbol": "SPY",
                "side": "long",
                "entry_price": 590,
                "current_price": 595,
                "unrealized_pl": 50,
                "unrealized_pl_pct": 0.85,
                "market_value": 5950,
            },
            {
                "symbol": "AAPL",
                "side": "long",
                "entry_price": 180,
                "current_price": 185,
                "unrealized_pl": 25,
                "unrealized_pl_pct": 2.78,
                "market_value": 925,
            },
        ]

        with patch("update_blog_positions.DASHBOARD_MD", sample_dashboard):
            result = update_dashboard_md(positions)

        assert result is True

        content = sample_dashboard.read_text()
        assert "Paper Account (2 positions)" in content
        assert "SPY" in content
        assert "AAPL" in content

    def test_update_dashboard_missing_file(self, tmp_path):
        """Test updating non-existent dashboard.md."""
        with patch("update_blog_positions.DASHBOARD_MD", tmp_path / "nonexistent.md"):
            result = update_dashboard_md([])

        assert result is False


class TestSmokeTests:
    """Smoke tests for the update_blog_positions script."""

    def test_script_exists(self):
        script_path = Path(__file__).parent.parent / "scripts" / "update_blog_positions.py"
        assert script_path.exists(), f"Script not found at {script_path}"

    def test_script_is_valid_python(self):
        script_path = Path(__file__).parent.parent / "scripts" / "update_blog_positions.py"
        import py_compile

        py_compile.compile(str(script_path), doraise=True)

    def test_script_has_shebang(self):
        script_path = Path(__file__).parent.parent / "scripts" / "update_blog_positions.py"
        content = script_path.read_text()
        assert content.startswith("#!/usr/bin/env python3")

    def test_script_has_docstring(self):
        script_path = Path(__file__).parent.parent / "scripts" / "update_blog_positions.py"
        content = script_path.read_text()
        assert '"""' in content

    def test_imports_work(self):
        """Verify all imports in the script work."""
        from update_blog_positions import (
            generate_positions_table,
            load_paper_account,
            load_positions,
            main,
            update_dashboard_md,
            update_index_md,
        )

        assert callable(load_positions)
        assert callable(load_paper_account)
        assert callable(generate_positions_table)
        assert callable(update_index_md)
        assert callable(update_dashboard_md)
        assert callable(main)


class TestMainFunction:
    """Test the main function."""

    def test_main_success(self, tmp_path):
        """Test main function with valid setup."""
        # Setup state file
        state_file = tmp_path / "data" / "system_state.json"
        state_file.parent.mkdir(parents=True)
        state = {
            "performance": {
                "open_positions": [
                    {
                        "symbol": "SPY",
                        "side": "long",
                        "entry_price": 590,
                        "current_price": 595,
                        "unrealized_pl": 50,
                        "unrealized_pl_pct": 0.85,
                        "market_value": 5950,
                    }
                ]
            },
            "paper_account": {"current_equity": 100942.23, "total_pl_pct": 0.94, "win_rate": 80},
        }
        state_file.write_text(json.dumps(state))

        # Setup index.md
        index_path = tmp_path / "docs" / "index.md"
        index_path.parent.mkdir(parents=True)
        index_path.write_text("""### Paper Trading (R&D)

| Metric | Value | Trend |
|--------|-------|-------|

> **Strategy**: Test.

---

## What's Working
""")

        # Setup dashboard.md
        dashboard_path = tmp_path / "docs" / "progress_dashboard.md"
        dashboard_path.write_text("""## Current Positions

### Live Account

---

## Recent Trades
""")

        with (
            patch("update_blog_positions.SYSTEM_STATE", state_file),
            patch("update_blog_positions.INDEX_MD", index_path),
            patch("update_blog_positions.DASHBOARD_MD", dashboard_path),
        ):
            from update_blog_positions import main

            result = main()

        assert result == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_position_with_missing_fields(self):
        """Test handling positions with missing fields."""
        positions = [
            {"symbol": "TEST"},  # Missing most fields
        ]

        # Should not crash, should use defaults
        table = generate_positions_table(positions)
        assert "TEST" in table

    def test_position_with_zero_values(self):
        """Test handling positions with zero values."""
        positions = [
            {
                "symbol": "ZERO",
                "side": "long",
                "entry_price": 0,
                "current_price": 0,
                "unrealized_pl": 0,
                "unrealized_pl_pct": 0,
                "market_value": 0,
            },
        ]

        table = generate_positions_table(positions)
        assert "ZERO" in table
        assert "$0.00" in table

    def test_large_position_values(self):
        """Test handling large position values."""
        positions = [
            {
                "symbol": "BIG",
                "side": "long",
                "entry_price": 1000000.00,
                "current_price": 1100000.00,
                "unrealized_pl": 100000.00,
                "unrealized_pl_pct": 10.0,
                "market_value": 11000000.00,
            },
        ]

        table = generate_positions_table(positions)
        assert "BIG" in table
        assert "$1,000,000.00" in table  # entry_price
        assert "$1,100,000.00" in table  # current_price
        assert "+$100,000.00" in table  # unrealized_pl
