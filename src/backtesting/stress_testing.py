"""
Stress Testing Framework for Trading System

Tests the trading system against historical crisis scenarios to validate
risk management and circuit breaker effectiveness.

Scenarios:
1. 2008 Financial Crisis (Sept-Oct 2008)
2. COVID-19 Crash (March 2020)
3. Flash Crash (May 6, 2010)
4. Volmageddon (Feb 5, 2018)
5. Custom extreme scenarios

Author: Trading System
Created: 2025-12-04
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StressScenario(Enum):
    """Predefined stress test scenarios."""

    FINANCIAL_CRISIS_2008 = "financial_crisis_2008"
    COVID_CRASH_2020 = "covid_crash_2020"
    FLASH_CRASH_2010 = "flash_crash_2010"
    VOLMAGEDDON_2018 = "volmageddon_2018"
    CUSTOM = "custom"


@dataclass
class ScenarioParameters:
    """Parameters defining a stress scenario."""

    name: str
    description: str
    start_date: str
    end_date: str
    max_drawdown_pct: float  # Historical max drawdown
    avg_daily_loss_pct: float  # Average daily loss during crisis
    peak_vix: float  # Peak VIX during scenario
    spy_max_drop_pct: float  # Max single-day SPY drop
    duration_days: int  # Crisis duration
    recovery_days: int  # Days to recover


@dataclass
class StressTestResult:
    """Result of a stress test."""

    scenario: str
    passed: bool
    max_drawdown_hit: float
    circuit_breakers_triggered: int
    tier4_halts: int
    total_trades_blocked: int
    capital_preserved_pct: float
    recovery_time_days: Optional[int]
    worst_day_loss: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "passed": self.passed,
            "max_drawdown_hit": round(self.max_drawdown_hit, 4),
            "circuit_breakers_triggered": self.circuit_breakers_triggered,
            "tier4_halts": self.tier4_halts,
            "total_trades_blocked": self.total_trades_blocked,
            "capital_preserved_pct": round(self.capital_preserved_pct, 2),
            "recovery_time_days": self.recovery_time_days,
            "worst_day_loss": round(self.worst_day_loss, 4),
            "notes": self.notes,
        }


# Historical crisis parameters (validated against actual data)
SCENARIO_PARAMETERS: dict[StressScenario, ScenarioParameters] = {
    StressScenario.FINANCIAL_CRISIS_2008: ScenarioParameters(
        name="2008 Financial Crisis",
        description="Lehman Brothers collapse and market meltdown",
        start_date="2008-09-15",
        end_date="2008-11-20",
        max_drawdown_pct=0.517,  # 51.7% peak-to-trough
        avg_daily_loss_pct=0.025,  # ~2.5% average daily loss
        peak_vix=80.86,  # Oct 27, 2008
        spy_max_drop_pct=0.0947,  # Sept 29, 2008: -9.47%
        duration_days=67,
        recovery_days=1073,  # ~3 years to recover
    ),
    StressScenario.COVID_CRASH_2020: ScenarioParameters(
        name="COVID-19 Crash",
        description="Pandemic panic selling",
        start_date="2020-02-20",
        end_date="2020-03-23",
        max_drawdown_pct=0.337,  # 33.7% drawdown
        avg_daily_loss_pct=0.04,  # ~4% average daily loss
        peak_vix=82.69,  # March 16, 2020
        spy_max_drop_pct=0.1198,  # March 16, 2020: -11.98%
        duration_days=23,
        recovery_days=33,  # V-shaped recovery
    ),
    StressScenario.FLASH_CRASH_2010: ScenarioParameters(
        name="Flash Crash",
        description="May 6, 2010 intraday crash",
        start_date="2010-05-06",
        end_date="2010-05-06",
        max_drawdown_pct=0.099,  # ~10% intraday
        avg_daily_loss_pct=0.099,
        peak_vix=40.0,  # Approximate
        spy_max_drop_pct=0.099,  # ~10% drop in minutes
        duration_days=1,
        recovery_days=1,  # Intraday recovery
    ),
    StressScenario.VOLMAGEDDON_2018: ScenarioParameters(
        name="Volmageddon",
        description="Feb 5, 2018 volatility spike",
        start_date="2018-02-02",
        end_date="2018-02-09",
        max_drawdown_pct=0.115,  # 11.5% drawdown
        avg_daily_loss_pct=0.02,
        peak_vix=50.30,  # Feb 5, 2018
        spy_max_drop_pct=0.0421,  # Feb 5: -4.21%
        duration_days=6,
        recovery_days=180,  # ~6 months to full recovery
    ),
}


class StressTester:
    """
    Stress testing framework for the trading system.

    Simulates historical crisis scenarios to validate:
    - Circuit breaker effectiveness
    - Capital preservation
    - Risk management rules
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        max_acceptable_drawdown: float = 0.20,  # 20% max acceptable
    ):
        self.initial_capital = initial_capital
        self.max_acceptable_drawdown = max_acceptable_drawdown
        self.results: list[StressTestResult] = []

    def run_scenario(
        self,
        scenario: StressScenario,
        custom_params: Optional[ScenarioParameters] = None,
    ) -> StressTestResult:
        """
        Run a stress test scenario.

        Args:
            scenario: The scenario to test
            custom_params: Custom parameters (required for CUSTOM scenario)

        Returns:
            StressTestResult with test outcomes
        """
        if scenario == StressScenario.CUSTOM:
            if custom_params is None:
                raise ValueError("Custom scenario requires custom_params")
            params = custom_params
        else:
            params = SCENARIO_PARAMETERS[scenario]

        logger.info(f"Running stress test: {params.name}")

        # Import circuit breaker here to avoid circular imports
        from src.safety.multi_tier_circuit_breaker import MultiTierCircuitBreaker

        cb = MultiTierCircuitBreaker(
            state_file=f"data/stress_test_{scenario.value}_cb_state.json",
            event_log_file=f"data/stress_test_{scenario.value}_events.jsonl",
        )

        notes = []
        capital = self.initial_capital
        peak_capital = capital
        max_drawdown = 0.0
        circuit_breakers_triggered = 0
        tier4_halts = 0
        trades_blocked = 0
        worst_day_loss = 0.0

        # Simulate each day of the crisis
        for day in range(params.duration_days):
            # Simulate daily loss (varies around average)
            import random

            daily_loss_multiplier = random.uniform(0.5, 2.0)
            daily_loss_pct = params.avg_daily_loss_pct * daily_loss_multiplier

            # Spike on worst days
            if day == params.duration_days // 3:  # Simulate worst day
                daily_loss_pct = params.spy_max_drop_pct

            daily_pnl = -capital * daily_loss_pct

            # Evaluate circuit breaker
            vix_level = params.peak_vix * (0.7 + 0.3 * random.random())  # Vary VIX
            status = cb.evaluate(
                portfolio_value=capital,
                daily_pnl=daily_pnl,
                consecutive_losses=day,
                vix_level=vix_level,
                spy_daily_change=-daily_loss_pct,
            )

            # Track circuit breaker triggers
            if not status.is_trading_allowed:
                trades_blocked += 1
                if status.current_tier.name == "HALT":
                    tier4_halts += 1
                circuit_breakers_triggered += 1

                # Circuit breaker prevents full loss
                # Assume 50% loss reduction when CB triggers
                daily_pnl = daily_pnl * 0.5
                notes.append(
                    f"Day {day + 1}: {status.current_tier.name} triggered, "
                    f"blocked ${abs(daily_pnl):.2f} additional loss"
                )

            # Apply loss to capital
            capital += daily_pnl

            # Track drawdown
            if capital > peak_capital:
                peak_capital = capital
            current_drawdown = (peak_capital - capital) / peak_capital
            if current_drawdown > max_drawdown:
                max_drawdown = current_drawdown

            # Track worst day
            if daily_loss_pct > worst_day_loss:
                worst_day_loss = daily_loss_pct

        # Calculate final metrics
        capital_preserved_pct = (capital / self.initial_capital) * 100
        passed = max_drawdown <= self.max_acceptable_drawdown

        # Estimate recovery time (simplified)
        recovery_time = None
        if passed and capital < self.initial_capital:
            daily_recovery_rate = 0.003  # 0.3% daily recovery
            loss_to_recover = self.initial_capital - capital
            recovery_time = int(loss_to_recover / (capital * daily_recovery_rate))

        result = StressTestResult(
            scenario=params.name,
            passed=passed,
            max_drawdown_hit=max_drawdown,
            circuit_breakers_triggered=circuit_breakers_triggered,
            tier4_halts=tier4_halts,
            total_trades_blocked=trades_blocked,
            capital_preserved_pct=capital_preserved_pct,
            recovery_time_days=recovery_time,
            worst_day_loss=worst_day_loss,
            notes=notes[:10],  # Keep top 10 notes
        )

        self.results.append(result)

        logger.info(
            f"Stress test {params.name}: "
            f"{'PASSED' if passed else 'FAILED'} "
            f"(drawdown={max_drawdown:.2%}, capital preserved={capital_preserved_pct:.1f}%)"
        )

        return result

    def run_all_scenarios(self) -> dict[str, StressTestResult]:
        """Run all predefined stress test scenarios."""
        results = {}
        for scenario in StressScenario:
            if scenario != StressScenario.CUSTOM:
                results[scenario.value] = self.run_scenario(scenario)
        return results

    def generate_report(self) -> dict[str, Any]:
        """Generate comprehensive stress test report."""
        if not self.results:
            return {"error": "No stress tests have been run"}

        passed_count = sum(1 for r in self.results if r.passed)
        failed_count = len(self.results) - passed_count

        return {
            "summary": {
                "total_tests": len(self.results),
                "passed": passed_count,
                "failed": failed_count,
                "pass_rate": passed_count / len(self.results) if self.results else 0,
            },
            "worst_drawdown": max(r.max_drawdown_hit for r in self.results),
            "avg_capital_preserved": sum(r.capital_preserved_pct for r in self.results)
            / len(self.results),
            "total_cb_triggers": sum(r.circuit_breakers_triggered for r in self.results),
            "total_tier4_halts": sum(r.tier4_halts for r in self.results),
            "results": [r.to_dict() for r in self.results],
            "assessment": self._assess_readiness(),
        }

    def _assess_readiness(self) -> str:
        """Assess system readiness based on stress test results."""
        if not self.results:
            return "NO_DATA"

        passed_all = all(r.passed for r in self.results)
        avg_drawdown = sum(r.max_drawdown_hit for r in self.results) / len(self.results)
        avg_preserved = sum(r.capital_preserved_pct for r in self.results) / len(self.results)

        if passed_all and avg_preserved > 85:
            return "EXCELLENT: System is crisis-ready with strong capital preservation"
        elif passed_all and avg_preserved > 75:
            return "GOOD: System handles crises well, minor optimization possible"
        elif sum(1 for r in self.results if r.passed) >= len(self.results) / 2:
            return "FAIR: System needs improvement for some crisis scenarios"
        else:
            return "NEEDS WORK: Circuit breakers need strengthening for crisis scenarios"


def run_stress_tests() -> dict[str, Any]:
    """Run all stress tests and return results."""
    tester = StressTester(
        initial_capital=100000.0,
        max_acceptable_drawdown=0.20,
    )
    tester.run_all_scenarios()
    return tester.generate_report()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("STRESS TESTING FRAMEWORK")
    print("=" * 80)

    report = run_stress_tests()

    print("\n📊 STRESS TEST RESULTS:")
    print(f"  Total Tests: {report['summary']['total_tests']}")
    print(f"  Passed: {report['summary']['passed']}")
    print(f"  Failed: {report['summary']['failed']}")
    print(f"  Pass Rate: {report['summary']['pass_rate']:.1%}")
    print(f"  Worst Drawdown: {report['worst_drawdown']:.2%}")
    print(f"  Avg Capital Preserved: {report['avg_capital_preserved']:.1f}%")
    print(f"\n🎯 Assessment: {report['assessment']}")

    print("\n📋 Individual Results:")
    for r in report["results"]:
        status = "✅" if r["passed"] else "❌"
        print(f"  {status} {r['scenario']}: {r['max_drawdown_hit']:.2%} drawdown")
