#!/usr/bin/env python3
"""Micro-cap deployment decision CLI (feat/live-micro-trade-cap).

Turn Igor's directive into a runnable check:

    "start trading very small (as small as possible); as I deposit more money,
     we can trade more."

Reads a balance (default paper simulation) and prints the gate's decision:
how much we *could* micro-deploy (equity fractional DCA) and whether live
execution is actually credentialed.

This is a DECISION surface, not an execution one: the CLI never moves money.
Real transfer still demands the existing bank/broker live credential + the
MERCURY_LIVE_TRANSFERS_ENABLED=1 hard stop (its own adapter gate).

Examples:
    uv run python scripts/micro_capital_gate.py --balance 100.0
    uv run python scripts/micro_capital_gate.py --balance 250.0 --json
    uv run python scripts/micro_capital_gate.py --check-live-readiness
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.micro.micro_capital_gate import (  # noqa: E402
    DEFAULT_DEPLOY_FRACTION,
    DEFAULT_HARD_FLOOR_USD,
    DEFAULT_LIVE_CAP_USD,
    compute_micro_cap,
    options_require_larger_capital,
)


def _live_readiness(env: dict[str, str]) -> dict[str, bool]:
    """Report whether live creds + hard-stop are present without printing them."""
    return {
        "MERCURY_API_TOKEN": bool(env.get("MERCURY_API_TOKEN")),
        "MERCURY_ACCOUNT_ID": bool(env.get("MERCURY_ACCOUNT_ID")),
        "MERCURY_LIVE_TRANSFERS_ENABLED": env.get("MERCURY_LIVE_TRANSFERS_ENABLED") == "1",
        "ALPACA_LIVE_API_KEY": bool(
            env.get("ALPACA_LIVE_API_KEY") or env.get("DIVIDEND_GROWTH_ALPACA_API_KEY")
        ),
    }


def _run(args: argparse.Namespace) -> int:
    dec = compute_micro_cap(
        args.balance,
        hard_floor_usd=args.hard_floor_usd,
        deploy_fraction=args.deploy_fraction,
        live_cap_usd=args.live_cap_usd,
    )

    if args.json:
        payload = {"micro_cap": dec.to_dict()}
        if args.live_readiness:
            payload["live_readiness"] = _live_readiness(dict(__import__("os").environ))
        print(json.dumps(payload, indent=2))
        return 0 if dec.can_deploy else 1

    floor, frac, cap = args.hard_floor_usd, args.deploy_fraction, args.live_cap_usd
    print(f"Micro-cap deploy gate (balance ${dec.available_balance_usd:.2f})")
    print(f"  hard floor    : ${floor:.2f}  (keep as Mercury buffer)")
    print(f"  deploy fraction: {frac:.0%}")
    print(f"  live cap       : ${cap:.2f}  (single live transfer bound)")
    if dec.can_deploy:
        print(
            f"  DECISION: deploy ${dec.deployable_usd:.2f} -> {', '.join(dec.deployable_symbols)}"
        )
        print(
            f"  (as small as possible at ${dec.available_balance_usd:.2f}; "
            f"deposit more to raise this)"
        )
    else:
        print("  DECISION: nothing to deploy")
        if dec.blocked_reason:
            print(f"  reason: {dec.blocked_reason}")
    print(f"  options: {options_require_larger_capital()}")
    if args.live_readiness:
        print("  live_readiness:", _live_readiness(__import__("os").environ))
    return 0 if dec.can_deploy else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--balance", type=float, default=100.0, help="bank balance USD (default 100.0)"
    )
    parser.add_argument("--hard-floor-usd", type=float, default=DEFAULT_HARD_FLOOR_USD)
    parser.add_argument("--deploy-fraction", type=float, default=DEFAULT_DEPLOY_FRACTION)
    parser.add_argument("--live-cap-usd", type=float, default=DEFAULT_LIVE_CAP_USD)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--live-readiness",
        action="store_true",
        help="also print whether live creds + hard-stop are present (booleans only)",
    )
    args = parser.parse_args()
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
