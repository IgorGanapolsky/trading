from src.testing.chaos_simulator import (
    DeterministicChaosSimulator,
    FaultType,
    SystemInvariantChecker,
    SimulationState,
)


def test_system_invariant_checker_clean_state():
    checker = SystemInvariantChecker()
    state = SimulationState(
        step_index=1,
        cash_balance=10000.0,
        account_drawdown_pct=0.01,
        open_leg_count=4,
        rl_quarantined=True,
        delta=0.15,
    )
    violations = checker.check_invariants(state, seed=42, fault=None)
    assert len(violations) == 0


def test_system_invariant_checker_drawdown_and_hedge_violations():
    checker = SystemInvariantChecker()
    state = SimulationState(
        step_index=5,
        cash_balance=10000.0,
        account_drawdown_pct=0.06,  # > 5% violation
        open_leg_count=2,  # != 0 or 4 violation
        rl_quarantined=True,
        delta=0.20,  # > 0.15 violation
    )
    violations = checker.check_invariants(state, seed=42, fault=FaultType.CIRCUIT_BREAKER_STORM)
    assert len(violations) == 3
    names = [v.invariant_name for v in violations]
    assert "DRAWDOWN_LIMIT_5_PCT" in names
    assert "IRON_CONDOR_4_LEG_HEDGE" in names
    assert "DELTA_LIMIT_15" in names


def test_deterministic_chaos_simulator_reproducibility():
    sim1 = DeterministicChaosSimulator(seed=12345)
    report1 = sim1.run_simulation(steps=50, fault_rate=0.20)

    sim2 = DeterministicChaosSimulator(seed=12345)
    report2 = sim2.run_simulation(steps=50, fault_rate=0.20)

    # Deterministic replay proof: exact same faults & violations
    assert report1["faults_injected_count"] == report2["faults_injected_count"]
    assert report1["invariant_violations_count"] == report2["invariant_violations_count"]
    assert report1["violations"] == report2["violations"]
