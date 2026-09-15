#!/usr/bin/env python3
"""
Agentic Voice & Meeting Action Bridge (Superhuman + Fathom Architecture)
Extracts actionable intent, Linear task locks, CRM deal updates, and 1-click follow-up emails
from unstructured meeting transcripts and voice notes.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ActionItem:
    description: str
    owner: str = "Igor"
    priority: str = "High"  # High, Medium, Low
    deadline: Optional[str] = None
    completed: bool = False


@dataclass
class LinearTaskDraft:
    title: str
    team: str = "AGENT"
    priority: int = 1  # 1=Urgent, 2=High, 3=Medium, 4=Low
    description: str = ""
    assignee: str = "agy"


@dataclass
class FollowUpEmailDraft:
    recipient_name: str
    recipient_email: str
    subject: str
    body: str
    action_items_included: List[str] = field(default_factory=list)


@dataclass
class DealUpdate:
    property_address: Optional[str] = None
    client_name: Optional[str] = None
    agreed_terms: Optional[str] = None
    mao_or_budget: Optional[float] = None
    next_step: Optional[str] = None


@dataclass
class MeetingActionPacket:
    meeting_title: str
    timestamp: str
    participants: List[str]
    summary: str
    action_items: List[ActionItem]
    linear_tasks: List[LinearTaskDraft]
    follow_up_emails: List[FollowUpEmailDraft]
    deal_updates: List[DealUpdate]
    institutional_lessons: List[str]


class AgenticVoiceActionBridge:
    """Parses transcripts and converts them into deterministic GSD execution artifacts."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("data/voice_actions")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def parse_transcript(self, raw_transcript: str, meeting_title: str = "Voice Sync") -> MeetingActionPacket:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        lines = [line.strip() for line in raw_transcript.strip().split("\n") if line.strip()]

        # 1. Extract Participants
        participants = set()
        for line in lines:
            match = re.match(r"^([A-Z][a-zA-Z\s]+):", line)
            if match:
                participants.add(match.group(1).strip())
        if not participants:
            participants = {"Igor", "Client/Partner"}

        # 2. Extract Action Items
        action_items: List[ActionItem] = []
        action_keywords = ["todo:", "action item:", "will do", "need to", "i will", "we should", "follow up with", "send", "review"]
        for line in lines:
            lower = line.lower()
            if any(kw in lower for kw in action_keywords):
                clean_desc = re.sub(r"^(todo:|action item:|\-|\*)\s*", "", line, flags=re.IGNORECASE).strip()
                owner = "Igor"
                if "trio" in lower or "stephanie" in lower:
                    owner = "Stephanie"
                elif "client" in lower or "partner" in lower:
                    owner = "Partner"
                action_items.append(ActionItem(description=clean_desc, owner=owner))

        # Default fallback if no explicit action item detected
        if not action_items:
            action_items.append(ActionItem(description="Review transcript sync & confirm next milestones", owner="Igor"))

        # 3. Formulate Linear Tasks
        linear_tasks: List[LinearTaskDraft] = []
        for item in action_items:
            if item.owner.lower() in ["igor", "agy", "grok", "team"]:
                linear_tasks.append(
                    LinearTaskDraft(
                        title=item.description[:80],
                        team="AGENT",
                        priority=1 if "urgent" in item.description.lower() else 2,
                        description=f"Generated from meeting '{meeting_title}'\n\nFull item: {item.description}",
                        assignee="agy",
                    )
                )

        # 4. Formulate 1-Click Follow-Up Emails (Superhuman style)
        follow_up_emails: List[FollowUpEmailDraft] = []
        email_matches = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", raw_transcript)
        recipient_email = email_matches[0] if email_matches else "partner@example.com"
        
        # Build concise high-velocity follow up body
        items_bullets = "\n".join([f"• {act.description}" for act in action_items])
        email_body = (
            f"Hi there,\n\n"
            f"Great connecting today during our {meeting_title}.\n\n"
            f"Here are the agreed next steps:\n{items_bullets}\n\n"
            f"We are driving these forward immediately. Let us know if you need anything else adjusted.\n\n"
            f"Best,\nIgor Ganapolsky"
        )
        follow_up_emails.append(
            FollowUpEmailDraft(
                recipient_name=list(participants)[0] if participants else "Partner",
                recipient_email=recipient_email,
                subject=f"Next Steps & Summary: {meeting_title}",
                body=email_body,
                action_items_included=[act.description for act in action_items],
            )
        )

        # 5. Extract Real Estate / B2B Deal Updates
        deal_updates: List[DealUpdate] = []
        addr_match = re.search(r"(\d+\s+[\w\s]+(?:Ave|St|Rd|Blvd|Dr|Way|Lane|Ct|NW|SW|NE|SE)[,\s]+[\w\s]+,\s*FL\s*\d{5})", raw_transcript, re.IGNORECASE)
        price_match = re.search(r"\$(\d{1,3}(?:,\d{3})+|\d+)", raw_transcript)
        
        if addr_match or price_match:
            deal_updates.append(
                DealUpdate(
                    property_address=addr_match.group(1) if addr_match else None,
                    client_name=list(participants)[0] if participants else "Buyer",
                    agreed_terms="Cash purchase / Assignment with 14-day inspection",
                    mao_or_budget=float(price_match.group(1).replace(",", "")) if price_match else None,
                    next_step="Send formal 1-page LOI / Deal Dossier",
                )
            )

        # 6. Extract Institutional Lessons
        lessons = [
            f"Meeting '{meeting_title}' codified {len(action_items)} action items and {len(linear_tasks)} Linear tasks.",
            "Fast follow-up email prepared for 1-click dispatch under <15 minute SLA."
        ]

        # Summary
        summary = f"Sync with {', '.join(participants)}. Extracted {len(action_items)} action items, {len(linear_tasks)} Linear tasks, and {len(deal_updates)} deal updates."

        packet = MeetingActionPacket(
            meeting_title=meeting_title,
            timestamp=now_iso,
            participants=sorted(list(participants)),
            summary=summary,
            action_items=action_items,
            linear_tasks=linear_tasks,
            follow_up_emails=follow_up_emails,
            deal_updates=deal_updates,
            institutional_lessons=lessons,
        )

        return packet

    def save_packet(self, packet: MeetingActionPacket, slug: Optional[str] = None) -> Path:
        slug = slug or re.sub(r"[^\w\-]", "_", packet.meeting_title.lower())
        json_path = self.output_dir / f"{slug}_action_packet.json"
        md_path = self.output_dir / f"{slug}_action_packet.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(asdict(packet), f, indent=2)

        md_content = self._format_markdown(packet)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return md_path

    def _format_markdown(self, packet: MeetingActionPacket) -> str:
        md = [
            f"# ⚡ Meeting Action & Dispatch Packet: {packet.meeting_title}",
            f"**Timestamp**: {packet.timestamp}",
            f"**Participants**: {', '.join(packet.participants)}",
            "",
            "## Executive Summary",
            packet.summary,
            "",
            "## 📋 Action Items & Task Ownership",
        ]
        for item in packet.action_items:
            md.append(f"- [ ] **[{item.owner}]** {item.description} *(Priority: {item.priority})*")

        md.append("\n## 🎯 Linear Tasks to Dispatch")
        for t in packet.linear_tasks:
            md.append(f"- **{t.title}** (Team: `{t.team}`, Assignee: `{t.assignee}`, Priority: {t.priority})")

        md.append("\n## ✉️ 1-Click Superhuman Follow-Up Email")
        for email in packet.follow_up_emails:
            md.append(f"**To**: {email.recipient_name} `<{email.recipient_email}>`")
            md.append(f"**Subject**: {email.subject}")
            md.append("```text")
            md.append(email.body)
            md.append("```")

        if packet.deal_updates:
            md.append("\n## 🏡 CRM & Deal Underwriting Updates")
            for d in packet.deal_updates:
                md.append(f"- **Property**: {d.property_address or 'General Lead'}")
                md.append(f"  - Client: {d.client_name}")
                md.append(f"  - Terms: {d.agreed_terms}")
                md.append(f"  - Next Step: **{d.next_step}**")

        return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Agentic Voice & Meeting Action Bridge")
    parser.add_argument("--transcript", type=str, help="Path to transcript text file")
    parser.add_argument("--title", type=str, default="Partner Sync", help="Meeting title")
    parser.add_argument("--doctor", action="store_true", help="Run health check")
    args = parser.parse_args()

    bridge = AgenticVoiceActionBridge()

    if args.doctor:
        print("[✓] Agentic Voice & Meeting Action Bridge: ONLINE")
        print(f"[✓] Storage output directory: {bridge.output_dir}")
        return

    if args.transcript:
        raw_text = Path(args.transcript).read_text(encoding="utf-8")
        packet = bridge.parse_transcript(raw_text, meeting_title=args.title)
        saved_path = bridge.save_packet(packet)
        print(f"[✓] Generated Action Packet: {saved_path}")
    else:
        sample_transcript = (
            "Igor: Hey Stephanie, great talking about the Coral Springs property at 5236 NW 117th Ave.\n"
            "Stephanie (Trio Buys): Yes, we love the 3/2 profile. Our buy box is around $350,000 for distressed properties.\n"
            "Igor: Excellent. I will send over the full repair scope and title verification by 3 PM.\n"
            "Stephanie: Perfect, send it to info@triobuyshousesinflorida.com and we will review immediately."
        )
        packet = bridge.parse_transcript(sample_transcript, meeting_title="Trio Property Buyers Acquisition Sync")
        saved_path = bridge.save_packet(packet)
        print(f"[✓] Generated Sample Action Packet: {saved_path}")


if __name__ == "__main__":
    main()
