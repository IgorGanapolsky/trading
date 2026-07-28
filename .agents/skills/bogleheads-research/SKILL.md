---
name: bogleheads-research
description: Bogleheads Forum Research & Active Thread Engagement Engine
---

# Bogleheads Research & Active Engagement Skill

Extracts real-time discussions and actively engages in Bogleheads.org forum threads.

## Capabilities

1. **RSS Feed Extractor**:
   ```bash
   python3 scripts/bogleheads_research.py
   ```
   Parses latest 15 forum discussions into `data/research/bogleheads_latest.json`.

2. **Drafting & Submitting Thread Replies**:
   ```bash
   python3 scripts/bogleheads_cli.py --topic-id 8819131 --title "Asset Allocation" --message "A 3-fund portfolio (VTI/VXUS/BND) offers low expense ratio diversification." --post
   ```

3. **Audit Log & Secrets**:
   - Outgoing posts logged to `data/audit/bogleheads_posts.json`.
   - Forum credentials stored securely in `~/.resume_secrets/bogleheads.json` (`chmod 0600`).
