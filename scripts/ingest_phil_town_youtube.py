#!/usr/bin/env python3
"""
Phil Town YouTube Channel Ingestion Script

Fetches Phil Town's Rule #1 Investing videos using multiple methods:
1. YouTube Data API v3 (requires YOUTUBE_API_KEY - most reliable)
2. yt-dlp fallback (may be blocked by YouTube)
3. Curated video list fallback (always works)

Usage:
    python3 scripts/ingest_phil_town_youtube.py --mode recent
    python3 scripts/ingest_phil_town_youtube.py --mode backfill
    YOUTUBE_API_KEY=xxx python3 scripts/ingest_phil_town_youtube.py --mode recent

Channel: https://youtube.com/@philtownrule1investing
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Phil Town's channel info
CHANNEL_ID = "UC20qsVeyVXpGgGDmVKHH_4g"
CHANNEL_URL = "https://www.youtube.com/@philtownrule1investing"

# Storage paths
RAG_TRANSCRIPTS = Path("rag_knowledge/youtube/transcripts")
RAG_INSIGHTS = Path("rag_knowledge/youtube/insights")
CACHE_FILE = Path("data/youtube_cache/phil_town_videos.json")
PROCESSED_FILE = Path("data/youtube_cache/processed_videos.json")

# Curated list of Phil Town's best videos (fallback when API/scraping fails)
# These are verified Phil Town Rule #1 Investing videos
CURATED_VIDEOS = [
    {"id": "Rm69dKSsTrA", "title": "How to Invest in Stocks for Beginners 2024"},
    {"id": "gWIi6WLczZA", "title": "Warren Buffett: How to Invest for Beginners"},
    {"id": "K6CkCQU_qkE", "title": "The 4 Ms of Investing - Rule #1 Investing"},
    {"id": "8pPnLzZmKKY", "title": "What is a Moat in Investing?"},
    {"id": "A9kZ_fVwLLo", "title": "Margin of Safety Explained"},
    {"id": "kBGDLhMunVg", "title": "How to Calculate Intrinsic Value"},
    {"id": "WRF86rX2wXs", "title": "Cash Secured Puts Strategy"},
    {"id": "Hfq4K1nP4v4", "title": "The Wheel Strategy Explained"},
    {"id": "HcZRD3YUKZM", "title": "Value Investing vs Growth Investing"},
    {"id": "Z5chrxMuBoo", "title": "Rule #1: Don't Lose Money"},
    {"id": "9hWMAL0q-xw", "title": "How to Read Financial Statements"},
    {"id": "n2QVWD0xSJk", "title": "Best Stocks to Buy Now"},
    {"id": "nKNSPmHJzQA", "title": "Covered Calls for Income"},
    {"id": "2DujxkHgVvE", "title": "When to Sell a Stock"},
    {"id": "rFhDNe6lvkc", "title": "Options Trading for Beginners"},
]


def ensure_directories():
    """Create required directories."""
    RAG_TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    RAG_INSIGHTS.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_videos_via_youtube_api(max_results: int = 50) -> list[dict]:
    """
    Fetch videos using official YouTube Data API v3.
    Requires YOUTUBE_API_KEY environment variable.
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        logger.info("YOUTUBE_API_KEY not set, skipping API method")
        return []

    try:
        import requests

        # Get channel's uploads playlist
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "key": api_key,
            "id": CHANNEL_ID,
            "part": "contentDetails",
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("items"):
            logger.error("Channel not found via API")
            return []

        uploads_playlist = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Get videos from uploads playlist
        videos = []
        next_page = None

        while len(videos) < max_results:
            url = "https://www.googleapis.com/youtube/v3/playlistItems"
            params = {
                "key": api_key,
                "playlistId": uploads_playlist,
                "part": "snippet",
                "maxResults": min(50, max_results - len(videos)),
            }
            if next_page:
                params["pageToken"] = next_page

            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("items", []):
                snippet = item["snippet"]
                videos.append({
                    "id": snippet["resourceId"]["videoId"],
                    "title": snippet["title"],
                    "upload_date": snippet["publishedAt"][:10].replace("-", ""),
                    "url": f"https://www.youtube.com/watch?v={snippet['resourceId']['videoId']}",
                })

            next_page = data.get("nextPageToken")
            if not next_page:
                break

        logger.info(f"YouTube API: Found {len(videos)} videos")
        return videos

    except Exception as e:
        logger.error(f"YouTube API failed: {e}")
        return []


def get_videos_via_ytdlp(max_results: int = 50) -> list[dict]:
    """
    Fetch videos using yt-dlp (may be blocked by YouTube).
    """
    try:
        import subprocess

        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--no-check-certificate",
            "-j",
            f"--playlist-end={max_results}",
            f"{CHANNEL_URL}/videos",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        videos = []
        for line in result.stdout.strip().split("\n"):
            if line:
                try:
                    data = json.loads(line)
                    videos.append({
                        "id": data.get("id"),
                        "title": data.get("title"),
                        "upload_date": data.get("upload_date"),
                        "url": f"https://www.youtube.com/watch?v={data.get('id')}",
                    })
                except json.JSONDecodeError:
                    continue

        logger.info(f"yt-dlp: Found {len(videos)} videos")
        return videos

    except Exception as e:
        logger.warning(f"yt-dlp failed (may be blocked): {e}")
        return []


def get_videos_curated() -> list[dict]:
    """Return curated list of known Phil Town videos."""
    logger.info(f"Using curated list: {len(CURATED_VIDEOS)} videos")
    return [
        {
            "id": v["id"],
            "title": v["title"],
            "upload_date": "unknown",
            "url": f"https://www.youtube.com/watch?v={v['id']}",
        }
        for v in CURATED_VIDEOS
    ]


def get_channel_videos(max_results: int = 50) -> list[dict]:
    """
    Fetch videos using best available method.
    Priority: YouTube API > yt-dlp > curated list
    """
    # Try YouTube API first (most reliable if key available)
    videos = get_videos_via_youtube_api(max_results)
    if videos:
        return videos

    # Try yt-dlp (often blocked)
    videos = get_videos_via_ytdlp(max_results)
    if videos:
        return videos

    # Fall back to curated list
    logger.warning("All fetch methods failed, using curated video list")
    return get_videos_curated()


def get_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
        transcript_data = api.fetch(video_id)

        # Handle both old and new API formats
        if hasattr(transcript_data, 'snippets'):
            full_text = " ".join([s.text for s in transcript_data.snippets])
        elif hasattr(transcript_data, '__iter__'):
            full_text = " ".join([s.text if hasattr(s, 'text') else s.get('text', '') for s in transcript_data])
        else:
            full_text = str(transcript_data)

        logger.info(f"Got transcript for {video_id}: {len(full_text)} chars")
        return full_text

    except Exception as e:
        logger.warning(f"Failed to get transcript for {video_id}: {e}")
        return None


def analyze_transcript(transcript: str, title: str) -> dict:
    """Extract trading insights from transcript."""
    insights = {
        "stocks_mentioned": [],
        "strategies": [],
        "key_concepts": [],
        "sentiment": "neutral",
        "actionable_items": [],
    }

    valid_tickers = {
        "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA",
        "BRK", "V", "MA", "JPM", "JNJ", "WMT", "PG", "HD", "DIS", "NFLX",
        "COST", "KO", "PEP", "MCD", "NKE", "SBUX", "TGT", "LOW", "CVS",
        "SPY", "QQQ", "IWM", "VTI", "VOO",
    }

    # Find tickers
    for match in re.findall(r"\b([A-Z]{1,5})\b", transcript):
        if match in valid_tickers and match not in insights["stocks_mentioned"]:
            insights["stocks_mentioned"].append(match)

    # Phil Town concepts
    concept_keywords = {
        "4 Ms": ["meaning", "moat", "management", "margin of safety"],
        "Moat": ["competitive advantage", "moat", "durable", "wide moat"],
        "Margin of Safety": ["margin of safety", "MOS", "sticker price", "buy price"],
        "Big Five Numbers": ["ROIC", "equity growth", "EPS growth", "sales growth"],
        "Rule #1": ["rule one", "rule #1", "don't lose money"],
        "Wonderful Company": ["wonderful company", "wonderful business"],
        "Options Strategy": ["put", "call", "covered call", "cash secured put", "wheel"],
    }

    transcript_lower = transcript.lower()
    for concept, keywords in concept_keywords.items():
        if any(kw.lower() in transcript_lower for kw in keywords):
            if concept not in insights["key_concepts"]:
                insights["key_concepts"].append(concept)

    # Sentiment
    bullish = sum(1 for w in ["buy", "bullish", "opportunity", "undervalued"] if w in transcript_lower)
    bearish = sum(1 for w in ["sell", "bearish", "overvalued", "risk"] if w in transcript_lower)
    if bullish > bearish + 2:
        insights["sentiment"] = "bullish"
    elif bearish > bullish + 2:
        insights["sentiment"] = "bearish"

    # Strategies
    if any(x in transcript_lower for x in ["cash secured put", "sell put", "wheel"]):
        insights["strategies"].append("Cash-Secured Puts")
    if any(x in transcript_lower for x in ["covered call", "sell call"]):
        insights["strategies"].append("Covered Calls")
    if any(x in transcript_lower for x in ["value investing", "intrinsic value"]):
        insights["strategies"].append("Value Investing")

    return insights


def save_to_rag(video: dict, transcript: str, insights: dict):
    """Save transcript and insights to RAG storage."""
    video_id = video["id"]
    title = video["title"]
    safe_title = re.sub(r"[^\w\s-]", "", title)[:50].strip().replace(" ", "_")

    # Save transcript
    transcript_file = RAG_TRANSCRIPTS / f"{video_id}_{safe_title}.md"
    transcript_content = f"""# {title}

**Video ID**: {video_id}
**URL**: {video.get("url", f"https://www.youtube.com/watch?v={video_id}")}
**Upload Date**: {video.get("upload_date", "Unknown")}
**Channel**: Phil Town - Rule #1 Investing
**Ingested**: {datetime.now().isoformat()}

## Key Concepts
{', '.join(insights.get('key_concepts', [])) or 'None identified'}

## Strategies
{', '.join(insights.get('strategies', [])) or 'None identified'}

## Transcript

{transcript}
"""
    transcript_file.write_text(transcript_content)
    logger.info(f"Saved transcript: {transcript_file}")

    # Save insights
    insights_file = RAG_INSIGHTS / f"{video_id}_insights.json"
    insights_data = {
        "video_id": video_id,
        "title": title,
        "url": video.get("url"),
        "upload_date": video.get("upload_date"),
        "ingested_at": datetime.now().isoformat(),
        "channel": "Phil Town - Rule #1 Investing",
        **insights,
    }
    insights_file.write_text(json.dumps(insights_data, indent=2))
    logger.info(f"Saved insights: {insights_file}")

    return transcript_file, insights_file


def load_processed_videos() -> set:
    """Load set of already processed video IDs."""
    if PROCESSED_FILE.exists():
        try:
            data = json.loads(PROCESSED_FILE.read_text())
            return set(data.get("processed_ids", []))
        except Exception:
            pass
    return set()


def save_processed_videos(processed_ids: set):
    """Save set of processed video IDs."""
    data = {
        "processed_ids": list(processed_ids),
        "last_updated": datetime.now().isoformat(),
        "count": len(processed_ids),
    }
    PROCESSED_FILE.write_text(json.dumps(data, indent=2))


def ingest_videos(videos: list[dict], skip_processed: bool = True) -> dict:
    """Ingest videos into RAG."""
    processed = load_processed_videos()
    results = {"success": 0, "failed": 0, "skipped": 0, "videos": []}

    for video in videos:
        video_id = video["id"]
        if not video_id:
            continue

        if skip_processed and video_id in processed:
            logger.info(f"Skipping already processed: {video_id}")
            results["skipped"] += 1
            continue

        logger.info(f"Processing: {video.get('title', video_id)}")

        transcript = get_transcript(video_id)
        if not transcript:
            results["failed"] += 1
            continue

        insights = analyze_transcript(transcript, video.get("title", ""))

        try:
            save_to_rag(video, transcript, insights)
            processed.add(video_id)
            results["success"] += 1
            results["videos"].append({
                "id": video_id,
                "title": video.get("title"),
                "concepts": insights["key_concepts"],
            })
        except Exception as e:
            logger.error(f"Failed to save {video_id}: {e}")
            results["failed"] += 1

    save_processed_videos(processed)
    return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Phil Town YouTube videos to RAG")
    parser.add_argument(
        "--mode",
        choices=["backfill", "recent", "new"],
        default="recent",
        help="Ingestion mode: backfill=all, recent=last 10, new=only unprocessed",
    )
    parser.add_argument("--max-videos", type=int, default=50, help="Max videos to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Show without processing")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("PHIL TOWN YOUTUBE INGESTION")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"YOUTUBE_API_KEY: {'SET' if os.environ.get('YOUTUBE_API_KEY') else 'NOT SET'}")
    logger.info("=" * 60)

    ensure_directories()

    max_videos = {"backfill": 500, "recent": 10, "new": args.max_videos}.get(args.mode, 10)

    logger.info(f"Fetching up to {max_videos} videos...")
    videos = get_channel_videos(max_results=max_videos)

    if not videos:
        logger.error("No videos found from any method!")
        return {"success": False, "reason": "no_videos_found"}

    logger.info(f"Found {len(videos)} videos to process")

    if args.dry_run:
        logger.info("DRY RUN - Would process:")
        for v in videos[:10]:
            logger.info(f"  - {v['id']}: {v.get('title', 'Unknown')}")
        return {"success": True, "dry_run": True, "video_count": len(videos)}

    results = ingest_videos(videos, skip_processed=(args.mode in ["new", "recent"]))

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETE")
    logger.info(f"Success: {results['success']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Skipped: {results['skipped']}")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    result = main()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
