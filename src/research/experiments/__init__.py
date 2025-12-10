"""
Experiment tracking and model registry.

Provides tools for managing experiments:
- Experiment configuration and tracking
- Metric and artifact logging
- Model versioning and registry
- Git SHA and data snapshot linking
"""

from src.research.experiments.registry import (
    ModelRegistry,
    ModelStage,
    ModelVersion,
)
from src.research.experiments.tracker import (
    ExperimentConfig,
    ExperimentRun,
    ExperimentTracker,
)

__all__ = [
    "ExperimentTracker",
    "ExperimentConfig",
    "ExperimentRun",
    "ModelRegistry",
    "ModelVersion",
    "ModelStage",
]
