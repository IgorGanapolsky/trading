#!/usr/bin/env python3
"""Validate multi-agent claims, worktrees, Herdr state, and PR metadata."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.coordination.agent_contract import (  # noqa: E402
    audit_repository,
    default_vault_root,
    has_errors,
    protect_worktree,
    validate_local_preflight,
    validate_pr_event,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
    )
    parser.add_argument("--vault-root", type=Path, default=default_vault_root())
    subcommands = parser.add_subparsers(dest="command", required=True)

    preflight = subcommands.add_parser("preflight", help="fail closed before repository writes")
    preflight.add_argument("--issue")
    preflight.add_argument("--agent")
    preflight.add_argument("--file", action="append", default=[])

    audit = subcommands.add_parser("audit", help="reconcile claims, worktrees, and Herdr")
    audit.add_argument("--warn-only", action="store_true")

    validate_pr = subcommands.add_parser("validate-pr", help="validate a GitHub PR event")
    validate_pr.add_argument("--event", type=Path, required=True)

    protect = subcommands.add_parser("protect-worktree", help="check before worktree removal")
    protect.add_argument("--path", type=Path, required=True)
    return parser


def _findings_payload(findings: Sequence[object]) -> dict[str, object]:
    serialized = [asdict(item) for item in findings]
    return {
        "findings": serialized,
        "errors": sum(item["severity"] == "error" for item in serialized),
        "warnings": sum(item["severity"] == "warning" for item in serialized),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    vault_root = args.vault_root.expanduser().resolve()

    if args.command == "preflight":
        findings = validate_local_preflight(
            repo_root,
            vault_root=vault_root,
            issue_key=args.issue,
            agent=args.agent,
            candidate_files=args.file,
        )
        payload = _findings_payload(findings)
    elif args.command == "audit":
        payload = audit_repository(repo_root, vault_root=vault_root)
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0 if args.warn_only or payload["errors"] == 0 else 1
    elif args.command == "validate-pr":
        event = json.loads(args.event.read_text(encoding="utf-8"))
        findings = validate_pr_event(event)
        payload = _findings_payload(findings)
    else:
        findings = protect_worktree(repo_root, args.path, vault_root=vault_root)
        payload = _findings_payload(findings)

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if has_errors(findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
