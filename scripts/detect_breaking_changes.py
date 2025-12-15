#!/usr/bin/env python3
"""
BREAKING CHANGE DETECTOR
========================
Monitors main branch and alerts immediately if breaking changes detected.

Runs hourly during trading hours to catch issues FAST.

Usage:
    python3 scripts/detect_breaking_changes.py
    
Exit codes:
    0 = No breaking changes detected
    1 = BREAKING CHANGES DETECTED (alert!)
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Dict


class BreakingChangeDetector:
    """Detect and alert on breaking changes to trading operations."""
    
    CRITICAL_FILES = [
        "src/orchestrator/main.py",
        "src/safety/circuit_breaker.py",
        "src/safety/risk_manager.py",
        "src/strategies/base.py",
        "data/system_state.json",
    ]
    
    def __init__(self):
        self.workspace = Path(__file__).parent.parent
        self.issues: List[Dict] = []
        
    def check_recent_commits(self, num_commits: int = 5) -> bool:
        """Check recent commits for breaking changes."""
        print(f"🔍 CHECKING LAST {num_commits} COMMITS")
        print("=" * 60)
        
        # Get recent commits
        result = subprocess.run(
            ["git", "log", f"-{num_commits}", "--oneline"],
            capture_output=True,
            text=True,
            cwd=self.workspace
        )
        
        print("\nRecent commits:")
        print(result.stdout)
        print()
        
        # Check each critical file
        all_ok = True
        for file in self.CRITICAL_FILES:
            if not self.check_file_integrity(file):
                all_ok = False
        
        # Try to import trading orchestrator
        print("\n🧪 Testing TradingOrchestrator import...")
        if not self.test_trading_import():
            all_ok = False
        
        return all_ok
    
    def check_file_integrity(self, file_path: str) -> bool:
        """Check if a critical file is intact."""
        full_path = self.workspace / file_path
        
        # Check existence
        if not full_path.exists():
            self.issues.append({
                "severity": "CRITICAL",
                "file": file_path,
                "issue": "File missing!"
            })
            print(f"❌ CRITICAL: {file_path} is MISSING")
            return False
        
        # Check syntax for Python files
        if file_path.endswith('.py'):
            try:
                with open(full_path) as f:
                    import ast
                    ast.parse(f.read(), filename=str(full_path))
                print(f"✅ {file_path} - OK")
                return True
            except SyntaxError as e:
                self.issues.append({
                    "severity": "CRITICAL",
                    "file": file_path,
                    "issue": f"Syntax error: {e}"
                })
                print(f"❌ CRITICAL: {file_path} - SYNTAX ERROR")
                return False
        
        # Check JSON validity
        if file_path.endswith('.json'):
            try:
                import json
                with open(full_path) as f:
                    json.load(f)
                print(f"✅ {file_path} - OK")
                return True
            except json.JSONDecodeError as e:
                self.issues.append({
                    "severity": "CRITICAL",
                    "file": file_path,
                    "issue": f"Invalid JSON: {e}"
                })
                print(f"❌ CRITICAL: {file_path} - INVALID JSON")
                return False
        
        print(f"✅ {file_path} - exists")
        return True
    
    def test_trading_import(self) -> bool:
        """Test if TradingOrchestrator can be imported."""
        result = subprocess.run(
            [
                sys.executable, "-c",
                "from src.orchestrator.main import TradingOrchestrator; "
                "print('OK')"
            ],
            capture_output=True,
            text=True,
            cwd=self.workspace
        )
        
        if result.returncode != 0:
            self.issues.append({
                "severity": "CRITICAL",
                "file": "src/orchestrator/main.py",
                "issue": f"Cannot import TradingOrchestrator"
            })
            print(f"❌ CRITICAL: TradingOrchestrator import FAILED")
            return False
        
        print("✅ TradingOrchestrator import - OK")
        return True
    
    def generate_alert(self) -> str:
        """Generate alert message."""
        alert = "🚨 BREAKING CHANGES DETECTED 🚨\n\n"
        alert += f"Found {len(self.issues)} critical issues:\n\n"
        
        for issue in self.issues:
            alert += f"• [{issue['severity']}] {issue['file']}\n"
            alert += f"  {issue['issue']}\n\n"
        
        alert += "⚠️  TRADING OPERATIONS MAY BE BROKEN!\n"
        alert += "🔧 Fix immediately or revert breaking commit.\n"
        
        return alert
    
    def run(self) -> bool:
        """Run breaking change detection."""
        all_ok = self.check_recent_commits()
        
        print("\n" + "=" * 60)
        if all_ok:
            print("✅ NO BREAKING CHANGES DETECTED")
            print("Trading operations are functional.")
            return True
        else:
            print("❌ BREAKING CHANGES DETECTED!")
            print("\n" + self.generate_alert())
            return False


def main():
    """Run detection."""
    detector = BreakingChangeDetector()
    
    if detector.run():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
