"""
Data Hygiene and Rotation System

Ensures data quality, freshness, and prevents stale/inaccurate data from being used.
Validates historical data, rotates old data, and checks model staleness.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DataHygieneChecker:
    """Comprehensive data hygiene and quality validation system."""

    # Quality thresholds
    MAX_DATA_AGE_DAYS = 365  # Keep max 1 year of historical data
    MIN_DATA_COMPLETENESS = 0.95  # 95% of expected days must exist
    MAX_OUTLIER_ZSCORE = 4.0  # Reject outliers beyond 4 standard deviations
    MAX_GAP_DAYS = 5  # Max consecutive missing days

    # Model staleness thresholds
    MODEL_MAX_AGE_DAYS = 30  # Models older than 30 days are stale
    MODEL_MIN_PERFORMANCE = 0.6  # Models below 60% accuracy need retraining

    def __init__(self, data_dir: str = "data/historical", models_dir: str = "data/models"):
        self.data_dir = Path(data_dir)
        self.models_dir = Path(models_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def validate_historical_data_quality(
        self, symbol: str, hist_data: pd.DataFrame, min_days: int = 252
    ) -> dict[str, Any]:
        """
        Validate historical data quality and completeness.

        Args:
            symbol: Ticker symbol
            hist_data: Historical data DataFrame
            min_days: Minimum days required

        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []

        # Check 1: Data exists
        if hist_data.empty:
            return {
                "valid": False,
                "symbol": symbol,
                "issues": ["No data available"],
                "warnings": [],
                "quality_score": 0.0,
            }

        # Check 2: Minimum days requirement
        if len(hist_data) < min_days:
            issues.append(f"Insufficient data: {len(hist_data)} days (need {min_days})")

        # Check 3: Date range completeness
        expected_days = self._calculate_expected_trading_days(hist_data)
        completeness = len(hist_data) / expected_days if expected_days > 0 else 0

        if completeness < self.MIN_DATA_COMPLETENESS:
            issues.append(
                f"Low completeness: {completeness:.1%} (expected {self.MIN_DATA_COMPLETENESS:.1%})"
            )

        # Check 4: Date gaps
        gaps = self._detect_date_gaps(hist_data)
        if gaps:
            max_gap = max(gap["days"] for gap in gaps)
            if max_gap > self.MAX_GAP_DAYS:
                issues.append(f"Large date gap: {max_gap} days")
            else:
                warnings.append(f"Date gaps detected: {len(gaps)} gaps (max {max_gap} days)")

        # Check 5: Missing required columns
        required_cols = ["Open", "High", "Low", "Close", "Volume"]
        missing_cols = [col for col in required_cols if col not in hist_data.columns]
        if missing_cols:
            issues.append(f"Missing columns: {missing_cols}")

        # Check 6: Data freshness (most recent date)
        if not hist_data.empty:
            latest_date = (
                hist_data.index[-1]
                if isinstance(hist_data.index[0], pd.Timestamp)
                else pd.to_datetime(hist_data.index[-1])
            )
            age_days = (datetime.now() - latest_date.to_pydatetime()).days

            if age_days > 30:
                warnings.append(f"Data is {age_days} days old (most recent: {latest_date.date()})")

        # Check 7: Outlier detection
        outliers = self._detect_outliers(hist_data)
        if outliers["count"] > 0:
            warnings.append(
                f"Outliers detected: {outliers['count']} rows "
                f"(max z-score: {outliers['max_zscore']:.2f})"
            )

        # Check 8: Data consistency (OHLC validation)
        consistency_issues = self._validate_ohlc_consistency(hist_data)
        if consistency_issues:
            issues.extend(consistency_issues)

        # Calculate quality score
        quality_score = self._calculate_quality_score(
            completeness=completeness,
            has_issues=len(issues) > 0,
            outlier_ratio=(outliers["count"] / len(hist_data) if not hist_data.empty else 0),
            gap_count=len(gaps),
        )

        return {
            "valid": len(issues) == 0,
            "symbol": symbol,
            "issues": issues,
            "warnings": warnings,
            "quality_score": quality_score,
            "metrics": {
                "days": len(hist_data),
                "completeness": completeness,
                "date_range": {
                    "start": str(hist_data.index[0]) if not hist_data.empty else None,
                    "end": str(hist_data.index[-1]) if not hist_data.empty else None,
                },
                "gaps": len(gaps),
                "outliers": outliers["count"],
                "age_days": age_days if not hist_data.empty else None,
            },
        }

    def rotate_old_historical_data(
        self, max_age_days: int = None, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Rotate (delete) historical data older than threshold.

        Args:
            max_age_days: Maximum age in days (default: MAX_DATA_AGE_DAYS)
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with rotation results
        """
        if max_age_days is None:
            max_age_days = self.MAX_DATA_AGE_DAYS

        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        deleted_files = []
        deleted_size = 0

        for csv_file in self.data_dir.glob("*.csv"):
            try:
                # Check file modification time
                file_mtime = datetime.fromtimestamp(csv_file.stat().st_mtime)

                # Also check data inside file
                df = pd.read_csv(csv_file, index_col=0, parse_dates=True, nrows=1)
                if not df.empty:
                    file_latest_date = (
                        df.index[-1]
                        if isinstance(df.index[0], pd.Timestamp)
                        else pd.to_datetime(df.index[-1])
                    )
                    file_latest_date = file_latest_date.to_pydatetime()

                    # Delete if file is old OR data inside is old
                    if file_mtime < cutoff_date or file_latest_date < cutoff_date:
                        file_size = csv_file.stat().st_size

                        if not dry_run:
                            csv_file.unlink()

                        deleted_files.append(
                            {
                                "file": csv_file.name,
                                "file_age_days": (datetime.now() - file_mtime).days,
                                "data_age_days": (datetime.now() - file_latest_date).days,
                                "size_kb": round(file_size / 1024, 2),
                            }
                        )
                        deleted_size += file_size
            except Exception as e:
                logger.warning(f"Error processing {csv_file}: {e}")

        return {
            "success": True,
            "dry_run": dry_run,
            "cutoff_date": cutoff_date.isoformat(),
            "files_deleted": len(deleted_files),
            "space_freed_mb": round(deleted_size / (1024 * 1024), 2),
            "deleted_files": deleted_files[:20],  # Limit to first 20
        }

    def check_model_staleness(self, model_path: str | None = None) -> dict[str, Any]:
        """
        Check if model is stale and needs retraining.

        Args:
            model_path: Path to model file (default: find latest)

        Returns:
            Dictionary with staleness check results
        """
        if model_path is None:
            # Find latest model
            model_files = list(self.models_dir.glob("lstm_feature_extractor*.pt"))
            if not model_files:
                return {
                    "stale": True,
                    "reason": "No model found",
                    "model_path": None,
                    "age_days": None,
                }

            model_path = max(model_files, key=lambda p: p.stat().st_mtime)

        model_path = Path(model_path)

        if not model_path.exists():
            return {
                "stale": True,
                "reason": "Model file not found",
                "model_path": str(model_path),
                "age_days": None,
            }

        # Check file age
        model_mtime = datetime.fromtimestamp(model_path.stat().st_mtime)
        age_days = (datetime.now() - model_mtime).days

        stale = age_days > self.MODEL_MAX_AGE_DAYS

        return {
            "stale": stale,
            "reason": f"Model is {age_days} days old" if stale else "Model is fresh",
            "model_path": str(model_path),
            "age_days": age_days,
            "max_age_days": self.MODEL_MAX_AGE_DAYS,
            "needs_retraining": stale,
        }

    def cleanup_stale_models(
        self, max_age_days: int = None, keep_latest: bool = True, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Clean up stale model files.

        Args:
            max_age_days: Maximum age in days (default: MODEL_MAX_AGE_DAYS * 2)
            keep_latest: If True, always keep the latest model
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleanup results
        """
        if max_age_days is None:
            max_age_days = self.MODEL_MAX_AGE_DAYS * 2

        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        model_files = list(self.models_dir.glob("lstm_feature_extractor*.pt"))

        if not model_files:
            return {
                "success": True,
                "files_deleted": 0,
                "message": "No model files found",
            }

        # Sort by modification time (newest first)
        model_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        deleted_files = []
        deleted_size = 0

        for i, model_file in enumerate(model_files):
            file_mtime = datetime.fromtimestamp(model_file.stat().st_mtime)

            # Skip latest model if keep_latest=True
            if keep_latest and i == 0:
                continue

            if file_mtime < cutoff_date:
                file_size = model_file.stat().st_size

                if not dry_run:
                    model_file.unlink()

                deleted_files.append(
                    {
                        "file": model_file.name,
                        "age_days": (datetime.now() - file_mtime).days,
                        "size_mb": round(file_size / (1024 * 1024), 2),
                    }
                )
                deleted_size += file_size

        return {
            "success": True,
            "dry_run": dry_run,
            "files_deleted": len(deleted_files),
            "space_freed_mb": round(deleted_size / (1024 * 1024), 2),
            "deleted_files": deleted_files,
            "kept_latest": keep_latest,
        }

    def run_full_hygiene_check(self, symbols: list[str] | None = None) -> dict[str, Any]:
        """
        Run comprehensive hygiene check on all data and models.

        Args:
            symbols: List of symbols to check (default: all in data_dir)

        Returns:
            Dictionary with full hygiene report
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "data_validation": {},
            "model_staleness": {},
            "recommendations": [],
        }

        # Find symbols if not provided
        if symbols is None:
            csv_files = list(self.data_dir.glob("*.csv"))
            symbols = list(set(f.name.split("_")[0] for f in csv_files))

        # Validate each symbol's data
        from src.utils.data_collector import DataCollector

        collector = DataCollector(data_dir=str(self.data_dir))

        for symbol in symbols:
            hist_data = collector.load_historical_data(symbol)
            validation = self.validate_historical_data_quality(symbol, hist_data)
            report["data_validation"][symbol] = validation

            if not validation["valid"]:
                report["recommendations"].append(
                    f"Fix data quality issues for {symbol}: {', '.join(validation['issues'])}"
                )

        # Check model staleness
        model_check = self.check_model_staleness()
        report["model_staleness"] = model_check

        if model_check["stale"]:
            report["recommendations"].append(f"Retrain model: {model_check['reason']}")

        return report

    # Helper methods

    def _calculate_expected_trading_days(self, hist_data: pd.DataFrame) -> int:
        """Calculate expected number of trading days in date range."""
        if hist_data.empty:
            return 0

        start_date = (
            hist_data.index[0]
            if isinstance(hist_data.index[0], pd.Timestamp)
            else pd.to_datetime(hist_data.index[0])
        )
        end_date = (
            hist_data.index[-1]
            if isinstance(hist_data.index[-1], pd.Timestamp)
            else pd.to_datetime(hist_data.index[-1])
        )

        # Approximate: ~252 trading days per year
        days_diff = (end_date - start_date).days
        expected = int(days_diff * 252 / 365)

        return max(expected, len(hist_data))  # At least as many as we have

    def _detect_date_gaps(self, hist_data: pd.DataFrame) -> list[dict[str, Any]]:
        """Detect gaps in date sequence."""
        if hist_data.empty or len(hist_data) < 2:
            return []

        gaps = []
        dates = pd.to_datetime(hist_data.index).sort_values()
        dates_list = list(dates)  # Convert to list for indexing

        for i in range(len(dates_list) - 1):
            gap_days = (dates_list[i + 1] - dates_list[i]).days

            if gap_days > 1:  # More than 1 day gap
                gaps.append(
                    {
                        "start": str(dates_list[i]),
                        "end": str(dates_list[i + 1]),
                        "days": gap_days,
                    }
                )

        return gaps

    def _detect_outliers(self, hist_data: pd.DataFrame) -> dict[str, Any]:
        """Detect statistical outliers in price data."""
        if hist_data.empty or "Close" not in hist_data.columns:
            return {"count": 0, "max_zscore": 0.0}

        prices = hist_data["Close"].values

        # Calculate z-scores
        mean_price = np.mean(prices)
        std_price = np.std(prices)

        if std_price == 0:
            return {"count": 0, "max_zscore": 0.0}

        z_scores = np.abs((prices - mean_price) / std_price)
        outliers = z_scores > self.MAX_OUTLIER_ZSCORE

        return {"count": int(np.sum(outliers)), "max_zscore": float(np.max(z_scores))}

    def _validate_ohlc_consistency(self, hist_data: pd.DataFrame) -> list[str]:
        """Validate OHLC data consistency."""
        issues = []

        required_cols = ["Open", "High", "Low", "Close"]
        if not all(col in hist_data.columns for col in required_cols):
            return issues  # Already checked elsewhere

        # High >= Low
        invalid_hl = (hist_data["High"] < hist_data["Low"]).sum()
        if invalid_hl > 0:
            issues.append(f"High < Low in {invalid_hl} rows")

        # High >= Open, Close
        invalid_ho = (hist_data["High"] < hist_data["Open"]).sum()
        invalid_hc = (hist_data["High"] < hist_data["Close"]).sum()
        if invalid_ho > 0 or invalid_hc > 0:
            issues.append(f"High < Open/Close in {invalid_ho + invalid_hc} rows")

        # Low <= Open, Close
        invalid_lo = (hist_data["Low"] > hist_data["Open"]).sum()
        invalid_lc = (hist_data["Low"] > hist_data["Close"]).sum()
        if invalid_lo > 0 or invalid_lc > 0:
            issues.append(f"Low > Open/Close in {invalid_lo + invalid_lc} rows")

        return issues

    def _calculate_quality_score(
        self,
        completeness: float,
        has_issues: bool,
        outlier_ratio: float,
        gap_count: int,
    ) -> float:
        """Calculate overall data quality score (0.0 to 1.0)."""
        score = completeness * 0.5  # Base score from completeness

        if not has_issues:
            score += 0.3  # Bonus for no critical issues

        # Penalize outliers
        score -= min(outlier_ratio * 0.1, 0.1)

        # Penalize gaps
        score -= min(gap_count * 0.01, 0.1)

        return max(0.0, min(1.0, score))
