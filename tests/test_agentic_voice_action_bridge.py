#!/usr/bin/env python3
"""
Unit tests for Agentic Voice & Meeting Action Bridge (Superhuman + Fathom Architecture).
"""

from pathlib import Path

from scripts.agentic_voice_action_bridge import AgenticVoiceActionBridge


def test_agentic_voice_action_bridge_initialization(tmp_path: Path):
    bridge = AgenticVoiceActionBridge(output_dir=tmp_path)
    assert bridge.output_dir == tmp_path
    assert tmp_path.exists()


def test_parse_transcript_action_items_and_tasks(tmp_path: Path):
    bridge = AgenticVoiceActionBridge(output_dir=tmp_path)
    raw_transcript = (
        "Igor: We need to finalize the ThumbGate $3,000 partner pilot contract.\n"
        "Alex (LegalTech CTO): Sounds great, send the Stripe invoice to alex@legaltech.io and we will sign today.\n"
        "Igor: I will configure the pre-action interdiction proxy and verify the test harness."
    )
    packet = bridge.parse_transcript(raw_transcript, meeting_title="LegalTech Pilot Closing Call")

    assert packet.meeting_title == "LegalTech Pilot Closing Call"
    assert len(packet.participants) >= 1
    assert len(packet.action_items) >= 2
    assert len(packet.linear_tasks) >= 1
    assert len(packet.follow_up_emails) == 1
    assert packet.follow_up_emails[0].recipient_email == "alex@legaltech.io"
    assert "LegalTech Pilot Closing Call" in packet.follow_up_emails[0].subject


def test_parse_transcript_real_estate_deal_extraction(tmp_path: Path):
    bridge = AgenticVoiceActionBridge(output_dir=tmp_path)
    raw_transcript = (
        "Igor: Let us review 5236 NW 117th Ave, Coral Springs, FL 33076.\n"
        "Stephanie: We can close at $350,000 cash if inspection passes."
    )
    packet = bridge.parse_transcript(raw_transcript, meeting_title="Coral Springs Acquisition Review")

    assert len(packet.deal_updates) == 1
    deal = packet.deal_updates[0]
    assert "5236 NW 117th Ave" in (deal.property_address or "")
    assert deal.mao_or_budget == 350000.0


def test_save_packet_generates_json_and_markdown(tmp_path: Path):
    bridge = AgenticVoiceActionBridge(output_dir=tmp_path)
    sample_transcript = "Igor: Need to deploy the new CodeQL action v4.38.0 and verify CI."
    packet = bridge.parse_transcript(sample_transcript, meeting_title="Security Ops Sync")

    md_path = bridge.save_packet(packet, slug="security_ops_sync")
    json_path = tmp_path / "security_ops_sync_action_packet.json"

    assert md_path.exists()
    assert json_path.exists()

    content = md_path.read_text(encoding="utf-8")
    assert "Security Ops Sync" in content
    assert "Linear Tasks" in content
    assert "Superhuman Follow-Up Email" in content
