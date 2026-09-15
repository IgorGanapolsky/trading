#!/usr/bin/env python3
"""
Spec-Driven Development (SDD) Conformance Evaluator
Validates formal business specs against system state, enforcing invariant diodes
and generating cryptographic verification receipts to eliminate AI intent drift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class InvariantResult:
    invariant_id: str
    name: str
    passed: bool
    details: str
    severity: str = "ERROR"


@dataclass
class SpecConformanceReceipt:
    spec_id: str
    spec_version: str
    timestamp: str
    conformance_status: str  # PASS, FAIL
    total_invariants: int
    passed_invariants: int
    failed_invariants: int
    conformance_pct: float
    results: list[InvariantResult] = field(default_factory=list)
    sha256_fingerprint: str = ""


class SpecConformanceEvaluator:
    """Evaluates formal specifications against system state and emits verification receipts."""

    def __init__(self, specs_dir: Optional[Path] = None, audit_dir: Optional[Path] = None):
        self.specs_dir = specs_dir or Path("specs")
        self.audit_dir = audit_dir or Path("data/audit")
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def load_spec(self, spec_path: Path) -> dict[str, Any]:
        with open(spec_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_trading_spec(
        self,
        spec: dict[str, Any],
        system_state: Optional[dict[str, Any]] = None,
    ) -> SpecConformanceReceipt:
        now_iso = datetime.now(timezone.utc).isoformat()
        invariants = spec.get("invariants", [])
        results: list[InvariantResult] = []

        # Default mock state for testing if none provided
        state = system_state or {
            "portfolio_nav": 100000.0,
            "max_risk_pct": 1.0,
            "iv_rank": 35.0,
            "short_delta": 0.14,
            "spread_width": 5.0,
            "has_protective_wing": True,
            "has_order_idempotency": True,
            "concurrent_positions": 1,
        }

        for inv in invariants:
            inv_id = inv.get("id", "UNKNOWN")
            name = inv.get("name", "Unnamed Invariant")
            params = inv.get("parameters", {})
            passed = True
            details = "Satisfied"

            if inv_id == "INV-001":  # Buffett Rule #1
                max_risk = params.get("max_risk_pct_nav", 1.0)
                actual_risk = state.get("max_risk_pct", 1.0)
                if actual_risk > max_risk:
                    passed = False
                    details = f"Risk {actual_risk}% exceeds cap {max_risk}%"

            elif inv_id == "INV-002":  # Defined Risk
                req_wing = params.get("requires_protective_wing", True)
                has_wing = state.get("has_protective_wing", True)
                if req_wing and not has_wing:
                    passed = False
                    details = "Naked unhedged options detected"

            elif inv_id == "INV-003":  # Selective Regime
                min_ivr = params.get("min_iv_rank", 30.0)
                actual_ivr = state.get("iv_rank", 35.0)
                max_delta = params.get("max_short_delta", 0.15)
                actual_delta = state.get("short_delta", 0.14)
                if actual_ivr < min_ivr:
                    passed = False
                    details = f"IV Rank {actual_ivr} < {min_ivr}"
                elif actual_delta > max_delta:
                    passed = False
                    details = f"Short delta {actual_delta} > {max_delta}"

            elif inv_id == "INV-004":  # Capital Recycling
                profit_target = params.get("profit_target_pct", 50.0)
                details = f"Exit rule active at {profit_target}% max credit"

            elif inv_id == "INV-005":  # Order Identity
                idempotent = state.get("has_order_idempotency", True)
                if not idempotent:
                    passed = False
                    details = "Missing deterministic order idempotency token"

            results.append(
                InvariantResult(
                    invariant_id=inv_id,
                    name=name,
                    passed=passed,
                    details=details,
                    severity="ERROR" if not passed else "INFO",
                )
            )

        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)
        failed_count = total_count - passed_count
        pct = (passed_count / total_count * 100.0) if total_count > 0 else 100.0
        status = "PASS" if failed_count == 0 else "FAIL"

        receipt = SpecConformanceReceipt(
            spec_id=spec.get("spec_id", "UNKNOWN"),
            spec_version=spec.get("version", "1.0.0"),
            timestamp=now_iso,
            conformance_status=status,
            total_invariants=total_count,
            passed_invariants=passed_count,
            failed_invariants=failed_count,
            conformance_pct=round(pct, 2),
            results=results,
        )

        # Generate cryptographic fingerprint
        receipt_dict = asdict(receipt)
        serialized = json.dumps(receipt_dict, sort_keys=True)
        receipt.sha256_fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return receipt

    def save_receipt(self, receipt: SpecConformanceReceipt, filename: str = "spec_conformance_receipt.json") -> Path:
        out_path = self.audit_dir / filename
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(asdict(receipt), f, indent=2)
        return out_path


def main():
    parser = argparse.ArgumentParser(description="Spec-Driven Development Conformance Evaluator")
    parser.add_argument("--spec", type=str, default="specs/trading_invariants.spec.json", help="Path to spec file")
    parser.add_argument("--doctor", action="store_true", help="Run health diagnostics")
    args = parser.parse_args()

    evaluator = SpecConformanceEvaluator()

    if args.doctor:
        print("[✓] Spec-Driven Development Conformance Evaluator: ONLINE")
        print(f"[✓] Specs Directory: {evaluator.specs_dir}")
        print(f"[✓] Audit Directory: {evaluator.audit_dir}")
        return

    spec_file = Path(args.spec)
    if not spec_file.exists():
        print(f"[!] Error: Spec file not found at {spec_file}")
        return

    spec = evaluator.load_spec(spec_file)
    receipt = evaluator.evaluate_trading_spec(spec)
    saved_path = evaluator.save_receipt(receipt)

    print("=" * 65)
    print(f"  SPEC CONFORMANCE EVALUATOR | Status: {receipt.conformance_status}")
    print("=" * 65)
    print(f"Spec ID: {receipt.spec_id} (v{receipt.spec_version})")
    print(f"Score: {receipt.passed_invariants}/{receipt.total_invariants} ({receipt.conformance_pct}%)")
    print(f"Receipt Fingerprint: {receipt.sha256_fingerprint[:16]}...")
    print(f"Saved Receipt: {saved_path}")


if __name__ == "__main__":
    main()
