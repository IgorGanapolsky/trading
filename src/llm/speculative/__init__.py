"""Speculative decoding FORMAT steal: n-gram draft + lossless verify.

Not a GPU serving stack. Not a trained draft head. Optional LLM path only —
risk engine still owns entries.
"""

from src.llm.speculative.ngram import DraftProposal, ngram_draft, tokenize
from src.llm.speculative.policy import (
    DraftMeasurement,
    choose_D,
    estimated_speedup,
)
from src.llm.speculative.verify import VerifyResult, verify_draft

__all__ = [
    "DraftMeasurement",
    "DraftProposal",
    "VerifyResult",
    "choose_D",
    "estimated_speedup",
    "ngram_draft",
    "tokenize",
    "verify_draft",
]
