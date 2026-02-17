from scripts.generate_judge_demo_page import _snapshot_html


def test_snapshot_html_uses_defaults_when_manifest_missing() -> None:
    html = _snapshot_html({})
    assert "Most Important Screenshot (Tetrate Evidence)" in html
    assert "/trading/assets/snapshots/judge_tetrate_metrics_latest.png" in html
    assert "/trading/lessons/ops-status.html" in html
    assert "Captured: unknown" in html


def test_snapshot_html_uses_manifest_urls() -> None:
    manifest = {
        "latest": {
            "alpaca_paper": {
                "url": "/trading/assets/snapshots/alpaca_paper_20260216_191010.png",
                "diagram_url": "/trading/assets/snapshots/paperbanana_paper_20260216_191010.svg",
                "captured_at_utc": "2026-02-16T19:10:10Z",
                "technical_explainer": "paper technical summary",
            },
            "alpaca_live": {
                "url": "/trading/assets/snapshots/alpaca_live_20260216_191010.png",
                "diagram_url": "/trading/assets/snapshots/paperbanana_live_20260216_191010.svg",
                "captured_at_utc": "2026-02-16T19:10:10Z",
                "technical_explainer": "live technical summary",
            },
            "progress": {
                "url": "/trading/assets/snapshots/progress_20260216_191010.png",
                "captured_at_utc": "2026-02-16T19:10:10Z",
            },
        }
    }

    html = _snapshot_html(manifest)

    assert "Most Important Screenshot (Tetrate Evidence)" in html
    assert "/trading/assets/snapshots/judge_tetrate_metrics_latest.png" in html
    assert "/trading/lessons/ops-status.html" in html
    assert "2026-02-16T19:10:10Z" in html
