"""Model-free suffix / n-gram drafter (NVIDIA table: no training, O(1) lookup).

Not a trained draft head. Not a second LLM.
"""

from __future__ import annotations

from dataclasses import dataclass


def tokenize(text: str) -> list[str]:
    return [tok for tok in str(text or "").split() if tok]


@dataclass(frozen=True)
class DraftProposal:
    tokens: list[str]
    D: int
    mechanism: str
    n: int
    draft_overhead: float  # rho * D analog; n-gram lookup is ~0


def ngram_draft(prefix: str, corpus: str, *, D: int, n: int = 3) -> DraftProposal:
    """Propose up to D tokens by matching the longest prefix suffix in corpus."""

    d_len = max(0, int(D))
    order = max(1, int(n))
    prefix_toks = tokenize(prefix)
    corpus_toks = tokenize(corpus)
    if d_len == 0 or not prefix_toks or len(corpus_toks) < 2:
        return DraftProposal(
            tokens=[], D=d_len, mechanism="suffix_ngram", n=order, draft_overhead=0.0
        )

    drafted: list[str] = []
    for window in range(min(order, len(prefix_toks)), 0, -1):
        needle = tuple(prefix_toks[-window:])
        last_idx = None
        for i in range(len(corpus_toks) - window):
            if tuple(corpus_toks[i : i + window]) == needle:
                last_idx = i + window
        if last_idx is None:
            continue
        drafted = corpus_toks[last_idx : last_idx + d_len]
        break
    return DraftProposal(
        tokens=list(drafted),
        D=d_len,
        mechanism="suffix_ngram",
        n=order,
        draft_overhead=0.0,
    )
