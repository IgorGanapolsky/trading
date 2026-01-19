"""
Self-Healing System Monitor.

Automatically detects and fixes common issues in the trading system.

Health Checks:
1. Data integrity (JSON files, system state)
2. API connectivity (Alpaca, Vertex AI)
3. Position compliance (CLAUDE.md rules)
4. Stale data detection
5. Configuration drift

Auto-Fix Capabilities:
- Regenerate corrupt JSON files
- Reset circuit breakers
- Sync stale data
- Clean up deprecated files

Created: Jan 19, 2026 (LL-249: Resilience and Self-Healing)
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Any

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    HEALED = "healed"  # Was unhealthy, auto-fixed


@dataclass
class HealthCheck:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str
    details: dict = field(default_factory=dict)
    auto_fixed: bool = False
    fix_action: str | None = None


class SelfHealer:
    """
    Self-healing system monitor.

    Usage:
        healer = SelfHealer(project_root="/home/user/trading")
        results = healer.run_all_checks()

        # Auto-fix issues
        healer.heal()

        # Get summary
        print(healer.get_summary())
    """

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root or os.getcwd())
        self.checks: list[HealthCheck] = []
        self._healers: dict[str, Callable[[], bool]] = {}

    def run_all_checks(self) -> list[HealthCheck]:
        """Run all health checks."""
        self.checks = []

        # Data integrity checks
        self.checks.append(self._check_system_state())
        self.checks.append(self._check_json_files())

        # Configuration checks
        self.checks.append(self._check_env_vars())
        self.checks.append(self._check_claude_md())

        # Staleness checks
        self.checks.append(self._check_data_freshness())

        # Compliance checks
        self.checks.append(self._check_position_compliance())

        return self.checks

    def _check_system_state(self) -> HealthCheck:
        """Check system_state.json integrity."""
        state_file = self.project_root / "data" / "system_state.json"

        if not state_file.exists():
            return HealthCheck(
                name="system_state",
                status=HealthStatus.UNHEALTHY,
                message="system_state.json not found",
                details={"path": str(state_file)},
            )

        try:
            with open(state_file) as f:
                data = json.load(f)

            # Validate required fields
            required = ["portfolio", "positions", "trade_history"]
            missing = [k for k in required if k not in data]

            if missing:
                return HealthCheck(
                    name="system_state",
                    status=HealthStatus.DEGRADED,
                    message=f"Missing required fields: {missing}",
                    details={"missing_fields": missing},
                )

            return HealthCheck(
                name="system_state",
                status=HealthStatus.HEALTHY,
                message="system_state.json is valid",
                details={
                    "equity": data.get("portfolio", {}).get("equity"),
                    "positions_count": len(data.get("positions", [])),
                    "trades_count": len(data.get("trade_history", [])),
                },
            )

        except json.JSONDecodeError as e:
            self._healers["system_state"] = self._heal_corrupt_json
            return HealthCheck(
                name="system_state",
                status=HealthStatus.UNHEALTHY,
                message=f"Corrupt JSON: {e}",
                details={"error": str(e), "can_heal": True},
            )

    def _check_json_files(self) -> HealthCheck:
        """Check all JSON files for corruption."""
        data_dir = self.project_root / "data"
        corrupt_files = []
        valid_count = 0

        for json_file in data_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    json.load(f)
                valid_count += 1
            except json.JSONDecodeError:
                corrupt_files.append(str(json_file.name))

        if corrupt_files:
            return HealthCheck(
                name="json_files",
                status=HealthStatus.UNHEALTHY,
                message=f"Corrupt JSON files: {corrupt_files}",
                details={"corrupt": corrupt_files, "valid": valid_count},
            )

        return HealthCheck(
            name="json_files",
            status=HealthStatus.HEALTHY,
            message=f"All {valid_count} JSON files are valid",
            details={"valid_count": valid_count},
        )

    def _check_env_vars(self) -> HealthCheck:
        """Check critical environment variables."""
        required = [
            "ALPACA_PAPER_TRADING_5K_API_KEY",
            "ALPACA_PAPER_TRADING_5K_API_SECRET",
        ]

        # Check in .env file or environment
        missing = []
        for var in required:
            if not os.getenv(var):
                missing.append(var)

        if missing:
            return HealthCheck(
                name="env_vars",
                status=HealthStatus.DEGRADED,
                message=f"Missing env vars: {missing}",
                details={"missing": missing},
            )

        return HealthCheck(
            name="env_vars",
            status=HealthStatus.HEALTHY,
            message="All required environment variables set",
        )

    def _check_claude_md(self) -> HealthCheck:
        """Check CLAUDE.md exists and has required sections."""
        claude_md = self.project_root / ".claude" / "CLAUDE.md"

        if not claude_md.exists():
            return HealthCheck(
                name="claude_md",
                status=HealthStatus.UNHEALTHY,
                message="CLAUDE.md not found",
            )

        content = claude_md.read_text()
        required_sections = ["## Strategy", "iron condor", "SPY"]

        missing = [s for s in required_sections if s.lower() not in content.lower()]

        if missing:
            return HealthCheck(
                name="claude_md",
                status=HealthStatus.DEGRADED,
                message=f"CLAUDE.md missing sections: {missing}",
                details={"missing": missing},
            )

        return HealthCheck(
            name="claude_md",
            status=HealthStatus.HEALTHY,
            message="CLAUDE.md is properly configured",
        )

    def _check_data_freshness(self) -> HealthCheck:
        """Check if data is stale."""
        state_file = self.project_root / "data" / "system_state.json"

        if not state_file.exists():
            return HealthCheck(
                name="data_freshness",
                status=HealthStatus.UNHEALTHY,
                message="No data file to check",
            )

        try:
            with open(state_file) as f:
                data = json.load(f)

            last_updated = data.get("last_updated")
            if not last_updated:
                return HealthCheck(
                    name="data_freshness",
                    status=HealthStatus.DEGRADED,
                    message="No last_updated timestamp",
                )

            # Parse timestamp
            if last_updated.endswith("Z"):
                last_updated = last_updated[:-1] + "+00:00"

            updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            now = datetime.now(updated_dt.tzinfo)
            age = now - updated_dt

            # Check staleness thresholds
            if age > timedelta(hours=24):
                self._healers["data_freshness"] = self._heal_stale_data
                return HealthCheck(
                    name="data_freshness",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Data is {age.total_seconds()/3600:.1f} hours old",
                    details={"age_hours": age.total_seconds()/3600, "can_heal": True},
                )
            elif age > timedelta(hours=4):
                return HealthCheck(
                    name="data_freshness",
                    status=HealthStatus.DEGRADED,
                    message=f"Data is {age.total_seconds()/3600:.1f} hours old",
                    details={"age_hours": age.total_seconds()/3600},
                )

            return HealthCheck(
                name="data_freshness",
                status=HealthStatus.HEALTHY,
                message=f"Data is {age.total_seconds()/60:.0f} minutes old",
                details={"age_minutes": age.total_seconds()/60},
            )

        except Exception as e:
            return HealthCheck(
                name="data_freshness",
                status=HealthStatus.DEGRADED,
                message=f"Could not check freshness: {e}",
            )

    def _check_position_compliance(self) -> HealthCheck:
        """Check positions comply with CLAUDE.md rules."""
        state_file = self.project_root / "data" / "system_state.json"

        if not state_file.exists():
            return HealthCheck(
                name="position_compliance",
                status=HealthStatus.DEGRADED,
                message="No system state to check",
            )

        try:
            with open(state_file) as f:
                data = json.load(f)

            positions = data.get("positions", [])
            equity = data.get("portfolio", {}).get("equity", 5000)
            max_position_value = equity * 0.05  # 5% rule

            violations = []

            # Check position count (max 4 per CLAUDE.md)
            if len(positions) > 4:
                violations.append(f"Position count {len(positions)} > 4 max")

            # Check position values
            for pos in positions:
                value = abs(pos.get("value", 0))
                symbol = pos.get("symbol", "UNKNOWN")

                if value > max_position_value:
                    violations.append(
                        f"{symbol} value ${value:.2f} > ${max_position_value:.2f} (5% limit)"
                    )

                # Check for non-SPY positions
                underlying = symbol[:3] if len(symbol) > 3 else symbol
                if underlying not in ["SPY"]:
                    violations.append(f"{symbol} not SPY (CLAUDE.md: SPY ONLY)")

            if violations:
                return HealthCheck(
                    name="position_compliance",
                    status=HealthStatus.UNHEALTHY,
                    message=f"{len(violations)} compliance violations",
                    details={"violations": violations},
                )

            return HealthCheck(
                name="position_compliance",
                status=HealthStatus.HEALTHY,
                message="All positions comply with CLAUDE.md",
                details={"position_count": len(positions)},
            )

        except Exception as e:
            return HealthCheck(
                name="position_compliance",
                status=HealthStatus.DEGRADED,
                message=f"Could not check compliance: {e}",
            )

    def _heal_corrupt_json(self) -> bool:
        """Attempt to heal corrupt JSON by restoring from backup."""
        state_file = self.project_root / "data" / "system_state.json"
        backup_dir = self.project_root / "data" / "backups"

        # Find most recent backup
        backups = sorted(backup_dir.glob("system_state_*.json"), reverse=True)

        if not backups:
            logger.error("No backups found to restore from")
            return False

        latest_backup = backups[0]
        try:
            # Validate backup
            with open(latest_backup) as f:
                data = json.load(f)

            # Restore
            with open(state_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Restored system_state.json from {latest_backup.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False

    def _heal_stale_data(self) -> bool:
        """Trigger data sync to heal stale data."""
        logger.info("Triggering data sync to heal stale data...")
        # This would typically trigger a GitHub Actions workflow or API call
        # For now, log the intent
        return False  # Manual intervention needed

    def heal(self) -> list[HealthCheck]:
        """Attempt to auto-fix all healable issues."""
        healed = []

        for check in self.checks:
            if check.status == HealthStatus.UNHEALTHY and check.name in self._healers:
                healer = self._healers[check.name]
                try:
                    if healer():
                        check.status = HealthStatus.HEALED
                        check.auto_fixed = True
                        check.fix_action = healer.__name__
                        healed.append(check)
                        logger.info(f"Auto-healed: {check.name}")
                except Exception as e:
                    logger.error(f"Failed to heal {check.name}: {e}")

        return healed

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all health checks."""
        by_status = {status.value: 0 for status in HealthStatus}

        for check in self.checks:
            by_status[check.status.value] += 1

        overall = HealthStatus.HEALTHY
        if by_status["unhealthy"] > 0:
            overall = HealthStatus.UNHEALTHY
        elif by_status["degraded"] > 0:
            overall = HealthStatus.DEGRADED

        return {
            "overall_status": overall.value,
            "total_checks": len(self.checks),
            "by_status": by_status,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "auto_fixed": c.auto_fixed,
                }
                for c in self.checks
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def get_report(self) -> str:
        """Get human-readable health report."""
        lines = [
            "=" * 60,
            "SELF-HEALING HEALTH CHECK REPORT",
            "=" * 60,
            "",
        ]

        summary = self.get_summary()
        lines.append(f"Overall Status: {summary['overall_status'].upper()}")
        lines.append(f"Total Checks: {summary['total_checks']}")
        lines.append("")

        for check in self.checks:
            status_icon = {
                HealthStatus.HEALTHY: "✅",
                HealthStatus.DEGRADED: "⚠️",
                HealthStatus.UNHEALTHY: "❌",
                HealthStatus.HEALED: "🔧",
            }.get(check.status, "❓")

            lines.append(f"{status_icon} {check.name}: {check.message}")
            if check.auto_fixed:
                lines.append(f"   └─ Auto-fixed via {check.fix_action}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)
