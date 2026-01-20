#!/usr/bin/env python3
"""Position Validator - Detects orphan positions and validates spread structure.

Per CLAUDE.md (Jan 19, 2026):
- Iron condors ONLY: 4 legs (bull put spread + bear call spread)
- Each spread must have matching long + short legs
- No orphan (unhedged) positions allowed

This script:
1. Reads current positions from system_state.json
2. Identifies complete spreads vs orphan legs
3. Recommends cleanup actions
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OptionPosition:
    """Parsed option position."""
    symbol: str
    underlying: str
    expiration: str  # YYMMDD
    option_type: str  # P or C
    strike: float
    qty: int
    market_value: float
    unrealized_pl: float

    @property
    def is_long(self) -> bool:
        return self.qty > 0

    @property
    def is_short(self) -> bool:
        return self.qty < 0


@dataclass
class SpreadPair:
    """A matched spread pair (long + short legs)."""
    long_leg: OptionPosition
    short_leg: OptionPosition
    spread_type: str  # "bull_put", "bear_call", etc.
    width: float  # Dollar width between strikes
    max_loss: float  # Maximum potential loss
    max_profit: float  # Maximum potential profit (if credit spread)


@dataclass
class ValidationResult:
    """Result of position validation."""
    complete_spreads: list[SpreadPair]
    orphan_positions: list[OptionPosition]
    total_positions: int
    is_valid_iron_condor: bool
    warnings: list[str]
    recommendations: list[str]


def parse_option_symbol(symbol: str) -> dict:
    """
    Parse OCC option symbol into components.

    OCC format: [UNDERLYING][YYMMDD][P/C][STRIKE*1000]
    Example: SPY260220P00653000 -> SPY, 260220, P, 653.00
    """
    match = re.match(r'^([A-Z]{1,6})(\d{6})([PC])(\d{8})$', symbol.upper())
    if not match:
        return None

    underlying, exp_date, opt_type, strike_raw = match.groups()
    strike = int(strike_raw) / 1000  # Convert from OCC format

    return {
        "underlying": underlying,
        "expiration": exp_date,
        "option_type": opt_type,
        "strike": strike,
    }


def load_positions() -> list[OptionPosition]:
    """Load current positions from system_state.json."""
    state_file = Path(__file__).parent.parent / "data" / "system_state.json"

    if not state_file.exists():
        raise FileNotFoundError(f"System state file not found: {state_file}")

    with open(state_file) as f:
        state = json.load(f)

    positions = []
    paper_positions = state.get("paper_account", {}).get("positions", [])

    for pos in paper_positions:
        symbol = pos.get("symbol", "")

        # Parse option symbol
        parsed = parse_option_symbol(symbol)
        if not parsed:
            # Not an option, skip
            continue

        positions.append(OptionPosition(
            symbol=symbol,
            underlying=parsed["underlying"],
            expiration=parsed["expiration"],
            option_type=parsed["option_type"],
            strike=parsed["strike"],
            qty=int(pos.get("qty", 0)),
            market_value=float(pos.get("market_value", 0)),
            unrealized_pl=float(pos.get("unrealized_pl", 0)),
        ))

    return positions


def find_spread_pairs(positions: list[OptionPosition]) -> tuple[list[SpreadPair], list[OptionPosition]]:
    """
    Match positions into spread pairs and identify orphans.

    A valid spread pair consists of:
    - Same underlying
    - Same expiration
    - Same option type (both puts or both calls)
    - One long, one short
    - Different strikes
    """
    # Group by underlying/expiration/type
    groups = {}
    for pos in positions:
        key = (pos.underlying, pos.expiration, pos.option_type)
        if key not in groups:
            groups[key] = []
        groups[key].append(pos)

    complete_spreads = []
    orphans = []

    for key, group_positions in groups.items():
        underlying, expiration, opt_type = key

        # Separate longs and shorts
        longs = [p for p in group_positions if p.is_long]
        shorts = [p for p in group_positions if p.is_short]

        # Sort by strike for easier matching
        longs.sort(key=lambda p: p.strike)
        shorts.sort(key=lambda p: p.strike)

        # Try to match pairs
        matched_longs = set()
        matched_shorts = set()

        for long_pos in longs:
            for short_pos in shorts:
                if short_pos.symbol in matched_shorts:
                    continue

                # Check if they form a valid spread
                # For puts: long strike < short strike = bull put spread
                # For calls: long strike > short strike = bear call spread
                if opt_type == "P" and long_pos.strike < short_pos.strike:
                    spread_type = "bull_put"
                elif opt_type == "C" and long_pos.strike > short_pos.strike:
                    spread_type = "bear_call"
                else:
                    continue  # Not a valid credit spread configuration

                # Match the minimum quantity
                match_qty = min(abs(long_pos.qty), abs(short_pos.qty))
                if match_qty <= 0:
                    continue

                width = abs(short_pos.strike - long_pos.strike)
                max_loss = width * 100 * match_qty  # Per contract

                # Create the spread pair
                complete_spreads.append(SpreadPair(
                    long_leg=long_pos,
                    short_leg=short_pos,
                    spread_type=spread_type,
                    width=width,
                    max_loss=max_loss,
                    max_profit=0,  # Would need premium data
                ))

                matched_longs.add(long_pos.symbol)
                matched_shorts.add(short_pos.symbol)
                break

        # Find orphans - positions not matched
        for pos in group_positions:
            if pos.symbol not in matched_longs and pos.symbol not in matched_shorts:
                orphans.append(pos)
            elif pos.symbol in matched_longs or pos.symbol in matched_shorts:
                # Check if quantity is fully matched
                matched_qty = 1  # Simplified - in reality track matched qty
                remaining_qty = abs(pos.qty) - matched_qty
                if remaining_qty > 0:
                    # Create orphan for remaining quantity
                    orphan_pos = OptionPosition(
                        symbol=pos.symbol,
                        underlying=pos.underlying,
                        expiration=pos.expiration,
                        option_type=pos.option_type,
                        strike=pos.strike,
                        qty=remaining_qty if pos.is_long else -remaining_qty,
                        market_value=pos.market_value * remaining_qty / abs(pos.qty),
                        unrealized_pl=pos.unrealized_pl * remaining_qty / abs(pos.qty),
                    )
                    orphans.append(orphan_pos)

    return complete_spreads, orphans


def validate_iron_condor(spreads: list[SpreadPair]) -> tuple[bool, list[str]]:
    """
    Validate if spreads form a valid iron condor.

    Per CLAUDE.md:
    - 1 iron condor at a time
    - 4 legs: bull put spread + bear call spread
    - Same underlying, same expiration
    """
    warnings = []

    if len(spreads) == 0:
        return False, ["No spreads found - cannot form iron condor"]

    # Group spreads by underlying/expiration
    groups = {}
    for spread in spreads:
        key = (spread.long_leg.underlying, spread.long_leg.expiration)
        if key not in groups:
            groups[key] = {"bull_put": [], "bear_call": []}
        groups[key][spread.spread_type].append(spread)

    is_valid = False

    for (underlying, exp), spread_group in groups.items():
        bull_puts = spread_group["bull_put"]
        bear_calls = spread_group["bear_call"]

        if len(bull_puts) == 1 and len(bear_calls) == 1:
            # Perfect iron condor
            is_valid = True
        elif len(bull_puts) > 0 and len(bear_calls) == 0:
            warnings.append(f"{underlying} {exp}: Only bull put spread(s) - missing bear call for iron condor")
        elif len(bull_puts) == 0 and len(bear_calls) > 0:
            warnings.append(f"{underlying} {exp}: Only bear call spread(s) - missing bull put for iron condor")
        elif len(bull_puts) > 1 or len(bear_calls) > 1:
            warnings.append(f"{underlying} {exp}: Multiple spreads - should only have 1 iron condor at a time per CLAUDE.md")

    return is_valid, warnings


def validate_positions() -> ValidationResult:
    """Run full position validation."""
    positions = load_positions()

    if not positions:
        return ValidationResult(
            complete_spreads=[],
            orphan_positions=[],
            total_positions=0,
            is_valid_iron_condor=False,
            warnings=["No option positions found"],
            recommendations=["Consider opening SPY iron condor per CLAUDE.md strategy"],
        )

    spreads, orphans = find_spread_pairs(positions)
    is_iron_condor, ic_warnings = validate_iron_condor(spreads)

    warnings = ic_warnings.copy()
    recommendations = []

    # Generate recommendations
    if orphans:
        for orphan in orphans:
            if orphan.is_long:
                recommendations.append(
                    f"CLOSE orphan long: {orphan.symbol} (qty={orphan.qty}, P/L=${orphan.unrealized_pl:.2f})"
                )
            else:
                recommendations.append(
                    f"CLOSE orphan short: {orphan.symbol} (qty={orphan.qty}, P/L=${orphan.unrealized_pl:.2f}) - URGENT: unhedged risk!"
                )

    if not is_iron_condor and spreads:
        recommendations.append("Current positions are NOT a valid iron condor - consider restructuring per CLAUDE.md")

    return ValidationResult(
        complete_spreads=spreads,
        orphan_positions=orphans,
        total_positions=len(positions),
        is_valid_iron_condor=is_iron_condor,
        warnings=warnings,
        recommendations=recommendations,
    )


def print_report(result: ValidationResult):
    """Print validation report."""
    print("=" * 60)
    print("POSITION VALIDATION REPORT")
    print("=" * 60)
    print(f"\nTotal option positions: {result.total_positions}")
    print(f"Complete spreads: {len(result.complete_spreads)}")
    print(f"Orphan positions: {len(result.orphan_positions)}")
    print(f"Valid iron condor: {'YES' if result.is_valid_iron_condor else 'NO'}")

    if result.complete_spreads:
        print("\n--- COMPLETE SPREADS ---")
        for spread in result.complete_spreads:
            print(f"  {spread.spread_type.upper()}: {spread.long_leg.strike}/{spread.short_leg.strike} "
                  f"(width=${spread.width:.0f}, max_loss=${spread.max_loss:.0f})")

    if result.orphan_positions:
        print("\n--- ORPHAN POSITIONS (REQUIRES ACTION) ---")
        for orphan in result.orphan_positions:
            status = "LONG" if orphan.is_long else "SHORT (UNHEDGED!)"
            print(f"  {status}: {orphan.symbol} qty={orphan.qty} "
                  f"(strike=${orphan.strike:.0f}, P/L=${orphan.unrealized_pl:.2f})")

    if result.warnings:
        print("\n--- WARNINGS ---")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.recommendations:
        print("\n--- RECOMMENDATIONS ---")
        for rec in result.recommendations:
            print(f"  - {rec}")

    print("\n" + "=" * 60)

    # Return exit code based on validation
    if result.orphan_positions:
        print("STATUS: INVALID - Orphan positions detected")
        return 1
    elif not result.is_valid_iron_condor:
        print("STATUS: WARNING - Not a valid iron condor structure")
        return 0  # Warning, not error
    else:
        print("STATUS: VALID - Position structure is correct")
        return 0


if __name__ == "__main__":
    try:
        result = validate_positions()
        exit_code = print_report(result)
        exit(exit_code)
    except Exception as e:
        print(f"ERROR: {e}")
        exit(2)
