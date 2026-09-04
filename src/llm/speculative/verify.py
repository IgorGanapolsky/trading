"""Lossless draft-then-verify: accept until first mismatch.

NVIDIA: AL ranges from 1 to 1+D because the target can always emit one
ground-truth token in addition to accepted drafts. Only accepted tokens
are retained, so the sequence matches standard decoding.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class VerifyResult:
    accepted: list[str]
    rejected_at: int | None
    bonus: str | None
    AL: int
    D: int
    lossless: bool
    mechanism: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_draft(
    draft: Sequence[str],
    target: Sequence[str],
    *,
    mechanism: str = "suffix_ngram",
) -> VerifyResult:
    """Compare draft to target tokens. Stop at the first mismatch."""

    draft_toks = [str(tok) for tok in draft]
    target_toks = [str(tok) for tok in target]
    accepted: list[str] = []
    rejected_at: int | None = None
    for i, tok in enumerate(draft_toks):
        if i >= len(target_toks) or tok != target_toks[i]:
            rejected_at = i
            bonus = target_toks[i] if i < len(target_toks) else None
            al = len(accepted) + (1 if bonus is not None else 0)
            return VerifyResult(
                accepted=accepted,
                rejected_at=rejected_at,
                bonus=bonus,
                AL=max(al, 1 if target_toks else 0),
                D=len(draft_toks),
                lossless=True,
                mechanism=mechanism,
            )
        accepted.append(tok)
    bonus = target_toks[len(draft_toks)] if len(target_toks) > len(draft_toks) else None
    al = len(accepted) + (1 if bonus is not None else 0)
    if al == 0 and target_toks:
        al = 1
        bonus = target_toks[0]
    return VerifyResult(
        accepted=accepted,
        rejected_at=None,
        bonus=bonus,
        AL=al,
        D=len(draft_toks),
        lossless=True,
        mechanism=mechanism,
    )
