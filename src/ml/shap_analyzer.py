"""
SHAP Feature Importance Analysis for ML Trading Models

Provides explainability and feature importance analysis using SHAP
(SHapley Additive exPlanations) values. Critical for:

1. Identifying which features drive trading decisions
2. Detecting potential overfitting (e.g., reliance on time-based features)
3. Understanding model behavior across different market regimes
4. Validating that the model learns meaningful patterns

Key Warning Signs:
- High importance on "Day of Week" or "Hour" = likely overfitting
- Zero importance on fundamental features = model not learning edge
- Unstable importance across time = model drift

Author: Trading System
Created: 2025-12-10
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Try to import SHAP (optional dependency)
try:
    import shap

    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP not installed. Run: pip install shap")


@dataclass
class FeatureImportanceReport:
    """Report containing feature importance analysis."""

    model_name: str
    timestamp: str
    feature_names: list[str]
    importance_scores: dict[str, float]
    importance_ranking: list[tuple[str, float]]
    warnings: list[str]
    recommendations: list[str]
    shap_values_summary: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "timestamp": self.timestamp,
            "feature_names": self.feature_names,
            "importance_scores": self.importance_scores,
            "importance_ranking": self.importance_ranking,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "shap_values_summary": self.shap_values_summary,
        }

    def save(self, filepath: Path) -> None:
        """Save report to JSON file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        logger.info(f"Feature importance report saved to {filepath}")


class SHAPAnalyzer:
    """
    SHAP-based feature importance analyzer for trading models.

    Supports:
    - Tree-based models (XGBoost, LightGBM, RandomForest)
    - Neural networks (via DeepExplainer or KernelExplainer)
    - Ensemble models
    """

    # Features that indicate potential overfitting if highly important
    SUSPICIOUS_FEATURES = {
        "day_of_week",
        "dayofweek",
        "weekday",
        "hour",
        "hour_of_day",
        "time_of_day",
        "month",
        "quarter",
        "year",
        "day_of_month",
        "day_of_year",
        "minute",
        "second",
    }

    # Features that SHOULD be important for a valid trading model
    EXPECTED_IMPORTANT = {
        "returns",
        "rsi",
        "macd",
        "signal",
        "volatility",
        "volume",
        "momentum",
        "trend",
        "sentiment",
        "close",
        "price",
        "spread",
    }

    def __init__(
        self,
        model: Any,
        feature_names: list[str],
        model_type: str = "auto",
    ):
        """
        Initialize SHAP analyzer.

        Args:
            model: Trained model (sklearn, XGBoost, PyTorch, etc.)
            feature_names: List of feature names
            model_type: "tree", "neural", "linear", or "auto" (auto-detect)
        """
        if not SHAP_AVAILABLE:
            raise ImportError("SHAP is required. Install with: pip install shap")

        self.model = model
        self.feature_names = feature_names
        self.model_type = model_type
        self.explainer = None
        self.shap_values = None

        logger.info(f"SHAPAnalyzer initialized with {len(feature_names)} features")

    def compute_shap_values(
        self,
        X: np.ndarray,
        background_samples: int = 100,
    ) -> np.ndarray:
        """
        Compute SHAP values for the given data.

        Args:
            X: Feature matrix (n_samples, n_features)
            background_samples: Number of samples for background dataset

        Returns:
            SHAP values array (n_samples, n_features)
        """
        if self.model_type == "auto":
            self.model_type = self._detect_model_type()

        logger.info(f"Computing SHAP values using {self.model_type} explainer...")

        # Select appropriate explainer
        if self.model_type == "tree":
            self.explainer = shap.TreeExplainer(self.model)
            self.shap_values = self.explainer.shap_values(X)

        elif self.model_type == "linear":
            self.explainer = shap.LinearExplainer(self.model, X[:background_samples])
            self.shap_values = self.explainer.shap_values(X)

        else:  # neural or unknown - use KernelExplainer
            background = shap.sample(X, min(background_samples, len(X)))
            self.explainer = shap.KernelExplainer(self._model_predict, background)
            self.shap_values = self.explainer.shap_values(X[:100])  # Limit for speed

        # Handle multi-output models
        if isinstance(self.shap_values, list):
            # Use last output for classification
            self.shap_values = self.shap_values[-1]

        logger.info(f"SHAP values computed: shape {self.shap_values.shape}")
        return self.shap_values

    def _detect_model_type(self) -> str:
        """Auto-detect model type."""
        model_class = type(self.model).__name__.lower()

        if any(t in model_class for t in ["tree", "forest", "xgb", "lgb", "catboost"]):
            return "tree"
        elif any(t in model_class for t in ["linear", "ridge", "lasso", "logistic"]):
            return "linear"
        else:
            return "neural"

    def _model_predict(self, X: np.ndarray) -> np.ndarray:
        """Wrapper for model prediction."""
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        elif hasattr(self.model, "predict"):
            return self.model.predict(X)
        else:
            # PyTorch model
            import torch

            with torch.no_grad():
                tensor = torch.FloatTensor(X)
                return self.model(tensor).numpy()

    def get_feature_importance(self) -> dict[str, float]:
        """
        Calculate feature importance from SHAP values.

        Returns:
            Dict mapping feature names to importance scores (0-100 scale)
        """
        if self.shap_values is None:
            raise ValueError("Call compute_shap_values() first")

        # Mean absolute SHAP value per feature
        mean_abs_shap = np.abs(self.shap_values).mean(axis=0)

        # Normalize to 0-100 scale
        total = mean_abs_shap.sum()
        if total > 0:
            normalized = (mean_abs_shap / total) * 100
        else:
            normalized = np.zeros_like(mean_abs_shap)

        importance = {}
        for i, name in enumerate(self.feature_names):
            if i < len(normalized):
                importance[name] = float(normalized[i])
            else:
                importance[name] = 0.0

        return importance

    def analyze(
        self,
        X: np.ndarray,
        output_dir: Optional[Path] = None,
    ) -> FeatureImportanceReport:
        """
        Run full SHAP analysis and generate report.

        Args:
            X: Feature matrix
            output_dir: Optional directory to save report and plots

        Returns:
            FeatureImportanceReport with analysis results
        """
        # Compute SHAP values
        self.compute_shap_values(X)

        # Get importance scores
        importance = self.get_feature_importance()

        # Rank features by importance
        ranking = sorted(importance.items(), key=lambda x: x[1], reverse=True)

        # Check for warning signs
        warnings = []
        recommendations = []

        # Check for suspicious features
        for feature, score in ranking[:5]:  # Top 5 features
            feature_lower = feature.lower()
            if any(sus in feature_lower for sus in self.SUSPICIOUS_FEATURES):
                warnings.append(
                    f"⚠️ '{feature}' is in top 5 with {score:.1f}% importance - "
                    "may indicate overfitting to temporal patterns"
                )

        # Check for expected important features
        top_features_lower = {f.lower() for f, _ in ranking[:10]}
        expected_found = sum(
            1 for exp in self.EXPECTED_IMPORTANT if any(exp in f for f in top_features_lower)
        )

        if expected_found < 3:
            warnings.append(
                f"⚠️ Only {expected_found}/10 top features are fundamentals - "
                "model may not be learning meaningful patterns"
            )

        # Check for feature concentration
        top_3_importance = sum(score for _, score in ranking[:3])
        if top_3_importance > 70:
            warnings.append(
                f"⚠️ Top 3 features account for {top_3_importance:.1f}% of importance - "
                "model may be overly dependent on few features"
            )

        # Generate recommendations
        if warnings:
            recommendations.append(
                "Review feature engineering - consider removing or transforming "
                "highly suspicious features"
            )
            recommendations.append("Run walk-forward validation to check for temporal overfitting")
        else:
            recommendations.append(
                "Feature importance looks healthy - model appears to learn "
                "from fundamental trading signals"
            )

        # SHAP summary statistics
        shap_summary = {
            "mean_abs_shap": float(np.abs(self.shap_values).mean()),
            "max_shap": float(np.abs(self.shap_values).max()),
            "std_shap": float(self.shap_values.std()),
            "n_samples": int(self.shap_values.shape[0]),
            "n_features": int(self.shap_values.shape[1]),
        }

        report = FeatureImportanceReport(
            model_name=type(self.model).__name__,
            timestamp=datetime.now().isoformat(),
            feature_names=self.feature_names,
            importance_scores=importance,
            importance_ranking=ranking,
            warnings=warnings,
            recommendations=recommendations,
            shap_values_summary=shap_summary,
        )

        # Save report if output directory provided
        if output_dir:
            output_dir = Path(output_dir)
            report.save(output_dir / "feature_importance_report.json")

            # Save SHAP values for further analysis
            np.save(output_dir / "shap_values.npy", self.shap_values)

        return report


def analyze_model_features(
    model: Any,
    X: np.ndarray,
    feature_names: list[str],
    output_dir: Optional[str] = None,
) -> FeatureImportanceReport:
    """
    Convenience function to analyze feature importance.

    Args:
        model: Trained model
        X: Feature matrix
        feature_names: List of feature names
        output_dir: Optional output directory

    Returns:
        FeatureImportanceReport
    """
    analyzer = SHAPAnalyzer(model, feature_names)
    return analyzer.analyze(X, output_dir=Path(output_dir) if output_dir else None)


def quick_importance_check(
    importance_scores: dict[str, float],
) -> dict[str, Any]:
    """
    Quick check of feature importance for warning signs.

    Args:
        importance_scores: Dict of feature name -> importance score

    Returns:
        Dict with 'healthy', 'warnings', 'top_features'
    """
    warnings = []

    # Sort by importance
    sorted_features = sorted(importance_scores.items(), key=lambda x: x[1], reverse=True)

    # Check top features
    for feature, score in sorted_features[:5]:
        feature_lower = feature.lower()
        if any(sus in feature_lower for sus in SHAPAnalyzer.SUSPICIOUS_FEATURES):
            warnings.append(f"'{feature}' ({score:.1f}%) is time-based - possible overfit")

    # Check concentration
    top_3_pct = sum(s for _, s in sorted_features[:3])
    if top_3_pct > 70:
        warnings.append(f"Top 3 features = {top_3_pct:.1f}% - high concentration")

    return {
        "healthy": len(warnings) == 0,
        "warnings": warnings,
        "top_features": sorted_features[:10],
    }


if __name__ == "__main__":
    """Demo the SHAP analyzer with a simple example."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("SHAP FEATURE IMPORTANCE DEMO")
    print("=" * 80)

    if not SHAP_AVAILABLE:
        print("\n❌ SHAP not installed. Install with: pip install shap")
        print("\nShowing quick_importance_check() demo instead:\n")

        # Demo with mock importance scores
        mock_scores = {
            "RSI": 25.0,
            "MACD": 20.0,
            "day_of_week": 18.0,  # Suspicious!
            "Volatility": 12.0,
            "Returns": 10.0,
            "Volume": 8.0,
            "hour": 4.0,  # Suspicious!
            "Sentiment": 3.0,
        }

        result = quick_importance_check(mock_scores)

        print("Mock Feature Importance Scores:")
        for feature, score in sorted(mock_scores.items(), key=lambda x: -x[1]):
            print(f"  {feature}: {score:.1f}%")

        print(f"\nHealth Check: {'✅ HEALTHY' if result['healthy'] else '⚠️ WARNINGS'}")

        if result["warnings"]:
            print("\nWarnings:")
            for w in result["warnings"]:
                print(f"  - {w}")
    else:
        # Full demo with sklearn model
        from sklearn.ensemble import RandomForestClassifier

        # Generate synthetic data
        np.random.seed(42)
        n_samples = 500

        feature_names = [
            "RSI",
            "MACD",
            "Volatility",
            "Returns",
            "Volume",
            "Sentiment",
            "day_of_week",
            "hour",
        ]

        X = np.random.randn(n_samples, len(feature_names))
        # Make RSI and MACD actually predictive
        y = ((X[:, 0] > 0) & (X[:, 1] > 0)).astype(int)

        # Train simple model
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)

        # Analyze
        print("\nAnalyzing RandomForest model...")
        report = analyze_model_features(model, X, feature_names)

        print("\nFeature Importance Ranking:")
        for i, (feature, score) in enumerate(report.importance_ranking, 1):
            print(f"  {i}. {feature}: {score:.1f}%")

        print(f"\nWarnings ({len(report.warnings)}):")
        for w in report.warnings:
            print(f"  {w}")

        print("\nRecommendations:")
        for r in report.recommendations:
            print(f"  - {r}")
