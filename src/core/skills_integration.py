"""
Claude Skills Integration Module
Wraps all Claude Skills for use in trading orchestrator
"""

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class SkillsIntegration:
    """Integration wrapper for all Claude Skills"""

    def __init__(self):
        """Initialize all skill modules"""
        self.sentiment_analyzer = None
        self.position_sizer = None
        self.anomaly_detector = None
        self.performance_monitor = None
        self.financial_data_fetcher = None
        self.portfolio_risk_assessor = None

        self._initialize_skills()

    def _initialize_skills(self):
        """Lazy load skill modules"""
        skills_path = project_root / ".claude" / "skills"

        # Add all skill script directories to path
        for skill_dir in skills_path.iterdir():
            if skill_dir.is_dir() and (skill_dir / "scripts").exists():
                sys.path.insert(0, str(skill_dir / "scripts"))

        try:
            # Sentiment Analyzer
            import sentiment_analyzer

            self.sentiment_analyzer = sentiment_analyzer.SentimentAnalyzer()
            logger.info("✅ Sentiment Analyzer skill loaded")
        except Exception as e:
            logger.warning(f"⚠️ Could not load Sentiment Analyzer skill: {e}")

        try:
            # Position Sizer
            import position_sizer

            self.position_sizer = position_sizer.PositionSizer()
            logger.info("✅ Position Sizer skill loaded")
        except Exception as e:
            logger.warning(f"⚠️ Could not load Position Sizer skill: {e}")

        try:
            # Anomaly Detector
            import anomaly_detector

            self.anomaly_detector = anomaly_detector.AnomalyDetector()
            logger.info("✅ Anomaly Detector skill loaded")
        except Exception as e:
            logger.warning(f"⚠️ Could not load Anomaly Detector skill: {e}")

        try:
            # Performance Monitor
            import performance_monitor

            self.performance_monitor = performance_monitor.PerformanceMonitor()
            logger.info("✅ Performance Monitor skill loaded")
        except Exception as e:
            logger.warning(f"⚠️ Could not load Performance Monitor skill: {e}")

        try:
            # Financial Data Fetcher
            import fetch_data

            self.financial_data_fetcher = fetch_data.FinancialDataFetcher()
            logger.info("✅ Financial Data Fetcher skill loaded")
        except Exception as e:
            logger.warning(f"⚠️ Could not load Financial Data Fetcher skill: {e}")

        try:
            # Portfolio Risk Assessment
            import risk_assessment

            self.portfolio_risk_assessor = risk_assessment.PortfolioRiskAssessor()
            logger.info("✅ Portfolio Risk Assessment skill loaded")
        except Exception as e:
            logger.warning(f"⚠️ Could not load Portfolio Risk Assessment skill: {e}")

    def get_sentiment(self, symbols: list[str]) -> dict[str, Any]:
        """Get composite sentiment for symbols"""
        if not self.sentiment_analyzer:
            return {"success": False, "error": "Sentiment Analyzer not available"}
        return self.sentiment_analyzer.get_composite_sentiment(symbols=symbols)

    def calculate_position(self, symbol: str, account_value: float, **kwargs) -> dict[str, Any]:
        """Calculate position size"""
        if not self.position_sizer:
            return {"success": False, "error": "Position Sizer not available"}
        return self.position_sizer.calculate_position_size(
            symbol=symbol, account_value=account_value, **kwargs
        )

    def detect_execution_anomalies(
        self,
        order_id: str,
        expected_price: float,
        actual_fill_price: float,
        quantity: float,
        order_type: str,
        timestamp: str,
    ) -> dict[str, Any]:
        """Detect execution anomalies"""
        if not self.anomaly_detector:
            return {"success": False, "error": "Anomaly Detector not available"}
        return self.anomaly_detector.detect_execution_anomalies(
            order_id=order_id,
            expected_price=expected_price,
            actual_fill_price=actual_fill_price,
            quantity=quantity,
            order_type=order_type,
            timestamp=timestamp,
        )

    def get_performance_metrics(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        benchmark_symbol: str = "SPY",
    ) -> dict[str, Any]:
        """Get performance metrics"""
        if not self.performance_monitor:
            return {"success": False, "error": "Performance Monitor not available"}
        return self.performance_monitor.calculate_performance_metrics(
            start_date=start_date, end_date=end_date, benchmark_symbol=benchmark_symbol
        )

    def assess_portfolio_health(self) -> dict[str, Any]:
        """Assess portfolio health"""
        if not self.portfolio_risk_assessor:
            return {"success": False, "error": "Portfolio Risk Assessor not available"}
        return self.portfolio_risk_assessor.assess_portfolio_health()

    def get_price_data(self, symbols: list[str], **kwargs) -> dict[str, Any]:
        """Get price data"""
        if not self.financial_data_fetcher:
            return {"success": False, "error": "Financial Data Fetcher not available"}
        return self.financial_data_fetcher.get_price_data(symbols=symbols, **kwargs)


# Global instance
_skills_instance: SkillsIntegration | None = None


def get_skills() -> SkillsIntegration:
    """Get global skills instance"""
    global _skills_instance
    if _skills_instance is None:
        _skills_instance = SkillsIntegration()
    return _skills_instance
