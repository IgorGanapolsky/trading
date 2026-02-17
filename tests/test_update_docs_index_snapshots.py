from scripts.update_docs_index import build_snapshot_block


def test_build_snapshot_block_uses_manifest_diagrams_and_explainers() -> None:
    manifest = {
        "latest": {
            "alpaca_paper": {
                "url": "/trading/assets/snapshots/alpaca_paper_latest.png",
                "diagram_url": "/trading/assets/snapshots/paperbanana_paper_latest.svg",
                "captured_at_utc": "2026-02-16T19:10:10Z",
                "technical_explainer": "paper summary",
            },
            "alpaca_live": {
                "url": "/trading/assets/snapshots/alpaca_live_latest.png",
                "diagram_url": "/trading/assets/snapshots/paperbanana_live_latest.svg",
                "captured_at_utc": "2026-02-16T19:10:11Z",
                "technical_explainer": "live summary",
            },
            "progress": {
                "url": "/trading/assets/snapshots/progress_latest.png",
                "captured_at_utc": "2026-02-16T19:10:12Z",
            },
        }
    }

    block = build_snapshot_block(manifest)

    assert "AUTO_SNAPSHOT_START" in block
    assert "Progress Dashboard (Most Relevant)" in block
    assert "[Open full live dashboard](/trading/)" in block
    assert "/trading/assets/snapshots/progress_latest.png" in block
    assert "Raw manifest: [`/trading/data/alpaca_snapshots.json`](/trading/data/alpaca_snapshots.json)" in block
    assert "paper summary" not in block
    assert "live summary" not in block
