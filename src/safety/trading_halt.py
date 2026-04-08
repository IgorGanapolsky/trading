"""Helpers for detecting active trading halts.

This centralizes the repo's halt sentinels so entry points and trade gates do
not drift between `data/TRADING_HALTED` and the older `data/trading_halt.txt`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_HALT_FILES: tuple[tuple[Path, str], ...] = (
    (Path("data/TRADING_HALTED"), "system_halt"),
    (Path("data/trading_halt.txt"), "legacy_manual_halt"),
)


@dataclass(frozen=True)
class TradingHaltState:
    """Current repo trading halt state."""

    active: bool
    kind: str = "none"
    path: str = ""
    reason: str = ""


def get_trading_halt_state(repo_root: Path | None = None) -> TradingHaltState:
    """Return the first active halt sentinel found under the repo root."""
    root = repo_root or Path(".")

    for relative_path, kind in DEFAULT_HALT_FILES:
        candidate = root / relative_path
        if not candidate.exists():
            continue

        reason = candidate.read_text(encoding="utf-8", errors="ignore").strip()
        if not reason:
            reason = f"Trading halted via {candidate.name}."

        return TradingHaltState(
            active=True,
            kind=kind,
            path=str(candidate),
            reason=reason,
        )

    return TradingHaltState(active=False)
