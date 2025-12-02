"""
Value Cost Averaging (VCA) Strategy Module

Value Cost Averaging adjusts investment amounts based on portfolio performance
relative to a target value path. When portfolio is below target, invest more;
when above target, invest less.

This complements Dollar Cost Averaging (DCA) by providing dynamic allocation
that responds to market conditions.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VCATargetPath:
    """Represents a target value path for VCA strategy."""

    start_date: datetime
    start_value: float
    target_growth_rate: float  # Annual growth rate (e.g., 0.10 for 10%)
    periods_per_year: int = 252  # Trading days per year

    def get_target_value(self, date: datetime) -> float:
        """
        Calculate target portfolio value for a given date.

        Args:
            date: Date to calculate target for

        Returns:
            Target portfolio value in dollars
        """
        days_elapsed = (date - self.start_date).days
        years_elapsed = days_elapsed / self.periods_per_year
        target_value = self.start_value * (1 + self.target_growth_rate) ** years_elapsed
        return target_value


@dataclass
class VCACalculation:
    """Result of VCA calculation."""

    base_amount: float
    adjusted_amount: float
    adjustment_factor: float
    current_value: float
    target_value: float
    deviation_pct: float
    should_invest: bool
    reason: str


class VCAStrategy:
    """
    Value Cost Averaging Strategy.

    Adjusts investment amounts based on portfolio performance relative to
    a target value path. This allows for:
    - Increased investments when portfolio is below target (buying more at lower prices)
    - Decreased investments when portfolio is above target (buying less at higher prices)
    - Potential selling when portfolio significantly exceeds target

    Attributes:
        base_allocation: Base daily investment amount (used as reference)
        target_growth_rate: Annual target growth rate (default: 10%)
        max_adjustment_factor: Maximum multiplier for investment (default: 2.0x)
        min_adjustment_factor: Minimum multiplier for investment (default: 0.3x)
        deviation_threshold: Deviation % that triggers adjustment (default: 5%)
        sell_threshold: Deviation % that triggers selling instead of buying (default: 20%)
    """

    DEFAULT_TARGET_GROWTH_RATE = 0.10  # 10% annual growth
    DEFAULT_MAX_ADJUSTMENT = 2.0  # Max 2x base amount
    DEFAULT_MIN_ADJUSTMENT = 0.3  # Min 0.3x base amount
    DEFAULT_DEVIATION_THRESHOLD = 0.05  # 5% deviation triggers adjustment
    DEFAULT_SELL_THRESHOLD = 0.20  # 20% above target triggers selling consideration

    def __init__(
        self,
        base_allocation: float,
        target_growth_rate: Optional[float] = None,
        max_adjustment_factor: Optional[float] = None,
        min_adjustment_factor: Optional[float] = None,
        deviation_threshold: Optional[float] = None,
        sell_threshold: Optional[float] = None,
        start_date: Optional[datetime] = None,
        start_value: Optional[float] = None,
    ):
        """
        Initialize VCA Strategy.

        Args:
            base_allocation: Base daily investment amount
            target_growth_rate: Annual target growth rate (default: 10%)
            max_adjustment_factor: Maximum investment multiplier (default: 2.0x)
            min_adjustment_factor: Minimum investment multiplier (default: 0.3x)
            deviation_threshold: Deviation % that triggers adjustment (default: 5%)
            sell_threshold: Deviation % that triggers selling (default: 20%)
            start_date: Start date for target path (default: now)
            start_value: Starting portfolio value (default: 0)
        """
        if base_allocation <= 0:
            raise ValueError(f"base_allocation must be positive, got {base_allocation}")

        self.base_allocation = base_allocation
        self.target_growth_rate = target_growth_rate or self.DEFAULT_TARGET_GROWTH_RATE
        self.max_adjustment_factor = max_adjustment_factor or self.DEFAULT_MAX_ADJUSTMENT
        self.min_adjustment_factor = min_adjustment_factor or self.DEFAULT_MIN_ADJUSTMENT
        self.deviation_threshold = deviation_threshold or self.DEFAULT_DEVIATION_THRESHOLD
        self.sell_threshold = sell_threshold or self.DEFAULT_SELL_THRESHOLD

        # Initialize target path
        self.start_date = start_date or datetime.now()
        self.start_value = start_value or 0.0
        self.target_path = VCATargetPath(
            start_date=self.start_date,
            start_value=self.start_value,
            target_growth_rate=self.target_growth_rate,
        )

        # Track history
        self.calculation_history: list[VCACalculation] = []

        logger.info(
            f"VCA Strategy initialized: base=${base_allocation:.2f}, "
            f"target_growth={self.target_growth_rate:.1%}, "
            f"adjustment_range=[{self.min_adjustment_factor:.1f}x, {self.max_adjustment_factor:.1f}x]"
        )

    def calculate_investment_amount(
        self,
        current_portfolio_value: float,
        date: Optional[datetime] = None,
    ) -> VCACalculation:
        """
        Calculate adjusted investment amount based on portfolio performance.

        Args:
            current_portfolio_value: Current total portfolio value
            date: Date for calculation (default: now)

        Returns:
            VCACalculation with adjusted amount and reasoning
        """
        if date is None:
            date = datetime.now()

        # Get target value for this date
        target_value = self.target_path.get_target_value(date)

        # Calculate deviation from target
        if target_value > 0:
            deviation_pct = (current_portfolio_value - target_value) / target_value
        else:
            # If no target value yet, use base allocation
            deviation_pct = 0.0

        # Determine adjustment factor
        adjustment_factor = 1.0
        should_invest = True
        reason = "Base allocation"

        if abs(deviation_pct) < self.deviation_threshold:
            # Within threshold - use base allocation
            adjustment_factor = 1.0
            reason = f"Portfolio on target (deviation: {deviation_pct:.2%})"
        elif deviation_pct < 0:
            # Below target - invest more
            # More negative deviation = higher adjustment
            # Linear scaling: -20% deviation -> 2.0x, 0% deviation -> 1.0x
            raw_factor = (
                1.0
                + abs(deviation_pct) * (self.max_adjustment_factor - 1.0) / self.deviation_threshold
            )
            adjustment_factor = min(raw_factor, self.max_adjustment_factor)
            reason = (
                f"Below target by {abs(deviation_pct):.2%} - "
                f"increasing investment ({adjustment_factor:.2f}x)"
            )
        else:
            # Above target - invest less or potentially sell
            if deviation_pct >= self.sell_threshold:
                # Significantly above target - skip investment
                adjustment_factor = 0.0
                should_invest = False
                reason = (
                    f"Above target by {deviation_pct:.2%} - "
                    f"skipping investment (consider taking profits)"
                )
            else:
                # Moderately above target - reduce investment
                # Linear scaling: 0% deviation -> 1.0x, sell_threshold -> 0.3x
                raw_factor = 1.0 - (deviation_pct / self.sell_threshold) * (
                    1.0 - self.min_adjustment_factor
                )
                adjustment_factor = max(raw_factor, self.min_adjustment_factor)
                reason = (
                    f"Above target by {deviation_pct:.2%} - "
                    f"reducing investment ({adjustment_factor:.2f}x)"
                )

        # Calculate adjusted amount
        adjusted_amount = self.base_allocation * adjustment_factor

        # Round to reasonable precision
        adjusted_amount = round(adjusted_amount, 2)

        calculation = VCACalculation(
            base_amount=self.base_allocation,
            adjusted_amount=adjusted_amount,
            adjustment_factor=adjustment_factor,
            current_value=current_portfolio_value,
            target_value=target_value,
            deviation_pct=deviation_pct,
            should_invest=should_invest,
            reason=reason,
        )

        # Store in history
        self.calculation_history.append(calculation)

        logger.info(
            f"VCA Calculation: current=${current_portfolio_value:.2f}, "
            f"target=${target_value:.2f}, deviation={deviation_pct:.2%}, "
            f"adjustment={adjustment_factor:.2f}x, amount=${adjusted_amount:.2f}"
        )

        return calculation

    def update_start_value(self, new_value: float) -> None:
        """
        Update the starting value for target path calculation.

        This is useful when portfolio value changes significantly (e.g., after
        a large deposit or withdrawal).

        Args:
            new_value: New starting portfolio value
        """
        self.start_value = new_value
        self.target_path.start_value = new_value
        logger.info(f"VCA start value updated to ${new_value:.2f}")

    def get_target_value(self, date: Optional[datetime] = None) -> float:
        """
        Get target portfolio value for a given date.

        Args:
            date: Date to calculate for (default: now)

        Returns:
            Target portfolio value
        """
        if date is None:
            date = datetime.now()
        return self.target_path.get_target_value(date)

    def get_recent_calculations(self, n: int = 10) -> list[VCACalculation]:
        """
        Get recent VCA calculations.

        Args:
            n: Number of recent calculations to return

        Returns:
            List of recent VCACalculation objects
        """
        return self.calculation_history[-n:] if self.calculation_history else []


def create_vca_strategy_from_config(
    base_allocation: float,
    config: Optional[dict] = None,
) -> VCAStrategy:
    """
    Create VCA strategy from configuration dictionary.

    Args:
        base_allocation: Base daily investment amount
        config: Optional configuration dict with VCA parameters

    Returns:
        Configured VCAStrategy instance
    """
    if config is None:
        config = {}

    return VCAStrategy(
        base_allocation=base_allocation,
        target_growth_rate=config.get("target_growth_rate"),
        max_adjustment_factor=config.get("max_adjustment_factor"),
        min_adjustment_factor=config.get("min_adjustment_factor"),
        deviation_threshold=config.get("deviation_threshold"),
        sell_threshold=config.get("sell_threshold"),
        start_date=config.get("start_date"),
        start_value=config.get("start_value"),
    )


# Example usage
if __name__ == "__main__":
    # Example: VCA strategy with $100 base allocation
    vca = VCAStrategy(
        base_allocation=100.0,
        target_growth_rate=0.10,  # 10% annual growth
        max_adjustment_factor=2.0,  # Up to 2x base
        min_adjustment_factor=0.3,  # Down to 0.3x base
    )

    # Simulate portfolio values
    test_cases = [
        (5000.0, "Below target"),
        (5500.0, "On target"),
        (6000.0, "Above target"),
        (7000.0, "Significantly above target"),
    ]

    for portfolio_value, description in test_cases:
        calc = vca.calculate_investment_amount(portfolio_value)
        print(f"\n{description}:")
        print(f"  Portfolio: ${portfolio_value:.2f}")
        print(f"  Target: ${calc.target_value:.2f}")
        print(f"  Deviation: {calc.deviation_pct:.2%}")
        print(f"  Adjustment: {calc.adjustment_factor:.2f}x")
        print(f"  Investment: ${calc.adjusted_amount:.2f}")
        print(f"  Reason: {calc.reason}")
