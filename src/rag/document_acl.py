"""Document-level sensitivity / ACL for the single-operator trading lab.

This is not multi-tenant SaaS ACL. It is production hygiene:
- classify lessons as operator-only vs shareable
- block secret-like material from entering the RAG index
- provide a filter so future HTTP/MCP surfaces cannot dump secrets

Default tenant: the CEO/operator only (TENANT_OPERATOR).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class Sensitivity(StrEnum):
    """Document sensitivity for retrieval filtering."""

    PUBLIC_OK = "public_ok"  # may appear in public docs later
    OPERATOR_ONLY = "operator_only"  # default for lessons
    # Label only — not a credential (bandit B105 false positive).
    FORBIDDEN = "forbidden_index"  # must never be indexed


class TenantId(StrEnum):
    """Single-tenant lab. Expand only with real isolation."""

    OPERATOR = "operator"


# Patterns that must never land in vector/FTS indexes.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk_test_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAPCA-[A-Z0-9]{20,}\b", re.IGNORECASE),
    re.compile(r"(?i)api[_-]?secret[_-]?key\s*[:=]\s*\S+"),
    re.compile(r"(?i)(password|passwd|secret)\s*[:=]\s*\S+"),
)


@dataclass(frozen=True)
class DocumentACL:
    tenant_id: TenantId
    sensitivity: Sensitivity
    allowed_tenants: frozenset[str]

    def permits(self, requester_tenant: str) -> bool:
        if self.sensitivity == Sensitivity.FORBIDDEN:
            return False
        return requester_tenant in self.allowed_tenants or self.sensitivity == Sensitivity.PUBLIC_OK


DEFAULT_LESSON_ACL = DocumentACL(
    tenant_id=TenantId.OPERATOR,
    sensitivity=Sensitivity.OPERATOR_ONLY,
    allowed_tenants=frozenset({TenantId.OPERATOR.value}),
)


def detect_secrets(text: str) -> list[str]:
    """Return human-readable secret pattern hits (never the secret value)."""
    hits: list[str] = []
    for pat in _SECRET_PATTERNS:
        if pat.search(text or ""):
            hits.append(pat.pattern[:48])
    return hits


def scrub_secrets(text: str) -> str:
    """Redact secret-like substrings before indexing."""
    scrubbed = text or ""
    for pat in _SECRET_PATTERNS:
        scrubbed = pat.sub("[REDACTED_SECRET]", scrubbed)
    return scrubbed


def classify_for_index(text: str, *, source: str = "lesson") -> DocumentACL:
    """Classify document; secret hits → FORBIDDEN (reject index)."""
    if detect_secrets(text):
        return DocumentACL(
            tenant_id=TenantId.OPERATOR,
            sensitivity=Sensitivity.FORBIDDEN,
            allowed_tenants=frozenset(),
        )
    # Lessons and trade journals stay operator-only by default.
    if source in {"lesson", "feedback", "trade_journal", "manual"}:
        return DEFAULT_LESSON_ACL
    return DocumentACL(
        tenant_id=TenantId.OPERATOR,
        sensitivity=Sensitivity.PUBLIC_OK,
        allowed_tenants=frozenset({TenantId.OPERATOR.value}),
    )


def filter_results_for_tenant(
    results: Iterable[dict],
    *,
    requester_tenant: str = TenantId.OPERATOR.value,
    default_acl: DocumentACL = DEFAULT_LESSON_ACL,
) -> list[dict]:
    """Filter retrieval rows by tenant/sensitivity (defaults allow operator)."""
    out: list[dict] = []
    for row in results:
        sens = str(row.get("sensitivity") or default_acl.sensitivity.value)
        if sens == Sensitivity.FORBIDDEN.value:
            continue
        allowed = row.get("allowed_tenants")
        if allowed is None:
            if default_acl.permits(requester_tenant):
                out.append(row)
            continue
        if requester_tenant in set(allowed) or sens == Sensitivity.PUBLIC_OK.value:
            out.append(row)
    return out


def assert_indexable(text: str) -> str:
    """Return scrubbed text or raise if classification forbids indexing."""
    acl = classify_for_index(text)
    if acl.sensitivity == Sensitivity.FORBIDDEN:
        raise ValueError("Document contains secret-like material; refused for RAG index")
    return scrub_secrets(text)
