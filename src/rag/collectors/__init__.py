# FRED Collector module exports
from src.rag.collectors.fred_collector import FREDCollector

# Backward compatibility alias (camelCase)
FredCollector = FREDCollector

__all__ = ["FREDCollector", "FredCollector"]
