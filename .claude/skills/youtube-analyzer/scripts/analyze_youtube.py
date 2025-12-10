#!/usr/bin/env python3
"""
YouTube Video Analyzer for Trading Insights

Extracts video metadata, transcripts, and optionally analyzes content
for trading insights using AI.

Usage:
    python3 analyze_youtube.py --url "https://youtube.com/watch?v=VIDEO_ID"
    python3 analyze_youtube.py --video-id "VIDEO_ID" --analyze
    python3 analyze_youtube.py --url "URL" --output docs/youtube_analysis/
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    import yt_dlp
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )
except ImportError as e:
    print(f"Error: Required package not installed: {e}")
    print("Install with: pip install yt-dlp youtube-transcript-api")
    sys.exit(1)

# Optional: AI analysis support
try:
    from dotenv import load_dotenv

    load_dotenv()
    from openai import OpenAI

    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class YouTubeAnalyzer:
    """Analyze YouTube videos for trading insights."""

    def __init__(self, output_dir: str = "docs/youtube_analysis", use_ai: bool = False):
        """
        Initialize YouTube analyzer.

        Args:
            output_dir: Directory to save analysis reports
            use_ai: Whether to use AI for content analysis
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_ai = use_ai and AI_AVAILABLE

        if self.use_ai:
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                logger.warning("OPENROUTER_API_KEY not found - AI analysis disabled")
                self.use_ai = False
            else:
                self.ai_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    def extract_video_id(self, url: str) -> str | None:
        """
        Extract video ID from YouTube URL.

        Args:
            url: YouTube URL

        Returns:
            Video ID or None if not found
        """
        patterns = [
            r"(?:v=|/)([0-9A-Za-z_-]{11}).*",
            r"(?:embed/)([0-9A-Za-z_-]{11})",
            r"^([0-9A-Za-z_-]{11})$",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def fetch_metadata(self, video_id: str) -> dict:
        """
        Fetch video metadata using yt-dlp.

        Args:
            video_id: YouTube video ID

        Returns:
            Dictionary with metadata
        """
        logger.info(f"Fetching metadata for video: {video_id}")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )

                metadata = {
                    "video_id": video_id,
                    "title": info.get("title", "Unknown"),
                    "channel": info.get("channel", "Unknown"),
                    "channel_id": info.get("channel_id", "Unknown"),
                    "upload_date": info.get("upload_date", "Unknown"),
                    "duration": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                    "like_count": info.get("like_count", 0),
                    "description": info.get("description", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                }

                logger.info(f"Metadata fetched: {metadata['title']}")
                return metadata

        except Exception as e:
            logger.error(f"Failed to fetch metadata: {e}")
            raise

    def fetch_transcript(self, video_id: str) -> list[dict]:
        """
        Fetch video transcript.

        Args:
            video_id: YouTube video ID

        Returns:
            List of transcript segments
        """
        logger.info(f"Fetching transcript for video: {video_id}")

        try:
            # Use the new API: create instance and fetch
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id, languages=["en"])

            # Convert to list of dicts for compatibility
            transcript = [
                {"start": s.start, "duration": s.duration, "text": s.text} for s in fetched.snippets
            ]

            logger.info(f"Transcript fetched: {len(transcript)} segments")
            return transcript

        except NoTranscriptFound:
            logger.error("No transcript found for video")
            raise
        except TranscriptsDisabled:
            logger.error("Transcripts are disabled for this video")
            raise
        except VideoUnavailable:
            logger.error("Video is unavailable")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch transcript: {e}")
            raise

    def format_transcript(self, transcript: list[dict]) -> str:
        """
        Format transcript segments into readable text.

        Args:
            transcript: List of transcript segments

        Returns:
            Formatted transcript text
        """
        formatted = []
        for segment in transcript:
            timestamp = int(segment["start"])
            minutes = timestamp // 60
            seconds = timestamp % 60
            text = segment["text"].strip()
            formatted.append(f"[{minutes:02d}:{seconds:02d}] {text}")

        return "\n".join(formatted)

    def analyze_with_ai(self, metadata: dict, transcript_text: str) -> dict:
        """
        Analyze video content using AI.

        Args:
            metadata: Video metadata
            transcript_text: Full transcript text

        Returns:
            Dictionary with analysis results
        """
        if not self.use_ai:
            return {"error": "AI analysis not available"}

        logger.info("Analyzing content with AI...")

        prompt = f"""Analyze this YouTube video transcript for trading insights.

Video Title: {metadata["title"]}
Channel: {metadata["channel"]}

Transcript:
{transcript_text[:10000]}  # Limit to first 10k chars

Please provide:

1. EXECUTIVE SUMMARY (3-5 bullet points of key takeaways)

2. STOCK PICKS (if any mentioned):
   - Ticker symbol
   - Bullish or Bearish
   - Confidence level (High/Medium/Low)
   - Brief reasoning

3. TRADING STRATEGIES (if any discussed):
   - Strategy name/type
   - Entry/exit criteria
   - Risk management

4. RISK FACTORS (warnings or cautions mentioned):
   - Specific risks
   - Market conditions to watch

5. ACTIONABLE RECOMMENDATIONS:
   - What traders should do next
   - Specific actions to take

6. KEY TIMESTAMPS (if specific insights at certain times):
   - Timestamp
   - What was discussed

Format as markdown sections. Be specific and extract concrete trading signals.
If no trading content is found, clearly state that.
"""

        try:
            response = self.ai_client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                messages=[{"role": "user", "content": prompt}],
            )

            analysis = response.choices[0].message.content
            logger.info("AI analysis complete")
            return {"analysis": analysis}

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {"error": str(e)}

    def generate_report(
        self, metadata: dict, transcript: list[dict], ai_analysis: dict | None = None
    ) -> str:
        """
        Generate markdown report.

        Args:
            metadata: Video metadata
            transcript: Transcript segments
            ai_analysis: Optional AI analysis results

        Returns:
            Markdown report content
        """
        transcript_text = self.format_transcript(transcript)

        report_lines = [
            f"# YouTube Analysis: {metadata['title']}",
            "",
            "## Video Metadata",
            "",
            f"- **Title**: {metadata['title']}",
            f"- **Channel**: {metadata['channel']}",
            f"- **Upload Date**: {metadata['upload_date']}",
            f"- **Duration**: {metadata['duration'] // 60}m {metadata['duration'] % 60}s",
            f"- **Views**: {metadata['view_count']:,}",
            f"- **Likes**: {metadata['like_count']:,}",
            f"- **URL**: {metadata['url']}",
            "",
            "---",
            "",
        ]

        # Add AI analysis if available
        if ai_analysis and "analysis" in ai_analysis:
            report_lines.extend(["## AI Analysis", "", ai_analysis["analysis"], "", "---", ""])

        # Add full transcript
        report_lines.extend(
            [
                "## Full Transcript",
                "",
                transcript_text,
                "",
                "---",
                "",
                f"*Analysis generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            ]
        )

        return "\n".join(report_lines)

    def save_report(self, report: str, metadata: dict) -> Path:
        """
        Save report to file.

        Args:
            report: Markdown report content
            metadata: Video metadata

        Returns:
            Path to saved file
        """
        # Create safe filename
        title = re.sub(r"[^\w\s-]", "", metadata["title"])
        title = re.sub(r"[-\s]+", "_", title)
        title = title[:50]  # Limit length

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"youtube_{title}_{timestamp}.md"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"Report saved: {filepath}")
        return filepath

    def analyze_video(self, video_url: str) -> Path:
        """
        Complete analysis workflow.

        Args:
            video_url: YouTube URL or video ID

        Returns:
            Path to saved report
        """
        # Extract video ID
        video_id = self.extract_video_id(video_url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from: {video_url}")

        logger.info(f"Analyzing video: {video_id}")

        # Fetch metadata
        metadata = self.fetch_metadata(video_id)

        # Fetch transcript
        transcript = self.fetch_transcript(video_id)

        # AI analysis (optional)
        ai_analysis = None
        if self.use_ai:
            transcript_text = self.format_transcript(transcript)
            ai_analysis = self.analyze_with_ai(metadata, transcript_text)

        # Generate report
        report = self.generate_report(metadata, transcript, ai_analysis)

        # Save report
        filepath = self.save_report(report, metadata)

        logger.info(f"Analysis complete: {filepath}")
        return filepath


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze YouTube videos for trading insights")
    parser.add_argument("--url", help="YouTube video URL")
    parser.add_argument("--video-id", help="YouTube video ID (alternative to --url)")
    parser.add_argument(
        "--output",
        default="docs/youtube_analysis",
        help="Output directory (default: docs/youtube_analysis)",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Enable AI analysis (requires OpenRouter API key)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate input
    if not args.url and not args.video_id:
        parser.error("Either --url or --video-id is required")

    video_input = args.url or args.video_id

    # Check AI availability
    if args.analyze and not AI_AVAILABLE:
        logger.warning("AI analysis requested but dependencies not available")
        logger.warning("Install with: pip install openai python-dotenv")
        args.analyze = False

    try:
        # Create analyzer
        analyzer = YouTubeAnalyzer(output_dir=args.output, use_ai=args.analyze)

        # Analyze video
        report_path = analyzer.analyze_video(video_input)

        print("\n✓ Analysis complete!")
        print(f"Report saved to: {report_path}")

        if not args.analyze:
            print("\nTip: Use --analyze flag for AI-powered trading insights")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
