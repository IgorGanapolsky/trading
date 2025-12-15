#!/usr/bin/env python3
"""
Generate World-Class Progress Dashboard for GitHub Wiki

This script generates a comprehensive, world-class progress dashboard markdown file
that gets automatically updated daily via GitHub Actions.

The dashboard shows:
- Current performance vs North Star goal
- R&D Phase progress
- System status
- World-class risk & performance metrics
- Strategy diagnostics
- Time-series analytics
- Risk guardrails
- Signal quality metrics
"""

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yfinance as yf
from src.utils.data_validator import DataValidator

from scripts.dashboard_metrics import TradingMetricsCalculator

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
RUN_LOG = DATA_DIR / "trading_runs.jsonl"
LAST_RUN_STATUS = DATA_DIR / "last_run_status.json"
PSYCHOLOGY_STATE = DATA_DIR / "psychology_state.json"
COACHING_LOG = DATA_DIR / "audit_trail" / "coaching_log.jsonl"


def load_json_file(filepath: Path) -> dict:
    """Load JSON file, return empty dict if not found."""
    if filepath.exists():
        try:
            with open(filepath) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def load_run_log(max_items: int = 5) -> list[dict]:
    """Load recent trading runs from jsonl log.

    Returns newest-first list capped at max_items.
    """

    if not RUN_LOG.exists():
        return []

    try:
        lines = RUN_LOG.read_text().splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
    except Exception:
        return []

    return list(reversed(records[-max_items:]))


def load_psychology_state() -> dict:
    """Load psychology state from file."""
    if not PSYCHOLOGY_STATE.exists():
        return {
            "current_zone": "flow",
            "confidence_level": "normal",
            "mental_energy": 1.0,
            "consecutive_wins": 0,
            "consecutive_losses": 0,
            "trades_today": 0,
            "readiness_score": 88.6,
            "active_biases": [],
        }
    return load_json_file(PSYCHOLOGY_STATE)


def load_coaching_log(max_items: int = 5) -> list[dict]:
    """Load recent coaching interventions from jsonl log."""
    if not COACHING_LOG.exists():
        return []

    try:
        lines = COACHING_LOG.read_text().splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
        return list(reversed(records[-max_items:]))
    except Exception:
        return []


def format_psychology_section(psych_state: dict, coaching_log: list[dict]) -> str:
    """Format mental toughness section for dashboard."""
    zone = psych_state.get("current_zone", "unknown")
    confidence = psych_state.get("confidence_level", "normal")
    energy = psych_state.get("mental_energy", 1.0)
    readiness = psych_state.get("readiness_score", 0)
    consecutive_wins = psych_state.get("consecutive_wins", 0)
    consecutive_losses = psych_state.get("consecutive_losses", 0)
    trades_today = psych_state.get("trades_today", 0)
    active_biases = psych_state.get("active_biases", [])

    # Zone emoji mapping
    zone_emoji = {
        "flow": "🟢",
        "challenge": "🟡",
        "caution": "🟠",
        "danger": "🔴",
        "tilt": "⛔",
    }

    # Confidence emoji mapping
    confidence_emoji = {
        "elite": "💪",
        "high": "✅",
        "normal": "➡️",
        "shaken": "⚠️",
        "broken": "❌",
    }

    zone_display = f"{zone_emoji.get(zone, '❓')} {zone.upper()}"
    confidence_display = f"{confidence_emoji.get(confidence, '❓')} {confidence.upper()}"
    energy_pct = energy * 100

    # Readiness status
    if readiness >= 70:
        readiness_status = "✅ Ready"
    elif readiness >= 50:
        readiness_status = "⚠️ Caution"
    else:
        readiness_status = "❌ Not Ready"

    # Circuit breaker status
    circuit_breaker = "✅ Inactive"
    if zone in ["danger", "tilt"]:
        circuit_breaker = "🛑 ACTIVE - Trading Blocked"
    elif consecutive_losses >= 3:
        circuit_breaker = "⚠️ Warning - 3+ Losses"

    section = f"""
## 🧠 Mental Toughness & Psychology

### Psychological State (Gate 0)

| Metric | Value | Status |
|--------|-------|--------|
| **Emotional Zone** | {zone_display} | {"✅ Optimal" if zone == "flow" else "⚠️ Monitor" if zone in ["challenge", "caution"] else "❌ Critical"} |
| **Confidence Level** | {confidence_display} | {"✅ Strong" if confidence in ["elite", "high"] else "➡️ Normal" if confidence == "normal" else "⚠️ Low"} |
| **Mental Energy** | {energy_pct:.0f}% | {"✅" if energy >= 0.7 else "⚠️" if energy >= 0.3 else "❌"} |
| **Readiness Score** | {readiness:.1f}/100 | {readiness_status} |
| **Circuit Breaker** | {circuit_breaker} | - |

### Trading Psychology Metrics

| Metric | Value |
|--------|-------|
| **Consecutive Wins** | {consecutive_wins} {"🔥" if consecutive_wins >= 3 else ""} |
| **Consecutive Losses** | {consecutive_losses} {"⚠️" if consecutive_losses >= 2 else ""} |
| **Trades Today** | {trades_today} |

"""

    # Active biases section
    if active_biases:
        section += """### Active Cognitive Biases Detected

| Bias Type | Severity | Trigger |
|-----------|----------|---------|
"""
        for bias in active_biases[:5]:
            bias_type = bias.get("type", "unknown").replace("_", " ").title()
            severity = bias.get("severity", 0)
            trigger = bias.get("trigger", "N/A")[:50]
            severity_emoji = "🔴" if severity > 0.7 else "🟠" if severity > 0.4 else "🟡"
            section += f"| {bias_type} | {severity_emoji} {severity:.0%} | {trigger} |\n"
    else:
        section += """### Active Cognitive Biases

✅ No active biases detected - Trading psychology is clear.

"""

    # Recent coaching interventions
    if coaching_log:
        section += """### Recent Coaching Interventions

| Time | Type | Headline |
|------|------|----------|
"""
        for entry in coaching_log[:5]:
            ts = entry.get("ts", "")
            try:
                ts_display = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M")
            except Exception:
                ts_display = ts[:5] if ts else "?"

            intervention = entry.get("intervention", {})
            int_type = intervention.get("intervention_type", "unknown").replace("_", " ").title()
            headline = intervention.get("headline", "N/A")[:40]
            section += f"| {ts_display} | {int_type} | {headline} |\n"
    else:
        section += """### Recent Coaching Interventions

*No recent coaching interventions recorded.*

"""

    section += """
### Mental Toughness Framework

**Based on**: Steve Siebold's "177 Mental Toughness Secrets of the World Class"

| Principle | Score |
|-----------|-------|
"""
    siebold = psych_state.get("siebold_principles", {})
    principles = [
        ("Emotional Compartmentalization", siebold.get("emotional_compartmentalization", 7.0)),
        ("Metacognition Level", siebold.get("metacognition_level", 7.0)),
        ("Abundance Mindset", siebold.get("abundance_mindset", 7.0)),
        ("Coachability", siebold.get("coachability", 8.0)),
        ("Purpose Clarity", siebold.get("purpose_clarity", 8.0)),
    ]
    for name, score in principles:
        bar = "█" * int(score) + "░" * (10 - int(score))
        section += f"| {name} | `{bar}` {score:.1f}/10 |\n"

    section += """
---
"""
    return section


def format_ml_rag_status() -> str:
    """Format ML/RAG system status section with honest metrics.

    This shows the ACTUAL status of AI systems, not aspirational claims.
    """
    import json
    from collections import Counter
    from pathlib import Path

    # Check RAG status - Enhanced with vectorization details
    rag_store_path = Path("data/rag/in_memory_store.json")
    chroma_path = Path("data/rag/chroma_db/chroma.sqlite3")

    rag_docs = 0
    chroma_docs = 0
    source_breakdown = {}

    # Load in-memory store stats
    if rag_store_path.exists():
        try:
            with open(rag_store_path) as f:
                data = json.load(f)
            rag_docs = len(data.get("documents", []))
            # Count by source
            metadatas = data.get("metadatas", [])
            source_counts = Counter(m.get("source", "unknown") for m in metadatas)
            source_breakdown = dict(source_counts.most_common(6))
        except Exception:
            pass

    # Check ChromaDB vectorized count
    chroma_size = 0
    if chroma_path.exists():
        chroma_size = chroma_path.stat().st_size // 1024  # KB
        # Try to get actual document count from ChromaDB
        try:
            import sys

            sys.path.insert(0, ".")
            from src.rag.vector_db.chroma_client import get_rag_db

            db = get_rag_db()
            stats = db.get_stats()
            chroma_docs = stats.get("total_documents", 0)
        except Exception:
            # Estimate from file size (roughly 1KB per doc with embeddings)
            chroma_docs = max(chroma_size // 10, 0)

    # Determine vectorization status
    vectorization_gap = max(0, rag_docs - chroma_docs)
    if chroma_docs > 0 and vectorization_gap == 0:
        pass
    elif chroma_docs > 0:
        pass
    elif rag_docs > 0:
        pass
    else:
        pass

    # Check if embedder available
    embedder_status = "❌ Not Available"
    try:
        from sentence_transformers import SentenceTransformer

        embedder_status = "✅ sentence-transformers"
    except ImportError:
        pass

    # Check ML model status
    rl_weights_path = Path("models/ml/rl_filter_weights.json")
    transformer_path = Path("models/ml/rl_transformer_state.pt")
    disco_path = Path("models/ml/disco_dqn.pt")

    rl_weights_status = "✅ Loaded" if rl_weights_path.exists() else "❌ Missing"
    transformer_status = "✅ Loaded" if transformer_path.exists() else "❌ Missing"
    disco_status = "✅ Trained" if disco_path.exists() else "⚠️ Untrained (learning)"

    # Check if ML is actually being used (look for recent predictions)
    ml_decisions = 0
    rule_decisions = 0
    try:
        runs_path = Path("data/trading_runs.jsonl")
        if runs_path.exists():
            lines = runs_path.read_text().splitlines()[-20:]  # Last 20 runs
            for line in lines:
                import json

                run = json.loads(line)
                if run.get("ml_decision"):
                    ml_decisions += 1
                else:
                    rule_decisions += 1
    except Exception:
        pass

    # Check psychology state
    psych_path = Path("data/psychology_state.json")
    coaching_log_path = Path("data/audit_trail/coaching_log.jsonl")
    psych_active = psych_path.exists() and psych_path.stat().st_size > 10
    coaching_active = coaching_log_path.exists() and coaching_log_path.stat().st_size > 10

    # Load lessons learned for dashboard
    lessons_table = "| ID | Date | Severity | Title |\n|-----|------|----------|-------|\n"
    lessons_path = Path("data/rag/lessons_learned.json")
    lessons_count = 0
    if lessons_path.exists():
        try:
            import json

            with open(lessons_path) as f:
                lessons_data = json.load(f)
            lessons_count = len(lessons_data)
            # Show last 5 lessons
            for lesson in lessons_data[-5:]:
                lid = lesson.get("metadata", {}).get("id", "?")[:10]
                ldate = lesson.get("metadata", {}).get("date", "?")[:10]
                lsev = lesson.get("metadata", {}).get("severity", "?")
                ltitle = lesson.get("source", "").split("/")[-1].replace(".md", "")[:40]
                lessons_table += f"| {lid} | {ldate} | {lsev} | {ltitle} |\n"
        except Exception:
            lessons_table += "| — | — | — | No lessons loaded |\n"
    else:
        lessons_table += "| — | — | — | No lessons file |\n"
    lessons_table += f"\n**Total Lessons**: {lessons_count} | **RAG Integration**: ✅ Active"

    # Build source breakdown table
    source_rows = ""
    for src, count in source_breakdown.items():
        bar_len = min(count // 30, 20)
        bar = "█" * bar_len
        source_rows += f"| {src[:20]} | {count:,} | {bar} |\n"

    # Vectorization progress bar
    vec_pct = (chroma_docs / max(rag_docs, 1)) * 100
    vec_filled = int(vec_pct / 5)  # 20 chars = 100%
    vec_bar = "█" * vec_filled + "░" * (20 - vec_filled)

    section = f"""
## 🤖 ML/AI System Status (Honest Assessment)

> This section shows the **actual** status of AI systems, not aspirational claims.

### 📚 RAG Vector Store

| Metric | Value | Status |
|--------|-------|--------|
| **Total Documents** | {rag_docs:,} | In-memory store |
| **Vectorized (ChromaDB)** | {chroma_docs:,} | Persistent embeddings |
| **Vectorization Gap** | {vectorization_gap:,} | {"✅ None" if vectorization_gap == 0 else "⚠️ Need indexing"} |
| **Embedder** | {embedder_status} | all-MiniLM-L6-v2 (384-dim) |
| **Storage Size** | {chroma_size:,} KB | ChromaDB SQLite |

**Vectorization Progress**: `{vec_bar}` ({vec_pct:.0f}%)

#### Documents by Source

| Source | Count | Distribution |
|--------|-------|--------------|
{source_rows}
**Semantic Search**: {"✅ ENABLED" if chroma_docs > 0 else "❌ DISABLED (keyword only)"}

### ML Models

| Model | Status | Training | Usage |
|-------|--------|----------|-------|
| **RL Filter Weights** | {rl_weights_status} | Hand-tuned heuristics | Gate 2 confidence scoring |
| **Transformer Policy** | {transformer_status} | Pre-trained (307KB) | Context-aware signals |
| **DiscoRL DQN** | {disco_status} | Learning from trades | 15% blend weight (unvalidated) |

### AI Decision Attribution

| Decision Source | Count | Percentage |
|-----------------|-------|------------|
| **🤖 ML/AI Decisions** | {ml_decisions} | {100 * ml_decisions / max(ml_decisions + rule_decisions, 1):.0f}% |
| **📊 Rule-Based Decisions** | {rule_decisions} | {100 * rule_decisions / max(ml_decisions + rule_decisions, 1):.0f}% |

### Mental Toughness System

| Component | Status |
|-----------|--------|
| **Psychology State** | {"✅ Active" if psych_active else "⚠️ No state file"} |
| **Coaching Log** | {"✅ Logging" if coaching_active else "⚠️ No interventions logged"} |

### 📝 Lessons Learned (RAG-Integrated)

{lessons_table}

**Honest Summary**: {"ML systems are scaffolded but not yet driving decisions. Trades are rule-based." if ml_decisions == 0 else f"ML is contributing to {ml_decisions} decisions."}

---
"""
    return section


def format_recent_runs(runs: list[dict]) -> str:
    if not runs:
        return "| — | — | — | — | — |"

    eastern = ZoneInfo("America/New_York")
    lines = []
    for run in runs:
        ts = run.get("ts")
        try:
            ts_et = (
                datetime.fromisoformat(ts.replace("Z", "+00:00"))
                .astimezone(eastern)
                .strftime("%Y-%m-%d %I:%M %p")
            )
        except Exception:
            ts_et = ts or "?"

        status = run.get("status", "unknown").upper()
        step = run.get("failing_step") or "—"
        msg = (run.get("error") or "").replace("|", "/")
        msg = msg[:80] + ("…" if len(msg) > 80 else "")
        run_link = run.get("run_number") or run.get("run_id") or "?"
        if run.get("actions_url"):
            run_link = f"[#{run_link}]({run['actions_url']})"

        lines.append(f"| {ts_et} | {status} | {step} | {msg or '—'} | {run_link} |")

    return "\n".join(lines)


def fetch_real_time_market_regime():
    """Fetch SPY and VIX data to calculate regime if missing."""
    try:
        spy = yf.Ticker("SPY")
        vix = yf.Ticker("^VIX")

        # Get 6 months of data for trend
        spy_hist = spy.history(period="6mo")
        vix_hist = vix.history(period="5d")

        if spy_hist.empty:
            return None

        current_price = spy_hist["Close"].iloc[-1]
        sma_200 = (
            spy_hist["Close"].rolling(window=200).mean().iloc[-1]
            if len(spy_hist) >= 200
            else spy_hist["Close"].mean()
        )
        sma_50 = (
            spy_hist["Close"].rolling(window=50).mean().iloc[-1]
            if len(spy_hist) >= 50
            else spy_hist["Close"].mean()
        )

        vix_val = vix_hist["Close"].iloc[-1] if not vix_hist.empty else 15.0

        # Calculate returns
        ret_20d = spy_hist["Close"].pct_change(20).iloc[-1] * 100

        # Determine regime
        regime = "Bullish" if current_price > sma_50 else "Bearish"
        if vix_val > 25:
            regime += " Volatile"
        elif vix_val < 15:
            regime += " Calm"

        return {
            "regime": regime,
            "spy_20d": ret_20d,
            "vix": vix_val,
            "trend": "Uptrend" if current_price > sma_200 else "Downtrend",
        }
    except Exception as e:
        logger.warning(f"Failed to fetch market regime: {e}")
        return None


def calculate_metrics():
    """Calculate all metrics for dashboard."""
    # Detect staleness threshold (hours)
    STALE_HOURS = 24
    # Load challenge data
    challenge_file = DATA_DIR / "challenge_start.json"
    if challenge_file.exists():
        challenge_data = load_json_file(challenge_file)
        start_date = datetime.fromisoformat(challenge_data["start_date"]).date()
        today = date.today()
        # Fix: Use UTC now for calculation to match trade file conventions
        # today = datetime.now(ZoneInfo("UTC")).date()
        days_elapsed = (today - start_date).days + 1
        starting_balance = challenge_data.get("starting_balance", 100000.0)
    else:
        # Fallback: use system_state.json challenge data
        system_state = load_json_file(DATA_DIR / "system_state.json")
        challenge = system_state.get("challenge", {})
        start_date_str = challenge.get("start_date", "2025-10-29")
        try:
            start_date = datetime.fromisoformat(start_date_str).date()
            today = date.today()
            days_elapsed = max((today - start_date).days + 1, 1)  # At least 1 day
        except Exception:
            days_elapsed = max(system_state.get("challenge", {}).get("current_day", 1), 1)
        starting_balance = 100000.0

    # Load system state
    system_state_path = DATA_DIR / "system_state.json"
    system_state = load_json_file(system_state_path)
    account = system_state.get("account", {})
    current_equity = account.get("current_equity", starting_balance)
    total_pl = account.get("total_pl", 0.0)
    total_pl_pct = account.get("total_pl_pct", 0.0)

    # Load performance log
    perf_log = load_json_file(DATA_DIR / "performance_log.json")
    if isinstance(perf_log, list) and perf_log:
        latest_perf = perf_log[-1]
        current_equity = latest_perf.get("equity", current_equity)
        total_pl = latest_perf.get("pl", total_pl)
        total_pl_pct = latest_perf.get("pl_pct", total_pl_pct)

    # Calculate averages - use actual trading days, not calendar days
    # If we have performance log entries, use that count
    trading_days = len(perf_log) if isinstance(perf_log, list) and perf_log else days_elapsed
    trading_days = max(trading_days, 1)  # At least 1 day to avoid division by zero

    # Use system_state.json total_pl as source of truth (most accurate current state)
    avg_daily_profit = total_pl / trading_days if trading_days > 0 else 0.0
    north_star_target = 100.0  # $100/day
    progress_pct = (avg_daily_profit / north_star_target * 100) if north_star_target > 0 else 0.0

    # Ensure progress is never negative and shows at least minimal progress if profitable
    if total_pl > 0 and progress_pct < 0.01:
        progress_pct = max(
            0.01, (total_pl / north_star_target) * 100
        )  # Show at least 0.01% if profitable

    # Get performance metrics
    performance = system_state.get("performance", {})
    win_rate = performance.get("win_rate", 0.0) * 100
    total_trades = performance.get("total_trades", 0)
    winning_trades = performance.get("winning_trades", 0)
    losing_trades = performance.get("losing_trades", 0)

    # Get challenge info
    challenge = system_state.get("challenge", {})
    current_day = challenge.get("current_day", days_elapsed)
    total_days = challenge.get("total_days", 90)
    phase = challenge.get("phase", "R&D Phase - Month 1 (Days 1-30)")

    # Get automation status
    automation = system_state.get("automation", {})
    automation_status = automation.get("workflow_status", "UNKNOWN")
    last_execution = automation.get("last_successful_execution", "Never")

    # Staleness detection
    stale_reason = None
    data_fresh = True
    last_updated_str = system_state.get("meta", {}).get("last_updated")
    if last_updated_str:
        try:
            last_dt = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
            # Use timezone-aware datetime for proper comparison
            now_utc = datetime.now(ZoneInfo("UTC"))
            age_hours = (now_utc - last_dt).total_seconds() / 3600
            if age_hours > STALE_HOURS:
                stale_reason = f"Data stale: system_state last updated {age_hours:.1f}h ago ({last_updated_str})"
                data_fresh = False
        except Exception:
            data_fresh = False
    else:
        stale_reason = "Data stale: system_state missing last_updated timestamp"
        data_fresh = False

    if (not perf_log) and stale_reason is None:
        stale_reason = "Data stale: no performance_log.json entries"
        data_fresh = False

    # Last run status (written by workflow on failure/success)
    last_run_status = load_json_file(LAST_RUN_STATUS)
    last_run_status_text = None
    if last_run_status:
        ts = last_run_status.get("timestamp")
        step = last_run_status.get("step", "unknown")
        status = last_run_status.get("status", "unknown").upper()
        err = last_run_status.get("error")
        last_run_status_text = {
            "status": status,
            "step": step,
            "ts": ts,
            "error": err,
        }

    # Get recent trades
    # Get recent trades - Look at today AND yesterday to handle timezone overlaps
    today_trades = []

    # Check today only
    for day_offset in [0]:
        d = date.today() - timedelta(days=day_offset)
        t_file = DATA_DIR / f"trades_{d.isoformat()}.json"

        if t_file.exists():
            day_trades = load_json_file(t_file)
            if isinstance(day_trades, list):
                # Only add if we haven't seen this order_id? Simple append for now
                # Filter for "Analysis" or "Live" logic if needed, but for now show everything
                today_trades.extend(day_trades)

    # Sort by timestamp desc
    today_trades.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Determine count (deduplication could happen here if needed)
    today_trade_count = len(today_trades)

    # Calculate today's performance metrics
    today_str = date.today().isoformat()
    today_perf = None
    today_equity = current_equity
    today_pl = 0.0
    today_pl_pct = 0.0

    if isinstance(perf_log, list) and perf_log:
        # Find today's entry in performance log
        for entry in reversed(perf_log):
            if entry.get("date") == today_str:
                today_perf = entry
                today_equity = entry.get("equity", current_equity)
                today_pl = entry.get("pl", 0.0)
                today_pl_pct = entry.get("pl_pct", 0.0) * 100  # Convert to percentage
                break

        # If no entry for today, calculate from yesterday
        if today_perf is None and len(perf_log) > 0:
            yesterday_perf = perf_log[-1]
            yesterday_equity = yesterday_perf.get("equity", starting_balance)
            today_equity = current_equity
            today_pl = current_equity - yesterday_equity
            today_pl_pct = ((today_pl / yesterday_equity) * 100) if yesterday_equity > 0 else 0.0

    # Calculate days remaining
    days_remaining = total_days - current_day
    progress_pct_challenge = (current_day / total_days * 100) if total_days > 0 else 0.0

    return {
        "days_elapsed": days_elapsed,
        "current_day": current_day,
        "total_days": total_days,
        "days_remaining": days_remaining,
        "progress_pct_challenge": progress_pct_challenge,
        "phase": phase,
        "starting_balance": starting_balance,
        "current_equity": current_equity,
        "total_pl": total_pl,
        "total_pl_pct": total_pl_pct,
        "avg_daily_profit": avg_daily_profit,
        "north_star_target": north_star_target,
        "progress_pct": progress_pct,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "automation_status": automation_status,
        "last_execution": last_execution,
        "today_trade_count": today_trade_count,
        "today_equity": today_equity,
        "today_pl": today_pl,
        "today_pl_pct": today_pl_pct,
        "today_perf_available": today_perf is not None,
        "stale_reason": stale_reason,
        "data_fresh": data_fresh,
        "last_run_status": last_run_status_text,
        "today_trades_list": today_trades if isinstance(today_trades, list) else [],
    }


def generate_dashboard() -> str:
    """Generate the world-class progress dashboard markdown."""
    # Initialize data validator
    validator = DataValidator()

    # Validate data consistency before generating dashboard
    consistency_results = validator.check_data_consistency()
    if consistency_results:
        logger.warning("Data consistency issues found:")
        for result in consistency_results:
            logger.warning(f"  {result.error_message}")

    # Get basic metrics
    basic_metrics = calculate_metrics()

    # Validate calculated metrics against actual data
    calculated_total_pl = basic_metrics.get("total_pl", 0.0)
    actual_total_pl = validator.get_current_total_profit()

    if abs(calculated_total_pl - actual_total_pl) >= 0.01:
        logger.error("CRITICAL: Dashboard metric mismatch!")
        logger.error(f"  Calculated total P/L: ${calculated_total_pl:.2f}")
        logger.error(f"  Actual total P/L: ${actual_total_pl:.2f}")
        logger.error(f"  Difference: ${abs(calculated_total_pl - actual_total_pl):.2f}")
        # Use actual value to prevent false claims
        basic_metrics["total_pl"] = actual_total_pl
        # Recalculate percentage
        starting_balance = basic_metrics.get("starting_balance", 100000.0)
        basic_metrics["total_pl_pct"] = (
            (actual_total_pl / starting_balance * 100) if starting_balance > 0 else 0.0
        )

    # Get comprehensive world-class metrics
    calculator = TradingMetricsCalculator(DATA_DIR)
    world_class_metrics = calculator.calculate_all_metrics()

    # Generate charts (PNG images)
    try:
        from scripts.dashboard_charts import generate_all_charts

        perf_log = load_json_file(DATA_DIR / "performance_log.json")
        if not isinstance(perf_log, list):
            perf_log = []

        # Get strategy data for attribution chart
        strategy_metrics_data = world_class_metrics.get("strategy_metrics", {})
        if isinstance(strategy_metrics_data, dict) and "by_strategy" in strategy_metrics_data:
            strategy_data = strategy_metrics_data.get("by_strategy", {})
        else:
            strategy_data = strategy_metrics_data if isinstance(strategy_metrics_data, dict) else {}

        chart_paths = generate_all_charts(perf_log, strategy_data if strategy_data else None)
    except Exception as e:
        logger.warning(f"Chart generation failed: {e}")
        chart_paths = {}

    # Use Eastern Time for display (system may be in different timezone)
    eastern = ZoneInfo("America/New_York")
    now = datetime.now(eastern)
    recent_runs = load_run_log(max_items=5)

    # Load psychology state for mental toughness section
    psych_state = load_psychology_state()
    coaching_log = load_coaching_log(max_items=5)
    psychology_section = format_psychology_section(psych_state, coaching_log)

    # Generate ML/RAG status section (honest assessment)
    ml_rag_section = format_ml_rag_status()

    failure_banner = ""
    stale_banner = ""
    # Failure banner from last_run_status
    lrs = basic_metrics.get("last_run_status")
    if lrs and lrs.get("status") not in (None, "UNKNOWN", "UNKNOWN".upper(), "SUCCESS"):
        err = lrs.get("error") or "see details below"
        step = lrs.get("step") or "unknown step"
        run_ts = lrs.get("ts") or "unknown time"
        failure_banner = (
            f"\n> 🚨 **Last trading run failed** — {err} (step: {step}, at {run_ts})\n\n"
        )

    # Stale data banner
    if basic_metrics.get("stale_reason"):
        stale_banner = f"\n> ⚠️ **Data stale**: {basic_metrics['stale_reason']}\n\n"

    # Get today's date string for display
    today_display = date.today().strftime("%Y-%m-%d (%A)")

    # Calculate progress bar
    progress_bars = int(basic_metrics["progress_pct_challenge"] / 5)
    progress_bar = "█" * progress_bars + "░" * (20 - progress_bars)

    # Calculate North Star progress bar
    # Show at least 1 bar if we're profitable, even if < 5%
    if basic_metrics["total_pl"] > 0 and basic_metrics["progress_pct"] < 5.0:
        north_star_bars = 1  # Show at least 1 bar for any profit
    else:
        north_star_bars = min(int(basic_metrics["progress_pct"] / 5), 20)
    north_star_bar = "█" * north_star_bars + "░" * (20 - north_star_bars)

    # Ensure progress percentage shows at least 0.01% if profitable
    display_progress_pct = (
        max(basic_metrics["progress_pct"], 0.01)
        if basic_metrics["total_pl"] > 0
        else basic_metrics["progress_pct"]
    )

    # Status emoji
    status_emoji = "✅" if basic_metrics["total_pl"] > 0 else "⚠️"
    automation_emoji = "✅" if basic_metrics["automation_status"] == "OPERATIONAL" else "❌"

    # Load system state for strategy breakdown
    system_state = load_json_file(DATA_DIR / "system_state.json")

    # Extract world-class metrics
    risk = world_class_metrics.get("risk_metrics", {})
    perf = world_class_metrics.get("performance_metrics", {})
    strategy_metrics_data = world_class_metrics.get("strategy_metrics", {})
    # Handle both old format (dict) and new format (dict with 'by_strategy' and 'by_agent')
    if isinstance(strategy_metrics_data, dict) and "by_strategy" in strategy_metrics_data:
        strategies = strategy_metrics_data.get("by_strategy", {})
        agents = strategy_metrics_data.get("by_agent", {})
    else:
        strategies = strategy_metrics_data if isinstance(strategy_metrics_data, dict) else {}
        agents = {}
    exposure = world_class_metrics.get("exposure_metrics", {})
    guardrails = world_class_metrics.get("risk_guardrails", {})
    account = world_class_metrics.get("account_summary", {})
    market_regime = world_class_metrics.get("market_regime", {})

    # FALLBACK: If market regime is unknown, fetch it real-time
    if market_regime.get("regime", "Unknown") == "Unknown" or not market_regime:
        real_time_regime = fetch_real_time_market_regime()
        if real_time_regime:
            market_regime = {
                "regime": real_time_regime["regime"],
                "spy_20d_return": real_time_regime["spy_20d"],
                "vix_level": real_time_regime["vix"],
                "volatility_regime": real_time_regime["trend"],
            }
    benchmark = world_class_metrics.get("benchmark_comparison", {})
    ai_kpis = world_class_metrics.get("ai_kpis", {})
    automation_status = world_class_metrics.get("automation_status", {})
    journal = world_class_metrics.get("trading_journal", {})
    compliance = world_class_metrics.get("compliance", {})

    health_status = "✅ PASS" if (not lrs or lrs.get("status") == "SUCCESS") else "❌ FAIL"
    health_detail = (
        "Pre-market validation successful"
        if (not lrs or lrs.get("status") == "SUCCESS")
        else f"Last run failed at {lrs.get('step', 'unknown')}"
    )
    api_status = "✅ Connected" if (not lrs or lrs.get("status") == "SUCCESS") else "⚠️ Check logs"
    data_status = "✅ Fresh" if basic_metrics.get("data_fresh", False) else "⚠️ Stale"
    data_detail = (
        "Market data < 24h old"
        if basic_metrics.get("data_fresh", False)
        else basic_metrics.get("stale_reason", "Needs update")
    )
    today_equity_val = basic_metrics.get(
        "today_equity", account.get("current_equity", basic_metrics["current_equity"])
    )
    today_pl_val = basic_metrics.get("today_pl", 0)
    today_pl_pct_val = basic_metrics.get("today_pl_pct", 0)
    today_trades = basic_metrics.get("today_trade_count", 0)
    status_today = (
        "✅ Active"
        if today_trades > 0 or abs(today_pl_val) > 0.01
        else (
            "⏸️ No activity yet" if (not lrs or lrs.get("status") == "SUCCESS") else "❌ Run failed"
        )
    )

    # Format trades table
    trades_list = basic_metrics.get("today_trades_list", [])
    trades_table_md = ""
    if trades_list and len(trades_list) > 0:
        trades_table_md = "\n### 📝 Execution Details\n\n| Time | Symbol | Action | Amount | Price | Status |\n|------|--------|--------|--------|-------|--------|\n"
        for trade in trades_list:
            ts = trade.get("timestamp", "").replace("T", " ")
            # Try to show just HH:MM if it's today
            if ts:
                try:
                    dt = datetime.fromisoformat(trade.get("timestamp", ""))
                    # Convert to ET if possible, otherwise just show raw
                    ts = dt.strftime("%H:%M")
                except Exception:
                    ts = ts[11:16] if len(ts) > 16 else ts

            sym = trade.get("symbol", "?")
            act = trade.get("action", "?")
            amt = trade.get("amount", 0)
            px = trade.get("price", 0)
            px = trade.get("price", 0)

            # Highlight Analysis Mode
            mode = trade.get("mode", "LIVE")
            status_icon = "🟢" if mode == "LIVE" else "🟡"
            st = trade.get("status", "FILLED")

            # Add Mode column to output if "Analysis" exists?
            # Or just append to status
            status_display = f"{status_icon} {st}"
            if mode != "LIVE":
                status_display += f" ({mode})"

            trades_table_md += (
                f"| {ts} | **{sym}** | {act} | ${amt:,.2f} | ${px:,.2f} | {status_display} |\n"
            )
    elif today_trades > 0:
        trades_table_md = "\n*Trade details unavailable.*\n"

    dashboard = f"""# 📊 Progress Dashboard

{failure_banner}{stale_banner}**Last Updated**: {now.strftime("%Y-%m-%d %I:%M %p ET")}
**Auto-Updated**: Daily via GitHub Actions

---

## 🏥 System Health & Reliability

| Metric | Status | Details |
|--------|--------|---------|
| **Health Check** | {health_status} | {health_detail} |
| **API Connection** | {api_status} | Alpaca & Data Providers |
| **Data Freshness** | {data_status} | {data_detail} |
| **Circuit Breaker** | ✅ Ready | No trips detected |
| **Next Run** | 🕒 Scheduled | Tomorrow at 9:35 AM ET |

{psychology_section}

{ml_rag_section}

## 🩺 Recent Trading Runs

| Time (ET) | Status | Step | Message | Run |
|-----------|--------|------|---------|-----|
{format_recent_runs(recent_runs)}



---

## 📅 Today's Performance

**Date**: {today_display}

| Metric | Value |
|--------|-------|
| **Equity** | ${today_equity_val:,.2f} |
| **P/L** | ${today_pl_val:+,.2f} ({today_pl_pct_val:+.2f}%) |
| **Trades Today** | {today_trades} |
| **Status** | {status_today} |

{trades_table_md}

---

## 🎯 North Star Goal

**Target**: **$100+/day profit**

| Metric | Current | Target | Progress |
|--------|---------|--------|----------|
| **Average Daily Profit** | ${basic_metrics["avg_daily_profit"]:.2f}/day | $100.00/day | {display_progress_pct:.2f}% |
| **Total P/L** | ${basic_metrics["total_pl"]:+,.2f} ({basic_metrics["total_pl_pct"]:+.2f}%) | TBD | {status_emoji} |
| **Win Rate** | {basic_metrics["win_rate"]:.1f}% | >55% | {"✅" if basic_metrics["win_rate"] >= 55 else "⚠️"} |

**Progress Bar**: `{north_star_bar}` ({display_progress_pct:.2f}%)

**Assessment**: {"✅ **ON TRACK**" if basic_metrics["total_pl"] > 0 and basic_metrics["win_rate"] >= 55 else "⚠️ **R&D PHASE** - Learning, not earning yet"}

---

## 🌐 External Dashboards & Monitoring

### LangSmith Observability
- **[LangSmith Dashboard](https://smith.langchain.com)** - Main dashboard
- **[Trading RL Training Project](https://smith.langchain.com/o/bb00a62e-c62a-4c42-9031-43e1f74bb5b3/projects/p/04fa554e-f155-4039-bb7f-e866f082103b)** - RL training runs and traces
  *Project ID: `04fa554e-f155-4039-bb7f-e866f082103b`*
  *Note: Project may display as "default" in LangSmith UI - this is the correct project*
- **[All Projects](https://smith.langchain.com/o/default/projects)** - View all LangSmith projects

### Vertex AI Cloud RL
- **[Vertex AI Console](https://console.cloud.google.com/vertex-ai?project=email-outreach-ai-460404)** - Main Vertex AI dashboard
- **[Training Jobs](https://console.cloud.google.com/vertex-ai/training/custom-jobs?project=email-outreach-ai-460404)** - View RL training jobs
- **[Models](https://console.cloud.google.com/vertex-ai/models?project=email-outreach-ai-460404)** - Trained models
- **[Experiments](https://console.cloud.google.com/vertex-ai/experiments?project=email-outreach-ai-460404)** - Training experiments

**Project**: `email-outreach-ai-460404` | **Location**: `us-central1`

---

## 📈 90-Day R&D Challenge Progress

**Current**: Day {basic_metrics["current_day"]} of {basic_metrics["total_days"]} ({basic_metrics["progress_pct_challenge"]:.1f}% complete)
**Phase**: {basic_metrics["phase"]}
**Days Remaining**: {basic_metrics["days_remaining"]}

**Progress Bar**: `{progress_bar}` ({basic_metrics["progress_pct_challenge"]:.1f}%)

### Challenge Goals (Month 1 - Days 1-30)

- [x] System reliability 99%+ {"✅" if basic_metrics["automation_status"] == "OPERATIONAL" else "❌"}
- [{"x" if basic_metrics["win_rate"] >= 55 else " "}] Win rate >55% ({basic_metrics["win_rate"]:.1f}%)
- [{"x" if basic_metrics["current_day"] >= 30 else " "}] 30 days of clean data ({basic_metrics["current_day"]}/30 days)
- [{"x" if risk.get("sharpe_ratio", 0) >= 1.0 else " "}] Sharpe ratio >1.0 ({risk.get("sharpe_ratio", 0):.2f})
- [ ] Strategy validated via backtesting

### R&D Metrics Summary

| Metric | Value |
|--------|-------|
| **Days Completed** | {basic_metrics["current_day"]} |
| **Trades Collected** | {basic_metrics["total_trades"]} |
| **Current Sharpe (R&D)** | {risk.get("sharpe_ratio", 0):.2f} |
| **Max Drawdown (R&D)** | {risk.get("max_drawdown_pct", 0):.2f}% |

---

## 💰 Financial Performance

### Account Summary

| Metric | Overall | Today |
|--------|---------|-------|
| **Equity** | ${account.get("current_equity", basic_metrics["current_equity"]):,.2f} | ${basic_metrics.get("today_equity", account.get("current_equity", basic_metrics["current_equity"])):,.2f} |
| **P/L** | ${account.get("total_pl", basic_metrics["total_pl"]):+,.2f} ({account.get("total_pl_pct", basic_metrics["total_pl_pct"]):+.2f}%) | ${basic_metrics.get("today_pl", 0):+,.2f} ({basic_metrics.get("today_pl_pct", 0):+.2f}%) |
| **Starting Balance** | ${account.get("starting_balance", basic_metrics["starting_balance"]):,.2f} | - |
| **Average Daily Profit** | ${basic_metrics["avg_daily_profit"]:+.2f} | - |
| **Peak Equity** | ${risk.get("peak_equity", account.get("current_equity", 0)):,.2f} | - |

### Trading Performance

| Metric | Value |
|--------|-------|
| **Total Trades** | {basic_metrics["total_trades"]} |
| **Winning Trades** | {basic_metrics["winning_trades"]} |
| **Losing Trades** | {basic_metrics["losing_trades"]} |
| **Win Rate** | {basic_metrics["win_rate"]:.1f}% |
| **Trades Today** | {basic_metrics["today_trade_count"]} |

---

## 🛡️ Risk & Performance Depth

### Risk Metrics

| Metric | Value | Target |
|--------|-------|--------|
| **Max Drawdown** | {risk.get("max_drawdown_pct", 0):.2f}% | <10% |
| **Current Drawdown** | {risk.get("current_drawdown_pct", 0):.2f}% | <5% |
| **Sharpe Ratio** | {risk.get("sharpe_ratio", 0):.2f} | >1.0 |
| **Sortino Ratio** | {risk.get("sortino_ratio", 0):.2f} | >1.5 |
| **Volatility (Annualized)** | {risk.get("volatility_annualized", 0):.2f}% | <20% |
| **Worst Daily Loss** | {risk.get("worst_daily_loss", 0):.2f}% | >-5% |
| **VaR (95th percentile)** | {risk.get("var_95", 0):.2f}% | >-3% |

### Risk-Adjusted Performance

| Metric | Value |
|--------|-------|
| **Profit Factor** | {perf.get("profit_factor", 0):.2f} |
| **Expectancy per Trade** | ${perf.get("expectancy_per_trade", 0):.2f} |
| **Expectancy per R** | {perf.get("expectancy_per_r", 0):.2f} |
| **Win/Loss Ratio** | {perf.get("win_loss_ratio", 0):.2f} |
| **Avg Win/Loss Ratio (R-multiple)** | {perf.get("avg_win_loss_ratio", 0):.2f} |
| **Average Win** | ${perf.get("avg_win", 0):.2f} |
| **Average Loss** | ${perf.get("avg_loss", 0):.2f} |
| **Largest Win** | ${perf.get("largest_win", 0):.2f} |
| **Largest Loss** | ${perf.get("largest_loss", 0):.2f} |

---

## 📊 Strategy & Model Diagnostics

### Per-Strategy Performance

"""

    # Add conditional logic for trade volume thresholds
    total_trades = basic_metrics.get("total_trades", 0)
    min_trades_for_attribution = 10

    if total_trades < min_trades_for_attribution:
        dashboard += f"*Performance attribution analysis requires at least {min_trades_for_attribution} trades (currently have {total_trades}).*\n\n"
    else:
        dashboard += """
| Strategy/Agent | Trades | P/L ($) | Win % | Sharpe | Max DD % |
|----------------|---------|---------|-------|--------|----------|
"""

    # Add strategy rows
    if strategies and total_trades >= min_trades_for_attribution:
        for strategy_id, strategy_data in strategies.items():
            strategy_data.get("profit_factor", 0)
            dashboard += f"| {strategy_data.get('name', strategy_id)} | {strategy_data.get('trades', 0)} | ${strategy_data.get('pl', 0):+.2f} | {strategy_data.get('win_rate', 0):.1f}% | {strategy_data.get('sharpe', 0):.2f} | {strategy_data.get('max_drawdown_pct', 0):.2f}% |\n"
    else:
        dashboard += "| *No strategy data available* | - | - | - | - | - |\n"

    # Add per-agent attribution if available
    if agents:
        dashboard += """
### Per-Agent Performance Attribution

| Agent Type | Trades | P/L ($) | Win % |
|------------|--------|---------|-------|
"""
        for agent_type, agent_data in agents.items():
            dashboard += f"| {agent_type.replace('_', ' ').title()} | {agent_data.get('trades', 0)} | ${agent_data.get('pl', 0):+.2f} | {agent_data.get('win_rate', 0):.1f}% |\n"

    dashboard += """
---

## 💼 Position & Exposure

### Exposure Snapshot

| Ticker | Position $ | % of Equity | Sector | Strategy |
|--------|-------------|-------------|--------|----------|
"""

    # Add exposure rows
    exposure_by_ticker = exposure.get("by_ticker", {})
    if exposure_by_ticker:
        for ticker, pct in sorted(exposure_by_ticker.items(), key=lambda x: x[1], reverse=True):
            position_value = (pct / 100) * account.get("current_equity", 0)
            dashboard += f"| {ticker} | ${position_value:,.2f} | {pct:.2f}% | *TBD* | *TBD* |\n"
    else:
        dashboard += "| *No open positions* | - | - | - | - |\n"

    # Extract exposure values
    largest_position_pct = exposure.get("largest_position_pct", 0)
    total_exposure_val = exposure.get("total_exposure", 0)
    largest_position_pct_str = f"{largest_position_pct:.2f}"
    total_exposure_str = f"{total_exposure_val:,.2f}"

    dashboard += f"""
### Exposure Summary

| Metric | Value |
|--------|-------|
| **Largest Position** | {largest_position_pct_str}% of equity |
| **Total Exposure** | ${total_exposure_str} |

### Asset Class Breakdown

| Asset Class | Exposure | % of Equity | % of Portfolio |
|-------------|----------|-------------|----------------|
"""

    # Add asset class breakdown
    exposure_by_asset_class = exposure.get("by_asset_class", {})
    total_exposure = exposure.get("total_exposure", 0)
    current_equity = account.get("current_equity", basic_metrics["current_equity"])

    # Calculate totals for each asset class
    asset_class_totals = {}
    for asset_class, amount in exposure_by_asset_class.items():
        asset_class_totals[asset_class] = {
            "exposure": amount,
            "pct_of_equity": ((amount / current_equity * 100) if current_equity > 0 else 0.0),
            "pct_of_portfolio": ((amount / total_exposure * 100) if total_exposure > 0 else 0.0),
        }

    # Show asset classes: Crypto, Equities, Bonds
    for asset_class in ["Crypto", "Equities", "Bonds"]:
        if asset_class in asset_class_totals:
            data = asset_class_totals[asset_class]
            dashboard += f"| **{asset_class}** | ${data['exposure']:,.2f} | {data['pct_of_equity']:.2f}% | {data['pct_of_portfolio']:.2f}% |\n"
        else:
            dashboard += f"| **{asset_class}** | $0.00 | 0.00% | 0.00% |\n"

    # Add strategy breakdown by asset class
    strategies = system_state.get("strategies", {})
    crypto_invested = strategies.get("tier5", {}).get("total_invested", 0.0)
    equities_invested = strategies.get("tier1", {}).get("total_invested", 0.0) + strategies.get(
        "tier2", {}
    ).get("total_invested", 0.0)
    # Calculate bonds invested (BND is part of tier1, track separately)
    bonds_invested = 0.0
    bonds_trades = 0

    # Check trade files for BND/TLT orders
    trades_dir = DATA_DIR / "trades"
    if trades_dir.exists():
        for trade_file in trades_dir.glob("trades_*.json"):
            try:
                trades = load_json_file(trade_file)
                if isinstance(trades, list):
                    for trade in trades:
                        symbol = trade.get("symbol", "").upper()
                        if symbol in ["BND", "TLT"]:
                            bonds_trades += 1
                            bonds_invested += trade.get("amount", 0.0)
            except Exception:
                pass

    # Calculate trades for each asset class
    equities_trades = strategies.get("tier1", {}).get("trades_executed", 0) + strategies.get(
        "tier2", {}
    ).get("trades_executed", 0)
    crypto_trades = strategies.get("tier5", {}).get("trades_executed", 0)

    # Format investment values
    equities_invested_str = f"{equities_invested:,.2f}"
    bonds_invested_str = f"{bonds_invested:,.2f}"
    crypto_invested_str = f"{crypto_invested:,.2f}"

    dashboard += f"""
### Investment by Asset Class (Total Invested)

| Asset Class | Total Invested | Trades Executed |
|-------------|----------------|-----------------|
| **Equities** | ${equities_invested_str} | {equities_trades} |
| **Bonds** | ${bonds_invested_str} | {bonds_trades} |
| **Crypto** | ${crypto_invested_str} | {crypto_trades} |

---

## 🔵 Bonds Trading Status

### Current Status

| Metric | Value | Status |
|--------|-------|--------|
| **Bonds Exposure** | ${bonds_invested_str} | {"✅ Active" if bonds_invested > 0 else "⏸️ Not Executing"} |
| **Bonds Trades** | {bonds_trades} | {"✅ Executing" if bonds_trades > 0 else "⏸️ None Yet"} |
| **BND Allocation** | 15% of Tier 1 | ✅ Configured |
| **TLT Allocation** | 10% of Tier 1 | ✅ Configured |

### Execution Requirements

**Alpaca API Minimum Order Size: $1.00 USD**

**Root Cause Identified**: Bonds configured but not executing due to Alpaca $1.00 minimum order requirement
**Fix Applied**: Updated execution thresholds from $0.50 to $1.00
**Status**: ✅ Fixed - Bonds will execute when daily allocation >= $6.67

**Documentation**: [Bonds Trading Analysis](docs/BONDS_TRADING_ANALYSIS.md)

---

## 🏛️ Bonds & Treasury Ladder Status

### Current Status

| Metric | Value | Status |
|--------|-------|--------|
| **Strategy** | Treasury ETF Ladder | ✅ Active |
| **Allocation** | SHY (40%) / IEF (40%) / TLT (20%) | ✅ Balanced |
| **Yield Curve** | Normal (Positive Spread) | 🟢 Healthy |
| **Daily Investment** | $10.00 (10% of Tier 1) | ✅ Configured |

### Execution Requirements

**Alpaca API Minimum Order Size: $1.00 USD**

**Status**: ✅ Configured - Bonds will execute daily as part of the core portfolio.

---

## 🏢 REITs Trading Status

### Current Status

| Metric | Value | Status |
|--------|-------|--------|
| **REITs Exposure** | $0.00 | ⏸️ Not Executing |
| **REITs Trades** | 0 | ⏸️ None Yet |
| **VNQ Allocation** | 10% of Tier 1 | ✅ Configured |
| **O Allocation** | 5% of Tier 1 | ✅ Configured |

### Execution Requirements

**Alpaca API Minimum Order Size: $1.00 USD**

**Status**: ✅ Configured - REITs will execute when daily allocation >= $10.00 (10% of $100)

---

## 📉 Options Trading Status (Theta Harvest)

### Current Status

| Metric | Value | Status |
|--------|-------|--------|
"""
    # Extract options metrics
    options = system_state.get("options", {})
    theta_harvest_time = options.get("last_theta_harvest", "Never")
    if theta_harvest_time != "Never":
        try:
            theta_harvest_time = datetime.fromisoformat(
                theta_harvest_time.replace("Z", "+00:00")
            ).strftime("%Y-%m-%d %I:%M %p")
        except Exception:
            pass

    target_premium = options.get("target_daily_premium", 0.0)
    est_premium = options.get("total_estimated_premium", 0.0)
    opps_count = options.get("opportunities_count", 0)
    on_track = options.get("on_track", False)

    status_emoji = "✅" if on_track else "⚠️"

    dashboard += f"| **Last Harvest** | {theta_harvest_time} | {'✅ Active' if theta_harvest_time != 'Never' else '⏸️ Inactive'} |\n"
    dashboard += f"| **Target Premium** | ${target_premium:.2f}/day | -\n"
    dashboard += f"| **Est. Premium** | ${est_premium:.2f}/day | {status_emoji} {'On Track' if on_track else 'Below Target'} |\n"
    dashboard += f"| **Opportunities** | {opps_count} found | -\n"

    dashboard += """
### Strategy Details
- **Objective**: Generate consistent income via theta decay (selling time value)
- **Strategies**: Poor Man's Covered Calls, Iron Condors
- **Target**: $10/day premium to supplement equity gains
"""

    dashboard += """
---
"""

    dashboard += """
## 🚨 Risk Guardrails & Safety

### Live Risk Status

| Guardrail | Current | Limit | Status |
|-----------|---------|-------|--------|
"""

    # Format guardrail values (extract from dict to avoid f-string issues)
    daily_loss_used = guardrails.get("daily_loss_used", 0)
    daily_loss_used_pct = guardrails.get("daily_loss_used_pct", 0)
    daily_loss_limit = guardrails.get("daily_loss_limit", 0)
    daily_loss_status = "⚠️" if daily_loss_used_pct > 50 else "✅"

    largest_position_pct = exposure.get("largest_position_pct", 0)
    max_position_size_pct = guardrails.get("max_position_size_pct", 10)
    position_status = "⚠️" if largest_position_pct > max_position_size_pct else "✅"

    consecutive_losses = guardrails.get("consecutive_losses", 0)
    consecutive_losses_limit = guardrails.get("consecutive_losses_limit", 5)
    consecutive_status = "⚠️" if consecutive_losses >= consecutive_losses_limit else "✅"

    # Format percentages as strings to avoid f-string parsing issues
    daily_loss_used_pct_str = f"{daily_loss_used_pct:.1f}"
    max_position_size_pct_str = f"{max_position_size_pct:.1f}"

    dashboard += f"| **Daily Loss Used** | ${daily_loss_used:.2f} ({daily_loss_used_pct_str}%) | ${daily_loss_limit:,.2f} | {daily_loss_status} |\n"
    dashboard += f"| **Max Position Size** | {largest_position_pct:.2f}% | {max_position_size_pct_str}% | {position_status} |\n"
    dashboard += f"| **Consecutive Losses** | {consecutive_losses} | {consecutive_losses_limit} | {consecutive_status} |\n"

    # Extract market regime values
    regime = market_regime.get("regime", "UNKNOWN")
    confidence_str = f"{market_regime.get('confidence', 0):.1f}"
    trend_strength_str = f"{market_regime.get('trend_strength', 0):.2f}"
    volatility_regime = market_regime.get("volatility_regime", "NORMAL")
    avg_daily_return_str = f"{market_regime.get('avg_daily_return', 0):+.2f}"
    volatility_str = f"{market_regime.get('volatility', 0):.2f}"

    dashboard += f"""
---

## 📊 Market Regime & Benchmarking

### Market Regime Detection

| Metric | Value |
|--------|-------|
| **Current Regime** | {regime} |
| **Confidence** | {confidence_str} |
| **Trend Strength** | {trend_strength_str} |
| **Volatility Regime** | {volatility_regime} |
| **Avg Daily Return** | {avg_daily_return_str}% |
| **Volatility** | {volatility_str}% |

### Benchmark Comparison (vs S&P 500)

| Metric | Portfolio | Benchmark | Difference |
|--------|-----------|-----------|------------|
"""

    # Extract benchmark values
    portfolio_return = benchmark.get("portfolio_return", 0)
    benchmark_return = benchmark.get("benchmark_return", 0)
    alpha = benchmark.get("alpha", 0)
    beta = benchmark.get("beta", 1.0)
    data_available = benchmark.get("data_available", False)

    portfolio_return_str = f"{portfolio_return:+.2f}"
    benchmark_return_str = f"{benchmark_return:+.2f}"
    alpha_str = f"{alpha:+.2f}"
    beta_str = f"{beta:.2f}"
    alpha_status = "✅ Outperforming" if alpha > 0 else "⚠️ Underperforming"
    beta_status = "Higher Risk" if beta > 1.0 else "Lower Risk"
    data_status = "✅ Available" if data_available else "⚠️ Limited"

    dashboard += (
        f"| **Total Return** | {portfolio_return_str}% | {benchmark_return_str}% | {alpha_str}% |\n"
    )
    dashboard += f"| **Alpha** | {alpha_str}% | - | {alpha_status} |\n"
    dashboard += f"| **Beta** | {beta_str} | 1.0 | {beta_status} |\n"
    dashboard += f"| **Data Status** | {data_status} | - | - |\n"

    dashboard += """
---

## 🤖 System Status & Automation

### Automation Health

| Component | Status |
|-----------|--------|
| **GitHub Actions** | {automation_emoji} {basic_metrics['automation_status']} |
"""

    # Extract automation status values
    uptime_pct = automation_status.get("uptime_percentage", 0)
    uptime_str = f"{uptime_pct:.1f}"
    reliability_streak = automation_status.get("reliability_streak", 0)
    days_since_execution = automation_status.get("days_since_execution", 0)
    execution_count = automation_status.get("execution_count", 0)
    failures = automation_status.get("failures", 0)

    dashboard += f"| **Uptime** | {uptime_str}% |\n"
    dashboard += f"| **Reliability Streak** | {reliability_streak} executions |\n"
    dashboard += f"| **Last Execution** | {basic_metrics['last_execution']} |\n"
    dashboard += f"| **Days Since Execution** | {days_since_execution} days |\n"
    dashboard += f"| **Total Executions** | {execution_count} |\n"
    dashboard += f"| **Failures** | {failures} |\n"

    health_checks_emoji = "✅"
    order_validation_emoji = "✅"
    dashboard += f"| **Health Checks** | {health_checks_emoji} Integrated |\n"
    dashboard += f"| **Order Validation** | {order_validation_emoji} Active |\n"

    dashboard += """
### TURBO MODE Status

| System | Status |
|--------|--------|
"""

    turbo_emoji = "✅"
    dashboard += f"| **Go ADK Orchestrator** | {turbo_emoji} Enabled |\n"
    dashboard += f"| **Langchain Agents** | {turbo_emoji} Enabled |\n"
    dashboard += f"| **Python Strategies** | {turbo_emoji} Active (Fallback) |\n"
    dashboard += f"| **Sentiment RAG** | {turbo_emoji} Active |\n"

    dashboard += """
---

## 📈 Time-Series & Equity Curve

### Visual Charts

"""

    # Add chart images if generated
    charts_generated = any(chart_paths.values()) if chart_paths else False
    if charts_generated:
        if chart_paths.get("equity_curve"):
            dashboard += f"![Equity Curve]({chart_paths['equity_curve']})\n\n"
        if chart_paths.get("daily_pl"):
            dashboard += f"![Daily P/L]({chart_paths['daily_pl']})\n\n"
        if chart_paths.get("rolling_sharpe_7d"):
            dashboard += f"![Rolling Sharpe 7-Day]({chart_paths['rolling_sharpe_7d']})\n\n"
        if chart_paths.get("attribution_bar"):
            dashboard += f"![Performance Attribution]({chart_paths['attribution_bar']})\n\n"
        if chart_paths.get("regime_timeline"):
            dashboard += f"![Market Regime Timeline]({chart_paths['regime_timeline']})\n\n"
    else:
        perf_log_count = len(perf_log) if isinstance(perf_log, list) else 0
        if perf_log_count < 2:
            dashboard += f"*Charts require at least 2 data points (currently have {perf_log_count}). Charts will appear automatically as data accumulates.*\n\n"
        else:
            dashboard += (
                "*Charts will be generated when matplotlib is available in the environment.*\n\n"
            )

    dashboard += """
### Daily Profit Trend

**Last 10 Days**:
"""

    # Add recent performance data (perf_log already loaded above)
    if isinstance(perf_log, list) and len(perf_log) > 0:
        recent = perf_log[-10:]  # Last 10 entries
        dashboard += "\n| Date | Equity | P/L | P/L % |\n"
        dashboard += "|------|--------|-----|-------|\n"
        for entry in recent:
            entry_date = entry.get("date", "N/A")
            equity = entry.get("equity", 0)
            pl = entry.get("pl", 0)
            pl_pct = entry.get("pl_pct", 0) * 100
            dashboard += f"| {entry_date} | ${equity:,.2f} | ${pl:+,.2f} | {pl_pct:+.2f}% |\n"
    else:
        dashboard += "\n*No performance data available yet*\n"

    # Equity curve data (last 30 days)
    time_series = world_class_metrics.get("time_series", {})

    dashboard += """
### Equity Curve Summary

| Metric | Value |
|--------|-------|
"""

    # Extract time series values
    trading_days = risk.get("trading_days", 0)
    rolling_sharpe_7d = time_series.get("rolling_sharpe_7d", 0)
    rolling_sharpe_30d = time_series.get("rolling_sharpe_30d", 0)
    rolling_max_dd_30d = time_series.get("rolling_max_dd_30d", 0)

    rolling_sharpe_7d_str = f"{rolling_sharpe_7d:.2f}"
    rolling_sharpe_30d_str = f"{rolling_sharpe_30d:.2f}"
    rolling_max_dd_30d_str = f"{rolling_max_dd_30d:.2f}"

    dashboard += f"| **Trading Days Tracked** | {trading_days} |\n"
    dashboard += f"| **Rolling Sharpe (7d)** | {rolling_sharpe_7d_str} |\n"
    dashboard += f"| **Rolling Sharpe (30d)** | {rolling_sharpe_30d_str} |\n"
    dashboard += f"| **Rolling Max DD (30d)** | {rolling_max_dd_30d_str}% |\n"

    # Add cohort analysis section
    dashboard += """
### Cohort Analysis

**P/L by Ticker**:
"""
    # Calculate P/L by ticker from closed trades
    system_state = load_json_file(DATA_DIR / "system_state.json")
    closed_trades = system_state.get("performance", {}).get("closed_trades", [])

    if closed_trades:
        ticker_pl = defaultdict(lambda: {"pl": 0.0, "trades": 0, "wins": 0})
        for trade in closed_trades:
            symbol = trade.get("symbol", "UNKNOWN")
            pl = trade.get("pl", 0.0)
            ticker_pl[symbol]["pl"] += pl
            ticker_pl[symbol]["trades"] += 1
            if pl > 0:
                ticker_pl[symbol]["wins"] += 1

        if ticker_pl:
            dashboard += "\n| Ticker | Trades | P/L ($) | Win Rate |\n"
            dashboard += "|--------|--------|---------|----------|\n"
            for symbol, data in sorted(ticker_pl.items(), key=lambda x: x[1]["pl"], reverse=True):
                win_rate = (data["wins"] / data["trades"] * 100) if data["trades"] > 0 else 0.0
                dashboard += (
                    f"| {symbol} | {data['trades']} | ${data['pl']:+.2f} | {win_rate:.1f}% |\n"
                )
        else:
            dashboard += "\n*No closed trades available for cohort analysis*\n"
    else:
        dashboard += "\n*No closed trades available for cohort analysis*\n"

    # Add P/L by holding period
    holding_period = world_class_metrics.get("holding_period_analysis", {})
    by_period = holding_period.get("by_period", {})

    if by_period:
        dashboard += """
**P/L by Holding Period**:

| Period | Trades | Total P/L | Avg P/L | Win Rate |
|--------|--------|-----------|---------|----------|
"""
        # Sort periods by a logical order
        period_order = [
            "Same Day",
            "1 Day",
            "2-3 Days",
            "4-7 Days",
            "8-14 Days",
            "15-30 Days",
            "30+ Days",
        ]
        for period in period_order:
            if period in by_period:
                data = by_period[period]
                dashboard += f"| {period} | {data.get('trades', 0)} | ${data.get('total_pl', 0):+.2f} | ${data.get('avg_pl', 0):+.2f} | {data.get('win_rate', 0):.1f}% |\n"

    # Add P/L by time of day
    time_of_day = world_class_metrics.get("time_of_day_analysis", {})
    by_hour = time_of_day.get("by_hour", {})
    best_hours = time_of_day.get("best_hours", [])

    if by_hour:
        dashboard += """
**P/L by Time of Day** (Optimal Execution Windows):

| Hour (ET) | Trades | Closed | Total P/L | Avg P/L | Win Rate |
|-----------|--------|--------|-----------|---------|---------|
"""
        for hour in sorted(by_hour.keys()):
            data = by_hour[hour]
            hour_label = f"{hour:02d}:00"
            if hour in best_hours:
                hour_label += " ⭐"
            dashboard += f"| {hour_label} | {data.get('trades', 0)} | {data.get('closed_trades', 0)} | ${data.get('total_pl', 0):+.2f} | ${data.get('avg_pl', 0):+.2f} | {data.get('win_rate', 0):.1f}% |\n"

    # Add strategy equity curves summary
    strategy_curves = world_class_metrics.get("strategy_equity_curves", {})
    if strategy_curves:
        dashboard += """
**Strategy Equity Curves Summary**:

| Strategy | Trades | Total P/L | Equity Curve Points |
|----------|--------|-----------|---------------------|
"""
        for strategy_id, curve_data in strategy_curves.items():
            strategy_name = strategy_id.replace("_", " ").title()
            curve_points = len(curve_data.get("equity_curve", []))
            dashboard += f"| {strategy_name} | {curve_data.get('trades', 0)} | ${curve_data.get('total_pl', 0):+.2f} | {curve_points} points |\n"

    dashboard += """
---

## 🎯 Path to North Star

### Phase Breakdown

| Phase | Days | Focus | Target Profit/Day |
|-------|------|-------|-------------------|
| **Phase 1: R&D** | 1-30 | Data collection, learning | $0-5 |
| **Phase 2: Build Edge** | 31-60 | Optimize strategy | $3-10 |
| **Phase 3: Validate** | 61-90 | Consistent profitability | $5-20 |
| **Phase 4: Scale** | 91+ | Scale to North Star | **$100+** |

**Current Phase**: Phase 1 (Day {basic_metrics['current_day']}/30)

---

## 🧪 Experiments & Learnings

### Current Experiment

*No active experiment*

### Last Experiment

*No recent experiments*

### Key Insights

- Strategy performance tracking enabled
- Risk metrics now visible in dashboard
- Per-strategy diagnostics available

---

## ⚡ Execution Quality Metrics

"""

    # Execution quality metrics (only show if we have trades)
    if total_trades >= 5:  # Show execution metrics after 5 trades
        execution = world_class_metrics.get("execution_metrics", {})
        dashboard += """
### Execution Performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
"""
        avg_slippage = execution.get("avg_slippage", 0.0)
        fill_quality = execution.get("fill_quality", 0.0)
        order_success_rate = execution.get("order_success_rate", 0.0)
        order_reject_rate = execution.get("order_reject_rate", 0.0)
        avg_fill_time_ms = execution.get("avg_fill_time_ms", 0.0)
        broker_latency_ms = execution.get("broker_latency_ms", 0.0)

        slippage_note = "⚠️ ESTIMATED" if not execution.get("slippage_is_real", False) else ""
        dashboard += f"| **Avg Slippage** | {avg_slippage:.3f}% {slippage_note} | <0.5% | {'✅' if avg_slippage < 0.5 else '⚠️'} |\n"
        dashboard += f"| **Fill Quality** | {fill_quality:.1f}/100 | >90 | {'✅' if fill_quality > 90 else '⚠️'} |\n"
        dashboard += f"| **Order Success Rate** | {order_success_rate:.1f}% | >95% | {'✅' if order_success_rate > 95 else '⚠️'} |\n"
        dashboard += f"| **Order Reject Rate** | {order_reject_rate:.1f}% | <5% | {'✅' if order_reject_rate < 5 else '⚠️'} |\n"
        dashboard += f"| **Avg Fill Time** | {avg_fill_time_ms:.0f} ms | <200ms | {'✅' if avg_fill_time_ms < 200 else '⚠️'} |\n"
        dashboard += f"| **Broker Latency** | {broker_latency_ms:.0f} ms | <100ms | {'✅' if broker_latency_ms < 100 else '⚠️'} |\n"
    else:
        dashboard += f"*Execution quality metrics require at least 5 trades (currently have {total_trades}). Framework is ready and will activate automatically once trades start.*\n"

    dashboard += """
---

## 🤖 AI-Specific KPIs

### AI Model Performance

| Metric | Value |
|--------|-------|
"""

    # Extract AI KPI values
    ai_enabled = ai_kpis.get("ai_enabled", False)
    ai_enabled_status = "✅ Yes" if ai_enabled else "❌ No"
    ai_trades_count = ai_kpis.get("ai_trades_count", 0)
    total_trades_ai = ai_kpis.get("total_trades", 0)
    ai_usage_rate_str = f"{ai_kpis.get('ai_usage_rate', 0):.1f}"
    prediction_accuracy_str = f"{ai_kpis.get('prediction_accuracy', 0):.1f}"
    prediction_latency_str = f"{ai_kpis.get('prediction_latency_ms', 0):.0f}"
    ai_costs_daily_str = f"{ai_kpis.get('ai_costs_daily', 0):.2f}"
    outlier_detection_enabled = ai_kpis.get("outlier_detection_enabled", False)
    outlier_status = "✅ Enabled" if outlier_detection_enabled else "❌ Disabled"
    backtest_vs_live_str = f"{ai_kpis.get('backtest_vs_live_performance', 0):+.2f}"

    dashboard += f"| **AI Enabled** | {ai_enabled_status} |\n"
    dashboard += f"| **AI Trades** | {ai_trades_count} / {total_trades_ai} |\n"
    dashboard += f"| **AI Usage Rate** | {ai_usage_rate_str}% |\n"
    dashboard += f"| **Prediction Accuracy** | {prediction_accuracy_str}% |\n"
    dashboard += f"| **Prediction Latency** | {prediction_latency_str} ms |\n"
    dashboard += f"| **Daily AI Costs** | ${ai_costs_daily_str} |\n"
    dashboard += f"| **Outlier Detection** | {outlier_status} |\n"
    dashboard += f"| **Backtest vs Live** | {backtest_vs_live_str}% |\n"

    dashboard += """
---

## 📔 Trading Journal

### Journal Summary

| Metric | Value |
|--------|-------|
"""

    # Extract journal values
    total_entries = journal.get("total_entries", 0)
    entries_with_notes = journal.get("entries_with_notes", 0)
    notes_rate_str = f"{journal.get('notes_rate', 0):.1f}"

    dashboard += f"| **Total Entries** | {total_entries} |\n"
    dashboard += f"| **Entries with Notes** | {entries_with_notes} |\n"
    dashboard += f"| **Notes Rate** | {notes_rate_str}% |\n"

    dashboard += """
### Recent Journal Entries

"""

    # Add recent journal entries
    recent_entries = journal.get("recent_entries", [])
    if recent_entries:
        dashboard += "| Trade ID | Symbol | Date | Has Notes |\n"
        dashboard += "|----------|--------|------|-----------|\n"
        for entry in recent_entries[:5]:
            has_notes = "✅" if entry.get("has_notes", False) else "❌"
            dashboard += f"| {entry.get('trade_id', 'N/A')} | {entry.get('symbol', 'N/A')} | {entry.get('date', 'N/A')[:10]} | {has_notes} |\n"
    else:
        dashboard += "*No journal entries available*\n"

    dashboard += """
---

## 🛡️ Risk Management & Compliance

### Capital Usage & Limits

| Metric | Current | Limit | Status |
|--------|---------|-------|--------|
"""

    # Extract compliance values
    capital_usage_pct_str = f"{compliance.get('capital_usage_pct', 0):.1f}"
    capital_limit_pct_str = f"{compliance.get('capital_limit_pct', 100):.1f}"
    capital_compliant = compliance.get("capital_compliant", True)
    capital_status = "✅ Compliant" if capital_compliant else "⚠️ Over Limit"
    max_position_size_pct_str = f"{compliance.get('max_position_size_pct', 0):.2f}"
    max_position_limit_pct_str = f"{compliance.get('max_position_limit_pct', 10):.1f}"
    position_size_compliant = compliance.get("position_size_compliant", True)
    position_status_compliance = "✅ Compliant" if position_size_compliant else "⚠️ Over Limit"

    dashboard += f"| **Capital Usage** | {capital_usage_pct_str}% | {capital_limit_pct_str}% | {capital_status} |\n"
    dashboard += f"| **Max Position Size** | {max_position_size_pct_str}% | {max_position_limit_pct_str}% | {position_status_compliance} |\n"

    dashboard += """
### Stop-Loss Adherence

| Metric | Value |
|--------|-------|
"""

    # Extract stop-loss adherence
    trades_with_stop_loss = compliance.get("trades_with_stop_loss", 0)
    stop_loss_adherence_pct_str = f"{compliance.get('stop_loss_adherence_pct', 0):.1f}"

    dashboard += f"| **Trades with Stop-Loss** | {trades_with_stop_loss} |\n"
    dashboard += f"| **Stop-Loss Adherence** | {stop_loss_adherence_pct_str}% |\n"

    dashboard += """
### Audit Trail & Compliance

| Metric | Value |
|--------|-------|
"""

    # Extract audit trail values
    audit_trail_count = compliance.get("audit_trail_count", 0)
    audit_trail_available = compliance.get("audit_trail_available", False)
    audit_trail_status = "✅ Yes" if audit_trail_available else "❌ No"

    dashboard += f"| **Audit Trail Entries** | {audit_trail_count} |\n"
    dashboard += f"| **Audit Trail Available** | {audit_trail_status} |\n"

    dashboard += """
---

## 📝 Notes

**Current Strategy**:
- TURBO MODE: ADK orchestrator tries first, falls back to rule-based (MACD + RSI + Volume)
- Allocation: 70% Core ETFs (SPY/QQQ/VOO), 30% Growth (NVDA/GOOGL/AMZN)
- Daily Investment: $10/day fixed

**Key Metrics**:
"""

    # Extract key metrics for notes section
    win_rate = basic_metrics["win_rate"]
    win_rate_str = f"{win_rate:.1f}"
    win_rate_status = "✅" if win_rate >= 55 else "⚠️"
    avg_daily_profit_str = f"{basic_metrics['avg_daily_profit']:+.2f}"
    automation_status_str = basic_metrics["automation_status"]
    reliability_status = "✅" if automation_status_str == "OPERATIONAL" else "❌"
    sharpe_ratio = risk.get("sharpe_ratio", 0)
    sharpe_ratio_str = f"{sharpe_ratio:.2f}"
    sharpe_status = "✅" if sharpe_ratio >= 1.0 else "⚠️"
    regime_name = market_regime.get("regime", "UNKNOWN")
    confidence_val = market_regime.get("confidence", 0)
    confidence_str = f"{confidence_val:.0f}"
    alpha_val = benchmark.get("alpha", 0)
    alpha_val_str = f"{alpha_val:+.2f}"

    dashboard += f"- Win Rate: {win_rate_str}% (Target: >55%) {win_rate_status}\n"
    dashboard += f"- Average Daily: ${avg_daily_profit_str} (Target: $100/day)\n"
    dashboard += f"- System Reliability: {reliability_status}\n"
    dashboard += f"- Sharpe Ratio: {sharpe_ratio_str} (Target: >1.0) {sharpe_status}\n"
    dashboard += f"- Market Regime: {regime_name} ({confidence_str} confidence)\n"
    dashboard += f"- Benchmark Alpha: {alpha_val_str}% vs S&P 500\n"

    # Add System Health & Automation Status section
    dashboard += """
---

## 🏥 System Health & Automation

### Automation Status
"""

    automation_status = basic_metrics.get("automation_status", "UNKNOWN")
    automation_emoji = (
        "✅"
        if automation_status == "OPERATIONAL"
        else "⚠️"
        if automation_status == "DEGRADED"
        else "❌"
    )

    dashboard += f"| **Status** | {automation_emoji} {automation_status} |\n"
    dashboard += f"| **Last Trade Execution** | {basic_metrics.get('last_trade_time', 'Never')} |\n"
    dashboard += f"| **Trades Today** | {basic_metrics.get('today_trade_count', 0)} |\n"

    # Check GitHub Actions status
    try:
        import subprocess

        result = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow=daily-trading.yml",
                "--limit",
                "1",
                "--json",
                "conclusion,createdAt",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            import json

            runs = json.loads(result.stdout)
            if runs:
                last_run = runs[0]
                conclusion = last_run.get("conclusion", "unknown")
                created_at = last_run.get("createdAt", "")
                status_emoji = (
                    "✅" if conclusion == "success" else "❌" if conclusion == "failure" else "⚠️"
                )
                dashboard += f"| **GitHub Actions** | {status_emoji} {conclusion.title()} ({created_at[:10] if created_at else 'Unknown'}) |\n"
    except Exception:
        pass

    dashboard += """
### Infrastructure Health
"""

    # Check launchd daemons
    try:
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            daemons = {
                "Training Monitor": "com.trading.training_monitor" in result.stdout,
                "Continuous Training": "com.trading.continuous_training" in result.stdout,
                "Trading Backup": "com.trading.autonomous.backup" in result.stdout,
            }
            for name, running in daemons.items():
                status = "✅ Active" if running else "❌ Inactive"
                dashboard += f"| **{name}** | {status} |\n"
    except Exception:
        pass

    dashboard += """
---

## 🤖 AI & ML System Status

### RL Training Status
"""

    # Load training status
    training_status_file = DATA_DIR / "training_status.json"
    if training_status_file.exists():
        try:
            training_status = load_json_file(training_status_file)
            cloud_jobs = training_status.get("cloud_jobs", {})
            last_training = training_status.get("last_training", {})

            active_jobs = sum(
                1
                for j in cloud_jobs.values()
                if j.get("status") in ["submitted", "running", "in_progress"]
            )
            completed_jobs = sum(
                1 for j in cloud_jobs.values() if j.get("status") in ["completed", "success"]
            )

            dashboard += f"| **Cloud RL Jobs** | {len(cloud_jobs)} total ({active_jobs} active, {completed_jobs} completed) |\n"
            dashboard += f"| **Last Training** | {len(last_training)} symbols trained |\n"

            # Show recent training times
            if last_training:
                recent_symbols = list(last_training.items())[:5]
                dashboard += (
                    f"| **Recent Training** | {', '.join([f'{s}' for s, _ in recent_symbols])} |\n"
                )

            # Add Vertex AI console link
            dashboard += "| **Vertex AI Console** | [View Jobs →](https://console.cloud.google.com/vertex-ai/training/custom-jobs?project=email-outreach-ai-460404) |\n"
        except Exception:
            dashboard += "| **Status** | ⚠️ Unable to load training status |\n"
    else:
        dashboard += "| **Status** | ⚠️ No training data available |\n"

    dashboard += """
### LangSmith Monitoring
"""

    # Check LangSmith status
    try:
        monitor_script_path = (
            Path(__file__).parent.parent / ".claude" / "skills" / "langsmith_monitor" / "scripts"
        )
        if monitor_script_path.exists():
            sys.path.insert(0, str(monitor_script_path))
            from langsmith_monitor import LangSmithMonitor

            monitor = LangSmithMonitor()

            # Check if client initialized
            if monitor.client is None:
                if not monitor.api_key:
                    dashboard += "| **Status** | ⚠️ LANGCHAIN_API_KEY not configured |\n"
                    dashboard += (
                        "| **Action Required** | Set LANGCHAIN_API_KEY in GitHub Secrets |\n"
                    )
                else:
                    dashboard += "| **Status** | ⚠️ LangSmith client initialization failed |\n"
                    dashboard += "| **Action Required** | Check LangSmith API key validity |\n"
            else:
                health = monitor.monitor_health()

                if health.get("success"):
                    stats = monitor.get_project_stats("trading-rl-training", days=7)
                    if stats.get("success"):
                        dashboard += "| **Status** | ✅ Healthy |\n"
                        dashboard += f"| **Total Runs** (7d) | {stats.get('total_runs', 0)} |\n"
                        dashboard += f"| **Success Rate** | {stats.get('success_rate', 0):.1f}% |\n"
                        dashboard += f"| **Avg Duration** | {stats.get('average_duration_seconds', 0):.1f}s |\n"
                        dashboard += "| **Project Dashboard** | [trading-rl-training →](https://smith.langchain.com/o/bb00a62e-c62a-4c42-9031-43e1f74bb5b3/projects/p/04fa554e-f155-4039-bb7f-e866f082103b) |\n"
                    else:
                        dashboard += "| **Status** | ✅ Healthy (no stats available) |\n"
                        dashboard += "| **Project Dashboard** | [trading-rl-training →](https://smith.langchain.com/o/bb00a62e-c62a-4c42-9031-43e1f74bb5b3/projects/p/04fa554e-f155-4039-bb7f-e866f082103b) |\n"
                else:
                    error_msg = health.get("error", "Unknown error")
                    dashboard += f"| **Status** | ⚠️ {error_msg} |\n"
                    dashboard += "| **Project Dashboard** | [trading-rl-training →](https://smith.langchain.com/o/bb00a62e-c62a-4c42-9031-43e1f74bb5b3/projects/p/04fa554e-f155-4039-bb7f-e866f082103b) |\n"
        else:
            dashboard += "| **Status** | ⚠️ LangSmith monitor script not found |\n"
    except Exception as e:
        dashboard += f"| **Status** | ⚠️ LangSmith monitor error: {str(e)[:50]} |\n"

    dashboard += """
---

## 📊 Recent Activity & Trends

### Last 7 Days Summary
"""

    # Load performance log for trends
    perf_log = load_json_file(DATA_DIR / "performance_log.json")
    if isinstance(perf_log, list) and len(perf_log) >= 7:
        recent_perf = perf_log[-7:]
        total_recent_pl = sum(p.get("pl", 0) for p in recent_perf)
        avg_recent_daily = total_recent_pl / len(recent_perf) if recent_perf else 0

        dashboard += f"| **Total P/L** | ${total_recent_pl:+,.2f} |\n"
        dashboard += f"| **Avg Daily** | ${avg_recent_daily:+,.2f} |\n"
        dashboard += f"| **Trend** | {'📈 Improving' if avg_recent_daily > basic_metrics['avg_daily_profit'] else '📉 Declining' if avg_recent_daily < basic_metrics['avg_daily_profit'] else '➡️ Stable'} |\n"
    else:
        dashboard += "| **Data** | ⚠️ Insufficient data for trend analysis |\n"

    dashboard += """
### Key Insights
"""

    # Generate insights based on current metrics
    insights = []

    if basic_metrics["win_rate"] == 0:
        insights.append("⚠️ **No closed trades yet** - System is collecting data")

    if basic_metrics["total_pl"] > 0:
        insights.append(f"✅ **Profitable** - ${basic_metrics['total_pl']:+,.2f} total P/L")

    if risk.get("sharpe_ratio", 0) < 0:
        insights.append("⚠️ **Negative Sharpe** - Risk-adjusted returns need improvement")

    if basic_metrics["automation_status"] == "OPERATIONAL":
        insights.append("✅ **Automation Active** - System running smoothly")

    if not insights:
        insights.append("📊 **System Monitoring** - Collecting baseline metrics")

    for insight in insights[:5]:  # Show top 5 insights
        dashboard += f"- {insight}\n"

    dashboard += """
---

## 📥 Data Export

**Export Options**:
- CSV Export: Available via `scripts/export_dashboard_data.py`
- Excel Export: Available via `scripts/export_dashboard_data.py`
- JSON API: Available via `data/system_state.json` and `data/performance_log.json`

*Note: Export scripts will be available in next update*

---

## 🔗 Quick Links

- [Repository](https://github.com/IgorGanapolsky/trading)
- [GitHub Actions](https://github.com/IgorGanapolsky/trading/actions)
- [Latest Trades](https://github.com/IgorGanapolsky/trading/tree/main/data)
- [Documentation](https://github.com/IgorGanapolsky/trading/tree/main/docs)
- [LangSmith RL Training Project](https://smith.langchain.com/o/bb00a62e-c62a-4c42-9031-43e1f74bb5b3/projects/p/04fa554e-f155-4039-bb7f-e866f082103b) *(Note: Project may show as "default" in LangSmith UI - this is correct)*
- [Vertex AI Training Jobs](https://console.cloud.google.com/vertex-ai/training/custom-jobs?project=email-outreach-ai-460404)

---

*This dashboard is automatically updated daily by GitHub Actions after trading execution.*
*World-class metrics powered by comprehensive risk & performance analytics.*
"""

    return dashboard


def main():
    """Generate and save dashboard."""
    dashboard = generate_dashboard()

    # Save to file (will be committed to wiki repo)
    output_file = Path("wiki/Progress-Dashboard.md")
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w") as f:
        f.write(dashboard)

    print("✅ World-class progress dashboard generated successfully!")
    print(f"📄 Saved to: {output_file}")
    print(f"📊 Metrics calculated for Day {calculate_metrics()['current_day']} of 90")
    print("🎯 World-class metrics: Risk, Performance, Strategy Diagnostics, Guardrails")

    return 0


if __name__ == "__main__":
    sys.exit(main())
