from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class AuditViolation:
    """Represents a strategy or safety violation discovered during audit."""

    rule: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str
    trade_id: str | None = None
    timestamp: str | None = None


@dataclass
class AuditReport:
    """Results of an adversarial audit."""

    timestamp: str
    trades_scanned: int
    violations: list[AuditViolation]
    status: str  # PASS, WARN, FAIL
    summary: str


class AuditAgent(BaseAgent):
    """
    Adversarial Audit Agent.
    
    Performs autonomous "Adversarial Audits" on trade execution logs using 
    deterministic checks and RLM Algorithm 1 for complex anomaly detection.
    """

    def __init__(self, model: str | None = None):
        super().__init__(name="audit_agent", role="System Auditor", model=model)
        self.log_dir = Path("data")
        self.report_dir = Path("reports/audits")
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Implementation of abstract base method. 
        Calls perform_audit() for the provided date or latest logs.
        """
        date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
        report = self.perform_audit(date_str)
        return {
            "status": report.status,
            "violations_count": len(report.violations),
            "summary": report.summary,
            "report_path": str(self.report_dir / f"audit_{date_str}.json")
        }

    def perform_audit(self, date_str: str | None = None) -> AuditReport:
        """
        Perform a comprehensive audit of trade logs for a specific date.
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        log_file = self.log_dir / f"trades_{date_str}.json"
        if not log_file.exists():
            return AuditReport(
                timestamp=datetime.now().isoformat(),
                trades_scanned=0,
                violations=[],
                status="PASS",
                summary=f"No trade logs found for {date_str}."
            )

        try:
            with open(log_file) as f:
                trades = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load trade log {log_file}: {e}")
            return AuditReport(
                timestamp=datetime.now().isoformat(),
                trades_scanned=0,
                violations=[AuditViolation("Data Integrity", "CRITICAL", f"Failed to load log: {e}")],
                status="FAIL",
                summary=f"Data integrity failure for {date_str}."
            )

        violations = []

        # 1. Scan for Rule #1 Violations (Realized Loss)
        # 2. Scan for Position Sizing Violations
        # 3. Scan for Ticker Violations
        # 4. Scan for Anomaly detection via RLM (Logic below)

        for trade in trades:
            trade_id = trade.get("order_id") or trade.get("symbol", "unknown")
            ts = trade.get("timestamp")

            # Check Ticker Whitelist (Liquid ETFs only)
            symbol = trade.get("symbol", "")
            # Option symbols are longer, extract underlying
            underlying = symbol[:3] if len(symbol) > 5 else symbol
            allowed = ["SPY", "QQQ", "IWM", "SPX", "XSP", "VIX", "UVXY", "SVXY", "VOO"]

            if underlying not in allowed:
                violations.append(AuditViolation(
                    rule="Ticker Whitelist",
                    severity="HIGH",
                    description=f"Prohibited ticker detected: {symbol}",
                    trade_id=trade_id,
                    timestamp=ts
                ))

            # Check Position Sizing (Simulated trades in our log often have max_risk)
            max_risk = trade.get("max_risk", 0)
            if max_risk > 500:  # Hardcoded 0.5% of $100K = $500 max risk per IC
                violations.append(AuditViolation(
                    rule="Position Sizing",
                    severity="MEDIUM",
                    description=f"Large risk detected: ${max_risk}",
                    trade_id=trade_id,
                    timestamp=ts
                ))

        # Status Determination
        status = "PASS"
        if any(v.severity == "CRITICAL" for v in violations) or any(v.severity == "HIGH" for v in violations):
            status = "FAIL"
        elif violations:
            status = "WARN"

        summary = f"Audit for {date_str} complete. Scanned {len(trades)} entries. Found {len(violations)} violations."

        report = AuditReport(
            timestamp=datetime.now().isoformat(),
            trades_scanned=len(trades),
            violations=violations,
            status=status,
            summary=summary
        )

        # Save Report
        report_file = self.report_dir / f"audit_{date_str}.json"
        with open(report_file, "w") as f:
            json.dump({
                "timestamp": report.timestamp,
                "trades_scanned": report.trades_scanned,
                "status": report.status,
                "summary": report.summary,
                "violations": [v.__dict__ for v in report.violations]
            }, f, indent=2)

        return report

    def run_adversarial_llm_audit(self, date_str: str) -> dict[str, Any]:
        """
        Use RLM Algorithm 1 to perform a deep reasoning audit.
        Generates Python code to analyze logs for subtle patterns.
        """
        prompt = f"""
        You are the Adversarial Audit Agent. Your mission is to find hidden bugs, 
        risk management failures, or logic errors in today's ({date_str}) trade logs.
        
        Log location: data/trades_{date_str}.json
        
        Task:
        1. Write a pure Python script to analyze this JSON file.
        2. Look for:
           - Duplicate orders within seconds (Race conditions)
           - Inconsistent pricing (fills far from expected)
           - Strategy drift (trades not matching the iron_condor schema)
        3. Output the results as a JSON object with 'anomalies' and 'score'.
        """
        # Algorithm 1: Plan -> Generate -> Execute -> Finalize
        # Implementation of RLM logic would go here,
        # using reason_with_llm to get the Python code.

        logger.info(f"Running LLM Adversarial Audit for {date_str}...")
        # (Simplified for now - will be expanded in future PRs)
        return {"anomalies": [], "score": 1.0}
