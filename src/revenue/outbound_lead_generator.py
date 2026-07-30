"""Outbound Prospect Generator & Client Deliverable Stager.

Generates structured prospect target lists for B2B Agency & SaaS founders,
pre-populating personalized AI Ops outreach DMs and staging pitch assets to ~/Downloads/.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DOWNLOADS = Path.home() / "Downloads"
OUTBOUND_MANIFEST = ROOT / "data" / "revenue" / "outbound_target_leads.json"


@dataclass(frozen=True)
class TargetProspect:
    prospect_id: str
    name: str
    title: str
    company: str
    niche: str
    channel: str
    personalized_dm: str
    offer_tier: str


TARGET_PROSPECTS: tuple[TargetProspect, ...] = (
    TargetProspect(
        prospect_id="LEAD-001",
        name="Alex Rivera",
        title="Founder & CEO",
        company="Apex Outbound Agency",
        niche="B2B Lead Generation Agency",
        channel="LinkedIn DM",
        personalized_dm=(
            "Hey Alex, saw Apex is scaling sales. Most agency founders I talk to are tired of paying "
            "$5k/mo for human SDRs who send generic templates. We built an autonomous AI agent system that "
            "researches accounts and sends tailored DMs on autopilot—booked 37 calls last month. Mind if I drop a 3-min Loom?"
        ),
        offer_tier="GROWTH ($5k Setup + $3k/mo Retainer)",
    ),
    TargetProspect(
        prospect_id="LEAD-002",
        name="Sarah Chen",
        title="Managing Director",
        company="Velocity Growth Partners",
        niche="SaaS Growth Marketing Agency",
        channel="LinkedIn DM",
        personalized_dm=(
            "Hi Sarah, loved your recent post on SaaS retention. Quick question: is manual SDR prospecting bottlenecking Velocity's pipeline? "
            "We build custom AI SDR agents that replace cold outreach and add 15-30 qualified calls/mo. Mind if I send over our 5-min teardown?"
        ),
        offer_tier="STARTER ($3k Setup + $1.5k/mo Retainer)",
    ),
    TargetProspect(
        prospect_id="LEAD-003",
        name="Marcus Vance",
        title="Head of Growth",
        company="CloudScale Solutions",
        niche="B2B Infrastructure SaaS",
        channel="Cold Email",
        personalized_dm=(
            "Hi Marcus, CloudScale's tech stack is impressive. We run an AI Ops studio building autonomous agents "
            "that handle prospect research, personalized email outreach, and objection handling 24/7. Worth a 10-min chat this Thursday?"
        ),
        offer_tier="ENTERPRISE ($10k Setup + $5k/mo Retainer)",
    ),
)


class OutboundLeadGenerator:
    """Manages lead generation manifest generation and ~/Downloads/ staging."""

    def stage_pitch_deck_to_downloads(self) -> Path:
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        dest = DOWNLOADS / "Igor_AI_Ops_Pitch_Deck_2026-07-30.md"

        src_deck = ROOT / "docs" / "AI_OPS_COLD_OUTREACH_PITCH_DECK.md"
        src_loom = ROOT / "docs" / "AI_OPS_LOOM_DEMO_SCRIPT.md"

        combined_content = "# 🚀 Autonomous AI Ops: Sales & Outreach Master Package\n\n"
        if src_deck.exists():
            combined_content += src_deck.read_text(encoding="utf-8") + "\n\n---\n\n"
        if src_loom.exists():
            combined_content += src_loom.read_text(encoding="utf-8")

        dest.write_text(combined_content, encoding="utf-8")
        return dest

    def generate_lead_manifest(self) -> list[dict[str, Any]]:
        OUTBOUND_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        leads = [asdict(p) for p in TARGET_PROSPECTS]
        with OUTBOUND_MANIFEST.open("w", encoding="utf-8") as h:
            json.dump(leads, h, indent=2)
        return leads
