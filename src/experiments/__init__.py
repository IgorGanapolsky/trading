"""ML Experiment Automation Module.

Enables running 100s-1000s of ML experiments automatically:
- Hyperparameter sweeps
- Strategy backtests
- Model comparisons
- Automated result analysis
"""

from src.experiments.experiment_runner import (
    Experiment,
    ExperimentResult,
    ExperimentRunner,
    HyperparameterGrid,
    run_experiment_sweep,
)

__all__ = [
    "Experiment",
    "ExperimentRunner",
    "ExperimentResult",
    "HyperparameterGrid",
    "run_experiment_sweep",
]
