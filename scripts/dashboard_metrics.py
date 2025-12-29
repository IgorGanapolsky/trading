"""Dashboard metrics utilities."""


def get_dashboard_metrics() -> dict:
    """Get current dashboard metrics.

    Returns:
        Dictionary with dashboard metrics.
    """
    return {
        "equity": 0,
        "pl": 0,
        "win_rate": 0,
        "trades_today": 0,
    }
