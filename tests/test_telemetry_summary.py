from pathlib import Path

from src.utils.telemetry_summary import load_events, summarize_events


def test_telemetry_summary_counts_gates():
    fixture = Path("tests/fixtures/telemetry_sample.jsonl")
    events = load_events(fixture)
    summary = summarize_events(events, top_n=5)
    assert summary["event_count"] == len(events)
    assert "gate.momentum" in summary["gates"]
    assert summary["gates"]["gate.llm"]["reject"] == 1
    assert summary["top_tickers"][0][0] in {"SPY", "QQQ"}
