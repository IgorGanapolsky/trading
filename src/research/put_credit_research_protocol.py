"""Put-credit research protocol (freeCodeCamp Deep Agents handbook — high-ROI only).

Maps the handbook's anti-overfitting design onto spy_put_credit WITHOUT LangChain,
EODHD, or agent-written strategies:

1. Deterministic evaluation owns evidence (paired ledger metrics only)
2. Fixed selection rule declared before looking at challenger results
3. Append-only experiment registry (failures recorded, no silent drop)
4. Train/validation split for protocol *comparison*; holdout locked until freeze
5. Agents/humans may propose protocol variants; they never rewrite metrics

Does NOT submit trades. Does NOT claim edge. Live remains kill-switch blocked.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Fixed BEFORE any protocol variant is judged (handbook § selection rule).
SELECTION_RULE_TEXT = """
# Put-credit protocol selection rule (fixed)

A challenger protocol replaces the incumbent champion only if ALL of the following hold
on the **validation** slice of closed put-credit trades (not development, not holdout):

1. Validation expectancy is not worse than the incumbent's
2. Validation profit factor is not worse than the incumbent's (when both defined)
3. Validation total realized P/L is not worse than the incumbent's
4. Challenger has at least as many closed trades as the incumbent on the validation slice

Ties go to the incumbent. Higher development expectancy alone is never sufficient.
Holdout metrics are never used until a champion is frozen.
"""

HOLDOUT_FRACTION = 0.20
MIN_HOLDOUT_TRADES = 3
DEFAULT_RESEARCH_DIR = Path("data/research/put_credit_protocol")


@dataclass(frozen=True)
class SliceMetrics:
    n: int
    wins: int
    losses: int
    expectancy: float | None
    profit_factor: float | None
    total_realized_pnl: float
    win_rate_pct: float | None

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # JSON-safe inf
        if d["profit_factor"] is not None and math.isinf(d["profit_factor"]):
            d["profit_factor"] = "Infinity"
        return d


@dataclass(frozen=True)
class ProtocolVariant:
    """A researchable protocol knob set — not a live order instruction."""

    version: str
    name: str
    params: dict[str, Any]
    notes: str = ""


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _trade_rows(trades_payload: Any) -> list[dict[str, Any]]:
    if isinstance(trades_payload, list):
        return [t for t in trades_payload if isinstance(t, dict)]
    if not isinstance(trades_payload, dict):
        return []
    for key in ("trades", "closed_trades", "paired", "trade_history"):
        rows = trades_payload.get(key)
        if isinstance(rows, list):
            return [t for t in rows if isinstance(t, dict)]
    return []


def _is_put_credit_trade(row: dict[str, Any]) -> bool:
    blob = " ".join(
        str(row.get(k) or "")
        for k in ("strategy", "strategy_family", "structure", "type", "signature", "id")
    ).lower()
    if "iron_condor" in blob and "put_credit" not in blob and "bull_put" not in blob:
        return False
    return any(
        token in blob
        for token in ("spy_put_credit", "put_credit", "bull_put", "bull put", "pcs_")
    )


def _is_closed(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "").lower()
    if status in {"closed", "filled_closed", "done"}:
        return True
    if row.get("exit_time") or row.get("exit_date"):
        return True
    if _as_float(row.get("realized_pnl")) is not None and status != "open":
        return status != "open"
    return _as_float(row.get("estimated_exit_pnl")) is not None


def _extract_pnl(row: dict[str, Any]) -> float | None:
    for key in ("realized_pnl", "estimated_exit_pnl", "pnl", "pl"):
        pnl = _as_float(row.get(key))
        if pnl is not None:
            return pnl
    entry = _as_float(row.get("entry_net_cash")) or _as_float(row.get("entry_credit"))
    exit_ = _as_float(row.get("exit_net_cash"))
    if entry is not None and exit_ is not None:
        return entry + exit_
    return None


def metrics_from_pnls(pnls: list[float]) -> SliceMetrics:
    n = len(pnls)
    if n == 0:
        return SliceMetrics(0, 0, 0, None, None, 0.0, None)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    total = sum(pnls)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf: float | None
    if gross_loss > 0:
        pf = gross_win / gross_loss
    elif n > 0 and gross_win > 0:
        pf = float("inf")
    else:
        pf = None
    return SliceMetrics(
        n=n,
        wins=len(wins),
        losses=len(losses),
        expectancy=round(total / n, 4),
        profit_factor=None if pf is None else (pf if math.isinf(pf) else round(pf, 4)),
        total_realized_pnl=round(total, 2),
        win_rate_pct=round(len(wins) / n * 100.0, 2),
    )


def extract_closed_put_credit_pnls(trades_payload: Any) -> list[tuple[str, float]]:
    """Return chronological (exit_time, pnl) for closed spy_put_credit rows."""
    rows = [r for r in _trade_rows(trades_payload) if _is_put_credit_trade(r) and _is_closed(r)]
    rows.sort(key=lambda r: str(r.get("exit_time") or r.get("exit_date") or ""))
    out: list[tuple[str, float]] = []
    for r in rows:
        pnl = _extract_pnl(r)
        if pnl is None:
            continue
        ts = str(r.get("exit_time") or r.get("exit_date") or "")
        out.append((ts, float(pnl)))
    return out


def split_dev_val_holdout(
    timed_pnls: list[tuple[str, float]],
    *,
    holdout_fraction: float = HOLDOUT_FRACTION,
    min_holdout: int = MIN_HOLDOUT_TRADES,
) -> dict[str, list[float]]:
    """Chronological split: early=dev, mid=val, final holdout locked until freeze.

    With small n, holdout is empty until there are enough trades for a meaningful tail.
    """
    pnls = [p for _, p in timed_pnls]
    n = len(pnls)
    if n == 0:
        return {"development": [], "validation": [], "holdout": []}
    holdout_n = 0
    if n >= min_holdout * 3:
        holdout_n = max(min_holdout, int(math.floor(n * holdout_fraction)))
        # leave room for dev+val
        holdout_n = min(holdout_n, n // 3)
    core = pnls[: n - holdout_n] if holdout_n else pnls
    holdout = pnls[n - holdout_n :] if holdout_n else []
    if not core:
        return {"development": [], "validation": [], "holdout": holdout}
    mid = max(1, len(core) // 2)
    return {
        "development": core[:mid],
        "validation": core[mid:],
        "holdout": holdout,
    }


def select_champion(
    challenger: SliceMetrics,
    incumbent: SliceMetrics | None,
    *,
    challenger_name: str,
    incumbent_name: str,
) -> tuple[str, str, list[str]]:
    """Apply fixed selection rule on validation metrics only."""
    if incumbent is None or incumbent.n == 0:
        return challenger_name, "no incumbent", []
    checks: list[tuple[str, bool]] = []
    c_exp = challenger.expectancy if challenger.expectancy is not None else float("-inf")
    i_exp = incumbent.expectancy if incumbent.expectancy is not None else float("-inf")
    checks.append(("validation expectancy not worse", c_exp >= i_exp))

    def _pf(m: SliceMetrics) -> float:
        if m.profit_factor is None:
            return float("-inf")
        if isinstance(m.profit_factor, float) and math.isinf(m.profit_factor):
            return 1e18
        return float(m.profit_factor)

    checks.append(("validation profit factor not worse", _pf(challenger) >= _pf(incumbent)))
    checks.append(
        (
            "validation total P/L not worse",
            challenger.total_realized_pnl >= incumbent.total_realized_pnl,
        )
    )
    checks.append(("validation n not smaller", challenger.n >= incumbent.n))
    failed = [name for name, ok in checks if not ok]
    if failed:
        return incumbent_name, "incumbent retained; challenger failed: " + "; ".join(failed), failed
    return challenger_name, "challenger passed all fixed gates", []


class ExperimentRegistry:
    """Append-only JSONL registry — handbook experiment history."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        payload = dict(record)
        payload.setdefault("ts", datetime.now(UTC).isoformat())
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"status": "corrupt_line", "raw": line[:200]})
        return rows


def evaluate_splits(timed_pnls: list[tuple[str, float]]) -> dict[str, Any]:
    splits = split_dev_val_holdout(timed_pnls)
    return {
        "selection_rule": SELECTION_RULE_TEXT.strip(),
        "split_sizes": {k: len(v) for k, v in splits.items()},
        "development": metrics_from_pnls(splits["development"]).as_dict(),
        "validation": metrics_from_pnls(splits["validation"]).as_dict(),
        "holdout": {
            **metrics_from_pnls(splits["holdout"]).as_dict(),
            "locked": True,
            "note": "Holdout locked until freeze_champion; do not use for selection.",
        },
        "full_sample": metrics_from_pnls([p for _, p in timed_pnls]).as_dict(),
        "n_closed": len(timed_pnls),
    }


def freeze_champion(
    research_dir: Path,
    *,
    champion: ProtocolVariant,
    validation: SliceMetrics,
    rationale: str,
    holdout_unlocked: bool = False,
) -> Path:
    """Write champion freeze. Holdout evaluation is a separate explicit step."""
    research_dir.mkdir(parents=True, exist_ok=True)
    path = research_dir / "champion.json"
    if path.is_file() and not holdout_unlocked:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("frozen") and not existing.get("holdout_unlocked"):
            raise RuntimeError("champion already frozen; refuse overwrite without unlock path")
    payload = {
        "frozen": True,
        "frozen_at": datetime.now(UTC).isoformat(),
        "champion": {
            "version": champion.version,
            "name": champion.name,
            "params": champion.params,
            "notes": champion.notes,
        },
        "validation": validation.as_dict(),
        "rationale": rationale,
        "holdout_unlocked": holdout_unlocked,
        "live_trading": False,
        "disclaimer": (
            "Freeze is research bookkeeping only. Live capital stays blocked until "
            "kill criteria EDGE_CANDIDATE on the full put-credit cohort."
        ),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def unlock_holdout_once(
    research_dir: Path,
    timed_pnls: list[tuple[str, float]],
) -> dict[str, Any]:
    """One-shot holdout evaluation after freeze; cannot revise champion after."""
    champion_path = research_dir / "champion.json"
    if not champion_path.is_file():
        raise RuntimeError("no frozen champion")
    champion = json.loads(champion_path.read_text(encoding="utf-8"))
    if champion.get("holdout_report"):
        raise RuntimeError("holdout already evaluated; refuse re-run (handbook freeze)")
    splits = split_dev_val_holdout(timed_pnls)
    holdout = metrics_from_pnls(splits["holdout"])
    report = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "holdout": holdout.as_dict(),
        "note": "Post-freeze holdout only. Do not change protocol after seeing this.",
    }
    champion["holdout_unlocked"] = True
    champion["holdout_report"] = report
    champion_path.write_text(json.dumps(champion, indent=2) + "\n", encoding="utf-8")
    registry = ExperimentRegistry(research_dir / "registry.jsonl")
    registry.append({"event": "holdout_unlock", "report": report, "status": "ok"})
    return report


def run_baseline_snapshot(
    trades_payload: Any,
    research_dir: Path,
    *,
    variant: ProtocolVariant | None = None,
) -> dict[str, Any]:
    """Record current put-credit cohort as protocol v1 baseline (no trade side effects)."""
    research_dir = Path(research_dir)
    research_dir.mkdir(parents=True, exist_ok=True)
    (research_dir / "SELECTION_RULE.md").write_text(SELECTION_RULE_TEXT.strip() + "\n", encoding="utf-8")

    variant = variant or ProtocolVariant(
        version="v1",
        name="spy-put-credit-baseline",
        params={
            "family": "spy_put_credit",
            "max_daily_structures": 3,
            "max_concurrent": 2,
            "lot_size": 1,
            "wing": 5,
            "take_profit_pct": 0.25,
            "stop_loss_pct": 2.0,
            "exit_dte": 7,
            "research_preferred_ivr": 30.0,
            "paper_min_ivr_env": "PUT_CREDIT_MIN_IVR",
        },
        notes="Manual baseline matching active paper validation profile.",
    )
    timed = extract_closed_put_credit_pnls(trades_payload)
    evaluation = evaluate_splits(timed)
    registry = ExperimentRegistry(research_dir / "registry.jsonl")
    record = {
        "event": "experiment",
        "status": "ok" if timed else "insufficient_sample",
        "version": variant.version,
        "name": variant.name,
        "params": variant.params,
        "notes": variant.notes,
        "evaluation": evaluation,
    }
    registry.append(record)
    snapshot_path = research_dir / "latest_snapshot.json"
    snapshot_path.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    return record


def compare_challenger(
    trades_payload: Any,
    *,
    challenger: ProtocolVariant,
    incumbent: ProtocolVariant,
    research_dir: Path,
) -> dict[str, Any]:
    """Compare two protocol labels on the SAME closed trades (labeling experiment).

    For put-credit, protocol variants currently share outcomes; this records the
    decision machinery and validation metrics so future stratified filters
    (e.g. IVR>=30 only) can challenge the baseline honestly.
    """
    timed = extract_closed_put_credit_pnls(trades_payload)
    # Optional filter by params flag preferred_ivr_only using journal regime if present
    # (future). Today both see full sample; selection still applies fixed gates.
    evaluation = evaluate_splits(timed)
    # Incumbent and challenger share metrics unless params define a filter.
    c_pnls = _filter_pnls_for_params(trades_payload, challenger.params)
    i_pnls = _filter_pnls_for_params(trades_payload, incumbent.params)
    c_val = metrics_from_pnls(split_dev_val_holdout([(f"t{i}", p) for i, p in enumerate(c_pnls)])["validation"])
    i_val = metrics_from_pnls(split_dev_val_holdout([(f"t{i}", p) for i, p in enumerate(i_pnls)])["validation"])
    winner, rationale, failed = select_champion(
        c_val, i_val, challenger_name=challenger.version, incumbent_name=incumbent.version
    )
    decision = {
        "event": "decision",
        "status": "ok",
        "challenger": asdict(challenger),
        "incumbent": asdict(incumbent),
        "challenger_validation": c_val.as_dict(),
        "incumbent_validation": i_val.as_dict(),
        "champion": winner,
        "rationale": rationale,
        "failed_gates": failed,
        "full_evaluation": evaluation,
    }
    ExperimentRegistry(Path(research_dir) / "registry.jsonl").append(decision)
    return decision


def _filter_pnls_for_params(trades_payload: Any, params: dict[str, Any]) -> list[float]:
    """Filter closed put-credit pnls by protocol params (e.g. preferred IVR cohort)."""
    min_ivr = params.get("min_ivr_for_edge_claim")
    rows = [r for r in _trade_rows(trades_payload) if _is_put_credit_trade(r) and _is_closed(r)]
    rows.sort(key=lambda r: str(r.get("exit_time") or r.get("exit_date") or ""))
    pnls: list[float] = []
    for r in rows:
        if min_ivr is not None:
            ivr = _as_float(
                (r.get("regime") or {}).get("iv_rank_proxy")
                if isinstance(r.get("regime"), dict)
                else r.get("iv_rank_proxy")
            )
            # If IVR missing, exclude from preferred-IVR challenger (fail closed)
            if ivr is None or ivr < float(min_ivr):
                continue
        pnl = _extract_pnl(r)
        if pnl is not None:
            pnls.append(float(pnl))
    return pnls


def scorecard_research_section(trades_payload: Any) -> dict[str, Any]:
    """Read-only research view for cohort scorecard (no registry writes)."""
    timed = extract_closed_put_credit_pnls(trades_payload)
    evaluation = evaluate_splits(timed)
    n = evaluation["n_closed"]
    return {
        "handbook_roi": "deterministic_eval_fixed_selection_holdout",
        "langchain_adopted": False,
        "selection_rule_fixed": True,
        "n_closed": n,
        "split_sizes": evaluation["split_sizes"],
        "development": evaluation["development"],
        "validation": evaluation["validation"],
        "holdout": evaluation["holdout"],
        "full_sample": evaluation["full_sample"],
        "honesty": {
            "edge_claim_allowed": False if n < 30 else None,
            "holdout_usable_for_selection": False,
            "note": (
                "Research splits are for protocol comparison only. Live remains blocked "
                "until kill_criteria EDGE_CANDIDATE on the full put-credit cohort."
            ),
        },
    }


def research_critic_audit(
    *,
    trades_payload: Any,
    decision: dict[str, Any] | None = None,
    champion_path: Path | None = None,
    kill_n: int = 30,
) -> dict[str, Any]:
    """Deterministic research critic (handbook critic role — no LLM).

    Fails closed on:
    - decisions that reference holdout metrics for promotion
    - champion freeze claiming live readiness
    - edge/profit claims when closed n < kill_n
    """
    findings: list[dict[str, str]] = []
    timed = extract_closed_put_credit_pnls(trades_payload)
    n = len(timed)

    if decision:
        if decision.get("used_holdout_for_selection") is True:
            findings.append(
                {
                    "severity": "error",
                    "code": "holdout_used_for_selection",
                    "message": "Holdout metrics must not drive champion selection",
                }
            )
        if decision.get("claim_profitable") is True and n < kill_n:
            findings.append(
                {
                    "severity": "error",
                    "code": "premature_edge_claim",
                    "message": f"Edge claim with n={n} < {kill_n}",
                }
            )

    if champion_path and Path(champion_path).is_file():
        champ = json.loads(Path(champion_path).read_text(encoding="utf-8"))
        if champ.get("live_trading") is True:
            findings.append(
                {
                    "severity": "error",
                    "code": "freeze_claims_live",
                    "message": "Champion freeze must keep live_trading=false",
                }
            )
        if champ.get("claim_profitable") is True and n < kill_n:
            findings.append(
                {
                    "severity": "error",
                    "code": "freeze_claims_profit",
                    "message": "Champion freeze must not claim profitability before n gate",
                }
            )

    # Soft warnings
    if n < kill_n:
        findings.append(
            {
                "severity": "info",
                "code": "insufficient_sample",
                "message": f"Closed put-credit n={n}; research only, no edge claim",
            }
        )

    errors = [f for f in findings if f["severity"] == "error"]
    return {
        "role": "research_critic",
        "pass": len(errors) == 0,
        "n_closed": n,
        "findings": findings,
        "errors": len(errors),
    }
