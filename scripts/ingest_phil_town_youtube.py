#!/usr/bin/env python3
"""
Phil Town YouTube Channel Ingestion Script

Automatically fetches and stores Phil Town's Rule #1 Investing videos
into RAG for ML pipeline synthesis.

Usage:
    python3 scripts/ingest_phil_town_youtube.py --mode backfill  # All historical
    python3 scripts/ingest_phil_town_youtube.py --mode recent    # Last 10 videos
    python3 scripts/ingest_phil_town_youtube.py --mode new       # Only new since last run

Channel: https://youtube.com/@philtownrule1investing
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Phil Town's channel info
CHANNEL_ID = "UC20qsVeyVXpGgGDmVKHH_4g"  # @philtownrule1investing
CHANNEL_URL = "https://www.youtube.com/@philtownrule1investing"

# Storage paths
RAG_TRANSCRIPTS = Path("rag_knowledge/youtube/transcripts")
RAG_INSIGHTS = Path("rag_knowledge/youtube/insights")
CACHE_FILE = Path("data/youtube_cache/phil_town_videos.json")
PROCESSED_FILE = Path("data/youtube_cache/processed_videos.json")


def ensure_directories():
    """Create required directories."""
    RAG_TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    RAG_INSIGHTS.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_channel_videos(max_results: int = 50) -> list[dict]:
    """
    Fetch video list from Phil Town's channel using yt-dlp.

    Returns list of {id, title, upload_date, duration}
    """
    try:
        import json as json_module
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
                    data = json_module.loads(line)
                    videos.append(
                        {
                            "id": data.get("id"),
                            "title": data.get("title"),
                            "upload_date": data.get("upload_date"),
                            "duration": data.get("duration"),
                            "url": f"https://www.youtube.com/watch?v={data.get('id')}",
                        }
                    )
                except json_module.JSONDecodeError:
                    continue

        logger.info(f"Found {len(videos)} videos from channel")
        return videos

    except Exception as e:
        logger.error(f"Failed to fetch channel videos: {e}")
        return []


def get_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript for a video using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

        # Combine all text segments
        full_text = " ".join([segment["text"] for segment in transcript_list])

        logger.info(f"Got transcript for {video_id}: {len(full_text)} chars")
        return full_text

    except Exception as e:
        logger.warning(f"Failed to get transcript for {video_id}: {e}")
        return None


def analyze_transcript(transcript: str, title: str) -> dict:
    """
    Extract trading insights from transcript using keyword analysis.

    For ML pipeline integration, we identify:
    - Stock mentions (tickers)
    - Strategy concepts (4 Ms, moat, margin of safety)
    - Sentiment indicators
    - Actionable advice
    """
    insights = {
        "stocks_mentioned": [],
        "strategies": [],
        "key_concepts": [],
        "sentiment": "neutral",
        "actionable_items": [],
    }

    # Stock ticker pattern (1-5 uppercase letters)
    ticker_pattern = r"\b([A-Z]{1,5})\b"

    # Known valid tickers to filter noise
    valid_tickers = {
        "AAPL",
        "MSFT",
        "GOOGL",
        "GOOG",
        "AMZN",
        "META",
        "NVDA",
        "TSLA",
        "BRK",
        "V",
        "MA",
        "JPM",
        "JNJ",
        "WMT",
        "PG",
        "HD",
        "DIS",
        "NFLX",
        "COST",
        "KO",
        "PEP",
        "MCD",
        "NKE",
        "SBUX",
        "TGT",
        "LOW",
        "CVS",
        "SPY",
        "QQQ",
        "IWM",
        "VTI",
        "VOO",
    }

    # Find potential tickers
    matches = re.findall(ticker_pattern, transcript)
    for match in matches:
        if match in valid_tickers:
            if match not in insights["stocks_mentioned"]:
                insights["stocks_mentioned"].append(match)

    # Phil Town key concepts
    concept_keywords = {
        "4 Ms": ["meaning", "moat", "management", "margin of safety"],
        "Moat": ["competitive advantage", "moat", "durable", "wide moat", "narrow moat"],
        "Margin of Safety": ["margin of safety", "MOS", "sticker price", "buy price"],
        "Big Five Numbers": ["ROIC", "equity growth", "EPS growth", "sales growth", "cash growth"],
        "Rule #1": ["rule one", "rule #1", "rule number one", "don't lose money"],
        "Wonderful Company": ["wonderful company", "wonderful business", "great company"],
        "10-10 Rule": ["10 cap", "10 year", "owner earnings"],
        "Options Strategy": ["put", "call", "covered call", "cash secured put", "wheel"],
    }

    transcript_lower = transcript.lower()
    for concept, keywords in concept_keywords.items():
        for keyword in keywords:
            if keyword.lower() in transcript_lower:
                if concept not in insights["key_concepts"]:
                    insights["key_concepts"].append(concept)
                break

    # Sentiment analysis (simple keyword-based)
    bullish_words = ["buy", "bullish", "opportunity", "undervalued", "growth", "strong"]
    bearish_words = ["sell", "bearish", "overvalued", "risk", "caution", "avoid"]

    bullish_count = sum(1 for word in bullish_words if word in transcript_lower)
    bearish_count = sum(1 for word in bearish_words if word in transcript_lower)

    if bullish_count > bearish_count + 2:
        insights["sentiment"] = "bullish"
    elif bearish_count > bullish_count + 2:
        insights["sentiment"] = "bearish"

    # Strategy detection
    if any(x in transcript_lower for x in ["cash secured put", "sell put", "wheel strategy"]):
        insights["strategies"].append("Cash-Secured Puts")
    if any(x in transcript_lower for x in ["covered call", "sell call"]):
        insights["strategies"].append("Covered Calls")
    if any(x in transcript_lower for x in ["buy and hold", "long term", "10 years"]):
        insights["strategies"].append("Buy and Hold")
    if any(x in transcript_lower for x in ["value investing", "intrinsic value", "undervalued"]):
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
        except:
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
    """Ingest a list of videos into RAG."""
    processed = load_processed_videos()
    results = {"success": 0, "failed": 0, "skipped": 0, "videos": []}

    for video in videos:
        video_id = video["id"]

        if skip_processed and video_id in processed:
            logger.info(f"Skipping already processed: {video_id}")
            results["skipped"] += 1
            continue

        logger.info(f"Processing: {video['title']}")

        # Get transcript
        transcript = get_transcript(video_id)
        if not transcript:
            results["failed"] += 1
            continue

        # Analyze
        insights = analyze_transcript(transcript, video["title"])

        # Save to RAG
        try:
            save_to_rag(video, transcript, insights)
            processed.add(video_id)
            results["success"] += 1
            results["videos"].append(
                {
                    "id": video_id,
                    "title": video["title"],
                    "concepts": insights["key_concepts"],
                    "stocks": insights["stocks_mentioned"],
                }
            )
        except Exception as e:
            logger.error(f"Failed to save {video_id}: {e}")
            results["failed"] += 1

    # Update processed list
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
    parser.add_argument(
        "--max-videos", type=int, default=50, help="Maximum videos to fetch (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually doing it",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("PHIL TOWN YOUTUBE INGESTION")
    logger.info(f"Mode: {args.mode}")
    logger.info("=" * 60)

    ensure_directories()

    # Determine how many videos to fetch
    max_videos = {
        "backfill": 500,  # All historical
        "recent": 10,  # Last 10
        "new": args.max_videos,
    }.get(args.mode, 10)

    # Fetch videos
    logger.info(f"Fetching up to {max_videos} videos from channel...")
    videos = get_channel_videos(max_results=max_videos)

    if not videos:
        logger.error("No videos found. Check network or channel URL.")
        return {"success": False, "reason": "no_videos_found"}

    if args.dry_run:
        logger.info("DRY RUN - Would process these videos:")
        for v in videos[:10]:
            logger.info(f"  - {v['id']}: {v['title']}")
        return {"success": True, "dry_run": True, "video_count": len(videos)}

    # Ingest videos
    skip_processed = args.mode in ["new", "recent"]
    results = ingest_videos(videos, skip_processed=skip_processed)

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
