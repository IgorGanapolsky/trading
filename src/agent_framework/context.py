"""Dataclasses for run configuration and agent context."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RunMode(Enum):
    """Execution mode for an orchestrated run."""

    LIVE = "live"
    PAPER = "paper"
    DRY_RUN = "dry_run"


@dataclass
class AgentConfig:
    """Configuration values injected into agents."""

    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any | None = None) -> Any:
        return self.data.get(key, default)

    def copy_with(self, **overrides: Any) -> AgentConfig:
        """Return a shallow copy with updates."""
        new_data = self.data.copy()
        if "data" in overrides:
            new_data.update(overrides.pop("data"))
        return AgentConfig(data=new_data)


@dataclass
class RunContext:
    """Shared context passed between orchestrator and agents."""

    mode: RunMode
    force: bool = False
    run_id: str | None = None
    config: AgentConfig = field(default_factory=AgentConfig)
    workspace_dir: Path = field(default_factory=lambda: Path.cwd())
    state_cache: dict[str, Any] = field(default_factory=dict)

    def copy_with(self, **overrides: Any) -> RunContext:
        """Return a shallow copy with updates."""
        data = self.__dict__.copy()
        data.update(overrides)
        return RunContext(**data)
