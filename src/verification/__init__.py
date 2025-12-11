"""
Comprehensive Verification System

Multi-layer verification to prevent trading system failures.
Integrates with RAG, ML pipeline, and lessons learned.

Created: Dec 11, 2025 (after syntax error incident)
Updated: Dec 11, 2025 (added FACTS Benchmark factuality monitor)
"""

from .pre_merge_verifier import PreMergeVerifier
from .post_deploy_verifier import PostDeployVerifier
from .continuous_verifier import ContinuousVerifier
from .rag_safety_checker import RAGSafetyChecker
from .factuality_monitor import (
    FactualityMonitor,
    create_factuality_monitor,
    FACTS_BENCHMARK_SCORES,
    HallucinationType,
    VerificationSource,
)

__all__ = [
    "PreMergeVerifier",
    "PostDeployVerifier",
    "ContinuousVerifier",
    "RAGSafetyChecker",
    "FactualityMonitor",
    "create_factuality_monitor",
    "FACTS_BENCHMARK_SCORES",
    "HallucinationType",
    "VerificationSource",
]
