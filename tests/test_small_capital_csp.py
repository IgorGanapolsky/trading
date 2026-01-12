"""Tests for small capital CSP strategy."""

import json
from pathlib import Path

import pytest


class TestCapitalTiers:
    """Test capital tier logic."""

    def test_tier_configuration_exists(self):
        """Verify tier configuration is properly defined."""
        # Import after patching potential dependencies
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import CAPITAL_TIERS

        assert 500 in CAPITAL_TIERS
        assert 1000 in CAPITAL_TIERS
        assert 2000 in CAPITAL_TIERS
        assert 5000 in CAPITAL_TIERS

    def test_tier_500_has_cheap_stocks(self):
        """$500 tier should only have cheap stocks."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import CAPITAL_TIERS

        tier = CAPITAL_TIERS[500]
        assert tier["max_strike"] == 5.0
        assert "F" in tier["watchlist"] or "SOFI" in tier["watchlist"]

    def test_get_tier_for_insufficient_capital(self):
        """$200 should return insufficient tier."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import get_tier_for_capital

        tier = get_tier_for_capital(200)
        assert tier["tier_capital"] == 0
        assert tier["max_strike"] == 0
        assert "INSUFFICIENT" in tier["strategy"]

    def test_get_tier_for_500(self):
        """$500 should return tier 500."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import get_tier_for_capital

        tier = get_tier_for_capital(500)
        assert tier["tier_capital"] == 500
        assert tier["max_strike"] == 5.0

    def test_get_tier_for_750(self):
        """$750 should still use tier 500."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import get_tier_for_capital

        tier = get_tier_for_capital(750)
        assert tier["tier_capital"] == 500

    def test_get_tier_for_5000(self):
        """$5000 should use tier 5000."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import get_tier_for_capital

        tier = get_tier_for_capital(5000)
        assert tier["tier_capital"] == 5000
        assert tier["max_strike"] == 50.0


class TestRecommendation:
    """Test Phil Town recommendation logic."""

    def test_strong_buy_below_mos(self):
        """Price below MOS should be STRONG BUY."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import get_recommendation

        result = get_recommendation(current=40, sticker=100, mos=50)
        assert "STRONG BUY" in result

    def test_buy_below_sticker(self):
        """Price below sticker but above MOS should be BUY."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import get_recommendation

        result = get_recommendation(current=75, sticker=100, mos=50)
        assert "BUY" in result and "STRONG" not in result

    def test_hold_near_fair_value(self):
        """Price near sticker should be HOLD."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import get_recommendation

        result = get_recommendation(current=105, sticker=100, mos=50)
        assert "HOLD" in result

    def test_overvalued(self):
        """Price well above sticker should be OVERVALUED."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from scripts.small_capital_csp import get_recommendation

        result = get_recommendation(current=150, sticker=100, mos=50)
        assert "OVERVALUED" in result


class TestWatchlistFile:
    """Test watchlist JSON file."""

    def test_watchlist_file_exists(self):
        """Watchlist file should exist."""
        watchlist_path = Path("data/watchlist_4ms_small_capital.json")
        assert watchlist_path.exists()

    def test_watchlist_has_capital_tiers(self):
        """Watchlist should have capital tier configuration."""
        watchlist_path = Path("data/watchlist_4ms_small_capital.json")
        with open(watchlist_path) as f:
            data = json.load(f)

        assert "capital_tiers" in data
        assert "tier_2_500" in data["capital_tiers"]

    def test_watchlist_has_4ms_stocks(self):
        """Watchlist should have 4Ms analyzed stocks."""
        watchlist_path = Path("data/watchlist_4ms_small_capital.json")
        with open(watchlist_path) as f:
            data = json.load(f)

        assert "small_cap_4ms_watchlist" in data
        stocks = data["small_cap_4ms_watchlist"]
        assert len(stocks) > 0

        # Each stock should have 4Ms fields
        for stock in stocks:
            assert "symbol" in stock
            assert "meaning" in stock
            assert "moat" in stock
            assert "management" in stock


@pytest.mark.skip(reason="System state structure changed - tests need update")
class TestSystemStateMilestones:
    """Test system state milestone corrections."""

    def test_first_trade_target_is_500(self):
        """First trade should require $500, not $200."""
        state_path = Path("data/system_state.json")
        with open(state_path) as f:
            state = json.load(f)

        target = state["account"]["deposit_strategy"]["target_for_first_trade"]
        assert target == 500.0, f"First trade target should be $500, got ${target}"

    def test_200_tier_has_zero_daily_target(self):
        """$200 tier should have $0 daily target (accumulation only)."""
        state_path = Path("data/system_state.json")
        with open(state_path) as f:
            state = json.load(f)

        tiers = state["account"]["north_star"]["capital_tiers"]
        tier_200 = next((t for t in tiers if t["capital"] == 200), None)

        assert tier_200 is not None
        assert tier_200["daily_target"] == 0

    def test_500_tier_has_realistic_target(self):
        """$500 tier should have realistic daily target (~$1.50)."""
        state_path = Path("data/system_state.json")
        with open(state_path) as f:
            state = json.load(f)

        tiers = state["account"]["north_star"]["capital_tiers"]
        tier_500 = next((t for t in tiers if t["capital"] == 500), None)

        assert tier_500 is not None
        assert tier_500["daily_target"] <= 5.0, "Daily target should be realistic"
