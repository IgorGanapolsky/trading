# HIGH: Parent-child retrieval requires parent-level diversity

**Severity**: HIGH

## Incident

The first hierarchical retrieval implementation correctly kept child chunks
through reranking, but allowed two final sections from the same parent lesson.
Duplicate parent IDs consumed top-five slots and reduced measured Precision@5
from 0.74 to 0.40 and Recall@5 from about 0.90 to 0.49.

## Root Cause

Candidate diversity was evaluated at the child-chunk level while the golden
set and downstream citations operate at the parent-lesson level. Long lessons
therefore dominated the reranker input and final result list even when the
individual child chunks were relevant.

## Prevention

Keep child chunks distinct for BM25/vector fusion and cross-encoder reranking,
but cap reranker input to two children per parent, overfetch until enough unique
parents are represented, and emit only the best section per parent lesson.
Evaluate Precision, Recall, MRR, and nDCG on final parent IDs after every
hierarchical retrieval change. Reject the candidate artifact whenever that
deterministic holdout regresses, regardless of architectural appeal.

## Tags

`rag` `parent-child` `retrieval-diversity` `offline-evaluation` `regression-gate`
