#!/usr/bin/env python3
"""
Options-Focused YouTube Channel Ingestion

Ingests options trading content from quality sources that align with
our cash-secured puts strategy (Phil Town + options education).

Channels:
- Option Alpha (Kirk Du Plessis) - Options mechanics
- InTheMoney (Adam) - Wheel strategy, CSPs
- SMB Capital - Professional options trading

Usage:
    python3 scripts/ingest_options_youtube.py --channel option-alpha --mode recent
    python3 scripts/ingest_options_youtube.py --all --mode recent
"""

import argparse
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Options-focused channels (using handles, not IDs - more reliable)
CHANNELS = {
    "option-alpha": {
        "name": "Option Alpha",
        "handle": "@optionalpha",
        "url": "https://www.youtube.com/@optionalpha",
        "focus": ["options basics", "premium selling", "probability"],
        "relevance": "high",  # Very aligned with CSP strategy
    },
    "inthemoney": {
        "name": "InTheMoney",
        "handle": "@InTheMoneyAdam",
        "url": "https://www.youtube.com/@InTheMoneyAdam",
        "focus": ["wheel strategy", "CSPs", "covered calls"],
        "relevance": "high",  # Wheel strategy expert
    },
    "tastylive": {
        "name": "tastylive",
        "handle": "@tastylive",
        "url": "https://www.youtube.com/@tastylive",
        "focus": ["options mechanics", "greeks", "volatility"],
        "relevance": "medium",  # Good education, more complex
    },
}

# Storage paths
RAG_OPTIONS = Path("rag_knowledge/youtube/options")
CACHE_FILE = Path("data/youtube_cache/options_videos.json")


def ensure_directories():
    """Create required directories."""
    RAG_OPTIONS.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_channel_videos(channel_url: str, max_results: int = 10) -> list[dict]:
    """Fetch video list from channel using yt-dlp.

    Args:
        channel_url: Full YouTube channel URL (e.g., https://www.youtube.com/@optionalpha)
        max_results: Maximum videos to fetch
    """
    try:
        import yt_dlp
    except ImportError:
        logger.error("yt-dlp not installed. Run: pip install yt-dlp")
        return []

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "playlistend": max_results,
    }

    # Ensure we're fetching from videos tab
    videos_url = channel_url.rstrip("/") + "/videos"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(videos_url, download=False)
            if not result or "entries" not in result:
                return []

            videos = []
            for entry in result["entries"][:max_results]:
                if entry:
                    videos.append({
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
                    })
            return videos
    except Exception as e:
        logger.error(f"Failed to fetch channel videos: {e}")
        return []


def get_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript for a video using youtube-transcript-api v1.0+."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
    except ImportError:
        logger.error("youtube-transcript-api not installed")
        return None

    try:
        # v1.0+ API requires instantiation
        ytt_api = YouTubeTranscriptApi()
        transcript_data = ytt_api.fetch(video_id)
        return " ".join([segment.text for segment in transcript_data])
    except (TranscriptsDisabled, NoTranscriptFound):
        logger.warning(f"No transcript available for {video_id}")
        return None
    except Exception as e:
        logger.warning(f"Transcript error for {video_id}: {e}")
        return None


def filter_options_relevant(title: str, transcript: str) -> bool:
    """Filter to only options-relevant content."""
    text = f"{title} {transcript}".lower()

    # Must-have terms (at least one)
    options_terms = [
        "put", "call", "option", "premium", "strike", "expiration",
        "wheel", "covered call", "cash-secured", "credit spread",
        "theta", "delta", "gamma", "vega", "implied volatility",
        "iron condor", "strangle", "straddle"
    ]

    # Exclude terms (skip video if present)
    exclude_terms = [
        "crypto", "bitcoin", "forex", "futures only", "day trading scalp"
    ]

    has_options = any(term in text for term in options_terms)
    has_exclude = any(term in text for term in exclude_terms)

    return has_options and not has_exclude


def save_transcript(channel_key: str, video: dict, transcript: str):
    """Save transcript to RAG knowledge base."""
    channel_dir = RAG_OPTIONS / channel_key
    channel_dir.mkdir(parents=True, exist_ok=True)

    # Create markdown file
    safe_title = re.sub(r'[^\w\s-]', '', video["title"])[:50]
    filename = f"{video['id']}_{safe_title}.md"
    filepath = channel_dir / filename

    content = f"""# {video['title']}

**Source**: {CHANNELS[channel_key]['name']}
**Video ID**: {video['id']}
**URL**: {video['url']}
**Ingested**: {datetime.now().isoformat()}
**Topics**: {', '.join(CHANNELS[channel_key]['focus'])}

---

## Transcript

{transcript}
"""

    filepath.write_text(content)
    logger.info(f"Saved: {filepath.name}")
    return filepath


def load_cache() -> dict:
    """Load processed videos cache."""
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {"processed": {}, "last_run": None}


def save_cache(cache: dict):
    """Save processed videos cache."""
    cache["last_run"] = datetime.now().isoformat()
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def ingest_channel(channel_key: str, mode: str = "recent", max_videos: int = 10) -> dict:
    """Ingest videos from a single channel."""
    if channel_key not in CHANNELS:
        logger.error(f"Unknown channel: {channel_key}")
        return {"error": f"Unknown channel: {channel_key}"}

    channel = CHANNELS[channel_key]
    cache = load_cache()

    if channel_key not in cache["processed"]:
        cache["processed"][channel_key] = []

    logger.info(f"Ingesting from {channel['name']}...")

    videos = get_channel_videos(channel["url"], max_videos)
    stats = {"fetched": len(videos), "processed": 0, "skipped": 0, "no_transcript": 0}

    for video in videos:
        if not video or not video.get("id"):
            continue

        # Skip if already processed
        if video["id"] in cache["processed"][channel_key]:
            stats["skipped"] += 1
            continue

        # Get transcript
        transcript = get_transcript(video["id"])
        if not transcript:
            stats["no_transcript"] += 1
            cache["processed"][channel_key].append(video["id"])
            continue

        # Filter for options relevance
        if not filter_options_relevant(video["title"], transcript):
            stats["skipped"] += 1
            cache["processed"][channel_key].append(video["id"])
            continue

        # Save to RAG
        save_transcript(channel_key, video, transcript)
        cache["processed"][channel_key].append(video["id"])
        stats["processed"] += 1

    save_cache(cache)
    return stats


def main():
    parser = argparse.ArgumentParser(description="Options YouTube Ingestion")
    parser.add_argument("--channel", type=str, choices=list(CHANNELS.keys()),
                        help="Specific channel to ingest")
    parser.add_argument("--all", action="store_true", help="Ingest from all channels")
    parser.add_argument("--mode", type=str, default="recent",
                        choices=["recent", "backfill"],
                        help="Ingestion mode")
    parser.add_argument("--max", type=int, default=10, help="Max videos per channel")
    parser.add_argument("--list", action="store_true", help="List available channels")
    args = parser.parse_args()

    if args.list:
        print("\nAvailable options channels:")
        for key, ch in CHANNELS.items():
            print(f"  {key}: {ch['name']} ({ch['relevance']} relevance)")
            print(f"    Focus: {', '.join(ch['focus'])}")
        return

    ensure_directories()

    if args.all:
        channels = list(CHANNELS.keys())
    elif args.channel:
        channels = [args.channel]
    else:
        # Default to high-relevance channels only
        channels = [k for k, v in CHANNELS.items() if v["relevance"] == "high"]

    max_videos = 50 if args.mode == "backfill" else args.max

    print(f"\n🎬 Options YouTube Ingestion")
    print(f"   Mode: {args.mode}")
    print(f"   Channels: {', '.join(channels)}")
    print()

    total_stats = {"processed": 0, "skipped": 0}

    for channel_key in channels:
        stats = ingest_channel(channel_key, args.mode, max_videos)
        if "error" not in stats:
            total_stats["processed"] += stats.get("processed", 0)
            total_stats["skipped"] += stats.get("skipped", 0)
            print(f"   {CHANNELS[channel_key]['name']}: {stats}")

    print(f"\n✅ Total: {total_stats['processed']} videos ingested, {total_stats['skipped']} skipped")


if __name__ == "__main__":
    main()
