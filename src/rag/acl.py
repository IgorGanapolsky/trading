"""Document-level ACL for trading RAG (single-tenant ready, multi-principal model).

Even a solo operator system needs document ACL to prevent:
  - paper-only lessons leaking into live-facing prompts
  - risk-critical rules being filtered out
  - future multi-agent principals reading the wrong corpus slice

Principals request access with a role set; chunks/docs declare required roles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterable


class DocSensitivity(StrEnum):
    PUBLIC = "public"  # general education
    OPERATOR = "operator"  # default lessons
    RISK_CRITICAL = "risk_critical"  # stops, kill switch, inventory
    PAPER_ONLY = "paper_only"  # validation cohort notes
    LIVE_RESTRICTED = "live_restricted"  # never inject into live prompts


class PrincipalRole(StrEnum):
    ANON = "anon"
    OPERATOR = "operator"
    RISK = "risk"
    PAPER = "paper"
    LIVE = "live"
    ADMIN = "admin"


# Role → sensitivities allowed
_ROLE_ALLOW: dict[PrincipalRole, set[DocSensitivity]] = {
    PrincipalRole.ANON: {DocSensitivity.PUBLIC},
    PrincipalRole.OPERATOR: {
        DocSensitivity.PUBLIC,
        DocSensitivity.OPERATOR,
        DocSensitivity.RISK_CRITICAL,
        DocSensitivity.PAPER_ONLY,
    },
    PrincipalRole.RISK: {
        DocSensitivity.PUBLIC,
        DocSensitivity.OPERATOR,
        DocSensitivity.RISK_CRITICAL,
    },
    PrincipalRole.PAPER: {
        DocSensitivity.PUBLIC,
        DocSensitivity.OPERATOR,
        DocSensitivity.RISK_CRITICAL,
        DocSensitivity.PAPER_ONLY,
    },
    PrincipalRole.LIVE: {
        DocSensitivity.PUBLIC,
        DocSensitivity.OPERATOR,
        DocSensitivity.RISK_CRITICAL,
        # PAPER_ONLY excluded from live
        # LIVE_RESTRICTED excluded unless ADMIN
    },
    PrincipalRole.ADMIN: set(DocSensitivity),
}


@dataclass(frozen=True)
class Principal:
    name: str
    roles: frozenset[PrincipalRole] = field(
        default_factory=lambda: frozenset({PrincipalRole.OPERATOR})
    )

    @classmethod
    def operator(cls, name: str = "operator") -> Principal:
        return cls(
            name=name,
            roles=frozenset({PrincipalRole.OPERATOR, PrincipalRole.PAPER, PrincipalRole.RISK}),
        )

    @classmethod
    def live_trader(cls, name: str = "live") -> Principal:
        return cls(
            name=name,
            roles=frozenset({PrincipalRole.LIVE, PrincipalRole.OPERATOR, PrincipalRole.RISK}),
        )

    @classmethod
    def admin(cls, name: str = "admin") -> Principal:
        return cls(name=name, roles=frozenset({PrincipalRole.ADMIN}))


def infer_sensitivity(
    *,
    severity: str = "",
    tags: Iterable[str] | None = None,
    text: str = "",
    explicit: str | None = None,
) -> DocSensitivity:
    if explicit:
        try:
            return DocSensitivity(explicit)
        except ValueError:
            pass
    sev = (severity or "").upper()
    blob = f"{' '.join(tags or [])} {text}".lower()
    if "live_restricted" in blob or "do not inject live" in blob:
        return DocSensitivity.LIVE_RESTRICTED
    if sev in {"CRITICAL", "P0"} or any(
        k in blob for k in ("kill switch", "stop loss", "halt", "inventory", "never")
    ):
        return DocSensitivity.RISK_CRITICAL
    if "paper" in blob or "validation cohort" in blob:
        return DocSensitivity.PAPER_ONLY
    if sev in {"LOW"} and "public" in blob:
        return DocSensitivity.PUBLIC
    return DocSensitivity.OPERATOR


def allowed_sensitivities(principal: Principal) -> set[DocSensitivity]:
    """Union of role grants, with live-mode hard denials.

    If the principal holds LIVE without ADMIN, paper-only and live-restricted
    documents are denied even when OPERATOR would otherwise allow them. This
    prevents paper cohort notes from leaking into live-facing prompts when a
    principal is constructed as live+operator.
    """
    allowed: set[DocSensitivity] = set()
    for role in principal.roles:
        allowed |= _ROLE_ALLOW.get(role, set())
    if PrincipalRole.ADMIN in principal.roles:
        return allowed
    if PrincipalRole.LIVE in principal.roles:
        allowed.discard(DocSensitivity.PAPER_ONLY)
        allowed.discard(DocSensitivity.LIVE_RESTRICTED)
    return allowed


def is_allowed(
    principal: Principal,
    sensitivity: DocSensitivity | str,
) -> bool:
    if isinstance(sensitivity, str):
        try:
            sensitivity = DocSensitivity(sensitivity)
        except ValueError:
            sensitivity = DocSensitivity.OPERATOR
    return sensitivity in allowed_sensitivities(principal)


def filter_documents(
    docs: list[dict[str, Any]],
    principal: Principal,
    *,
    sensitivity_key: str = "sensitivity",
) -> list[dict[str, Any]]:
    """Filter retrieved docs by ACL; deny-by-default on missing/unknown."""
    out: list[dict[str, Any]] = []
    for doc in docs:
        sens = doc.get(sensitivity_key) or (doc.get("metadata") or {}).get(sensitivity_key)
        if sens is None:
            # Infer from fields if missing
            sens = infer_sensitivity(
                severity=str(doc.get("severity") or ""),
                tags=doc.get("tags") or [],
                text=str(doc.get("title") or "") + " " + str(doc.get("snippet") or "")[:400],
            )
            doc = {**doc, sensitivity_key: sens.value if isinstance(sens, DocSensitivity) else sens}
        if is_allowed(principal, sens if isinstance(sens, DocSensitivity) else str(sens)):
            out.append(doc)
    return out


def attach_acl_metadata(
    metadata: dict[str, Any],
    *,
    severity: str = "",
    text: str = "",
    explicit: str | None = None,
) -> dict[str, Any]:
    sens = infer_sensitivity(
        severity=severity or str(metadata.get("severity") or ""),
        tags=metadata.get("tags") or [],
        text=text,
        explicit=explicit or metadata.get("sensitivity"),
    )
    out = dict(metadata)
    out["sensitivity"] = sens.value
    out["acl_version"] = 1
    return out
