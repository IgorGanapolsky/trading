#!/usr/bin/env python3
"""Bolt Forge FORMAT steal: explicit opt-in before any session export.

Sources:
  https://support.bolt.new/account-and-subscription/bolt-forge
  https://thenewstack.io/bolt-forge-training-data/

Steal: per-session consent, secret strip + seeded tests, operator vs research
pool, leaving stops NEW collection (already-exported stays).

Do not clone Bolt Forge. Do not send traces to Arcee. Do not claim 50x compute.
Default is DENY. Export is local file only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "data" / "runtime" / "session_export_log.jsonl"
OPERATOR_LANES = frozenset({"operator", "spy_put_credit", "live"})
RESEARCH_LANES = frozenset({"research", "grpo", "eval"})
SOURCES = (
    "https://support.bolt.new/account-and-subscription/bolt-forge",
    "https://thenewstack.io/bolt-forge-training-data/",
)
SEED_SECRET = "PKTEST_FORGE_SEED_NOT_REAL"  # nosec B105 — fixture token, not a credential

SECRET_RES = (
    re.compile(r"(?i)(APCA_API_(?:KEY_ID|SECRET_KEY)\s*[=:]\s*)\S+"),
    re.compile(r"(?i)(ghp|gho|github_pat)_[A-Za-z0-9_]+"),
    re.compile(r"(?i)(sk[-_]live|sk[-_]test|rk_live)[-_A-Za-z0-9]+"),
    re.compile(r"(?i)(Bearer\s+)\S+"),
    re.compile(re.escape(SEED_SECRET)),
)


def redact(text: str) -> str:
    out = text
    for pat in SECRET_RES:
        out = pat.sub("[REDACTED]", out)
    return out


def assert_export_allowed(
    *,
    lane: str,
    opt_in: bool,
    understand_irreversible: bool,
    allow_operator: bool,
) -> None:
    if not opt_in or not understand_irreversible:
        raise PermissionError("default DENY: need --opt-in-export and --i-understand-irreversible")
    if lane in OPERATOR_LANES and not allow_operator:
        raise PermissionError(
            "operator lane (spy_put_credit/live) is not a training pool; "
            "pass --allow-operator-lane only for a local redacted debug dump"
        )
    if lane not in RESEARCH_LANES and lane not in OPERATOR_LANES:
        raise ValueError(f"unknown lane {lane!r}")


def export_session(
    text: str,
    *,
    lane: str,
    dest: Path,
    log: Path,
    opt_in: bool,
    understand_irreversible: bool,
    allow_operator: bool,
) -> dict[str, Any]:
    assert_export_allowed(
        lane=lane,
        opt_in=opt_in,
        understand_irreversible=understand_irreversible,
        allow_operator=allow_operator,
    )
    body = redact(text)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")
    rec = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "lane": lane,
        "dest": str(dest),
        "bytes": len(body.encode("utf-8")),
        "irreversible": True,
        "remote_upload": False,
    }
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return {
        "ok": True,
        "exported": True,
        "remote_upload": False,
        "irreversible": True,
        "lane": lane,
        "dest": str(dest),
        "refuses": [
            "do_not_clone_bolt_forge",
            "do_not_send_to_arcee",
            "do_not_claim_50x_compute",
            "already_exported_is_not_auto_deleted",
        ],
        "sources": list(SOURCES),
    }


def status(*, log: Path) -> dict[str, Any]:
    n = 0
    if log.exists():
        n = sum(1 for line in log.read_text(encoding="utf-8").splitlines() if line.strip())
    return {
        "ok": True,
        "default_deny": True,
        "n_exported_local": n,
        "remote_upload": False,
        "opt_out_stops_new_only": True,
        "sources": list(SOURCES),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="local redacted dump; never uploads")
    e.add_argument("--input", type=Path, required=True)
    e.add_argument("--dest", type=Path, required=True)
    e.add_argument("--lane", required=True)
    e.add_argument("--log", type=Path, default=DEFAULT_LOG)
    e.add_argument("--opt-in-export", action="store_true")
    e.add_argument("--i-understand-irreversible", action="store_true")
    e.add_argument("--allow-operator-lane", action="store_true")
    sub.add_parser("status")
    args = p.parse_args(argv)
    if args.cmd == "status":
        json.dump(status(log=DEFAULT_LOG), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    try:
        report = export_session(
            args.input.read_text(encoding="utf-8", errors="replace"),
            lane=args.lane,
            dest=args.dest,
            log=args.log,
            opt_in=args.opt_in_export,
            understand_irreversible=args.i_understand_irreversible,
            allow_operator=args.allow_operator_lane,
        )
    except PermissionError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 2
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
