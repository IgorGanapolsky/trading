"""
Test iron condor expiration calculation.

LL-292: Lost $22.61 on Jan 23, 2026 because expiration was calculated
for Sunday (Feb 22) instead of Friday. SPY options only expire on Fridays.
"""

from datetime import datetime, timedelta


def calculate_friday_expiry(target_dte: int = 30) -> datetime:
    """
    Calculate option expiry date that lands on a FRIDAY.

    SPY options expire on Fridays. This function ensures the expiry
    is always a Friday that's at least target_dte days away.
    """
    target_date = datetime.now() + timedelta(days=target_dte)
    # weekday(): Monday=0, Friday=4
    days_until_friday = (4 - target_date.weekday()) % 7
    if days_until_friday == 0 and target_date.weekday() != 4:
        days_until_friday = 7  # Next Friday if we're past Friday
    # If target is Sat/Sun, go to next Friday
    if target_date.weekday() > 4:  # Saturday=5, Sunday=6
        days_until_friday = (4 - target_date.weekday()) % 7
    expiry_date = target_date + timedelta(days=days_until_friday)
    # If this pushed us too close (<21 DTE), use the Friday after
    actual_dte = (expiry_date - datetime.now()).days
    if actual_dte < 21:
        expiry_date += timedelta(days=7)
    return expiry_date


def test_expiry_is_friday():
    """Expiry MUST be a Friday (weekday=4)."""
    expiry = calculate_friday_expiry(30)
    assert expiry.weekday() == 4, (
        f"Expected Friday (4), got {expiry.weekday()} ({expiry.strftime('%A')})"
    )


def test_expiry_not_weekend():
    """Expiry must never be Saturday or Sunday."""
    for dte in [21, 30, 35, 45]:
        expiry = calculate_friday_expiry(dte)
        assert expiry.weekday() not in [5, 6], f"Expiry {expiry} is a weekend day!"


def test_expiry_at_least_21_dte():
    """Expiry must be at least 21 DTE to avoid gamma risk."""
    expiry = calculate_friday_expiry(30)
    dte = (expiry - datetime.now()).days
    assert dte >= 21, f"DTE {dte} is less than minimum 21"


def test_jan23_2026_bug():
    """
    Regression test for LL-292 bug.

    On Jan 23, 2026, 30 DTE calculated to Feb 22, 2026 (Sunday).
    This caused all orders to fail with "asset not found".
    """
    # Simulate Jan 23, 2026
    jan23 = datetime(2026, 1, 23)
    target = jan23 + timedelta(days=30)  # Feb 22, 2026

    # Feb 22, 2026 is a Sunday
    assert target.weekday() == 6, "Feb 22, 2026 should be Sunday"

    # The fix should adjust to Feb 27 (Friday)
    days_until_friday = (4 - target.weekday()) % 7
    if days_until_friday == 0 and target.weekday() != 4:
        days_until_friday = 7
    if target.weekday() > 4:
        days_until_friday = (4 - target.weekday()) % 7
    corrected = target + timedelta(days=days_until_friday)

    assert corrected.weekday() == 4, (
        f"Corrected date should be Friday, got {corrected.strftime('%A')}"
    )
    assert corrected.month == 2, "Should still be February"
    assert corrected.day >= 27, "Should be Feb 27 or 28"
