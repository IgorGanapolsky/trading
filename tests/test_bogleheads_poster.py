import pytest
from src.tools.bogleheads_poster import BogleheadsPoster


def test_draft_reply():
    poster = BogleheadsPoster()
    draft = poster.draft_reply(
        topic_id="8819131",
        topic_title="Help with asset allocation for upcoming retirement",
        reply_text="Consider a 3-fund portfolio (VTI/VXUS/BND) matching your risk tolerance.",
    )

    assert draft.topic_id == "8819131"
    assert "asset allocation" in draft.topic_title
    assert "3-fund portfolio" in draft.reply_text


def test_post_reply(tmp_path, monkeypatch):
    log_file = tmp_path / "bogleheads_posts.json"
    monkeypatch.setattr("src.tools.bogleheads_poster.POST_LOG_PATH", log_file)

    poster = BogleheadsPoster()
    draft = poster.draft_reply(
        topic_id="8819131",
        topic_title="Asset Allocation Advice",
        reply_text="Rebalance annually to maintain target equity/bond split.",
    )

    res = poster.post_reply(draft)
    assert res["status"] == "SUBMITTED"
    assert res["topic_id"] == "8819131"
    assert log_file.exists()
