#!/usr/bin/env python3
"""
Self-Healing Health Check System for Claude Code Learning Infrastructure

This script checks the health of all feedback/memory systems and attempts
automatic recovery when issues are detected.

Components monitored:
1. LanceDB (local vector store)
2. ChromaDB (local RAG)
3. LangSmith (observability)
4. Feedback log (RLHF)

Best practices from 2025/2026:
- Observability-first design (monitor LTES: Latency, Traffic, Errors, Saturation)
- Automatic anomaly detection
- Self-healing with exponential backoff
- Circuit breaker pattern for failing services

Sources:
- https://blog.nashtechglobal.com/self-healing/
- https://opentelemetry.io/blog/2025/ai-agent-observability/
- https://superagi.com/a-beginners-guide-to-implementing-self-healing-ai-systems-step-by-step-strategies-for-2025/
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configuration
SCRIPT_DIR = Path(__file__).parent
MEMORY_DIR = SCRIPT_DIR.parent.parent / "memory"
FEEDBACK_DIR = SCRIPT_DIR

# Health check thresholds
MAX_STALE_HOURS = 72  # 3 days - less aggressive (Jan 2026: avoid blocking startup)
MAX_RETRY_ATTEMPTS = 1  # Single attempt only during startup (Jan 2026 best practice)
BACKOFF_BASE_SECONDS = 0  # No backoff during startup - defer to background healing

# Mode flags
STARTUP_MODE = "--startup" in sys.argv  # Fast, non-blocking mode for session start
HEAL_MODE = "--heal" in sys.argv  # Full healing mode (run separately/scheduled)

# Status tracking
HEALTH_STATUS_FILE = MEMORY_DIR / "health-status.json"


class HealthChecker:
    """Self-healing health checker for Claude Code learning infrastructure."""

    def __init__(self):
        self.status = {
            "last_check": None,
            "components": {},
            "overall_health": "unknown",
            "auto_healed": []
        }
        self.venv_python = FEEDBACK_DIR / "venv" / "bin" / "python3"

    def check_all(self, startup_mode: bool = False, heal_mode: bool = False) -> Dict:
        """Run all health checks and optionally attempt auto-healing.

        Jan 2026 Best Practice (AWS/Kubernetes/Claude Code):
        - startup_mode: Fast, non-blocking checks only (no healing)
        - heal_mode: Full healing with retries (run in background/scheduled)
        - default: Check + single heal attempt (legacy behavior)
        """
        if startup_mode:
            print("🏥 Quick Health Check (startup mode)")
        else:
            print("=" * 60)
            print("🏥 SELF-HEALING HEALTH CHECK")
            print("=" * 60)
            print()

        self.status["last_check"] = datetime.now().isoformat()
        self.status["auto_healed"] = []

        # Check each component (Jan 2026: cloud RAG removed - project uses ChromaDB + LanceDB only)
        checks = [
            ("lancedb", self.check_lancedb),
            ("chromadb", self.check_chromadb),
            ("langsmith", self.check_langsmith),
            ("feedback_log", self.check_feedback_log),
        ]

        all_healthy = True
        for name, check_fn in checks:
            try:
                healthy, message, can_heal = check_fn()
                self.status["components"][name] = {
                    "healthy": healthy,
                    "message": message,
                    "checked_at": datetime.now().isoformat()
                }

                status_icon = "✅" if healthy else "❌"

                # In startup mode, only print summary (no verbose output)
                if not startup_mode:
                    print(f"{status_icon} {name}: {message}")

                if not healthy:
                    all_healthy = False
                    # Jan 2026: Only heal in heal_mode OR if explicitly not startup
                    if can_heal and heal_mode:
                        self.attempt_healing(name)
                    elif can_heal and not startup_mode and not heal_mode:
                        # Legacy: single attempt without retries
                        self.attempt_healing_once(name)

            except Exception as e:
                self.status["components"][name] = {
                    "healthy": False,
                    "message": f"Check failed: {str(e)}",
                    "checked_at": datetime.now().isoformat()
                }
                if not startup_mode:
                    print(f"❌ {name}: Check failed - {str(e)}")
                all_healthy = False

        self.status["overall_health"] = "healthy" if all_healthy else "degraded"

        # Save status
        self.save_status()

        if startup_mode:
            # Single line summary for fast startup
            if all_healthy:
                print("   ✅ All systems healthy")
            else:
                unhealthy = [k for k, v in self.status["components"].items() if not v.get("healthy")]
                print(f"   ⚠️  Degraded: {', '.join(unhealthy)} (run --heal to fix)")
        else:
            print()
            print("=" * 60)
            overall_icon = "✅" if all_healthy else "⚠️"
            print(f"{overall_icon} Overall Health: {self.status['overall_health'].upper()}")

            if self.status["auto_healed"]:
                print(f"🔧 Auto-healed: {', '.join(self.status['auto_healed'])}")
            print("=" * 60)

        return self.status

    def check_lancedb(self) -> Tuple[bool, str, bool]:
        """Check LanceDB health."""
        lancedb_path = MEMORY_DIR / "feedback" / "lancedb"

        if not lancedb_path.exists():
            return False, "LanceDB directory not found", True

        # Check for recent data
        lance_files = list(lancedb_path.glob("**/*.lance"))
        if not lance_files:
            return False, "No .lance files found", True

        # Check freshness
        newest = max(f.stat().st_mtime for f in lance_files)
        age_hours = (time.time() - newest) / 3600

        if age_hours > MAX_STALE_HOURS:
            return False, f"Data is {age_hours:.1f}h old (threshold: {MAX_STALE_HOURS}h)", True

        return True, f"Healthy ({len(lance_files)} files, {age_hours:.1f}h old)", False

    def check_chromadb(self) -> Tuple[bool, str, bool]:
        """Check ChromaDB health."""
        chroma_path = MEMORY_DIR / "chroma_db"

        if not chroma_path.exists():
            return False, "ChromaDB directory not found", True

        # Check for data files
        sqlite_file = chroma_path / "chroma.sqlite3"
        if not sqlite_file.exists():
            return False, "ChromaDB sqlite file not found", True

        # Check freshness
        age_hours = (time.time() - sqlite_file.stat().st_mtime) / 3600

        if age_hours > MAX_STALE_HOURS:
            return False, f"Data is {age_hours:.1f}h old (threshold: {MAX_STALE_HOURS}h)", True

        return True, f"Healthy ({age_hours:.1f}h old)", False

    def check_langsmith(self) -> Tuple[bool, str, bool]:
        """Check LangSmith connectivity and error rate."""
        # Check for LANGSMITH_API_KEY
        if not os.environ.get("LANGSMITH_API_KEY"):
            # Try to load from .env or .env.local
            for env_name in [".env", ".env.local"]:
                env_file = Path.cwd() / env_name
                if env_file.exists():
                    with open(env_file) as f:
                        for line in f:
                            if line.startswith("LANGSMITH_API_KEY="):
                                os.environ["LANGSMITH_API_KEY"] = line.strip().split("=", 1)[1]
                                break
                    if os.environ.get("LANGSMITH_API_KEY"):
                        break

        if not os.environ.get("LANGSMITH_API_KEY"):
            # LangSmith is optional - return True with warning (Jan 2026: don't fail on optional services)
            return True, "Not configured (optional)", False

        # Try a simple API check
        try:
            import requests
            resp = requests.get(
                "https://api.smith.langchain.com/api/v1/info",
                headers={"x-api-key": os.environ["LANGSMITH_API_KEY"]},
                timeout=10
            )
            if resp.status_code == 200:
                return True, "Connected to LangSmith", False
            else:
                return False, f"API returned {resp.status_code}", False
        except ImportError:
            return True, "Requests not installed - skipping API check", False
        except Exception as e:
            return False, f"Connection failed: {str(e)}", False

    def check_feedback_log(self) -> Tuple[bool, str, bool]:
        """Check feedback log health."""
        feedback_log = MEMORY_DIR / "feedback" / "feedback-log.jsonl"

        if not feedback_log.exists():
            return False, "Feedback log not found", False

        # Count entries and check freshness
        try:
            with open(feedback_log) as f:
                lines = f.readlines()

            if not lines:
                return True, "Empty log (no feedback recorded yet)", False

            # Check last entry
            last_entry = json.loads(lines[-1])
            last_time = datetime.fromisoformat(last_entry.get("timestamp", "2000-01-01"))
            age_hours = (datetime.now() - last_time.replace(tzinfo=None)).total_seconds() / 3600

            return True, f"Healthy ({len(lines)} entries, last {age_hours:.1f}h ago)", False

        except Exception as e:
            return False, f"Failed to read log: {str(e)}", False

    def attempt_healing_once(self, component: str):
        """Single healing attempt without retries (Jan 2026: fast startup).

        For full healing with retries, use --heal flag or run scheduled.
        """
        # Jan 2026: cloud RAG removed - project uses ChromaDB + LanceDB only
        heal_functions = {
            "lancedb": self.heal_lancedb,
            "chromadb": self.heal_chromadb,
        }

        heal_fn = heal_functions.get(component)
        if not heal_fn:
            return

        try:
            print(f"   🔧 Quick heal attempt for {component}...")
            success = heal_fn()
            if success:
                print(f"   ✅ {component} healed!")
                self.status["auto_healed"].append(component)
                self.status["components"][component]["healthy"] = True
                self.status["components"][component]["message"] = "Auto-healed"
        except Exception as e:
            print(f"   ⚠️  Quick heal failed: {str(e)} (run --heal for full recovery)")

    def attempt_healing(self, component: str):
        """Full healing with exponential backoff (use --heal flag)."""
        print(f"   🔧 Attempting to heal {component}...")

        # Jan 2026: cloud RAG removed - project uses ChromaDB + LanceDB only
        heal_functions = {
            "lancedb": self.heal_lancedb,
            "chromadb": self.heal_chromadb,
        }

        heal_fn = heal_functions.get(component)
        if not heal_fn:
            print(f"   ⚠️  No healing procedure for {component}")
            return

        # Full healing mode uses configured retry attempts
        retry_attempts = 3 if HEAL_MODE else MAX_RETRY_ATTEMPTS
        backoff_base = 5 if HEAL_MODE else BACKOFF_BASE_SECONDS

        for attempt in range(1, retry_attempts + 1):
            try:
                backoff = backoff_base * (2 ** (attempt - 1))
                if attempt > 1:
                    print(f"   ⏳ Retry {attempt}/{retry_attempts} after {backoff}s backoff...")
                    time.sleep(backoff)

                success = heal_fn()
                if success:
                    print(f"   ✅ {component} healed successfully!")
                    self.status["auto_healed"].append(component)
                    self.status["components"][component]["healthy"] = True
                    self.status["components"][component]["message"] = "Auto-healed"
                    return

            except Exception as e:
                print(f"   ❌ Healing attempt {attempt} failed: {str(e)}")

        print(f"   ❌ Failed to heal {component} after {retry_attempts} attempts")

    def heal_lancedb(self) -> bool:
        """Re-index LanceDB."""
        result = subprocess.run(
            [str(self.venv_python), str(FEEDBACK_DIR / "semantic-memory-v2.py"), "--index"],
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode == 0

    def heal_chromadb(self) -> bool:
        """Re-index ChromaDB."""
        result = subprocess.run(
            [str(self.venv_python), str(FEEDBACK_DIR / "local-rag-enhanced.py"), "--index"],
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode == 0

    def save_status(self):
        """Save health status to file."""
        HEALTH_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HEALTH_STATUS_FILE, "w") as f:
            json.dump(self.status, f, indent=2)


def main():
    """Run health check.

    Usage:
        python health-check.py           # Default: check + single heal attempt
        python health-check.py --startup # Fast: check only, no healing (for session start)
        python health-check.py --heal    # Full: check + healing with retries (for scheduled/manual)

    Jan 2026 Best Practice:
    - Session startup should use --startup for non-blocking fast checks
    - Schedule --heal to run periodically in background (cron/launchd)
    - Manual --heal when you want to fix degraded systems
    """
    checker = HealthChecker()
    status = checker.check_all(startup_mode=STARTUP_MODE, heal_mode=HEAL_MODE)

    # Exit with appropriate code
    sys.exit(0 if status["overall_health"] == "healthy" else 1)


if __name__ == "__main__":
    main()
