"""Micro-capital deployment gate (feat/live-micro-trade-cap).

Owns the rule that turns Igor's directive into code:

  "start trading very small (as small as possible); as I deposit more money,
   we can trade more."

This is the sizing + safety gate for the *equity fractional DCA* path
(SCHD via mercury_income_loop / DividendGrowthStrategy) — the only surface
that can trade at all under ~$500. Options (spy_put_credit) are hard-excluded
here by construction: option contracts bind ~$500+ collateral each, so a
sub-$500 account physically cannot open options. This gate refuses to deploy
into them and records why.

Design rules (Karpathy-simple on purpose):

  * micro=True -> we deploy only when the available surplus EXCEEDS a small
    hard floor. The deployable amount is `min(surplus, deposit_fraction *
    balance)`. Both are tiny by default so "as small as possible".
  * As Igor deposits more, `surplus` grows -> deployable grows. This is the
    literal "deposit more, trade more" curve with no magic knobs.
  * A hard LIVE cap (`live_cap_usd`) bounds the single-transfer amount; it
    gates live mode only, never paper. Intentionally no secret-shuffling:
    real money still requires existing Mercury/Alpaca live credentials and
    MERCURY_LIVE_TRANSFERS_ENABLED=1 (see src/adapters/bank_adapter.py).

Everything here is pure/deterministic so it is unit-testable and safe to
call from cron. No network, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_HARD_FLOOR_USD = 25.0  # keep a small buffer in Mercury; trade the surplus
DEFAULT_DEPLOY_FRACTION = 0.10  # deploy at most 10% of balance per cycle
DEFAULT_LIVE_CAP_USD = 50.0  # single live transfer never exceeds $50 (honeypot)
DEFAULT_UNIVERSE = ("SCHD",)  # match DividendGrowthStrategy.DEFAULT_UNIVERSE


@dataclass(frozen=True)
class MicroCapDecision:
    """Result of running the deploy gate against a bank balance."""

    available_balance_usd: float
    hard_floor_usd: float
    deploy_fraction: float
    live_cap_usd: float
    deployable_usd: float
    deployable_symbols: tuple[str, ...]
    blocked_reason: str | None = None

    @property
    def can_deploy(self) -> bool:
        return self.deployable_usd > 0 and self.blocked_reason is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "balance_usd": round(self.available_balance_usd, 2),
            "deployable_usd": round(self.deployable_usd, 2),
            "deployable": self.can_deploy,
            "deployable_symbols": list(self.deployable_symbols),
            "blocked_reason": self.blocked_reason,
        }


def compute_micro_cap(
    balance_usd: float,
    *,
    hard_floor_usd: float = DEFAULT_HARD_FLOOR_USD,
    deploy_fraction: float = DEFAULT_DEPLOY_FRACTION,
    live_cap_usd: float = DEFAULT_LIVE_CAP_USD,
    universe: tuple[str, ...] = DEFAULT_UNIVERSE,
) -> MicroCapDecision:
    """Decide how much (if any) to deploy from `balance_usd`.

    Pure function: no I/O, no network, no global state. Callers (the CLI or
    any orchestrator) are responsible for actually moving money only after
    checking `.can_deploy` AND their own live-credential check.
    """
    if balance_usd <= 0:
        return MicroCapDecision(
            available_balance_usd=balance_usd,
            hard_floor_usd=hard_floor_usd,
            deploy_fraction=deploy_fraction,
            live_cap_usd=live_cap_usd,
            deployable_usd=0.0,
            deployable_symbols=tuple(),
            blocked_reason="balance is non-positive",
        )

    surplus = balance_usd - hard_floor_usd
    if surplus <= 0:
        return MicroCapDecision(
            available_balance_usd=balance_usd,
            hard_floor_usd=hard_floor_usd,
            deploy_fraction=deploy_fraction,
            live_cap_usd=live_cap_usd,
            deployable_usd=0.0,
            deployable_symbols=tuple(),
            blocked_reason=(
                f"balance ${balance_usd:.2f} is at/below the ${hard_floor_usd:.2f} "
                "hard floor; keep the buffer and wait for the next deposit"
            ),
        )

    # Deploy the smaller of (fraction of surplus) vs the hard live cap.
    # This guarantees "as small as possible" at every balance level and keeps
    # a single transfer bounded in live mode.
    deployable = min(surplus * deploy_fraction, live_cap_usd)
    return MicroCapDecision(
        available_balance_usd=balance_usd,
        hard_floor_usd=hard_floor_usd,
        deploy_fraction=deploy_fraction,
        live_cap_usd=live_cap_usd,
        deployable_usd=max(0.0, deployable),
        deployable_symbols=universe,
    )


def options_require_larger_capital() -> str:
    """Human-readable reason options are excluded from micro trading."""
    return (
        "options require ~$500+ collateral per contract, so a sub-$500 account "
        "cannot open an option leg; options are only reachable after the equity "
        "DCA prove-out and a live account above $500"
    )
