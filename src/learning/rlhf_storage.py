"""Stub file - rlhf_storage (original deleted in cleanup)."""

from typing import Any


def store_trade_trajectory(
    episode_id: str = "",
    entry_state: dict = None,
    action: int = 0,
    reward: float = 0.0,
    *args,
    **kwargs,
) -> dict[str, Any]:
    """Stub for store_trade_trajectory - does nothing."""
    return {"stored": False, "episode_id": episode_id}
