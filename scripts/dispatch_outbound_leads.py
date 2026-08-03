"""Outbound Lead Dispatcher & Staging Tool.

Formats target leads into ready-to-dispatch outreach packages and stages
them directly to ~/Downloads/OUTBOUND_LEADS_DISPATCH.txt.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"
MANIFEST_FILE = ROOT / "data" / "revenue" / "outbound_target_leads.json"
DISPATCH_FILE = DOWNLOADS / "OUTBOUND_LEADS_DISPATCH.txt"


def dispatch_leads() -> Path:
    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"Lead manifest missing at {MANIFEST_FILE}")

    with MANIFEST_FILE.open("r", encoding="utf-8") as h:
        leads = json.load(h)

    output = []
    output.append("============================================================")
    output.append("📬 OUTBOUND LEADS DISPATCH PACKAGE")
    output.append("============================================================\n")

    for i, lead in enumerate(leads, 1):
        output.append(f"LEAD #{i}: {lead['name']} ({lead['company']})")
        output.append(f"Title     : {lead['title']}")
        output.append(f"Niche     : {lead['niche']}")
        output.append(f"Channel   : {lead['channel']}")
        output.append(f"Offer Tier: {lead['offer_tier']}")
        output.append("--- PERSONALIZED MESSAGE DRAFT ---")
        output.append(lead["personalized_dm"])
        output.append("\n" + "=" * 60 + "\n")

    DISPATCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    DISPATCH_FILE.write_text("\n".join(output), encoding="utf-8")
    return DISPATCH_FILE


if __name__ == "__main__":
    path = dispatch_leads()
    print(f"✅ Dispatched {path}")
