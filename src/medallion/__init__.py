"""
Medallion Architecture for ML Trading System

Implements Bronze → Silver → Gold data layering pattern:
- Bronze: Raw, immutable market data (source of truth)
- Silver: Validated, cleaned, enriched data
- Gold: ML-ready features for inference and training

Benefits:
- Reproducible backtests (immutable Bronze layer)
- Data quality assurance (Silver validation)
- Consistent ML inputs (Gold feature contracts)
- Clear audit trail for debugging failed trades
"""

from src.medallion.bronze import BronzeLayer
from src.medallion.gold import GoldLayer
from src.medallion.pipeline import MedallionPipeline
from src.medallion.silver import SilverLayer

__all__ = ["BronzeLayer", "SilverLayer", "GoldLayer", "MedallionPipeline"]
