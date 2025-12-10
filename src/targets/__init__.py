"""
Target Model Module

This module makes the $100/day goal an explicit, measurable constraint.
It provides capital calculations, risk modeling, and progress tracking.

Author: Trading System
Created: 2025-12-03
"""

from src.targets.capital_model import CapitalModel, CapitalRequirements
from src.targets.daily_target import DailyTargetModel, TargetMetrics
from src.targets.progress_tracker import DailyProgress, ProgressTracker

__all__ = [
    "DailyTargetModel",
    "TargetMetrics",
    "CapitalModel",
    "CapitalRequirements",
    "ProgressTracker",
    "DailyProgress",
]
