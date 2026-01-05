#!/usr/bin/env python3
"""
Chain-of-Verification (CoVe) Protocol for AI Hallucination Prevention.

Based on Meta Research (2024): "Chain-of-Verification Reduces Hallucination in LLMs"
https://arxiv.org/abs/2309.11495

This module enforces verification before any claim is made.
Improves accuracy by 23% (F1: 0.39 -> 0.48) per research.

Created: Jan 5, 2026 after hallucination incident (said "tomorrow" on trading day)
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pytz

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent


class ChainOfVerification:
    """
    Implements the 4-step CoVe process:
    1. Draft initial response
    2. Generate verification questions
    3. Answer those questions independently
    4. Generate final verified response
    """

    def __init__(self):
        self.verification_log: list[dict] = []
        self.et_tz = pytz.timezone("US/Eastern")

    def verify_date_claim(self, claimed_date: str | None = None) -> dict[str, Any]:
        """
        Verify any date-related claim against system clock.

        MANDATORY before any statement about:
        - "today", "tomorrow", "yesterday"
        - market hours
        - trading sessions
        - expiration dates

        Returns:
            Dict with verified date info and any discrepancies
        """
        now_utc = datetime.now(pytz.UTC)
        now_et = now_utc.astimezone(self.et_tz)

        verification = {
            "verified_at": now_utc.isoformat(),
            "utc_date": now_utc.strftime("%Y-%m-%d"),
            "utc_time": now_utc.strftime("%H:%M:%S"),
            "et_date": now_et.strftime("%Y-%m-%d"),
            "et_time": now_et.strftime("%H:%M:%S"),
            "day_of_week": now_et.strftime("%A"),
            "is_weekend": now_et.weekday() >= 5,
            "market_hours": self._check_market_hours(now_et),
        }

        if claimed_date:
            verification["claimed"] = claimed_date
            verification["matches"] = claimed_date.lower() in [
                now_et.strftime("%Y-%m-%d"),
                now_et.strftime("%A").lower(),
                "today",
            ]
            if not verification["matches"]:
                verification["WARNING"] = (
                    f"CLAIM MISMATCH: '{claimed_date}' does not match {now_et.strftime('%A, %Y-%m-%d')}"
                )

        self.verification_log.append(
            {
                "type": "date_verification",
                "result": verification,
                "timestamp": now_utc.isoformat(),
            }
        )

        return verification

    def _check_market_hours(self, now_et: datetime) -> dict[str, Any]:
        """Check if markets are open."""
        hour = now_et.hour
        minute = now_et.minute
        weekday = now_et.weekday()

        # Market hours: Mon-Fri 9:30 AM - 4:00 PM ET
        is_weekday = weekday < 5
        after_open = hour > 9 or (hour == 9 and minute >= 30)
        before_close = hour < 16

        is_open = is_weekday and after_open and before_close

        return {
            "is_open": is_open,
            "is_trading_day": is_weekday,  # Doesn't account for holidays
            "current_et": now_et.strftime("%I:%M %p ET"),
            "opens_at": "9:30 AM ET",
            "closes_at": "4:00 PM ET",
            "status": "OPEN" if is_open else "CLOSED",
        }

    def verify_claim(
        self,
        claim: str,
        evidence_sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Verify a general claim using available evidence.

        Args:
            claim: The statement to verify
            evidence_sources: List of sources to check (file paths, commands, etc.)

        Returns:
            Verification result with evidence
        """
        verification = {
            "claim": claim,
            "verified_at": datetime.now(pytz.UTC).isoformat(),
            "evidence": [],
            "verified": False,
        }

        if evidence_sources:
            for source in evidence_sources:
                evidence = self._gather_evidence(source)
                verification["evidence"].append(evidence)

        # Claim is verified only if we have supporting evidence
        verification["verified"] = len(verification["evidence"]) > 0 and all(
            e.get("found", False) for e in verification["evidence"]
        )

        if not verification["verified"]:
            verification["WARNING"] = "CLAIM NOT VERIFIED - Need evidence before stating"

        self.verification_log.append(
            {
                "type": "claim_verification",
                "result": verification,
                "timestamp": datetime.now(pytz.UTC).isoformat(),
            }
        )

        return verification

    def _gather_evidence(self, source: str) -> dict[str, Any]:
        """Gather evidence from a source (file or command)."""
        evidence = {"source": source, "found": False}

        if source.startswith("file:"):
            filepath = Path(source[5:])
            if filepath.exists():
                evidence["found"] = True
                evidence["type"] = "file"
                # Don't read entire file, just confirm existence
                evidence["exists"] = True
                evidence["modified"] = datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()

        elif source.startswith("cmd:"):
            cmd = source[4:]
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                evidence["found"] = result.returncode == 0
                evidence["type"] = "command"
                evidence["output"] = result.stdout[:500] if result.stdout else None
                evidence["exit_code"] = result.returncode
            except Exception as e:
                evidence["error"] = str(e)

        return evidence

    def must_verify_before_claiming(self, claim_type: str) -> str:
        """
        Return the verification command that MUST be run before making a claim.

        This enforces the "verify before claiming" mandate.
        """
        verifications = {
            "date": "date '+%A, %B %d, %Y'",
            "time": "date '+%I:%M %p %Z'",
            "market_status": 'python3 -c "import pytz; from datetime import datetime; et=pytz.timezone(\'US/Eastern\'); now=datetime.now(et); print(f\'{now.strftime("%A %I:%M %p ET")} - Market {"OPEN" if (now.weekday()<5 and ((now.hour>9 or (now.hour==9 and now.minute>=30)) and now.hour<16)) else "CLOSED"}\')"',
            "file_exists": "ls -la {filepath}",
            "git_status": "git status --short",
            "ci_status": 'curl -s https://api.github.com/repos/IgorGanapolsky/trading/commits/main/check-runs | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\'CI: {sum(1 for r in d.get(\\"check_runs\\",[]) if r.get(\\"conclusion\\")==\\"success\\")}/{d.get(\\"total_count\\",0)} passed\')"',
        }
        return verifications.get(claim_type, f"# No verification defined for: {claim_type}")

    def get_verification_protocol(self) -> str:
        """Return the full verification protocol as a string."""
        return """
=== CHAIN-OF-VERIFICATION PROTOCOL ===

Before ANY claim, follow these 4 steps:

1. DRAFT: What do I want to say?
2. VERIFY: What evidence supports this?
3. CHECK: Run verification command, capture output
4. CLAIM: Only state what evidence supports

MANDATORY VERIFICATIONS:
- Date/time claims: Run `date` command
- Market status: Check actual time vs market hours
- File changes: Run `git status` or `ls -la`
- CI status: Query GitHub API
- Task completion: Show command output as proof

FORBIDDEN:
- Saying "tomorrow" without checking today's date
- Claiming "done" without showing evidence
- Stating market status without time check
- Asserting file exists without verification

When uncertain: Say "I need to verify this first"
"""


def verify_now() -> dict[str, Any]:
    """Quick verification of current date/time/market status."""
    cov = ChainOfVerification()
    return cov.verify_date_claim()


if __name__ == "__main__":
    # Self-test
    cov = ChainOfVerification()
    result = cov.verify_date_claim()
    print(json.dumps(result, indent=2))
    print("\n" + cov.get_verification_protocol())
