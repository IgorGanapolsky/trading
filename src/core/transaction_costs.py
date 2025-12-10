"""
Transaction Cost Modeling Module.

This module provides realistic transaction cost modeling for backtesting
and live trading. It accounts for:
    - Bid-ask spread costs
    - Market impact (price movement from order execution)
    - Slippage (difference between expected and actual fill price)
    - Commission fees
    - Borrowing costs for short positions

Accurate cost modeling is critical for realistic P&L estimation.

Author: Trading System
Created: 2025-12-04
"""

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types with different cost profiles."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class AssetClass(Enum):
    """Asset classes with different cost characteristics."""

    US_EQUITY = "us_equity"
    ETF = "etf"
    OPTION = "option"
    CRYPTO = "crypto"
    FOREX = "forex"


@dataclass
class TransactionCost:
    """Breakdown of transaction costs for a single trade."""

    spread_cost: float  # Bid-ask spread cost
    market_impact: float  # Price impact from execution
    slippage: float  # Execution slippage
    commission: float  # Broker commission
    borrowing_cost: float  # For short positions
    total_cost: float  # Sum of all costs

    # As percentages of trade value
    spread_cost_pct: float
    market_impact_pct: float
    slippage_pct: float
    commission_pct: float
    borrowing_cost_pct: float
    total_cost_pct: float


@dataclass
class CostModelParams:
    """Parameters for cost modeling."""

    # Spread model
    base_spread_bps: float = 2.0  # Base spread in basis points
    volatility_multiplier: float = 0.5  # Spread increases with volatility

    # Market impact model (square-root model)
    impact_coefficient: float = 0.1  # Kyle's lambda equivalent
    participation_rate: float = 0.1  # Fraction of ADV we represent

    # Slippage model
    base_slippage_bps: float = 1.0  # Base slippage
    volatility_slippage_mult: float = 0.3  # Slippage increases with volatility

    # Commissions
    commission_per_share: float = 0.0  # Per-share commission (0 for Alpaca)
    min_commission: float = 0.0  # Minimum commission per trade

    # Short selling
    borrow_rate_annual: float = 0.02  # 2% annual borrow rate


class TransactionCostModel:
    """
    Comprehensive transaction cost model.

    Implements realistic cost estimation using:
    1. Spread model: Bid-ask spread based on volatility and liquidity
    2. Impact model: Square-root market impact model
    3. Slippage model: Execution slippage based on volatility
    4. Commission model: Broker fees
    5. Borrow model: Short selling costs
    """

    def __init__(
        self,
        asset_class: AssetClass = AssetClass.US_EQUITY,
        params: CostModelParams | None = None,
    ):
        """
        Initialize transaction cost model.

        Args:
            asset_class: Asset class for cost estimation
            params: Custom cost model parameters
        """
        self.asset_class = asset_class
        self.params = params or self._get_default_params(asset_class)

        logger.info(f"Initialized cost model for {asset_class.value}")

    def _get_default_params(self, asset_class: AssetClass) -> CostModelParams:
        """Get default parameters based on asset class."""
        if asset_class == AssetClass.US_EQUITY:
            return CostModelParams(
                base_spread_bps=2.0,
                impact_coefficient=0.1,
                base_slippage_bps=1.0,
                commission_per_share=0.0,  # Free at Alpaca
            )
        elif asset_class == AssetClass.ETF:
            return CostModelParams(
                base_spread_bps=1.0,  # Tighter spreads
                impact_coefficient=0.05,  # Less impact
                base_slippage_bps=0.5,
                commission_per_share=0.0,
            )
        elif asset_class == AssetClass.OPTION:
            return CostModelParams(
                base_spread_bps=20.0,  # Wide spreads
                impact_coefficient=0.3,  # High impact
                base_slippage_bps=5.0,
                commission_per_share=0.0,
            )
        elif asset_class == AssetClass.CRYPTO:
            return CostModelParams(
                base_spread_bps=5.0,
                impact_coefficient=0.2,
                base_slippage_bps=3.0,
                commission_per_share=0.0,
            )
        else:  # FOREX
            return CostModelParams(
                base_spread_bps=0.5,  # Very tight
                impact_coefficient=0.02,
                base_slippage_bps=0.3,
                commission_per_share=0.0,
            )

    def estimate_cost(
        self,
        symbol: str,
        quantity: float,
        price: float,
        order_type: OrderType = OrderType.MARKET,
        is_buy: bool = True,
        volatility: float | None = None,
        avg_daily_volume: float | None = None,
        holding_days: int = 0,
    ) -> TransactionCost:
        """
        Estimate transaction costs for a trade.

        Args:
            symbol: Trading symbol
            quantity: Number of shares/contracts
            price: Expected execution price
            order_type: Type of order
            is_buy: True for buy, False for sell
            volatility: Annualized volatility (optional, uses default if None)
            avg_daily_volume: Average daily volume for impact calculation
            holding_days: Days position held (for borrow cost calculation)

        Returns:
            TransactionCost with detailed cost breakdown
        """
        trade_value = abs(quantity * price)

        if trade_value == 0:
            return TransactionCost(
                spread_cost=0.0,
                market_impact=0.0,
                slippage=0.0,
                commission=0.0,
                borrowing_cost=0.0,
                total_cost=0.0,
                spread_cost_pct=0.0,
                market_impact_pct=0.0,
                slippage_pct=0.0,
                commission_pct=0.0,
                borrowing_cost_pct=0.0,
                total_cost_pct=0.0,
            )

        # Use default volatility if not provided
        vol = volatility if volatility is not None else 0.20  # 20% annualized default

        # 1. Calculate spread cost
        spread_bps = self._calculate_spread(vol)
        spread_cost = trade_value * (spread_bps / 10000) / 2  # Half-spread for one-way

        # 2. Calculate market impact
        if avg_daily_volume and avg_daily_volume > 0:
            market_impact = self._calculate_market_impact(quantity, price, avg_daily_volume, vol)
        else:
            # Default impact based on trade value
            impact_bps = self.params.impact_coefficient * np.sqrt(trade_value / 100000) * 10
            market_impact = trade_value * (impact_bps / 10000)

        # 3. Calculate slippage
        slippage = self._calculate_slippage(trade_value, vol, order_type)

        # 4. Calculate commission
        commission = max(
            self.params.min_commission,
            abs(quantity) * self.params.commission_per_share,
        )

        # 5. Calculate borrowing cost (for short positions)
        borrowing_cost = 0.0
        if not is_buy and holding_days > 0:
            borrowing_cost = self._calculate_borrow_cost(trade_value, holding_days)

        # Total cost
        total_cost = spread_cost + market_impact + slippage + commission + borrowing_cost

        return TransactionCost(
            spread_cost=spread_cost,
            market_impact=market_impact,
            slippage=slippage,
            commission=commission,
            borrowing_cost=borrowing_cost,
            total_cost=total_cost,
            spread_cost_pct=spread_cost / trade_value * 100 if trade_value > 0 else 0,
            market_impact_pct=market_impact / trade_value * 100 if trade_value > 0 else 0,
            slippage_pct=slippage / trade_value * 100 if trade_value > 0 else 0,
            commission_pct=commission / trade_value * 100 if trade_value > 0 else 0,
            borrowing_cost_pct=borrowing_cost / trade_value * 100 if trade_value > 0 else 0,
            total_cost_pct=total_cost / trade_value * 100 if trade_value > 0 else 0,
        )

    def _calculate_spread(self, volatility: float) -> float:
        """
        Calculate bid-ask spread in basis points.

        Spread increases with volatility (market makers widen spreads).
        """
        base = self.params.base_spread_bps
        vol_adjustment = self.params.volatility_multiplier * (
            volatility / 0.20
        )  # Normalize to 20% vol

        return base * (1 + vol_adjustment)

    def _calculate_market_impact(
        self,
        quantity: float,
        price: float,
        avg_daily_volume: float,
        volatility: float,
    ) -> float:
        """
        Calculate market impact using square-root model.

        Impact = coefficient * volatility * sqrt(quantity / ADV)

        This is based on the Almgren-Chriss model.
        """
        if avg_daily_volume <= 0:
            return 0.0

        trade_value = abs(quantity * price)
        participation = abs(quantity) / avg_daily_volume

        # Square-root impact model
        impact_pct = self.params.impact_coefficient * volatility * np.sqrt(participation)

        return trade_value * impact_pct

    def _calculate_slippage(
        self,
        trade_value: float,
        volatility: float,
        order_type: OrderType,
    ) -> float:
        """
        Calculate execution slippage.

        Market orders have higher slippage than limit orders.
        """
        base_bps = self.params.base_slippage_bps
        vol_adjustment = self.params.volatility_slippage_mult * (volatility / 0.20)

        slippage_bps = base_bps * (1 + vol_adjustment)

        # Order type adjustments
        if order_type == OrderType.LIMIT:
            slippage_bps *= 0.3  # Much less slippage for limit orders
        elif order_type == OrderType.STOP:
            slippage_bps *= 2.0  # Stop orders often execute at worse prices

        return trade_value * (slippage_bps / 10000)

    def _calculate_borrow_cost(self, trade_value: float, holding_days: int) -> float:
        """Calculate borrowing cost for short positions."""
        daily_rate = self.params.borrow_rate_annual / 252
        return trade_value * daily_rate * holding_days

    def estimate_round_trip(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        holding_days: int = 1,
        volatility: float | None = None,
        avg_daily_volume: float | None = None,
    ) -> tuple[float, TransactionCost, TransactionCost]:
        """
        Estimate total round-trip transaction costs.

        Args:
            symbol: Trading symbol
            quantity: Number of shares (positive for long, negative for short)
            entry_price: Entry price
            exit_price: Exit price
            holding_days: Days position was held
            volatility: Annualized volatility
            avg_daily_volume: Average daily volume

        Returns:
            Tuple of (total_cost, entry_cost, exit_cost)
        """
        is_long = quantity > 0

        entry_cost = self.estimate_cost(
            symbol=symbol,
            quantity=abs(quantity),
            price=entry_price,
            is_buy=is_long,
            volatility=volatility,
            avg_daily_volume=avg_daily_volume,
            holding_days=0,  # No borrow cost at entry
        )

        exit_cost = self.estimate_cost(
            symbol=symbol,
            quantity=abs(quantity),
            price=exit_price,
            is_buy=not is_long,  # Opposite side to close
            volatility=volatility,
            avg_daily_volume=avg_daily_volume,
            holding_days=holding_days if not is_long else 0,
        )

        total = entry_cost.total_cost + exit_cost.total_cost

        return total, entry_cost, exit_cost

    def adjust_returns(
        self,
        trades: list[dict],
        price_data: pd.DataFrame | None = None,
    ) -> list[dict]:
        """
        Adjust trade returns for transaction costs.

        Args:
            trades: List of trade dictionaries with entry/exit prices
            price_data: Optional price data for volatility calculation

        Returns:
            Trades with adjusted returns
        """
        adjusted_trades = []

        for trade in trades:
            trade_copy = trade.copy()

            symbol = trade.get("symbol", "SPY")
            quantity = trade.get("quantity", 1)
            entry_price = trade.get("entry_price", trade.get("price", 100))
            exit_price = trade.get("exit_price", entry_price)
            holding_days = trade.get("holding_days", 1)

            # Calculate volatility from price data if available
            vol = None
            if price_data is not None and symbol in price_data.columns:
                returns = price_data[symbol].pct_change().dropna()
                if len(returns) > 20:
                    vol = returns.std() * np.sqrt(252)

            total_cost, _, _ = self.estimate_round_trip(
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                exit_price=exit_price,
                holding_days=holding_days,
                volatility=vol,
            )

            # Adjust P&L
            original_pnl = trade.get("pnl", (exit_price - entry_price) * quantity)
            adjusted_pnl = original_pnl - total_cost

            trade_copy["original_pnl"] = original_pnl
            trade_copy["transaction_costs"] = total_cost
            trade_copy["adjusted_pnl"] = adjusted_pnl

            # Adjust return percentage
            trade_value = abs(quantity * entry_price)
            if trade_value > 0:
                trade_copy["original_return_pct"] = (original_pnl / trade_value) * 100
                trade_copy["adjusted_return_pct"] = (adjusted_pnl / trade_value) * 100
                trade_copy["cost_impact_pct"] = (total_cost / trade_value) * 100

            adjusted_trades.append(trade_copy)

        return adjusted_trades


def calculate_breakeven_edge(
    trades_per_year: int = 250,
    avg_trade_value: float = 10000.0,
    cost_model: TransactionCostModel | None = None,
) -> float:
    """
    Calculate the minimum edge needed to break even after costs.

    Args:
        trades_per_year: Expected number of trades per year
        avg_trade_value: Average trade value
        cost_model: Transaction cost model to use

    Returns:
        Minimum required return per trade (in percent)
    """
    if cost_model is None:
        cost_model = TransactionCostModel(AssetClass.US_EQUITY)

    # Estimate average round-trip cost
    cost = cost_model.estimate_cost(
        symbol="SPY",
        quantity=avg_trade_value / 100,  # Assume $100 stock
        price=100,
    )

    # Double for round-trip
    round_trip_cost_pct = cost.total_cost_pct * 2

    return round_trip_cost_pct


def generate_cost_report(
    trades: list[dict],
    cost_model: TransactionCostModel | None = None,
) -> str:
    """
    Generate transaction cost analysis report.

    Args:
        trades: List of trades to analyze
        cost_model: Cost model to use

    Returns:
        Formatted report string
    """
    if cost_model is None:
        cost_model = TransactionCostModel(AssetClass.US_EQUITY)

    adjusted = cost_model.adjust_returns(trades)

    total_original_pnl = sum(t.get("original_pnl", 0) for t in adjusted)
    total_costs = sum(t.get("transaction_costs", 0) for t in adjusted)
    total_adjusted_pnl = sum(t.get("adjusted_pnl", 0) for t in adjusted)

    report = []
    report.append("=" * 60)
    report.append("TRANSACTION COST ANALYSIS")
    report.append("=" * 60)
    report.append(f"\nTrades Analyzed: {len(trades)}")
    report.append("\nP&L Summary:")
    report.append(f"  Gross P&L: ${total_original_pnl:,.2f}")
    report.append(f"  Transaction Costs: ${total_costs:,.2f}")
    report.append(f"  Net P&L: ${total_adjusted_pnl:,.2f}")

    if total_original_pnl != 0:
        cost_drag = (total_costs / abs(total_original_pnl)) * 100
        report.append(f"  Cost as % of Gross: {cost_drag:.1f}%")

    # Per-trade averages
    if len(adjusted) > 0:
        avg_cost = total_costs / len(adjusted)
        avg_cost_pct = np.mean([t.get("cost_impact_pct", 0) for t in adjusted])

        report.append("\nPer-Trade Averages:")
        report.append(f"  Average Cost: ${avg_cost:.2f}")
        report.append(f"  Average Cost %: {avg_cost_pct:.3f}%")

    report.append("\n" + "=" * 60)

    return "\n".join(report)
