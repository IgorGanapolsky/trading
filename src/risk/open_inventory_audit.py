"""Open option inventory audit for iron-condor validation hygiene.

Detects the failure mode we hit on SPY 2026-08-21:

* journaled 1-lot IC (P703-708 / C776-781)
* broker book showed 2-lot call vertical + an extra put vertical on the same expiry

Without this check, validation entries stack on dirty inventory, the exit loop
cannot map legs cleanly to credits, and the controlled-experiment 1-lot rule is
silently violated after fill.

Pure functions. No broker closes. Callers decide whether to block new entries.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPTION_OCC = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")


@dataclass(frozen=True)
class ParsedLeg:
    symbol: str
    root: str
    expiry_ymd: str  # YYMMDD
    right: str  # C or P
    strike: float
    qty: float


@dataclass
class InventoryFinding:
    code: str
    severity: str  # "block" | "warn"
    message: str
    expiry_ymd: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class InventoryAuditResult:
    clean: bool
    findings: list[InventoryFinding] = field(default_factory=list)
    legs: list[ParsedLeg] = field(default_factory=list)
    expiries: list[str] = field(default_factory=list)
    max_abs_qty: float = 0.0
    option_leg_count: int = 0
    audited_at: str = ""

    def block_reasons(self) -> list[str]:
        return [f.message for f in self.findings if f.severity == "block"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "clean": self.clean,
            "audited_at": self.audited_at,
            "option_leg_count": self.option_leg_count,
            "max_abs_qty": self.max_abs_qty,
            "expiries": list(self.expiries),
            "findings": [asdict(f) for f in self.findings],
            "legs": [asdict(leg) for leg in self.legs],
            "block_reasons": self.block_reasons(),
        }


def parse_option_leg(symbol: str, qty: float) -> ParsedLeg | None:
    match = OPTION_OCC.match(str(symbol).strip().upper())
    if not match:
        return None
    root, ymd, right, strike_raw = match.groups()
    return ParsedLeg(
        symbol=str(symbol).strip().upper(),
        root=root,
        expiry_ymd=ymd,
        right=right,
        strike=int(strike_raw) / 1000.0,
        qty=float(qty),
    )


def _qty_from_position(row: dict[str, Any]) -> float:
    for key in ("qty", "quantity", "qty_available"):
        if row.get(key) is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    return 0.0


def normalize_positions(positions: list[dict[str, Any]] | None) -> list[ParsedLeg]:
    legs: list[ParsedLeg] = []
    for row in positions or []:
        if not isinstance(row, dict):
            continue
        symbol = row.get("symbol")
        if not symbol:
            continue
        parsed = parse_option_leg(str(symbol), _qty_from_position(row))
        if parsed is not None and abs(parsed.qty) > 1e-9:
            legs.append(parsed)
    return legs


def _ic_key(expiry_ymd: str) -> str:
    return f"IC_{expiry_ymd}"


def _expected_structure_qty_map(entry: dict[str, Any]) -> dict[tuple[str, float], float]:
    """Map (right, strike) -> signed qty from a journaled IC entry."""
    strikes = entry.get("strikes") or {}
    try:
        qty = abs(float(entry.get("quantity") or 1))
    except (TypeError, ValueError):
        qty = 1.0
    if qty <= 0:
        qty = 1.0

    mapping: dict[tuple[str, float], float] = {}
    try:
        short_put = float(strikes["short_put"])
        long_put = float(strikes["long_put"])
        short_call = float(strikes["short_call"])
        long_call = float(strikes["long_call"])
    except (KeyError, TypeError, ValueError):
        return mapping

    mapping[("P", short_put)] = -qty
    mapping[("P", long_put)] = qty
    mapping[("C", short_call)] = -qty
    mapping[("C", long_call)] = qty
    return mapping


def audit_open_inventory(
    positions: list[dict[str, Any]] | None,
    ic_entries: dict[str, Any] | None,
    *,
    max_contracts_per_trade: float = 1.0,
    max_concurrent_iron_condors: int = 2,
) -> InventoryAuditResult:
    """Audit open option legs against controlled-experiment + journal records."""
    legs = normalize_positions(positions)
    findings: list[InventoryFinding] = []
    entries = ic_entries if isinstance(ic_entries, dict) else {}

    max_abs = max((abs(leg.qty) for leg in legs), default=0.0)
    expiries = sorted({leg.expiry_ymd for leg in legs})

    # Global lot-size rule: any open leg above 1-lot violates validation hygiene.
    if max_abs > max_contracts_per_trade + 1e-9:
        offenders = [
            {"symbol": leg.symbol, "qty": leg.qty}
            for leg in legs
            if abs(leg.qty) > max_contracts_per_trade + 1e-9
        ]
        findings.append(
            InventoryFinding(
                code="LOT_SIZE_EXCEEDED",
                severity="block",
                message=(
                    f"Open option leg qty exceeds max_contracts_per_trade="
                    f"{max_contracts_per_trade} (max_abs_qty={max_abs})"
                ),
                details={"offenders": offenders, "max_abs_qty": max_abs},
            )
        )

    # Too many distinct expiries with structures can still be OK (max concurrent ICs),
    # but > max concurrent expiries is a block for new entries.
    if len(expiries) > max_concurrent_iron_condors:
        findings.append(
            InventoryFinding(
                code="TOO_MANY_EXPIRIES",
                severity="block",
                message=(
                    f"{len(expiries)} open option expiries exceed "
                    f"max_concurrent_iron_condors={max_concurrent_iron_condors}"
                ),
                details={"expiries": expiries},
            )
        )

    by_expiry: dict[str, list[ParsedLeg]] = {}
    for leg in legs:
        by_expiry.setdefault(leg.expiry_ymd, []).append(leg)

    for expiry_ymd, exp_legs in sorted(by_expiry.items()):
        key = _ic_key(expiry_ymd)
        entry = entries.get(key)
        if not isinstance(entry, dict):
            # Legacy keys sometimes used IC_YYYYMMDD — try nothing else; CI already
            # covers missing keys. Treat as block for new entries (exit loop blind).
            findings.append(
                InventoryFinding(
                    code="UNJOURNALED_EXPIRY",
                    severity="block",
                    message=(
                        f"Open option expiry {expiry_ymd} has no {key} record in "
                        "ic_entries.json — exit loop cannot evaluate stop/target"
                    ),
                    expiry_ymd=expiry_ymd,
                    details={"leg_symbols": [leg.symbol for leg in exp_legs]},
                )
            )
            continue

        expected = _expected_structure_qty_map(entry)
        actual: dict[tuple[str, float], float] = {}
        for leg in exp_legs:
            k = (leg.right, leg.strike)
            actual[k] = actual.get(k, 0.0) + leg.qty

        if not expected:
            findings.append(
                InventoryFinding(
                    code="JOURNAL_STRIKES_INCOMPLETE",
                    severity="block",
                    message=f"{key} exists but strikes are incomplete",
                    expiry_ymd=expiry_ymd,
                    details={"entry_keys": sorted(entry.keys())},
                )
            )
            continue

        # Qty / composition mismatch vs journaled 4-leg structure
        extras = []
        for k, qty in actual.items():
            exp_qty = expected.get(k)
            if exp_qty is None:
                extras.append({"right": k[0], "strike": k[1], "qty": qty})
            elif abs(qty - exp_qty) > 1e-9:
                findings.append(
                    InventoryFinding(
                        code="QTY_MISMATCH",
                        severity="block",
                        message=(
                            f"{key}: {k[0]}{k[1]:g} qty={qty} does not match "
                            f"journaled qty={exp_qty}"
                        ),
                        expiry_ymd=expiry_ymd,
                        details={
                            "right": k[0],
                            "strike": k[1],
                            "actual_qty": qty,
                            "journal_qty": exp_qty,
                        },
                    )
                )

        missing = []
        for k, exp_qty in expected.items():
            if k not in actual:
                missing.append({"right": k[0], "strike": k[1], "journal_qty": exp_qty})

        if extras:
            findings.append(
                InventoryFinding(
                    code="EXTRA_LEGS",
                    severity="block",
                    message=(
                        f"{key}: {len(extras)} open leg(s) not in journaled structure "
                        f"(orphan verticals or residual risk)"
                    ),
                    expiry_ymd=expiry_ymd,
                    details={"extras": extras},
                )
            )
        if missing:
            findings.append(
                InventoryFinding(
                    code="MISSING_LEGS",
                    severity="block",
                    message=f"{key}: journaled legs missing from broker book",
                    expiry_ymd=expiry_ymd,
                    details={"missing": missing},
                )
            )

        # Same-expiry multi-structure signal: more than 4 legs or extra shorts
        short_units = sum(abs(leg.qty) for leg in exp_legs if leg.qty < 0)
        if short_units > max_contracts_per_trade * 2 + 1e-9:
            # One IC has 2 short legs (put+call) * qty
            findings.append(
                InventoryFinding(
                    code="SAME_EXPIRY_OVERSTACK",
                    severity="block",
                    message=(
                        f"Expiry {expiry_ymd}: short-leg units={short_units} exceed "
                        f"one 1-lot iron condor (expected <= {max_contracts_per_trade * 2})"
                    ),
                    expiry_ymd=expiry_ymd,
                    details={"short_units": short_units, "leg_count": len(exp_legs)},
                )
            )

    clean = not any(f.severity == "block" for f in findings)
    return InventoryAuditResult(
        clean=clean,
        findings=findings,
        legs=legs,
        expiries=expiries,
        max_abs_qty=max_abs,
        option_leg_count=len(legs),
        audited_at=datetime.now(timezone.utc).isoformat(),
    )


def audit_from_files(
    repo_root: Path | str,
    *,
    max_contracts_per_trade: float = 1.0,
    max_concurrent_iron_condors: int = 2,
) -> InventoryAuditResult:
    root = Path(repo_root)
    state_path = root / "data" / "system_state.json"
    entries_path = root / "data" / "ic_entries.json"

    positions: list[dict[str, Any]] = []
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        positions = list(state.get("positions") or [])
        if not positions:
            # Some syncs only populate performance.open_positions
            open_pos = (state.get("performance") or {}).get("open_positions") or []
            for row in open_pos:
                if not isinstance(row, dict):
                    continue
                positions.append(
                    {
                        "symbol": row.get("symbol"),
                        "qty": row.get("quantity", row.get("qty")),
                    }
                )

    entries: dict[str, Any] = {}
    if entries_path.exists():
        raw = json.loads(entries_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            entries = raw

    return audit_open_inventory(
        positions,
        entries,
        max_contracts_per_trade=max_contracts_per_trade,
        max_concurrent_iron_condors=max_concurrent_iron_condors,
    )


def write_audit_report(
    result: InventoryAuditResult,
    path: Path | str,
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return out
