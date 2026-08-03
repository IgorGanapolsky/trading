#!/usr/bin/env python3
"""One Ralph+GSD profit tick: inventory, manage dry-runs, cohort + production plane.

Paper-only. Never submits live risk. Never claims profitability.

GSD phase 2 (put-credit edge path) now also surfaces the world-class production
scorecard and production_gate control plane so ops grade is visible each tick.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404 — fixed local scripts only
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(args: list[str], *, stdout_keep: int = 4000) -> dict:
    proc = subprocess.run(  # nosec B603 — argv is fixed repo scripts, not shell
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        shell=False,
    )
    return {
        "cmd": args,
        "rc": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-stdout_keep:],
        "stderr_tail": (proc.stderr or "")[-1500:],
    }


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _parse_json_blob(raw: str) -> dict[str, Any]:
    """Best-effort JSON object extract from script stdout."""
    if not raw:
        return {"parse_error": True, "raw_tail": ""}
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start < 0 or end <= start:
            return {"parse_error": True, "raw_tail": raw[-500:]}
        return json.loads(raw[start:end])
    except Exception:
        return {"parse_error": True, "raw_tail": raw[-500:]}


def _load_world_class_card(step: dict[str, Any]) -> dict[str, Any]:
    """Prefer audit file written by the scorecard (full JSON); fall back to stdout."""
    for rel in (
        "data/audit/world_class_production_latest.json",
        "data/audit/world_class_production_scorecard_latest.json",
    ):
        card = _load_json_file(ROOT / rel)
        if card and card.get("schema_version"):
            return card
    # Direct import fallback when subprocess output truncated / script missing
    try:
        from scripts.world_class_production_scorecard import build_world_class_card

        return build_world_class_card()
    except Exception as exc:  # noqa: BLE001
        parsed = _parse_json_blob(step.get("stdout_tail") or "")
        if not parsed.get("parse_error"):
            return parsed
        return {
            "parse_error": True,
            "error": str(exc),
            "raw_tail": (step.get("stdout_tail") or "")[-500:],
        }


def _evaluate_production_gate_safe() -> dict[str, Any]:
    """Import evaluate_production_gate when available; degrade gracefully."""
    try:
        from src.risk.production_gate import evaluate_production_gate

        pg = evaluate_production_gate(for_live=False)
        if hasattr(pg, "to_dict"):
            return pg.to_dict()
        return {
            "ok": bool(getattr(pg, "ok", False)),
            "score_0_10": getattr(pg, "score_0_10", None),
            "grade": getattr(pg, "grade", None),
            "allow_new_risk": bool(getattr(pg, "allow_new_risk", False)),
            "allow_live_capital": bool(getattr(pg, "allow_live_capital", False)),
            "blockers": list(getattr(pg, "blockers", []) or []),
        }
    except Exception as exc:  # noqa: BLE001 — control plane optional on older trees
        return {
            "error": str(exc),
            "ok": False,
            "score_0_10": None,
            "grade": None,
            "allow_new_risk": False,
            "allow_live_capital": False,
            "blockers": [f"import_or_eval_failed:{exc}"],
        }


def _world_class_summary(card: dict[str, Any]) -> dict[str, Any]:
    """Compact world-class scorecard view for the tick report."""
    if not isinstance(card, dict) or card.get("parse_error"):
        return {
            "available": False,
            "overall_grade": None,
            "overall_score_0_10": None,
            "process_ops_grade": None,
            "process_ops_score_0_10": None,
            "error": card.get("parse_error") or card.get("error"),
        }
    overall = card.get("overall") or {}
    return {
        "available": True,
        "overall_grade": overall.get("grade"),
        "overall_score_0_10": overall.get("score_0_10"),
        "process_ops_grade": overall.get("process_ops_grade"),
        "process_ops_score_0_10": overall.get("process_ops_score_0_10"),
        "label": overall.get("label"),
        "put_credit_closed_n": (card.get("truth") or {}).get("put_credit_closed_n"),
        "kill_verdict": (card.get("truth") or {}).get("kill_verdict"),
    }


def main() -> int:
    py = ROOT / ".venv" / "bin" / "python"
    python = str(py if py.is_file() else Path(sys.executable))
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    out_dir = ROOT / "data" / "audit" / "ralph_ticks"
    out_dir.mkdir(parents=True, exist_ok=True)

    steps = {
        "inventory": _run([python, "scripts/audit_open_inventory.py"]),
        "regime": _run([python, "scripts/spy_put_credit.py", "--regime-status"]),
        "put_credit_manage_dry": _run(
            [python, "scripts/spy_put_credit.py", "--manage-exits", "--dry-run"]
        ),
        "residual_ic_dry": _run([python, "scripts/residual_ic_manager.py", "--dry-run"]),
        "cohort": _run([python, "scripts/put_credit_cohort_scorecard.py", "--json"]),
        # Production control plane (GSD phase 2 ops surface)
        "world_class": _run(
            [python, "scripts/world_class_production_scorecard.py", "--json"],
            stdout_keep=120_000,
        ),
    }

    cohort = _parse_json_blob(steps["cohort"]["stdout_tail"])
    regime = _parse_json_blob(steps["regime"]["stdout_tail"])
    if regime.get("parse_error"):
        regime = {"parse_error": True, "rc": steps["regime"]["rc"]}

    world_class_card = _load_world_class_card(steps["world_class"])
    world_class = _world_class_summary(world_class_card)

    # Prefer direct Python import for structured production_gate; fall back to
    # scorecard-embedded view when import fails.
    production_gate = _evaluate_production_gate_safe()
    if production_gate.get("error") and isinstance(world_class_card, dict):
        embedded = world_class_card.get("production_gate")
        if isinstance(embedded, dict) and not embedded.get("error"):
            production_gate = {**embedded, "source": "world_class_scorecard"}
        else:
            production_gate.setdefault("source", "degraded")
    else:
        production_gate.setdefault("source", "evaluate_production_gate")

    gate_present = (
        production_gate.get("grade") is not None or production_gate.get("score_0_10") is not None
    )

    gsd: dict[str, Any] = {
        "milestone": "v2.0-put-credit-edge",
        "phase": 2,
        "phase_name": "Smart Entry Quality",
        "completion_promise": "EDGE_GATE_READY_OR_KILLED",
    }
    if gate_present:
        gsd["phase_note"] = (
            "phase 2 + production control plane: "
            f"ops_grade={production_gate.get('grade')} "
            f"ops_score={production_gate.get('score_0_10')} "
            f"allow_new_risk={production_gate.get('allow_new_risk')} "
            "(paper only; edge still requires n≥30 EDGE_CANDIDATE)"
        )
        gsd["production_control_plane"] = True
    else:
        gsd["phase_note"] = "phase 2 put-credit edge path; production gate unavailable this tick"
        gsd["production_control_plane"] = False

    report = {
        "schema_version": "ralph-gsd-profit-tick/3",
        "framework": "ralph+gsd",
        "ts": ts,
        "rcs": {k: v["rc"] for k, v in steps.items()},
        "inventory_ok": steps["inventory"]["rc"] in (0, 2),  # 2 = unclean still ran
        "inventory_clean": steps["inventory"]["rc"] == 0,
        "regime": {
            "allowed": regime.get("allowed"),
            "blockers": regime.get("blockers"),
            "soft_flags": regime.get("soft_flags"),
            "vix": (regime.get("snapshot") or {}).get("vix"),
            "iv_rank_proxy": (regime.get("snapshot") or {}).get("iv_rank_proxy"),
            "rc": steps["regime"]["rc"],
        },
        "cohort": {
            "closed_n": (cohort.get("closed") or {}).get("closed_n"),
            "open_n": (cohort.get("open") or {}).get("open_n"),
            "kill_verdict": ((cohort.get("closed") or {}).get("kill_criteria") or {}).get(
                "verdict"
            ),
            "progress_pct": (cohort.get("progress") or {}).get("pct_to_gate"),
            "claim_profitable": False,  # honesty: never claim from thin sample
            "live_deposit_ready": False,  # paper path only on this tick
            "rolling_20": (cohort.get("closed") or {}).get("rolling_20"),
        },
        "production_gate": {
            "grade": production_gate.get("grade"),
            "score_0_10": production_gate.get("score_0_10"),
            "allow_new_risk": bool(production_gate.get("allow_new_risk")),
            "allow_live_capital": bool(production_gate.get("allow_live_capital")),
            "ok": production_gate.get("ok"),
            "blockers": production_gate.get("blockers") or [],
            "source": production_gate.get("source"),
            "error": production_gate.get("error"),
        },
        "world_class": world_class,
        "gsd": gsd,
        "honesty": (
            "paper validation only; live_blocked; no profitability claim; "
            "production_gate/ops grade ≠ edge"
        ),
    }
    report_path = out_dir / f"tick_{ts}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # Detail dumps for debugging
    (out_dir / f"tick_{ts}_inventory.txt").write_text(
        steps["inventory"]["stdout_tail"], encoding="utf-8"
    )
    (out_dir / f"tick_{ts}_cohort.json").write_text(
        json.dumps(cohort, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / f"tick_{ts}_regime.json").write_text(
        json.dumps(regime, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / f"tick_{ts}_world_class.json").write_text(
        json.dumps(world_class_card, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (out_dir / f"tick_{ts}_production_gate.json").write_text(
        json.dumps(production_gate, indent=2, default=str) + "\n", encoding="utf-8"
    )

    ralph_state = ROOT / ".claude" / "ralph" / "state.json"
    ralph_state.parent.mkdir(parents=True, exist_ok=True)
    prev: dict[str, Any] = {}
    if ralph_state.is_file():
        try:
            prev = json.loads(ralph_state.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    prev.update(
        {
            "active": True,
            "framework": "ralph+gsd",
            "goal": "put_credit_edge_proof_n30",
            "iteration": int(prev.get("iteration") or 0) + 1,
            "max_iterations": int(prev.get("max_iterations") or 10_000),
            "last_tick_at": datetime.now(UTC).isoformat(),
            "last_tick_report": str(report_path),
            "claim_profitable": False,
            "status": "running",
            "completion_promise": "EDGE_GATE_READY_OR_KILLED",
            "production_gate_grade": production_gate.get("grade"),
            "production_gate_score": production_gate.get("score_0_10"),
            "allow_new_risk": bool(production_gate.get("allow_new_risk")),
        }
    )
    ralph_state.write_text(json.dumps(prev, indent=2) + "\n", encoding="utf-8")

    # Do not dump full report JSON to stdout (CodeQL: clear-text financial fields).
    # Full report remains on disk at report_path.
    print(
        "ralph_tick "
        f"iteration={prev['iteration']} "
        f"grade={production_gate.get('grade')} "
        f"score={production_gate.get('score_0_10')} "
        f"allow_new_risk={bool(production_gate.get('allow_new_risk'))} "
        f"report={report_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
