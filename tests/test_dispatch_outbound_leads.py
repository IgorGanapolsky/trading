from scripts.dispatch_outbound_leads import dispatch_leads


def test_dispatch_leads_creates_file():
    dest = dispatch_leads()
    assert dest.exists()
    content = dest.read_text(encoding="utf-8")
    assert "OUTBOUND LEADS DISPATCH PACKAGE" in content
    assert "Alex Rivera" in content
