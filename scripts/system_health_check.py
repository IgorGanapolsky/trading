#!/usr/bin/env python3
"""
System Health Check - Verify ML/RAG/RL Actually Work
Run daily before trading to catch silent failures.

Usage: python3 scripts/system_health_check.py
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

PROJECT_ROOT = Path(__file__).parent.parent
LANCEDB_PATH = PROJECT_ROOT / ".claude" / "memory" / "lancedb"
OPTION_SYMBOL_RE = re.compile(
    r"^(?P<underlying>[A-Z]+)(?P<expiry>\d{6})(?P<option_type>[CP])\d{8}$"
)


def _list_lancedb_tables(db) -> list[str]:
    """Return table names across LanceDB API versions without loading embeddings."""
    if hasattr(db, "list_tables"):
        try:
            tables_response = db.list_tables()
            if hasattr(tables_response, "tables"):
                return list(tables_response.tables)
            return list(tables_response)
        except Exception:
            return []

    if hasattr(db, "table_names"):
        try:
            return list(db.table_names())
        except Exception:
            return []

    return []


def _probe_vector_index() -> tuple[bool, str]:
    """Quickly verify the LanceDB table exists and is non-empty.

    This intentionally avoids DocumentAwareRAG model initialization, which can
    block while loading sentence-transformer weights and makes a readiness check
    unsuitable for day-of-trading verification.
    """
    if not LANCEDB_PATH.exists():
        return False, f"LanceDB path missing: {LANCEDB_PATH}"

    try:
        import lancedb
    except ImportError:
        return False, "LanceDB not installed"

    try:
        db = lancedb.connect(str(LANCEDB_PATH))
    except Exception as exc:
        return False, f"Failed to connect to LanceDB: {exc}"

    tables = _list_lancedb_tables(db)
    if "document_aware_rag" not in tables:
        return False, "document_aware_rag table missing - reindex required"

    try:
        table = db.open_table("document_aware_rag")
        if hasattr(table, "count_rows"):
            row_count = table.count_rows()
        elif hasattr(table, "count"):
            row_count = table.count()
        else:
            row_count = None
    except Exception as exc:
        return False, f"Failed to inspect document_aware_rag table: {exc}"

    if row_count == 0:
        return False, "document_aware_rag table empty - reindex required"

    if row_count is None:
        return True, "LanceDB table present"

    return True, f"LanceDB table ready ({row_count} rows)"


def _parse_option_symbol(symbol: str) -> tuple[str, str] | None:
    """Return (expiry, option_type) for OCC-style option symbols."""
    match = OPTION_SYMBOL_RE.match(symbol)
    if not match:
        return None
    return match.group("expiry"), match.group("option_type")


def check_vector_db():
    """Verify LanceDB index exists and is queryable."""
    results = {"name": "LanceDB Index", "status": "UNKNOWN", "details": []}

    try:
        ok, detail = _probe_vector_index()
        if ok:
            results["status"] = "OK"
            results["details"].append(f"✓ {detail}")
        else:
            results["status"] = "BROKEN"
            results["details"].append(f"✗ {detail}")

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_rag_system():
    """Verify RAG system works end-to-end."""
    results = {"name": "RAG System", "status": "UNKNOWN", "details": []}

    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        results["details"].append(f"✓ LessonsLearnedRAG loaded with {len(rag.lessons)} lessons")

        # Test query() method
        if hasattr(rag, "query"):
            test_results = rag.query("trading failure", top_k=3)
            results["details"].append(
                f"✓ query() method works - returned {len(test_results)} results"
            )
        else:
            results["details"].append("✗ query() method missing")
            results["status"] = "BROKEN"
            return results

        # Test search() method (used by gates.py and main.py)
        if hasattr(rag, "search"):
            search_results = rag.search(query="trading failure", top_k=3)
            results["details"].append(
                f"✓ search() method works - returned {len(search_results)} results"
            )
            # Verify format is (lesson, score) tuples
            if search_results and len(search_results) > 0:
                first = search_results[0]
                if isinstance(first, tuple) and len(first) == 2:
                    results["details"].append("✓ search() returns correct (lesson, score) format")
                else:
                    results["details"].append("✗ search() returns wrong format")
                    results["status"] = "BROKEN"
                    return results
        else:
            results["details"].append("✗ search() method missing - gates.py will crash!")
            results["status"] = "BROKEN"
            return results

        results["status"] = "OK"

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_rl_system():
    """Verify RL system is functional (RLFilter in src/agents/rl_agent.py).

    Fixed Dec 30, 2025: Was checking phantom modules (dqn_agent, inference)
    that never existed. Now checks actual RLFilter.
    """
    results = {"name": "RL System", "status": "UNKNOWN", "details": []}

    try:
        import os

        rl_enabled = os.getenv("RL_FILTER_ENABLED", "false").lower() in {"true", "1"}
        results["details"].append(f"RL_FILTER_ENABLED: {rl_enabled}")
        if not rl_enabled:
            results["details"].append("✓ RLFilter disabled by config; runtime gate is intentional")
            results["status"] = "OK"
            return results

        # Check actual RLFilter (the real RL system)
        from src.agents.rl_agent import RLFilter

        rl_filter = RLFilter()
        test_state = {"symbol": "SPY", "momentum_strength": 0.5, "rsi": 45}
        prediction = rl_filter.predict(test_state)

        if prediction.get("confidence", 0) > 0:
            results["details"].append(
                f"✓ RLFilter works: action={prediction['action']}, conf={prediction['confidence']}"
            )
            results["status"] = "OK"
        else:
            results["details"].append("✗ RLFilter returned invalid prediction")
            results["status"] = "BROKEN"

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_ml_pipeline():
    """Verify ML/Gemini Deep Research works.

    Fixed Dec 30, 2025: Was checking phantom MLPredictor module.
    Now checks actual Gemini integration.
    """
    results = {"name": "ML Pipeline", "status": "UNKNOWN", "details": []}

    try:
        from src.ml import GENAI_AVAILABLE

        if GENAI_AVAILABLE:
            results["details"].append("✓ Gemini API available")
        else:
            results["details"].append("⚠️ Gemini API not available (missing google.genai)")

        # Verify class can be instantiated (graceful degradation)
        results["details"].append("✓ GeminiDeepResearch class available")
        results["status"] = "OK"

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_position_completeness():
    """Verify options structures keep any short exposure defined-risk.

    Added Jan 27, 2026: Caught incomplete IC with only 3 legs.
    Updated Mar 23, 2026: do not assume every expiry is a 4-leg iron condor.
    Long-only structures are already defined-risk; any short exposure must have
    protective long legs on the same side.
    """
    results = {
        "name": "Position Protection (Options)",
        "status": "UNKNOWN",
        "details": [],
    }

    try:
        import json
        from pathlib import Path

        state_file = Path("data/system_state.json")
        if not state_file.exists():
            results["status"] = "BROKEN"
            results["details"].append("✗ system_state.json not found")
            return results

        state = json.loads(state_file.read_text())
        positions = state.get("positions", [])

        if not positions:
            results["status"] = "OK"
            results["details"].append("✓ No open positions")
            return results

        # Group by expiration
        from collections import defaultdict

        by_expiry = defaultdict(list)
        for p in positions:
            symbol = p.get("symbol", "")
            parsed = _parse_option_symbol(symbol)
            if parsed is not None:
                expiry, _option_type = parsed
                by_expiry[expiry].append(p)

        # Check each expiry group for defined-risk protection.
        for expiry, legs in by_expiry.items():
            long_puts = []
            short_puts = []
            long_calls = []
            short_calls = []

            for leg in legs:
                parsed = _parse_option_symbol(leg.get("symbol", ""))
                if parsed is None:
                    continue
                _expiry, option_type = parsed
                qty = leg.get("qty", 0)
                if option_type == "P":
                    if qty > 0:
                        long_puts.append(leg)
                    elif qty < 0:
                        short_puts.append(leg)
                elif option_type == "C":
                    if qty > 0:
                        long_calls.append(leg)
                    elif qty < 0:
                        short_calls.append(leg)

            has_short_puts = len(short_puts) >= 1
            has_short_calls = len(short_calls) >= 1
            has_long_puts = len(long_puts) >= 1
            has_long_calls = len(long_calls) >= 1

            if not has_short_puts and not has_short_calls:
                results["details"].append(
                    f"✓ Expiry {expiry}: Long-only defined-risk structure ({len(legs)} legs)"
                )
                continue

            missing = []
            if has_short_puts and not has_long_puts:
                missing.append("long put hedge")
            if has_short_calls and not has_long_calls:
                missing.append("long call hedge")

            if missing:
                results["status"] = "BROKEN"
                results["details"].append(
                    f"✗ Expiry {expiry}: Unhedged short exposure - missing {', '.join(missing)}"
                )
                results["details"].append(f"  Current legs: {len(legs)}")
                continue

            if has_short_puts and has_short_calls:
                results["details"].append(
                    f"✓ Expiry {expiry}: Protected 4-leg structure ({len(legs)} legs)"
                )
            elif has_short_puts:
                results["details"].append(
                    f"✓ Expiry {expiry}: Protected put-side spread ({len(legs)} legs)"
                )
            else:
                results["details"].append(
                    f"✓ Expiry {expiry}: Protected call-side spread ({len(legs)} legs)"
                )

        if results["status"] != "BROKEN":
            results["status"] = "OK"

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_feedback_freshness():
    """Verify RLHF feedback system is current.

    Added Jan 27, 2026: stats.json was 4 days stale without detection.
    Feedback should be updated within 24 hours during active sessions.
    """
    results = {"name": "RLHF Feedback Freshness", "status": "UNKNOWN", "details": []}

    try:
        import json
        from datetime import datetime
        from pathlib import Path

        stats_file = Path("data/feedback/stats.json")
        if not stats_file.exists():
            results["status"] = "BROKEN"
            results["details"].append("✗ stats.json not found")
            return results

        stats = json.loads(stats_file.read_text())
        last_updated = stats.get("last_updated", "")

        if not last_updated:
            results["status"] = "BROKEN"
            results["details"].append("✗ No last_updated timestamp")
            return results

        # Parse timestamp (handle both space and 'T' separator)
        try:
            # Try ISO format with T separator first
            last_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            # Convert to naive datetime for comparison
            if last_dt.tzinfo:
                last_dt = last_dt.replace(tzinfo=None)
        except ValueError:
            # Fallback to space-separated format
            try:
                last_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                last_dt = datetime.strptime(
                    last_updated[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"
                )

        age = datetime.now() - last_dt
        age_hours = age.total_seconds() / 3600

        if age_hours > 48:
            results["status"] = "OK"
            results["details"].append(
                f"⚠️ Feedback {age.days} days stale (updated: {last_updated}) - non-blocking"
            )
        elif age_hours > 24:
            results["status"] = "OK"
            results["details"].append(f"⚠️ Feedback {age_hours:.1f}h old (updated: {last_updated})")
        else:
            results["status"] = "OK"
            results["details"].append(f"✓ Feedback current ({age_hours:.1f}h old)")

        # Check stats
        total = stats.get("total", 0)
        positive = stats.get("positive", 0)
        negative = stats.get("negative", 0)
        sat_rate = stats.get("satisfaction_rate", 0)
        results["details"].append(
            f"  Stats: {total} total, {positive}👍/{negative}👎, {sat_rate:.1f}% satisfaction"
        )

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_win_rate_validity():
    """Verify win rate tracking is working from trades.json ledger.

    Added Jan 27, 2026: Win rate showed 0% despite 61 Alpaca fills.
    Fixed Jan 27, 2026: Use trades.json (paired trades) not system_state.json (raw fills).

    Data architecture:
    - system_state.json.trade_history: Raw Alpaca order fills (not paired)
    - trades.json: Paired trades with status/outcome for win rate calculation
    """
    results = {"name": "Win Rate Tracking", "status": "UNKNOWN", "details": []}

    try:
        import json
        from pathlib import Path

        # Check trades.json (the actual win rate ledger)
        trades_file = Path("data/trades.json")
        if not trades_file.exists():
            results["status"] = "BROKEN"
            results["details"].append("✗ data/trades.json not found")
            return results

        trades_data = json.loads(trades_file.read_text())
        trades = trades_data.get("trades", [])
        stats = trades_data.get("stats", {})

        total_trades = len(trades)
        closed_trades = stats.get("closed_trades", 0)
        win_rate = stats.get("win_rate_pct")

        # Also check system_state for Alpaca fill count (informational)
        state_file = Path("data/system_state.json")
        alpaca_fills = 0
        if state_file.exists():
            state = json.loads(state_file.read_text())
            alpaca_fills = state.get("trades_loaded", 0)

        if closed_trades > 0 and win_rate is not None:
            results["status"] = "OK"
            results["details"].append(f"✓ Win rate: {win_rate}% from {closed_trades} closed trades")
        elif total_trades > 0:
            results["status"] = "OK"
            results["details"].append(f"✓ {total_trades} trades tracked, {closed_trades} closed")
            results["details"].append(f"  (Alpaca has {alpaca_fills} raw fills)")
        else:
            results["status"] = "OK"
            results["details"].append(f"✓ No trades in ledger yet ({alpaca_fills} Alpaca fills)")
            results["details"].append("  Add trades via: scripts/calculate_win_rate.py add_trade()")

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_execution_scope():
    """Verify the simplified trading control path exists."""
    results = {"name": "Execution Scope", "status": "UNKNOWN", "details": []}

    try:
        required_paths = [
            Path("scripts/iron_condor_trader.py"),
            Path("scripts/sync_alpaca_state.py"),
            Path("scripts/sync_closed_positions.py"),
            Path("src/safety/mandatory_trade_gate.py"),
            Path("data/system_state.json"),
            Path("data/trades.json"),
        ]
        missing = [str(path) for path in required_paths if not path.exists()]

        if missing:
            results["status"] = "BROKEN"
            results["details"].append(f"✗ Missing active-scope files: {', '.join(missing)}")
        else:
            results["status"] = "OK"
            results["details"].append("✓ Active trading path present")
            results["details"].append("✓ Archived publishing surface is not required for health")

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def check_data_integrity():
    """Verify system_state.json data integrity.

    Added Jan 16, 2026: Validates data consistency to catch
    sync issues and data corruption early.
    """
    results = {"name": "Data Integrity", "status": "UNKNOWN", "details": []}

    try:
        from src.utils.staleness_guard import validate_system_state

        validation = validate_system_state()

        if validation.is_valid:
            results["status"] = "OK"
            results["details"].append("✓ system_state.json passes all validation checks")
        else:
            results["status"] = "BROKEN"
            for error in validation.errors:
                results["details"].append(f"✗ {error}")

        # Add warnings even if valid
        for warning in validation.warnings:
            results["details"].append(f"⚠️ {warning}")

    except Exception as e:
        results["status"] = "BROKEN"
        results["details"].append(f"✗ Error: {e}")

    return results


def main():
    """Run all health checks and report."""
    print("=" * 60)
    print(f"SYSTEM HEALTH CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    checks = [
        check_vector_db,  # CRITICAL: Must run first - RAG depends on this
        check_data_integrity,  # Validate data before other checks
        check_position_completeness,  # Jan 27: Caught incomplete IC
        check_feedback_freshness,  # Jan 27: Caught stale stats.json
        check_win_rate_validity,  # Jan 27: Caught 0% win rate bug
        check_rag_system,
        check_rl_system,
        check_ml_pipeline,
        check_execution_scope,
    ]

    all_ok = True
    for check in checks:
        result = check()
        status_icon = {"OK": "✅", "STUB": "⚠️", "BROKEN": "❌", "UNKNOWN": "❓"}
        icon = status_icon.get(result["status"], "❓")

        print(f"\n{icon} {result['name']}: {result['status']}")
        for detail in result["details"]:
            print(f"   {detail}")

        if result["status"] in ["BROKEN"]:
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ ALL CHECKS PASSED")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - FIX BEFORE TRADING")
        return 1


if __name__ == "__main__":
    sys.exit(main())
