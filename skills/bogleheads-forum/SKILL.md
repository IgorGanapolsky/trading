---
name: bogleheads-forum
description: >
  Trading-repo Bogleheads research/ingest via RSS and optional logged-in forum use
  (Keychain eazyigz @ bogleheads.org). Trigger: Bogleheads, passive forum, three-fund,
  bogleheads_research. Slash: /bogleheads-forum.
---

# Bogleheads (trading repo)

Canonical full skill: `~/.grok/skills/bogleheads-forum/SKILL.md`.

## Quick commands

```bash
python3 scripts/bogleheads_research.py
# output: data/research/bogleheads_latest.json
```

Credentials: Keychain `bogleheads.org` / `eazyigz` (never in git).

Ingest into lessons only after secret scrub + quality_gate. Not an edge claim.
