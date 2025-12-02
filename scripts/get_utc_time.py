#!/usr/bin/env python3
"""
Calculate UTC time for Eastern Time schedules, automatically handling DST.

This script calculates the correct UTC time for a given Eastern Time,
automatically accounting for Daylight Saving Time transitions.

Usage:
    python3 scripts/get_utc_time.py <hour> <minute> [day_of_week]

Examples:
    python3 scripts/get_utc_time.py 9 35        # 9:35 AM ET -> UTC
    python3 scripts/get_utc_time.py 10 0 0,6    # 10:00 AM ET on weekends -> UTC
"""

import sys
from datetime import datetime, timedelta

import pytz


def get_utc_cron(eastern_hour: int, eastern_minute: int, day_of_week: str = None) -> str:
    """
    Calculate UTC cron expression for Eastern Time, handling DST automatically.

    Args:
        eastern_hour: Hour in Eastern Time (0-23)
        eastern_minute: Minute (0-59)
        day_of_week: Optional day of week (e.g., "1-5" for weekdays, "0,6" for weekends)

    Returns:
        Cron expression string (minute hour * * day_of_week)
    """
    eastern = pytz.timezone("America/New_York")
    utc = pytz.UTC

    # Get current date to determine DST status
    now = datetime.now(eastern)

    # Create a time object for Eastern Time
    et_time = now.replace(hour=eastern_hour, minute=eastern_minute, second=0, microsecond=0)

    # Convert to UTC
    utc_time = eastern.localize(et_time).astimezone(utc)

    # Extract UTC hour and minute
    utc_hour = utc_time.hour
    utc_minute = utc_time.minute

    # Build cron expression
    cron_parts = [str(utc_minute), str(utc_hour), "*", "*"]

    if day_of_week:
        cron_parts.append(day_of_week)
    else:
        cron_parts.append("*")

    return " ".join(cron_parts)


def get_utc_time_info(eastern_hour: int, eastern_minute: int) -> dict:
    """
    Get detailed timezone information for Eastern Time conversion.

    Returns:
        Dictionary with UTC time, DST status, and cron expression
    """
    eastern = pytz.timezone("America/New_York")
    utc = pytz.UTC

    now = datetime.now(eastern)
    et_time = now.replace(hour=eastern_hour, minute=eastern_minute, second=0, microsecond=0)
    et_localized = eastern.localize(et_time)
    utc_time = et_localized.astimezone(utc)

    is_dst = et_localized.dst() != timedelta(0)

    return {
        "eastern_time": f"{eastern_hour:02d}:{eastern_minute:02d}",
        "utc_time": f"{utc_time.hour:02d}:{utc_time.minute:02d}",
        "is_dst": is_dst,
        "timezone_name": "EDT" if is_dst else "EST",
        "utc_offset": f"UTC{'+' if is_dst else ''}{et_localized.utcoffset().total_seconds() / 3600:.0f}",
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/get_utc_time.py <hour> <minute> [day_of_week]")
        print("\nExamples:")
        print("  python3 scripts/get_utc_time.py 9 35        # 9:35 AM ET")
        print("  python3 scripts/get_utc_time.py 10 0 0,6     # 10:00 AM ET on weekends")
        sys.exit(1)

    try:
        hour = int(sys.argv[1])
        minute = int(sys.argv[2])
        day_of_week = sys.argv[3] if len(sys.argv) > 3 else None

        if not (0 <= hour <= 23):
            print(f"Error: Hour must be 0-23, got {hour}")
            sys.exit(1)
        if not (0 <= minute <= 59):
            print(f"Error: Minute must be 0-59, got {minute}")
            sys.exit(1)

        cron = get_utc_cron(hour, minute, day_of_week)
        info = get_utc_time_info(hour, minute)

        print(
            f"Eastern Time: {info['eastern_time']} {info['timezone_name']} ({info['utc_offset']})"
        )
        print(f"UTC Time: {info['utc_time']} UTC")
        print(f"Cron Expression: '{cron}'")
        print(
            f"\nCurrent DST Status: {'Daylight Saving Time (EDT)' if info['is_dst'] else 'Standard Time (EST)'}"
        )

        # Output cron for easy copy-paste
        print("\n# Copy this to your workflow:")
        print(f"- cron: '{cron}'")

    except ValueError as e:
        print(f"Error: Invalid input - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
