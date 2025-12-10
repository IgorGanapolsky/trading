from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.analytics.options_profit_planner import OptionsProfitPlanner, ThetaHarvestExecutor
from src.utils.regime_detector import RegimeDetector

logger = logging.getLogger(__name__)


@dataclass
class OptionsLiveSimResult:
    """Structured payload produced by the live options simulator."""

    account_equity: float
    regime_label: str
    regime_source: str
    theta_plan: dict[str, Any]
    profit_summary: dict[str, Any]
    profit_summary_path: Path | None = None


class OptionsLiveSimulator:
    """
    Wire together the Options Profit Planner + Theta Harvest executor.

    Responsibilities:
        - Read the latest account equity from system_state.json
        - Resolve the current market regime (live VIX snapshot or override)
        - Produce the premium pacing summary from stored Rule #1 snapshots
        - Generate theta opportunities gated by equity/IV/delta rules
        - Persist combined artifacts for dashboards + audits
    """

    def __init__(
        self,
        *,
        system_state_path: Path | str = Path("data/system_state.json"),
        snapshot_dir: Path | str = Path("data/options_signals"),
        target_daily_profit: float = 10.0,
        trading_days_per_month: int = 21,
        planner: OptionsProfitPlanner | None = None,
        theta_executor: ThetaHarvestExecutor | None = None,
        paper: bool = True,
    ) -> None:
        self.system_state_path = Path(system_state_path)
        snapshot_dir = Path(snapshot_dir)
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        self.planner = planner or OptionsProfitPlanner(
            target_daily_profit=target_daily_profit,
            trading_days_per_month=trading_days_per_month,
            snapshot_dir=snapshot_dir,
        )
        self.theta_executor = theta_executor or ThetaHarvestExecutor(paper=paper)

    # ------------------------------------------------------------------ #
    # Data loading helpers
    # ------------------------------------------------------------------ #
    def load_account_equity(self, override: float | None = None) -> float:
        """Return the account equity from system_state.json (or override)."""
        if override is not None:
            return float(override)

        if not self.system_state_path.exists():
            raise FileNotFoundError(
                f"System state not found at {self.system_state_path}. "
                "Pass --equity to override when running locally."
            )

        with self.system_state_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        account = payload.get("account") or {}
        equity = account.get("current_equity")
        if equity is None:
            raise ValueError(
                f"System state at {self.system_state_path} is missing account.current_equity"
            )
        return float(equity)

    @staticmethod
    def _normalize_symbols(symbols: Iterable[str] | None) -> list[str]:
        if not symbols:
            return ["SPY", "QQQ", "IWM"]
        return [symbol.strip().upper() for symbol in symbols if symbol.strip()]

    def resolve_regime_label(
        self,
        override: str | None = None,
        *,
        use_live_snapshot: bool = True,
    ) -> tuple[str, str]:
        """
        Determine the regime label plus source metadata.

        Returns:
            (label, source) where source ∈ {"override", "live", "fallback"}
        """
        if override:
            return override, "override"

        if use_live_snapshot:
            try:
                snapshot = RegimeDetector().detect_live_regime()
                label = getattr(snapshot, "label", None)
                if label:
                    return label, "live"
            except Exception as exc:  # pragma: no cover - network/infra failures
                logger.warning("Live regime detection failed, falling back to 'calm': %s", exc)

        return "calm", "fallback"

    # ------------------------------------------------------------------ #
    # Core orchestration
    # ------------------------------------------------------------------ #
    def run(
        self,
        *,
        account_equity: float | None = None,
        regime_label: str | None = None,
        snapshot: dict[str, Any] | None = None,
        symbols: Iterable[str] | None = None,
        persist_summary: bool = True,
    ) -> OptionsLiveSimResult:
        """
        Execute the live simulation and return structured results.
        """
        equity = self.load_account_equity(account_equity)
        resolved_regime, regime_source = self.resolve_regime_label(regime_label)
        snapshot_payload = snapshot if snapshot is not None else self.planner.load_latest_snapshot()

        profit_summary = self.planner.build_summary_from_snapshot(snapshot_payload)
        summary_path = self.planner.persist_summary(profit_summary) if persist_summary else None

        theta_plan = self.theta_executor.generate_theta_plan(
            account_equity=equity,
            regime_label=resolved_regime,
            symbols=self._normalize_symbols(symbols),
        )

        return OptionsLiveSimResult(
            account_equity=equity,
            regime_label=resolved_regime,
            regime_source=regime_source,
            theta_plan=theta_plan,
            profit_summary=profit_summary,
            profit_summary_path=summary_path,
        )

    def persist_combined_plan(
        self,
        result: OptionsLiveSimResult,
        output_path: Path | str,
    ) -> Path:
        """
        Persist a combined JSON artifact containing planner + theta plan output.
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "account_equity": result.account_equity,
            "regime": {
                "label": result.regime_label,
                "source": result.regime_source,
            },
            "theta_plan": result.theta_plan,
            "profit_summary": result.profit_summary,
            "profit_summary_path": str(result.profit_summary_path)
            if result.profit_summary_path
            else None,
        }

        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        logger.info("Saved options live simulation → %s", path)
        return path
