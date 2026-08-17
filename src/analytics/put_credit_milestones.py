"""Earned put-credit milestones (EYL-style recognition, ledger-only).

Steals process patterns from options education communities (e.g. earned jackets /
weekly accountability) WITHOUT branding, courses, or profit guarantees:

1. Recognition is *earned* from paired closed put-credit rows only
2. Ladder is process gates, not "1000% returns"
3. System is education/validation — not a signal service
4. Weekly accountability packet is a fixed review ritual

Does NOT submit trades or unlock live capital.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

# Fixed ladder (declared before results — same spirit as research selection rule).
MILESTONE_LADDER: tuple[dict[str, Any], ...] = (
    {
        "id": "m0_started",
        "title": "Foundation",
        "requirement": "At least 1 closed put-credit structure on the paired ledger",
        "n_closed_min": 1,
        "requires_edge_candidate": False,
    },
    {
        "id": "m1_process_ten",
        "title": "Process",
        "requirement": "At least 10 closed put-credit structures (sample building)",
        "n_closed_min": 10,
        "requires_edge_candidate": False,
    },
    {
        "id": "m2_evidence_thirty",
        "title": "Evidence",
        "requirement": "At least 30 closed put-credit structures (kill-criteria sample floor)",
        "n_closed_min": 30,
        "requires_edge_candidate": False,
    },
    {
        "id": "m3_edge_candidate",
        "title": "Edge Candidate",
        "requirement": "n>=30 AND kill verdict EDGE_CANDIDATE (expectancy>0, PF>1, total PnL>0)",
        "n_closed_min": 30,
        "requires_edge_candidate": True,
    },
)

# Risk framework printed on every accountability packet (EYL: risk awareness).
RISK_FRAMEWORK = {
    "family": "spy_put_credit",
    "paper_only": True,
    "lot_size": 1,
    "max_concurrent": 2,
    "max_daily_structures": 3,
    "stop_loss_pct_of_credit": 2.0,
    "take_profit_pct_of_credit": 0.25,
    "exit_dte": 7,
    "not_a_signal_service": True,
    "not_a_profit_guarantee": True,
}


@dataclass(frozen=True)
class MilestoneStatus:
    id: str
    title: str
    requirement: str
    earned: bool
    earned_at: str | None
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _kill_is_edge_candidate(closed_summary: dict[str, Any]) -> bool:
    kill = closed_summary.get("kill_criteria") or {}
    if str(kill.get("verdict") or "") == "EDGE_CANDIDATE":
        return True
    return bool(kill.get("pass_all")) is True


def evaluate_milestones(
    closed_summary: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate earned milestones from cohort closed summary (no side effects)."""
    now = now or datetime.now(UTC)
    n = int(closed_summary.get("closed_n") or 0)
    edge = _kill_is_edge_candidate(closed_summary)
    statuses: list[MilestoneStatus] = []
    for step in MILESTONE_LADDER:
        n_ok = n >= int(step["n_closed_min"])
        edge_ok = (not step["requires_edge_candidate"]) or edge
        earned = bool(n_ok and edge_ok)
        statuses.append(
            MilestoneStatus(
                id=str(step["id"]),
                title=str(step["title"]),
                requirement=str(step["requirement"]),
                earned=earned,
                earned_at=now.isoformat() if earned else None,
                evidence={
                    "n_closed": n,
                    "n_closed_min": step["n_closed_min"],
                    "edge_candidate": edge,
                    "requires_edge_candidate": step["requires_edge_candidate"],
                },
            )
        )

    earned = [s for s in statuses if s.earned]
    next_ms = next((s for s in statuses if not s.earned), None)
    # Highest earned title (EYL "jacket" analogue — process recognition only)
    jacket = earned[-1].title if earned else "None"
    return {
        "schema_version": "put-credit-milestones/1",
        "generated_at": now.isoformat(),
        "earned_count": len(earned),
        "total_count": len(statuses),
        "highest_earned": jacket,
        "milestones": [s.as_dict() for s in statuses],
        "next": next_ms.as_dict() if next_ms else None,
        "honesty": {
            "earned_not_given": True,
            "not_profit_jacket": True,
            "note": (
                "Milestones recognize process evidence on the paired put-credit ledger only. "
                "They do not guarantee returns and do not unlock live capital."
            ),
        },
        "risk_framework": RISK_FRAMEWORK,
    }


def build_weekly_accountability_packet(
    scorecard: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Weekly Investors-Club style packet from an existing cohort scorecard."""
    now = now or datetime.now(UTC)
    closed = scorecard.get("closed") or {}
    open_ = scorecard.get("open") or {}
    progress = scorecard.get("progress") or {}
    honesty = scorecard.get("honesty") or {}
    research = scorecard.get("research_protocol") or {}
    milestones = evaluate_milestones(closed, now=now)

    return {
        "schema_version": "put-credit-weekly-accountability/1",
        "generated_at": now.isoformat(),
        "ritual": "weekly_investors_club_style_review",
        "source": "EYL-style accountability (process only; no signals)",
        "active_family": scorecard.get("active_family"),
        "paper_only": scorecard.get("paper_only"),
        "live_blocked": scorecard.get("live_blocked"),
        "this_week_questions": [
            "Did we follow 1-lot / max concurrent / regime gates?",
            "Any inventory unclean or journal desync?",
            "What is closed_n vs n=30 gate?",
            "Any protocol change? If yes, was it registered under fixed selection rule?",
            "Did we claim profit without EDGE_CANDIDATE? (must be no)",
        ],
        "metrics": {
            "open_n": open_.get("open_n"),
            "closed_n": closed.get("closed_n"),
            "win_rate_pct": closed.get("win_rate_pct"),
            "profit_factor": closed.get("profit_factor"),
            "expectancy": closed.get("expectancy"),
            "total_realized_pnl": closed.get("total_realized_pnl"),
            "kill_verdict": (closed.get("kill_criteria") or {}).get("verdict"),
            "progress_pct_to_gate": progress.get("pct_to_gate"),
            "remaining_to_gate": progress.get("remaining_to_gate"),
        },
        "milestones": milestones,
        "research_protocol": {
            "n_closed": research.get("n_closed"),
            "split_sizes": research.get("split_sizes"),
            "critic_pass": (research.get("critic") or {}).get("pass"),
            "langchain_adopted": research.get("langchain_adopted", False),
        },
        "honesty": honesty,
        "risk_framework": RISK_FRAMEWORK,
        "not_a_signal_service": True,
    }


def render_weekly_markdown(packet: dict[str, Any]) -> str:
    m = packet.get("metrics") or {}
    ms = packet.get("milestones") or {}
    lines = [
        "# Put-credit weekly accountability",
        "",
        f"Generated: `{packet.get('generated_at')}`",
        "",
        "## Ritual questions",
    ]
    for q in packet.get("this_week_questions") or []:
        lines.append(f"- [ ] {q}")
    lines.extend(
        [
            "",
            "## Metrics (ledger)",
            f"- open_n: `{m.get('open_n')}`",
            f"- closed_n: `{m.get('closed_n')}` / 30",
            f"- win_rate_pct: `{m.get('win_rate_pct')}`",
            f"- profit_factor: `{m.get('profit_factor')}`",
            f"- expectancy: `{m.get('expectancy')}`",
            f"- total_realized_pnl: `{m.get('total_realized_pnl')}`",
            f"- kill_verdict: `{m.get('kill_verdict')}`",
            f"- progress_to_gate: `{m.get('progress_pct_to_gate')}%`",
            "",
            f"## Milestones (highest earned: **{ms.get('highest_earned')}**)",
        ]
    )
    for row in ms.get("milestones") or []:
        mark = "x" if row.get("earned") else " "
        lines.append(f"- [{mark}] **{row.get('title')}** — {row.get('requirement')}")
    lines.extend(
        [
            "",
            "## Risk framework",
            f"- paper_only: `{RISK_FRAMEWORK['paper_only']}`",
            f"- lot_size: `{RISK_FRAMEWORK['lot_size']}` max_concurrent: `{RISK_FRAMEWORK['max_concurrent']}`",
            f"- stop: `{RISK_FRAMEWORK['stop_loss_pct_of_credit']}`x credit · TP: `{RISK_FRAMEWORK['take_profit_pct_of_credit']}` · exit_dte: `{RISK_FRAMEWORK['exit_dte']}`",
            "",
            "## Honesty",
            f"- not a signal service: `{packet.get('not_a_signal_service')}`",
            f"- note: {(packet.get('honesty') or {}).get('note')}",
            "",
        ]
    )
    return "\n".join(lines)
