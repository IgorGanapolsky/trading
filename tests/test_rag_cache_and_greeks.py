from src.rag.rag_cache import RAGQueryCache
from src.analysis.options_greeks_analyzer import OptionsGreeksAnalyzer


def test_rag_query_cache_hit_and_miss():
    cache = RAGQueryCache(capacity=10, ttl_seconds=60.0)
    assert cache.get("iron condor") is None

    cache.put("iron condor", ["LL-323", "LL-301"], latency_ms=45.0)
    res = cache.get("iron condor")
    assert res == ["LL-323", "LL-301"]
    assert cache.hits == 1
    assert cache.misses == 1


def test_options_greeks_analyzer_put_delta():
    analyzer = OptionsGreeksAnalyzer()
    greeks = analyzer.calculate_greeks(
        underlying_price=550.0,
        strike_price=520.0,
        dte=45,
        iv=0.18,
        option_type="put",
    )

    assert greeks.underlying_price == 550.0
    assert greeks.strike_price == 520.0
    assert -0.25 <= greeks.delta <= -0.05
    assert greeks.theta < 0.0
