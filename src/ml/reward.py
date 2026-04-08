"""
Composite reward function for iron condor RL training.

R = w1*R_return - w2*R_downside + w3*R_benchmark

Based on arXiv 2506.04358: Risk-Aware RL Reward for Financial Trading.
Phil Town Rule #1 encoded: downside risk has 2x weight of return.

This replaces raw P/L as the training signal for GRPO and future RL agents.
"""

import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

JOURNAL_FILE = Path(__file__).parent.parent.parent / "data" / "trade_journal.jsonl"

# Reward weights — loss avoidance > return maximization (Phil Town Rule #1)
W_RETURN = 1.0  # Reward for positive returns
W_DOWNSIDE = 2.0  # Penalty for downside risk (2x weight = loss aversion)
W_BENCHMARK = 0.5  # Reward for exceeding risk-free benchmark


def compute_trade_reward(
    pnl: float,
    credit: float,
    max_loss: float,
    dte_at_exit: int,
    dte_at_entry: int = 30,
    risk_free_rate: float = 0.05,
) -> dict:
    """Compute composite reward for a single trade.

    Args:
        pnl: Realized P/L in dollars
        credit: Entry credit per share
        max_loss: Maximum possible loss (wing_width * 100 - credit * 100)
        dte_at_exit: Days to expiration at exit
        dte_at_entry: Days to expiration at entry
        risk_free_rate: Annual risk-free rate for benchmark comparison

    Returns:
        dict with total_reward, components, and metadata
    """
    if max_loss == 0 or credit == 0:
        return {"total_reward": 0, "components": {}, "error": "zero max_loss or credit"}

    # 1. Return component: annualized return on risk
    holding_days = max(1, dte_at_entry - dte_at_exit)
    return_pct = pnl / max_loss  # Return on max risk
    annualized = return_pct * (365 / holding_days) if holding_days > 0 else 0
    r_return = min(annualized, 5.0)  # Cap at 500% annualized to prevent outlier skew

    # 2. Downside risk component: asymmetric penalty for losses
    # Sortino-inspired: only penalize negative returns, squared for severity
    if pnl < 0:
        loss_severity = (pnl / max_loss) ** 2  # Squared loss as fraction of max
        r_downside = loss_severity * (365 / holding_days)  # Annualized downside
    else:
        r_downside = 0.0

    # 3. Benchmark excess: did we beat holding cash?
    holding_years = holding_days / 365
    risk_free_return = max_loss * risk_free_rate * holding_years
    benchmark_excess = (pnl - risk_free_return) / max_loss
    r_benchmark = max(-1.0, min(1.0, benchmark_excess))  # Clamp

    # Composite reward
    total = W_RETURN * r_return - W_DOWNSIDE * r_downside + W_BENCHMARK * r_benchmark

    return {
        "total_reward": round(total, 4),
        "components": {
            "return": round(r_return, 4),
            "downside": round(r_downside, 4),
            "benchmark_excess": round(r_benchmark, 4),
        },
        "weights": {"w_return": W_RETURN, "w_downside": W_DOWNSIDE, "w_benchmark": W_BENCHMARK},
        "inputs": {
            "pnl": pnl,
            "credit": credit,
            "max_loss": max_loss,
            "holding_days": holding_days,
            "annualized_return_pct": round(annualized * 100, 1),
        },
    }


def compute_portfolio_reward(lookback_trades: int = 30) -> dict:
    """Compute aggregate reward across recent trades.

    Returns portfolio-level metrics: Sharpe-like ratio, win rate reward,
    average composite reward, and drawdown penalty.
    """
    if not JOURNAL_FILE.exists():
        return {"error": "no journal", "total_reward": 0}

    trades = []
    for line in JOURNAL_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            trades.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    trades = trades[-lookback_trades:]
    if not trades:
        return {"error": "no trades", "total_reward": 0}

    # Compute per-trade rewards
    rewards = []
    pnls = []
    for t in trades:
        credit = t.get("credit_per_share", 0.81)
        max_loss = 10.0 * 100 - credit * 100  # $10 wing width assumption
        r = compute_trade_reward(
            pnl=t.get("pnl", 0),
            credit=credit,
            max_loss=max_loss,
            dte_at_exit=t.get("dte_at_exit", 7),
        )
        rewards.append(r["total_reward"])
        pnls.append(t.get("pnl", 0))

    avg_reward = sum(rewards) / len(rewards)
    avg_pnl = sum(pnls) / len(pnls)
    win_rate = sum(1 for p in pnls if p > 0) / len(pnls)

    # Sharpe-like: mean reward / std reward
    if len(rewards) > 1:
        mean_r = sum(rewards) / len(rewards)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in rewards) / (len(rewards) - 1))
        sharpe = mean_r / std_r if std_r > 0 else 0
    else:
        sharpe = 0

    # Max drawdown from P/L series
    cumulative = []
    running = 0
    for p in pnls:
        running += p
        cumulative.append(running)
    peak = cumulative[0]
    max_dd = 0
    for c in cumulative:
        peak = max(peak, c)
        dd = peak - c
        max_dd = max(max_dd, dd)

    return {
        "total_reward": round(avg_reward, 4),
        "trade_count": len(trades),
        "avg_pnl": round(avg_pnl, 2),
        "win_rate": round(win_rate, 3),
        "sharpe_like": round(sharpe, 3),
        "max_drawdown": round(max_dd, 2),
        "per_trade_rewards": rewards,
    }
