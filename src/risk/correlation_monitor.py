"""Cross-Strategy Correlation Monitor.

Monitors correlation across ALL positions from ALL strategy tiers to prevent
hidden concentration risk. This is the critical gap identified in the Dec 3
revenue strategy analysis.

Key Features:
- Calculates correlation matrix for current portfolio
- Blocks trades that would increase average correlation above threshold
- Sector/theme clustering detection
- Real-time portfolio heat calculation

Integration Points:
- UnifiedRiskManager.validate_trade() - pre-trade correlation check
- RiskAgent.analyze() - correlation context for LLM decisions
- Circuit breakers - halt if correlation spike detected
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Sector mappings for theme/sector concentration detection
SECTOR_MAP = {
    # Tech / Growth
    "AAPL": "tech",
    "MSFT": "tech",
    "GOOGL": "tech",
    "GOOG": "tech",
    "AMZN": "tech",
    "META": "tech",
    "NVDA": "tech",
    "AMD": "tech",
    "INTC": "tech",
    "CRM": "tech",
    "ADBE": "tech",
    "NFLX": "tech",
    "TSLA": "tech",
    # ETFs
    "SPY": "broad_market",
    "QQQ": "tech_etf",
    "VOO": "broad_market",
    "IWM": "small_cap",
    "DIA": "broad_market",
    # Financials
    "JPM": "financials",
    "BAC": "financials",
    "GS": "financials",
    "MS": "financials",
    "V": "financials",
    "MA": "financials",
    # Healthcare
    "JNJ": "healthcare",
    "UNH": "healthcare",
    "PFE": "healthcare",
    "ABBV": "healthcare",
    "MRK": "healthcare",
    # Energy
    "XOM": "energy",
    "CVX": "energy",
    "COP": "energy",
    # Consumer
    "WMT": "consumer",
    "COST": "consumer",
    "HD": "consumer",
    "NKE": "consumer",
    # Bonds/Treasuries
    "TLT": "bonds",
    "IEF": "bonds",
    "SHY": "bonds",
    "GOVT": "bonds",
    "BND": "bonds",
    "ZROZ": "bonds",
    # Crypto proxies
    "BITO": "crypto",
    "GBTC": "crypto",
    # Safe havens
    "GLD": "safe_haven",
    "SLV": "safe_haven",
    "VNQ": "real_estate",
    "SCHD": "dividend",
}


@dataclass
class CorrelationAlert:
    """Alert raised when correlation threshold breached."""

    level: str  # INFO, WARNING, CRITICAL
    message: str
    current_avg_correlation: float
    threshold: float
    problematic_pairs: list[tuple[str, str, float]]
    timestamp: datetime


@dataclass
class CorrelationCheckResult:
    """Result of pre-trade correlation check."""

    approved: bool
    reason: str
    current_avg_correlation: float
    projected_avg_correlation: float
    sector_exposure: dict[str, float]
    high_correlation_pairs: list[tuple[str, str, float]]
    recommendation: str  # APPROVE, REDUCE, REJECT


class CrossStrategyCorrelationMonitor:
    """
    Monitors correlation across all strategy tiers to prevent hidden concentration.

    The Dec 3 analysis identified this as critical gap:
    - Each tier (Core, Growth, IPO, Options, Crypto) operates independently
    - No check if "Core" MACD buy + "Growth" momentum buy on same underlying
    - Could build 2x concentrated positions without detection

    This monitor solves that by:
    1. Maintaining rolling correlation matrix of all held positions
    2. Checking proposed trades against existing portfolio correlation
    3. Blocking trades that would increase avg correlation above threshold
    4. Alerting on sector/theme concentration
    """

    def __init__(
        self,
        max_avg_correlation: float = 0.65,
        max_pair_correlation: float = 0.85,
        max_sector_exposure: float = 0.40,
        lookback_days: int = 60,
        correlation_decay_factor: float = 0.94,  # EWMA decay
    ):
        """
        Initialize correlation monitor.

        Args:
            max_avg_correlation: Maximum average portfolio correlation (default 0.65)
            max_pair_correlation: Maximum correlation between any two positions (0.85)
            max_sector_exposure: Maximum exposure to any single sector (40%)
            lookback_days: Days of history for correlation calculation
            correlation_decay_factor: EWMA decay for recent-weighted correlation
        """
        self.max_avg_correlation = max_avg_correlation
        self.max_pair_correlation = max_pair_correlation
        self.max_sector_exposure = max_sector_exposure
        self.lookback_days = lookback_days
        self.correlation_decay_factor = correlation_decay_factor

        # Cache for correlation matrix (recomputed daily)
        self._correlation_cache: pd.DataFrame | None = None
        self._cache_timestamp: datetime | None = None
        self._cache_symbols: list[str] = []

        # Alert history
        self._alerts: list[CorrelationAlert] = []

    def check_trade(
        self,
        proposed_symbol: str,
        proposed_amount: float,
        current_positions: dict[str, float],
        historical_returns: pd.DataFrame | None = None,
    ) -> CorrelationCheckResult:
        """
        Check if proposed trade would breach correlation thresholds.

        Args:
            proposed_symbol: Symbol to buy
            proposed_amount: Dollar amount to allocate
            current_positions: Dict of {symbol: dollar_value} for current positions
            historical_returns: DataFrame of daily returns (symbol columns, date index)
                               If None, will fetch from cache or return approval

        Returns:
            CorrelationCheckResult with approval decision and reasoning
        """
        # If no current positions, any trade is approved
        if not current_positions:
            return CorrelationCheckResult(
                approved=True,
                reason="First position - no correlation risk",
                current_avg_correlation=0.0,
                projected_avg_correlation=0.0,
                sector_exposure={},
                high_correlation_pairs=[],
                recommendation="APPROVE",
            )

        # Check sector exposure first (fast check)
        sector_result = self._check_sector_exposure(
            proposed_symbol, proposed_amount, current_positions
        )
        if not sector_result["approved"]:
            return CorrelationCheckResult(
                approved=False,
                reason=sector_result["reason"],
                current_avg_correlation=0.0,
                projected_avg_correlation=0.0,
                sector_exposure=sector_result["exposure"],
                high_correlation_pairs=[],
                recommendation="REJECT",
            )

        # If no historical returns provided, use heuristic based on sector
        if historical_returns is None or historical_returns.empty:
            return self._heuristic_correlation_check(
                proposed_symbol, proposed_amount, current_positions
            )

        # Calculate current portfolio correlation
        current_symbols = list(current_positions.keys())
        relevant_symbols = current_symbols + [proposed_symbol]

        # Filter returns to relevant symbols
        available_symbols = [s for s in relevant_symbols if s in historical_returns.columns]
        if len(available_symbols) < 2:
            return CorrelationCheckResult(
                approved=True,
                reason="Insufficient data for correlation calculation - proceeding with caution",
                current_avg_correlation=0.0,
                projected_avg_correlation=0.0,
                sector_exposure=sector_result["exposure"],
                high_correlation_pairs=[],
                recommendation="APPROVE",
            )

        returns_subset = historical_returns[available_symbols].dropna()

        if len(returns_subset) < 20:  # Need at least 20 days
            return CorrelationCheckResult(
                approved=True,
                reason="Insufficient history for correlation - proceeding with caution",
                current_avg_correlation=0.0,
                projected_avg_correlation=0.0,
                sector_exposure=sector_result["exposure"],
                high_correlation_pairs=[],
                recommendation="APPROVE",
            )

        # Calculate correlation matrix with exponential decay (recent data weighted more)
        corr_matrix = self._calculate_ewma_correlation(returns_subset)

        # Current average correlation (without proposed)
        current_only = [s for s in current_symbols if s in corr_matrix.columns]
        current_avg_corr = self._calculate_avg_correlation(corr_matrix, current_only)

        # Projected average correlation (with proposed)
        all_symbols = list(set(current_only + [proposed_symbol]))
        if proposed_symbol in corr_matrix.columns:
            projected_avg_corr = self._calculate_avg_correlation(corr_matrix, all_symbols)
        else:
            # Symbol not in our data - use sector-based estimate
            projected_avg_corr = current_avg_corr + 0.05  # Conservative estimate

        # Find high correlation pairs
        high_corr_pairs = []
        if proposed_symbol in corr_matrix.columns:
            for existing in current_only:
                if existing in corr_matrix.columns:
                    pair_corr = corr_matrix.loc[proposed_symbol, existing]
                    if abs(pair_corr) > self.max_pair_correlation:
                        high_corr_pairs.append((proposed_symbol, existing, pair_corr))

        # Decision logic
        if projected_avg_corr > self.max_avg_correlation:
            return CorrelationCheckResult(
                approved=False,
                reason=f"Trade would increase avg correlation to {projected_avg_corr:.2f} "
                f"(threshold: {self.max_avg_correlation:.2f})",
                current_avg_correlation=current_avg_corr,
                projected_avg_correlation=projected_avg_corr,
                sector_exposure=sector_result["exposure"],
                high_correlation_pairs=high_corr_pairs,
                recommendation="REJECT",
            )

        if high_corr_pairs:
            # Has high correlation with existing position - warn but may allow reduced size
            worst_pair = max(high_corr_pairs, key=lambda x: abs(x[2]))
            return CorrelationCheckResult(
                approved=False,
                reason=f"High correlation ({worst_pair[2]:.2f}) with existing position {worst_pair[1]}",
                current_avg_correlation=current_avg_corr,
                projected_avg_correlation=projected_avg_corr,
                sector_exposure=sector_result["exposure"],
                high_correlation_pairs=high_corr_pairs,
                recommendation="REDUCE",  # Allow at 50% size
            )

        # Check if correlation is increasing significantly
        correlation_increase = projected_avg_corr - current_avg_corr
        if correlation_increase > 0.10:  # 10% increase is notable
            return CorrelationCheckResult(
                approved=True,
                reason=f"Trade approved but increases correlation by {correlation_increase:.2f}",
                current_avg_correlation=current_avg_corr,
                projected_avg_correlation=projected_avg_corr,
                sector_exposure=sector_result["exposure"],
                high_correlation_pairs=high_corr_pairs,
                recommendation="APPROVE",
            )

        return CorrelationCheckResult(
            approved=True,
            reason="Trade within correlation limits",
            current_avg_correlation=current_avg_corr,
            projected_avg_correlation=projected_avg_corr,
            sector_exposure=sector_result["exposure"],
            high_correlation_pairs=high_corr_pairs,
            recommendation="APPROVE",
        )

    def _check_sector_exposure(
        self,
        proposed_symbol: str,
        proposed_amount: float,
        current_positions: dict[str, float],
    ) -> dict[str, Any]:
        """Check if proposed trade breaches sector concentration limits."""
        # Calculate current sector exposure
        total_value = sum(current_positions.values()) + proposed_amount
        sector_exposure: dict[str, float] = {}

        for symbol, value in current_positions.items():
            sector = SECTOR_MAP.get(symbol, "other")
            sector_exposure[sector] = sector_exposure.get(sector, 0) + value

        # Add proposed position
        proposed_sector = SECTOR_MAP.get(proposed_symbol, "other")
        sector_exposure[proposed_sector] = sector_exposure.get(proposed_sector, 0) + proposed_amount

        # Convert to percentages
        sector_pct = {k: v / total_value for k, v in sector_exposure.items()}

        # Check thresholds
        for sector, pct in sector_pct.items():
            if pct > self.max_sector_exposure:
                return {
                    "approved": False,
                    "reason": f"Sector '{sector}' exposure would be {pct:.1%} "
                    f"(max: {self.max_sector_exposure:.1%})",
                    "exposure": sector_pct,
                }

        return {"approved": True, "reason": "Sector exposure within limits", "exposure": sector_pct}

    def _calculate_ewma_correlation(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Calculate exponentially weighted correlation matrix."""
        # Apply exponential weights (recent data more important)
        weights = np.array(
            [self.correlation_decay_factor**i for i in range(len(returns) - 1, -1, -1)]
        )
        weights = weights / weights.sum()

        # Weighted covariance calculation
        weighted_returns = returns.values * weights[:, np.newaxis]
        weighted_means = weighted_returns.sum(axis=0)

        centered = returns.values - weighted_means
        weighted_cov = (centered.T * weights) @ centered

        # Convert to correlation
        std_devs = np.sqrt(np.diag(weighted_cov))
        std_outer = np.outer(std_devs, std_devs)
        std_outer[std_outer == 0] = 1  # Avoid division by zero

        corr_matrix = weighted_cov / std_outer

        return pd.DataFrame(corr_matrix, index=returns.columns, columns=returns.columns)

    def _calculate_avg_correlation(self, corr_matrix: pd.DataFrame, symbols: list[str]) -> float:
        """Calculate average pairwise correlation for given symbols."""
        if len(symbols) < 2:
            return 0.0

        valid_symbols = [s for s in symbols if s in corr_matrix.columns]
        if len(valid_symbols) < 2:
            return 0.0

        subset = corr_matrix.loc[valid_symbols, valid_symbols]

        # Get upper triangle (excluding diagonal)
        mask = np.triu(np.ones_like(subset, dtype=bool), k=1)
        correlations = subset.values[mask]

        return float(np.mean(np.abs(correlations))) if len(correlations) > 0 else 0.0

    def _heuristic_correlation_check(
        self,
        proposed_symbol: str,
        proposed_amount: float,
        current_positions: dict[str, float],
    ) -> CorrelationCheckResult:
        """
        Heuristic correlation check when no historical data available.
        Uses sector-based assumptions.
        """
        proposed_sector = SECTOR_MAP.get(proposed_symbol, "other")

        # Check for same-sector positions (high correlation likely)
        same_sector_positions = []
        for symbol in current_positions:
            if SECTOR_MAP.get(symbol, "other") == proposed_sector:
                same_sector_positions.append(symbol)

        if len(same_sector_positions) >= 2:
            return CorrelationCheckResult(
                approved=False,
                reason=f"Already have {len(same_sector_positions)} positions in '{proposed_sector}' sector",
                current_avg_correlation=0.6,  # Estimated
                projected_avg_correlation=0.7,  # Estimated higher
                sector_exposure={},
                high_correlation_pairs=[
                    (proposed_symbol, s, 0.7) for s in same_sector_positions[:2]
                ],
                recommendation="REJECT",
            )

        if len(same_sector_positions) == 1:
            return CorrelationCheckResult(
                approved=True,
                reason=f"One existing position in '{proposed_sector}' - proceed with reduced size",
                current_avg_correlation=0.5,
                projected_avg_correlation=0.6,
                sector_exposure={},
                high_correlation_pairs=[(proposed_symbol, same_sector_positions[0], 0.65)],
                recommendation="REDUCE",
            )

        return CorrelationCheckResult(
            approved=True,
            reason="No same-sector positions - correlation risk low",
            current_avg_correlation=0.4,
            projected_avg_correlation=0.45,
            sector_exposure={},
            high_correlation_pairs=[],
            recommendation="APPROVE",
        )

    def get_portfolio_heat(self, positions: dict[str, float]) -> dict[str, Any]:
        """
        Calculate overall portfolio 'heat' - a composite risk metric.

        Returns:
            Dict with:
            - heat_score: 0-100 (higher = more concentrated/correlated)
            - sector_concentration: Herfindahl index of sector exposure
            - largest_position_pct: Largest single position as % of total
            - avg_correlation: Average pairwise correlation (estimated if no data)
        """
        if not positions:
            return {
                "heat_score": 0,
                "sector_concentration": 0,
                "largest_position_pct": 0,
                "avg_correlation": 0,
                "status": "COOL",
            }

        total_value = sum(positions.values())
        position_pcts = {k: v / total_value for k, v in positions.items()}

        # Largest position
        largest_pct = max(position_pcts.values())

        # Sector concentration (Herfindahl-Hirschman Index)
        sector_values: dict[str, float] = {}
        for symbol, value in positions.items():
            sector = SECTOR_MAP.get(symbol, "other")
            sector_values[sector] = sector_values.get(sector, 0) + value

        sector_pcts = [v / total_value for v in sector_values.values()]
        hhi = sum(p**2 for p in sector_pcts)

        # Estimate correlation based on sector mix
        tech_weight = (
            sector_values.get("tech", 0) + sector_values.get("tech_etf", 0)
        ) / total_value
        bond_weight = sector_values.get("bonds", 0) / total_value

        # Tech-heavy = higher correlation, bonds = lower
        est_correlation = 0.4 + (tech_weight * 0.3) - (bond_weight * 0.2)
        est_correlation = max(0.2, min(0.9, est_correlation))

        # Composite heat score (0-100)
        heat_score = (
            largest_pct * 100 * 0.3  # Position concentration
            + hhi * 100 * 0.3  # Sector concentration
            + est_correlation * 100 * 0.4  # Estimated correlation
        )

        status = "COOL" if heat_score < 40 else "WARM" if heat_score < 60 else "HOT"

        return {
            "heat_score": round(heat_score, 1),
            "sector_concentration": round(hhi, 3),
            "largest_position_pct": round(largest_pct * 100, 1),
            "avg_correlation": round(est_correlation, 2),
            "status": status,
            "sector_breakdown": {
                k: round(v / total_value * 100, 1) for k, v in sector_values.items()
            },
        }

    def generate_alert(
        self,
        positions: dict[str, float],
        historical_returns: pd.DataFrame | None = None,
    ) -> CorrelationAlert | None:
        """
        Check current portfolio and generate alert if thresholds breached.

        Returns:
            CorrelationAlert if threshold breached, None otherwise
        """
        if len(positions) < 2:
            return None

        heat = self.get_portfolio_heat(positions)

        if heat["heat_score"] > 70:
            level = "CRITICAL"
            message = (
                f"Portfolio heat CRITICAL ({heat['heat_score']:.0f}/100) - reduce concentration"
            )
        elif heat["heat_score"] > 55:
            level = "WARNING"
            message = f"Portfolio heat elevated ({heat['heat_score']:.0f}/100) - monitor closely"
        else:
            return None

        alert = CorrelationAlert(
            level=level,
            message=message,
            current_avg_correlation=heat["avg_correlation"],
            threshold=self.max_avg_correlation,
            problematic_pairs=[],  # Would populate with real correlation data
            timestamp=datetime.now(),
        )

        self._alerts.append(alert)
        logger.warning(f"[CORRELATION] {level}: {message}")

        return alert


# Singleton instance for easy import
_correlation_monitor: CrossStrategyCorrelationMonitor | None = None


def get_correlation_monitor() -> CrossStrategyCorrelationMonitor:
    """Get or create the global correlation monitor instance."""
    global _correlation_monitor
    if _correlation_monitor is None:
        _correlation_monitor = CrossStrategyCorrelationMonitor()
    return _correlation_monitor
