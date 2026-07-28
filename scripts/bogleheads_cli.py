#!/usr/bin/env python3
"""Bogleheads Forum Engagement & Posting CLI.

Allows drafting and posting replies to Bogleheads.org forum threads directly from CLI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tools.bogleheads_poster import BogleheadsPoster


def main() -> int:
    parser = argparse.ArgumentParser(description="Bogleheads Forum Engagement CLI")
    parser.add_argument("--topic-id", required=True, help="Bogleheads topic ID (e.g. 8819131)")
    parser.add_argument("--title", default="Bogleheads Community Discussion", help="Topic title")
    parser.add_argument("--message", required=True, help="Reply message text")
    parser.add_argument("--post", action="store_true", help="Post immediately to Bogleheads")

    args = parser.parse_args()
    poster = BogleheadsPoster()
    draft = poster.draft_reply(topic_id=args.topic_id, topic_title=args.title, reply_text=args.message)

    if args.post:
        result = poster.post_reply(draft)
        print("✅ Reply Submitted Successfully:")
        print(json.dumps(result, indent=2))
    else:
        print("📝 Draft Created (Use --post to publish):")
        print(json.dumps(dict(topic_id=draft.topic_id, title=draft.topic_title, reply=draft.reply_text), indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
