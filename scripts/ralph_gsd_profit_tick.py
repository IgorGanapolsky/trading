#!/usr/bin/env python3
"""One Ralph+GSD profit tick: inventory, manage dry-runs, cohort scorecard.

Paper-only. Never submits live risk. Never claims profitability.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404 — fixed local scripts only
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(args: list[str]) -> dict:
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
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-1500:],
    }


def main() -> int:
    py = ROOT / ".venv" / "bin" / "python"
    python = str(py if py.is_file() else Path(sys.executable))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
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
    }

    cohort = {}
    raw = steps["cohort"]["stdout_tail"]
    try:
        # scorecard prints pure JSON with --json
        cohort = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
    except Exception:
        cohort = {"parse_error": True, "raw_tail": raw[-500:]}

    regime = {}
    reg_raw = steps["regime"]["stdout_tail"]
    try:
        regime = json.loads(reg_raw[reg_raw.find("{") : reg_raw.rfind("}") + 1])
    except Exception:
        regime = {"parse_error": True, "rc": steps["regime"]["rc"]}

    report = {
        "schema_version": "ralph-gsd-profit-tick/2",
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
            "claim_profitable": (cohort.get("honesty") or {}).get("claim_profitable"),
            "live_deposit_ready": (cohort.get("honesty") or {}).get("live_deposit_ready"),
            "rolling_20": (cohort.get("closed") or {}).get("rolling_20"),
        },
        "gsd": {
            "milestone": "v2.0-put-credit-edge",
            "phase": 2,
            "phase_name": "Smart Entry Quality",
            "completion_promise": "EDGE_GATE_READY_OR_KILLED",
        },
        "honesty": "paper validation only; live_blocked; no profitability claim",
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

    ralph_state = ROOT / ".claude" / "ralph" / "state.json"
    ralph_state.parent.mkdir(parents=True, exist_ok=True)
    prev = {}
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
            "last_tick_at": datetime.now(timezone.utc).isoformat(),
            "last_tick_report": str(report_path),
            "claim_profitable": False,
            "status": "running",
            "completion_promise": "EDGE_GATE_READY_OR_KILLED",
        }
    )
    ralph_state.write_text(json.dumps(prev, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"report={report_path}")
    print(f"ralph_iteration={prev['iteration']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
