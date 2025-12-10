"""
Research Package - Alpha Research Framework

This package provides a structured framework for alpha research, feature engineering,
and strategy development following world-class quantitative trading practices.

Modules:
    - alpha: Alpha signal generation and factor library
    - labeling: Target variable creation (triple-barrier, directional, volatility)
    - baselines: Canonical baseline strategies for benchmarking
    - experiments: Experiment tracking and model registry
    - portfolio: Portfolio construction and optimization
    - factors: Factor analysis and exposure tracking
    - data_contracts: Schema validation and data quality checks

Usage:
    from src.research import AlphaResearcher, TripleBarrierLabeler
    from src.research.baselines import BuyAndHoldBaseline, MomentumBaseline
    from src.research.portfolio import PortfolioOptimizer
    from src.research.experiments import ExperimentTracker
    from src.research.factors import FactorModel

Author: Trading System
Created: 2025-12-02
"""

from src.research.alpha import AlphaResearcher, FeatureConfig, FeatureLibrary
from src.research.baselines import (
    BacktestResult,
    BaselineStrategy,
    BuyAndHoldBaseline,
    MeanReversionBaseline,
    MovingAverageCrossover,
    TimeSeriesMomentum,
    run_baseline_comparison,
)
from src.research.data_contracts import (
    DataQualityReport,
    DataSnapshot,
    DataValidator,
    FutureReturns,
    Label,
    OHLCVSchema,
    SignalSnapshot,
)
from src.research.experiments import (
    ExperimentConfig,
    ExperimentRun,
    ExperimentTracker,
    ModelRegistry,
)
from src.research.factors import (
    FactorAttributionResult,
    FactorExposure,
    FactorModel,
    FactorRiskMonitor,
    PCAFactorDiscovery,
    SyntheticFactorGenerator,
)
from src.research.labeling import (
    DirectionalLabeler,
    LabelingResult,
    TripleBarrierConfig,
    TripleBarrierLabeler,
    VolatilityLabeler,
    create_complete_labels,
)
from src.research.portfolio import (
    OptimizationMethod,
    PortfolioConstraints,
    PortfolioOptimizer,
    PortfolioResult,
    calculate_portfolio_stats,
)

__all__ = [
    # Alpha Research
    "AlphaResearcher",
    "FeatureLibrary",
    "FeatureConfig",
    # Labeling
    "TripleBarrierLabeler",
    "TripleBarrierConfig",
    "DirectionalLabeler",
    "VolatilityLabeler",
    "LabelingResult",
    "create_complete_labels",
    # Baselines
    "BaselineStrategy",
    "BuyAndHoldBaseline",
    "MovingAverageCrossover",
    "TimeSeriesMomentum",
    "MeanReversionBaseline",
    "BacktestResult",
    "run_baseline_comparison",
    # Data Contracts
    "DataValidator",
    "DataSnapshot",
    "OHLCVSchema",
    "DataQualityReport",
    "SignalSnapshot",
    "FutureReturns",
    "Label",
    # Experiments
    "ExperimentTracker",
    "ExperimentConfig",
    "ExperimentRun",
    "ModelRegistry",
    # Portfolio
    "PortfolioOptimizer",
    "PortfolioConstraints",
    "PortfolioResult",
    "OptimizationMethod",
    "calculate_portfolio_stats",
    # Factors
    "FactorModel",
    "FactorExposure",
    "FactorAttributionResult",
    "FactorRiskMonitor",
    "PCAFactorDiscovery",
    "SyntheticFactorGenerator",
]
