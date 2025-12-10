from pathlib import Path

import pytest
from src.pipeline.strategy_registry import StageConfig, StrategyRegistry


def write_registry(tmp_path: Path) -> Path:
    path = tmp_path / "strategies.yaml"
    path.write_text(
        """
strategies:
  sample:
    label: Sample Strategy
    stages:
      backtest:
        command: "python3 tests/fixtures/run_backtest.py"
        description: "Run unit backtest"
      execute:
        command: "python3 scripts/autonomous_trader.py"
""",
        encoding="utf-8",
    )
    return path


def test_registry_loads_strategies(tmp_path: Path) -> None:
    registry = StrategyRegistry(write_registry(tmp_path))
    strategy = registry.get("sample")
    assert strategy.label == "Sample Strategy"
    assert "backtest" in strategy.stages
    assert isinstance(strategy.stages["backtest"], StageConfig)


def test_missing_stage_command_raises(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.yaml"
    bad_path.write_text(
        """
strategies:
  broken:
    stages:
      backtest:
        description: "No command provided"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        StrategyRegistry(bad_path)


def test_get_unknown_strategy(tmp_path: Path) -> None:
    registry = StrategyRegistry(write_registry(tmp_path))
    with pytest.raises(KeyError):
        registry.get("unknown")
