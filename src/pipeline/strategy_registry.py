from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class StageConfig:
    name: str
    command: str
    description: str | None = None


@dataclass(frozen=True)
class StrategyConfig:
    strategy_id: str
    label: str
    description: str | None
    stages: dict[str, StageConfig]


class StrategyRegistry:
    """
    Lightweight loader for strategy metadata defined in config/strategies.yaml.
    """

    def __init__(self, registry_path: Path | str = Path("config/strategies.yaml")) -> None:
        self.registry_path = Path(registry_path)
        if not self.registry_path.exists():
            raise FileNotFoundError(
                f"Strategy registry not found at {self.registry_path}. "
                "Create config/strategies.yaml or pass a custom path."
            )
        self._strategies = self._load()

    def _load(self) -> dict[str, StrategyConfig]:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        strategies = payload.get("strategies")
        if not strategies:
            raise ValueError(f"No strategies defined in {self.registry_path}")

        parsed: dict[str, StrategyConfig] = {}
        for strategy_id, cfg in strategies.items():
            stages_payload = cfg.get("stages") or {}
            stages: dict[str, StageConfig] = {}
            for stage_name, stage_cfg in stages_payload.items():
                command = stage_cfg.get("command")
                if not command:
                    raise ValueError(
                        f"Stage '{stage_name}' for strategy '{strategy_id}' is missing a command."
                    )
                stages[stage_name] = StageConfig(
                    name=stage_name,
                    command=command,
                    description=stage_cfg.get("description"),
                )
            parsed[strategy_id] = StrategyConfig(
                strategy_id=strategy_id,
                label=cfg.get("label", strategy_id),
                description=cfg.get("description"),
                stages=stages,
            )
        return parsed

    def list_strategies(self) -> Iterable[StrategyConfig]:
        return self._strategies.values()

    def get(self, strategy_id: str) -> StrategyConfig:
        try:
            return self._strategies[strategy_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._strategies.keys()))
            raise KeyError(f"Strategy '{strategy_id}' not found. Available: {available}") from exc

    def list_stages(self, strategy_id: str) -> Iterable[StageConfig]:
        return self.get(strategy_id).stages.values()
