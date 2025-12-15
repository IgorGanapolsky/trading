# Quantum Trading Quick Start Guide

## 🚀 Week 1: Get Started in Under 2 Hours

### Step 1: Create IBM Quantum Account (5 minutes)
1. Go to https://quantum-computing.ibm.com
2. Sign up with email or GitHub
3. Access free IBM Quantum Experience
4. Get up to 127 qubits for experimentation

### Step 2: Install Qiskit (10 minutes)
```bash
# In your trading system environment
python3 -m pip install qiskit qiskit-finance qiskit-optimization

# Verify installation
python3 -c "import qiskit; print(qiskit.__version__)"
```

### Step 3: Run Your First Quantum Circuit (15 minutes)
```python
from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler

# Create a simple quantum circuit
qc = QuantumCircuit(2)
qc.h(0)  # Hadamard gate (superposition)
qc.cx(0, 1)  # CNOT gate (entanglement)
qc.measure_all()

# Run on IBM Quantum simulator
service = QiskitRuntimeService()
backend = service.backend("ibmq_qasm_simulator")
sampler = Sampler(backend)

# Execute
job = sampler.run(qc, shots=1000)
result = job.result()
print(result)
```

### Step 4: Portfolio Optimization Example (60 minutes)
```python
from qiskit_finance.applications.optimization import PortfolioOptimization
from qiskit_algorithms.optimizers import COBYLA
from qiskit_algorithms import QAOA
from qiskit.primitives import Sampler
import numpy as np

# Example: 4-asset portfolio
n_assets = 4
expected_returns = np.array([0.05, 0.08, 0.06, 0.09])
cov_matrix = np.array([
    [0.01, 0.002, 0.001, 0.003],
    [0.002, 0.02, 0.004, 0.002],
    [0.001, 0.004, 0.015, 0.001],
    [0.003, 0.002, 0.001, 0.025]
])
risk_factor = 0.5
budget = 1000

# Create portfolio optimization problem
portfolio = PortfolioOptimization(
    expected_returns=expected_returns,
    covariances=cov_matrix,
    risk_factor=risk_factor,
    budget=budget
)

# Convert to QUBO
qubo = portfolio.to_quadratic_program()

# Solve with QAOA
optimizer = COBYLA(maxiter=50)
qaoa = QAOA(sampler=Sampler(), optimizer=optimizer, reps=3)

result = qaoa.compute_minimum_eigenvalue(qubo)

# Extract solution
optimal_weights = portfolio.interpret(result)
print(f"Optimal Portfolio Allocation: {optimal_weights}")
print(f"Expected Return: {expected_returns @ optimal_weights}")
```

### Step 5: Compare with Classical (30 minutes)
```python
from scipy.optimize import minimize

def classical_portfolio_optimization(returns, cov, risk_factor):
    """Classical mean-variance optimization"""
    n = len(returns)
    
    def objective(w):
        portfolio_return = returns @ w
        portfolio_risk = w @ cov @ w
        return -(portfolio_return - risk_factor * portfolio_risk)
    
    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},  # Weights sum to 1
    ]
    bounds = tuple((0, 1) for _ in range(n))
    initial_guess = np.ones(n) / n
    
    result = minimize(
        objective, 
        initial_guess, 
        method='SLSQP',
        bounds=bounds, 
        constraints=constraints
    )
    
    return result.x

# Compare
classical_weights = classical_portfolio_optimization(
    expected_returns, 
    cov_matrix, 
    risk_factor
)

print("\nComparison:")
print(f"Quantum QAOA:  {optimal_weights}")
print(f"Classical:     {classical_weights}")
print(f"Difference:    {np.abs(optimal_weights - classical_weights).sum():.4f}")
```

## 📚 Week 2-4: Build Foundation

### Essential Concepts to Master

#### 1. Qubits and Superposition
```python
# Single qubit in superposition
qc = QuantumCircuit(1, 1)
qc.h(0)  # Apply Hadamard gate
qc.measure(0, 0)

# Result: 50% |0⟩, 50% |1⟩
```

**Trading Analogy**: Like holding multiple portfolio positions simultaneously until "measurement" (market close) collapses to actual performance.

#### 2. Entanglement
```python
# Create entangled pair
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)  # Entangle qubit 1 with qubit 0
qc.measure([0, 1], [0, 1])

# Result: Always correlated (00 or 11)
```

**Trading Analogy**: Correlated assets where measuring one gives information about the other.

#### 3. Quantum Gates
- **H (Hadamard)**: Create superposition (explore solutions)
- **X (Pauli-X)**: Bit flip (buy ↔ sell)
- **CNOT**: Create correlation (model asset relationships)
- **RY, RZ**: Rotation (continuous optimization parameters)

#### 4. Measurement
```python
# Measurement collapses quantum state
qc.measure_all()

# Run multiple times to get probability distribution
job = sampler.run(qc, shots=1000)
```

**Trading Analogy**: Running multiple backtests to estimate strategy performance distribution.

### Learning Resources (Priority Order)

1. **Qiskit Textbook** (FREE)
   - Start: https://learn.qiskit.org/course/introduction
   - Chapters 1-3: Quantum states and gates
   - Chapters 5-6: Quantum algorithms
   - Time: ~15 hours

2. **IBM Quantum Learning Paths** (FREE)
   - Basics of quantum information
   - Fundamentals of quantum algorithms
   - Quantum computing and finance
   - Time: ~20 hours

3. **YouTube Crash Course**
   - Qiskit: "Coding with Qiskit" series (2 hours)
   - MinutePhysics: "Quantum Computing" playlist (30 min)
   - PBS Space Time: "Quantum Mechanics" episodes (2 hours)

## 🔬 Week 5-8: Advanced Algorithms

### QAOA Deep Dive

#### Understanding QAOA Layers

```python
from qiskit.circuit import QuantumCircuit, Parameter

# QAOA circuit structure
p = 3  # Number of layers
n = 4  # Number of qubits (assets)

# Initialize in superposition
qc = QuantumCircuit(n)
for i in range(n):
    qc.h(i)

# QAOA layers
gamma = [Parameter(f'γ_{i}') for i in range(p)]
beta = [Parameter(f'β_{i}') for i in range(p)]

for layer in range(p):
    # Problem Hamiltonian (encode objective)
    # ... add problem-specific gates ...
    
    # Mixer Hamiltonian (explore solutions)
    for i in range(n):
        qc.rx(2 * beta[layer], i)

qc.measure_all()
```

#### Parameter Optimization

```python
from scipy.optimize import minimize

def qaoa_objective(params, qc, backend):
    """Evaluate QAOA circuit with given parameters"""
    # Bind parameters
    bound_qc = qc.assign_parameters(params)
    
    # Execute circuit
    job = backend.run(transpile(bound_qc, backend), shots=1024)
    result = job.result()
    counts = result.get_counts()
    
    # Calculate expectation value
    expectation = calculate_expectation(counts)
    return expectation

# Optimize parameters
initial_params = np.random.rand(2 * p)
result = minimize(
    qaoa_objective,
    initial_params,
    args=(qc, backend),
    method='COBYLA',
    options={'maxiter': 100}
)

optimal_params = result.x
```

### Quantum Amplitude Estimation

For option pricing with quadratic speedup:

```python
from qiskit_finance.applications import EuropeanCallPricing

# Option parameters
spot_price = 100
strike_price = 105
volatility = 0.2
risk_free_rate = 0.05
maturity = 1.0

# Create pricing problem
european_call = EuropeanCallPricing(
    num_uncertainty_qubits=3,
    strike_price=strike_price,
    maturity=maturity,
    volatility=volatility,
    spot_price=spot_price,
    risk_free_rate=risk_free_rate
)

# Classical Monte Carlo: O(ε⁻²) samples
classical_price = european_call.value_monte_carlo(num_samples=10000)

# Quantum Amplitude Estimation: O(ε⁻¹) queries
# (Requires quantum hardware or simulator)
# quantum_price = european_call.value_quantum(...)

print(f"Classical Monte Carlo: ${classical_price:.2f}")
```

### Variational Quantum Eigensolver (VQE)

For covariance matrix estimation:

```python
from qiskit.algorithms import VQE
from qiskit.circuit.library import TwoLocal

# Create variational ansatz
ansatz = TwoLocal(num_qubits=4, rotation_blocks='ry', entanglement_blocks='cz')

# Set up VQE
vqe = VQE(
    ansatz=ansatz,
    optimizer=COBYLA(maxiter=100),
    quantum_instance=Sampler()
)

# Find ground state energy (smallest eigenvalue)
result = vqe.compute_minimum_eigenvalue(operator)
eigenvalue = result.eigenvalue.real
```

## 💼 Week 9-12: Trading Integration

### Quantum-Enhanced Portfolio Rebalancing

```python
class QuantumPortfolioOptimizer:
    """Hybrid quantum-classical portfolio optimizer"""
    
    def __init__(self, quantum_backend='simulator'):
        self.service = QiskitRuntimeService()
        self.backend = self.service.backend(quantum_backend)
        self.qaoa_depth = 3
        
    def optimize(self, returns, cov_matrix, risk_factor=0.5):
        """
        Optimize portfolio using QAOA.
        
        Args:
            returns: Expected returns for each asset
            cov_matrix: Covariance matrix
            risk_factor: Risk aversion (0=max return, 1=min risk)
            
        Returns:
            Optimal portfolio weights
        """
        n_assets = len(returns)
        
        # Build QUBO problem
        portfolio_problem = PortfolioOptimization(
            expected_returns=returns,
            covariances=cov_matrix,
            risk_factor=risk_factor,
            budget=1
        )
        qubo = portfolio_problem.to_quadratic_program()
        
        # Solve with QAOA
        optimizer = COBYLA(maxiter=100)
        qaoa = QAOA(
            sampler=Sampler(self.backend),
            optimizer=optimizer,
            reps=self.qaoa_depth
        )
        
        result = qaoa.compute_minimum_eigenvalue(qubo)
        weights = portfolio_problem.interpret(result)
        
        return weights

# Usage in trading system
optimizer = QuantumPortfolioOptimizer(quantum_backend='ibmq_qasm_simulator')

# Get current market data
returns = estimate_expected_returns(historical_data)
cov = estimate_covariance(historical_data)

# Optimize portfolio
optimal_weights = optimizer.optimize(returns, cov, risk_factor=0.5)

# Generate rebalancing trades
current_weights = get_current_positions()
trades = calculate_rebalance_trades(current_weights, optimal_weights)
```

### Quantum Signal Generation

```python
class QuantumSignalGenerator:
    """Generate trading signals using quantum ML"""
    
    def __init__(self):
        self.feature_map = ZZFeatureMap(feature_dimension=4, reps=2)
        self.ansatz = RealAmplitudes(num_qubits=4, reps=3)
        
    def train(self, X_train, y_train):
        """Train quantum classifier on historical data"""
        from qiskit_machine_learning.algorithms import VQC
        
        vqc = VQC(
            feature_map=self.feature_map,
            ansatz=self.ansatz,
            optimizer=COBYLA(maxiter=100)
        )
        
        vqc.fit(X_train, y_train)
        self.classifier = vqc
        
    def predict(self, X_new):
        """Generate trading signal (buy/sell/hold)"""
        return self.classifier.predict(X_new)

# Usage
signal_generator = QuantumSignalGenerator()

# Train on historical data
features = extract_technical_indicators(historical_data)
labels = calculate_future_returns(historical_data) > 0  # Binary classification

signal_generator.train(features, labels)

# Generate signal for today
today_features = extract_technical_indicators(today_data)
signal = signal_generator.predict(today_features)
```

### Backtesting Quantum Strategies

```python
def backtest_quantum_portfolio(
    data, 
    rebalance_freq='monthly',
    quantum_backend='simulator'
):
    """
    Backtest quantum portfolio optimization strategy.
    
    Args:
        data: Historical price data
        rebalance_freq: How often to rebalance
        quantum_backend: 'simulator' or IBM quantum hardware
        
    Returns:
        Performance metrics
    """
    optimizer = QuantumPortfolioOptimizer(quantum_backend)
    portfolio_values = []
    
    for date in rebalance_dates:
        # Get data up to this date
        historical = data[:date]
        
        # Estimate parameters
        returns = estimate_returns(historical)
        cov = estimate_covariance(historical)
        
        # Optimize with quantum
        weights = optimizer.optimize(returns, cov)
        
        # Hold until next rebalance
        next_date = date + rebalance_freq
        period_return = calculate_return(data[date:next_date], weights)
        portfolio_values.append(period_return)
    
    # Calculate performance metrics
    total_return = np.prod(1 + np.array(portfolio_values)) - 1
    sharpe = np.mean(portfolio_values) / np.std(portfolio_values) * np.sqrt(252)
    
    return {
        'total_return': total_return,
        'sharpe_ratio': sharpe,
        'portfolio_values': portfolio_values
    }

# Run backtest
results = backtest_quantum_portfolio(
    historical_data,
    rebalance_freq='monthly',
    quantum_backend='ibmq_qasm_simulator'
)

print(f"Quantum Strategy Return: {results['total_return']:.2%}")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
```

## 🎯 Practical Tips

### Do's ✅
1. **Start with simulators** - Free, fast, no noise
2. **Use small problems** - 3-5 assets initially
3. **Benchmark vs classical** - Always compare performance
4. **Document everything** - Record parameters, results, insights
5. **Use error mitigation** - Readout error correction on real hardware
6. **Multiple runs** - Quantum results are probabilistic
7. **Warm start** - Initialize with classical solution

### Don'ts ❌
1. **Don't expect magic** - Quantum won't solve all problems
2. **Don't use for real-time** - Latency too high (2025)
3. **Don't trust single run** - Always aggregate multiple shots
4. **Don't skip classical comparison** - May not have advantage yet
5. **Don't over-engineer** - Start simple, add complexity gradually
6. **Don't ignore noise** - Real quantum hardware is noisy
7. **Don't bet the farm** - Experimental technology

### Debugging Quantum Circuits

```python
# Visualize circuit
qc.draw('mpl')  # Matplotlib visualization
qc.draw('text')  # Text representation

# Check circuit properties
print(f"Depth: {qc.depth()}")
print(f"Gate count: {qc.size()}")
print(f"Qubits: {qc.num_qubits}")

# Simulate step-by-step
from qiskit.quantum_info import Statevector

state = Statevector.from_instruction(qc)
print(state)  # See quantum state at each step

# Analyze results
from qiskit.visualization import plot_histogram

job = backend.run(qc, shots=1000)
counts = job.result().get_counts()
plot_histogram(counts)
```

## 📊 Success Checklist

### Month 1
- [ ] IBM Quantum account created
- [ ] Qiskit installed and working
- [ ] First quantum circuit executed
- [ ] Portfolio optimization example working
- [ ] Comparison with classical optimizer

### Month 2
- [ ] Understand superposition and entanglement
- [ ] QAOA algorithm implemented
- [ ] VQE algorithm working
- [ ] Complete Qiskit textbook chapters 1-3

### Month 3
- [ ] Quantum portfolio optimizer integrated
- [ ] Backtest quantum strategy
- [ ] Run on real IBM quantum hardware
- [ ] Document lessons learned

### Month 4+
- [ ] Experiment with quantum ML
- [ ] Explore D-Wave quantum annealing
- [ ] Contribute to Qiskit community
- [ ] Publish findings (if appropriate)

## 🚀 Next Actions

1. **Create IBM Quantum account** - Do it now (5 minutes)
2. **Install Qiskit** - `pip install qiskit qiskit-finance`
3. **Run first example** - Copy portfolio code above
4. **Schedule learning time** - Block 2-3 hours/week
5. **Join community** - Qiskit Slack, Stack Exchange

---

**Remember**: Quantum computing is a long-term investment. Focus on learning fundamentals now, experiment with algorithms, and stay ready to scale when hardware improves. The goal is to build quantum literacy and identify quantum-advantaged problems, not to magically solve trading overnight.

**Budget**: $0 (all resources free)  
**Time**: 2-3 hours/week  
**Timeline**: 3-6 months to proficiency  
**Expected Value**: High (2027+), Medium (learning value 2025)
