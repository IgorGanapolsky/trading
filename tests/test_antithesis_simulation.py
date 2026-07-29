"""Unit tests for Antithesis-style Deterministic Simulation Testing (DST)."""

from __future__ import annotations

from src.testing.antithesis_simulation import (
    DeterministicMarketSimulator,
    SimulationConfig,
)


def test_antithesis_deterministic_simulation_1000_steps():
    """Verify 1,000 deterministic state-space simulation iterations pass all safety invariants."""
    config = SimulationConfig(seed=42, num_iterations=1000, fault_injection_rate=0.20)
    simulator = DeterministicMarketSimulator(config)
    report = simulator.run_simulation()

    assert report.success is True
    assert report.total_iterations == 1000
    assert report.faults_injected > 0
    assert report.invariants_checked > 2000
    assert len(report.failed_invariants) == 0


def test_antithesis_simulation_reproducibility():
    """Verify simulation is 100% deterministic given identical seed."""
    sim1 = DeterministicMarketSimulator(SimulationConfig(seed=123, num_iterations=100))
    sim2 = DeterministicMarketSimulator(SimulationConfig(seed=123, num_iterations=100))

    rep1 = sim1.run_simulation()
    rep2 = sim2.run_simulation()

    assert rep1.faults_injected == rep2.faults_injected
    assert rep1.invariants_passed == rep2.invariants_passed
