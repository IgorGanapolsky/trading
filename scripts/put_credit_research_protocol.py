#!/usr/bin/env python3
"""CLI for put-credit research protocol (handbook high-ROI layer).

Never submits trades. Research bookkeeping only.

Usage:
  .venv/bin/python scripts/put_credit_research_protocol.py --baseline
  .venv/bin/python scripts/put_credit_research_protocol.py --compare-preferred-ivr
  .venv/bin/python scripts/put_credit_research_protocol.py --freeze-baseline
  .venv/bin/python scripts/put_credit_research_protocol.py --unlock-holdout
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.put_credit_research_protocol import (  # noqa: E402
    ProtocolVariant,
    compare_challenger,
    extract_closed_put_credit_pnls,
    freeze_champion,
    metrics_from_pnls,
    research_critic_audit,
    run_baseline_snapshot,
    split_dev_val_holdout,
    unlock_holdout_once,
)

DEFAULT_TRADES = ROOT / "data" / "trades.json"
DEFAULT_DIR = ROOT / "data" / "research" / "put_credit_protocol"


def _load_trades(path: Path) -> object:
    if not path.is_file():
        return {"trades": []}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trades", type=Path, default=DEFAULT_TRADES)
    p.add_argument("--research-dir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--baseline", action="store_true", help="Record v1 baseline snapshot")
    p.add_argument(
        "--compare-preferred-ivr",
        action="store_true",
        help="Challenge baseline with IVR>=30 preferred-edge filter on closed trades",
    )
    p.add_argument("--freeze-baseline", action="store_true")
    p.add_argument("--unlock-holdout", action="store_true")
    p.add_argument(
        "--critic-audit",
        action="store_true",
        help="Deterministic research critic (no LLM); exit 1 on hard failures",
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    trades = _load_trades(args.trades)
    out: dict = {}

    if args.baseline or not any(
        [
            args.compare_preferred_ivr,
            args.freeze_baseline,
            args.unlock_holdout,
            args.critic_audit,
        ]
    ):
        out["baseline"] = run_baseline_snapshot(trades, args.research_dir)

    if args.compare_preferred_ivr:
        incumbent = ProtocolVariant(
            version="v1",
            name="spy-put-credit-baseline",
            params={"family": "spy_put_credit"},
        )
        challenger = ProtocolVariant(
            version="v2-preferred-ivr",
            name="spy-put-credit-preferred-ivr-30",
            params={"family": "spy_put_credit", "min_ivr_for_edge_claim": 30.0},
            notes="Edge-claim stratum only; paper entries may still use lower MIN_IVR.",
        )
        out["compare"] = compare_challenger(
            trades,
            challenger=challenger,
            incumbent=incumbent,
            research_dir=args.research_dir,
        )

    if args.freeze_baseline:
        timed = extract_closed_put_credit_pnls(trades)
        val = metrics_from_pnls(split_dev_val_holdout(timed)["validation"])
        path = freeze_champion(
            args.research_dir,
            champion=ProtocolVariant(
                version="v1",
                name="spy-put-credit-baseline",
                params={"family": "spy_put_credit"},
            ),
            validation=val,
            rationale="Freeze current baseline for research trail (not live unlock).",
        )
        out["freeze"] = {"path": str(path), "validation": val.as_dict()}

    if args.unlock_holdout:
        out["holdout"] = unlock_holdout_once(
            args.research_dir, extract_closed_put_credit_pnls(trades)
        )

    if args.critic_audit:
        champ = Path(args.research_dir) / "champion.json"
        out["critic"] = research_critic_audit(
            trades_payload=trades,
            decision=out.get("compare") if isinstance(out.get("compare"), dict) else None,
            champion_path=champ if champ.is_file() else None,
        )

    text = json.dumps(out, indent=2, default=str)
    print(text)
    if args.critic_audit and not out.get("critic", {}).get("pass", True):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
