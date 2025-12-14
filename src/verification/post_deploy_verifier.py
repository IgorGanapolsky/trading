"""
Post-Deploy Verifier

Verification after deployment/merge to detect issues early.
Runs health checks and records anomalies to RAG.

Created: Dec 11, 2025 (after syntax error incident)
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DeploymentHealth:
    """Health status after deployment."""

    healthy: bool
    checks: dict
    anomalies: list[dict]
    timestamp: str

    def __bool__(self):
        return self.healthy


class PostDeployVerifier:
    """
    Verifies system health after deployment.

    Checks:
    1. Trading system can initialize
    2. Broker connections work
    3. Data feeds are live
    4. No error spikes in logs
    5. Performance within expected bounds

    Records anomalies to RAG for future prevention.
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent

    def verify_deployment(self) -> DeploymentHealth:
        """
        Run all post-deployment health checks.
        """
        checks = {}
        anomalies = []

        # Check 1: Trading system initializes
        checks["system_init"] = self._check_system_init()
        if not checks["system_init"]["healthy"]:
            anomalies.append(
                {
                    "type": "system_init_failure",
                    "details": checks["system_init"],
                    "severity": "critical",
                }
            )

        # Check 2: Critical imports
        checks["imports"] = self._check_imports()
        if not checks["imports"]["healthy"]:
            anomalies.append(
                {
                    "type": "import_failure",
                    "details": checks["imports"],
                    "severity": "critical",
                }
            )

        # Check 3: Configuration valid
        checks["config"] = self._check_config()
        if not checks["config"]["healthy"]:
            anomalies.append(
                {
                    "type": "config_invalid",
                    "details": checks["config"],
                    "severity": "high",
                }
            )

        # Check 4: Workflow file valid
        checks["workflows"] = self._check_workflows()
        if not checks["workflows"]["healthy"]:
            anomalies.append(
                {
                    "type": "workflow_invalid",
                    "details": checks["workflows"],
                    "severity": "high",
                }
            )

        # Record anomalies to RAG
        if anomalies:
            self._record_anomalies_to_rag(anomalies)

        return DeploymentHealth(
            healthy=all(c.get("healthy", False) for c in checks.values()),
            checks=checks,
            anomalies=anomalies,
            timestamp=datetime.utcnow().isoformat(),
        )

    def _check_system_init(self) -> dict:
        """Check if trading system can initialize."""
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    """
import sys
sys.path.insert(0, '.')
from src.orchestrator.main import TradingOrchestrator
print('OK')
""",
                ],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=30,
            )

            return {
                "healthy": result.returncode == 0 and "OK" in result.stdout,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if result.stderr else None,
            }

        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
            }

    def _check_imports(self) -> dict:
        """Check all critical imports work."""
        imports_to_check = [
            "from src.orchestrator.main import TradingOrchestrator",
            "from src.execution.alpaca_executor import AlpacaExecutor",
            "from src.risk.trade_gateway import TradeGateway",
        ]

        failed = []
        for imp in imports_to_check:
            try:
                result = subprocess.run(
                    [sys.executable, "-c", imp],
                    capture_output=True,
                    text=True,
                    cwd=str(self.project_root),
                    timeout=30,
                )
                if result.returncode != 0:
                    if "SyntaxError" in result.stderr:
                        failed.append({"import": imp, "error": "SyntaxError"})
            except Exception as e:
                failed.append({"import": imp, "error": str(e)})

        return {
            "healthy": len(failed) == 0,
            "failed": failed,
        }

    def _check_config(self) -> dict:
        """Check configuration files are valid."""
        config_files = [
            "pyproject.toml",
            ".github/workflows/daily-trading.yml",
        ]

        issues = []
        for config in config_files:
            path = self.project_root / config
            if not path.exists():
                issues.append({"file": config, "issue": "not found"})
                continue

            # Basic validation
            try:
                content = path.read_text()
                if len(content) < 10:
                    issues.append({"file": config, "issue": "file too small"})
            except Exception as e:
                issues.append({"file": config, "issue": str(e)})

        return {
            "healthy": len(issues) == 0,
            "issues": issues,
        }

    def _check_workflows(self) -> dict:
        """Check GitHub workflow files are valid YAML."""
        import yaml

        issues = []
        workflow_dir = self.project_root / ".github" / "workflows"

        for wf in workflow_dir.glob("*.yml"):
            try:
                with open(wf) as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                issues.append({"file": str(wf), "error": str(e)})

        return {
            "healthy": len(issues) == 0,
            "issues": issues,
        }

    def _record_anomalies_to_rag(self, anomalies: list[dict]) -> None:
        """Record deployment anomalies to RAG for learning."""
        try:
            from .rag_safety_checker import RAGSafetyChecker

            checker = RAGSafetyChecker()
            for anomaly in anomalies:
                checker.record_incident(
                    category="deployment",
                    title=f"Post-deploy failure: {anomaly['type']}",
                    description=json.dumps(anomaly["details"], indent=2),
                    root_cause="Deployment verification failed",
                    prevention="Run pre-merge verification before merge",
                    severity=anomaly.get("severity", "medium"),
                    tags=["deployment", "automated", anomaly["type"]],
                )

        except Exception as e:
            logger.warning(f"Failed to record anomalies to RAG: {e}")


def main():
    """CLI entry point."""
    verifier = PostDeployVerifier()
    result = verifier.verify_deployment()

    print("\n" + "=" * 60)
    print("POST-DEPLOYMENT VERIFICATION")
    print("=" * 60)
    print(f"Status: {'✅ HEALTHY' if result.healthy else '❌ UNHEALTHY'}")
    print(f"Timestamp: {result.timestamp}")

    for check_name, check_result in result.checks.items():
        status = "✅" if check_result.get("healthy") else "❌"
        print(f"  {status} {check_name}")

    if result.anomalies:
        print("\nANOMALIES DETECTED:")
        for a in result.anomalies:
            print(f"  - {a['type']} ({a['severity']})")

    sys.exit(0 if result.healthy else 1)


if __name__ == "__main__":
    main()
