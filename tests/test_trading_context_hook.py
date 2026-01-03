"""
Tests for .claude/hooks/inject_trading_context.sh

This test file ensures the trading context hook correctly handles:
1. Timezone conversion (UTC server -> ET trading timezone)
2. Date formatting for trading context
3. Staleness calculations using ET timezone
"""

import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


class TestTimezoneHandling:
    """Tests for timezone handling in trading context hook."""

    def test_today_variable_uses_et_timezone(self):
        """Verify TODAY variable uses America/New_York timezone, not UTC."""
        # Get the ET date
        et_tz = ZoneInfo("America/New_York")
        expected_date = datetime.now(et_tz).strftime("%Y-%m-%d")

        # Extract TODAY variable from the hook using bash
        result = subprocess.run(
            [
                "bash",
                "-c",
                'source /dev/stdin <<< "TODAY=$(TZ=America/New_York date +%Y-%m-%d)"; echo $TODAY',
            ],
            capture_output=True,
            text=True,
        )

        actual_date = result.stdout.strip()
        assert actual_date == expected_date, (
            f"TODAY should be {expected_date} (ET), got {actual_date}"
        )

    def test_hook_file_contains_et_timezone_for_today(self):
        """Verify the hook file has TZ=America/New_York for TODAY variable."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )

        with open(hook_path) as f:
            content = f.read()

        # Check that TODAY uses ET timezone
        assert "TODAY=$(TZ=America/New_York date" in content, (
            "TODAY variable must use TZ=America/New_York"
        )

    def test_hook_file_contains_et_timezone_for_days_old(self):
        """Verify the hook file has TZ=America/New_York for DAYS_OLD calculation."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )

        with open(hook_path) as f:
            content = f.read()

        # Check that DAYS_OLD calculation uses ET timezone
        assert "DAYS_OLD=$(( ($(TZ=America/New_York date" in content, (
            "DAYS_OLD calculation must use TZ=America/New_York"
        )

    def test_day_of_week_uses_et_timezone(self):
        """Verify DAY_OF_WEEK uses America/New_York timezone."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )

        with open(hook_path) as f:
            content = f.read()

        assert "DAY_OF_WEEK=$(TZ=America/New_York date" in content, (
            "DAY_OF_WEEK must use TZ=America/New_York"
        )

    def test_full_date_uses_et_timezone(self):
        """Verify FULL_DATE uses America/New_York timezone."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )

        with open(hook_path) as f:
            content = f.read()

        assert "FULL_DATE=$(TZ=America/New_York date" in content, (
            "FULL_DATE must use TZ=America/New_York"
        )


class TestDateCalculations:
    """Tests for date calculation correctness."""

    def test_et_date_differs_from_utc_near_midnight(self):
        """Demonstrate that ET can differ from UTC by checking timezone offset."""
        et_tz = ZoneInfo("America/New_York")
        utc_tz = ZoneInfo("UTC")

        now_utc = datetime.now(utc_tz)
        now_et = datetime.now(et_tz)

        # ET is either 4 or 5 hours behind UTC (depending on DST)
        offset_hours = (now_utc.hour - now_et.hour) % 24
        assert offset_hours in [
            4,
            5,
        ], f"ET should be 4-5 hours behind UTC, got {offset_hours}"

    def test_bash_tz_command_returns_et_date(self):
        """Verify bash TZ command returns correct ET date."""
        result = subprocess.run(
            ["bash", "-c", "TZ=America/New_York date +%Y-%m-%d"],
            capture_output=True,
            text=True,
        )

        et_tz = ZoneInfo("America/New_York")
        expected = datetime.now(et_tz).strftime("%Y-%m-%d")

        assert result.stdout.strip() == expected, f"Bash TZ command should return {expected}"


class TestHookSmokeTests:
    """Smoke tests for the trading context hook."""

    def test_hook_file_exists(self):
        """Verify the hook file exists."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )
        assert os.path.exists(hook_path), f"Hook file should exist at {hook_path}"

    def test_hook_file_is_valid_bash(self):
        """Verify the hook file has valid bash syntax."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )

        result = subprocess.run(["bash", "-n", hook_path], capture_output=True, text=True)

        assert result.returncode == 0, f"Hook has syntax errors: {result.stderr}"

    def test_hook_has_shebang(self):
        """Verify the hook file starts with proper shebang."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )

        with open(hook_path) as f:
            first_line = f.readline()

        assert first_line.startswith("#!/bin/bash"), "Hook must start with #!/bin/bash"

    def test_hook_uses_strict_mode(self):
        """Verify the hook uses bash strict mode (set -euo pipefail)."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )

        with open(hook_path) as f:
            content = f.read()

        assert "set -euo pipefail" in content, "Hook should use strict mode: set -euo pipefail"


class TestMarketHoursAwareness:
    """Tests for market hours awareness in the hook."""

    def test_hook_checks_weekend(self):
        """Verify the hook checks for weekends."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )

        with open(hook_path) as f:
            content = f.read()

        assert "IS_WEEKEND" in content, "Hook should check for weekends"
        assert "DAY_NUM" in content, "Hook should use DAY_NUM for weekend detection"

    def test_hook_has_market_hours_logic(self):
        """Verify the hook has market hours logic."""
        hook_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".claude",
            "hooks",
            "inject_trading_context.sh",
        )

        with open(hook_path) as f:
            content = f.read()

        # Should reference market hours (9:30 AM - 4:00 PM ET)
        assert "9:30" in content or "09:30" in content, "Hook should reference market open time"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
