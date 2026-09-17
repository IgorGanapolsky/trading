#!/usr/bin/env python3
"""TypeSafe System One claim gate (FORMAT steal — not a TypeSafe product clone).

Confidence-gated routing over typed questions:
  - Noul: is the claim supported by the supplied facts?
  - Choice: allow | abstain | deny
  - Score: how harmful if asserted as true?

Offline mode (--offline or missing key) uses deterministic ledger heuristics so
CI and paper-lab honesty gates never depend on a live paid hop.

Stolen patterns: docs.typesafe.ai confidence-routing + llm_guardrails cookbooks.
Console entry: console.typesafe.ai/hook (signed-in operator session).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.typesafe_client import (  # noqa: E402
    DEFAULT_MODEL,
    load_api_key,
    system_one,
)

EDGE_CLAIM_RE = re.compile(
    r"\b(profitab|expectancy|profit factor|edge|validated|proven|"
    r"beat the market|positive expectancy|pf\s*>\s*1)\b",
    re.IGNORECASE,
)

QUESTIONS = {
    "claim_supported": {
        "type": "noul",
        "instructions": (
            "Given only the facts object, is the claim supported by evidence? "
            "Treat missing sample size, live_blocked, or zero closed trades as "
            "not supporting profitability or edge claims."
        ),
    },
    "action": {
        "type": "choice",
        "instructions": "What should the trading agent do with this claim?",
        "criteria": {
            "allow": "Claim is evidenced; safe to state as fact",
            "abstain": "Evidence missing or insufficient; say verifying/unknown",
            "deny": "Claim contradicts known facts; refuse it",
        },
    },
    "severity": {
        "type": "score",
        "instructions": (
            "How harmful would it be if an agent asserted this claim as true "
            "to the operator?"
        ),
        "criteria": [
            "Harmless wording drift",
            "Misleading but reversible",
            "Trust-breaking false edge claim",
        ],
    },
}


def load_trading_facts(repo_root: Path | None = None) -> dict[str, Any]:
    """Best-effort facts from local ledgers (never invents profitability)."""
    root = repo_root or ROOT
    facts: dict[str, Any] = {
        "active_family": "spy_put_credit",
        "paper_only": True,
        "live_blocked": True,
        "paired_buffett_closes": None,
        "source_files": [],
    }

    kill = root / "data" / "runtime" / "strategy_kill_switch.json"
    if kill.exists():
        try:
            data = json.loads(kill.read_text(encoding="utf-8"))
            facts["active_family"] = data.get("active_family") or facts["active_family"]
            facts["paper_only"] = bool(data.get("paper_only", True))
            facts["live_blocked"] = bool(data.get("live_blocked", True))
            facts["source_files"].append(str(kill.relative_to(root)))
        except (OSError, json.JSONDecodeError):
            pass

    trades = root / "data" / "trades.json"
    if trades.exists():
        try:
            data = json.loads(trades.read_text(encoding="utf-8"))
            rows = data.get("trades") if isinstance(data, dict) else data
            if isinstance(rows, list):
                buffett = [
                    r
                    for r in rows
                    if isinstance(r, dict)
                    and str(r.get("profile_name") or r.get("profile") or "")
                    .lower()
                    .find("buffett")
                    >= 0
                    and r.get("status") in (None, "closed", "CLOSED")
                ]
                # Prefer explicit closed marker when present
                closed = [
                    r
                    for r in buffett
                    if str(r.get("status") or "closed").lower() == "closed"
                    or r.get("exit_time")
                    or r.get("closed_at")
                ]
                facts["paired_buffett_closes"] = len(closed or buffett)
                facts["source_files"].append(str(trades.relative_to(root)))
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    entries = root / "data" / "put_credit_entries.json"
    if entries.exists() and facts["paired_buffett_closes"] is None:
        try:
            data = json.loads(entries.read_text(encoding="utf-8"))
            rows = data if isinstance(data, list) else data.get("entries") or []
            closed = [
                r
                for r in rows
                if isinstance(r, dict)
                and str(r.get("status") or "").lower() in {"closed", "exited"}
            ]
            facts["paired_buffett_closes"] = len(closed)
            facts["source_files"].append(str(entries.relative_to(root)))
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    if facts["paired_buffett_closes"] is None:
        facts["paired_buffett_closes"] = 0
    return facts


def offline_decide(claim: str, facts: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic confidence-style decision without calling TypeSafe."""
    n = int(facts.get("paired_buffett_closes") or 0)
    live_blocked = bool(facts.get("live_blocked", True))
    looks_like_edge = bool(EDGE_CLAIM_RE.search(claim))

    if looks_like_edge and (n < 30 or live_blocked):
        action = "deny"
        supported = 0.03
        severity = 1.99
        confidence = 0.85
        reason = (
            f"edge/profit claim with paired_buffett_closes={n} (<30) "
            f"and live_blocked={live_blocked}"
        )
    elif looks_like_edge and n >= 30:
        action = "abstain"
        supported = 0.45
        severity = 1.2
        confidence = 0.55
        reason = (
            "sample may be large enough but offline gate cannot certify "
            "expectancy/PF without live TypeSafe + ledger metrics"
        )
    else:
        action = "abstain"
        supported = 0.4
        severity = 0.6
        confidence = 0.5
        reason = "offline mode: non-edge claim defaults to abstain"

    return {
        "ok": action == "allow",
        "mode": "offline",
        "stolen_format": "typesafe confidence-gated routing (not a clone)",
        "claim": claim,
        "facts": dict(facts),
        "action": action,
        "confidence": confidence,
        "claim_supported_noul": supported,
        "severity_score": severity,
        "reason": reason,
        "answers": {
            "claim_supported": {"type": "noul", "noul": supported},
            "action": {
                "type": "choice",
                "choice": action,
                "confidence": confidence,
                "probabilities": {
                    "allow": 1.0 if action == "allow" else 0.0,
                    "abstain": 1.0 if action == "abstain" else 0.0,
                    "deny": 1.0 if action == "deny" else 0.0,
                },
            },
            "severity": {
                "type": "score",
                "score": severity,
                "confidence": confidence,
            },
        },
        "gate": (
            "ALLOW"
            if action == "allow"
            else ("DENY: refuse false edge claim" if action == "deny" else "ABSTAIN: verifying")
        ),
        "evaluated_at": datetime.now(UTC).isoformat(),
    }


def apply_confidence_routing(
    *,
    action: str,
    confidence: float | None,
    min_confidence: float,
    claim_supported_noul: float | None = None,
    severity_score: float | None = None,
) -> str:
    """Compose answers in code (TypeSafe confidence-routing + severity).

    - Low confidence on allow → abstain
    - Unsupported claim (noul low) + high harm score → deny
    """
    routed = action
    if (
        claim_supported_noul is not None
        and severity_score is not None
        and claim_supported_noul < 0.2
        and severity_score >= 1.5
    ):
        routed = "deny"
    if confidence is None:
        return routed
    if confidence < min_confidence and routed == "allow":
        return "abstain"
    return routed


def online_decide(
    claim: str,
    facts: Mapping[str, Any],
    *,
    api_key: str,
    model: str = DEFAULT_MODEL,
    min_confidence: float = 0.6,
) -> dict[str, Any]:
    state = {"claim": claim, "facts": dict(facts)}
    body = system_one(state=state, questions=QUESTIONS, api_key=api_key, model=model)
    answers = body.get("answers") or {}
    action_ans = answers.get("action") or {}
    action = str(action_ans.get("choice") or "abstain")
    confidence = action_ans.get("confidence")
    try:
        confidence_f = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_f = None
    noul_raw = (answers.get("claim_supported") or {}).get("noul")
    severity_raw = (answers.get("severity") or {}).get("score")
    try:
        noul = float(noul_raw) if noul_raw is not None else None
    except (TypeError, ValueError):
        noul = None
    try:
        severity = float(severity_raw) if severity_raw is not None else None
    except (TypeError, ValueError):
        severity = None
    routed = apply_confidence_routing(
        action=action,
        confidence=confidence_f,
        min_confidence=min_confidence,
        claim_supported_noul=noul,
        severity_score=severity,
    )
    return {
        "ok": routed == "allow",
        "mode": "online",
        "stolen_format": "typesafe confidence-gated routing (not a clone)",
        "model": body.get("model") or model,
        "claim": claim,
        "facts": dict(facts),
        "action": routed,
        "raw_action": action,
        "confidence": confidence_f,
        "min_confidence": min_confidence,
        "claim_supported_noul": noul,
        "severity_score": severity,
        "answers": answers,
        "usage": body.get("usage"),
        "gate": (
            "ALLOW"
            if routed == "allow"
            else (
                "DENY: refuse false edge claim"
                if routed == "deny"
                else "ABSTAIN: verifying"
            )
        ),
        "evaluated_at": datetime.now(UTC).isoformat(),
    }


def decide(
    claim: str,
    *,
    offline: bool = False,
    repo_root: Path | None = None,
    facts: Mapping[str, Any] | None = None,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    min_confidence: float = 0.6,
) -> dict[str, Any]:
    facts_obj = dict(facts) if facts is not None else load_trading_facts(repo_root)
    key = api_key if api_key is not None else load_api_key()
    if offline or not key:
        result = offline_decide(claim, facts_obj)
        if not key and not offline:
            result["note"] = "TYPESAFE_API_KEY missing; used offline heuristic"
        return result
    return online_decide(
        claim,
        facts_obj,
        api_key=key,
        model=model,
        min_confidence=min_confidence,
    )


def _exit_for_action(action: str) -> int:
    if action == "allow":
        return 0
    if action == "deny":
        return 3
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim", required=True, help="Operator-facing claim to gate")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Force deterministic local heuristic (no API)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Confidence floor for allow (TypeSafe second axis)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Ledger root (default: repository root)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args(argv)

    result = decide(
        args.claim,
        offline=args.offline,
        repo_root=args.repo_root,
        model=args.model,
        min_confidence=args.min_confidence,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    return _exit_for_action(str(result.get("action") or "abstain"))


if __name__ == "__main__":
    raise SystemExit(main())
