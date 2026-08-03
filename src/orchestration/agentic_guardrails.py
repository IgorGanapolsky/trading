"""
Agentic Guardrails - GitHub Copilot Agentic Best Practices Implementation.

Based on: https://github.blog/ai-and-ml/github-copilot/how-to-maximize-github-copilots-agentic-capabilities/

Key principles implemented:
1. Architecture analysis phase before any changes
2. Review gates between swarm phases
3. Dual-read migration strategy for data safety
4. CEO approval required for trading logic changes
5. Module contracts for agent boundaries

CRITICAL: Phil Town Rule #1 compliance - never alter trading logic without human review.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Project paths
PROJECT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
CONTRACTS_DIR = PROJECT_DIR / "docs" / "module_contracts"

# Ensure directories exist
CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)


class ChangeCategory(Enum):
    """Categories of changes with different approval requirements."""

    TRADING_LOGIC = "trading_logic"  # REQUIRES CEO APPROVAL
    RISK_MANAGEMENT = "risk_management"  # REQUIRES CEO APPROVAL
    DATA_MIGRATION = "data_migration"  # REQUIRES DUAL-READ VALIDATION
    AGENT_BEHAVIOR = "agent_behavior"  # REQUIRES REVIEW GATE
    UI_CONTENT = "ui_content"  # AUTO-APPROVED
    DOCUMENTATION = "documentation"  # AUTO-APPROVED
    TEST_CODE = "test_code"  # AUTO-APPROVED


class ApprovalStatus(Enum):
    """Status of change approval."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"


@dataclass
class ModuleContract:
    """Defines boundaries and responsibilities of a system module."""

    module_name: str
    description: str
    responsibilities: list[str]
    inputs: dict[str, str]  # name -> type/description
    outputs: dict[str, str]  # name -> type/description
    dependencies: list[str]  # modules this depends on
    dependents: list[str]  # modules that depend on this
    change_category: ChangeCategory
    owner: str = "CTO"  # Default owner is Claude CTO
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "description": self.description,
            "responsibilities": self.responsibilities,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "change_category": self.change_category.value,
            "owner": self.owner,
            "last_updated": self.last_updated.isoformat(),
        }

    def save(self) -> Path:
        """Save contract to docs/module_contracts/."""
        filepath = CONTRACTS_DIR / f"{self.module_name}.json"
        filepath.write_text(json.dumps(self.to_dict(), indent=2))
        return filepath


@dataclass
class ChangeRequest:
    """A request to change system behavior."""

    change_id: str
    description: str
    category: ChangeCategory
    affected_modules: list[str]
    proposed_changes: str
    rollback_procedure: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    ceo_approval_required: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    approved_by: str | None = None

    def __post_init__(self):
        # Determine if CEO approval is required
        if self.category in [
            ChangeCategory.TRADING_LOGIC,
            ChangeCategory.RISK_MANAGEMENT,
        ]:
            self.ceo_approval_required = True


class ArchitectureAnalyzer:
    """
    Analyzes system architecture before changes.

    Implements "Start with architecture, not code" principle.
    """

    # Known module contracts
    CORE_MODULES: dict[str, ModuleContract] = {}

    def __init__(self):
        self._load_contracts()

    def _load_contracts(self) -> None:
        """Load existing module contracts."""
        for filepath in CONTRACTS_DIR.glob("*.json"):
            try:
                data = json.loads(filepath.read_text())
                contract = ModuleContract(
                    module_name=data["module_name"],
                    description=data["description"],
                    responsibilities=data["responsibilities"],
                    inputs=data["inputs"],
                    outputs=data["outputs"],
                    dependencies=data["dependencies"],
                    dependents=data["dependents"],
                    change_category=ChangeCategory(data["change_category"]),
                    owner=data.get("owner", "CTO"),
                )
                self.CORE_MODULES[contract.module_name] = contract
            except (json.JSONDecodeError, KeyError):
                continue

    def analyze_change_impact(self, affected_files: list[str]) -> dict[str, Any]:
        """
        Analyze the impact of changes to specific files.

        Returns blast radius analysis.
        """
        affected_modules = set()
        downstream_impact = set()
        change_categories = set()

        for filepath in affected_files:
            # Determine module from filepath
            module = self._filepath_to_module(filepath)
            if module:
                affected_modules.add(module)

                # Check contract for dependencies
                if module in self.CORE_MODULES:
                    contract = self.CORE_MODULES[module]
                    downstream_impact.update(contract.dependents)
                    change_categories.add(contract.change_category)

        # Determine highest-risk category
        risk_order = [
            ChangeCategory.TRADING_LOGIC,
            ChangeCategory.RISK_MANAGEMENT,
            ChangeCategory.DATA_MIGRATION,
            ChangeCategory.AGENT_BEHAVIOR,
            ChangeCategory.TEST_CODE,
            ChangeCategory.UI_CONTENT,
            ChangeCategory.DOCUMENTATION,
        ]

        highest_risk = ChangeCategory.DOCUMENTATION
        for cat in risk_order:
            if cat in change_categories:
                highest_risk = cat
                break

        return {
            "affected_modules": list(affected_modules),
            "downstream_impact": list(downstream_impact),
            "blast_radius": len(affected_modules) + len(downstream_impact),
            "highest_risk_category": highest_risk.value,
            "requires_ceo_approval": highest_risk
            in [ChangeCategory.TRADING_LOGIC, ChangeCategory.RISK_MANAGEMENT],
            "requires_dual_read": highest_risk == ChangeCategory.DATA_MIGRATION,
        }

    def _filepath_to_module(self, filepath: str) -> str | None:
        """Map a filepath to its module name."""
        path = Path(filepath)

        # Trading logic files
        if "trading" in str(path) or "order" in str(path):
            return "trading_execution"

        # Risk management
        if "risk" in str(path):
            return "risk_management"

        # Data files
        if "data/" in str(path) or "system_state" in str(path):
            return "data_layer"

        # Agents
        if "agent" in str(path):
            return "agent_swarm"

        # Tests
        if "test" in str(path):
            return "test_suite"

        return None


class ReviewGate:
    """
    Implements review gates between swarm phases.

    "Execute in controlled phases with review gates between."
    """

    def __init__(self, gate_name: str):
        self.gate_name = gate_name
        self.checks_passed: list[str] = []
        self.checks_failed: list[str] = []
        self.is_open = False

    def add_check(self, check_name: str, passed: bool, reason: str = "") -> None:
        """Add a check result to the gate."""
        if passed:
            self.checks_passed.append(check_name)
        else:
            self.checks_failed.append(f"{check_name}: {reason}")

    def evaluate(self) -> tuple[bool, str]:
        """Evaluate if the gate should open."""
        if self.checks_failed:
            self.is_open = False
            return (
                False,
                f"Gate {self.gate_name} BLOCKED: {', '.join(self.checks_failed)}",
            )

        if not self.checks_passed:
            self.is_open = False
            return False, f"Gate {self.gate_name} BLOCKED: No checks passed"

        self.is_open = True
        return (
            True,
            f"Gate {self.gate_name} OPEN: {len(self.checks_passed)} checks passed",
        )


class DualReadMigration:
    """
    Implements dual-read strategy for safe data migrations.

    "Design migrations that remain reversible."
    """

    def __init__(self, source_path: Path, target_path: Path):
        self.source_path = source_path
        self.target_path = target_path
        self.backup_path = source_path.with_suffix(".backup.json")
        self.migration_log: list[dict] = []

    def create_backup(self) -> bool:
        """Create backup before migration."""
        try:
            if self.source_path.exists():
                import shutil

                shutil.copy2(self.source_path, self.backup_path)
                self.migration_log.append(
                    {
                        "action": "backup_created",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "backup_path": str(self.backup_path),
                    }
                )
                return True
        except Exception as e:
            self.migration_log.append(
                {
                    "action": "backup_failed",
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        return False

    def validate_dual_read(self) -> tuple[bool, str]:
        """
        Validate that both old and new formats can be read.

        Returns (success, message).
        """
        errors = []

        # Check source readability
        if self.source_path.exists():
            try:
                json.loads(self.source_path.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"Source unreadable: {e}")

        # Check target readability
        if self.target_path.exists():
            try:
                json.loads(self.target_path.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"Target unreadable: {e}")

        # Check backup readability
        if self.backup_path.exists():
            try:
                json.loads(self.backup_path.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"Backup unreadable: {e}")

        if errors:
            return False, "; ".join(errors)

        return True, "Dual-read validation passed"

    def rollback(self) -> bool:
        """Rollback to backup."""
        try:
            if self.backup_path.exists():
                import shutil

                shutil.copy2(self.backup_path, self.source_path)
                self.migration_log.append(
                    {
                        "action": "rollback_completed",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                return True
        except Exception as e:
            self.migration_log.append(
                {
                    "action": "rollback_failed",
                    "error": str(e),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        return False


class CEOApprovalGate:
    """
    Gate that requires CEO approval for trading logic changes.

    "Copilot should support your decision-making, not replace it."
    """

    PROTECTED_PATTERNS = [
        "position_size",
        "max_loss",
        "stop_loss",
        "delta",
        "strike",
        "expiration",
        "entry_rules",
        "exit_rules",
        "phil_town",
        "rule_1",
        "risk_percent",
    ]

    def __init__(self):
        self.pending_approvals: list[ChangeRequest] = []

    def check_requires_approval(self, change_description: str, affected_code: str) -> bool:
        """Check if a change requires CEO approval."""
        combined = (change_description + affected_code).lower()
        return any(pattern in combined for pattern in self.PROTECTED_PATTERNS)

    def request_approval(self, change: ChangeRequest) -> str:
        """
        Request CEO approval for a change.

        Returns approval request message.
        """
        self.pending_approvals.append(change)

        return f"""
═══════════════════════════════════════════════════════════
🚨 CEO APPROVAL REQUIRED - TRADING LOGIC CHANGE
═══════════════════════════════════════════════════════════
Change ID: {change.change_id}
Category: {change.category.value}
Description: {change.description}

Affected Modules: {", ".join(change.affected_modules)}

Proposed Changes:
{change.proposed_changes}

Rollback Procedure:
{change.rollback_procedure}

⚠️  This change affects trading logic protected by Phil Town Rule #1.
Please review and respond with:
- "approve {change.change_id}" to proceed
- "reject {change.change_id}" to cancel
═══════════════════════════════════════════════════════════
"""

    def process_approval(self, change_id: str, approved: bool, approver: str = "CEO") -> bool:
        """Process an approval decision."""
        for change in self.pending_approvals:
            if change.change_id == change_id:
                if approved:
                    change.status = ApprovalStatus.APPROVED
                    change.approved_at = datetime.now(UTC)
                    change.approved_by = approver
                else:
                    change.status = ApprovalStatus.REJECTED

                self.pending_approvals.remove(change)
                return True

        return False


def create_core_module_contracts() -> list[Path]:
    """Create module contracts for core system components."""
    contracts = [
        ModuleContract(
            module_name="trading_execution",
            description="Executes iron condor trades on SPY via Alpaca API",
            responsibilities=[
                "Submit option orders to Alpaca",
                "Validate position sizing (max 5%)",
                "Enforce Phil Town Rule #1",
                "Track trade history",
            ],
            inputs={
                "signal": "float 0-1 from swarm consensus",
                "regime": "str market regime from ML clustering",
                "vix": "float current VIX level",
            },
            outputs={
                "order_id": "str Alpaca order ID",
                "trade_result": "dict with P/L and status",
            },
            dependencies=["risk_management", "agent_swarm", "data_layer"],
            dependents=[],
            change_category=ChangeCategory.TRADING_LOGIC,
            owner="CEO",  # Trading logic owned by CEO
        ),
        ModuleContract(
            module_name="risk_management",
            description="Enforces risk limits and position sizing rules",
            responsibilities=[
                "Calculate max position size (5% rule)",
                "Enforce stop-loss at 100% of credit",
                "Block trades in unfavorable regimes",
                "Track daily/weekly risk exposure",
            ],
            inputs={
                "portfolio_value": "float current account value",
                "proposed_trade": "dict trade parameters",
            },
            outputs={
                "approved": "bool whether trade passes risk checks",
                "adjusted_size": "int position size after risk adjustment",
                "risk_score": "float 0-1 risk assessment",
            },
            dependencies=["data_layer"],
            dependents=["trading_execution"],
            change_category=ChangeCategory.RISK_MANAGEMENT,
            owner="CEO",  # Risk management owned by CEO
        ),
        ModuleContract(
            module_name="agent_swarm",
            description="Multi-agent coordination for trading signals",
            responsibilities=[
                "Orchestrate gate-keeper agents (risk, regime)",
                "Run analysis agents in parallel",
                "Aggregate weighted signals",
                "Enforce structured reasoning pipeline",
            ],
            inputs={
                "market_data": "dict current market conditions",
                "mode": "str swarm execution mode",
            },
            outputs={
                "consensus": "float 0-1 trading signal",
                "decision": "str 'trade' or 'hold'",
                "agent_results": "list individual agent outputs",
            },
            dependencies=["data_layer"],
            dependents=["trading_execution"],
            change_category=ChangeCategory.AGENT_BEHAVIOR,
            owner="CTO",
        ),
        ModuleContract(
            module_name="data_layer",
            description="Manages system state and trade history",
            responsibilities=[
                "Sync with Alpaca API",
                "Maintain system_state.json",
                "Track trade history",
                "Provide data to all modules",
            ],
            inputs={
                "alpaca_credentials": "dict API keys",
                "update_data": "dict data to persist",
            },
            outputs={
                "system_state": "dict current system state",
                "trade_history": "list past trades",
            },
            dependencies=[],
            dependents=["trading_execution", "risk_management", "agent_swarm"],
            change_category=ChangeCategory.DATA_MIGRATION,
            owner="CTO",
        ),
        ModuleContract(
            module_name="research_agent",
            description="Perplexity Deep Research for strategy optimization",
            responsibilities=[
                "Run weekend backtest research",
                "Extract metrics from research",
                "Update optimal parameters",
                "Feed results to RAG",
            ],
            inputs={
                "queries": "list BacktestQuery objects",
                "priority_filter": "int query priority threshold",
            },
            outputs={
                "results": "list BacktestResult objects",
                "csv_path": "Path to exported CSV",
                "rag_lessons": "list Path to RAG lesson files",
            },
            dependencies=["data_layer"],
            dependents=["agent_swarm"],
            change_category=ChangeCategory.AGENT_BEHAVIOR,
            owner="CTO",
        ),
    ]

    paths = []
    for contract in contracts:
        path = contract.save()
        paths.append(path)
        print(f"Created contract: {path.name}")

    return paths


# Global instances
architecture_analyzer = ArchitectureAnalyzer()
ceo_approval_gate = CEOApprovalGate()


def analyze_before_change(affected_files: list[str]) -> dict[str, Any]:
    """
    Analyze architecture impact before making changes.

    This should be called before any significant code change.
    """
    return architecture_analyzer.analyze_change_impact(affected_files)


def create_review_gate(gate_name: str) -> ReviewGate:
    """Create a new review gate for a swarm phase."""
    return ReviewGate(gate_name)


def request_ceo_approval_if_needed(
    change_description: str,
    affected_code: str,
    affected_modules: list[str],
    rollback_procedure: str,
) -> tuple[bool, str]:
    """
    Check if CEO approval is needed and request it if so.

    Returns (needs_approval, message).
    """
    if ceo_approval_gate.check_requires_approval(change_description, affected_code):
        change = ChangeRequest(
            change_id=f"CHG-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            description=change_description,
            category=ChangeCategory.TRADING_LOGIC,
            affected_modules=affected_modules,
            proposed_changes=affected_code[:500],
            rollback_procedure=rollback_procedure,
        )
        message = ceo_approval_gate.request_approval(change)
        return True, message

    return False, "No approval required - proceeding automatically"


if __name__ == "__main__":
    # Create core module contracts
    print("Creating module contracts...")
    paths = create_core_module_contracts()
    print(f"\nCreated {len(paths)} module contracts in {CONTRACTS_DIR}")

    # Demo architecture analysis
    print("\n--- Architecture Analysis Demo ---")
    analysis = analyze_before_change(["src/trading/order_executor.py", "src/agents/risk_agent.py"])
    print(json.dumps(analysis, indent=2))
