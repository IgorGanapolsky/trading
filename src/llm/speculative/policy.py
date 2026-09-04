"""Draft-length policy: increase D only while AL gain justifies draft cost.

NVIDIA guideline 4. We do not invent wall-clock speedup. Without measured AL,
speedup is None — never NVIDIA's published curves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

FORBIDDEN_CLAIMS = (
    "tensorrt-llm",
    "nvidia 1.3",
    "1.7x throughput",
    "eagle-3 training",
    "model-optimizer",
)


@dataclass(frozen=True)
class DraftMeasurement:
    D: int
    AL: float
    draft_overhead: float


def estimated_speedup(AL: float, D: int, draft_overhead: float) -> float | None:
    """AL / (1 + Od). None when AL was not measured (AL <= 0)."""

    if AL <= 0 or D < 0 or draft_overhead < 0:
        return None
    return float(AL) / (1.0 + float(draft_overhead))


def choose_D(measurements: Sequence[DraftMeasurement], *, max_D: int) -> int:
    """Pick D with the best measured AL/(1+Od) that does not exceed max_D."""

    cap = max(0, int(max_D))
    best_d = 0
    best_score = 0.0
    for row in measurements:
        if row.D < 0 or cap < row.D:
            continue
        score = estimated_speedup(row.AL, row.D, row.draft_overhead)
        if score is None:
            continue
        if score > best_score or (score == best_score and best_d > row.D):
            best_score = score
            best_d = row.D
    return best_d


def lookalike_hits(source: str) -> list[str]:
    lowered = source.lower()
    return [snip for snip in FORBIDDEN_CLAIMS if snip in lowered]
