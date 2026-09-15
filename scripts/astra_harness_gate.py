#!/usr/bin/env python3
"""Astra harness gate (InfoQ GPT-6 Astra FORMAT) — local, budget-fail-closed.

Steal patterns, not the model:
  - searchable session notes (not compaction-only)
  - consequential actions need confirmation class
  - computer-use via BrowserOS/neo — not invent Ask-mode
  - never set gpt-6-astra / OpenAI API as primary under fleet cap
  - evidence gate before retry / claim (hallucination pressure)
  - offensive cyber capabilities stay blocked

EXIT 0 when ok. EXIT 2 with --strict on hard fails.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Consequential classes that must stay recommend/confirm — never silent auto
CONSEQUENTIAL = frozenset(
    {
        "email_send",
        "calendar_write",
        "purchase",
        "force_push",
        "live_trade",
        "credential_write",
        "production_deploy",
    }
)

FORBIDDEN_PRIMARY_MODELS = frozenset(
    {
        "gpt-6-astra",
        "gpt-6",
        "o4-astra",
        "openai/gpt-6-astra",
    }
)


def evaluate(*, proposed_action: str = "", primary_model: str = "") -> dict:
    checks: list[dict] = []

    # 1) Notes rail present
    notes = ROOT / "scripts" / "astra_session_notes.py"
    checks.append(
        {
            "id": "searchable_notes_rail",
            "ok": notes.exists(),
            "detail": str(notes) if notes.exists() else "missing astra_session_notes.py",
        }
    )

    # 2) Primary model must not be Astra API under cap
    pm = (primary_model or os.environ.get("TRADING_PRIMARY_MODEL") or "").strip().lower()
    astra_primary = pm in FORBIDDEN_PRIMARY_MODELS or "gpt-6-astra" in pm
    checks.append(
        {
            "id": "no_astra_api_primary",
            "ok": not astra_primary,
            "detail": pm or "(unset — ok)",
            "why": "InfoQ/Astra rates blow fleet external cap; local/subscription first",
        }
    )

    # 3) Consequential action → must be gated
    action = (proposed_action or "").strip().lower()
    needs_confirm = any(c in action for c in CONSEQUENTIAL) or action in CONSEQUENTIAL
    checks.append(
        {
            "id": "consequential_confirmation",
            "ok": True,  # informational — caller must honor
            "needs_confirm": needs_confirm,
            "action": action or None,
            "detail": "recommend_only / human confirm required" if needs_confirm else "non-consequential",
        }
    )

    # 4) Computer-use rail honesty (BrowserOS preferred)
    neo = Path.home() / ".browseros"
    checks.append(
        {
            "id": "computer_use_rail",
            "ok": True,
            "detail": "prefer BrowserOS neo; never invent Ask-mode when tools exist",
            "browseros_present": neo.exists(),
        }
    )

    # 5) Offensive cyber blocked (Astra critical cyber class)
    offensive = any(
        w in action for w in ("exploit", "zero-day", "weaponize", "ransomware", "c2 beacon")
    )
    checks.append(
        {
            "id": "offensive_cyber_blocked",
            "ok": not offensive,
            "detail": "blocked" if offensive else "no offensive intent detected",
        }
    )

    # 6) Evidence-before-claim (hallucination pressure — Astra reports lower but monitorability harder)
    checks.append(
        {
            "id": "evidence_before_claim",
            "ok": True,
            "detail": "prefer receipts/SHAs over prose; Astra monitorability risk → explicit ledgers",
        }
    )

    hard = [c for c in checks if c["id"] in {"searchable_notes_rail", "no_astra_api_primary", "offensive_cyber_blocked"} and not c["ok"]]
    return {
        "ok": len(hard) == 0,
        "framework": "astra_harness_gate",
        "stolen_format": (
            "InfoQ GPT-6 Astra harness patterns — notes across windows, confirm "
            "consequential, budget-fail-closed primary model (not OpenAI product)"
        ),
        "source": {"infoq": "https://www.infoq.com/news/2026/09/openai-gpt6-astra/"},
        "checks": checks,
        "hard_fails": [c["id"] for c in hard],
        "practices": {
            "prefer": "local/subscription models; BrowserOS; searchable notes; HydraFusion Cascade",
            "never": "gpt-6-astra as primary; silent auto-send; offensive cyber; claim without evidence",
        },
        "ts": datetime.now(UTC).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proposed-action", default="")
    p.add_argument("--primary-model", default="")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    out = evaluate(proposed_action=args.proposed_action, primary_model=args.primary_model)
    print(json.dumps(out, indent=2, sort_keys=True))
    if args.strict and not out["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
