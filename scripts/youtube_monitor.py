#!/usr/bin/env python3
"""
Autonomous YouTube Video Monitoring System

Monitors financial YouTube channels for new videos, automatically downloads transcripts,
analyzes content, and updates trading system watchlists.

Runs daily at 8:00 AM ET (before market open at 9:30 AM)
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.core.multi_llm_analysis import MultiLLMAnalyzer

# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "scripts" / "youtube_channels.json"
WATCHLIST_FILE = BASE_DIR / "data" / "tier2_watchlist.json"
ANALYSIS_DIR = BASE_DIR / "docs" / "youtube_analysis"
LOG_FILE = BASE_DIR / "logs" / "youtube_analysis.log"
CACHE_DIR = BASE_DIR / "data" / "youtube_cache"

# Create directories
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class YouTubeMonitor:
    """Autonomous YouTube channel monitoring and analysis system"""

    def __init__(self, config_path: Path = CONFIG_FILE):
        """Initialize monitor with configuration"""
        self.config_path = config_path
        self.config = self._load_config()
        self.llm_analyzer = None
        self.processed_videos = self._load_processed_videos()

        # Initialize LLM analyzer if enabled in config
        if self.config.get("use_llm_analysis", False):
            try:
                self.llm_analyzer = MultiLLMAnalyzer()
                logger.info("✅ MultiLLM analyzer enabled")
            except Exception as e:
                logger.warning(f"⚠️  MultiLLM unavailable: {e}")
                logger.info("Using keyword-based analysis instead")

    def _load_config(self) -> dict:
        """Load configuration from JSON file"""
        if not self.config_path.exists():
            logger.error(f"❌ Config file not found: {self.config_path}")
            logger.info("Creating default configuration...")
            self._create_default_config()

        with open(self.config_path) as f:
            return json.load(f)

    def _create_default_config(self):
        """Create default configuration file"""
        default_config = {
            "version": "1.0",
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "use_llm_analysis": False,
            "lookback_hours": 24,
            "channels": [
                {
                    "name": "Parkev Tatevosian",
                    "channel_id": "UCz_cXN42EAGoWFpqSE5OjBA",
                    "handle": "@parkevtatevosian",
                    "focus": "Stock picks, value investing, dividend stocks",
                    "priority": "high",
                    "keywords": [
                        "stock",
                        "investing",
                        "buy",
                        "dividend",
                        "analysis",
                        "portfolio",
                    ],
                }
            ],
            "global_keywords": [
                "stock",
                "stocks",
                "investing",
                "investment",
                "buy",
                "portfolio",
                "trading",
                "market",
                "dividend",
                "growth",
                "analysis",
                "pick",
                "recommendation",
                "opportunity",
            ],
            "exclude_keywords": [
                "crypto",
                "cryptocurrency",
                "bitcoin",
                "forex",
                "day trading",
                "options",
                "futures",
            ],
            "analysis_parameters": {
                "min_video_length_seconds": 180,
                "max_video_length_seconds": 3600,
                "min_views": 100,
                "extract_tickers": True,
                "update_watchlist": True,
                "generate_report": True,
            },
        }

        with open(self.config_path, "w") as f:
            json.dump(default_config, f, indent=2)

        logger.info(f"✅ Created default config: {self.config_path}")

    def _load_processed_videos(self) -> dict:
        """Load history of processed videos"""
        cache_file = CACHE_DIR / "processed_videos.json"
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)
        return {}

    def _save_processed_videos(self):
        """Save history of processed videos"""
        cache_file = CACHE_DIR / "processed_videos.json"
        with open(cache_file, "w") as f:
            json.dump(self.processed_videos, f, indent=2)

    def get_recent_videos(self, channel_id: str, lookback_hours: int = 24) -> list[dict]:
        """
        Get recent videos from a YouTube channel

        Args:
            channel_id: YouTube channel ID
            lookback_hours: How far back to look for videos

        Returns:
            List of video metadata dictionaries
        """
        logger.info(
            f"🔍 Checking channel {channel_id} for videos in last {lookback_hours} hours..."
        )

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "playlistend": 10,  # Check last 10 videos
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get channel uploads - try multiple URL formats
                # Try @handle format first, then channel ID
                if channel_id.startswith("@"):
                    url = f"https://www.youtube.com/{channel_id}/videos"
                elif channel_id.startswith("UC"):
                    url = f"https://www.youtube.com/channel/{channel_id}/videos"
                else:
                    url = f"https://www.youtube.com/@{channel_id}/videos"

                info = ydl.extract_info(url, download=False)

                if not info or "entries" not in info:
                    logger.warning(f"⚠️  No videos found for channel {channel_id}")
                    return []

                # Filter for recent videos
                cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
                recent_videos = []

                for entry in info["entries"]:
                    if not entry:
                        continue

                    # Get full video info
                    video_id = entry.get("id")
                    if not video_id:
                        continue

                    video_info = ydl.extract_info(
                        f"https://www.youtube.com/watch?v={video_id}", download=False
                    )

                    # Check if already processed
                    if video_id in self.processed_videos:
                        logger.debug(f"⏭️  Skipping already processed: {video_id}")
                        continue

                    # Parse upload date
                    upload_date_str = video_info.get("upload_date", "")
                    if upload_date_str:
                        try:
                            upload_date = datetime.strptime(upload_date_str, "%Y%m%d")
                            if upload_date < cutoff_time:
                                continue
                        except ValueError:
                            logger.warning(f"⚠️  Invalid date format: {upload_date_str}")
                            continue

                    recent_videos.append(
                        {
                            "video_id": video_id,
                            "title": video_info.get("title", "Unknown"),
                            "channel": video_info.get("channel", "Unknown"),
                            "upload_date": upload_date_str,
                            "duration": video_info.get("duration", 0),
                            "view_count": video_info.get("view_count", 0),
                            "description": video_info.get("description", ""),
                            "url": f"https://www.youtube.com/watch?v={video_id}",
                        }
                    )

                logger.info(f"✅ Found {len(recent_videos)} new videos")
                return recent_videos

        except Exception as e:
            logger.error(f"❌ Error fetching videos: {e}")
            return []

    def is_trading_related(self, video: dict, channel_config: dict) -> bool:
        """
        Check if video is trading/investing related using keywords

        Args:
            video: Video metadata
            channel_config: Channel configuration with keywords

        Returns:
            True if video matches keywords
        """
        # Get text to search
        text = f"{video['title']} {video['description']}".lower()

        # Check channel-specific keywords
        channel_keywords = channel_config.get("keywords", [])
        if any(keyword.lower() in text for keyword in channel_keywords):
            return True

        # Check global keywords
        global_keywords = self.config.get("global_keywords", [])
        if any(keyword.lower() in text for keyword in global_keywords):
            return True

        # Check exclude keywords
        exclude_keywords = self.config.get("exclude_keywords", [])
        if any(keyword.lower() in text for keyword in exclude_keywords):
            logger.debug(f"⏭️  Excluded by keyword: {video['title']}")
            return False

        return False

    def get_transcript(self, video_id: str) -> Optional[str]:
        """
        Get video transcript using youtube-transcript-api

        Args:
            video_id: YouTube video ID

        Returns:
            Transcript text or None
        """
        # Check cache first
        cache_file = CACHE_DIR / f"{video_id}_transcript.txt"
        if cache_file.exists():
            logger.debug(f"📦 Using cached transcript for {video_id}")
            return cache_file.read_text()

        try:
            logger.info(f"📥 Downloading transcript for {video_id}...")
            # Use list_transcripts to get available transcripts
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # Get English transcript (auto-generated or manual)
            try:
                transcript_obj = transcript_list.find_transcript(["en"])
            except:
                # Try auto-generated
                transcript_obj = transcript_list.find_generated_transcript(["en"])

            # Fetch transcript
            transcript_data = transcript_obj.fetch()
            transcript = " ".join([t["text"] for t in transcript_data])

            # Cache it
            cache_file.write_text(transcript)

            logger.info(f"✅ Transcript downloaded ({len(transcript)} chars)")
            return transcript

        except Exception as e:
            logger.error(f"❌ Failed to get transcript: {e}")
            return None

    def analyze_video(self, video: dict, transcript: str) -> dict:
        """
        Analyze video transcript for trading insights

        Args:
            video: Video metadata
            transcript: Video transcript text

        Returns:
            Analysis results dictionary
        """
        logger.info(f"🤖 Analyzing: {video['title']}")

        if self.llm_analyzer:
            return self._llm_analysis(video, transcript)
        else:
            return self._keyword_analysis(video, transcript)

    def _keyword_analysis(self, video: dict, transcript: str) -> dict:
        """Simple keyword-based analysis"""
        # Look for stock tickers (1-5 uppercase letters)
        import re

        ticker_pattern = r"\b([A-Z]{1,5})\b"
        potential_tickers = re.findall(ticker_pattern, transcript)

        # Filter common words
        common_words = {
            "I",
            "A",
            "THE",
            "AND",
            "OR",
            "BUT",
            "IS",
            "ARE",
            "WAS",
            "WERE",
            "BE",
            "BEEN",
            "TO",
            "OF",
            "IN",
            "FOR",
            "ON",
            "AT",
            "BY",
            "WITH",
            "FROM",
        }
        tickers = [t for t in potential_tickers if t not in common_words]

        # Count mentions
        ticker_counts = {}
        for ticker in tickers:
            count = transcript.count(ticker)
            if count >= 3:  # Mentioned at least 3 times
                ticker_counts[ticker] = count

        return {
            "video_id": video["video_id"],
            "title": video["title"],
            "analysis_type": "keyword",
            "tickers_found": list(ticker_counts.keys()),
            "ticker_mentions": ticker_counts,
            "summary": f"Found {len(ticker_counts)} potential stock tickers",
            "timestamp": datetime.now().isoformat(),
        }

    def _llm_analysis(self, video: dict, transcript: str) -> dict:
        """LLM-based deep analysis"""
        # Truncate if too long
        max_chars = 15000
        if len(transcript) > max_chars:
            transcript = transcript[:max_chars] + "..."

        prompt = f"""
Analyze this YouTube trading video transcript and extract actionable stock picks.

VIDEO: {video["title"]}
CHANNEL: {video["channel"]}
DATE: {video["upload_date"]}

TRANSCRIPT:
{transcript}

Extract:
1. STOCK TICKERS mentioned (with confidence: high/medium/low)
2. BULLISH or BEARISH sentiment for each ticker
3. KEY REASONS for recommendation
4. PRICE TARGETS or entry zones (if mentioned)
5. RISK FACTORS or warnings
6. ACTIONABLE SUMMARY (2-3 sentences max)

Format as JSON with fields:
- tickers: list of {{"ticker": "AAPL", "sentiment": "bullish", "confidence": "high", "rationale": "..."}}
- summary: brief actionable summary
- risks: list of risk factors
- recommended_action: what to do (add to watchlist, buy, monitor, avoid)
"""

        try:
            analysis = self.llm_analyzer.analyze_sentiment(symbol="YOUTUBE_VIDEO", context=prompt)

            if isinstance(analysis, dict):
                return {
                    "video_id": video["video_id"],
                    "title": video["title"],
                    "analysis_type": "llm",
                    "analysis": analysis,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {
                    "video_id": video["video_id"],
                    "title": video["title"],
                    "analysis_type": "llm",
                    "summary": str(analysis),
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            logger.error(f"❌ LLM analysis failed: {e}")
            # Fallback to keyword analysis
            return self._keyword_analysis(video, transcript)

    def update_watchlist(self, analysis: dict) -> bool:
        """
        Update tier2_watchlist.json with new stock picks

        Args:
            analysis: Analysis results with tickers

        Returns:
            True if watchlist was updated
        """
        if not self.config["analysis_parameters"].get("update_watchlist", True):
            logger.debug("📋 Watchlist updates disabled in config")
            return False

        # Extract tickers from analysis
        tickers = []
        if analysis["analysis_type"] == "keyword":
            tickers = [
                {"ticker": t, "mentions": analysis["ticker_mentions"][t]}
                for t in analysis.get("tickers_found", [])
            ]
        elif analysis["analysis_type"] == "llm":
            # Parse LLM analysis for tickers
            analysis_data = analysis.get("analysis", {})
            if isinstance(analysis_data, dict) and "tickers" in analysis_data:
                tickers = analysis_data["tickers"]

        if not tickers:
            logger.info("📋 No tickers to add to watchlist")
            return False

        # Load current watchlist
        with open(WATCHLIST_FILE) as f:
            watchlist = json.load(f)

        # Add new stocks
        updated = False
        for ticker_data in tickers:
            ticker = ticker_data.get("ticker", "").upper()
            if not ticker:
                continue

            # Check if already exists
            existing_tickers = [s["ticker"] for s in watchlist.get("watchlist", [])]
            if ticker in existing_tickers:
                logger.debug(f"⏭️  {ticker} already in watchlist")
                continue

            # Add to watchlist
            watchlist.setdefault("watchlist", []).append(
                {
                    "ticker": ticker,
                    "name": f"{ticker} (from YouTube analysis)",
                    "source": f"YouTube - {analysis['title']}",
                    "date_added": datetime.now().strftime("%Y-%m-%d"),
                    "rationale": ticker_data.get(
                        "rationale", analysis.get("summary", "See video analysis")
                    ),
                    "priority": ticker_data.get("confidence", "medium").lower(),
                    "status": "watchlist",
                    "video_url": f"https://www.youtube.com/watch?v={analysis['video_id']}",
                    "analysis_file": f"docs/youtube_analysis/{analysis['video_id']}.md",
                }
            )

            logger.info(f"✅ Added {ticker} to watchlist")
            updated = True

        if updated:
            # Update metadata
            watchlist["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")

            # Save
            with open(WATCHLIST_FILE, "w") as f:
                json.dump(watchlist, f, indent=2)

            logger.info(f"💾 Watchlist updated with {len(tickers)} new stocks")

        return updated

    def save_analysis_report(self, video: dict, transcript: str, analysis: dict):
        """
        Save analysis report to markdown file

        Args:
            video: Video metadata
            transcript: Full transcript
            analysis: Analysis results
        """
        if not self.config["analysis_parameters"].get("generate_report", True):
            return

        report_file = ANALYSIS_DIR / f"{video['video_id']}.md"

        report = f"""# YouTube Video Analysis: {video["title"]}

**Channel**: {video["channel"]}
**Upload Date**: {video["upload_date"]}
**Duration**: {video["duration"]}s ({video["duration"] // 60} minutes)
**Views**: {video["view_count"]:,}
**Video URL**: {video["url"]}
**Analysis Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Analysis Type**: {analysis["analysis_type"].upper()}

---

## Summary

{analysis.get("summary", "No summary available")}

---

## Stock Picks

"""

        # Add tickers
        if analysis["analysis_type"] == "keyword":
            report += "### Tickers Mentioned (Keyword Analysis)\n\n"
            for ticker, count in analysis.get("ticker_mentions", {}).items():
                report += f"- **{ticker}**: Mentioned {count} times\n"
        elif analysis["analysis_type"] == "llm":
            report += "### AI-Extracted Stock Recommendations\n\n"
            analysis_data = analysis.get("analysis", {})
            if isinstance(analysis_data, dict) and "tickers" in analysis_data:
                for stock in analysis_data["tickers"]:
                    report += f"""
### {stock.get("ticker", "Unknown")}
- **Sentiment**: {stock.get("sentiment", "Unknown").upper()}
- **Confidence**: {stock.get("confidence", "Unknown").upper()}
- **Rationale**: {stock.get("rationale", "N/A")}
"""

        report += f"""

---

## Full Transcript

```
{transcript[:10000]}{"..." if len(transcript) > 10000 else ""}
```

---

*Generated by Autonomous YouTube Monitoring System*
*Report saved: {report_file}*
"""

        # Save report
        report_file.write_text(report)
        logger.info(f"💾 Saved analysis report: {report_file}")

    def process_video(self, video: dict, channel_config: dict) -> bool:
        """
        Complete processing pipeline for a single video

        Args:
            video: Video metadata
            channel_config: Channel configuration

        Returns:
            True if video was successfully processed
        """
        logger.info(f"\n{'=' * 60}")
        logger.info(f"📹 Processing: {video['title']}")
        logger.info(f"{'=' * 60}")

        # Check if trading-related
        if not self.is_trading_related(video, channel_config):
            logger.info("⏭️  Skipping non-trading video")
            self.processed_videos[video["video_id"]] = {
                "title": video["title"],
                "processed_at": datetime.now().isoformat(),
                "status": "skipped_not_trading_related",
            }
            self._save_processed_videos()
            return False

        # Get transcript
        transcript = self.get_transcript(video["video_id"])
        if not transcript:
            logger.warning("⚠️  No transcript available, skipping")
            self.processed_videos[video["video_id"]] = {
                "title": video["title"],
                "processed_at": datetime.now().isoformat(),
                "status": "skipped_no_transcript",
            }
            self._save_processed_videos()
            return False

        # Analyze
        analysis = self.analyze_video(video, transcript)

        # Update watchlist
        self.update_watchlist(analysis)

        # Save report
        self.save_analysis_report(video, transcript, analysis)

        # Mark as processed
        self.processed_videos[video["video_id"]] = {
            "title": video["title"],
            "processed_at": datetime.now().isoformat(),
            "status": "completed",
            "analysis_file": f"docs/youtube_analysis/{video['video_id']}.md",
        }
        self._save_processed_videos()

        logger.info("✅ Video processing complete")
        return True

    def run_monitoring(self):
        """
        Main monitoring loop - check all channels for new videos
        """
        logger.info("\n" + "=" * 60)
        logger.info("🚀 AUTONOMOUS YOUTUBE MONITORING - STARTING")
        logger.info("=" * 60)
        logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        lookback_hours = self.config.get("lookback_hours", 24)
        channels = self.config.get("channels", [])

        logger.info(f"📊 Monitoring {len(channels)} channels (lookback: {lookback_hours}h)")

        total_processed = 0
        total_found = 0

        for channel_config in channels:
            channel_name = channel_config["name"]
            channel_id = channel_config["channel_id"]

            logger.info(f"\n{'─' * 60}")
            logger.info(f"📺 Channel: {channel_name}")
            logger.info(f"{'─' * 60}")

            # Get recent videos
            videos = self.get_recent_videos(channel_id, lookback_hours)
            total_found += len(videos)

            if not videos:
                logger.info("📭 No new videos found")
                continue

            # Process each video
            for video in videos:
                try:
                    if self.process_video(video, channel_config):
                        total_processed += 1
                except Exception as e:
                    logger.error(f"❌ Error processing video: {e}")
                    continue

        logger.info("\n" + "=" * 60)
        logger.info("🏁 MONITORING COMPLETE")
        logger.info("=" * 60)
        logger.info(f"📊 Found: {total_found} new videos")
        logger.info(f"✅ Processed: {total_processed} videos")
        logger.info(f"📝 Logs: {LOG_FILE}")
        logger.info(f"📋 Watchlist: {WATCHLIST_FILE}")
        logger.info(f"📁 Reports: {ANALYSIS_DIR}")
        logger.info("=" * 60)


def main():
    """Main entry point"""
    try:
        monitor = YouTubeMonitor()
        monitor.run_monitoring()
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
