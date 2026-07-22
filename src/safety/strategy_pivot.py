"""Evidence-first strategy retirement and broker compatibility decisions.

The trading system must distinguish three questions that were previously
conflated:

* Does the strategy have a measured edge?
* Is the trade ledger trustworthy enough to measure that edge?
* Can the selected broker execute the strategy as designed?

This module is intentionally read-only.  It produces a fail-closed decision
that callers can use before opening new risk while allowing existing position
management to continue.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

OPTION_SYMBOL = re.compile(r"^(?P<root>[A-Z]+)(?P<expiry>\d{6})[CP]\d{8}$")


@dataclass(frozen=True)
class ValidationThresholds:
    """Minimum evidence required before a candidate may open paper risk."""

    min_closed_trades: int = 30
    min_expectancy_per_trade: float = 1.0
    min_profit_factor: float = 1.05
    min_total_realized_pnl: float = 1.0
    max_drawdown_pct: float = 10.0


DEFAULT_VALIDATION_THRESHOLDS = ValidationThresholds()


@dataclass(frozen=True)
class StrategyEvidence:
    """Comparable performance evidence for one exact rule set."""

    closed_trades: int
    expectancy_per_trade: float
    profit_factor: float
    total_realized_pnl: float
    max_drawdown_pct: float | None = None


@dataclass(frozen=True)
class LedgerAudit:
    """Structural checks that must pass before performance is trusted."""

    clean: bool
    issues: tuple[str, ...]
    raw_trade_rows: int
    reported_closed_trades: int
    unpaired_order_count: int
    attribution_clean: bool = True
    open_inventory_clean: bool = True


@dataclass(frozen=True)
class StrategyDecision:
    """Decision for the incumbent or a candidate strategy."""

    status: str
    may_open_new_positions: bool
    may_manage_existing_positions: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class BrokerSnapshot:
    """Observed account state plus documented API capabilities."""

    broker: str
    observed_at: str
    authenticated_web_session: bool
    funded: bool
    equity_usd: float
    api_key_configured: bool
    options_level: int
    supports_market_data: bool
    supports_equities: bool
    supports_single_leg_options: bool
    supports_multi_leg_options: bool
    paper_trading_verified: bool

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> BrokerSnapshot:
        account = payload.get("account", {})
        capabilities = payload.get("api_capabilities", {})
        return cls(
            broker=str(payload.get("broker", "unknown")),
            observed_at=str(payload.get("observed_at", "unknown")),
            authenticated_web_session=bool(account.get("authenticated_web_session", False)),
            funded=bool(account.get("funded", False)),
            equity_usd=float(account.get("equity_usd", 0.0) or 0.0),
            api_key_configured=bool(account.get("api_key_configured", False)),
            options_level=int(account.get("options_level", 0) or 0),
            supports_market_data=bool(capabilities.get("market_data", False)),
            supports_equities=bool(capabilities.get("equities", False)),
            supports_single_leg_options=bool(capabilities.get("single_leg_options", False)),
            supports_multi_leg_options=bool(capabilities.get("multi_leg_options", False)),
            paper_trading_verified=bool(capabilities.get("paper_trading_verified", False)),
        )


@dataclass(frozen=True)
class BrokerAssessment:
    """Whether a broker is useful for research and eligible for execution."""

    research_eligible: bool
    execution_eligible: bool
    blockers: tuple[str, ...]


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def audit_strategy_ledger(
    system_state: dict[str, Any],
    trades_data: dict[str, Any],
    ic_entries: dict[str, Any],
    *,
    symbol_root: str = "SPY",
) -> LedgerAudit:
    """Detect unpaired fills and open structures missing unique journal rows."""

    stats = trades_data.get("stats", {}) if isinstance(trades_data, dict) else {}
    raw_trades = trades_data.get("trades", []) if isinstance(trades_data, dict) else []
    raw_count = len(raw_trades) if isinstance(raw_trades, list) else 0
    reported_closed = _as_int(stats.get("closed_trades"), raw_count)
    unpaired_count = _as_int(stats.get("unpaired_order_count"), 0)
    issues: list[str] = []
    attribution_clean = True
    open_inventory_clean = True

    if unpaired_count > 0:
        attribution_clean = False
        issues.append(
            f"Trade ledger contains {unpaired_count} unpaired orders; cohort attribution is not clean."
        )

    if reported_closed != raw_count + unpaired_count:
        attribution_clean = False
        issues.append(
            "Reported closed-trade count does not reconcile to raw rows plus unpaired orders "
            f"({reported_closed} != {raw_count} + {unpaired_count})."
        )

    positions = system_state.get("performance", {}).get("open_positions", [])
    option_legs_by_expiry: dict[str, int] = {}
    if isinstance(positions, list):
        for position in positions:
            if not isinstance(position, dict):
                continue
            match = OPTION_SYMBOL.match(str(position.get("symbol", "")))
            if not match or match.group("root") != symbol_root:
                continue
            quantity = abs(_as_float(position.get("quantity"), 0.0))
            option_legs_by_expiry[match.group("expiry")] = option_legs_by_expiry.get(
                match.group("expiry"), 0
            ) + int(round(quantity))

    entry_keys = list(ic_entries) if isinstance(ic_entries, dict) else []
    for expiry, leg_contracts in sorted(option_legs_by_expiry.items()):
        if leg_contracts % 4:
            open_inventory_clean = False
            issues.append(
                f"Open {symbol_root} {expiry} exposure has {leg_contracts} leg-contracts, "
                "which cannot be partitioned into four-leg iron condors."
            )
            continue
        open_structures = leg_contracts // 4
        matching_entries = sum(1 for key in entry_keys if str(key).endswith(expiry))
        if matching_entries < open_structures:
            open_inventory_clean = False
            issues.append(
                f"Open {symbol_root} {expiry} exposure represents {open_structures} structures "
                f"but the journal has {matching_entries} expiry-keyed record(s); an entry was "
                "overwritten or never recorded."
            )

    return LedgerAudit(
        clean=not issues,
        issues=tuple(issues),
        raw_trade_rows=raw_count,
        reported_closed_trades=reported_closed,
        unpaired_order_count=unpaired_count,
        attribution_clean=attribution_clean,
        open_inventory_clean=open_inventory_clean,
    )


def incumbent_evidence(
    system_state: dict[str, Any], trades_data: dict[str, Any]
) -> StrategyEvidence:
    """Read the canonical lifetime ledger, falling back to trades.json stats."""

    weekly_gate = system_state.get("north_star_weekly_gate", {})
    ledger = weekly_gate.get("lifetime_ledger", {}) if isinstance(weekly_gate, dict) else {}
    if not isinstance(ledger, dict) or not ledger:
        ledger = trades_data.get("stats", {}) if isinstance(trades_data, dict) else {}

    drawdown = system_state.get("paper_account", {}).get("total_pl_pct")
    return StrategyEvidence(
        closed_trades=_as_int(ledger.get("closed_trades"), 0),
        expectancy_per_trade=_as_float(
            ledger.get("expectancy_per_trade", ledger.get("expectancy")), 0.0
        ),
        profit_factor=_as_float(ledger.get("profit_factor"), 0.0),
        total_realized_pnl=_as_float(
            ledger.get("total_realized_pnl", ledger.get("total_pnl")), 0.0
        ),
        max_drawdown_pct=abs(_as_float(drawdown)) if drawdown is not None else None,
    )


def evaluate_strategy(
    evidence: StrategyEvidence,
    ledger_audit: LedgerAudit,
    thresholds: ValidationThresholds = DEFAULT_VALIDATION_THRESHOLDS,
) -> StrategyDecision:
    """Fail closed when the edge is negative, incomplete, or untrustworthy."""

    reasons = list(ledger_audit.issues)
    enough_trades = evidence.closed_trades >= thresholds.min_closed_trades
    failed_edge = enough_trades and (
        evidence.expectancy_per_trade < thresholds.min_expectancy_per_trade
        or evidence.profit_factor < thresholds.min_profit_factor
        or evidence.total_realized_pnl < thresholds.min_total_realized_pnl
    )

    if failed_edge:
        reasons.append(
            "Measured lifetime edge failed the retirement floor: "
            f"{evidence.closed_trades} closes, expectancy ${evidence.expectancy_per_trade:.2f}, "
            f"profit factor {evidence.profit_factor:.2f}, realized P/L "
            f"${evidence.total_realized_pnl:.2f}."
        )
        return StrategyDecision(
            status="RETIRE_NEW_ENTRIES",
            may_open_new_positions=False,
            may_manage_existing_positions=True,
            reasons=tuple(reasons),
        )

    if not ledger_audit.clean:
        reasons.append("Performance cannot be promoted until the ledger is reconciled.")
        return StrategyDecision(
            status="BLOCKED_DATA_INTEGRITY",
            may_open_new_positions=False,
            may_manage_existing_positions=True,
            reasons=tuple(reasons),
        )

    if not enough_trades:
        reasons.append(
            f"Only {evidence.closed_trades}/{thresholds.min_closed_trades} clean paper trades exist."
        )
        return StrategyDecision(
            status="PAPER_VALIDATION_ONLY",
            may_open_new_positions=True,
            may_manage_existing_positions=True,
            reasons=tuple(reasons),
        )

    if evidence.max_drawdown_pct is not None and (
        evidence.max_drawdown_pct > thresholds.max_drawdown_pct
    ):
        reasons.append(
            f"Drawdown {evidence.max_drawdown_pct:.2f}% exceeds {thresholds.max_drawdown_pct:.2f}%."
        )
        return StrategyDecision(
            status="REJECT_DRAWDOWN",
            may_open_new_positions=False,
            may_manage_existing_positions=True,
            reasons=tuple(reasons),
        )

    reasons.append("All clean-sample promotion thresholds passed.")
    return StrategyDecision(
        status="PAPER_VALIDATED",
        may_open_new_positions=True,
        may_manage_existing_positions=True,
        reasons=tuple(reasons),
    )


def assess_broker(snapshot: BrokerSnapshot, requirements: dict[str, Any]) -> BrokerAssessment:
    """Check documented broker capability separately from strategy evidence."""

    blockers: list[str] = []
    asset_class = str(requirements.get("asset_class", "equity")).lower()
    legs = max(1, _as_int(requirements.get("legs"), 1))
    minimum_options_level = _as_int(requirements.get("minimum_options_level"), 0)
    requires_paper = bool(requirements.get("requires_paper_trading", True))

    if not snapshot.api_key_configured:
        blockers.append("No broker API key is configured.")
    if not snapshot.funded:
        blockers.append("The account is unfunded.")
    if requires_paper and not snapshot.paper_trading_verified:
        blockers.append("Paper-trading API support has not been verified.")

    if asset_class == "equity":
        if not snapshot.supports_equities:
            blockers.append("The API does not support equity execution.")
    elif asset_class == "option":
        if snapshot.options_level < minimum_options_level:
            blockers.append(
                f"Account options level {snapshot.options_level} is below required level "
                f"{minimum_options_level}."
            )
        if legs == 1 and not snapshot.supports_single_leg_options:
            blockers.append("The API does not support single-leg option execution.")
        if legs > 1 and not snapshot.supports_multi_leg_options:
            blockers.append("The API does not support atomic multi-leg option execution.")
    else:
        blockers.append(f"Unknown asset class: {asset_class}.")

    research_eligible = bool(snapshot.authenticated_web_session and snapshot.supports_market_data)
    return BrokerAssessment(
        research_eligible=research_eligible,
        execution_eligible=not blockers,
        blockers=tuple(blockers),
    )


def build_pivot_report(
    system_state: dict[str, Any],
    trades_data: dict[str, Any],
    ic_entries: dict[str, Any],
    tournament: dict[str, Any],
    broker_payload: dict[str, Any],
    inventory_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the auditable North Star and strategy-tournament decision."""

    thresholds = ValidationThresholds(**tournament.get("promotion_thresholds", {}))
    audit = audit_strategy_ledger(system_state, trades_data, ic_entries)
    evidence = incumbent_evidence(system_state, trades_data)
    incumbent = evaluate_strategy(evidence, audit, thresholds)
    broker = BrokerSnapshot.from_payload(broker_payload)
    inventory_evidence = inventory_payload if isinstance(inventory_payload, dict) else {}
    reconstruction = inventory_evidence.get("reconstruction", {})
    operational_inventory_clean = bool(
        inventory_evidence.get("clean") is True
        and inventory_evidence.get("authority") == "broker_filled_mleg_orders"
        and isinstance(reconstruction, dict)
        and not reconstruction.get("unresolved")
        and _as_int(reconstruction.get("pending_option_orders"), -1) == 0
    )

    candidates: list[dict[str, Any]] = []
    any_validated_candidate = False
    for candidate in tournament.get("candidates", []):
        candidate_evidence_payload = candidate.get("evidence", {})
        candidate_evidence = StrategyEvidence(
            closed_trades=_as_int(candidate_evidence_payload.get("closed_trades"), 0),
            expectancy_per_trade=_as_float(
                candidate_evidence_payload.get("expectancy_per_trade"), 0.0
            ),
            profit_factor=_as_float(candidate_evidence_payload.get("profit_factor"), 0.0),
            total_realized_pnl=_as_float(candidate_evidence_payload.get("total_realized_pnl"), 0.0),
            max_drawdown_pct=(
                _as_float(candidate_evidence_payload.get("max_drawdown_pct"))
                if candidate_evidence_payload.get("max_drawdown_pct") is not None
                else None
            ),
        )
        candidate_audit = LedgerAudit(
            clean=bool(candidate_evidence_payload.get("ledger_clean", True)),
            issues=tuple(candidate_evidence_payload.get("ledger_issues", [])),
            raw_trade_rows=candidate_evidence.closed_trades,
            reported_closed_trades=candidate_evidence.closed_trades,
            unpaired_order_count=0,
            attribution_clean=bool(candidate_evidence_payload.get("ledger_clean", True)),
            open_inventory_clean=True,
        )
        decision = evaluate_strategy(candidate_evidence, candidate_audit, thresholds)
        broker_assessment = assess_broker(broker, candidate.get("broker_requirements", {}))
        any_validated_candidate = any_validated_candidate or (decision.status == "PAPER_VALIDATED")
        candidates.append(
            {
                "strategy_id": candidate.get("strategy_id"),
                "active_paper_candidate": (
                    candidate.get("strategy_id") == tournament.get("active_paper_candidate_id")
                ),
                "hypothesis": candidate.get("hypothesis"),
                "rules": candidate.get("rules", {}),
                "evidence": asdict(candidate_evidence),
                "decision": asdict(decision),
                "broker_assessment": asdict(broker_assessment),
            }
        )

    paper_account = system_state.get("paper_account", {})
    starting_balance = _as_float(paper_account.get("starting_balance"), 100_000.0)
    equity = _as_float(paper_account.get("equity", paper_account.get("current_equity")), 0.0)
    total_pl = _as_float(paper_account.get("total_pl"), equity - starting_balance)
    on_course = bool(incumbent.status == "PAPER_VALIDATED" and total_pl > 0 and audit.clean)

    active_paper_candidate = next(
        (candidate for candidate in candidates if candidate["active_paper_candidate"]), None
    )
    if not operational_inventory_clean:
        system_action = "RECONCILE_INVENTORY_MANAGE_EXITS_ONLY"
        research_action = "PAPER_VALIDATE_SUCCESSOR_AFTER_BROKER_INVENTORY_CLEAN"
    elif any_validated_candidate:
        system_action = "PAPER_TRADE_VALIDATED_CANDIDATE"
        research_action = "CONTINUE_CONTROLLED_PAPER_VALIDATION"
    elif active_paper_candidate and (
        active_paper_candidate["decision"]["status"] == "PAPER_VALIDATION_ONLY"
    ):
        system_action = "RETIRE_INCUMBENT_PAPER_VALIDATE_SUCCESSOR"
        research_action = "RUN_ACTIVE_SUCCESSOR_PAPER_COHORT"
    else:
        system_action = "EXIT_ONLY_STAY_FLAT"
        research_action = "SELECT_AND_SPECIFY_PAPER_CANDIDATE"
    return {
        "system_action": system_action,
        "research_action": research_action,
        "north_star": {
            "on_course": on_course,
            "starting_balance": starting_balance,
            "current_equity": equity,
            "total_pl": total_pl,
            "drawdown_pct": abs(_as_float(paper_account.get("total_pl_pct"), 0.0)),
            "reason": (
                "No clean, validated positive-expectancy strategy is currently available."
                if not on_course
                else "Incumbent has clean positive evidence and positive paper P/L."
            ),
        },
        "incumbent": {
            "strategy_id": tournament.get("incumbent_strategy_id", "ic_simple"),
            "evidence": asdict(evidence),
            "ledger_audit": asdict(audit),
            "decision": asdict(incumbent),
        },
        "operational_inventory": {
            "clean": operational_inventory_clean,
            "authority": inventory_evidence.get("authority", "unverified"),
            "audited_at": inventory_evidence.get("audited_at"),
            "reconstruction": reconstruction if isinstance(reconstruction, dict) else {},
            "note": (
                "Broker inventory can be operationally clean while the legacy journal and "
                "performance attribution remain unclean."
            ),
        },
        "broker": {
            "snapshot": asdict(broker),
            "current_role": "RESEARCH_ONLY",
            "reason": (
                "Authenticated market research is available, but account and API execution "
                "requirements are not satisfied."
            ),
        },
        "promotion_thresholds": asdict(thresholds),
        "candidates": candidates,
    }
