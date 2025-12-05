"""
Conditional Entropy Feature Selector for Trading

Uses information-theoretic measures to select the most predictive features
for trading signals. Based on conditional entropy H(Y|X) to measure how much
uncertainty about the target (price direction) remains after observing each feature.

Key Concepts:
- H(Y) = Entropy of target variable (baseline uncertainty)
- H(Y|X) = Conditional entropy (remaining uncertainty after observing X)
- I(X;Y) = H(Y) - H(Y|X) = Mutual information (information gain)

Lower H(Y|X) = Higher predictive power = Better feature

Usage:
    selector = EntropyFeatureSelector()
    selected_features = selector.select_features(df, target='price_direction', k=10)

    # Get feature importance scores
    scores = selector.get_feature_scores(df, target='price_direction')

Author: Trading System CTO
Created: 2025-12-04
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class EntropyFeatureSelector:
    """
    Feature selector using conditional entropy and mutual information.

    Selects features that maximize information gain about the target variable,
    which for trading is typically price direction or return sign.
    """

    def __init__(self, n_bins: int = 10, min_samples_per_bin: int = 5):
        """
        Initialize the entropy feature selector.

        Args:
            n_bins: Number of bins for discretizing continuous features
            min_samples_per_bin: Minimum samples per bin to avoid sparse estimates
        """
        self.n_bins = n_bins
        self.min_samples_per_bin = min_samples_per_bin
        self._feature_scores: dict[str, dict] = {}

    def _discretize(self, x: np.ndarray, n_bins: Optional[int] = None) -> np.ndarray:
        """
        Discretize continuous variable into bins.

        Args:
            x: Continuous array to discretize
            n_bins: Number of bins (uses instance default if None)

        Returns:
            Discretized array with bin labels
        """
        n_bins = n_bins or self.n_bins

        # Handle NaN values
        valid_mask = ~np.isnan(x)
        if not valid_mask.any():
            return np.zeros_like(x, dtype=int)

        result = np.zeros_like(x, dtype=int)

        # Use quantile-based binning for robustness
        try:
            result[valid_mask] = pd.qcut(x[valid_mask], q=n_bins, labels=False, duplicates="drop")
        except ValueError:
            # Fall back to equal-width bins if quantiles fail
            result[valid_mask] = pd.cut(x[valid_mask], bins=n_bins, labels=False)

        return result

    def _entropy(self, x: np.ndarray) -> float:
        """
        Calculate Shannon entropy H(X).

        Args:
            x: Discrete array of values

        Returns:
            Entropy in bits
        """
        # Remove NaN values
        x = x[~np.isnan(x)]
        if len(x) == 0:
            return 0.0

        # Calculate probability distribution
        _, counts = np.unique(x, return_counts=True)
        probs = counts / len(x)

        # Filter zero probabilities
        probs = probs[probs > 0]

        # H(X) = -sum(p * log2(p))
        return -np.sum(probs * np.log2(probs))

    def _conditional_entropy(self, x: np.ndarray, y: np.ndarray) -> float:
        """
        Calculate conditional entropy H(Y|X).

        H(Y|X) = sum over x of P(X=x) * H(Y|X=x)

        Args:
            x: Conditioning variable (feature)
            y: Target variable

        Returns:
            Conditional entropy in bits
        """
        # Remove samples where either is NaN
        valid_mask = ~(np.isnan(x) | np.isnan(y))
        x = x[valid_mask]
        y = y[valid_mask]

        if len(x) == 0:
            return 0.0

        # Get unique values of conditioning variable
        x_values = np.unique(x)

        h_y_given_x = 0.0
        for x_val in x_values:
            # P(X=x)
            mask = x == x_val
            p_x = np.sum(mask) / len(x)

            # H(Y|X=x)
            y_given_x = y[mask]
            h_y_given_x_val = self._entropy(y_given_x)

            # Weighted sum
            h_y_given_x += p_x * h_y_given_x_val

        return h_y_given_x

    def _mutual_information(self, x: np.ndarray, y: np.ndarray) -> float:
        """
        Calculate mutual information I(X;Y) = H(Y) - H(Y|X).

        Higher MI = more information X provides about Y = better feature.

        Args:
            x: Feature variable
            y: Target variable

        Returns:
            Mutual information in bits
        """
        h_y = self._entropy(y)
        h_y_given_x = self._conditional_entropy(x, y)
        return h_y - h_y_given_x

    def _information_gain_ratio(self, x: np.ndarray, y: np.ndarray) -> float:
        """
        Calculate information gain ratio (normalized mutual information).

        IGR = I(X;Y) / H(X)

        Normalizes by feature entropy to avoid bias toward high-cardinality features.

        Args:
            x: Feature variable
            y: Target variable

        Returns:
            Information gain ratio (0 to 1)
        """
        mi = self._mutual_information(x, y)
        h_x = self._entropy(x)

        if h_x == 0:
            return 0.0

        return mi / h_x

    def score_feature(
        self, feature: np.ndarray, target: np.ndarray, feature_name: str = "feature"
    ) -> dict:
        """
        Score a single feature's predictive power.

        Args:
            feature: Feature values
            target: Target values
            feature_name: Name for logging

        Returns:
            Dict with entropy metrics
        """
        # Discretize continuous feature
        feature_discrete = self._discretize(feature)

        # Discretize target if continuous
        if len(np.unique(target)) > self.n_bins:
            target_discrete = self._discretize(target, n_bins=3)  # 3 classes: down, flat, up
        else:
            target_discrete = target

        # Calculate metrics
        h_y = self._entropy(target_discrete)
        h_y_given_x = self._conditional_entropy(feature_discrete, target_discrete)
        mi = h_y - h_y_given_x
        h_x = self._entropy(feature_discrete)
        igr = mi / h_x if h_x > 0 else 0.0

        # Uncertainty reduction percentage
        uncertainty_reduction = (1 - h_y_given_x / h_y) * 100 if h_y > 0 else 0.0

        scores = {
            "feature_name": feature_name,
            "entropy_target": h_y,
            "conditional_entropy": h_y_given_x,
            "mutual_information": mi,
            "entropy_feature": h_x,
            "information_gain_ratio": igr,
            "uncertainty_reduction_pct": uncertainty_reduction,
            "predictive_power": "high" if igr > 0.1 else "medium" if igr > 0.05 else "low",
        }

        return scores

    def get_feature_scores(
        self, df: pd.DataFrame, target: str, features: Optional[list[str]] = None
    ) -> pd.DataFrame:
        """
        Score all features in a dataframe.

        Args:
            df: DataFrame with features and target
            target: Name of target column
            features: List of feature columns (default: all except target)

        Returns:
            DataFrame with feature scores, sorted by mutual information
        """
        if features is None:
            features = [col for col in df.columns if col != target]

        target_values = df[target].values

        scores_list = []
        for feat in features:
            try:
                scores = self.score_feature(df[feat].values, target_values, feature_name=feat)
                scores_list.append(scores)
                self._feature_scores[feat] = scores
            except Exception as e:
                logger.warning(f"Failed to score feature {feat}: {e}")

        scores_df = pd.DataFrame(scores_list)
        scores_df = scores_df.sort_values("mutual_information", ascending=False)

        return scores_df

    def select_features(
        self,
        df: pd.DataFrame,
        target: str,
        k: Optional[int] = None,
        min_mi: float = 0.01,
        features: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Select top-k features by mutual information.

        Args:
            df: DataFrame with features and target
            target: Name of target column
            k: Number of features to select (default: all above min_mi)
            min_mi: Minimum mutual information threshold
            features: List of feature columns to consider

        Returns:
            List of selected feature names
        """
        scores_df = self.get_feature_scores(df, target, features)

        # Filter by minimum MI
        scores_df = scores_df[scores_df["mutual_information"] >= min_mi]

        # Select top k
        if k is not None:
            scores_df = scores_df.head(k)

        selected = scores_df["feature_name"].tolist()

        logger.info(f"Selected {len(selected)} features with MI >= {min_mi}")
        for _, row in scores_df.iterrows():
            logger.info(
                f"  {row['feature_name']}: MI={row['mutual_information']:.4f}, "
                f"Uncertainty reduction={row['uncertainty_reduction_pct']:.1f}%"
            )

        return selected

    def select_non_redundant_features(
        self, df: pd.DataFrame, target: str, k: int = 10, redundancy_threshold: float = 0.7
    ) -> list[str]:
        """
        Select features that are informative but not redundant with each other.

        Uses greedy forward selection: add feature with highest MI that has
        low redundancy with already selected features.

        Args:
            df: DataFrame with features and target
            target: Name of target column
            k: Maximum number of features to select
            redundancy_threshold: Max correlation with existing features

        Returns:
            List of selected non-redundant feature names
        """
        scores_df = self.get_feature_scores(df, target)
        all_features = scores_df["feature_name"].tolist()

        if not all_features:
            return []

        selected = [all_features[0]]  # Start with best feature

        for _ in range(k - 1):
            best_feature = None
            best_mi = -1

            for feat in all_features:
                if feat in selected:
                    continue

                # Check redundancy with selected features
                is_redundant = False
                for sel_feat in selected:
                    corr = abs(df[feat].corr(df[sel_feat]))
                    if corr > redundancy_threshold:
                        is_redundant = True
                        break

                if is_redundant:
                    continue

                # Get MI score
                mi = self._feature_scores[feat]["mutual_information"]
                if mi > best_mi:
                    best_mi = mi
                    best_feature = feat

            if best_feature is None:
                break

            selected.append(best_feature)

        logger.info(f"Selected {len(selected)} non-redundant features")
        return selected


def create_trading_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create standard trading features for entropy analysis.

    Args:
        df: DataFrame with OHLCV data (columns: open, high, low, close, volume)

    Returns:
        DataFrame with added technical features
    """
    result = df.copy()

    # Price features
    result["returns"] = result["close"].pct_change()
    result["log_returns"] = np.log(result["close"] / result["close"].shift(1))

    # Volatility
    result["volatility_5"] = result["returns"].rolling(5).std()
    result["volatility_20"] = result["returns"].rolling(20).std()

    # RSI
    delta = result["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    result["rsi_14"] = 100 - (100 / (1 + rs))

    # MACD
    ema_12 = result["close"].ewm(span=12).mean()
    ema_26 = result["close"].ewm(span=26).mean()
    result["macd"] = ema_12 - ema_26
    result["macd_signal"] = result["macd"].ewm(span=9).mean()
    result["macd_hist"] = result["macd"] - result["macd_signal"]

    # Volume features
    result["volume_sma_20"] = result["volume"].rolling(20).mean()
    result["volume_ratio"] = result["volume"] / result["volume_sma_20"]

    # Price position
    result["high_low_range"] = (result["high"] - result["low"]) / result["close"]
    result["close_position"] = (result["close"] - result["low"]) / (result["high"] - result["low"])

    # Moving averages
    result["sma_5"] = result["close"].rolling(5).mean()
    result["sma_20"] = result["close"].rolling(20).mean()
    result["sma_50"] = result["close"].rolling(50).mean()
    result["price_sma_ratio"] = result["close"] / result["sma_20"]

    # Momentum
    result["momentum_5"] = result["close"] / result["close"].shift(5) - 1
    result["momentum_20"] = result["close"] / result["close"].shift(20) - 1

    # Target: next day direction
    result["target_direction"] = np.sign(result["returns"].shift(-1))

    return result.dropna()


class FeatureSelectionPipeline:
    """
    Integration pipeline that connects entropy-based feature selection
    with the existing ML training infrastructure.
    """

    def __init__(
        self,
        n_features: int = 10,
        min_mi: float = 0.005,
        remove_redundant: bool = True,
        redundancy_threshold: float = 0.7,
    ):
        """
        Initialize the feature selection pipeline.

        Args:
            n_features: Maximum number of features to select
            min_mi: Minimum mutual information threshold
            remove_redundant: Whether to remove redundant features
            redundancy_threshold: Correlation threshold for redundancy
        """
        self.n_features = n_features
        self.min_mi = min_mi
        self.remove_redundant = remove_redundant
        self.redundancy_threshold = redundancy_threshold
        self.selector = EntropyFeatureSelector()
        self.selected_features: list[str] = []
        self.feature_scores: Optional[pd.DataFrame] = None

    def fit(self, df: pd.DataFrame, target: str = "target_direction") -> "FeatureSelectionPipeline":
        """
        Fit the feature selector to the data.

        Args:
            df: DataFrame with features and target
            target: Name of target column

        Returns:
            Self for chaining
        """
        # Get feature columns (exclude target and raw OHLCV)
        exclude_cols = {
            target,
            "open",
            "high",
            "low",
            "close",
            "volume",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        }
        feature_cols = [c for c in df.columns if c not in exclude_cols]

        # Score all features
        self.feature_scores = self.selector.get_feature_scores(df, target, feature_cols)

        # Select features
        if self.remove_redundant:
            self.selected_features = self.selector.select_non_redundant_features(
                df, target, k=self.n_features, redundancy_threshold=self.redundancy_threshold
            )
        else:
            self.selected_features = self.selector.select_features(
                df, target, k=self.n_features, min_mi=self.min_mi
            )

        logger.info(f"Feature selection complete: {len(self.selected_features)} features selected")
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform data to include only selected features.

        Args:
            df: DataFrame with all features

        Returns:
            DataFrame with only selected features
        """
        if not self.selected_features:
            raise ValueError("Must call fit() before transform()")

        # Include selected features plus any essential columns
        cols = [c for c in self.selected_features if c in df.columns]
        return df[cols]

    def fit_transform(self, df: pd.DataFrame, target: str = "target_direction") -> pd.DataFrame:
        """Fit and transform in one step."""
        self.fit(df, target)
        return self.transform(df)

    def get_feature_report(self) -> str:
        """
        Generate a human-readable report of feature selection results.

        Returns:
            Formatted report string
        """
        if self.feature_scores is None:
            return "No feature scores available. Run fit() first."

        lines = [
            "=" * 60,
            "ENTROPY-BASED FEATURE SELECTION REPORT",
            "=" * 60,
            "",
            f"Total features analyzed: {len(self.feature_scores)}",
            f"Features selected: {len(self.selected_features)}",
            "",
            "Selected Features (ranked by mutual information):",
            "-" * 40,
        ]

        for feat in self.selected_features:
            row = self.feature_scores[self.feature_scores["feature_name"] == feat].iloc[0]
            lines.append(
                f"  {feat}: MI={row['mutual_information']:.4f}, "
                f"Uncertainty↓={row['uncertainty_reduction_pct']:.2f}%"
            )

        lines.extend(
            [
                "",
                "Full Feature Rankings:",
                "-" * 40,
            ]
        )

        for _, row in self.feature_scores.head(20).iterrows():
            selected = "✓" if row["feature_name"] in self.selected_features else " "
            lines.append(
                f"  [{selected}] {row['feature_name']}: "
                f"MI={row['mutual_information']:.4f}, "
                f"Power={row['predictive_power']}"
            )

        return "\n".join(lines)

    def save_results(self, filepath: str = "data/feature_selection_results.json"):
        """Save feature selection results to JSON."""
        import json
        from pathlib import Path

        results = {
            "selected_features": self.selected_features,
            "n_features_analyzed": len(self.feature_scores)
            if self.feature_scores is not None
            else 0,
            "feature_scores": self.feature_scores.to_dict("records")
            if self.feature_scores is not None
            else [],
            "config": {
                "n_features": self.n_features,
                "min_mi": self.min_mi,
                "remove_redundant": self.remove_redundant,
                "redundancy_threshold": self.redundancy_threshold,
            },
        }

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Feature selection results saved to {filepath}")


def integrate_with_data_processor(
    data_processor, symbol: str = "SPY", n_features: int = 10
) -> list[str]:
    """
    Convenience function to integrate entropy feature selection with DataProcessor.

    Args:
        data_processor: Instance of DataProcessor from src.ml.data_processor
        symbol: Symbol to use for feature selection
        n_features: Number of features to select

    Returns:
        List of selected feature names
    """
    # Fetch and process data
    df = data_processor.fetch_data(symbol, period="2y")
    if df.empty:
        logger.warning(f"No data for {symbol}, using default features")
        return data_processor.feature_columns

    # Add technical indicators
    df = data_processor.add_technical_indicators(df)

    # Create target
    df["target_direction"] = np.sign(df["Close"].pct_change().shift(-1))

    # Drop NaN
    df = df.dropna()

    # Run feature selection
    pipeline = FeatureSelectionPipeline(n_features=n_features)
    pipeline.fit(df, "target_direction")

    # Print report
    print(pipeline.get_feature_report())

    # Save results
    pipeline.save_results()

    return pipeline.selected_features


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Generate sample data
    np.random.seed(42)
    n_samples = 1000

    # Create synthetic OHLCV data
    close = 100 + np.cumsum(np.random.randn(n_samples) * 0.5)
    df = pd.DataFrame(
        {
            "open": close + np.random.randn(n_samples) * 0.1,
            "high": close + np.abs(np.random.randn(n_samples) * 0.5),
            "low": close - np.abs(np.random.randn(n_samples) * 0.5),
            "close": close,
            "volume": np.random.randint(1000000, 5000000, n_samples),
        }
    )

    # Create features
    df = create_trading_features(df)

    # Initialize selector
    selector = EntropyFeatureSelector()

    # Get feature scores
    feature_cols = [
        c
        for c in df.columns
        if c not in ["target_direction", "open", "high", "low", "close", "volume"]
    ]
    scores = selector.get_feature_scores(df, "target_direction", feature_cols)

    print("\n=== Feature Scores by Mutual Information ===")
    print(
        scores[
            ["feature_name", "mutual_information", "uncertainty_reduction_pct", "predictive_power"]
        ].to_string()
    )

    # Select best features
    print("\n=== Selected Features ===")
    selected = selector.select_features(df, "target_direction", k=5)
    print(f"Top 5 features: {selected}")

    # Select non-redundant features
    print("\n=== Non-Redundant Features ===")
    non_redundant = selector.select_non_redundant_features(df, "target_direction", k=5)
    print(f"Non-redundant features: {non_redundant}")
