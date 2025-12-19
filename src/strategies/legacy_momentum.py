"""Stub module - original deleted in cleanup."""


class LegacyMomentumCalculator:
    """Stub for deleted momentum calculator.

    Provides minimal attributes needed by MomentumAgent.
    """

    # Default thresholds used by MomentumAgent
    macd_threshold: float = 0.0
    rsi_overbought: float = 70.0
    volume_min: float = 1000000.0

    def __init__(self, *args, **kwargs):
        pass

    def calculate(self, *args, **kwargs) -> float:
        return 0.0

    def get_signal(self, *args, **kwargs) -> str:
        return "neutral"
