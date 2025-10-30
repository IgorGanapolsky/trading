# YouTube Video Analysis Implementation Guide

## Executive Summary

This document provides implementation-ready recommendations for integrating YouTube video analysis capabilities into your trading system. After extensive research, I've identified the optimal approach combining multiple tools for maximum flexibility and reliability.

---

## Table of Contents
1. [Solution Comparison](#solution-comparison)
2. [Recommended Architecture](#recommended-architecture)
3. [Implementation Options](#implementation-options)
4. [Code Examples](#code-examples)
5. [Integration with Trading System](#integration-with-trading-system)
6. [Best Practices](#best-practices)

---

## Solution Comparison

### Option 1: MCP Server (Recommended for Claude-based workflows)
**Pros:**
- Zero-code integration with Claude Desktop/Code
- Pre-built transcript extraction
- Multiple server implementations available
- Direct integration with your existing Claude-based multi-LLM system

**Cons:**
- Requires Claude Desktop or Claude Code
- Less flexible for custom processing
- Limited to transcript extraction only

**Best For:** Quick integration, Claude Desktop workflows, manual video analysis

### Option 2: Python Libraries (Recommended for automated trading)
**Pros:**
- Full programmatic control
- Can be integrated into autonomous trading pipeline
- Combines metadata + transcripts + AI analysis
- Works with your existing MultiLLMAnalyzer
- No external dependencies

**Cons:**
- Requires more code
- Need to handle YouTube API limits

**Best For:** Automated analysis, batch processing, integration into trading bot

### Option 3: LangChain Integration (Recommended for RAG/document processing)
**Pros:**
- Clean document loader interface
- Easy integration with vector databases
- Built-in chunking and metadata handling
- Good for building knowledge bases

**Cons:**
- Adds LangChain dependency
- May be overkill for simple analysis

**Best For:** Building searchable video knowledge bases, RAG applications

---

## Recommended Architecture

### Primary Recommendation: **Hybrid Approach**

Use Python libraries for automation + MCP server for manual analysis:

```
┌─────────────────────────────────────────────┐
│         YouTube Analysis System             │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │   1. MCP Server (Manual Analysis)    │  │
│  │   - Quick video reviews              │  │
│  │   - Ad-hoc research                  │  │
│  │   - Claude Desktop integration       │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │   2. Python Automation               │  │
│  │   - youtube-transcript-api           │  │
│  │   - yt-dlp (metadata)                │  │
│  │   - MultiLLMAnalyzer (analysis)      │  │
│  │   - Scheduled batch processing       │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │   3. Trading Integration             │  │
│  │   - Extract trading signals          │  │
│  │   - Sentiment analysis               │  │
│  │   - Strategy identification          │  │
│  │   - Feed into decision engine        │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## Implementation Options

### Option A: MCP Server Setup (5 minutes)

**For Claude Code CLI:**
```bash
# Install YouTube transcript MCP server
claude mcp add-json "youtube-transcript" '{"command":"uvx","args":["--from","git+https://github.com/jkawamoto/mcp-youtube-transcript","mcp-youtube-transcript"]}'

# Restart Claude Code to load the server
```

**For Claude Desktop (Manual config):**
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "youtube-transcript": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/jkawamoto/mcp-youtube-transcript",
        "mcp-youtube-transcript"
      ]
    }
  }
}
```

**Usage:**
After setup, you can ask Claude:
- "Get the transcript from https://youtube.com/watch?v=VIDEO_ID"
- "Analyze this trading video for key insights: [URL]"
- "Extract actionable strategies from this YouTube video: [URL]"

### Option B: Python Library Implementation (RECOMMENDED)

**1. Install Dependencies:**
```bash
pip install youtube-transcript-api yt-dlp
```

**2. Update requirements.txt:**
Add these lines to `/Users/ganapolsky_i/workspace/git/igor/trading/requirements.txt`:
```
youtube-transcript-api==0.6.2
yt-dlp==2024.10.7
```

---

## Code Examples

### Example 1: Basic YouTube Video Analyzer

Create `/Users/ganapolsky_i/workspace/git/igor/trading/src/core/youtube_analyzer.py`:

```python
"""
YouTube Video Analysis Module for Trading System

Extracts video metadata, transcripts, and analyzes content for trading insights.
Integrates with MultiLLMAnalyzer for AI-powered analysis.
"""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)
import yt_dlp

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Container for YouTube video metadata."""
    video_id: str
    title: str
    description: str
    channel: str
    duration: int  # seconds
    upload_date: str
    view_count: int
    like_count: Optional[int]
    url: str


@dataclass
class TranscriptEntry:
    """Container for transcript entry with timestamp."""
    text: str
    start: float  # seconds
    duration: float


@dataclass
class VideoAnalysis:
    """Container for video analysis results."""
    metadata: VideoMetadata
    transcript: str
    transcript_entries: List[TranscriptEntry]
    trading_insights: List[str]
    sentiment_score: float
    key_strategies: List[str]
    actionable_items: List[str]
    risk_factors: List[str]
    confidence: float
    timestamp: float


class YouTubeAnalyzer:
    """
    YouTube video analyzer for extracting trading insights.

    This class provides methods to:
    - Extract video metadata
    - Download transcripts with timestamps
    - Analyze content for trading insights
    - Identify actionable strategies
    """

    def __init__(self):
        """Initialize the YouTube analyzer."""
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        logger.info("Initialized YouTubeAnalyzer")

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """
        Extract video ID from YouTube URL.

        Args:
            url: YouTube URL (various formats supported)

        Returns:
            Video ID or None if not found

        Examples:
            >>> extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            'dQw4w9WgXcQ'
            >>> extract_video_id("https://youtu.be/dQw4w9WgXcQ")
            'dQw4w9WgXcQ'
        """
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'([a-zA-Z0-9_-]{11})$'  # Just the ID
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def get_metadata(self, video_url: str) -> Optional[VideoMetadata]:
        """
        Extract video metadata using yt-dlp.

        Args:
            video_url: YouTube video URL or ID

        Returns:
            VideoMetadata object or None if extraction fails
        """
        video_id = self.extract_video_id(video_url)
        if not video_id:
            logger.error(f"Could not extract video ID from: {video_url}")
            return None

        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

                return VideoMetadata(
                    video_id=video_id,
                    title=info.get('title', 'Unknown'),
                    description=info.get('description', ''),
                    channel=info.get('uploader', 'Unknown'),
                    duration=info.get('duration', 0),
                    upload_date=info.get('upload_date', ''),
                    view_count=info.get('view_count', 0),
                    like_count=info.get('like_count'),
                    url=f"https://www.youtube.com/watch?v={video_id}"
                )
        except Exception as e:
            logger.error(f"Error extracting metadata for {video_id}: {str(e)}")
            return None

    def get_transcript(self, video_url: str, languages: List[str] = ['en']) -> Optional[List[TranscriptEntry]]:
        """
        Extract transcript with timestamps.

        Args:
            video_url: YouTube video URL or ID
            languages: List of preferred languages (default: ['en'])

        Returns:
            List of TranscriptEntry objects or None if extraction fails
        """
        video_id = self.extract_video_id(video_url)
        if not video_id:
            logger.error(f"Could not extract video ID from: {video_url}")
            return None

        try:
            # Get transcript
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)

            # Convert to TranscriptEntry objects
            entries = [
                TranscriptEntry(
                    text=entry['text'],
                    start=entry['start'],
                    duration=entry['duration']
                )
                for entry in transcript_list
            ]

            logger.info(f"Successfully extracted {len(entries)} transcript entries for {video_id}")
            return entries

        except TranscriptsDisabled:
            logger.warning(f"Transcripts are disabled for video {video_id}")
            return None
        except NoTranscriptFound:
            logger.warning(f"No transcript found for video {video_id} in languages {languages}")
            return None
        except VideoUnavailable:
            logger.error(f"Video {video_id} is unavailable")
            return None
        except Exception as e:
            logger.error(f"Error extracting transcript for {video_id}: {str(e)}")
            return None

    def format_transcript_for_analysis(self, entries: List[TranscriptEntry], include_timestamps: bool = True) -> str:
        """
        Format transcript entries into a readable text for analysis.

        Args:
            entries: List of TranscriptEntry objects
            include_timestamps: Whether to include timestamps

        Returns:
            Formatted transcript string
        """
        if include_timestamps:
            lines = [
                f"[{self._format_timestamp(entry.start)}] {entry.text}"
                for entry in entries
            ]
        else:
            lines = [entry.text for entry in entries]

        return "\n".join(lines)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """Convert seconds to MM:SS format."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    async def analyze_video_for_trading(
        self,
        video_url: str,
        llm_analyzer,  # MultiLLMAnalyzer instance
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a YouTube video for trading insights using MultiLLMAnalyzer.

        Args:
            video_url: YouTube video URL
            llm_analyzer: Instance of MultiLLMAnalyzer

        Returns:
            Dictionary containing analysis results
        """
        # Get metadata
        metadata = self.get_metadata(video_url)
        if not metadata:
            return None

        # Get transcript
        transcript_entries = self.get_transcript(video_url)
        if not transcript_entries:
            logger.warning(f"No transcript available for {video_url}")
            return None

        # Format transcript
        full_transcript = self.format_transcript_for_analysis(transcript_entries, include_timestamps=True)

        # Prepare analysis prompt
        prompt = f"""Analyze this YouTube trading video for actionable insights.

Video Title: {metadata.title}
Channel: {metadata.channel}
Duration: {metadata.duration // 60} minutes
Views: {metadata.view_count:,}

Transcript:
{full_transcript[:8000]}  # Limit to avoid token limits

Provide a comprehensive trading analysis in JSON format:
{{
    "sentiment": <-1.0 to 1.0>,
    "trading_insights": ["insight1", "insight2", ...],
    "key_strategies": ["strategy1", "strategy2", ...],
    "actionable_items": ["action1", "action2", ...],
    "risk_factors": ["risk1", "risk2", ...],
    "recommended_stocks": ["TICKER1", "TICKER2", ...],
    "time_horizon": "<short/medium/long term>",
    "confidence": <0.0 to 1.0>
}}

Focus on:
1. Specific trading strategies mentioned
2. Stock tickers and sectors discussed
3. Market outlook and sentiment
4. Risk management advice
5. Entry/exit points if mentioned
6. Actionable recommendations
"""

        system_prompt = """You are an expert trading analyst specializing in extracting actionable insights from trading content.
Focus on concrete, implementable strategies and avoid general market commentary.
Identify specific tickers, strategies, and risk factors."""

        try:
            # Query LLMs
            if llm_analyzer.use_async:
                responses = await llm_analyzer._query_all_llms_async(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.3,
                    max_tokens=2000
                )
            else:
                responses = llm_analyzer._query_all_llms_sync(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.3,
                    max_tokens=2000
                )

            # Parse responses
            import json
            all_insights = []
            all_strategies = []
            all_actions = []
            all_risks = []
            all_stocks = []
            sentiment_scores = []
            confidences = []

            for response in responses:
                if response.success and response.content:
                    try:
                        data = json.loads(response.content)
                        if 'trading_insights' in data:
                            all_insights.extend(data['trading_insights'])
                        if 'key_strategies' in data:
                            all_strategies.extend(data['key_strategies'])
                        if 'actionable_items' in data:
                            all_actions.extend(data['actionable_items'])
                        if 'risk_factors' in data:
                            all_risks.extend(data['risk_factors'])
                        if 'recommended_stocks' in data:
                            all_stocks.extend(data['recommended_stocks'])
                        if 'sentiment' in data:
                            sentiment_scores.append(data['sentiment'])
                        if 'confidence' in data:
                            confidences.append(data['confidence'])
                    except json.JSONDecodeError as e:
                        logger.warning(f"Error parsing response from {response.model}: {str(e)}")

            # Aggregate results
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

            return {
                'metadata': {
                    'video_id': metadata.video_id,
                    'title': metadata.title,
                    'channel': metadata.channel,
                    'url': metadata.url,
                    'duration': metadata.duration,
                    'views': metadata.view_count
                },
                'transcript_length': len(transcript_entries),
                'sentiment_score': avg_sentiment,
                'trading_insights': list(set(all_insights))[:15],
                'key_strategies': list(set(all_strategies))[:10],
                'actionable_items': list(set(all_actions))[:10],
                'risk_factors': list(set(all_risks))[:8],
                'recommended_stocks': list(set(all_stocks))[:10],
                'confidence': avg_confidence,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error analyzing video: {str(e)}")
            return None

    def extract_key_timestamps(
        self,
        entries: List[TranscriptEntry],
        keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract timestamps where specific keywords are mentioned.

        Args:
            entries: List of TranscriptEntry objects
            keywords: List of keywords to search for

        Returns:
            List of dictionaries with timestamp, text, and keyword
        """
        results = []

        for entry in entries:
            text_lower = entry.text.lower()
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    results.append({
                        'timestamp': entry.start,
                        'formatted_time': self._format_timestamp(entry.start),
                        'text': entry.text,
                        'keyword': keyword
                    })

        return results

    def batch_analyze_videos(
        self,
        video_urls: List[str],
        llm_analyzer
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple videos in batch.

        Args:
            video_urls: List of YouTube video URLs
            llm_analyzer: MultiLLMAnalyzer instance

        Returns:
            List of analysis results
        """
        import asyncio

        async def analyze_all():
            tasks = [
                self.analyze_video_for_trading(url, llm_analyzer)
                for url in video_urls
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)

        results = asyncio.run(analyze_all())

        # Filter out errors and None results
        valid_results = [r for r in results if r and not isinstance(r, Exception)]

        logger.info(f"Successfully analyzed {len(valid_results)}/{len(video_urls)} videos")
        return valid_results


# Example usage
if __name__ == "__main__":
    import asyncio
    from multi_llm_analysis import MultiLLMAnalyzer

    async def main():
        # Initialize analyzers
        youtube_analyzer = YouTubeAnalyzer()
        llm_analyzer = MultiLLMAnalyzer()

        # Example: Analyze a trading video
        video_url = "https://www.youtube.com/watch?v=EXAMPLE_VIDEO_ID"

        # Get metadata
        metadata = youtube_analyzer.get_metadata(video_url)
        if metadata:
            print(f"Title: {metadata.title}")
            print(f"Channel: {metadata.channel}")
            print(f"Views: {metadata.view_count:,}")

        # Get transcript
        transcript = youtube_analyzer.get_transcript(video_url)
        if transcript:
            print(f"\nTranscript entries: {len(transcript)}")
            print(f"First entry: {transcript[0].text}")

        # Analyze for trading insights
        analysis = await youtube_analyzer.analyze_video_for_trading(video_url, llm_analyzer)
        if analysis:
            print(f"\nTrading Analysis:")
            print(f"Sentiment: {analysis['sentiment_score']:.2f}")
            print(f"Key Strategies: {analysis['key_strategies'][:3]}")
            print(f"Recommended Stocks: {analysis['recommended_stocks']}")

        # Extract key timestamps
        keywords = ['buy', 'sell', 'bearish', 'bullish', 'risk']
        timestamps = youtube_analyzer.extract_key_timestamps(transcript, keywords)
        print(f"\nKey Timestamps:")
        for ts in timestamps[:5]:
            print(f"  {ts['formatted_time']} - {ts['keyword']}: {ts['text']}")

    asyncio.run(main())
```

### Example 2: Integration with Trading System

Create `/Users/ganapolsky_i/workspace/git/igor/trading/src/strategies/youtube_strategy.py`:

```python
"""
YouTube-Driven Trading Strategy

Monitors specific YouTube channels for trading insights and generates signals.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from src.core.youtube_analyzer import YouTubeAnalyzer
from src.core.multi_llm_analysis import MultiLLMAnalyzer

logger = logging.getLogger(__name__)


class YouTubeStrategy:
    """
    Trading strategy based on YouTube video analysis.

    Monitors specific channels/videos and generates trading signals
    based on sentiment and recommended actions.
    """

    def __init__(
        self,
        openrouter_api_key: str,
        watched_channels: Optional[List[str]] = None,
        sentiment_threshold: float = 0.6,
        confidence_threshold: float = 0.7
    ):
        """
        Initialize YouTube strategy.

        Args:
            openrouter_api_key: API key for LLM analysis
            watched_channels: List of channel IDs/names to monitor
            sentiment_threshold: Minimum sentiment for buy signals
            confidence_threshold: Minimum confidence for signals
        """
        self.youtube_analyzer = YouTubeAnalyzer()
        self.llm_analyzer = MultiLLMAnalyzer(api_key=openrouter_api_key)

        self.watched_channels = watched_channels or [
            # Add popular trading YouTube channels here
            "Financial Education",
            "Meet Kevin",
            "Graham Stephan"
        ]

        self.sentiment_threshold = sentiment_threshold
        self.confidence_threshold = confidence_threshold

        logger.info(f"Initialized YouTubeStrategy monitoring {len(self.watched_channels)} channels")

    async def analyze_video(self, video_url: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a single video and generate trading signals.

        Args:
            video_url: YouTube video URL

        Returns:
            Trading signal dictionary or None
        """
        analysis = await self.youtube_analyzer.analyze_video_for_trading(
            video_url,
            self.llm_analyzer
        )

        if not analysis:
            return None

        # Generate signals based on analysis
        signals = self._generate_signals(analysis)

        return {
            'video': analysis['metadata'],
            'analysis': analysis,
            'signals': signals,
            'timestamp': datetime.now().isoformat()
        }

    def _generate_signals(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate trading signals from video analysis.

        Args:
            analysis: Video analysis results

        Returns:
            List of trading signals
        """
        signals = []

        # Check confidence threshold
        if analysis['confidence'] < self.confidence_threshold:
            logger.info(f"Skipping signals - confidence {analysis['confidence']:.2f} below threshold")
            return signals

        sentiment = analysis['sentiment_score']
        stocks = analysis['recommended_stocks']

        # Generate buy signals for bullish sentiment
        if sentiment >= self.sentiment_threshold:
            for stock in stocks:
                signals.append({
                    'action': 'BUY',
                    'symbol': stock,
                    'sentiment': sentiment,
                    'confidence': analysis['confidence'],
                    'reasoning': f"Positive sentiment ({sentiment:.2f}) from video analysis",
                    'strategies': analysis['key_strategies'][:3],
                    'risk_factors': analysis['risk_factors'][:3]
                })

        # Generate sell signals for bearish sentiment
        elif sentiment <= -self.sentiment_threshold:
            for stock in stocks:
                signals.append({
                    'action': 'SELL',
                    'symbol': stock,
                    'sentiment': sentiment,
                    'confidence': analysis['confidence'],
                    'reasoning': f"Negative sentiment ({sentiment:.2f}) from video analysis",
                    'risk_factors': analysis['risk_factors'][:3]
                })

        logger.info(f"Generated {len(signals)} trading signals")
        return signals

    async def analyze_video_list(self, video_urls: List[str]) -> Dict[str, Any]:
        """
        Analyze multiple videos and aggregate signals.

        Args:
            video_urls: List of YouTube video URLs

        Returns:
            Aggregated analysis and signals
        """
        results = []
        all_signals = []

        for url in video_urls:
            result = await self.analyze_video(url)
            if result:
                results.append(result)
                all_signals.extend(result['signals'])

        # Aggregate signals by symbol
        symbol_signals = {}
        for signal in all_signals:
            symbol = signal['symbol']
            if symbol not in symbol_signals:
                symbol_signals[symbol] = []
            symbol_signals[symbol].append(signal)

        # Calculate aggregate sentiment per symbol
        aggregated = []
        for symbol, signals in symbol_signals.items():
            avg_sentiment = sum(s['sentiment'] for s in signals) / len(signals)
            avg_confidence = sum(s['confidence'] for s in signals) / len(signals)

            # Determine action based on consensus
            buy_count = sum(1 for s in signals if s['action'] == 'BUY')
            sell_count = sum(1 for s in signals if s['action'] == 'SELL')

            if buy_count > sell_count:
                action = 'BUY'
            elif sell_count > buy_count:
                action = 'SELL'
            else:
                action = 'HOLD'

            aggregated.append({
                'symbol': symbol,
                'action': action,
                'sentiment': avg_sentiment,
                'confidence': avg_confidence,
                'signal_count': len(signals),
                'buy_signals': buy_count,
                'sell_signals': sell_count
            })

        return {
            'videos_analyzed': len(results),
            'total_signals': len(all_signals),
            'aggregated_signals': aggregated,
            'timestamp': datetime.now().isoformat()
        }

    def filter_high_confidence_signals(
        self,
        signals: List[Dict[str, Any]],
        min_confidence: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Filter signals by confidence level.

        Args:
            signals: List of trading signals
            min_confidence: Minimum confidence threshold

        Returns:
            Filtered signals
        """
        return [s for s in signals if s.get('confidence', 0) >= min_confidence]


# Example usage
if __name__ == "__main__":
    import asyncio
    import os

    async def main():
        # Initialize strategy
        strategy = YouTubeStrategy(
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            sentiment_threshold=0.6,
            confidence_threshold=0.7
        )

        # Example: Analyze specific trading videos
        videos = [
            "https://www.youtube.com/watch?v=VIDEO_ID_1",
            "https://www.youtube.com/watch?v=VIDEO_ID_2",
        ]

        results = await strategy.analyze_video_list(videos)

        print(f"Analyzed {results['videos_analyzed']} videos")
        print(f"Generated {results['total_signals']} total signals")
        print(f"\nAggregated Signals:")
        for signal in results['aggregated_signals']:
            print(f"  {signal['symbol']}: {signal['action']} "
                  f"(sentiment: {signal['sentiment']:.2f}, "
                  f"confidence: {signal['confidence']:.2f})")

    asyncio.run(main())
```

### Example 3: Scheduled Video Monitoring

Create `/Users/ganapolsky_i/workspace/git/igor/trading/youtube_monitor.py`:

```python
"""
YouTube Video Monitor for Trading System

Periodically checks for new videos from watched channels and analyzes them.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from src.core.youtube_analyzer import YouTubeAnalyzer
from src.strategies.youtube_strategy import YouTubeStrategy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YouTubeMonitor:
    """
    Monitors YouTube channels for new trading content.
    """

    def __init__(self, config_path: str = "data/youtube_monitor_config.json"):
        """
        Initialize monitor.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()

        self.strategy = YouTubeStrategy(
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            watched_channels=self.config.get('watched_channels', []),
            sentiment_threshold=self.config.get('sentiment_threshold', 0.6),
            confidence_threshold=self.config.get('confidence_threshold', 0.7)
        )

        self.analyzed_videos = self._load_analyzed_videos()
        self.data_dir = Path("data/youtube_analysis")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> dict:
        """Load configuration from file."""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return self._create_default_config()

    def _create_default_config(self) -> dict:
        """Create default configuration."""
        config = {
            'watched_channels': [
                # Add your preferred trading channels
            ],
            'watched_videos': [
                # Add specific video URLs to monitor
            ],
            'keywords': ['stock', 'trade', 'buy', 'sell', 'market', 'analysis'],
            'sentiment_threshold': 0.6,
            'confidence_threshold': 0.7,
            'check_interval_hours': 24
        }

        # Save default config
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)

        return config

    def _load_analyzed_videos(self) -> set:
        """Load set of already analyzed video IDs."""
        history_file = "data/analyzed_videos.json"
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                data = json.load(f)
                return set(data.get('video_ids', []))
        return set()

    def _save_analyzed_videos(self):
        """Save analyzed video IDs."""
        history_file = "data/analyzed_videos.json"
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        with open(history_file, 'w') as f:
            json.dump({
                'video_ids': list(self.analyzed_videos),
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)

    async def check_and_analyze(self):
        """Check for new videos and analyze them."""
        logger.info("Starting YouTube video check...")

        # Get videos to analyze
        videos_to_analyze = [
            url for url in self.config.get('watched_videos', [])
            if YouTubeAnalyzer.extract_video_id(url) not in self.analyzed_videos
        ]

        if not videos_to_analyze:
            logger.info("No new videos to analyze")
            return

        logger.info(f"Found {len(videos_to_analyze)} new videos to analyze")

        # Analyze videos
        results = await self.strategy.analyze_video_list(videos_to_analyze)

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = self.data_dir / f"analysis_{timestamp}.json"

        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"Saved analysis results to {results_file}")

        # Update analyzed videos
        for url in videos_to_analyze:
            video_id = YouTubeAnalyzer.extract_video_id(url)
            if video_id:
                self.analyzed_videos.add(video_id)

        self._save_analyzed_videos()

        # Log high-confidence signals
        high_conf_signals = [
            s for s in results.get('aggregated_signals', [])
            if s['confidence'] >= 0.8
        ]

        if high_conf_signals:
            logger.info(f"\n{'='*60}")
            logger.info("HIGH CONFIDENCE TRADING SIGNALS:")
            for signal in high_conf_signals:
                logger.info(f"  {signal['symbol']}: {signal['action']} "
                           f"(confidence: {signal['confidence']:.2f})")
            logger.info(f"{'='*60}\n")

    async def run_continuous(self):
        """Run monitor continuously."""
        interval_hours = self.config.get('check_interval_hours', 24)

        logger.info(f"Starting continuous monitoring (checking every {interval_hours}h)")

        while True:
            try:
                await self.check_and_analyze()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")

            logger.info(f"Sleeping for {interval_hours} hours...")
            await asyncio.sleep(interval_hours * 3600)


async def main():
    """Main entry point."""
    monitor = YouTubeMonitor()

    # Check once
    await monitor.check_and_analyze()

    # Or run continuously
    # await monitor.run_continuous()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Integration with Trading System

### Step 1: Add YouTube Analysis to Multi-LLM System

Your existing `/Users/ganapolsky_i/workspace/git/igor/trading/src/core/multi_llm_analysis.py` already has the infrastructure. Simply import and use:

```python
from src.core.youtube_analyzer import YouTubeAnalyzer
from src.core.multi_llm_analysis import MultiLLMAnalyzer

# In your trading logic
youtube_analyzer = YouTubeAnalyzer()
llm_analyzer = MultiLLMAnalyzer()

# Analyze a video
video_url = "https://youtube.com/watch?v=..."
analysis = await youtube_analyzer.analyze_video_for_trading(video_url, llm_analyzer)

# Use analysis for trading decisions
if analysis['sentiment_score'] > 0.7:
    for stock in analysis['recommended_stocks']:
        # Execute buy order
        pass
```

### Step 2: Add to Daily Check-in

Modify `/Users/ganapolsky_i/workspace/git/igor/trading/daily_checkin.py` to include YouTube analysis:

```python
# Add to daily_checkin.py

from src.strategies.youtube_strategy import YouTubeStrategy

async def analyze_youtube_videos():
    """Analyze recent YouTube videos for trading insights."""
    strategy = YouTubeStrategy(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY")
    )

    # List of videos to check daily
    videos = [
        # Add URLs of daily market analysis videos
    ]

    results = await strategy.analyze_video_list(videos)

    return {
        'youtube_analysis': results,
        'high_confidence_signals': [
            s for s in results['aggregated_signals']
            if s['confidence'] >= 0.8
        ]
    }
```

### Step 3: Feed into Decision Engine

Add YouTube signals to your existing trading logic:

```python
# In your main trading loop
youtube_signals = await analyze_youtube_videos()

for signal in youtube_signals['high_confidence_signals']:
    if signal['action'] == 'BUY' and signal['confidence'] > 0.8:
        # Validate with other strategies
        # Execute trade if consensus
        pass
```

---

## Best Practices

### 1. Rate Limiting and Quotas
- YouTube has no official API usage in these libraries, but be respectful
- Add delays between requests: `time.sleep(1)` between videos
- Batch analyze videos during off-hours

### 2. Transcript Quality
- Always check if transcript exists before analysis
- Prefer manually created transcripts over auto-generated
- Handle multiple languages with fallback

```python
# Fallback language handling
def get_transcript_with_fallback(video_id):
    languages = ['en', 'en-US', 'en-GB']
    for lang in languages:
        try:
            return YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
        except:
            continue
    return None
```

### 3. Content Filtering
- Focus on videos with high view counts for quality
- Filter by channel reputation
- Check video age (recent videos more relevant)
- Filter by keywords in title/description

### 4. Signal Validation
- Never trade solely on YouTube analysis
- Use as one input among multiple sources
- Require high confidence (>0.8) for action
- Cross-validate with technical indicators

### 5. Timestamp Extraction
- Extract key moments for manual review
- Create clickable links with timestamps: `https://youtube.com/watch?v=VIDEO_ID&t=120s`
- Store important quotes with timestamps

### 6. Data Storage
```python
# Save all analyses for future reference
analysis_data = {
    'video_id': video_id,
    'title': title,
    'analysis': analysis,
    'timestamp': datetime.now().isoformat()
}

# Store in JSON or database
with open(f'data/youtube_analysis/{video_id}.json', 'w') as f:
    json.dump(analysis_data, f, indent=2)
```

### 7. Error Handling
```python
# Robust error handling
try:
    analysis = await youtube_analyzer.analyze_video_for_trading(url, llm_analyzer)
except Exception as e:
    logger.error(f"Failed to analyze {url}: {str(e)}")
    # Fall back to other signals
    analysis = None
```

---

## Recommended YouTube Channels for Trading Analysis

Consider monitoring these channels (add to config):

**Market Analysis:**
- Bloomberg Television
- CNBC Television
- Yahoo Finance

**Individual Traders:**
- Meet Kevin (Real Estate/Stocks)
- Graham Stephan (Personal Finance/Stocks)
- Andrei Jikh (Dividend Investing)
- Financial Education (Growth Stocks)

**Technical Analysis:**
- Rayner Teo
- The Chart Guys
- Trading 212

**Options/Advanced:**
- Option Alpha
- Tastytrade
- The Options Industry Council

---

## Summary & Next Steps

### Immediate Actions:

1. **Install Dependencies:**
   ```bash
   pip install youtube-transcript-api yt-dlp
   ```

2. **Create YouTube Analyzer Module:**
   - Copy the code examples to your system
   - Test with a few sample videos

3. **Setup MCP Server (Optional):**
   - For manual analysis in Claude Desktop/Code
   - Useful for ad-hoc research

4. **Configure Monitoring:**
   - Add your preferred channels to config
   - Set up daily/weekly analysis schedule

5. **Integrate with Trading System:**
   - Add YouTube signals to decision engine
   - Require high confidence for action
   - Cross-validate with other strategies

### Long-term Enhancements:

1. **Build Video Knowledge Base:**
   - Store all analyses in searchable database
   - Create RAG system for querying past insights

2. **Advanced Features:**
   - Automatic channel discovery
   - Trend detection across multiple videos
   - Sentiment tracking over time
   - Compare analyst predictions vs. actual performance

3. **Real-time Monitoring:**
   - Monitor for new video uploads
   - Instant analysis of breaking news videos
   - Alert system for high-confidence signals

4. **Performance Tracking:**
   - Track accuracy of YouTube-based signals
   - Compare against other strategies
   - Adjust confidence thresholds based on performance

---

## Conclusion

The **Python library approach** is recommended for your automated trading system because:

1. Full integration with your existing MultiLLMAnalyzer
2. Programmatic control over analysis pipeline
3. No external service dependencies
4. Can run in your autonomous trading loop
5. Easy to batch process and schedule

The **MCP server** is recommended as a supplement for manual research and ad-hoc analysis in Claude Desktop/Code.

Both approaches can coexist and complement each other for maximum flexibility.

**Estimated Implementation Time:** 2-4 hours for basic integration, 1-2 days for full production system.

**Expected Value:** High-quality trading insights from professional analysts, early identification of market trends, diversified signal sources beyond traditional indicators.
