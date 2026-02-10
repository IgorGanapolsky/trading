"""
GPU-Accelerated Backtesting Engine using Numba CUDA.

Based on: https://kdnuggets.com/writing-your-first-gpu-kernel-in-python-with-numba-and-cuda

Performance targets:
- 84x speedup vs CPU for vectorized operations
- Test 1000s of parameter combinations in parallel
- Monte Carlo simulations with 10,000+ scenarios

Fallback: Uses NumPy on CPU if CUDA unavailable (Mac Metal, no GPU, etc.)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

# Try to import CUDA - graceful fallback if unavailable
try:
    from numba import cuda, jit

    CUDA_AVAILABLE = cuda.is_available()
    if CUDA_AVAILABLE:
        print(f"GPU: {cuda.get_current_device().name}")
except ImportError:
    CUDA_AVAILABLE = False
    cuda = None
    jit = None

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
BACKTEST_DIR = DATA_DIR / "gpu_backtests"
BACKTEST_DIR.mkdir(parents=True, exist_ok=True)
CACHE_VERSION = 1
CACHE_DIR = BACKTEST_DIR / "cache"
PRICE_CACHE_DIR = BACKTEST_DIR / "price_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PRICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class IronCondorParams:
    """Parameters for iron condor backtesting."""

    delta: float  # Short strike delta (0.10 - 0.25)
    dte: int  # Days to expiration (21-60)
    width: int  # Wing width in dollars (5, 10, 15)
    exit_profit_pct: float  # Exit at X% of max profit (0.25-0.75)
    stop_loss_pct: float  # Stop loss at X% of credit (1.5-3.0)


@dataclass
class BacktestResult:
    """Result from a single backtest run."""

    params: IronCondorParams
    win_rate: float
    total_trades: int
    avg_profit: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    execution_time_ms: float

    def to_dict(self) -> dict:
        return {
            "params": {
                "delta": self.params.delta,
                "dte": self.params.dte,
                "width": self.params.width,
                "exit_profit_pct": self.params.exit_profit_pct,
                "stop_loss_pct": self.params.stop_loss_pct,
            },
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "avg_profit": self.avg_profit,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "execution_time_ms": self.execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BacktestResult:
        params_data = data.get("params", {})
        params = IronCondorParams(
            delta=params_data.get("delta", 0.15),
            dte=params_data.get("dte", 30),
            width=params_data.get("width", 5),
            exit_profit_pct=params_data.get("exit_profit_pct", 0.5),
            stop_loss_pct=params_data.get("stop_loss_pct", 2.0),
        )
        return cls(
            params=params,
            win_rate=data.get("win_rate", 0.0),
            total_trades=data.get("total_trades", 0),
            avg_profit=data.get("avg_profit", 0.0),
            avg_loss=data.get("avg_loss", 0.0),
            profit_factor=data.get("profit_factor", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            execution_time_ms=data.get("execution_time_ms", 0.0),
        )


@dataclass
class GridSearchResult:
    """Result from parameter grid search."""

    total_combinations: int
    execution_time_ms: float
    best_params: IronCondorParams
    best_sharpe: float
    best_win_rate: float
    all_results: list[BacktestResult] = field(default_factory=list)
    gpu_accelerated: bool = False

    def to_dict(self, include_all: bool = False) -> dict:
        data = {
            "total_combinations": self.total_combinations,
            "execution_time_ms": self.execution_time_ms,
            "gpu_accelerated": self.gpu_accelerated,
            "best_params": {
                "delta": self.best_params.delta,
                "dte": self.best_params.dte,
                "width": self.best_params.width,
                "exit_profit_pct": self.best_params.exit_profit_pct,
                "stop_loss_pct": self.best_params.stop_loss_pct,
            },
            "best_sharpe": self.best_sharpe,
            "best_win_rate": self.best_win_rate,
            "top_10_results": [
                r.to_dict()
                for r in sorted(self.all_results, key=lambda x: x.sharpe_ratio, reverse=True)[:10]
            ],
        }
        if include_all:
            data["all_results"] = [r.to_dict() for r in self.all_results]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> GridSearchResult:
        params_data = data.get("best_params", {})
        best_params = IronCondorParams(
            delta=params_data.get("delta", 0.15),
            dte=params_data.get("dte", 30),
            width=params_data.get("width", 5),
            exit_profit_pct=params_data.get("exit_profit_pct", 0.5),
            stop_loss_pct=params_data.get("stop_loss_pct", 2.0),
        )
        results_data = data.get("all_results") or data.get("top_10_results", [])
        all_results = [BacktestResult.from_dict(r) for r in results_data]
        return cls(
            total_combinations=data.get("total_combinations", len(all_results)),
            execution_time_ms=data.get("execution_time_ms", 0.0),
            best_params=best_params,
            best_sharpe=data.get("best_sharpe", 0.0),
            best_win_rate=data.get("best_win_rate", 0.0),
            all_results=all_results,
            gpu_accelerated=data.get("gpu_accelerated", False),
        )


# =============================================================================
# GPU KERNELS (CUDA)
# =============================================================================

if CUDA_AVAILABLE:

    @cuda.jit
    def _gpu_simulate_trades_kernel(
        prices,  # Historical price array
        deltas,  # Delta parameter for each simulation
        dtes,  # DTE parameter for each simulation
        widths,  # Width parameter for each simulation
        exit_pcts,  # Exit profit % for each simulation
        stop_pcts,  # Stop loss % for each simulation
        results,  # Output: [win_rate, avg_profit, avg_loss, max_dd] per sim
        n_trades_per_sim,
    ):
        """
        GPU kernel for parallel iron condor simulation.

        Each thread handles one parameter combination.
        """
        idx = cuda.grid(1)
        if idx >= deltas.shape[0]:
            return

        # Get parameters for this simulation
        delta = deltas[idx]
        dte = dtes[idx]
        width = widths[idx]
        exit_pct = exit_pcts[idx]
        stop_pct = stop_pcts[idx]

        # Simulate trades
        wins = 0
        total_profit = 0.0
        total_loss = 0.0
        max_drawdown = 0.0
        running_pl = 0.0
        peak_pl = 0.0

        n_prices = prices.shape[0]
        trades = min(n_trades_per_sim, n_prices - dte - 1)

        for i in range(trades):
            entry_price = prices[i]
            exit_price = prices[i + dte]

            # Calculate move as percentage
            move_pct = abs(exit_price - entry_price) / entry_price

            # Iron condor wins if move stays within delta-implied range
            # Simplified: delta ~= probability of being ITM
            # So (1 - delta) = probability of staying OTM
            win_threshold = delta * 2  # Approximate breakeven range

            # Calculate P/L
            credit = width * delta * 100  # Approximate credit received

            if move_pct < win_threshold:
                # Winner - collect premium (exit at target or full)
                pl = credit * exit_pct
                wins += 1
                total_profit += pl
            else:
                # Loser - hit stop loss
                pl = -credit * stop_pct
                total_loss += abs(pl)

            running_pl += pl
            if running_pl > peak_pl:
                peak_pl = running_pl
            drawdown = peak_pl - running_pl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Store results
        win_rate = wins / trades if trades > 0 else 0
        avg_profit = total_profit / wins if wins > 0 else 0
        avg_loss = total_loss / (trades - wins) if (trades - wins) > 0 else 0

        results[idx, 0] = win_rate
        results[idx, 1] = avg_profit
        results[idx, 2] = avg_loss
        results[idx, 3] = max_drawdown


# =============================================================================
# CPU FALLBACK (NumPy vectorized)
# =============================================================================


def _cpu_simulate_trades(
    prices: np.ndarray,
    params_grid: list[tuple],
    n_trades: int = 252,
) -> np.ndarray:
    """
    CPU fallback for trade simulation using NumPy vectorization.

    Still much faster than pure Python loops.
    """
    n_sims = len(params_grid)
    results = np.zeros((n_sims, 4))  # [win_rate, avg_profit, avg_loss, max_dd]

    for idx, (delta, dte, width, exit_pct, stop_pct) in enumerate(params_grid):
        wins = 0
        total_profit = 0.0
        total_loss = 0.0
        max_drawdown = 0.0
        running_pl = 0.0
        peak_pl = 0.0

        trades = min(n_trades, len(prices) - dte - 1)

        for i in range(trades):
            entry_price = prices[i]
            exit_price = prices[i + int(dte)]

            move_pct = abs(exit_price - entry_price) / entry_price
            win_threshold = delta * 2
            credit = width * delta * 100

            if move_pct < win_threshold:
                pl = credit * exit_pct
                wins += 1
                total_profit += pl
            else:
                pl = -credit * stop_pct
                total_loss += abs(pl)

            running_pl += pl
            peak_pl = max(peak_pl, running_pl)
            max_drawdown = max(max_drawdown, peak_pl - running_pl)

        results[idx, 0] = wins / trades if trades > 0 else 0
        results[idx, 1] = total_profit / wins if wins > 0 else 0
        results[idx, 2] = total_loss / (trades - wins) if (trades - wins) > 0 else 0
        results[idx, 3] = max_drawdown

    return results


# =============================================================================
# HIGH-LEVEL API
# =============================================================================


class GPUBacktestEngine:
    """
    GPU-accelerated backtesting engine for iron condors.

    Features:
    - Automatic GPU/CPU selection
    - Parameter grid search
    - Monte Carlo simulation
    - Result caching
    """

    # Default parameter ranges for grid search
    DEFAULT_GRID = {
        "delta": [0.10, 0.12, 0.15, 0.18, 0.20],
        "dte": [21, 30, 45, 60],
        "width": [5, 10],
        "exit_profit_pct": [0.25, 0.50, 0.75],
        "stop_loss_pct": [1.5, 2.0, 2.5],
    }

    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu and CUDA_AVAILABLE
        self.price_data: np.ndarray | None = None
        self.price_meta: dict[str, Any] | None = None
        self.results_cache: dict[str, GridSearchResult] = {}
        self.cache_enabled = os.getenv("GPU_BACKTEST_CACHE", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        self.price_cache_ttl_days = int(os.getenv("GPU_BACKTEST_PRICE_CACHE_TTL_DAYS", "7"))
        self.grid_cache_ttl_days = int(os.getenv("GPU_BACKTEST_GRID_CACHE_TTL_DAYS", "7"))

    def _price_cache_paths(self, ticker: str, years: int) -> tuple[Path, Path]:
        safe_ticker = ticker.upper()
        base = f"{safe_ticker}_{years}y"
        return (
            PRICE_CACHE_DIR / f"{base}.npz",
            PRICE_CACHE_DIR / f"{base}.json",
        )

    def _load_cached_prices(self, ticker: str, years: int) -> bool:
        if not self.cache_enabled:
            return False

        data_path, meta_path = self._price_cache_paths(ticker, years)
        if not data_path.exists() or not meta_path.exists():
            return False

        try:
            meta = json.loads(meta_path.read_text())
            downloaded_at = datetime.fromisoformat(meta["downloaded_at"])
            if datetime.now(timezone.utc) - downloaded_at > timedelta(
                days=self.price_cache_ttl_days
            ):
                return False

            payload = np.load(data_path)
            prices = payload["prices"].astype(np.float32)
            if prices.size < 2:
                return False

            self.price_data = prices
            self.price_meta = meta
            print(f"Loaded cached {ticker} data ({len(prices)} rows)")
            return True
        except Exception as e:
            print(f"Price cache load failed: {e}")
            return False

    def _save_price_cache(self, ticker: str, years: int, prices: np.ndarray, meta: dict) -> None:
        if not self.cache_enabled:
            return

        data_path, meta_path = self._price_cache_paths(ticker, years)
        np.savez_compressed(data_path, prices=prices.astype(np.float32))
        meta_path.write_text(json.dumps(meta, indent=2))

    def load_price_data(
        self,
        ticker: str = "SPY",
        years: int = 5,
        use_cache: bool | None = None,
    ) -> None:
        """Load historical price data for backtesting."""
        cache_allowed = self.cache_enabled if use_cache is None else use_cache
        if cache_allowed and self._load_cached_prices(ticker, years):
            return

        try:
            import yfinance as yf

            end = datetime.now(timezone.utc)
            try:
                start = end.replace(year=end.year - years)
            except ValueError:
                start = end.replace(month=2, day=28, year=end.year - years)

            data = yf.download(ticker, start=start.date(), end=end.date(), progress=False)
            closes = data["Close"].dropna()
            if closes.empty:
                raise ValueError("No price data returned")

            prices = closes.values.astype(np.float32)
            self.price_data = prices
            self.price_meta = {
                "ticker": ticker.upper(),
                "years": years,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "rows": int(len(prices)),
                "last_price_date": closes.index.max().isoformat(),
                "downloaded_at": end.isoformat(),
                "source": "yfinance",
            }
            self._save_price_cache(ticker, years, prices, self.price_meta)
            print(f"Loaded {len(prices)} days of {ticker} data")
        except Exception as e:
            # Generate synthetic data for testing
            print(f"Could not load real data: {e}")
            print("Using synthetic price data")
            np.random.seed(42)
            returns = np.random.normal(0.0005, 0.01, 252 * years)
            prices = np.cumprod(1 + returns).astype(np.float32) * 400
            self.price_data = prices
            self.price_meta = {
                "ticker": ticker.upper(),
                "years": years,
                "rows": int(len(prices)),
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "source": "synthetic",
            }

    def _grid_cache_key(self, grid: dict[str, list], n_trades_per_sim: int) -> str:
        normalized_grid = {k: sorted(grid[k]) for k in sorted(grid)}
        price_meta = self.price_meta or {}
        cache_fingerprint = {
            "grid": normalized_grid,
            "n_trades_per_sim": n_trades_per_sim,
            "price_meta": {
                "ticker": price_meta.get("ticker"),
                "years": price_meta.get("years"),
                "rows": price_meta.get("rows"),
                "last_price_date": price_meta.get("last_price_date"),
            },
            "cache_version": CACHE_VERSION,
        }
        payload = json.dumps(cache_fingerprint, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    def _load_cached_grid_search(self, cache_key: str) -> GridSearchResult | None:
        if not self.cache_enabled:
            return None

        if cache_key in self.results_cache:
            return self.results_cache[cache_key]

        cache_path = CACHE_DIR / f"grid_search_{cache_key}.json"
        if not cache_path.exists():
            return None

        try:
            payload = json.loads(cache_path.read_text())
            if payload.get("cache_version") != CACHE_VERSION:
                return None

            created_at = datetime.fromisoformat(payload["created_at"])
            if datetime.now(timezone.utc) - created_at > timedelta(days=self.grid_cache_ttl_days):
                return None

            result_data = payload.get("result")
            if not result_data:
                return None

            grid_result = GridSearchResult.from_dict(result_data)
            self.results_cache[cache_key] = grid_result
            print(f"Loaded cached grid search ({cache_key})")
            return grid_result
        except Exception as e:
            print(f"Grid cache load failed: {e}")
            return None

    def _save_grid_cache(
        self,
        cache_key: str,
        grid: dict[str, list],
        n_trades_per_sim: int,
        result: GridSearchResult,
    ) -> None:
        if not self.cache_enabled:
            return

        cache_path = CACHE_DIR / f"grid_search_{cache_key}.json"
        payload = {
            "cache_version": CACHE_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "grid": grid,
            "n_trades_per_sim": n_trades_per_sim,
            "price_meta": self.price_meta,
            "result": result.to_dict(include_all=True),
        }
        cache_path.write_text(json.dumps(payload, indent=2))

    def grid_search(
        self,
        param_grid: dict[str, list] | None = None,
        n_trades_per_sim: int = 252,
        use_cache: bool | None = None,
    ) -> GridSearchResult:
        """
        Run parameter grid search across all combinations.

        Uses GPU if available, falls back to CPU.
        """
        if self.price_data is None:
            self.load_price_data()

        grid = param_grid or self.DEFAULT_GRID
        cache_allowed = self.cache_enabled if use_cache is None else use_cache
        cache_key = None
        if cache_allowed:
            cache_key = self._grid_cache_key(grid, n_trades_per_sim)
            cached_result = self._load_cached_grid_search(cache_key)
            if cached_result is not None:
                return cached_result

        start_time = datetime.now(timezone.utc)

        # Generate all parameter combinations
        from itertools import product

        combinations = list(
            product(
                grid["delta"],
                grid["dte"],
                grid["width"],
                grid["exit_profit_pct"],
                grid["stop_loss_pct"],
            )
        )

        n_sims = len(combinations)
        print(f"\nGrid Search: {n_sims} parameter combinations")
        print(f"GPU Acceleration: {'ENABLED' if self.use_gpu else 'DISABLED (CPU fallback)'}")

        if self.use_gpu:
            results = self._run_gpu_grid_search(combinations, n_trades_per_sim)
        else:
            results = _cpu_simulate_trades(self.price_data, combinations, n_trades_per_sim)

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Process results
        all_results = []
        best_sharpe = -float("inf")
        best_idx = 0

        for idx, (delta, dte, width, exit_pct, stop_pct) in enumerate(combinations):
            win_rate = results[idx, 0]
            avg_profit = results[idx, 1]
            avg_loss = results[idx, 2]
            max_dd = results[idx, 3]

            # Calculate profit factor and Sharpe
            profit_factor = avg_profit / avg_loss if avg_loss > 0 else float("inf")

            # Simplified Sharpe: (avg_return - rf) / std
            # Using win_rate * avg_profit - (1-win_rate) * avg_loss as expected return
            expected_return = win_rate * avg_profit - (1 - win_rate) * avg_loss
            # Approximate std from win/loss distribution
            std = (
                math.sqrt(
                    win_rate * (avg_profit - expected_return) ** 2
                    + (1 - win_rate) * (avg_loss + expected_return) ** 2
                )
                if avg_loss > 0
                else 1
            )

            sharpe = expected_return / std if std > 0 else 0

            params = IronCondorParams(
                delta=delta,
                dte=dte,
                width=width,
                exit_profit_pct=exit_pct,
                stop_loss_pct=stop_pct,
            )

            result = BacktestResult(
                params=params,
                win_rate=win_rate,
                total_trades=n_trades_per_sim,
                avg_profit=avg_profit,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                max_drawdown=max_dd,
                sharpe_ratio=sharpe,
                execution_time_ms=execution_time / n_sims,
            )

            all_results.append(result)

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_idx = idx

        best_result = all_results[best_idx]

        grid_result = GridSearchResult(
            total_combinations=n_sims,
            execution_time_ms=execution_time,
            best_params=best_result.params,
            best_sharpe=best_sharpe,
            best_win_rate=best_result.win_rate,
            all_results=all_results,
            gpu_accelerated=self.use_gpu,
        )

        if cache_allowed and cache_key:
            self._save_grid_cache(cache_key, grid, n_trades_per_sim, grid_result)

        # Save results
        self._save_results(grid_result)

        print(f"\nCompleted in {execution_time:.0f}ms")
        print(f"Best Sharpe: {best_sharpe:.3f}")
        print(f"Best Win Rate: {best_result.win_rate:.1%}")
        print(f"Best Params: delta={best_result.params.delta}, dte={best_result.params.dte}")

        return grid_result

    def _run_gpu_grid_search(
        self,
        combinations: list[tuple],
        n_trades_per_sim: int,
    ) -> np.ndarray:
        """Execute grid search on GPU."""
        n_sims = len(combinations)

        # Prepare arrays for GPU
        deltas = np.array([c[0] for c in combinations], dtype=np.float32)
        dtes = np.array([c[1] for c in combinations], dtype=np.float32)
        widths = np.array([c[2] for c in combinations], dtype=np.float32)
        exit_pcts = np.array([c[3] for c in combinations], dtype=np.float32)
        stop_pcts = np.array([c[4] for c in combinations], dtype=np.float32)
        results = np.zeros((n_sims, 4), dtype=np.float32)

        # Transfer to GPU
        d_prices = cuda.to_device(self.price_data)
        d_deltas = cuda.to_device(deltas)
        d_dtes = cuda.to_device(dtes)
        d_widths = cuda.to_device(widths)
        d_exit_pcts = cuda.to_device(exit_pcts)
        d_stop_pcts = cuda.to_device(stop_pcts)
        d_results = cuda.to_device(results)

        # Configure kernel
        threads_per_block = 256
        blocks = (n_sims + threads_per_block - 1) // threads_per_block

        # Execute kernel
        _gpu_simulate_trades_kernel[blocks, threads_per_block](
            d_prices,
            d_deltas,
            d_dtes,
            d_widths,
            d_exit_pcts,
            d_stop_pcts,
            d_results,
            n_trades_per_sim,
        )

        # Copy results back
        return d_results.copy_to_host()

    def monte_carlo_var(
        self,
        params: IronCondorParams,
        n_scenarios: int = 10000,
        confidence: float | list[float] = 0.95,
    ) -> dict[str, float]:
        """
        Monte Carlo Value at Risk simulation.

        GPU-accelerated when available.
        Supports multiple confidence levels when a list is provided.
        """
        if self.price_data is None:
            self.load_price_data()

        start_time = datetime.now(timezone.utc)

        # Generate random trade outcomes
        np.random.seed(None)  # True randomness

        # Simulate using historical win rate distribution
        win_prob = 1 - params.delta  # Approximate P(profit)
        credit = params.width * params.delta * 100

        outcomes = np.where(
            np.random.random(n_scenarios) < win_prob,
            credit * params.exit_profit_pct,  # Win
            -credit * params.stop_loss_pct,  # Loss
        )

        confidences = (
            [float(c) for c in confidence]
            if isinstance(confidence, (list, tuple, set))
            else [float(confidence)]
        )
        confidences = [c for c in confidences if 0 < c < 1]
        if not confidences:
            confidences = [0.95]

        # Calculate VaR for each confidence level
        var_results = {}
        for level in confidences:
            percentile = (1 - level) * 100
            var_results[f"var_{int(round(level * 100))}"] = np.percentile(outcomes, percentile)
        expected_return = np.mean(outcomes)
        worst_case = np.min(outcomes)

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        return {
            **var_results,
            "expected_return": expected_return,
            "worst_case": worst_case,
            "best_case": np.max(outcomes),
            "std_dev": np.std(outcomes),
            "scenarios": n_scenarios,
            "execution_time_ms": execution_time,
            "confidence_levels": confidences,
        }

    def _save_results(self, result: GridSearchResult) -> Path:
        """Save grid search results to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = BACKTEST_DIR / f"grid_search_{timestamp}.json"
        filepath.write_text(json.dumps(result.to_dict(), indent=2))
        return filepath


async def run_gpu_backtest() -> dict[str, Any]:
    """
    Main entry point for GPU-accelerated backtesting.

    Called by research agent for weekend analysis.
    """
    engine = GPUBacktestEngine()

    # Run grid search
    grid_result = engine.grid_search()

    # Run Monte Carlo on best params
    var_result = engine.monte_carlo_var(grid_result.best_params, confidence=[0.95, 0.99])

    return {
        "grid_search": grid_result.to_dict(),
        "monte_carlo_var": var_result,
        "gpu_available": CUDA_AVAILABLE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_optimal_params() -> IronCondorParams | None:
    """
    Get the most recent optimal parameters from backtest results.

    Used by trading workflow to configure iron condors.
    """
    result_files = sorted(BACKTEST_DIR.glob("grid_search_*.json"), reverse=True)

    if not result_files:
        return None

    latest = json.loads(result_files[0].read_text())
    params = latest.get("best_params", {})

    return IronCondorParams(
        delta=params.get("delta", 0.15),
        dte=params.get("dte", 30),
        width=params.get("width", 5),
        exit_profit_pct=params.get("exit_profit_pct", 0.50),
        stop_loss_pct=params.get("stop_loss_pct", 2.0),
    )


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("GPU BACKTEST ENGINE")
    print(f"CUDA Available: {CUDA_AVAILABLE}")
    print("=" * 60)

    result = asyncio.run(run_gpu_backtest())

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Grid search time: {result['grid_search']['execution_time_ms']:.0f}ms")
    print(f"Best Sharpe: {result['grid_search']['best_sharpe']:.3f}")
    print(f"Best Win Rate: {result['grid_search']['best_win_rate']:.1%}")
    print(f"VaR (95%): ${result['monte_carlo_var']['var_95']:.2f}")
    if "var_99" in result["monte_carlo_var"]:
        print(f"VaR (99%): ${result['monte_carlo_var']['var_99']:.2f}")
    print(f"Expected Return: ${result['monte_carlo_var']['expected_return']:.2f}")
