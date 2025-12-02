"""State provider abstractions for orchestrator + agents."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class StateProvider(ABC):
    """Interface for reading/writing shared orchestrator state."""

    @abstractmethod
    def load(self) -> dict[str, Any]:
        """Return the persisted state."""

    @abstractmethod
    def save(self, state: dict[str, Any]) -> None:
        """Persist updated state atomically."""


class FileStateProvider(StateProvider):
    """Simple JSON-backed provider compatible with legacy workflows."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            logger.debug("State file %s missing, returning empty dict", self.path)
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to load state %s: %s", self.path, exc)
            raise

    def save(self, state: dict[str, Any]) -> None:
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.path)
