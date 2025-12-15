# QAOA for Portfolio Optimization

## Overview

Quantum Approximate Optimization Algorithm (QAOA) is a hybrid quantum-classical algorithm designed to solve combinatorial optimization problems. It's particularly well-suited for portfolio optimization with discrete constraints.

## Problem Formulation

### Classical Portfolio Optimization

Standard Markowitz mean-variance optimization:

```
maximize: μᵀw - λwᵀΣw
subject to: Σwᵢ = 1
           wᵢ ≥ 0
```

Where:
- w = portfolio weights
- μ = expected returns
- Σ = covariance matrix
- λ = risk aversion parameter

### Quantum Formulation (QUBO)

Convert to Quadratic Unconstrained Binary Optimization:

```
minimize: Σᵢⱼ Qᵢⱼ xᵢxⱼ
```

Where:
- xᵢ ∈ {0, 1} represents asset selection
- Q encodes returns, covariances, and constraints

## QAOA Algorithm Structure

### 1. Problem Hamiltonian

Encode the objective function as a quantum Hamiltonian:

```
H_C = Σᵢⱼ Qᵢⱼ ZᵢZⱼ
```

Where Zᵢ are Pauli-Z operators on qubits.

### 2. Mixer Hamiltonian

Apply quantum mixing to explore solution space:

```
H_M = Σᵢ Xᵢ
```

Where Xᵢ are Pauli-X operators.

### 3. QAOA Circuit

Alternate between problem and mixer layers:

```
|ψ(γ,β)⟩ = e^(-iβₚH_M) e^(-iγₚH_C) ... e^(-iβ₁H_M) e^(-iγ₁H_C) |+⟩^⊗n
```

Parameters γ and β are optimized classically.

### 4. Classical Optimization

Use classical optimizer (COBYLA, SPSA) to tune γ and β to minimize:

```
⟨ψ(γ,β)|H_C|ψ(γ,β)⟩
```

## Implementation Steps

### Step 1: Convert Portfolio Problem to QUBO

```python
import numpy as np
from qiskit_optimization.applications import PortfolioOptimization

# Example: 5 assets
n_assets = 5
returns = np.array([0.05, 0.08, 0.06, 0.09, 0.07])  # Expected returns
cov_matrix = np.array([...])  # Covariance matrix
risk_factor = 0.5  # Risk aversion
budget = 1000  # Total investment

# Create QUBO problem
portfolio = PortfolioOptimization(
    expected_returns=returns,
    covariances=cov_matrix,
    risk_factor=risk_factor,
    budget=budget
)
qubo = portfolio.to_quadratic_program()
```

### Step 2: Build QAOA Circuit

```python
from qiskit.algorithms.optimizers import COBYLA
from qiskit.algorithms import QAOA
from qiskit.primitives import Sampler

# Set QAOA parameters
p = 3  # Number of QAOA layers
optimizer = COBYLA(maxiter=100)
sampler = Sampler()

# Create QAOA instance
qaoa = QAOA(sampler=sampler, optimizer=optimizer, reps=p)
```

### Step 3: Solve and Extract Solution

```python
# Run QAOA
result = qaoa.compute_minimum_eigenvalue(qubo)

# Extract optimal portfolio
optimal_weights = portfolio.interpret(result)
print(f"Optimal portfolio: {optimal_weights}")
print(f"Expected return: {result.eigenvalue}")
```

### Step 4: Compare with Classical

```python
from scipy.optimize import minimize

def classical_portfolio(returns, cov, risk_factor):
    n = len(returns)
    
    def objective(w):
        return -(returns @ w - risk_factor * w @ cov @ w)
    
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1})
    bounds = tuple((0, 1) for _ in range(n))
    w0 = np.ones(n) / n
    
    result = minimize(objective, w0, method='SLSQP', 
                     bounds=bounds, constraints=constraints)
    return result.x

classical_weights = classical_portfolio(returns, cov_matrix, risk_factor)
print(f"Classical solution: {classical_weights}")
```

## Practical Considerations

### Current Limitations

1. **Qubit count**: n assets requires n qubits minimum
   - IBM Quantum: Up to 127 qubits (127 assets max)
   - Practical limit with noise: ~20-30 assets

2. **Circuit depth**: Deeper circuits → more noise
   - p=1: Shallow, fast, less accurate
   - p=3-5: Good balance
   - p>10: Too noisy on current hardware

3. **Optimization landscape**: 2p parameters to optimize
   - Classical optimization can get stuck in local minima
   - Multiple runs with random initialization recommended

### Best Practices

1. **Start small**: Test on 5-10 assets first
2. **Use simulation**: Debug on classical simulator before hardware
3. **Warm start**: Initialize γ, β from previous solutions
4. **Multiple shots**: Run circuit 1000-10000 times for statistics
5. **Error mitigation**: Use readout error correction

## Advanced Techniques

### 1. Recursive QAOA

For large portfolios (>30 assets):

```python
# Solve in stages
stage1_assets = assets[:30]  # First 30 assets
stage1_solution = qaoa.solve(stage1_assets)

# Refine with remaining assets
stage2_assets = stage1_solution.top_10 + assets[30:]
final_solution = qaoa.solve(stage2_assets)
```

### 2. Warm-Start QAOA (WS-QAOA)

Use classical solution to initialize quantum state:

```python
# Get classical solution
classical_solution = classical_portfolio(returns, cov_matrix, risk_factor)

# Initialize QAOA with classical state
qaoa_ws = QAOA(initial_state=classical_solution, ...)
result = qaoa_ws.compute_minimum_eigenvalue(qubo)
```

### 3. Multi-Angle QAOA (ma-QAOA)

Different angles for each qubit:

```python
# Instead of p pairs of angles, use n*p angles
# Better optimization landscape but more parameters
```

## Integration with Trading System

### Use Case 1: Daily Rebalancing

```python
# After market close, determine optimal portfolio for tomorrow
current_positions = get_current_positions()
target_positions = qaoa_portfolio_optimizer(
    assets=watchlist,
    current=current_positions,
    returns=predicted_returns,
    risk_factor=0.5
)
rebalance_orders = calculate_rebalance(current_positions, target_positions)
```

### Use Case 2: Constrained Optimization

```python
# Add real-world constraints
constraints = {
    'sector_limits': {'tech': 0.3, 'finance': 0.2},
    'min_position': 0.02,  # At least 2% per position
    'max_position': 0.15,  # At most 15% per position
    'turnover_limit': 0.1  # Max 10% portfolio turnover
}

optimal_portfolio = qaoa_with_constraints(
    assets=watchlist,
    constraints=constraints,
    returns=predicted_returns,
    cov_matrix=estimated_cov
)
```

### Use Case 3: Multi-Period Optimization

```python
# Optimize over multiple periods
horizons = [1, 5, 20]  # days
weights = [0.5, 0.3, 0.2]

portfolio = []
for h, w in zip(horizons, weights):
    returns_h = forecast_returns(horizon=h)
    portfolio_h = qaoa_optimize(returns_h)
    portfolio.append(portfolio_h * w)

final_portfolio = sum(portfolio)
```

## Performance Benchmarks

### Theoretical Advantage

- Classical quadratic programming: O(n³)
- QAOA (ideal): O(poly(n)) 
- Advantage appears around n > 100 assets

### Current Reality (2025)

- n < 20: Classical faster and more accurate
- n = 20-50: Comparable performance
- n > 50: Quantum advantage possible but noisy
- n > 100: Need error correction (not available yet)

### Reported Results

- **IBM (2020)**: 3-qubit problem solved with 99% accuracy
- **Goldman Sachs (2021)**: 50-asset portfolio on quantum simulator
- **JP Morgan (2022)**: D-Wave annealing for 100-asset portfolio
- **D-Wave (2023)**: 1000+ variable portfolio optimization

## When to Use QAOA vs Classical

### Use QAOA When:
✅ Many discrete constraints (sector limits, lot sizes)
✅ Non-convex objective function
✅ Large solution space (many assets)
✅ Research/experimentation goal

### Use Classical When:
✅ Small portfolio (<20 assets)
✅ Convex objective (standard Markowitz)
✅ Real-time decisions needed (milliseconds)
✅ Production system requiring stability

## Resources

### Code Examples
- IBM Qiskit Finance tutorials: https://qiskit.org/ecosystem/finance/
- D-Wave Ocean examples: https://github.com/dwave-examples/portfolio-optimization

### Papers
- "Quantum Approximate Optimization of Non-Planar Graph Problems" (Farhi et al., 2017)
- "Improving Variational Quantum Optimization using CVaR" (Barkoutsos et al., 2019)
- "Quantum optimization using variational algorithms on near-term quantum devices" (Cerezo et al., 2021)

### Tutorials
- Qiskit Finance: Portfolio Optimization - https://qiskit.org/ecosystem/finance/tutorials/01_portfolio_optimization.html
- PennyLane: QAOA - https://pennylane.ai/qml/demos/tutorial_qaoa_intro.html

## Next Steps

1. **Set up Qiskit Finance**: `pip install qiskit-finance`
2. **Run tutorial notebook**: Try 5-asset portfolio example
3. **Test on IBM Quantum**: Get free access at quantum-computing.ibm.com
4. **Benchmark vs classical**: Compare with scipy.optimize
5. **Integrate with backtester**: Test on historical data

---

**Complexity**: Advanced (requires quantum computing basics)
**Time to implement**: 2-4 weeks
**Production readiness**: Research/experimentation only (2025)
**Expected value**: Medium (2025) → High (2027+)
