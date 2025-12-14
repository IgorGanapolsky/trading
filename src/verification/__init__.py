"""
Comprehensive Verification System

Multi-layer verification to prevent trading system failures.
Integrates with RAG, ML pipeline, and lessons learned.

Created: Dec 11, 2025 (after syntax error incident)
Updated: Dec 11, 2025 (added FACTS Benchmark factuality monitor)
Updated: Dec 11, 2025 (added hallucination prevention pipeline)
Updated: Dec 11, 2025 (added position reconciler, circuit breaker, alerts, backtester)
"""

from .continuous_verifier import ContinuousVerifier
from .factuality_monitor import (
    FACTS_BENCHMARK_SCORES,
    FactualityMonitor,
    HallucinationType,
    VerificationSource,
    create_factuality_monitor,
)
from .hallucination_alerts import Alert, HallucinationAlertSystem
from .hallucination_prevention import (
    HallucinationPattern,
    HallucinationPreventionPipeline,
    Prediction,
    create_hallucination_pipeline,
)
from .llm_hallucination_rag_guard import (
    LLMHallucinationGuard,
    Violation,
    create_hallucination_guard,
)
from .model_circuit_breaker import CircuitState, ModelCircuitBreaker
from .position_reconciler import PositionReconciler, ReconciliationResult
from .post_deploy_verifier import PostDeployVerifier
from .pre_merge_verifier import PreMergeVerifier
from .rag_safety_checker import RAGSafetyChecker
from .signal_backtester import BacktestResult, SignalBacktester
from .automated_lesson_ingestion import AutomatedLessonIngestion, FailureEvent
from .ml_rag_integrated_verifier import MLRAGIntegratedVerifier, VerificationResult

__all__ = [
    # Core verifiers
    "PreMergeVerifier",
    "PostDeployVerifier",
    "ContinuousVerifier",
    "RAGSafetyChecker",
    # Automated lesson ingestion
    "AutomatedLessonIngestion",
    "FailureEvent",
    # ML+RAG integrated verification
    "MLRAGIntegratedVerifier",
    "VerificationResult",
    # FACTS Benchmark
    "FactualityMonitor",
    "create_factuality_monitor",
    "FACTS_BENCHMARK_SCORES",
    "HallucinationType",
    "VerificationSource",
    # Hallucination prevention
    "HallucinationPreventionPipeline",
    "create_hallucination_pipeline",
    "Prediction",
    "HallucinationPattern",
    # LLM Hallucination Guard
    "LLMHallucinationGuard",
    "create_hallucination_guard",
    "Violation",
    # Position reconciliation
    "PositionReconciler",
    "ReconciliationResult",
    # Circuit breaker
    "ModelCircuitBreaker",
    "CircuitState",
    # Backtesting
    "SignalBacktester",
    "BacktestResult",
    # Alerts
    "HallucinationAlertSystem",
    "Alert",
]
