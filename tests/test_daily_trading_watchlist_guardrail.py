from pathlib import Path


def test_daily_trading_auto_heals_missing_watchlist() -> None:
    workflow = Path(".github/workflows/daily-trading.yml").read_text(encoding="utf-8")

    assert "tier2_watchlist.json not found - auto-healing with SPY/IWM fallback" in workflow
    assert "fallback_payload" in workflow
    assert '"watchlist": ["SPY", "IWM"]' in workflow
    assert 'watchlist_path.write_text(json.dumps(fallback_payload, indent=2) + "\\n"' in workflow


def test_baseline_watchlist_file_exists() -> None:
    watchlist_path = Path("data/tier2_watchlist.json")
    assert watchlist_path.exists(), "data/tier2_watchlist.json should exist"

    content = watchlist_path.read_text(encoding="utf-8")
    assert '"watchlist"' in content
    assert '"SPY"' in content
    assert '"IWM"' in content
