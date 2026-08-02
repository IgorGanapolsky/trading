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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OPTION_OCC = re.compile(r"^([A-Z]+)(\d{6})([CP])(\d{8})$")
INACTIVE_PCS_STATES = {"closed", "cancelled", "rejected"}


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


def _expected_put_credit_qty_map(entry: dict[str, Any]) -> dict[tuple[str, float], float]:
    """Map (right, strike) -> signed qty from a journaled bull-put credit."""

    strikes = entry.get("strikes") or {}
    try:
        qty = abs(float(entry.get("quantity") or 1))
        short_put = float(strikes["short_put"])
        long_put = float(strikes["long_put"])
    except (KeyError, TypeError, ValueError):
        return {}
    if qty <= 0:
        qty = 1.0
    return {("P", short_put): -qty, ("P", long_put): qty}


def _normalize_expiry_ymd(value: Any) -> str:
    text = str(value or "").strip().replace("-", "")
    if len(text) == 8 and text.startswith("20"):
        return text[2:]
    return text if len(text) == 6 and text.isdigit() else ""


def _put_credit_expiry(key: str, entry: dict[str, Any]) -> str:
    explicit = _normalize_expiry_ymd(entry.get("expiry"))
    if explicit:
        return explicit
    match = re.match(r"^PCS_(\d{6})(?:_|$)", str(key))
    return match.group(1) if match else ""


JournalRecord = tuple[str, dict[str, Any], str]
LegKey = tuple[str, float]


def _group_legs_by_expiry(legs: list[ParsedLeg]) -> dict[str, list[ParsedLeg]]:
    grouped: dict[str, list[ParsedLeg]] = {}
    for leg in legs:
        grouped.setdefault(leg.expiry_ymd, []).append(leg)
    return grouped


def _journaled_structures(
    expiry_ymd: str,
    entries: dict[str, Any],
    pcs_entries: dict[str, Any],
) -> list[JournalRecord]:
    ic_prefix = _ic_key(expiry_ymd)
    journaled: list[JournalRecord] = [
        (str(key), entry, "iron_condor")
        for key, entry in entries.items()
        if isinstance(entry, dict)
        and (str(key) == ic_prefix or str(key).startswith(f"{ic_prefix}_"))
    ]
    for key, entry in pcs_entries.items():
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "open").strip().lower()
        if status in INACTIVE_PCS_STATES:
            continue
        if _put_credit_expiry(str(key), entry) == expiry_ymd:
            journaled.append((str(key), entry, "spy_put_credit"))
    return journaled


def _entry_quantity(entry: dict[str, Any]) -> float:
    try:
        return abs(float(entry.get("quantity") or 1))
    except (TypeError, ValueError):
        return 1.0


def _expected_from_journal(
    expiry_ymd: str,
    journaled: list[JournalRecord],
    max_contracts_per_trade: float,
) -> tuple[dict[LegKey, float], list[str], list[InventoryFinding]]:
    expected: dict[LegKey, float] = {}
    journal_keys: list[str] = []
    findings: list[InventoryFinding] = []
    for journal_key, journal_entry, family in journaled:
        journal_keys.append(journal_key)
        entry_qty = _entry_quantity(journal_entry)
        if entry_qty > max_contracts_per_trade + 1e-9:
            findings.append(
                InventoryFinding(
                    code="LOT_SIZE_EXCEEDED",
                    severity="block",
                    message=(
                        f"{journal_key} quantity={entry_qty} exceeds "
                        f"max_contracts_per_trade={max_contracts_per_trade}"
                    ),
                    expiry_ymd=expiry_ymd,
                    details={"journal_key": journal_key, "quantity": entry_qty},
                )
            )
        mapping = (
            _expected_put_credit_qty_map(journal_entry)
            if family == "spy_put_credit"
            else _expected_structure_qty_map(journal_entry)
        )
        for leg_key, qty in mapping.items():
            expected[leg_key] = expected.get(leg_key, 0.0) + qty
    return expected, journal_keys, findings


def _actual_qty_map(exp_legs: list[ParsedLeg]) -> dict[LegKey, float]:
    actual: dict[LegKey, float] = {}
    for leg in exp_legs:
        key = (leg.right, leg.strike)
        actual[key] = actual.get(key, 0.0) + leg.qty
    return actual


def _lot_size_finding(
    expiry_ymd: str,
    actual: dict[LegKey, float],
    expected: dict[LegKey, float],
    max_contracts_per_trade: float,
) -> InventoryFinding | None:
    offenders = [
        {
            "right": leg_key[0],
            "strike": leg_key[1],
            "actual_qty": actual_qty,
            "journal_qty": expected.get(leg_key, 0.0),
        }
        for leg_key, actual_qty in actual.items()
        if abs(actual_qty) > max(max_contracts_per_trade, abs(expected.get(leg_key, 0.0))) + 1e-9
    ]
    if not offenders:
        return None
    return InventoryFinding(
        code="LOT_SIZE_EXCEEDED",
        severity="block",
        message=(
            f"Expiry {expiry_ymd} has aggregated leg quantity not explained "
            "by distinct one-lot journal records"
        ),
        expiry_ymd=expiry_ymd,
        details={"offenders": offenders},
    )


def _quantity_mismatch_findings(
    expiry_ymd: str,
    actual: dict[LegKey, float],
    expected: dict[LegKey, float],
) -> list[InventoryFinding]:
    findings: list[InventoryFinding] = []
    for key, qty in actual.items():
        expected_qty = expected.get(key)
        if expected_qty is None or abs(qty - expected_qty) <= 1e-9:
            continue
        findings.append(
            InventoryFinding(
                code="QTY_MISMATCH",
                severity="block",
                message=(
                    f"Expiry {expiry_ymd}: {key[0]}{key[1]:g} qty={qty} does not match "
                    f"journaled qty={expected_qty}"
                ),
                expiry_ymd=expiry_ymd,
                details={
                    "right": key[0],
                    "strike": key[1],
                    "actual_qty": qty,
                    "journal_qty": expected_qty,
                },
            )
        )
    return findings


def _composition_findings(
    expiry_ymd: str,
    actual: dict[LegKey, float],
    expected: dict[LegKey, float],
) -> list[InventoryFinding]:
    extras = [
        {"right": key[0], "strike": key[1], "qty": qty}
        for key, qty in actual.items()
        if key not in expected
    ]
    missing = [
        {"right": key[0], "strike": key[1], "journal_qty": qty}
        for key, qty in expected.items()
        if key not in actual
    ]
    findings = _quantity_mismatch_findings(expiry_ymd, actual, expected)
    if extras:
        findings.append(
            InventoryFinding(
                code="EXTRA_LEGS",
                severity="block",
                message=(
                    f"Expiry {expiry_ymd}: {len(extras)} open leg(s) not in journaled structure "
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
                message=f"Expiry {expiry_ymd}: journaled legs missing from broker book",
                expiry_ymd=expiry_ymd,
                details={"missing": missing},
            )
        )
    return findings


def _overstack_finding(
    expiry_ymd: str,
    exp_legs: list[ParsedLeg],
    expected: dict[LegKey, float],
) -> InventoryFinding | None:
    short_units = sum(abs(leg.qty) for leg in exp_legs if leg.qty < 0)
    expected_short_units = sum(abs(qty) for qty in expected.values() if qty < 0)
    if short_units <= expected_short_units + 1e-9:
        return None
    return InventoryFinding(
        code="SAME_EXPIRY_OVERSTACK",
        severity="block",
        message=(
            f"Expiry {expiry_ymd}: short-leg units={short_units} exceed "
            f"journaled units={expected_short_units}"
        ),
        expiry_ymd=expiry_ymd,
        details={"short_units": short_units, "leg_count": len(exp_legs)},
    )


def _audit_expiry(
    expiry_ymd: str,
    exp_legs: list[ParsedLeg],
    entries: dict[str, Any],
    pcs_entries: dict[str, Any],
    max_contracts_per_trade: float,
) -> list[InventoryFinding]:
    journaled = _journaled_structures(expiry_ymd, entries, pcs_entries)
    if not journaled:
        return [
            InventoryFinding(
                code="UNJOURNALED_EXPIRY",
                severity="block",
                message=(
                    f"Open option expiry {expiry_ymd} has no IC or PCS journal record — "
                    "exit managers cannot evaluate stop/target"
                ),
                expiry_ymd=expiry_ymd,
                details={"leg_symbols": [leg.symbol for leg in exp_legs]},
            )
        ]

    expected, journal_keys, findings = _expected_from_journal(
        expiry_ymd,
        journaled,
        max_contracts_per_trade,
    )
    if not expected:
        findings.append(
            InventoryFinding(
                code="JOURNAL_STRIKES_INCOMPLETE",
                severity="block",
                message=f"Expiry {expiry_ymd} journal records have incomplete strikes",
                expiry_ymd=expiry_ymd,
                details={"journal_keys": journal_keys},
            )
        )
        return findings

    actual = _actual_qty_map(exp_legs)
    lot_size = _lot_size_finding(
        expiry_ymd,
        actual,
        expected,
        max_contracts_per_trade,
    )
    if lot_size:
        findings.append(lot_size)
    findings.extend(_composition_findings(expiry_ymd, actual, expected))
    overstack = _overstack_finding(expiry_ymd, exp_legs, expected)
    if overstack:
        findings.append(overstack)
    return findings


def audit_open_inventory(
    positions: list[dict[str, Any]] | None,
    ic_entries: dict[str, Any] | None,
    put_credit_entries: dict[str, Any] | None = None,
    *,
    max_contracts_per_trade: float = 1.0,
    max_concurrent_iron_condors: int = 2,
) -> InventoryAuditResult:
    """Audit open option legs against controlled-experiment + journal records."""
    legs = normalize_positions(positions)
    findings: list[InventoryFinding] = []
    entries = ic_entries if isinstance(ic_entries, dict) else {}
    pcs_entries = put_credit_entries if isinstance(put_credit_entries, dict) else {}

    max_abs = max((abs(leg.qty) for leg in legs), default=0.0)
    expiries = sorted({leg.expiry_ymd for leg in legs})

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

    for expiry_ymd, exp_legs in sorted(_group_legs_by_expiry(legs).items()):
        findings.extend(
            _audit_expiry(
                expiry_ymd,
                exp_legs,
                entries,
                pcs_entries,
                max_contracts_per_trade,
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
        audited_at=datetime.now(UTC).isoformat(),
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

    put_credit_entries: dict[str, Any] = {}
    put_credit_path = root / "data" / "put_credit_entries.json"
    if put_credit_path.exists():
        raw = json.loads(put_credit_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            put_credit_entries = raw

    return audit_open_inventory(
        positions,
        entries,
        put_credit_entries,
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
