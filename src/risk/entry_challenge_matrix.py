"""Policy-based ordered entry challenges for put-credit validation.

FORMAT steal from Airbnb Flexible Authentication (InfoQ 2026-09-08):
server/policy picks the next challenge instead of scattering client ifs.
We do **not** clone Airbnb auth, OTP flows, or their metrics.

Each challenge is a named gate. Evaluation is fail-closed and ordered:
the first failing challenge is the one agents should surface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Challenge:
    """One policy challenge in the entry matrix."""

    id: str
    title: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChallengeMatrixResult:
    allowed: bool
    challenges: tuple[Challenge, ...]
    first_blocker: str | None
    challenge_count: int
    passed_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "first_blocker": self.first_blocker,
            "challenge_count": self.challenge_count,
            "passed_count": self.passed_count,
            "challenges": [c.to_dict() for c in self.challenges],
        }


# Snapshot keys expected from callers (all optional → fail closed).
Snapshot = dict[str, Any]


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "paper"}
    return default


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _chal_paper_mode(snap: Snapshot) -> Challenge:
    mode = str(snap.get("trading_mode") or snap.get("mode") or "").lower()
    paper = _as_bool(snap.get("paper"), default=False) or mode in {
        "paper",
        "paper_trading",
        "sim",
    }
    return Challenge(
        id="paper_mode",
        title="Paper mode explicit",
        passed=paper,
        detail="paper" if paper else "live_or_missing_mode",
    )


def _chal_kill_switch(snap: Snapshot) -> Challenge:
    family = str(snap.get("active_family") or "").lower()
    if "live_blocked" not in snap or "ic_entries_killed" not in snap:
        return Challenge(
            id="kill_switch",
            title="Kill switch permits put-credit only",
            passed=False,
            detail="kill_switch_state_missing",
        )
    live_blocked = _as_bool(snap.get("live_blocked"), default=False)
    ic_killed = _as_bool(snap.get("ic_entries_killed"), default=False)
    ok = family in {"spy_put_credit", "put_credit", "spy-put-credit"} and live_blocked and ic_killed
    return Challenge(
        id="kill_switch",
        title="Kill switch permits put-credit only",
        passed=ok,
        detail=f"family={family or 'missing'} live_blocked={live_blocked} ic_killed={ic_killed}",
    )


def _chal_inventory(snap: Snapshot) -> Challenge:
    clean = _as_bool(snap.get("inventory_clean"), default=False)
    return Challenge(
        id="inventory_clean",
        title="Open inventory reconciled",
        passed=clean,
        detail="clean" if clean else "UNCLEAN_INVENTORY",
    )


def _chal_regime(snap: Snapshot) -> Challenge:
    ivr = _as_float(snap.get("iv_rank_proxy"))
    min_ivr = _as_float(snap.get("min_iv_rank"), 30.0) or 30.0
    if ivr is None:
        return Challenge(
            id="regime_ivr",
            title="IV rank proxy above minimum",
            passed=False,
            detail="iv_rank_proxy_missing",
        )
    ok = ivr >= min_ivr
    return Challenge(
        id="regime_ivr",
        title="IV rank proxy above minimum",
        passed=ok,
        detail=f"ivr={ivr} min={min_ivr}",
    )


def _chal_lot_size(snap: Snapshot) -> Challenge:
    if "lot_size" not in snap or "max_lot_size" not in snap:
        return Challenge(
            id="lot_size",
            title="One-lot only",
            passed=False,
            detail="lot_size_missing",
        )
    lots = _as_int(snap.get("lot_size"))
    max_lot = _as_int(snap.get("max_lot_size"))
    if lots is None or max_lot is None:
        return Challenge(
            id="lot_size",
            title="One-lot only",
            passed=False,
            detail="lot_size_invalid",
        )
    ok = lots == 1 and max_lot == 1
    return Challenge(
        id="lot_size",
        title="One-lot only",
        passed=ok,
        detail=f"lot_size={lots} max_lot_size={max_lot}",
    )


def _chal_concurrency(snap: Snapshot) -> Challenge:
    if "open_put_credits" not in snap or "max_concurrent_put_credits" not in snap:
        return Challenge(
            id="concurrency",
            title="Under max concurrent put credits",
            passed=False,
            detail="concurrency_limits_missing",
        )
    open_n = _as_int(snap.get("open_put_credits"))
    max_n = _as_int(snap.get("max_concurrent_put_credits"))
    if open_n is None or max_n is None:
        return Challenge(
            id="concurrency",
            title="Under max concurrent put credits",
            passed=False,
            detail="concurrency_limits_invalid",
        )
    # Preserve explicit zero maxima (do not coerce 0 → default).
    ok = open_n < max_n
    return Challenge(
        id="concurrency",
        title="Under max concurrent put credits",
        passed=ok,
        detail=f"open={open_n} max={max_n}",
    )


def _chal_daily_cap(snap: Snapshot) -> Challenge:
    if "structures_today" not in snap or "max_daily_structures" not in snap:
        return Challenge(
            id="daily_cap",
            title="Under max daily structures",
            passed=False,
            detail="daily_cap_missing",
        )
    today = _as_int(snap.get("structures_today"))
    max_day = _as_int(snap.get("max_daily_structures"))
    if today is None or max_day is None:
        return Challenge(
            id="daily_cap",
            title="Under max daily structures",
            passed=False,
            detail="daily_cap_invalid",
        )
    ok = today < max_day
    return Challenge(
        id="daily_cap",
        title="Under max daily structures",
        passed=ok,
        detail=f"today={today} max={max_day}",
    )


_ORDERED: tuple[Callable[[Snapshot], Challenge], ...] = (
    _chal_paper_mode,
    _chal_kill_switch,
    _chal_inventory,
    _chal_regime,
    _chal_lot_size,
    _chal_concurrency,
    _chal_daily_cap,
)


def evaluate_entry_challenges(snapshot: Snapshot | None = None) -> ChallengeMatrixResult:
    """Run the ordered challenge matrix. First failure is the blocker."""

    snap = dict(snapshot or {})
    challenges = tuple(fn(snap) for fn in _ORDERED)
    blocker = next((c.id for c in challenges if not c.passed), None)
    passed_n = sum(1 for c in challenges if c.passed)
    return ChallengeMatrixResult(
        allowed=blocker is None,
        challenges=challenges,
        first_blocker=blocker,
        challenge_count=len(challenges),
        passed_count=passed_n,
    )
