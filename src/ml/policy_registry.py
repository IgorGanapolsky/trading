"""Deterministic policy registry for learned-trading policy metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional


def _to_utc_datetime(value: Any) -> datetime:
    """Normalize supported inputs to timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
    else:
        raise TypeError(f"Unsupported datetime value type: {type(value)!r}")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class PolicyMetadata:
    """Metadata required to judge whether a policy is usable in production."""

    version: str
    trained_at: datetime
    trades_trained_on: int
    max_age_days: int
    min_trades_required: int

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        default_max_age_days: int,
        default_min_trades_required: int,
    ) -> PolicyMetadata:
        trained_at_raw = payload.get("trained_at")
        if trained_at_raw is None:
            raise ValueError("Policy metadata missing required field: trained_at")
        return cls(
            version=str(payload.get("version", "unknown")),
            trained_at=_to_utc_datetime(trained_at_raw),
            trades_trained_on=int(payload.get("trades_trained_on", 0)),
            max_age_days=int(payload.get("max_age_days", default_max_age_days)),
            min_trades_required=int(
                payload.get("min_trades_required", default_min_trades_required)
            ),
        )

    def age_days(self, *, as_of: Optional[datetime] = None) -> int:
        now = _to_utc_datetime(as_of or datetime.now(timezone.utc))
        if now < self.trained_at:
            return 0
        delta: timedelta = now - self.trained_at
        return delta.days

    def is_fresh(self, *, as_of: Optional[datetime] = None) -> bool:
        return self.age_days(as_of=as_of) <= self.max_age_days

    def has_sufficient_samples(self) -> bool:
        return self.trades_trained_on >= self.min_trades_required


class PolicyRegistry:
    """In-memory deterministic registry keyed by policy name."""

    def __init__(
        self,
        *,
        entries: Optional[Mapping[str, Mapping[str, Any]]] = None,
        default_max_age_days: int = 7,
        default_min_trades_required: int = 30,
    ) -> None:
        self.default_max_age_days = int(default_max_age_days)
        self.default_min_trades_required = int(default_min_trades_required)
        self._entries: dict[str, PolicyMetadata] = {}
        if entries:
            for policy_name, payload in entries.items():
                self.upsert(policy_name, payload)

    def upsert(self, policy_name: str, payload: Mapping[str, Any]) -> PolicyMetadata:
        metadata = PolicyMetadata.from_mapping(
            payload,
            default_max_age_days=self.default_max_age_days,
            default_min_trades_required=self.default_min_trades_required,
        )
        self._entries[policy_name] = metadata
        return metadata

    def get(self, policy_name: str) -> Optional[PolicyMetadata]:
        return self._entries.get(policy_name)

    def status(self, policy_name: str, *, as_of: Optional[datetime] = None) -> dict[str, Any]:
        metadata = self.get(policy_name)
        if metadata is None:
            return {
                "policy_name": policy_name,
                "exists": False,
                "is_fresh": False,
                "age_days": None,
                "version": None,
                "trades_trained_on": 0,
                "max_age_days": self.default_max_age_days,
                "min_trades_required": self.default_min_trades_required,
                "sufficient_samples": False,
            }

        return {
            "policy_name": policy_name,
            "exists": True,
            "is_fresh": metadata.is_fresh(as_of=as_of),
            "age_days": metadata.age_days(as_of=as_of),
            "version": metadata.version,
            "trades_trained_on": metadata.trades_trained_on,
            "max_age_days": metadata.max_age_days,
            "min_trades_required": metadata.min_trades_required,
            "sufficient_samples": metadata.has_sufficient_samples(),
        }

    def to_dict(self) -> dict[str, dict[str, Any]]:
        serialized: dict[str, dict[str, Any]] = {}
        for policy_name, meta in self._entries.items():
            serialized[policy_name] = {
                "version": meta.version,
                "trained_at": meta.trained_at.isoformat(),
                "trades_trained_on": meta.trades_trained_on,
                "max_age_days": meta.max_age_days,
                "min_trades_required": meta.min_trades_required,
            }
        return serialized
