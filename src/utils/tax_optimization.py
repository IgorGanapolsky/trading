"""
Tax Optimization Module for Trading System

Handles:
- Pattern Day Trader (PDT) rule compliance ($25k minimum equity)
- Wash sale rule tracking (30-day window)
- Short-term vs long-term capital gains optimization
- Tax-loss harvesting
- After-tax return calculations
- Integration with RL/ML pipeline for tax-aware decisions
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Tax rates (2025 - update annually)
SHORT_TERM_TAX_RATE = 0.37  # Highest federal bracket (37% + state)
LONG_TERM_TAX_RATE = 0.20  # Highest federal bracket (20% + state)
LONG_TERM_THRESHOLD_DAYS = 365  # Days to qualify for long-term capital gains

# Pattern Day Trader (PDT) rule
PDT_MINIMUM_EQUITY = 25000.0  # $25,000 minimum equity required
PDT_DAY_TRADE_THRESHOLD = 4  # 4+ day trades in 5 business days triggers PDT
PDT_LOOKBACK_DAYS = 5  # Look back 5 business days

# Wash sale rule
WASH_SALE_WINDOW_DAYS = 30  # Can't claim loss if repurchased within 30 days


@dataclass
class TaxLot:
    """Represents a tax lot (position) for tax tracking."""

    symbol: str
    quantity: float
    cost_basis: float
    purchase_date: datetime
    trade_id: str


@dataclass
class TaxEvent:
    """Represents a taxable event (trade closure)."""

    symbol: str
    sale_date: datetime
    sale_price: float
    quantity: float
    cost_basis: float
    holding_period_days: int
    gain_loss: float
    is_long_term: bool
    is_wash_sale: bool
    wash_sale_adjustment: float
    trade_id: str


class TaxOptimizer:
    """
    Tax optimization engine for trading system.

    Tracks:
    - Holding periods for long-term capital gains qualification
    - Day trading frequency for PDT rule compliance
    - Wash sale violations
    - Tax-loss harvesting opportunities
    - After-tax return calculations
    """

    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.tax_lots: dict[str, list[TaxLot]] = defaultdict(list)  # symbol -> list of lots
        self.tax_events: list[TaxEvent] = []
        self.day_trades: list[dict[str, Any]] = []  # Track day trades for PDT rule
        self.wash_sale_tracker: dict[str, list[datetime]] = defaultdict(
            list
        )  # symbol -> sale dates

    def record_trade_entry(
        self,
        symbol: str,
        quantity: float,
        price: float,
        trade_date: datetime,
        trade_id: str,
    ) -> None:
        """Record a trade entry (purchase) for tax tracking."""
        tax_lot = TaxLot(
            symbol=symbol,
            quantity=quantity,
            cost_basis=price * quantity,
            purchase_date=trade_date,
            trade_id=trade_id,
        )
        self.tax_lots[symbol].append(tax_lot)
        logger.debug(f"Recorded tax lot: {symbol} {quantity} @ ${price:.2f}")

    def record_trade_exit(
        self,
        symbol: str,
        quantity: float,
        price: float,
        sale_date: datetime,
        trade_id: str,
        method: str = "FIFO",  # FIFO, LIFO, or Specific Identification
    ) -> TaxEvent:
        """
        Record a trade exit (sale) and calculate tax implications.

        Returns:
            TaxEvent with tax calculations
        """
        if symbol not in self.tax_lots or not self.tax_lots[symbol]:
            logger.warning(f"No tax lots found for {symbol} - cannot calculate tax")
            return TaxEvent(
                symbol=symbol,
                sale_date=sale_date,
                sale_price=price,
                quantity=quantity,
                cost_basis=0.0,
                holding_period_days=0,
                gain_loss=0.0,
                is_long_term=False,
                is_wash_sale=False,
                wash_sale_adjustment=0.0,
                trade_id=trade_id,
            )

        # Select tax lot based on method (FIFO by default)
        if method == "FIFO":
            tax_lot = self.tax_lots[symbol].pop(0)  # First in, first out
        elif method == "LIFO":
            tax_lot = self.tax_lots[symbol].pop(-1)  # Last in, first out
        else:
            # Specific identification - use oldest lot
            tax_lot = min(self.tax_lots[symbol], key=lambda x: x.purchase_date)
            self.tax_lots[symbol].remove(tax_lot)

        # Calculate holding period
        holding_period = (sale_date - tax_lot.purchase_date).days
        is_long_term = holding_period >= LONG_TERM_THRESHOLD_DAYS

        # Calculate gain/loss
        proceeds = price * quantity
        cost_basis = tax_lot.cost_basis
        gain_loss = proceeds - cost_basis

        # Check for wash sale
        is_wash_sale = self._check_wash_sale(symbol, sale_date)
        wash_sale_adjustment = 0.0
        if is_wash_sale and gain_loss < 0:
            # Wash sale disallows loss deduction - add loss back to cost basis
            wash_sale_adjustment = abs(gain_loss)
            logger.warning(
                f"Wash sale detected: {symbol} sold {sale_date.date()} "
                f"within 30 days of previous sale"
            )

        # Check if this is a day trade (same-day entry/exit)
        is_day_trade = holding_period == 0
        if is_day_trade:
            self.day_trades.append(
                {
                    "symbol": symbol,
                    "date": sale_date.date(),
                    "trade_id": trade_id,
                }
            )

        # Create tax event
        tax_event = TaxEvent(
            symbol=symbol,
            sale_date=sale_date,
            sale_price=price,
            quantity=quantity,
            cost_basis=cost_basis,
            holding_period_days=holding_period,
            gain_loss=gain_loss,
            is_long_term=is_long_term,
            is_wash_sale=is_wash_sale,
            wash_sale_adjustment=wash_sale_adjustment,
            trade_id=trade_id,
        )

        self.tax_events.append(tax_event)
        self.wash_sale_tracker[symbol].append(sale_date)

        logger.debug(
            f"Recorded tax event: {symbol} {quantity} @ ${price:.2f} "
            f"| Gain/Loss: ${gain_loss:+.2f} | "
            f"{'Long-term' if is_long_term else 'Short-term'} | "
            f"{'Wash sale' if is_wash_sale else 'Clean'}"
        )

        return tax_event

    def _check_wash_sale(self, symbol: str, sale_date: datetime) -> bool:
        """Check if a sale violates wash sale rule (sold within 30 days of previous sale)."""
        if symbol not in self.wash_sale_tracker:
            return False

        for prev_sale_date in self.wash_sale_tracker[symbol]:
            days_diff = (sale_date - prev_sale_date).days
            if 0 < days_diff <= WASH_SALE_WINDOW_DAYS:
                return True

        return False

    def check_pdt_status(
        self, current_equity: float, lookback_days: int = PDT_LOOKBACK_DAYS
    ) -> dict[str, Any]:
        """
        Check Pattern Day Trader (PDT) rule compliance.

        PDT Rule: If you make 4+ day trades in 5 business days, you need $25k minimum equity.

        Returns:
            Dict with PDT status and warnings
        """
        if not self.day_trades:
            return {
                "is_pdt": False,
                "day_trades_count": 0,
                "lookback_days": lookback_days,
                "meets_equity_requirement": current_equity >= PDT_MINIMUM_EQUITY,
                "status": "✅ Compliant",
                "warnings": [],
            }

        # Count day trades in last N business days
        cutoff_date = datetime.now().date() - timedelta(days=lookback_days)
        recent_day_trades = [dt for dt in self.day_trades if dt["date"] >= cutoff_date]

        day_trade_count = len(recent_day_trades)
        is_pdt = day_trade_count >= PDT_DAY_TRADE_THRESHOLD
        meets_equity = current_equity >= PDT_MINIMUM_EQUITY

        warnings = []
        status = "✅ Compliant"

        if is_pdt and not meets_equity:
            status = "🚨 PDT VIOLATION RISK"
            warnings.append(
                f"⚠️ **PDT RULE VIOLATION**: {day_trade_count} day trades in last {lookback_days} days "
                f"requires ${PDT_MINIMUM_EQUITY:,.0f} minimum equity. Current: ${current_equity:,.2f}. "
                f"**Action**: Reduce day trading frequency or increase equity to ${PDT_MINIMUM_EQUITY:,.0f}+"
            )
        elif is_pdt and meets_equity:
            status = "⚠️ PDT Status Active"
            warnings.append(
                f"⚠️ **PDT STATUS ACTIVE**: {day_trade_count} day trades in last {lookback_days} days. "
                f"Must maintain ${PDT_MINIMUM_EQUITY:,.0f}+ equity to continue day trading."
            )
        elif day_trade_count >= 2:
            status = "⚠️ Approaching PDT Threshold"
            warnings.append(
                f"⚠️ **APPROACHING PDT THRESHOLD**: {day_trade_count} day trades in last {lookback_days} days. "
                f"Need {PDT_DAY_TRADE_THRESHOLD - day_trade_count} more day trades to trigger PDT rule."
            )

        return {
            "is_pdt": is_pdt,
            "day_trades_count": day_trade_count,
            "lookback_days": lookback_days,
            "meets_equity_requirement": meets_equity,
            "status": status,
            "warnings": warnings,
            "recent_day_trades": recent_day_trades,
        }

    def calculate_after_tax_returns(
        self, gross_returns: list[float], tax_events: Optional[list[TaxEvent]] = None
    ) -> dict[str, Any]:
        """
        Calculate after-tax returns based on tax events.

        Args:
            gross_returns: List of gross returns (pre-tax)
            tax_events: List of TaxEvent objects (if None, uses self.tax_events)

        Returns:
            Dict with after-tax metrics
        """
        if tax_events is None:
            tax_events = self.tax_events

        if not tax_events:
            return {
                "gross_return": 0.0,
                "tax_liability": 0.0,
                "after_tax_return": 0.0,
                "tax_efficiency": 1.0,
                "short_term_gains": 0.0,
                "long_term_gains": 0.0,
                "short_term_losses": 0.0,
                "long_term_losses": 0.0,
            }

        # Calculate gains/losses by type
        short_term_gains = sum(
            e.gain_loss for e in tax_events if not e.is_long_term and e.gain_loss > 0
        )
        short_term_losses = abs(
            sum(e.gain_loss for e in tax_events if not e.is_long_term and e.gain_loss < 0)
        )
        long_term_gains = sum(e.gain_loss for e in tax_events if e.is_long_term and e.gain_loss > 0)
        long_term_losses = abs(
            sum(e.gain_loss for e in tax_events if e.is_long_term and e.gain_loss < 0)
        )

        # Net short-term and long-term
        net_short_term = short_term_gains - short_term_losses
        net_long_term = long_term_gains - long_term_losses

        # Calculate tax liability
        # Short-term gains taxed as ordinary income (up to 37%)
        short_term_tax = max(0, net_short_term * SHORT_TERM_TAX_RATE)
        # Long-term gains taxed at capital gains rate (up to 20%)
        long_term_tax = max(0, net_long_term * LONG_TERM_TAX_RATE)

        # Apply $3,000 capital loss deduction limit (if net losses)
        if net_short_term < 0:
            deductible_loss = min(abs(net_short_term), 3000.0)
            short_term_tax = -deductible_loss * SHORT_TERM_TAX_RATE  # Tax benefit from loss
        if net_long_term < 0:
            deductible_loss = min(abs(net_long_term), 3000.0)
            long_term_tax = -deductible_loss * LONG_TERM_TAX_RATE

        total_tax = short_term_tax + long_term_tax

        # Gross return
        gross_return = sum(e.gain_loss for e in tax_events)
        after_tax_return = gross_return - total_tax

        # Tax efficiency (after-tax / gross)
        tax_efficiency = (after_tax_return / gross_return) if gross_return != 0 else 1.0

        return {
            "gross_return": gross_return,
            "tax_liability": total_tax,
            "after_tax_return": after_tax_return,
            "tax_efficiency": tax_efficiency,
            "short_term_gains": short_term_gains,
            "long_term_gains": long_term_gains,
            "short_term_losses": short_term_losses,
            "long_term_losses": long_term_losses,
            "net_short_term": net_short_term,
            "net_long_term": net_long_term,
            "short_term_tax": short_term_tax,
            "long_term_tax": long_term_tax,
        }

    def get_tax_optimization_recommendations(
        self, current_equity: float, open_positions: list[dict[str, Any]]
    ) -> list[str]:
        """
        Generate tax optimization recommendations.

        Returns:
            List of actionable recommendations
        """
        recommendations = []

        # Check PDT status
        pdt_status = self.check_pdt_status(current_equity)
        if pdt_status["warnings"]:
            recommendations.extend(pdt_status["warnings"])

        # Check for wash sale opportunities
        recent_losses = [
            e
            for e in self.tax_events
            if e.gain_loss < 0 and (datetime.now() - e.sale_date).days <= WASH_SALE_WINDOW_DAYS
        ]
        if recent_losses:
            recommendations.append(
                f"⚠️ **WASH SALE WARNING**: {len(recent_losses)} recent losses. "
                f"Avoid repurchasing these symbols within 30 days: "
                f"{', '.join(set(e.symbol for e in recent_losses))}"
            )

        # Check holding periods for long-term qualification
        open_symbols = {pos.get("symbol") for pos in open_positions if pos.get("symbol")}
        for symbol in open_symbols:
            if symbol in self.tax_lots:
                for lot in self.tax_lots[symbol]:
                    days_held = (datetime.now() - lot.purchase_date).days
                    days_to_long_term = LONG_TERM_THRESHOLD_DAYS - days_held
                    if 0 < days_to_long_term <= 30:
                        recommendations.append(
                            f"💡 **TAX OPTIMIZATION**: {symbol} held {days_held} days. "
                            f"Hold {days_to_long_term} more days for long-term capital gains rate "
                            f"({LONG_TERM_TAX_RATE * 100:.0f}% vs {SHORT_TERM_TAX_RATE * 100:.0f}%)."
                        )

        # Tax-loss harvesting opportunities
        if len(self.tax_events) >= 5:
            year_to_date_gains = sum(e.gain_loss for e in self.tax_events if e.gain_loss > 0)
            year_to_date_losses = abs(sum(e.gain_loss for e in self.tax_events if e.gain_loss < 0))
            if year_to_date_gains > year_to_date_losses:
                net_gains = year_to_date_gains - year_to_date_losses
                recommendations.append(
                    f"💡 **TAX-LOSS HARVESTING**: ${net_gains:.2f} net gains YTD. "
                    f"Consider realizing losses to offset gains before year-end."
                )

        return recommendations

    def calculate_tax_aware_reward_adjustment(
        self, trade_event: TaxEvent, base_reward: float
    ) -> float:
        """
        Adjust RL reward function to account for tax implications.

        This should be integrated into the RL pipeline to optimize for after-tax returns.

        Args:
            trade_event: TaxEvent from the trade
            base_reward: Base reward from RL agent (pre-tax)

        Returns:
            Tax-adjusted reward
        """
        # Penalize short-term gains (higher tax rate)
        if not trade_event.is_long_term and trade_event.gain_loss > 0:
            # Reduce reward by tax difference (37% - 20% = 17%)
            tax_penalty = trade_event.gain_loss * (SHORT_TERM_TAX_RATE - LONG_TERM_TAX_RATE)
            adjusted_reward = base_reward - tax_penalty
        # Reward long-term gains (lower tax rate)
        elif trade_event.is_long_term and trade_event.gain_loss > 0:
            # Bonus for tax efficiency
            tax_bonus = trade_event.gain_loss * (SHORT_TERM_TAX_RATE - LONG_TERM_TAX_RATE)
            adjusted_reward = base_reward + tax_bonus
        # Penalize wash sales (losses can't be deducted)
        elif trade_event.is_wash_sale:
            adjusted_reward = base_reward - trade_event.wash_sale_adjustment
        else:
            adjusted_reward = base_reward

        return adjusted_reward

    def get_tax_summary(self) -> dict[str, Any]:
        """Get comprehensive tax summary for dashboard."""
        if not self.tax_events:
            return {
                "total_trades": 0,
                "total_gains": 0.0,
                "total_losses": 0.0,
                "net_gain_loss": 0.0,
                "short_term_count": 0,
                "long_term_count": 0,
                "wash_sale_count": 0,
                "day_trade_count": len(self.day_trades),
                "estimated_tax": 0.0,
                "after_tax_return": 0.0,
            }

        after_tax = self.calculate_after_tax_returns([])

        return {
            "total_trades": len(self.tax_events),
            "total_gains": after_tax["short_term_gains"] + after_tax["long_term_gains"],
            "total_losses": after_tax["short_term_losses"] + after_tax["long_term_losses"],
            "net_gain_loss": after_tax["gross_return"],
            "short_term_count": sum(1 for e in self.tax_events if not e.is_long_term),
            "long_term_count": sum(1 for e in self.tax_events if e.is_long_term),
            "wash_sale_count": sum(1 for e in self.tax_events if e.is_wash_sale),
            "day_trade_count": len(self.day_trades),
            "estimated_tax": after_tax["tax_liability"],
            "after_tax_return": after_tax["after_tax_return"],
            "tax_efficiency": after_tax["tax_efficiency"],
            "short_term_tax_rate": SHORT_TERM_TAX_RATE,
            "long_term_tax_rate": LONG_TERM_TAX_RATE,
        }
