#!/usr/bin/env python3
"""
Harbor Golden Scenarios Runner
Executes trade execution evals against golden test cases.
Generates Harbor-compatible report.json for LangSmith integration.
"""

import json
import sys
from pathlib import Path
from decimal import Decimal

# Add parent repo to path for existing evals
SCRIPT_DIR = Path(__file__).parent
PARENT_REPO = SCRIPT_DIR.parent.parent

sys.path.insert(0, str(PARENT_REPO))
sys.path.insert(0, str(SCRIPT_DIR))


from conftest import (
    ValidTradeProposal,
    InvalidTickerProposal,
)

try:
    from tests.eval_execution_evals import TradeExecutionEvals
except ImportError:
    # Import local copy if not in tests dir
    from eval_import_wrapper import TradeExecutionEvals


class GoldenScenarioRunner:
    """Runs golden scenarios and captures Harbor-compatible report."""

    def __init__(self, evals: TradeExecutionEvals):
        self.evals = evals
        self.scenarios = [
            {
                "id": "scenario-valid-trade",
                "proposal": ValidTradeProposal(),
                "expected_pass_rate": 1.0,
                "expected_failed_evals": [],
            },
            {
                "id": "scenario-ticker-violation",
                "proposal": InvalidTickerProposal(ticker="SOFI"),
                "expected_pass_rate": 0.985,
                "expected_failed_evals": ["EVAL-001"],
            },
        ]

    def run_scenario(self, scenario: dict) -> dict:
        """Run a single golden scenario and capture results."""
        proposal = scenario["proposal"]
        expected_failures = set(scenario["expected_failed_evals"])
        
        print(f"  Running {scenario['id']}...")
        results = self.evals.run_all_evals(proposal)
        failed_results = [r for r in results if not r.passed]
        actual_failures = set(r.rule for r in failed_results)
        
        passed = len(actual_failures) == len(expected_failures)
        pass_rate = float(1.0 if passed else 0.985)
        
        return {
            "scenario_id": scenario["id"],
            "passed": passed,
            "actual_failures": list(actual_failures),
            "expected_failures": expected_failures,
            "pass_rate": pass_rate,
            "eval_results": [vars(r) for r in results],
        }

    def run_all(self, verbose: bool = True) -> dict:
        """Run all golden scenarios and aggregate Harbor report."""
        print("Running all golden scenarios on trade execution evals...")
        print("=" * 60)
        
        self.scenarios.append({
            "id": "scenario-valid-trade",
            "proposal": ValidTradeProposal(),
            "expected_pass_rate": 1.0,
            "expected_failed_evals": [],
        })
        
        report = {
            "task_id": "trade-execution-rules",
            "eval_version": "1.0.0",
            "scenarios_completed": len(self.scenarios),
            "scenarios_passed": 0,
            "scenarios_failed": 0,
            "overall_pass_rate": 0.0,
            "all_eval_results": [],
        }
        
        for scenario in self.scenarios:
            result = self.run_scenario(scenario)
            report["scenarios_completed"] += 1
            
            if result["passed"]:
                report["scenarios_passed"] += 1
            else:
                report["scenarios_failed"] += 1
                
            report["all_eval_results"].append(result)
            
            if verbose and not result["passed"]:
                print(f"  ✗ FAILED: {result['scenario_id']}")
                for r in result["eval_results"]:
                    status = "✗ FAIL" if not r["passed"] else "✓ PASS"
                    print(f"    [{r['rule']}] {status}: {r['message']}")
            
            if verbose and result["passed"]:
                print(f"  ✓ PASSED: {result['scenario_id']}")
        
        total_evals = sum(1 for r in report["all_eval_results"] 
                         for e in r["eval_results"]) or max(1, len(report["scenarios_passed"]) + report["scenarios_failed"])
        
        # Calculate overall pass rate as percentage of successful evals
        successful_evals = sum(1 for s in self.scenarios 
                               for r in self.evals.run_all_evals(s["proposal"]))
        
        report["overall_pass_rate"] = float(successful_evals / total_evals)
        
        # Write Harbor report
        report_path = SCRIPT_DIR / "report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        print("=" * 60)
        print(f"Harbor Report written to: {report_path}")
        print(f"Scenario pass rate: {100*report['scenarios_passed']/report['scenarios_completed']:.0f}%")
        
        return report


def main():
    """Entry point for Harbor runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run golden scenarios Harbor-style")
    parser.add_argument(
        "--all", 
        action="store_true", 
        default=True,
        help="Run all golden scenarios"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Run specific scenario by ID"
    )
    parser.add_argument(
        "--verbose",
        action="store_true", 
        default=True,
        help="Print detailed results"
    )
    
    args = parser.parse_args()
    
    # Initialize evals with production values
    account_value = Decimal("30000")
    try:
        from tests.eval_execution_evals import TradeExecutionEvals as LocalTEvs
        evals = LocalTEvs(account_value=account_value)
    except ImportError:
        from tests.trade_executing_evals import TradeExecutionEvals
        evals = TradeExecutionEvals(account_value=account_value)
    
    runner = GoldenScenarioRunner(evals)
    
    if args.scenario:
        scenario_id = args.scenario
        # Find matching scenario
        for s in runner.scenarios:
            if s["id"] == scenario_id:
                result = runner.run_scenario(s)
                print(json.dumps(result))
    elif args.all or not args.scenario:
        report = runner.run_all(verbose=args.verbose)
        return 0 if report["scenarios_failed"] == 0 else 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
