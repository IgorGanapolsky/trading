import pytest
from pathlib import Path
from src.revenue.outbound_lead_generator import OutboundLeadGenerator, TARGET_PROSPECTS


def test_lead_manifest_generation(tmp_path):
    generator = OutboundLeadGenerator()
    leads = generator.generate_lead_manifest()

    assert len(leads) >= 3
    assert leads[0]["prospect_id"] == "LEAD-001"
    assert leads[0]["company"] == "Apex Outbound Agency"
    assert "autonomous AI" in leads[0]["personalized_dm"]


def test_stage_pitch_deck_to_downloads():
    generator = OutboundLeadGenerator()
    dest = generator.stage_pitch_deck_to_downloads()

    assert dest.exists()
    content = dest.read_text(encoding="utf-8")
    assert "Autonomous AI Ops" in content
    assert "Loom Video Demo Script" in content
